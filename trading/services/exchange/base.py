from abc import ABC, abstractmethod
from decimal import Decimal


class ExchangeAdapter(ABC):
    @abstractmethod
    def get_price(self, symbol: str, chain: str = "", token_address: str = "") -> Decimal:
        raise NotImplementedError

    @abstractmethod
    def execute_order(
        self,
        side: str,
        symbol: str,
        notional_usd: Decimal,
        price_usd: Decimal,
        chain: str = "",
        token_address: str = "",
    ) -> dict:
        """Return fill dict: fill_price, quantity, fee_usd, slippage_usd."""
        raise NotImplementedError
