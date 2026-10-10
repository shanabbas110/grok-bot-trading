from decimal import Decimal

from django.utils import timezone

from trading.models import Agent, AppSettings, Order, Position, ScannedToken, TokenStatus
from trading.services.activity import log_activity
from trading.services.grok_decider import GrokDecider
from trading.services.paper_engine import PaperEngine
from trading.services.risk_guard import RiskGuard, TradeIntent


class AgentRunner:
    def __init__(self):
        self.decider = GrokDecider()
        self.paper = PaperEngine()

    def run_agent(self, agent: Agent):
        settings = AppSettings.get()
        if settings.kill_switch:
            return

        candidates = list(
            ScannedToken.objects.order_by("-volume_24h", "-liquidity_usd")[:12].values(
                "symbol",
                "chain",
                "token_address",
                "price_usd",
                "liquidity_usd",
                "volume_24h",
                "buy_sell_ratio",
            )
        )
        for c in candidates:
            c["price_usd"] = float(c["price_usd"] or 0)

        portfolio = {
            "cash": float(settings.cash_balance),
            "starting": float(settings.starting_balance),
            "open_positions": Position.objects.filter(status=Position.Status.OPEN, agent=agent).count(),
        }

        decision = self.decider.decide(agent.name, candidates, portfolio)
        settings.task_count += 1
        settings.save(update_fields=["task_count", "updated_at"])

        agent.last_tick_at = timezone.now()
        agent.save(update_fields=["last_tick_at"])

        if decision.get("action", "hold") == "hold":
            return

        symbol = decision.get("symbol", "").upper()
        token = ScannedToken.objects.filter(symbol__iexact=symbol).order_by("-last_seen_at").first()
        price = Decimal(str(token.price_usd if token and token.price_usd else decision.get("price", 0.001)))

        intent = TradeIntent(
            action=decision["action"],
            symbol=symbol,
            size_pct=float(decision.get("size_pct", 0)),
            stop_loss=float(decision.get("stop_loss")) if decision.get("stop_loss") is not None else None,
            take_profit=float(decision.get("take_profit")) if decision.get("take_profit") is not None else None,
            confidence=float(decision.get("confidence", 0)),
            price_usd=price,
            chain=token.chain if token else "",
            token_address=token.token_address if token else "",
        )

        guard = RiskGuard(agent=agent)
        risk = guard.evaluate(intent)
        if not risk.allowed:
            order = Order.objects.create(
                agent=agent,
                symbol=symbol or "?",
                chain=intent.chain,
                token_address=intent.token_address,
                side=Order.Side.BUY if intent.action == "buy" else Order.Side.SELL,
                status=Order.Status.REJECTED,
                size_pct=Decimal(str(intent.size_pct)),
                confidence=Decimal(str(intent.confidence)),
                reason=decision.get("reason", ""),
                rejection_reason=risk.reason,
            )
            TokenStatus.objects.create(
                symbol=symbol or "?",
                chain=intent.chain,
                state=TokenStatus.State.REJECTED,
                detail=f"REJECTED • {intent.action.upper()}",
                is_positive=False,
            )
            log_activity("risk", f"Rejected {symbol}: {risk.reason}", symbol=symbol, agent=agent)
            return

        if intent.action == "buy":
            order = Order.objects.create(
                agent=agent,
                symbol=symbol,
                chain=intent.chain,
                token_address=intent.token_address,
                side=Order.Side.BUY,
                size_pct=Decimal(str(intent.size_pct)),
                stop_loss_pct=Decimal(str(intent.stop_loss)),
                take_profit_pct=Decimal(str(intent.take_profit)),
                confidence=Decimal(str(intent.confidence)),
                reason=decision.get("reason", ""),
            )
            self.paper.process_buy_order(order)

    def run_all_running(self):
        for agent in Agent.objects.filter(status=Agent.Status.RUNNING):
            try:
                self.run_agent(agent)
            except Exception as e:
                log_activity("warn", f"Agent {agent.name} tick error: {e}", agent=agent)
