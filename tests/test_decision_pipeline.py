from django.test import TestCase, override_settings

from trading.models import Agent
from trading.services.decision_pipeline import DecisionPipeline


@override_settings(
    DECIDER_MODE="mock",
    JEV_BUY_CONFIDENCE_THRESHOLD=0.6,
    GROK_MIN_CONFIDENCE=0.6,
    DEFAULT_STOP_LOSS_PCT=3,
    DEFAULT_TAKE_PROFIT_PCT=4.5,
)
class DecisionPipelineTests(TestCase):
    def setUp(self):
        self.agent = Agent.objects.create(name="KESH")
        self.candidate = {
            "symbol": "TAFFY",
            "chain": "solana",
            "token_address": "x",
            "price_usd": 0.001,
            "liquidity_usd": 120000,
            "volume_24h": 90000,
            "buy_sell_ratio": 1.4,
            "pair_age_hours": 48,
        }
        self.portfolio = {"cash": 1000, "open_positions": 0}

    def test_mock_pipeline_returns_buy(self):
        pipe = DecisionPipeline()
        decision = pipe.evaluate_entry(self.agent, self.candidate, self.portfolio, {"honeypot": False})
        self.assertIsNotNone(decision)
        self.assertEqual(decision["action"], "buy")
        self.assertLessEqual(decision["take_profit"], 6.0)

    @override_settings(DECIDER_MODE="jev-only", JEV_BUY_CONFIDENCE_THRESHOLD=0.9)
    def test_jev_only_rejects_low_confidence(self):
        pipe = DecisionPipeline()
        weak = {**self.candidate, "buy_sell_ratio": 0.7, "volume_24h": 500, "liquidity_usd": 40000}
        decision = pipe.evaluate_entry(self.agent, weak, self.portfolio, {})
        self.assertIsNone(decision)
