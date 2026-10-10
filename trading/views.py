import json
from decimal import Decimal

from django.core.serializers.json import DjangoJSONEncoder
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from trading.models import (
    ActivityLog,
    Agent,
    AppSettings,
    BalanceSnapshot,
    Execution,
    Order,
    Position,
    TokenStatus,
    Trade,
)
from trading.services.paper_engine import PaperEngine
from trading.services.scanner import MarketScanner


def _win_rate_stats():
    wins = Trade.objects.filter(is_win=True).count()
    losses = Trade.objects.filter(is_win=False).count()
    closed = wins + losses
    rate = round((wins / closed) * 100) if closed else 0
    return {"wins": wins, "losses": losses, "closed": closed, "rate": rate}


def _dashboard_payload():
    settings = AppSettings.get()
    pnl = settings.cash_balance - settings.starting_balance
    pnl_pct = (float(pnl) / float(settings.starting_balance) * 100) if settings.starting_balance else 0
    wr = _win_rate_stats()

    open_positions = list(
        Position.objects.filter(status=Position.Status.OPEN).values(
            "id", "symbol", "chain", "entry_price", "quantity", "cost_basis_usd", "agent__name"
        )[:20]
    )
    for p in open_positions:
        p["entry_price"] = float(p["entry_price"])
        p["quantity"] = float(p["quantity"])
        p["cost_basis_usd"] = float(p["cost_basis_usd"])

    snapshots = list(BalanceSnapshot.objects.order_by("-recorded_at")[:100])
    snapshots.reverse()
    chart = [{"t": s.recorded_at.isoformat(), "v": float(s.equity_usd or s.balance_usd)} for s in snapshots]
    if not chart:
        chart = [{"t": settings.session_started_at.isoformat(), "v": float(settings.cash_balance)}]

    daily_target = float(settings.daily_target_pct)
    daily_progress = min(100, max(0, pnl_pct)) if pnl_pct > 0 else 0
    if daily_target > 0:
        daily_progress = min(100, (pnl_pct / daily_target) * 100) if pnl_pct > 0 else 0

    elapsed = settings.updated_at - settings.session_started_at
    hours = int(elapsed.total_seconds() // 3600)
    mins = int((elapsed.total_seconds() % 3600) // 60)
    secs = int(elapsed.total_seconds() % 60)

    return {
        "paper_mode": settings.paper_mode,
        "kill_switch": settings.kill_switch,
        "balance": float(settings.cash_balance),
        "starting_balance": float(settings.starting_balance),
        "subscription": float(settings.subscription_amount),
        "subscription_days": settings.subscription_next_days,
        "pnl": float(pnl),
        "pnl_pct": round(pnl_pct, 2),
        "total_fees": float(settings.total_fees),
        "task_count": settings.task_count,
        "win_rate": wr,
        "daily_target_pct": daily_target,
        "daily_progress_pct": round(daily_progress, 1),
        "session_timer": f"{hours:02d}:{mins:02d}:{secs:02d}",
        "chart": chart,
        "token_statuses": list(
            TokenStatus.objects.all()[:12].values("symbol", "state", "detail", "is_positive")
        ),
        "activity": [
            {
                "tag": a.tag,
                "message": a.message,
                "symbol": a.symbol,
                "created_at": a.created_at.isoformat(),
            }
            for a in ActivityLog.objects.all()[:80]
        ],
        "agents": list(
            Agent.objects.all().values("id", "name", "color", "status")
        ),
        "open_positions": open_positions,
        "recent_orders": list(
            Order.objects.all()[:15].values(
                "symbol", "side", "status", "notional_usd", "created_at", "agent__name"
            )
        ),
        "recent_executions": list(
            Execution.objects.select_related("order").all()[:15].values(
                "fill_price", "quantity", "fee_usd", "executed_at", "order__symbol", "order__agent__name"
            )
        ),
        "recent_trades": list(
            Trade.objects.all()[:15].values("symbol", "pnl_usd", "is_win", "closed_at", "agent__name")
        ),
        "live_prices": _live_prices(open_positions),
    }


def _live_prices(open_positions):
    from trading.models import ScannedToken

    symbols = {p["symbol"] for p in open_positions}
    prices = {}
    for sym in symbols:
        t = ScannedToken.objects.filter(symbol__iexact=sym).order_by("-last_seen_at").first()
        prices[sym] = float(t.price_usd) if t and t.price_usd else None
    return prices


@require_GET
def dashboard(request):
    return render(
        request,
        "dashboard.html",
        {"initial": json.dumps(_dashboard_payload(), cls=DjangoJSONEncoder)},
    )


@require_GET
def api_dashboard(request):
    return JsonResponse(_dashboard_payload())


@csrf_exempt
@require_POST
def api_agent_start(request, agent_id):
    agent = get_object_or_404(Agent, pk=agent_id)
    agent.status = Agent.Status.RUNNING
    agent.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": agent.status})


@csrf_exempt
@require_POST
def api_agent_stop(request, agent_id):
    agent = get_object_or_404(Agent, pk=agent_id)
    agent.status = Agent.Status.STOPPED
    agent.save(update_fields=["status"])
    return JsonResponse({"ok": True, "status": agent.status})


@csrf_exempt
@require_POST
def api_kill_switch(request):
    settings = AppSettings.get()
    body = json.loads(request.body or "{}")
    settings.kill_switch = bool(body.get("enabled", not settings.kill_switch))
    settings.save(update_fields=["kill_switch", "updated_at"])
    return JsonResponse({"ok": True, "kill_switch": settings.kill_switch})


@csrf_exempt
@require_POST
def api_paper_reset(request):
    settings = AppSettings.get()
    body = json.loads(request.body or "{}")
    amount = Decimal(str(body.get("amount", settings.starting_balance)))
    settings.cash_balance = amount
    settings.starting_balance = amount
    settings.total_fees = Decimal("0")
    settings.task_count = 0
    settings.save()
    Position.objects.filter(status=Position.Status.OPEN).update(status=Position.Status.CLOSED)
    PaperEngine().record_balance_snapshot()
    return JsonResponse({"ok": True, "balance": float(settings.cash_balance)})


@csrf_exempt
@require_POST
def api_paper_add_funds(request):
    settings = AppSettings.get()
    body = json.loads(request.body or "{}")
    amount = Decimal(str(body.get("amount", "100")))
    settings.cash_balance += amount
    settings.save(update_fields=["cash_balance", "updated_at"])
    PaperEngine().record_balance_snapshot()
    return JsonResponse({"ok": True, "balance": float(settings.cash_balance)})


@csrf_exempt
@require_POST
def api_scan_now(request):
    MarketScanner().scan()
    return JsonResponse({"ok": True})
