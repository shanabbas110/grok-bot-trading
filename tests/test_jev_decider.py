from django.test import TestCase, override_settings

from trading.services.jev_decider import JevDecider


class JevDeciderTests(TestCase):
    @override_settings(TYPESAFE_API_KEY="jv_live_test123")
    def test_hosted_endpoint_for_jv_live_key(self):
        decider = JevDecider()
        self.assertEqual(decider._endpoint(), "https://jevtypesafeai.com/api/v1/decide")

    @override_settings(TYPESAFE_API_KEY="ts_official_key")
    def test_typesafe_endpoint_for_non_jv_key(self):
        decider = JevDecider()
        self.assertEqual(decider._endpoint(), "https://api.typesafe.ai/v1/systemone")

    @override_settings(TYPESAFE_API_KEY="")
    def test_mock_entry_buy_on_strong_signals(self):
        decider = JevDecider()
        state = {
            "symbol": "TEST",
            "signals": {"trend": 0.8, "momentum": 0.75, "relative_strength": 0.7, "event_risk": 0.1},
            "safety": {"honeypot": False, "dev_wallet_high": False},
        }
        result = decider.evaluate_entry(state)
        self.assertIsNone(result.error)
        self.assertEqual(result.action, "buy")
        self.assertGreaterEqual(result.confidence, 0.6)
