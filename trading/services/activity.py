from trading.models import ActivityLog, Agent


def log_activity(tag: str, message: str, symbol: str = "", agent: Agent | None = None):
    ActivityLog.objects.create(tag=tag, message=message, symbol=symbol, agent=agent)
