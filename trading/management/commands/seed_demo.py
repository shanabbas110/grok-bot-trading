from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from trading.models import ActivityLog, Agent, AppSettings, BalanceSnapshot, ScannedToken, Trade
from trading.services.paper_engine import PaperEngine


class Command(BaseCommand):
    help = "Seed demo agents, sample tokens, activity, and balance history"

    def handle(self, *args, **options):
        settings = AppSettings.get()
        settings.paper_mode = True
        settings.kill_switch = False
        settings.starting_balance = Decimal("38.00")
        settings.cash_balance = Decimal("1096.75")
        settings.daily_target_pct = Decimal("15.00")
        settings.subscription_amount = Decimal("200.00")
        settings.subscription_next_days = 26
        settings.task_count = 2270
        settings.session_started_at = timezone.now()
        settings.save()

        agents = [
            ("ODEN", "#3b82f6"),
            ("VIRA", "#22d3ee"),
            ("KESH", "#f97316"),
            ("NOLU", "#22c55e"),
            ("TAMB", "#ec4899"),
            ("RYZO", "#a855f7"),
        ]
        for name, color in agents:
            Agent.objects.update_or_create(name=name, defaults={"color": color, "status": Agent.Status.STOPPED})

        kesh = Agent.objects.get(name="KESH")
        kesh.status = Agent.Status.RUNNING
        kesh.save()

        tokens = [
            ("BRAWL", "solana", 0.00042, 120000, 85000),
            ("GROM", "solana", 0.0011, 95000, 62000),
            ("VOLK", "ethereum", 0.0087, 210000, 140000),
            ("MIZZ", "solana", 0.00031, 88000, 120000),
            ("TAFFY", "solana", 0.00087, 76000, 55000),
        ]
        for sym, chain, price, liq, vol in tokens:
            ScannedToken.objects.update_or_create(
                symbol=sym,
                chain=chain,
                token_address=f"demo_{sym.lower()}",
                defaults={
                    "price_usd": Decimal(str(price)),
                    "liquidity_usd": Decimal(str(liq)),
                    "volume_24h": Decimal(str(vol)),
                    "buy_sell_ratio": Decimal("1.35"),
                    "source": "seed",
                },
            )

        ActivityLog.objects.all().delete()
        samples = [
            ("risk", "LP locked 56d • $BRAWL", "BRAWL"),
            ("scan", "1200 new pairs, 4 with LP > $50k", ""),
            ("big", "SOLD $MIZZ x4.9 +$621.08", "MIZZ"),
            ("exec", "BUY 4.00 SOL $TAFFY @ $0.00087", "TAFFY"),
            ("warn", "Skipping $GROM: dev wallet 18.2%", "GROM"),
        ]
        for tag, msg, sym in samples:
            ActivityLog.objects.create(tag=tag, message=msg, symbol=sym, agent=kesh)

        Trade.objects.all().delete()
        for i in range(50):
            Trade.objects.create(
                agent=kesh,
                symbol="MIZZ",
                entry_price=Decimal("0.0003"),
                exit_price=Decimal("0.00035"),
                quantity=Decimal("1000"),
                pnl_usd=Decimal("50"),
                is_win=True,
            )
        for i in range(10):
            Trade.objects.create(
                agent=Agent.objects.get(name="ODEN"),
                symbol="GROM",
                entry_price=Decimal("0.001"),
                exit_price=Decimal("0.0009"),
                quantity=Decimal("500"),
                pnl_usd=Decimal("-50"),
                is_win=False,
            )

        BalanceSnapshot.objects.all().delete()
        steps = [38, 45, 62, 98, 150, 280, 420, 650, 890, 1096.75]
        for i, bal in enumerate(steps):
            BalanceSnapshot.objects.create(balance_usd=Decimal(str(bal)), equity_usd=Decimal(str(bal)))

        PaperEngine().record_balance_snapshot()
        self.stdout.write(self.style.SUCCESS("Demo data seeded. KESH is running; start worker for live ticks."))
