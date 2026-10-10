from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("trading", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="appsettings",
            name="config",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.AddField(
            model_name="agent",
            name="strategy_preset",
            field=models.CharField(
                choices=[
                    ("conservative_scalper", "Conservative scalper"),
                    ("balanced_scalper", "Balanced scalper"),
                    ("aggressive_scalper", "Aggressive scalper"),
                    ("custom", "Custom"),
                ],
                default="balanced_scalper",
                max_length=32,
            ),
        ),
    ]
