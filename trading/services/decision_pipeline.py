"""Jev gate + Grok confirmation pipeline."""

from __future__ import annotations

import logging
import time

from trading.services.activity import log_activity
from trading.services.runtime_config import get_config
from trading.services.decision_metrics import DecisionMetrics
from trading.services.grok_decider import GrokDecider
from trading.services.jev_decider import JevDecider
from trading.services.market_signals import build_entry_state, build_exit_state

logger = logging.getLogger(__name__)


class DecisionPipeline:
    def __init__(self):
        self.jev = JevDecider()
        self.grok = GrokDecider()
        self.mode = str(get_config().get("decider_mode", "jev+grok")).lower()

    def _log_jev(self, symbol: str, decision, agent=None, prefix: str = "JEV"):
        msg = f"{prefix} ${symbol} {decision.action} conf={decision.confidence:.2f} {decision.latency_ms:.0f}ms"
        if decision.error:
            msg += f" err={decision.error[:80]}"
        log_activity("jev", msg, symbol=symbol, agent=agent)

    def _log_grok(self, symbol: str, decision: dict, latency_ms: float, agent=None, error: str | None = None):
        action = decision.get("action", "hold")
        conf = float(decision.get("confidence", 0))
        msg = f"GROK ${symbol} {action} conf={conf:.2f} {latency_ms:.0f}ms"
        if error:
            msg += f" err={error[:80]}"
        elif decision.get("reason"):
            msg += f" — {decision['reason'][:60]}"
        log_activity("grok", msg, symbol=symbol, agent=agent)

    def evaluate_entry(self, agent, candidate: dict, portfolio: dict, safety: dict) -> dict | None:
        """
        Returns trade decision dict or None if no trade.
        Keys: action, symbol, size_pct, stop_loss, take_profit, confidence, reason
        """
        symbol = candidate.get("symbol", "").upper()
        state = build_entry_state(candidate, portfolio, agent.name, safety)

        jev_result = None
        if self.mode in ("jev+grok", "jev-only", "mock"):
            jev_result = self.jev.evaluate_entry(state)
            self._log_jev(symbol, jev_result, agent=agent)
            if jev_result.error and self.mode != "mock":
                return None
            cfg = get_config()
            threshold = float(cfg.get("jev_buy_confidence_threshold", 0.72))
            offset = float(getattr(agent, "_jev_threshold_offset", 0) or 0)
            threshold = min(0.99, max(0.5, threshold + offset))
            if self.mode in ("jev+grok", "jev-only"):
                if jev_result.action != "buy" or jev_result.confidence < threshold:
                    return None

        if self.mode == "jev-only":
            if not jev_result or jev_result.action != "buy":
                return None
            return self._defaults_from_jev(jev_result, candidate)

        if self.mode == "grok-only":
            return self._grok_entry(agent, candidate, portfolio)

        if self.mode == "mock":
            if not jev_result or jev_result.action != "buy":
                return None
            grok = self.grok._mock_decide(agent.name, [candidate], portfolio)
            if grok.get("action") != "buy":
                return None
            return self._merge(jev_result, grok, candidate)

        # jev+grok
        grok_decision = self._grok_entry(agent, candidate, portfolio)
        if not grok_decision:
            return None
        if grok_decision.get("action") != "buy":
            return None
        if jev_result and jev_result.action != "buy":
            log_activity("warn", f"Grok buy ${symbol} blocked — Jev did not agree", symbol=symbol, agent=agent)
            return None
        return self._merge(jev_result, grok_decision, candidate)

    def _grok_entry(self, agent, candidate: dict, portfolio: dict) -> dict | None:
        symbol = candidate.get("symbol", "").upper()
        started = time.perf_counter()
        error = None
        try:
            decision = self.grok.decide(agent.name, [candidate], portfolio, allow_mock=False)
        except Exception as e:
            error = f"{type(e).__name__}: {e}"
            decision = {"action": "hold", "symbol": symbol, "confidence": 0}
        latency_ms = (time.perf_counter() - started) * 1000
        if error:
            DecisionMetrics.record("grok", latency_ms, error)
        else:
            DecisionMetrics.record("grok", latency_ms)
        self._log_grok(symbol, decision, latency_ms, agent=agent, error=error)
        if error:
            return None
        min_conf = float(get_config().get("grok_min_confidence", 0.65))
        if float(decision.get("confidence", 0)) < min_conf:
            return None
        return decision

    def _defaults_from_jev(self, jev_result, candidate: dict) -> dict:
        cfg = get_config()
        sl = float(cfg.get("default_stop_loss_pct", 3.0))
        tp = float(cfg.get("default_take_profit_pct", 4.5))
        size = float(cfg.get("default_position_size_pct", 6.0))
        return {
            "action": "buy",
            "symbol": candidate.get("symbol", "").upper(),
            "size_pct": size,
            "stop_loss": sl,
            "take_profit": tp,
            "confidence": jev_result.confidence,
            "reason": f"Jev-only entry ({jev_result.model})",
        }

    def _merge(self, jev_result, grok: dict, candidate: dict) -> dict:
        cfg = get_config()
        sl = float(grok.get("stop_loss") or cfg.get("default_stop_loss_pct", 3.0))
        tp = float(grok.get("take_profit") or cfg.get("default_take_profit_pct", 4.5))
        tp = min(tp, float(cfg.get("max_take_profit_pct", 6.0)))
        sl = min(sl, float(cfg.get("max_stop_loss_pct", 4.0)))
        conf = min(1.0, (float(grok.get("confidence", 0)) + float(jev_result.confidence)) / 2)
        return {
            "action": "buy",
            "symbol": (grok.get("symbol") or candidate.get("symbol", "")).upper(),
            "size_pct": float(grok.get("size_pct") or cfg.get("default_position_size_pct", 6.0)),
            "stop_loss": sl,
            "take_profit": tp,
            "confidence": conf,
            "reason": grok.get("reason") or "Jev+Grok agree",
        }

    def evaluate_exit(self, agent, position: dict, mark_price: float, portfolio: dict) -> bool:
        """Return True if position should be closed."""
        if self.mode == "grok-only":
            return False
        state = build_exit_state(position, mark_price, portfolio, agent.name)
        decision = self.jev.evaluate_exit(state)
        self._log_jev(position.get("symbol", ""), decision, agent=agent, prefix="JEV-EXIT")
        if decision.error:
            return False
        if decision.action == "sell":
            threshold = float(get_config().get("jev_exit_confidence_threshold", 0.6))
            return decision.confidence >= threshold
        return False
