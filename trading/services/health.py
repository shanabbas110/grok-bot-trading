"""Provider health checks for dashboard status panel."""

from __future__ import annotations

import os
import time

from django.conf import settings as django_settings

from trading.services.http_client import HttpClient
from trading.services.jev_decider import JevDecider
from trading.services.runtime_config import get_config


def _status(ok: bool, latency_ms: float = 0, detail: str = "") -> dict:
    return {
        "ok": ok,
        "latency_ms": round(latency_ms, 1),
        "detail": detail,
    }


def check_dexscreener() -> dict:
    client = HttpClient(timeout=8)
    started = time.perf_counter()
    try:
        resp = client.request("GET", "https://api.dexscreener.com/token-boosts/latest/v1")
        ok = resp.ok
        detail = "ok" if ok else f"HTTP {resp.status_code}"
    except Exception as e:
        return _status(False, (time.perf_counter() - started) * 1000, str(e)[:120])
    return _status(ok, (time.perf_counter() - started) * 1000, detail)


def check_geckoterminal() -> dict:
    client = HttpClient(timeout=8)
    started = time.perf_counter()
    try:
        resp = client.request("GET", "https://api.geckoterminal.com/api/v2/networks/solana/trending_pools")
        ok = resp.ok
        detail = "ok" if ok else f"HTTP {resp.status_code}"
    except Exception as e:
        return _status(False, (time.perf_counter() - started) * 1000, str(e)[:120])
    return _status(ok, (time.perf_counter() - started) * 1000, detail)


def check_goplus() -> dict:
    if not get_config().get("rug_check_enabled", True):
        return _status(True, 0, "disabled in config")
    client = HttpClient(timeout=8)
    started = time.perf_counter()
    try:
        resp = client.request(
            "GET",
            "https://api.gopluslabs.io/api/v1/token_security/1",
            params={"contract_addresses": "0x0000000000000000000000000000000000000000"},
        )
        ok = resp.status_code in (200, 400, 422)
        detail = "reachable" if ok else f"HTTP {resp.status_code}"
    except Exception as e:
        return _status(False, (time.perf_counter() - started) * 1000, str(e)[:120])
    return _status(ok, (time.perf_counter() - started) * 1000, detail)


def check_rugcheck() -> dict:
    if not get_config().get("rug_check_enabled", True):
        return _status(True, 0, "disabled in config")
    client = HttpClient(timeout=8)
    started = time.perf_counter()
    try:
        resp = client.request(
            "GET",
            "https://api.rugcheck.xyz/v1/tokens/So11111111111111111111111111111111111111112/report/summary",
        )
        ok = resp.status_code in (200, 404)
        detail = "reachable" if ok else f"HTTP {resp.status_code}"
    except Exception as e:
        return _status(False, (time.perf_counter() - started) * 1000, str(e)[:120])
    return _status(ok, (time.perf_counter() - started) * 1000, detail)


def check_jev() -> dict:
    key = os.environ.get("TYPESAFE_API_KEY", "")
    if not key:
        mode = get_config().get("decider_mode", "mock")
        if mode in ("jev+grok", "jev-only"):
            return _status(True, 0, "no key — using mock gate")
        return _status(True, 0, "not required for current mode")
    decider = JevDecider()
    started = time.perf_counter()
    try:
        result = decider.evaluate_entry(
            {
                "symbol": "HEALTH",
                "signals": {"trend": 0.5, "momentum": 0.5, "relative_strength": 0.5, "event_risk": 0.2},
                "safety": {"honeypot": False, "dev_wallet_high": False},
            }
        )
        ok = result.error is None
        detail = result.model if ok else (result.error or "error")[:80]
    except Exception as e:
        return _status(False, (time.perf_counter() - started) * 1000, str(e)[:120])
    return _status(ok, (time.perf_counter() - started) * 1000, detail)


def check_grok() -> dict:
    if not django_settings.XAI_API_KEY:
        mode = get_config().get("decider_mode", "mock")
        if mode in ("jev+grok", "grok-only"):
            return _status(True, 0, "no XAI_API_KEY — mock/rules")
        return _status(True, 0, "not required for current mode")
    started = time.perf_counter()
    try:
        from openai import OpenAI

        client = OpenAI(api_key=django_settings.XAI_API_KEY, base_url=django_settings.XAI_BASE_URL)
        client.models.list()
        detail = "authenticated"
        ok = True
    except Exception as e:
        return _status(False, (time.perf_counter() - started) * 1000, str(e)[:120])
    return _status(ok, (time.perf_counter() - started) * 1000, detail)


def all_providers() -> dict:
    return {
        "dexscreener": check_dexscreener(),
        "geckoterminal": check_geckoterminal(),
        "goplus": check_goplus(),
        "rugcheck": check_rugcheck(),
        "jev": check_jev(),
        "grok": check_grok(),
    }
