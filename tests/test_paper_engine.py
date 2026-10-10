from decimal import Decimal

from django.test import TestCase, override_settings

from trading.models import Agent, AppSettings, Order, Position, ScannedToken
from trading.services.paper_engine import PaperEngine


@override_settings(PAPER_FEE_BPS=30, PAPER_SLIPPAGE_BPS=50)
class PaperEngineTests(TestCase):
    def setUp(self):
        self.settings = AppSettings.get()
        self.settings.cash_balance = Decimal("1000")
        self.settings.starting_balance = Decimal("1000")
        self.settings.save()
        self.agent = Agent.objects.create(name="KESH")
        ScannedToken.objects.create(
            symbol="TAFFY",
            chain="solana",
            token_address="taffy",
            price_usd=Decimal("0.001"),
            liquidity_usd=Decimal("100000"),
        )

    def test_buy_creates_position_and_reduces_balance(self):
        order = Order.objects.create(
            agent=self.agent,
            symbol="TAFFY",
            chain="solana",
            token_address="taffy",
            side=Order.Side.BUY,
            size_pct=Decimal("10"),
            stop_loss_pct=Decimal("5"),
            take_profit_pct=Decimal("10"),
        )
        engine = PaperEngine()
        execution = engine.process_buy_order(order)
        self.assertIsNotNone(execution)
        self.settings.refresh_from_db()
        self.assertLess(self.settings.cash_balance, Decimal("1000"))
        self.assertEqual(Position.objects.filter(status=Position.Status.OPEN).count(), 1)

    def test_close_position_on_take_profit(self):
        order = Order.objects.create(
            agent=self.agent,
            symbol="TAFFY",
            chain="solana",
            token_address="taffy",
            side=Order.Side.BUY,
            size_pct=Decimal("10"),
            stop_loss_pct=Decimal("5"),
            take_profit_pct=Decimal("1"),
        )
        engine = PaperEngine()
        engine.process_buy_order(order)
        pos = Position.objects.get(status=Position.Status.OPEN)
        ScannedToken.objects.filter(symbol="TAFFY").update(price_usd=Decimal("0.002"))
        engine.maintain_positions()
        pos.refresh_from_db()
        self.assertEqual(pos.status, Position.Status.CLOSED)
        self.assertEqual(pos.close_reason, "take_profit")
