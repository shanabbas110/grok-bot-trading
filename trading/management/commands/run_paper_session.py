import time
from decimal import Decimal

from trading.services.runtime_config import get_config
from django.core.management.base import BaseCommand
from django.db.models import Sum
from django.utils import timezone

from trading.models import Agent, AppSettings, Trade
from trading.services.agent_runner import AgentRunner
from trading.services.decision_metrics import DecisionMetrics
from trading.services.paper_engine import PaperEngine
from trading.services.scanner import MarketScanner


class Command(BaseCommand):
    help = "Run scanner + agents in paper mode for N minutes, then print a summary"

    def add_arguments(self, parser):
        parser.add_argument("--minutes", type=int, default=5, help="Session length in minutes")
        parser.add_argument("--interval", type=int, default=20, help="Seconds between ticks")

    def handle(self, *args, **options):
        minutes = max(1, options["minutes"])
        interval = max(5, options["interval"])
        started = timezone.now()
        end_ts = started + timezone.timedelta(minutes=minutes)

        DecisionMetrics.reset()
        app = AppSettings.get()
        start_balance = app.cash_balance
        start_fees = app.total_fees

        running = Agent.objects.filter(status=Agent.Status.RUNNING).count()
        if running == 0:
            Agent.objects.update(status=Agent.Status.RUNNING)
            self.stdout.write("No running agents — started all agents for this session.")

        runner = AgentRunner()
        paper = PaperEngine()
        scanner = MarketScanner()

        self.stdout.write(
            f"Paper session: {minutes}m, tick every {interval}s, decider={get_config().get('decider_mode')}"
        )

        ticks = 0
        while timezone.now() < end_ts:
            try:
                scanner.scan()
                runner.run_all_running()
                paper.maintain_positions()
            except Exception as exc:
                self.stderr.write(f"Tick error: {exc}")
            ticks += 1
            remaining = (end_ts - timezone.now()).total_seconds()
            if remaining <= 0:
                break
            time.sleep(min(interval, remaining))

        app.refresh_from_db()
        trades = Trade.objects.filter(closed_at__gte=started)
        wins = trades.filter(is_win=True).count()
        losses = trades.filter(is_win=False).count()
        closed = wins + losses
        pnl_sum = trades.aggregate(total=Sum("pnl_usd"))["total"] or Decimal("0")
        fees_delta = app.total_fees - start_fees
        balance_delta = app.cash_balance - start_balance
        win_rate = round((wins / closed) * 100, 1) if closed else 0.0

        metrics = DecisionMetrics.summary()
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=== Paper session summary ==="))
        self.stdout.write(f"Duration: {minutes} minutes ({ticks} ticks)")
        self.stdout.write(f"Trades closed: {closed} ({wins} wins / {losses} losses) — win rate {win_rate}%")
        self.stdout.write(
            f"Target win rate: {get_config().get('win_rate_target_wins')}/"
            f"{get_config().get('win_rate_target_closed')} "
            f"({round(int(get_config().get('win_rate_target_wins', 50)) / int(get_config().get('win_rate_target_closed', 60)) * 100)}%)"
        )
        self.stdout.write(f"Trade P&L sum: ${float(pnl_sum):,.2f}")
        self.stdout.write(f"Balance change: ${float(balance_delta):,.2f}")
        self.stdout.write(f"Fees (session): ${float(fees_delta):,.4f}")
        self.stdout.write(f"Net after fees (balance Δ): ${float(balance_delta):,.2f}")

        self.stdout.write("\nDecision calls:")
        for model, st in metrics.get("models", {}).items():
            self.stdout.write(
                f"  {model}: {st['calls']} calls, {st['errors']} errors, "
                f"avg latency {st['avg_latency_ms']}ms"
            )
        if metrics.get("errors"):
            self.stdout.write("\nProvider errors (skipped gracefully):")
            for err in metrics["errors"][:20]:
                self.stdout.write(f"  - {err}")
