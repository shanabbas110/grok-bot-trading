from decimal import Decimal

from django.utils import timezone

from trading.models import Agent, AppSettings, Order, Position, ScannedToken, TokenStatus
from trading.services.activity import log_activity
from trading.services.agent_presets import PRESETS
from trading.services.decision_pipeline import DecisionPipeline
from trading.services.market_signals import indicators_summary, safety_from_token
from trading.services.paper_engine import PaperEngine
from trading.services.risk_guard import RiskGuard, TradeIntent


class AgentRunner:
    def __init__(self):
        self.pipeline = DecisionPipeline()
        self.paper = PaperEngine()

    def _portfolio(self, settings, agent: Agent) -> dict:
        return {
            "cash": float(settings.cash_balance),
            "starting": float(settings.starting_balance),
            "open_positions": Position.objects.filter(status=Position.Status.OPEN, agent=agent).count(),
        }

    def run_exit_checks(self, agent: Agent):
        settings = AppSettings.get()
        if settings.kill_switch:
            return
        portfolio = self._portfolio(settings, agent)
        for position in Position.objects.filter(status=Position.Status.OPEN, agent=agent):
            token = (
                ScannedToken.objects.filter(symbol__iexact=position.symbol)
                .order_by("-last_seen_at")
                .first()
            )
            mark = float(token.price_usd) if token and token.price_usd else float(position.entry_price)
            pos_dict = {
                "symbol": position.symbol,
                "chain": position.chain,
                "entry_price": float(position.entry_price),
                "cost_basis_usd": float(position.cost_basis_usd),
            }
            if self.pipeline.evaluate_exit(agent, pos_dict, mark, portfolio):
                self.paper.close_position(position, "jev_exit", Decimal(str(mark)))

    def run_agent(self, agent: Agent):
        settings = AppSettings.get()
        if settings.kill_switch:
            return

        self.run_exit_checks(agent)

        token_rows = ScannedToken.objects.order_by("-volume_24h", "-liquidity_usd")[:12]
        candidates = []
        for t in token_rows:
            c = {
                "symbol": t.symbol,
                "chain": t.chain,
                "token_address": t.token_address,
                "price_usd": float(t.price_usd or 0),
                "liquidity_usd": float(t.liquidity_usd or 0),
                "volume_24h": float(t.volume_24h or 0),
                "buy_sell_ratio": float(t.buy_sell_ratio or 1),
                "pair_age_hours": float(t.pair_age_hours) if t.pair_age_hours else None,
                "fdv_usd": float(t.fdv_usd) if t.fdv_usd else None,
                "rug_score": float(t.rug_score) if t.rug_score else None,
                "_token": t,
            }
            candidates.append(c)

        portfolio = self._portfolio(settings, agent)

        preset = PRESETS.get(agent.strategy_preset, {})
        agent._jev_threshold_offset = float(preset.get("jev_buy_offset", 0))

        decision = None
        for candidate in candidates:
            safety = safety_from_token(candidate["_token"])
            if safety.get("honeypot"):
                continue
            log_activity(
                "scan",
                f"${candidate['symbol']} signals: {indicators_summary(candidate, safety)}",
                symbol=candidate["symbol"],
                agent=agent,
            )
            decision = self.pipeline.evaluate_entry(agent, candidate, portfolio, safety)
            if decision and decision.get("action") == "buy":
                break

        settings.task_count += 1
        settings.save(update_fields=["task_count", "updated_at"])

        agent.last_tick_at = timezone.now()
        agent.save(update_fields=["last_tick_at"])

        if not decision or decision.get("action", "hold") != "buy":
            return

        symbol = decision.get("symbol", "").upper()
        token = ScannedToken.objects.filter(symbol__iexact=symbol).order_by("-last_seen_at").first()
        price = Decimal(str(token.price_usd if token and token.price_usd else decision.get("price", 0.001)))

        intent = TradeIntent(
            action="buy",
            symbol=symbol,
            size_pct=float(decision.get("size_pct", 0)),
            stop_loss=float(decision.get("stop_loss")) if decision.get("stop_loss") is not None else None,
            take_profit=float(decision.get("take_profit")) if decision.get("take_profit") is not None else None,
            confidence=float(decision.get("confidence", 0)),
            price_usd=price,
            chain=token.chain if token else "",
            token_address=token.token_address if token else "",
        )

        guard = RiskGuard(agent=agent)
        risk = guard.evaluate(intent)
        if not risk.allowed:
            Order.objects.create(
                agent=agent,
                symbol=symbol or "?",
                chain=intent.chain,
                token_address=intent.token_address,
                side=Order.Side.BUY,
                status=Order.Status.REJECTED,
                size_pct=Decimal(str(intent.size_pct)),
                confidence=Decimal(str(intent.confidence)),
                reason=decision.get("reason", ""),
                rejection_reason=risk.reason,
            )
            TokenStatus.objects.create(
                symbol=symbol or "?",
                chain=intent.chain,
                state=TokenStatus.State.REJECTED,
                detail=f"REJECTED • BUY",
                is_positive=False,
            )
            log_activity("risk", f"Rejected {symbol}: {risk.reason}", symbol=symbol, agent=agent)
            return

        order = Order.objects.create(
            agent=agent,
            symbol=symbol,
            chain=intent.chain,
            token_address=intent.token_address,
            side=Order.Side.BUY,
            size_pct=Decimal(str(intent.size_pct)),
            stop_loss_pct=Decimal(str(intent.stop_loss)),
            take_profit_pct=Decimal(str(intent.take_profit)),
            confidence=Decimal(str(intent.confidence)),
            reason=decision.get("reason", ""),
        )
        self.paper.process_buy_order(order)

    def run_all_running(self):
        for agent in Agent.objects.filter(status=Agent.Status.RUNNING):
            try:
                self.run_agent(agent)
            except Exception as e:
                log_activity("warn", f"Agent {agent.name} tick error: {e}", agent=agent)
