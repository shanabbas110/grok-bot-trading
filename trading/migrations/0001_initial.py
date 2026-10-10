# Generated manually for Grok Bot

import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="Agent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=32, unique=True)),
                ("color", models.CharField(default="#3b82f6", max_length=16)),
                ("status", models.CharField(choices=[("stopped", "Stopped"), ("running", "Running"), ("paused", "Paused")], default="stopped", max_length=16)),
                ("strategy_notes", models.TextField(blank=True, default="")),
                ("max_position_pct", models.DecimalField(decimal_places=2, default=Decimal("10"), max_digits=6)),
                ("min_confidence", models.DecimalField(decimal_places=2, default=Decimal("0.60"), max_digits=4)),
                ("preferred_chains", models.JSONField(blank=True, default=list)),
                ("tick_interval_seconds", models.PositiveIntegerField(default=30)),
                ("last_tick_at", models.DateTimeField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="AppSettings",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("paper_mode", models.BooleanField(default=True)),
                ("kill_switch", models.BooleanField(default=False)),
                ("starting_balance", models.DecimalField(decimal_places=2, default=Decimal("1000.00"), max_digits=18)),
                ("cash_balance", models.DecimalField(decimal_places=2, default=Decimal("1000.00"), max_digits=18)),
                ("daily_target_pct", models.DecimalField(decimal_places=2, default=Decimal("15.00"), max_digits=6)),
                ("subscription_amount", models.DecimalField(decimal_places=2, default=Decimal("200.00"), max_digits=18)),
                ("subscription_next_days", models.PositiveIntegerField(default=26)),
                ("total_fees", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18)),
                ("task_count", models.PositiveIntegerField(default=0)),
                ("session_started_at", models.DateTimeField(default=django.utils.timezone.now)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"verbose_name_plural": "App settings"},
        ),
        migrations.CreateModel(
            name="BalanceSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("balance_usd", models.DecimalField(decimal_places=2, max_digits=18)),
                ("equity_usd", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=18)),
                ("recorded_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"ordering": ["recorded_at"]},
        ),
        migrations.CreateModel(
            name="ScannedToken",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32)),
                ("name", models.CharField(blank=True, default="", max_length=128)),
                ("chain", models.CharField(blank=True, default="", max_length=32)),
                ("pair_address", models.CharField(blank=True, default="", max_length=128)),
                ("token_address", models.CharField(blank=True, default="", max_length=128)),
                ("price_usd", models.DecimalField(blank=True, decimal_places=12, max_digits=24, null=True)),
                ("liquidity_usd", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=18)),
                ("volume_24h", models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=18)),
                ("buy_sell_ratio", models.DecimalField(decimal_places=4, default=Decimal("1"), max_digits=8)),
                ("pair_age_hours", models.DecimalField(blank=True, decimal_places=2, max_digits=10, null=True)),
                ("fdv_usd", models.DecimalField(blank=True, decimal_places=2, max_digits=24, null=True)),
                ("rug_score", models.DecimalField(blank=True, decimal_places=2, max_digits=5, null=True)),
                ("rug_notes", models.JSONField(blank=True, default=dict)),
                ("source", models.CharField(default="dexscreener", max_length=32)),
                ("last_seen_at", models.DateTimeField(auto_now=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="TokenStatus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32)),
                ("chain", models.CharField(blank=True, default="", max_length=32)),
                ("state", models.CharField(choices=[("checking", "Checking"), ("approved", "Approved"), ("rejected", "Rejected"), ("trading", "Trading")], default="checking", max_length=16)),
                ("detail", models.CharField(blank=True, default="", max_length=128)),
                ("is_positive", models.BooleanField(default=False)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"ordering": ["-updated_at"]},
        ),
        migrations.CreateModel(
            name="Order",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32)),
                ("chain", models.CharField(blank=True, default="", max_length=32)),
                ("token_address", models.CharField(blank=True, default="", max_length=128)),
                ("side", models.CharField(choices=[("buy", "Buy"), ("sell", "Sell")], max_length=8)),
                ("status", models.CharField(choices=[("pending", "Pending"), ("filled", "Filled"), ("rejected", "Rejected"), ("cancelled", "Cancelled")], default="pending", max_length=16)),
                ("size_pct", models.DecimalField(decimal_places=2, default=Decimal("5"), max_digits=6)),
                ("notional_usd", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("price_usd", models.DecimalField(blank=True, decimal_places=12, max_digits=24, null=True)),
                ("stop_loss_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("take_profit_pct", models.DecimalField(blank=True, decimal_places=2, max_digits=6, null=True)),
                ("confidence", models.DecimalField(blank=True, decimal_places=2, max_digits=4, null=True)),
                ("reason", models.TextField(blank=True, default="")),
                ("rejection_reason", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("agent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="orders", to="trading.agent")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.CreateModel(
            name="Position",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32)),
                ("chain", models.CharField(blank=True, default="", max_length=32)),
                ("token_address", models.CharField(blank=True, default="", max_length=128)),
                ("status", models.CharField(choices=[("open", "Open"), ("closed", "Closed")], default="open", max_length=16)),
                ("entry_price", models.DecimalField(decimal_places=12, max_digits=24)),
                ("quantity", models.DecimalField(decimal_places=8, max_digits=24)),
                ("cost_basis_usd", models.DecimalField(decimal_places=4, max_digits=18)),
                ("stop_loss_price", models.DecimalField(blank=True, decimal_places=12, max_digits=24, null=True)),
                ("take_profit_price", models.DecimalField(blank=True, decimal_places=12, max_digits=24, null=True)),
                ("timeout_at", models.DateTimeField(blank=True, null=True)),
                ("exit_price", models.DecimalField(blank=True, decimal_places=12, max_digits=24, null=True)),
                ("realized_pnl_usd", models.DecimalField(blank=True, decimal_places=4, max_digits=18, null=True)),
                ("close_reason", models.CharField(blank=True, default="", max_length=32)),
                ("opened_at", models.DateTimeField(auto_now_add=True)),
                ("closed_at", models.DateTimeField(blank=True, null=True)),
                ("agent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="positions", to="trading.agent")),
            ],
            options={"ordering": ["-opened_at"]},
        ),
        migrations.CreateModel(
            name="Trade",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("symbol", models.CharField(max_length=32)),
                ("entry_price", models.DecimalField(decimal_places=12, max_digits=24)),
                ("exit_price", models.DecimalField(decimal_places=12, max_digits=24)),
                ("quantity", models.DecimalField(decimal_places=8, max_digits=24)),
                ("pnl_usd", models.DecimalField(decimal_places=4, max_digits=18)),
                ("fees_usd", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18)),
                ("is_win", models.BooleanField()),
                ("closed_at", models.DateTimeField(auto_now_add=True)),
                ("agent", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="trades", to="trading.agent")),
            ],
            options={"ordering": ["-closed_at"]},
        ),
        migrations.CreateModel(
            name="Execution",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("fill_price", models.DecimalField(decimal_places=12, max_digits=24)),
                ("quantity", models.DecimalField(decimal_places=8, max_digits=24)),
                ("fee_usd", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18)),
                ("slippage_usd", models.DecimalField(decimal_places=4, default=Decimal("0"), max_digits=18)),
                ("executed_at", models.DateTimeField(auto_now_add=True)),
                ("order", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="executions", to="trading.order")),
            ],
            options={"ordering": ["-executed_at"]},
        ),
        migrations.CreateModel(
            name="ActivityLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("tag", models.CharField(choices=[("info", "Info"), ("warn", "Warn"), ("risk", "Risk"), ("scan", "Scan"), ("exec", "Exec"), ("big", "Big")], default="info", max_length=16)),
                ("message", models.TextField()),
                ("symbol", models.CharField(blank=True, default="", max_length=32)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("agent", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to="trading.agent")),
            ],
            options={"ordering": ["-created_at"]},
        ),
        migrations.AddIndex(
            model_name="scannedtoken",
            index=models.Index(fields=["symbol", "chain"], name="trading_sca_symbol_6f0e2a_idx"),
        ),
    ]
