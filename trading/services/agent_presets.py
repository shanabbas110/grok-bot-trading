"""Per-agent strategy presets."""

from decimal import Decimal

PRESETS: dict[str, dict] = {
    "conservative_scalper": {
        "strategy_notes": "Conservative scalper: high confidence, small size, tight stops.",
        "max_position_pct": Decimal("5"),
        "min_confidence": Decimal("0.72"),
        "jev_buy_offset": 0.05,
        "take_profit_pct": 3.5,
        "stop_loss_pct": 2.5,
    },
    "balanced_scalper": {
        "strategy_notes": "Balanced selective scalps.",
        "max_position_pct": Decimal("8"),
        "min_confidence": Decimal("0.65"),
        "jev_buy_offset": 0.0,
        "take_profit_pct": 4.5,
        "stop_loss_pct": 3.0,
    },
    "aggressive_scalper": {
        "strategy_notes": "Aggressive scalper: more entries, wider targets.",
        "max_position_pct": Decimal("12"),
        "min_confidence": Decimal("0.58"),
        "jev_buy_offset": -0.06,
        "take_profit_pct": 6.0,
        "stop_loss_pct": 4.0,
    },
}


def apply_preset(agent, preset_key: str) -> None:
    preset = PRESETS.get(preset_key)
    if not preset:
        raise ValueError(f"Unknown preset: {preset_key}")
    agent.strategy_preset = preset_key
    agent.strategy_notes = preset["strategy_notes"]
    agent.max_position_pct = preset["max_position_pct"]
    agent.min_confidence = preset["min_confidence"]
    agent.save()
