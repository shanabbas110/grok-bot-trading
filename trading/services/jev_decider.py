"""Jev (TypeSafe) fast decision gate."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass

import os

from django.conf import settings as django_settings

from trading.services.decision_metrics import DecisionMetrics
from trading.services.http_client import HttpClient
from trading.services.runtime_config import get_config

logger = logging.getLogger(__name__)

ENTRY_QUESTIONS = {
    "action": {
        "type": "choice",
        "instructions": (
            "Short-term scalp entry gate. Prefer HOLD unless trend, momentum, and relative_strength "
            "are strong, event_risk is low, and safety flags are clean. "
            "Only BUY when evidence is clearly favorable for a quick tight take-profit."
        ),
        "criteria": {
            "buy": "enter now",
            "hold": "wait",
            "sell": "avoid or short (not used for entry)",
        },
    },
    "entry_quality": {
        "type": "score",
        "instructions": "Overall entry quality for a selective high win-rate scalp.",
        "criteria": ["poor", "weak", "ok", "good", "excellent"],
    },
}

EXIT_QUESTIONS = {
    "action": {
        "type": "choice",
        "instructions": (
            "Manage an open scalp. SELL to exit when momentum fades, risk rises, or "
            "unrealized_pnl_pct is enough to lock gains. HOLD otherwise."
        ),
        "criteria": {"sell": "exit now", "hold": "keep position"},
    },
    "exit_now": {
        "type": "noul",
        "instructions": "Exit this position immediately?",
    },
}


@dataclass
class JevDecision:
    action: str
    confidence: float
    latency_ms: float
    model: str
    raw: dict
    error: str | None = None
    entry_quality: float | None = None

    @property
    def ok(self) -> bool:
        return self.error is None


class JevDecider:
    def __init__(self):
        self.api_key = os.environ.get("TYPESAFE_API_KEY", "") or getattr(django_settings, "TYPESAFE_API_KEY", "")
        self.http = HttpClient(timeout=float(getattr(django_settings, "JEV_TIMEOUT_SECONDS", 30)))
        self.model = str(get_config().get("jev_model", "jev-1.13.0"))

    def _endpoint(self) -> str | None:
        if not self.api_key:
            return None
        if self.api_key.startswith("jv_live_"):
            return "https://jevtypesafeai.com/api/v1/decide"
        return "https://api.typesafe.ai/v1/systemone"

    def _call(self, state: dict, questions: dict) -> JevDecision:
        url = self._endpoint()
        if not url:
            return self._mock(state, questions)

        payload = {"model": self.model, "state": state, "questions": questions}
        started = time.perf_counter()
        try:
            data = self.http.post_json(
                url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            latency_ms = (time.perf_counter() - started) * 1000
            answers = data.get("answers") or {}
            action_block = answers.get("action") or {}
            action = str(action_block.get("choice", "hold")).lower()
            confidence = self._extract_confidence(action_block, action)

            entry_quality = None
            eq = answers.get("entry_quality") or {}
            if "score" in eq:
                entry_quality = float(eq.get("score", 0))

            exit_noul = (answers.get("exit_now") or {}).get("noul")
            cfg = get_config()
            if exit_noul is not None and float(exit_noul) >= float(cfg.get("jev_exit_noul_threshold", 0.65)):
                action = "sell"
                confidence = max(confidence, float(exit_noul))

            model = data.get("model") or self.model
            DecisionMetrics.record("jev", latency_ms)
            return JevDecision(action, confidence, latency_ms, model, data)
        except Exception as e:
            latency_ms = (time.perf_counter() - started) * 1000
            err = f"{type(e).__name__}: {e}"
            logger.warning("Jev request failed: %s", err)
            DecisionMetrics.record("jev", latency_ms, err)
            return JevDecision("hold", 0.0, latency_ms, self.model, {}, error=err)

    @staticmethod
    def _extract_confidence(action_block: dict, action: str) -> float:
        if "confidence" in action_block:
            return float(action_block["confidence"])
        probs = action_block.get("probabilities") or action_block.get("probs") or {}
        if isinstance(probs, dict) and action in probs:
            return float(probs[action])
        if isinstance(probs, dict) and probs:
            return float(max(probs.values()))
        return 0.55 if action in ("buy", "sell") else 0.5

    def evaluate_entry(self, state: dict) -> JevDecision:
        return self._call(state, ENTRY_QUESTIONS)

    def evaluate_exit(self, state: dict) -> JevDecision:
        return self._call(state, EXIT_QUESTIONS)

    def _mock(self, state: dict, questions: dict) -> JevDecision:
        """Rule-based gate when no API key or explicit mock mode."""
        signals = state.get("signals") or {}
        safety = state.get("safety") or {}
        trend = float(signals.get("trend", 0))
        mom = float(signals.get("momentum", 0))
        rs = float(signals.get("relative_strength", 0))
        risk = float(signals.get("event_risk", 0))
        sym = state.get("symbol", "")

        if safety.get("honeypot") or safety.get("dev_wallet_high"):
            return JevDecision("hold", 0.2, 1.0, "mock", {}, error=None)

        score = (trend * 0.35 + mom * 0.35 + rs * 0.3) - risk * 0.4
        is_exit = "exit_now" in questions
        if is_exit:
            pnl = float(state.get("unrealized_pnl_pct", 0))
            tp = float(get_config().get("default_take_profit_pct", 4.5))
            action = "sell" if pnl >= tp or pnl <= -2 else "hold"
            conf = 0.7 if action == "sell" else 0.55
            return JevDecision(action, conf, 1.0, "mock", {})

        if score >= 0.62 and risk < 0.45:
            conf = min(0.92, 0.55 + score * 0.35)
            return JevDecision("buy", round(conf, 3), 1.0, "mock", {})
        return JevDecision("hold", round(0.45 + score * 0.2, 3), 1.0, "mock", {})
