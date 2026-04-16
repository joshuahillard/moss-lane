#!/usr/bin/env python3
"""
Canonical repo-side defaults for Lazarus runtime configuration.

These values are the documented fallback defaults for new environments and
deployment scripts. VPS runtime truth remains layered:
code CFG -> bot_config -> dynamic_config.
"""

DEFAULTS = {
    "min_hourly_vol": 250,
    "min_chg_pct": 10.0,
    "max_chg_pct": 120.0,
    "min_liq": 30_000,
    "min_vmr": 0.10,
    "filter_regime": "v3.2_lowvol_epoch",
}

FILTER_KEYS = (
    "min_hourly_vol",
    "min_chg_pct",
    "max_chg_pct",
    "min_liq",
    "min_vmr",
)

EPOCH_KEY = "epoch_v32_lowvol"
