from celery import shared_task

from trading.services.agent_runner import AgentRunner
from trading.services.paper_engine import PaperEngine
from trading.services.scanner import MarketScanner


@shared_task
def run_all_agents_tick():
    AgentRunner().run_all_running()


@shared_task
def scan_markets():
    MarketScanner().scan()


@shared_task
def maintain_paper_positions():
    PaperEngine().maintain_positions()
