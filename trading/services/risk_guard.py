from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from trading.models import AppSettings, Order, Position


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

    def _max_position_pct(self) -> float:
        if self.agent and self.agent.max_position_pct:
            return min(float(self.agent.max_position_pct), settings.RISK_MAX_POSITION_PCT)
        return settings.RISK_MAX_POSITION_PCT

    def _min_confidence(self) -> float:
        if self.agent and self.agent.min_confidence:
            return max(float(self.agent.min_confidence), settings.RISK_MIN_CONFIDENCE)
        return settings.RISK_MIN_CONFIDENCE

    def evaluate(self, intent: TradeIntent) -> RiskDecision:
        if self.settings.kill_switch:
            return RiskDecision(False, "Kill switch active")

        if intent.action.lower() in ("hold", "none", "skip"):
            return RiskDecision(False, "No trade action")

        if intent.action.lower() not in ("buy", "sell"):
            return RiskDecision(False, f"Unknown action: {intent.action}")

        if intent.confidence < self._min_confidence():
            return RiskDecision(False, f"Confidence {intent.confidence:.2f} below min {self._min_confidence():.2f}")

        if settings.RISK_MANDATORY_SL_TP:
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
        if intent.action.lower() == "buy" and open_positions >= settings.RISK_MAX_OPEN_POSITIONS:
            return RiskDecision(False, f"Max open positions ({settings.RISK_MAX_OPEN_POSITIONS}) reached")

        hour_ago = timezone.now() - timedelta(hours=1)
        recent_trades = Order.objects.filter(created_at__gte=hour_ago, status=Order.Status.FILLED).count()
        if recent_trades >= settings.RISK_MAX_TRADES_PER_HOUR:
            return RiskDecision(False, f"Trades/hour limit ({settings.RISK_MAX_TRADES_PER_HOUR}) reached")

        starting = float(self.settings.starting_balance)
        cash = float(self.settings.cash_balance)
        daily_loss_limit = starting * (settings.RISK_DAILY_LOSS_KILL_PCT / 100.0)
        if cash < starting - daily_loss_limit:
            return RiskDecision(False, "Daily loss kill switch triggered")

        return RiskDecision(True, "OK")
