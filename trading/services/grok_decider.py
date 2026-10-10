import json
import logging
import random
from django.conf import settings
from openai import OpenAI

from trading.services.runtime_config import get_config

logger = logging.getLogger(__name__)

DECISION_SCHEMA = {
    "action": "buy|sell|hold",
    "symbol": "string",
    "size_pct": "float 1-15",
    "stop_loss": "float percent",
    "take_profit": "float percent",
    "confidence": "float 0-1",
    "reason": "short string",
}


class GrokDecider:
    def decide(self, agent_name: str, candidates: list[dict], portfolio: dict, allow_mock: bool = True) -> dict:
        if not settings.XAI_API_KEY:
            if allow_mock:
                return self._mock_decide(agent_name, candidates, portfolio)
            return {
                "action": "hold",
                "symbol": "",
                "size_pct": 0,
                "stop_loss": 3,
                "take_profit": 4.5,
                "confidence": 0,
                "reason": "XAI_API_KEY missing",
            }
        return self._grok_decide(agent_name, candidates, portfolio)

    def _mock_decide(self, agent_name: str, candidates: list[dict], portfolio: dict) -> dict:
        if not candidates:
            return {
                "action": "hold",
                "symbol": "",
                "size_pct": 0,
                "stop_loss": 3,
                "take_profit": 4.5,
                "confidence": 0.5,
                "reason": "No candidates",
            }
        c = candidates[0]
        signals_ok = float(c.get("buy_sell_ratio") or 1) >= 1.15
        if not signals_ok:
            return {
                "action": "hold",
                "symbol": c.get("symbol", ""),
                "size_pct": 0,
                "stop_loss": 3,
                "take_profit": 4.5,
                "confidence": 0.45,
                "reason": "Mock: weak buy/sell",
            }
        base_conf = 0.62 + (sum(ord(x) for x in agent_name) % 12) / 100
        return {
            "action": "buy",
            "symbol": c.get("symbol", ""),
            "size_pct": min(6 + (sum(ord(x) for x in agent_name) % 3), 8),
            "stop_loss": float(getattr(settings, "DEFAULT_STOP_LOSS_PCT", 3.0)),
            "take_profit": float(getattr(settings, "DEFAULT_TAKE_PROFIT_PCT", 4.5)),
            "confidence": round(base_conf, 2),
            "reason": f"Mock scalp on {c.get('symbol')}",
        }

    def _grok_decide(self, agent_name: str, candidates: list[dict], portfolio: dict) -> dict:
        client = OpenAI(api_key=settings.XAI_API_KEY, base_url=settings.XAI_BASE_URL)
        prompt = {
            "agent": agent_name,
            "task": (
                "Very short-term selective scalp. Prefer HOLD unless setup is strong. "
                "Use tight take_profit (3-6%) and stop_loss (2-4%). size_pct 4-8."
            ),
            "schema": DECISION_SCHEMA,
            "candidates": candidates[:3],
            "portfolio": portfolio,
        }
        try:
            resp = client.chat.completions.create(
                model=str(get_config().get("xai_model", settings.XAI_MODEL)),
                messages=[
                    {
                        "role": "system",
                        "content": "You are a selective crypto scalping bot. Output only valid JSON matching the schema.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                temperature=0.15,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or "{}"
            data = json.loads(text)
            return {
                "action": str(data.get("action", "hold")).lower(),
                "symbol": str(data.get("symbol", "")),
                "size_pct": float(data.get("size_pct", 0)),
                "stop_loss": float(data.get("stop_loss", 3)),
                "take_profit": float(data.get("take_profit", 4.5)),
                "confidence": float(data.get("confidence", 0)),
                "reason": str(data.get("reason", "")),
            }
        except Exception as e:
            logger.exception("Grok decision failed: %s", e)
            raise
