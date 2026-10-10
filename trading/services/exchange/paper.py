from decimal import Decimal

from trading.models import AppSettings, ScannedToken
from trading.services.runtime_config import get_config

from .base import ExchangeAdapter


class PaperExchangeAdapter(ExchangeAdapter):
    def get_price(self, symbol: str, chain: str = "", token_address: str = "") -> Decimal:
        qs = ScannedToken.objects.filter(symbol__iexact=symbol)
        if chain:
            qs = qs.filter(chain=chain)
        if token_address:
            qs = qs.filter(token_address=token_address)
        token = qs.order_by("-last_seen_at").first()
        if token and token.price_usd:
            return Decimal(token.price_usd)
        # deterministic fallback for tests / unknown symbols
        seed = sum(ord(c) for c in symbol.upper()) % 1000
        return Decimal("0.001") * (1 + Decimal(seed) / Decimal("1000"))

    def execute_order(
        self,
        side: str,
        symbol: str,
        notional_usd: Decimal,
        price_usd: Decimal,
        chain: str = "",
        token_address: str = "",
    ) -> dict:
        settings_obj = AppSettings.get()
        cfg = get_config()
        fee_bps = Decimal(int(cfg.get("paper_fee_bps", 30))) / Decimal("10000")
        slip_bps = Decimal(int(cfg.get("paper_slippage_bps", 50))) / Decimal("10000")

        slip_mult = Decimal("1") + slip_bps if side.lower() == "buy" else Decimal("1") - slip_bps
        fill_price = price_usd * slip_mult
        quantity = notional_usd / fill_price if fill_price > 0 else Decimal("0")
        fee_usd = notional_usd * fee_bps
        slippage_usd = abs(fill_price - price_usd) * quantity

        if side.lower() == "buy":
            total_cost = notional_usd + fee_usd
            if settings_obj.cash_balance < total_cost:
                raise ValueError("Insufficient paper balance")
            settings_obj.cash_balance -= total_cost
        else:
            proceeds = notional_usd - fee_usd
            settings_obj.cash_balance += proceeds

        settings_obj.total_fees += fee_usd
        settings_obj.save(update_fields=["cash_balance", "total_fees", "updated_at"])

        return {
            "fill_price": fill_price,
            "quantity": quantity,
            "fee_usd": fee_usd,
            "slippage_usd": slippage_usd,
        }
