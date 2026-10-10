import time

from django.core.management.base import BaseCommand

from trading.services.agent_runner import AgentRunner
from trading.services.paper_engine import PaperEngine
from trading.services.scanner import MarketScanner


class Command(BaseCommand):
    help = "Run scanner + agents + position maintenance in a loop (no Celery)"

    def add_arguments(self, parser):
        parser.add_argument("--interval", type=int, default=30)

    def handle(self, *args, **options):
        interval = options["interval"]
        runner = AgentRunner()
        paper = PaperEngine()
        scanner = MarketScanner()
        self.stdout.write(f"Starting loop every {interval}s...")
        while True:
            try:
                scanner.scan()
                runner.run_all_running()
                paper.maintain_positions()
            except Exception as e:
                self.stderr.write(str(e))
            time.sleep(interval)
