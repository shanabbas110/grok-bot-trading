from django.apps import AppConfig


class TradingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "trading"

    def ready(self):
        import sys

        skip = any(
            cmd in sys.argv
            for cmd in ("migrate", "makemigrations", "test", "shell", "collectstatic", "bootstrap")
        )
        if skip:
            return
        from trading.services.runtime_config import validate_startup

        validate_startup()
