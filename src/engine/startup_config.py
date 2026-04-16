#!/usr/bin/env python3
"""
Startup config override helpers for Lazarus runtime config.
"""

from __future__ import annotations

import sqlite3
from typing import Any, MutableMapping

STARTUP_OVERRIDE_KEYS = {
    "position_pct",
    "max_positions",
    "take_profit",
    "stop_loss",
    "trail_arm",
    "min_hourly_vol",
    "min_chg_pct",
    "max_chg_pct",
    "min_liq",
    "min_vmr",
    "filter_regime",
}


def coerce_cfg_value(cfg: MutableMapping[str, Any], key: str, raw: str):
    current = cfg[key]
    if isinstance(current, bool):
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(current, int) and not isinstance(current, bool):
        return int(float(raw))
    if isinstance(current, float):
        return float(raw)
    return str(raw)


def apply_startup_config_overrides(db_path: str, cfg: MutableMapping[str, Any], logger) -> None:
    """Apply bot_config and dynamic_config values before the startup banner."""
    try:
        conn = sqlite3.connect(db_path, timeout=5)
        try:
            sources = (
                ("bot_config", conn.execute("SELECT key, value FROM bot_config").fetchall()),
                ("dynamic_config", conn.execute("SELECT key, value FROM dynamic_config").fetchall()),
            )
        finally:
            conn.close()

        for source_name, rows in sources:
            for key, value in rows:
                if key not in STARTUP_OVERRIDE_KEYS:
                    continue
                try:
                    cfg[key] = coerce_cfg_value(cfg, key, value)
                    logger.info(f"Startup config: {key}={cfg[key]} ({source_name})")
                except Exception as exc:
                    logger.warning(f"Startup config parse failed for {key}={value!r}: {exc}")
    except Exception as exc:
        logger.warning(f"Startup config override load failed: {exc}")
