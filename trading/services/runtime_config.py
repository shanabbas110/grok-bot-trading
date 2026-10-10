"""Merge .env defaults with DB-backed overrides (AppSettings.config)."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ImproperlyConfigured

# Keys and env var mapping with type coercion
_CONFIG_SCHEMA: dict[str, dict[str, Any]] = {
    "decider_mode": {"env": "DECIDER_MODE", "type": "str", "choices": {"jev+grok", "grok-only", "jev-only", "mock"}},
    "jev_model": {"env": "JEV_MODEL", "type": "str"},
    "xai_model": {"env": "XAI_MODEL", "type": "str"},
    "jev_buy_confidence_threshold": {"env": "JEV_BUY_CONFIDENCE_THRESHOLD", "type": "float", "min": 0, "max": 1},
    "jev_exit_confidence_threshold": {"env": "JEV_EXIT_CONFIDENCE_THRESHOLD", "type": "float", "min": 0, "max": 1},
    "jev_exit_noul_threshold": {"env": "JEV_EXIT_NOUL_THRESHOLD", "type": "float", "min": 0, "max": 1},
    "grok_min_confidence": {"env": "GROK_MIN_CONFIDENCE", "type": "float", "min": 0, "max": 1},
    "scan_interval_seconds": {"env": "SCAN_INTERVAL_SECONDS", "type": "int", "min": 10},
    "agent_tick_seconds": {"env": "AGENT_TICK_SECONDS", "type": "int", "min": 5},
    "scan_min_liquidity_usd": {"env": "SCAN_MIN_LIQUIDITY_USD", "type": "float", "min": 0},
    "scan_min_volume_24h": {"env": "SCAN_MIN_VOLUME_24H", "type": "float", "min": 0},
    "scan_min_buy_sell_ratio": {"env": "SCAN_MIN_BUY_SELL_RATIO", "type": "float", "min": 0},
    "scan_max_pair_age_hours": {"env": "SCAN_MAX_PAIR_AGE_HOURS", "type": "float", "min": 0},
    "scan_max_fdv_liquidity_ratio": {"env": "SCAN_MAX_FDV_LIQUIDITY_RATIO", "type": "float", "min": 0},
    "rug_dev_wallet_pct_max": {"env": "RUG_DEV_WALLET_PCT_MAX", "type": "float", "min": 0, "max": 1},
    "rug_check_enabled": {"env": "RUG_CHECK_ENABLED", "type": "bool"},
    "default_position_size_pct": {"env": "DEFAULT_POSITION_SIZE_PCT", "type": "float", "min": 0.1, "max": 100},
    "default_stop_loss_pct": {"env": "DEFAULT_STOP_LOSS_PCT", "type": "float", "min": 0.1, "max": 50},
    "default_take_profit_pct": {"env": "DEFAULT_TAKE_PROFIT_PCT", "type": "float", "min": 0.1, "max": 100},
    "max_take_profit_pct": {"env": "MAX_TAKE_PROFIT_PCT", "type": "float", "min": 0.1, "max": 100},
    "max_stop_loss_pct": {"env": "MAX_STOP_LOSS_PCT", "type": "float", "min": 0.1, "max": 50},
    "paper_position_timeout_hours": {"env": "PAPER_POSITION_TIMEOUT_HOURS", "type": "float", "min": 0.1},
    "risk_max_position_pct": {"env": "RISK_MAX_POSITION_PCT", "type": "float", "min": 0.1, "max": 100},
    "risk_max_open_positions": {"env": "RISK_MAX_OPEN_POSITIONS", "type": "int", "min": 1},
    "risk_daily_loss_kill_pct": {"env": "RISK_DAILY_LOSS_KILL_PCT", "type": "float", "min": 0.1, "max": 100},
    "risk_max_trades_per_hour": {"env": "RISK_MAX_TRADES_PER_HOUR", "type": "int", "min": 1},
    "risk_min_confidence": {"env": "RISK_MIN_CONFIDENCE", "type": "float", "min": 0, "max": 1},
    "paper_fee_bps": {"env": "PAPER_FEE_BPS", "type": "int", "min": 0},
    "paper_slippage_bps": {"env": "PAPER_SLIPPAGE_BPS", "type": "int", "min": 0},
    "daily_target_pct": {"env": "DAILY_TARGET_PCT", "type": "float", "min": 0},
    "paper_starting_balance": {"env": "PAPER_STARTING_BALANCE", "type": "float", "min": 1},
    "chains_to_scan": {"env": "CHAINS_TO_SCAN", "type": "list"},
    "win_rate_target_wins": {"env": "WIN_RATE_TARGET_WINS", "type": "int", "min": 1},
    "win_rate_target_closed": {"env": "WIN_RATE_TARGET_CLOSED", "type": "int", "min": 1},
}


def _coerce(typ: str, raw: Any) -> Any:
    if raw is None:
        return None
    if typ == "str":
        return str(raw)
    if typ == "int":
        return int(float(raw))
    if typ == "float":
        return float(raw)
    if typ == "bool":
        if isinstance(raw, bool):
            return raw
        return str(raw).lower() in ("1", "true", "yes", "on")
    if typ == "list":
        if isinstance(raw, list):
            return [str(x).strip().lower() for x in raw if str(x).strip()]
        return [c.strip().lower() for c in str(raw).split(",") if c.strip()]
    return raw


def _default_for_key(key: str, meta: dict[str, Any]) -> Any:
    if key == "chains_to_scan":
        return ["solana", "ethereum", "base", "bsc"]
    if key == "rug_check_enabled":
        return True
    if key == "daily_target_pct":
        return 15.0
    try:
        from django.conf import settings as dj

        env_key = meta["env"]
        if hasattr(dj, env_key):
            return _coerce(meta["type"], getattr(dj, env_key))
    except Exception:
        pass
    return None


def env_defaults() -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, meta in _CONFIG_SCHEMA.items():
        env_key = meta["env"]
        raw = os.environ.get(env_key)
        if raw is None or raw == "":
            default = _default_for_key(key, meta)
            if default is not None:
                out[key] = default
            continue
        out[key] = _coerce(meta["type"], raw)
    for key, meta in _CONFIG_SCHEMA.items():
        if key not in out:
            default = _default_for_key(key, meta)
            if default is not None:
                out[key] = default
    return out


def validate_config(config: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    for key, meta in _CONFIG_SCHEMA.items():
        if key not in config:
            continue
        val = config[key]
        if val is None:
            continue
        try:
            val = _coerce(meta["type"], val)
        except (TypeError, ValueError):
            errors.append(f"{key}: invalid type (expected {meta['type']})")
            continue
        if "min" in meta and val < meta["min"]:
            errors.append(f"{key}: must be >= {meta['min']} (got {val})")
        if "max" in meta and val > meta["max"]:
            errors.append(f"{key}: must be <= {meta['max']} (got {val})")
        choices = meta.get("choices")
        if choices and val not in choices:
            errors.append(f"{key}: must be one of {sorted(choices)} (got {val})")
    wins = config.get("win_rate_target_wins", 50)
    closed = config.get("win_rate_target_closed", 60)
    if wins and closed and wins > closed:
        errors.append("win_rate_target_wins cannot exceed win_rate_target_closed")
    if config.get("default_take_profit_pct", 0) > config.get("max_take_profit_pct", 100):
        errors.append("default_take_profit_pct cannot exceed max_take_profit_pct")
    return errors


def validate_startup() -> None:
    """Raise ImproperlyConfigured with all validation errors."""
    cfg = get_config()
    errors = validate_config(cfg)
    if errors:
        raise ImproperlyConfigured("Invalid trading configuration:\n  - " + "\n  - ".join(errors))


def get_config() -> dict[str, Any]:
    merged = env_defaults()
    try:
        from trading.models import AppSettings

        row = AppSettings.get()
        overrides = row.config or {}
        for k, v in overrides.items():
            if v is not None and v != "":
                merged[k] = v
        if row.daily_target_pct is not None:
            merged["daily_target_pct"] = float(row.daily_target_pct)
        if row.starting_balance is not None:
            merged["paper_starting_balance"] = float(row.starting_balance)
    except Exception:
        pass
    # fill missing from schema defaults
    for key, meta in _CONFIG_SCHEMA.items():
        if key not in merged:
            if key == "chains_to_scan":
                merged[key] = ["solana", "ethereum", "base", "bsc"]
            elif key == "rug_check_enabled":
                merged[key] = True
            elif meta["type"] == "bool":
                merged[key] = False
    return merged


def get_config_schema() -> dict[str, dict[str, Any]]:
    return _CONFIG_SCHEMA


@dataclass
class Cfg:
    """Attribute access to merged config."""

    def __getattr__(self, name: str) -> Any:
        key = name.lower()
        if key not in _CONFIG_SCHEMA and key not in ("decider_mode",):
            raise AttributeError(name)
        return get_config().get(key)

    def get(self, key: str, default=None):
        return get_config().get(key, default)

    def as_dict(self) -> dict[str, Any]:
        return get_config()


cfg = Cfg()
