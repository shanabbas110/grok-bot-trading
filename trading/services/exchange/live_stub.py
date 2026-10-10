from decimal import Decimal

from .base import ExchangeAdapter


class LiveExchangeAdapter(ExchangeAdapter):
    """Stub for future live trading — always disabled."""

    enabled = False

    def get_price(self, symbol: str, chain: str = "", token_address: str = "") -> Decimal:
        raise RuntimeError("Live exchange adapter is disabled. Use paper mode.")

    def execute_order(self, side, symbol, notional_usd, price_usd, chain="", token_address=""):
        raise RuntimeError("Live exchange adapter is disabled. Use paper mode.")
