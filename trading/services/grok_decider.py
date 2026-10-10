import json
import logging
import random

from django.conf import settings
from openai import OpenAI

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
    def decide(self, agent_name: str, candidates: list[dict], portfolio: dict) -> dict:
        if not settings.XAI_API_KEY:
            return self._mock_decide(agent_name, candidates, portfolio)
        return self._grok_decide(agent_name, candidates, portfolio)

    def _mock_decide(self, agent_name: str, candidates: list[dict], portfolio: dict) -> dict:
        if not candidates:
            return {
                "action": "hold",
                "symbol": "",
                "size_pct": 0,
                "stop_loss": 5,
                "take_profit": 8,
                "confidence": 0.5,
                "reason": "No candidates",
            }
        c = random.choice(candidates[:5])
        # Agent name influences aggressiveness slightly
        base_conf = 0.58 + (sum(ord(x) for x in agent_name) % 15) / 100
        return {
            "action": "buy",
            "symbol": c.get("symbol", ""),
            "size_pct": min(8 + (sum(ord(x) for x in agent_name) % 5), 12),
            "stop_loss": 4.0,
            "take_profit": 9.0,
            "confidence": round(base_conf, 2),
            "reason": f"Mock scalp on {c.get('symbol')} (no XAI_API_KEY)",
        }

    def _grok_decide(self, agent_name: str, candidates: list[dict], portfolio: dict) -> dict:
        client = OpenAI(api_key=settings.XAI_API_KEY, base_url=settings.XAI_BASE_URL)
        prompt = {
            "agent": agent_name,
            "task": "Very short-term scalp decision. Respond with strict JSON only.",
            "schema": DECISION_SCHEMA,
            "candidates": candidates[:8],
            "portfolio": portfolio,
        }
        try:
            resp = client.chat.completions.create(
                model=settings.XAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a crypto scalping bot. Output only valid JSON matching the schema.",
                    },
                    {"role": "user", "content": json.dumps(prompt)},
                ],
                temperature=0.2,
                response_format={"type": "json_object"},
            )
            text = resp.choices[0].message.content or "{}"
            data = json.loads(text)
            return {
                "action": str(data.get("action", "hold")).lower(),
                "symbol": str(data.get("symbol", "")),
                "size_pct": float(data.get("size_pct", 0)),
                "stop_loss": float(data.get("stop_loss", 5)),
                "take_profit": float(data.get("take_profit", 10)),
                "confidence": float(data.get("confidence", 0)),
                "reason": str(data.get("reason", "")),
            }
        except Exception as e:
            logger.exception("Grok decision failed: %s", e)
            return self._mock_decide(agent_name, candidates, portfolio)
