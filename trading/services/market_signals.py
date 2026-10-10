"""Derive structured indicators and safety flags from scanned token rows."""

from __future__ import annotations

from decimal import Decimal


def _f(val, default=0.0) -> float:
    if val is None:
        return default
    return float(val)


def build_entry_state(candidate: dict, portfolio: dict, agent_name: str, safety: dict | None = None) -> dict:
    """Structured state for Jev / Grok entry decisions."""
    price = _f(candidate.get("price_usd"))
    liq = _f(candidate.get("liquidity_usd"))
    vol = _f(candidate.get("volume_24h"))
    ratio = _f(candidate.get("buy_sell_ratio"), 1.0)
    age = candidate.get("pair_age_hours")
    fdv = _f(candidate.get("fdv_usd")) if candidate.get("fdv_usd") else None
    rug = _f(candidate.get("rug_score"), 70.0)

    vol_liq = vol / liq if liq > 0 else 0.0
    momentum = min(1.0, max(0.0, (ratio - 0.8) / 1.2))
    trend = min(1.0, max(0.0, vol_liq * 2.5))
    liquidity_score = min(1.0, liq / 250_000) if liq else 0.0
    event_risk = 0.0
    if age is not None and float(age) < 6:
        event_risk = 0.65
    elif age is not None and float(age) < 24:
        event_risk = 0.35
    if fdv and liq > 0 and fdv / liq > 25:
        event_risk = max(event_risk, 0.5)

    safety = safety or {}
    dev_flag = bool(safety.get("dev_wallet_high"))
    honeypot = bool(safety.get("honeypot"))

    return {
        "agent": agent_name,
        "symbol": candidate.get("symbol", ""),
        "chain": candidate.get("chain", ""),
        "current_price": price,
        "liquidity_usd": liq,
        "volume_24h": vol,
        "buy_sell_ratio": ratio,
        "pair_age_hours": float(age) if age is not None else None,
        "signals": {
            "trend": round(trend, 3),
            "momentum": round(momentum, 3),
            "relative_strength": round(min(1.0, ratio / 2.0), 3),
            "liquidity_score": round(liquidity_score, 3),
            "event_risk": round(event_risk, 3),
            "rug_score": round(rug / 100.0, 3),
        },
        "safety": {
            "honeypot": honeypot,
            "dev_wallet_high": dev_flag,
            "lp_ok": safety.get("lp_ok", True),
        },
        "portfolio": {
            "cash_usd": _f(portfolio.get("cash")),
            "open_positions": int(portfolio.get("open_positions", 0)),
        },
        "policy": "Selective scalp: high win-rate, tight take-profits, skip marginal setups.",
    }


def build_exit_state(position: dict, mark_price: float, portfolio: dict, agent_name: str) -> dict:
    entry = _f(position.get("entry_price"))
    pnl_pct = ((mark_price - entry) / entry * 100) if entry > 0 else 0.0
    return {
        "agent": agent_name,
        "symbol": position.get("symbol", ""),
        "chain": position.get("chain", ""),
        "current_price": mark_price,
        "entry_price": entry,
        "unrealized_pnl_pct": round(pnl_pct, 3),
        "cost_basis_usd": _f(position.get("cost_basis_usd")),
        "portfolio": {
            "cash_usd": _f(portfolio.get("cash")),
            "open_positions": int(portfolio.get("open_positions", 0)),
        },
        "policy": "Exit early on weakness; protect gains with tight targets.",
    }


def safety_from_token(token) -> dict:
    from trading.services.runtime_config import get_config

    max_dev = float(get_config().get("rug_dev_wallet_pct_max", 0.12))
    notes = token.rug_notes if hasattr(token, "rug_notes") else {}
    goplus = notes.get("goplus") or {}
    dev_high = False
    if goplus:
        for key in ("owner_percent", "creator_percent"):
            val = goplus.get(key)
            if val and float(val) > max_dev:
                dev_high = True
    return {
        "honeypot": goplus.get("is_honeypot") == "1",
        "dev_wallet_high": dev_high,
        "lp_ok": bool(notes.get("lp_locked") or notes.get("rugcheck")),
    }


def indicators_summary(candidate: dict, safety: dict) -> str:
    state = build_entry_state(candidate, {"cash": 0, "open_positions": 0}, "—", safety)
    s = state["signals"]
    return (
        f"trend={s['trend']:.2f} mom={s['momentum']:.2f} "
        f"rs={s['relative_strength']:.2f} liq={s['liquidity_score']:.2f} "
        f"event_risk={s['event_risk']:.2f}"
    )
