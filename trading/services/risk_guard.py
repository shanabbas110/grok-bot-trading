from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings as django_settings
from django.utils import timezone

from trading.models import AppSettings, Order, Position
from trading.services.runtime_config import get_config


@dataclass
class RiskDecision:
    allowed: bool
    reason: str = ""


@dataclass
class TradeIntent:
    action: str
    symbol: str
    size_pct: float
    stop_loss: float | None
    take_profit: float | None
    confidence: float
    price_usd: Decimal
    chain: str = ""
    token_address: str = ""


class RiskGuard:
    def __init__(self, agent=None):
        self.agent = agent
        self.settings = AppSettings.get()

    def _cfg(self):
        return get_config()

    def _max_position_pct(self) -> float:
        cap = float(self._cfg().get("risk_max_position_pct", 15))
        if self.agent and self.agent.max_position_pct:
            return min(float(self.agent.max_position_pct), cap)
        return cap

    def _min_confidence(self) -> float:
        floor = float(self._cfg().get("risk_min_confidence", 0.62))
        if self.agent and self.agent.min_confidence:
            return max(float(self.agent.min_confidence), floor)
        return floor

    def evaluate(self, intent: TradeIntent) -> RiskDecision:
        if self.settings.kill_switch:
            return RiskDecision(False, "Kill switch active")

        if intent.action.lower() in ("hold", "none", "skip"):
            return RiskDecision(False, "No trade action")

        if intent.action.lower() not in ("buy", "sell"):
            return RiskDecision(False, f"Unknown action: {intent.action}")

        if intent.confidence < self._min_confidence():
            return RiskDecision(False, f"Confidence {intent.confidence:.2f} below min {self._min_confidence():.2f}")

        if django_settings.RISK_MANDATORY_SL_TP:
            if intent.stop_loss is None or intent.take_profit is None:
                return RiskDecision(False, "Stop loss and take profit are mandatory")
            if intent.stop_loss <= 0 or intent.take_profit <= 0:
                return RiskDecision(False, "Invalid SL/TP values")

        if intent.size_pct <= 0 or intent.size_pct > self._max_position_pct():
            return RiskDecision(False, f"Size {intent.size_pct}% exceeds max {self._max_position_pct()}%")

        if intent.price_usd <= 0:
            return RiskDecision(False, "Invalid price")

        if intent.price_usd > Decimal("1000000") or intent.price_usd < Decimal("0.0000000001"):
            return RiskDecision(False, "Price sanity check failed")

        open_positions = Position.objects.filter(status=Position.Status.OPEN).count()
        max_open = int(self._cfg().get("risk_max_open_positions", 5))
        if intent.action.lower() == "buy" and open_positions >= max_open:
            return RiskDecision(False, f"Max open positions ({max_open}) reached")

        hour_ago = timezone.now() - timedelta(hours=1)
        recent_trades = Order.objects.filter(created_at__gte=hour_ago, status=Order.Status.FILLED).count()
        max_tph = int(self._cfg().get("risk_max_trades_per_hour", 20))
        if recent_trades >= max_tph:
            return RiskDecision(False, f"Trades/hour limit ({max_tph}) reached")

        starting = float(self.settings.starting_balance)
        cash = float(self.settings.cash_balance)
        kill_pct = float(self._cfg().get("risk_daily_loss_kill_pct", 10))
        daily_loss_limit = starting * (kill_pct / 100.0)
        if cash < starting - daily_loss_limit:
            return RiskDecision(False, "Daily loss kill switch triggered")

        return RiskDecision(True, "OK")
