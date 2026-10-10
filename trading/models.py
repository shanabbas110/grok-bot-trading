from decimal import Decimal

from django.db import models
from django.utils import timezone


class AppSettings(models.Model):
    """Singleton-style app configuration."""

    paper_mode = models.BooleanField(default=True)
    kill_switch = models.BooleanField(default=False)
    starting_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("1000.00"))
    cash_balance = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("1000.00"))
    daily_target_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("15.00"))
    subscription_amount = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("200.00"))
    subscription_next_days = models.PositiveIntegerField(default=26)
    total_fees = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    task_count = models.PositiveIntegerField(default=0)
    session_started_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    config = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name_plural = "App settings"

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class Agent(models.Model):
    class Status(models.TextChoices):
        STOPPED = "stopped", "Stopped"
        RUNNING = "running", "Running"
        PAUSED = "paused", "Paused"

    class StrategyPreset(models.TextChoices):
        CONSERVATIVE = "conservative_scalper", "Conservative scalper"
        BALANCED = "balanced_scalper", "Balanced scalper"
        AGGRESSIVE = "aggressive_scalper", "Aggressive scalper"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=32, unique=True)
    color = models.CharField(max_length=16, default="#3b82f6")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.STOPPED)
    strategy_preset = models.CharField(
        max_length=32, choices=StrategyPreset.choices, default=StrategyPreset.BALANCED
    )
    strategy_notes = models.TextField(blank=True, default="")
    max_position_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("10"))
    min_confidence = models.DecimalField(max_digits=4, decimal_places=2, default=Decimal("0.60"))
    preferred_chains = models.JSONField(default=list, blank=True)
    tick_interval_seconds = models.PositiveIntegerField(default=30)
    last_tick_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ScannedToken(models.Model):
    symbol = models.CharField(max_length=32)
    name = models.CharField(max_length=128, blank=True, default="")
    chain = models.CharField(max_length=32, blank=True, default="")
    pair_address = models.CharField(max_length=128, blank=True, default="")
    token_address = models.CharField(max_length=128, blank=True, default="")
    price_usd = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    liquidity_usd = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    volume_24h = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    buy_sell_ratio = models.DecimalField(max_digits=8, decimal_places=4, default=Decimal("1"))
    pair_age_hours = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    fdv_usd = models.DecimalField(max_digits=24, decimal_places=2, null=True, blank=True)
    rug_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    rug_notes = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=32, default="dexscreener")
    last_seen_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["symbol", "chain"])]


class TokenStatus(models.Model):
    """Per-token dashboard status row."""

    class State(models.TextChoices):
        CHECKING = "checking", "Checking"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        TRADING = "trading", "Trading"

    symbol = models.CharField(max_length=32)
    chain = models.CharField(max_length=32, blank=True, default="")
    state = models.CharField(max_length=16, choices=State.choices, default=State.CHECKING)
    detail = models.CharField(max_length=128, blank=True, default="")
    is_positive = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]


class Order(models.Model):
    class Side(models.TextChoices):
        BUY = "buy", "Buy"
        SELL = "sell", "Sell"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        FILLED = "filled", "Filled"
        REJECTED = "rejected", "Rejected"
        CANCELLED = "cancelled", "Cancelled"

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="orders")
    symbol = models.CharField(max_length=32)
    chain = models.CharField(max_length=32, blank=True, default="")
    token_address = models.CharField(max_length=128, blank=True, default="")
    side = models.CharField(max_length=8, choices=Side.choices)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    size_pct = models.DecimalField(max_digits=6, decimal_places=2, default=Decimal("5"))
    notional_usd = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    price_usd = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    stop_loss_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    take_profit_pct = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    confidence = models.DecimalField(max_digits=4, decimal_places=2, null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    rejection_reason = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class Execution(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="executions")
    fill_price = models.DecimalField(max_digits=24, decimal_places=12)
    quantity = models.DecimalField(max_digits=24, decimal_places=8)
    fee_usd = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    slippage_usd = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    executed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-executed_at"]


class Position(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="positions")
    symbol = models.CharField(max_length=32)
    chain = models.CharField(max_length=32, blank=True, default="")
    token_address = models.CharField(max_length=128, blank=True, default="")
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.OPEN)
    entry_price = models.DecimalField(max_digits=24, decimal_places=12)
    quantity = models.DecimalField(max_digits=24, decimal_places=8)
    cost_basis_usd = models.DecimalField(max_digits=18, decimal_places=4)
    stop_loss_price = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    take_profit_price = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    timeout_at = models.DateTimeField(null=True, blank=True)
    exit_price = models.DecimalField(max_digits=24, decimal_places=12, null=True, blank=True)
    realized_pnl_usd = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    close_reason = models.CharField(max_length=32, blank=True, default="")
    opened_at = models.DateTimeField(auto_now_add=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-opened_at"]


class Trade(models.Model):
    """Closed round-trip summary."""

    agent = models.ForeignKey(Agent, on_delete=models.CASCADE, related_name="trades")
    symbol = models.CharField(max_length=32)
    entry_price = models.DecimalField(max_digits=24, decimal_places=12)
    exit_price = models.DecimalField(max_digits=24, decimal_places=12)
    quantity = models.DecimalField(max_digits=24, decimal_places=8)
    pnl_usd = models.DecimalField(max_digits=18, decimal_places=4)
    fees_usd = models.DecimalField(max_digits=18, decimal_places=4, default=Decimal("0"))
    is_win = models.BooleanField()
    closed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-closed_at"]


class BalanceSnapshot(models.Model):
    balance_usd = models.DecimalField(max_digits=18, decimal_places=2)
    equity_usd = models.DecimalField(max_digits=18, decimal_places=2, default=Decimal("0"))
    recorded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recorded_at"]


class ActivityLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARN = "warn", "Warn"
        RISK = "risk", "Risk"
        SCAN = "scan", "Scan"
        EXEC = "exec", "Exec"
        BIG = "big", "Big"
        JEV = "jev", "Jev"
        GROK = "grok", "Grok"

    tag = models.CharField(max_length=16, choices=Level.choices, default=Level.INFO)
    message = models.TextField()
    symbol = models.CharField(max_length=32, blank=True, default="")
    agent = models.ForeignKey(Agent, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
