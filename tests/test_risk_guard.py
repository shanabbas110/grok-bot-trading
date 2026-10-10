from decimal import Decimal

from django.test import TestCase, override_settings

from trading.models import Agent, AppSettings, Order, Position
from trading.services.risk_guard import RiskGuard, TradeIntent


class RiskGuardTests(TestCase):
    def setUp(self):
        self.settings = AppSettings.get()
        self.settings.kill_switch = False
        self.settings.starting_balance = Decimal("1000")
        self.settings.cash_balance = Decimal("1000")
        self.settings.save()
        self.agent = Agent.objects.create(name="TEST")

    def test_rejects_low_confidence(self):
        guard = RiskGuard(agent=self.agent)
        intent = TradeIntent(
            action="buy",
            symbol="FOO",
            size_pct=5,
            stop_loss=4,
            take_profit=8,
            confidence=0.2,
            price_usd=Decimal("1.0"),
        )
        result = guard.evaluate(intent)
        self.assertFalse(result.allowed)
        self.assertIn("Confidence", result.reason)

    def test_rejects_missing_sl_tp(self):
        guard = RiskGuard(agent=self.agent)
        intent = TradeIntent(
            action="buy",
            symbol="FOO",
            size_pct=5,
            stop_loss=None,
            take_profit=None,
            confidence=0.9,
            price_usd=Decimal("1.0"),
        )
        result = guard.evaluate(intent)
        self.assertFalse(result.allowed)

    def test_rejects_oversized_position(self):
        guard = RiskGuard(agent=self.agent)
        intent = TradeIntent(
            action="buy",
            symbol="FOO",
            size_pct=50,
            stop_loss=4,
            take_profit=8,
            confidence=0.9,
            price_usd=Decimal("1.0"),
        )
        result = guard.evaluate(intent)
        self.assertFalse(result.allowed)

    def test_rejects_max_open_positions(self):
        row = AppSettings.get()
        row.config = {**(row.config or {}), "risk_max_open_positions": 1}
        row.save()
        Position.objects.create(
            agent=self.agent,
            symbol="BAR",
            entry_price=Decimal("1"),
            quantity=Decimal("10"),
            cost_basis_usd=Decimal("10"),
            status=Position.Status.OPEN,
        )
        guard = RiskGuard(agent=self.agent)
        intent = TradeIntent(
            action="buy",
            symbol="FOO",
            size_pct=5,
            stop_loss=4,
            take_profit=8,
            confidence=0.9,
            price_usd=Decimal("1.0"),
        )
        result = guard.evaluate(intent)
        self.assertFalse(result.allowed)

    def test_kill_switch(self):
        self.settings.kill_switch = True
        self.settings.save()
        guard = RiskGuard(agent=self.agent)
        intent = TradeIntent("buy", "FOO", 5, 4, 8, 0.9, Decimal("1"))
        self.assertFalse(guard.evaluate(intent).allowed)

    def test_allows_valid_buy(self):
        guard = RiskGuard(agent=self.agent)
        intent = TradeIntent("buy", "FOO", 5, 4, 8, 0.9, Decimal("0.05"))
        self.assertTrue(guard.evaluate(intent).allowed)
