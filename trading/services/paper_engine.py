from datetime import timedelta
from decimal import Decimal

from django.conf import settings as django_settings
from django.utils import timezone

from trading.models import AppSettings, BalanceSnapshot, Execution, Order, Position, Trade
from trading.services.activity import log_activity
from trading.services.exchange.paper import PaperExchangeAdapter


class PaperEngine:
    def __init__(self):
        self.exchange = PaperExchangeAdapter()

    def record_balance_snapshot(self):
        settings = AppSettings.get()
        open_cost = sum(
            p.cost_basis_usd for p in Position.objects.filter(status=Position.Status.OPEN)
        )
        equity = settings.cash_balance + Decimal(open_cost)
        BalanceSnapshot.objects.create(balance_usd=settings.cash_balance, equity_usd=equity)

    def process_buy_order(self, order: Order) -> Execution | None:
        price = self.exchange.get_price(order.symbol, order.chain, order.token_address)
        settings = AppSettings.get()
        notional = settings.cash_balance * (order.size_pct / Decimal("100"))
        if notional <= 0:
            order.status = Order.Status.REJECTED
            order.rejection_reason = "Zero notional"
            order.save()
            return None

        try:
            fill = self.exchange.execute_order(
                "buy", order.symbol, notional, price, order.chain, order.token_address
            )
        except ValueError as e:
            order.status = Order.Status.REJECTED
            order.rejection_reason = str(e)
            order.save()
            return None

        order.status = Order.Status.FILLED
        order.notional_usd = notional
        order.price_usd = price
        order.save()

        sl_pct = order.stop_loss_pct or Decimal("5")
        tp_pct = order.take_profit_pct or Decimal("10")
        entry = fill["fill_price"]
        stop_loss_price = entry * (Decimal("1") - sl_pct / Decimal("100"))
        take_profit_price = entry * (Decimal("1") + tp_pct / Decimal("100"))

        Position.objects.create(
            agent=order.agent,
            symbol=order.symbol,
            chain=order.chain,
            token_address=order.token_address,
            entry_price=entry,
            quantity=fill["quantity"],
            cost_basis_usd=notional,
            stop_loss_price=stop_loss_price,
            take_profit_price=take_profit_price,
            timeout_at=timezone.now()
            + timedelta(hours=float(getattr(django_settings, "PAPER_POSITION_TIMEOUT_HOURS", 1.5))),
        )

        execution = Execution.objects.create(
            order=order,
            fill_price=fill["fill_price"],
            quantity=fill["quantity"],
            fee_usd=fill["fee_usd"],
            slippage_usd=fill["slippage_usd"],
        )
        log_activity(
            "exec",
            f"BUY {fill['quantity']:.4f} ${order.symbol} @ ${fill['fill_price']}",
            symbol=order.symbol,
            agent=order.agent,
        )
        self.record_balance_snapshot()
        return execution

    def close_position(self, position: Position, reason: str, exit_price: Decimal | None = None):
        if position.status != Position.Status.OPEN:
            return
        price = exit_price or self.exchange.get_price(position.symbol, position.chain, position.token_address)
        notional = price * position.quantity
        fill = self.exchange.execute_order(
            "sell", position.symbol, notional, price, position.chain, position.token_address
        )
        proceeds = notional - fill["fee_usd"]
        pnl = proceeds - position.cost_basis_usd

        position.status = Position.Status.CLOSED
        position.exit_price = fill["fill_price"]
        position.realized_pnl_usd = pnl
        position.close_reason = reason
        position.closed_at = timezone.now()
        position.save()

        Trade.objects.create(
            agent=position.agent,
            symbol=position.symbol,
            entry_price=position.entry_price,
            exit_price=fill["fill_price"],
            quantity=position.quantity,
            pnl_usd=pnl,
            fees_usd=fill["fee_usd"],
            is_win=pnl > 0,
        )

        tag = "big" if pnl > 0 else "warn"
        sign = "+" if pnl >= 0 else ""
        log_activity(
            tag,
            f"SOLD ${position.symbol} {position.quantity:.2f} {sign}${pnl:.2f} ({reason})",
            symbol=position.symbol,
            agent=position.agent,
        )
        self.record_balance_snapshot()

    def maintain_positions(self):
        for position in Position.objects.filter(status=Position.Status.OPEN):
            price = self.exchange.get_price(position.symbol, position.chain, position.token_address)
            if position.stop_loss_price and price <= position.stop_loss_price:
                self.close_position(position, "stop_loss", price)
                continue
            if position.take_profit_price and price >= position.take_profit_price:
                self.close_position(position, "take_profit", price)
                continue
            if position.timeout_at and timezone.now() >= position.timeout_at:
                self.close_position(position, "timeout", price)
