from django.test import TestCase, override_settings

from trading.models import AppSettings
from trading.services.runtime_config import get_config, validate_config, validate_startup


class RuntimeConfigTests(TestCase):
    def test_validate_accepts_defaults(self):
        errors = validate_config(get_config())
        self.assertEqual(errors, [])

    def test_validate_rejects_bad_decider_mode(self):
        cfg = get_config()
        cfg["decider_mode"] = "invalid"
        errors = validate_config(cfg)
        self.assertTrue(any("decider_mode" in e for e in errors))

    def test_db_override_merges(self):
        row = AppSettings.get()
        row.config = {"jev_buy_confidence_threshold": 0.8}
        row.save()
        self.assertEqual(get_config()["jev_buy_confidence_threshold"], 0.8)

    def test_startup_validation(self):
        validate_startup()
