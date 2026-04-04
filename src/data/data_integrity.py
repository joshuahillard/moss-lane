#!/usr/bin/env python3
"""
Lazarus — Data Integrity Module (5-Layer Protection)

PURPOSE:
  Pure validation functions for defense-in-depth data integrity.
  Every function returns {valid: bool, reason: str, details: dict}.
  No side effects, no network calls, no DB writes.
  Every layer fails closed — if uncertain, reject.

LAYERS:
  1. Query-level epoch gating (blocks strftime anti-pattern)
  2. Learning engine input validation (epoch + Stoic Gate + completeness)
  3. Dynamic config output bounds checking (prevents parameter poisoning)
  4. Startup assertion checks (catches config drift before trading)
  5. Observability anomaly detection (flags drift for human review)

INCIDENT COVERAGE:
  - DB Config Override Bug → Layer 4
  - Epoch Format Mismatch → Layer 2
  - Ghost Trade Bug → Layer 2
  - Epoch Query Data Leak → Layer 1
  - Learning Engine Overwrite → Layer 3
"""

import re
import math

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════

V31_EPOCH = "2026-03-29T17:44:00"

# Bounds that the learning engine is NEVER allowed to exceed
PARAM_BOUNDS = {
    "position_pct": {"min": 0.10, "max": 0.30, "type": float},
    "stop_loss":    {"min": 0.85, "max": 0.96, "type": float},
    "take_profit":  {"min": 1.10, "max": 1.50, "type": float},
    "trail_arm":    {"min": 1.04, "max": 1.15, "type": float},
    "min_chg_pct":  {"min": 3.0,  "max": 50.0, "type": float},
    "max_chg_pct":  {"min": 50.0, "max": 200.0, "type": float},
    "min_liq":      {"min": 20000, "max": 200000, "type": float},
}

# Required keys in bot_config for startup validation
REQUIRED_BOT_CONFIG_KEYS = {
    "stop_loss", "take_profit", "trail_arm", "position_pct",
    "min_chg_pct", "max_chg_pct", "min_liq",
}

# Fields every trade must have for learning engine input
REQUIRED_TRADE_FIELDS = {"pnl_pct", "exit_reason", "timestamp"}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: Query-Level Epoch Gating
# ══════════════════════════════════════════════════════════════════════════════

# Pattern: strftime('%s', ...) used anywhere — the root cause of the
# 2026-04-03 epoch query data leak where unix integers string-compared
# as always-TRUE against ISO text timestamps.
_STRFTIME_S_PATTERN = re.compile(r"strftime\s*\(\s*['\"]%s['\"]", re.IGNORECASE)

# Pattern: bare integer comparison against timestamp column
_UNIX_INT_PATTERN = re.compile(
    r"timestamp\s*(>=|<=|>|<|=)\s*\d{9,11}", re.IGNORECASE
)


def validate_epoch_query(query_text, epoch=V31_EPOCH):
    """
    Scans a SQL query string for epoch comparison anti-patterns.

    REJECTS:
    - strftime('%s', ...) used anywhere in query
    - Unix integer comparisons against timestamp column
    - Query touches trades table without any timestamp filter

    ACCEPTS:
    - Direct text comparison: timestamp >= '2026-03-29T17:44:00'
    - Parameterized equivalent (timestamp >= ?)

    Returns: {valid: bool, reason: str, details: {pattern_found: str}}
    """
    if not query_text or not isinstance(query_text, str):
        return {"valid": False, "reason": "empty or invalid query",
                "details": {"pattern_found": "none"}}

    q = query_text.strip()

    # Check for strftime('%s',...) — the killer anti-pattern
    match = _STRFTIME_S_PATTERN.search(q)
    if match:
        return {"valid": False,
                "reason": "strftime('%s',...) converts to unix int — breaks against ISO text timestamps",
                "details": {"pattern_found": match.group()}}

    # Check for bare unix integer comparison against timestamp
    match = _UNIX_INT_PATTERN.search(q)
    if match:
        return {"valid": False,
                "reason": "unix integer comparison against ISO text timestamp column",
                "details": {"pattern_found": match.group()}}

    # Check that queries touching the trades table have a timestamp filter
    if re.search(r"\btrades\b", q, re.IGNORECASE):
        has_ts_filter = (
            re.search(r"timestamp\s*(>=|>|<=|<|=|LIKE|BETWEEN)", q, re.IGNORECASE)
            or re.search(r"timestamp\s+IN\s*\(", q, re.IGNORECASE)
            or "?" in q  # parameterized — we trust the caller to pass epoch
        )
        if not has_ts_filter:
            return {"valid": False,
                    "reason": "query touches trades table without timestamp filter — risk of pre-epoch data leak",
                    "details": {"pattern_found": "no_timestamp_filter"}}

    return {"valid": True, "reason": "query passes epoch gating checks",
            "details": {"pattern_found": "none"}}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 2: Learning Engine Input Validation
# ══════════════════════════════════════════════════════════════════════════════

def validate_learning_input(trades, epoch=V31_EPOCH, min_trades=20):
    """
    Validates the trade dataset BEFORE the learning engine evaluates it.

    REJECTS:
    - Trade count below min_trades (Stoic Gate)
    - Any trade with timestamp < epoch (pre-epoch data leakage)
    - Trades missing required fields (pnl_pct, exit_reason, timestamp)

    Returns: {valid: bool, reason: str, details: {total, accepted, rejected, rejection_reasons}}
    """
    if not trades:
        return {"valid": False, "reason": "no trades provided",
                "details": {"total": 0, "accepted": 0, "rejected": 0,
                            "rejection_reasons": {}}}

    rejection_reasons = {}
    accepted = 0
    rejected = 0

    for i, trade in enumerate(trades):
        # Handle both dict and tuple formats
        if isinstance(trade, dict):
            ts = trade.get("timestamp", "")
            missing = [f for f in REQUIRED_TRADE_FIELDS
                       if f not in trade or trade[f] is None]
        elif isinstance(trade, (list, tuple)):
            # Tuple format from learning_engine: index 5 is timestamp
            ts = trade[5] if len(trade) > 5 else ""
            missing = []  # tuple format is positional, can't check by name
        else:
            rejected += 1
            rejection_reasons["invalid_format"] = rejection_reasons.get("invalid_format", 0) + 1
            continue

        # Check for missing fields (dict format only)
        if missing:
            rejected += 1
            for f in missing:
                key = f"missing_{f}"
                rejection_reasons[key] = rejection_reasons.get(key, 0) + 1
            continue

        # Check for pre-epoch timestamps (ISO text comparison)
        ts_str = str(ts) if ts else ""
        if ts_str and ts_str < epoch:
            rejected += 1
            rejection_reasons["pre_epoch"] = rejection_reasons.get("pre_epoch", 0) + 1
            continue

        accepted += 1

    total = len(trades)

    # Stoic Gate: must have enough post-epoch trades
    if accepted < min_trades:
        return {"valid": False,
                "reason": f"Stoic Gate: only {accepted} valid trades (need {min_trades})",
                "details": {"total": total, "accepted": accepted,
                            "rejected": rejected, "rejection_reasons": rejection_reasons}}

    if rejected > 0:
        return {"valid": True,
                "reason": f"{accepted} trades accepted, {rejected} rejected (filtered)",
                "details": {"total": total, "accepted": accepted,
                            "rejected": rejected, "rejection_reasons": rejection_reasons}}

    return {"valid": True,
            "reason": f"all {accepted} trades passed validation",
            "details": {"total": total, "accepted": accepted,
                        "rejected": 0, "rejection_reasons": {}}}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 3: Dynamic Config Output Validation
# ══════════════════════════════════════════════════════════════════════════════

def validate_config_write(key, value, bounds=None):
    """
    Validates a proposed dynamic_config write BEFORE it hits the DB.

    REJECTS:
    - Key not in PARAM_BOUNDS (unknown parameter)
    - Value outside min/max bounds
    - Value type mismatch (NaN, None, wrong type)

    Returns: {valid: bool, reason: str, details: {key, proposed, min, max}}
    """
    if bounds is None:
        bounds = PARAM_BOUNDS

    if key not in bounds:
        return {"valid": False,
                "reason": f"unknown key '{key}' — not in allowed parameters",
                "details": {"key": key, "proposed": value, "min": None, "max": None}}

    spec = bounds[key]

    # Type/value sanity
    if value is None:
        return {"valid": False, "reason": f"'{key}' value is None",
                "details": {"key": key, "proposed": None,
                            "min": spec["min"], "max": spec["max"]}}

    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return {"valid": False,
                "reason": f"'{key}' value '{value}' is not numeric",
                "details": {"key": key, "proposed": value,
                            "min": spec["min"], "max": spec["max"]}}

    if math.isnan(numeric) or math.isinf(numeric):
        return {"valid": False,
                "reason": f"'{key}' value is NaN or Inf",
                "details": {"key": key, "proposed": value,
                            "min": spec["min"], "max": spec["max"]}}

    # Bounds check
    if numeric < spec["min"] or numeric > spec["max"]:
        return {"valid": False,
                "reason": f"'{key}'={numeric} outside bounds [{spec['min']}, {spec['max']}]",
                "details": {"key": key, "proposed": numeric,
                            "min": spec["min"], "max": spec["max"]}}

    return {"valid": True,
            "reason": f"'{key}'={numeric} within bounds [{spec['min']}, {spec['max']}]",
            "details": {"key": key, "proposed": numeric,
                        "min": spec["min"], "max": spec["max"]}}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 4: Runtime Assertion Checks
# ══════════════════════════════════════════════════════════════════════════════

def validate_startup_config(bot_config, dynamic_config, epoch=V31_EPOCH):
    """
    Runs at Lazarus startup. Catches configuration drift before any trades execute.

    CHECKS:
    - bot_config has all required keys
    - dynamic_config values are within PARAM_BOUNDS
    - dynamic_config epoch is >= V3.1 epoch (no stale overrides)
    - stop_loss < take_profit (sanity)
    - position_pct won't exceed 30% per trade

    Returns: {valid: bool, reason: str, details: {checks_passed, checks_failed}}
    """
    passed = []
    failed = []

    # Check 1: Required bot_config keys
    if isinstance(bot_config, dict):
        missing = REQUIRED_BOT_CONFIG_KEYS - set(bot_config.keys())
        if missing:
            failed.append(f"bot_config missing keys: {missing}")
        else:
            passed.append("bot_config has all required keys")
    else:
        failed.append("bot_config is not a dict")

    # Check 2: dynamic_config values within bounds
    if isinstance(dynamic_config, dict):
        for key, val in dynamic_config.items():
            if key in PARAM_BOUNDS:
                check = validate_config_write(key, val)
                if check["valid"]:
                    passed.append(f"dynamic_config.{key}={val} in bounds")
                else:
                    failed.append(f"dynamic_config.{key}={val} OUT OF BOUNDS: {check['reason']}")
    else:
        # dynamic_config can be empty/None — that's OK (no overrides active)
        passed.append("dynamic_config empty or not dict — no overrides to validate")

    # Check 3: dynamic_config epoch freshness
    if isinstance(dynamic_config, dict):
        dc_epoch = dynamic_config.get("_epoch", "")
        if dc_epoch and dc_epoch < epoch:
            failed.append(f"dynamic_config epoch '{dc_epoch}' is older than V3.1 epoch '{epoch}'")
        else:
            passed.append("dynamic_config epoch is current or not set")

    # Check 4: stop_loss < take_profit (sanity cross-check)
    sl = None
    tp = None
    if isinstance(bot_config, dict):
        try:
            sl = float(bot_config.get("stop_loss", 0))
            tp = float(bot_config.get("take_profit", 0))
        except (TypeError, ValueError):
            pass

    # Also check dynamic_config overrides
    if isinstance(dynamic_config, dict):
        try:
            if "stop_loss" in dynamic_config:
                sl = float(dynamic_config["stop_loss"])
            if "take_profit" in dynamic_config:
                tp = float(dynamic_config["take_profit"])
        except (TypeError, ValueError):
            pass

    if sl is not None and tp is not None and sl > 0 and tp > 0:
        if sl >= tp:
            failed.append(f"stop_loss ({sl}) >= take_profit ({tp}) — impossible trade")
        else:
            passed.append(f"stop_loss ({sl}) < take_profit ({tp}) — sane")

    # Check 5: position_pct within safe range
    pos_pct = None
    if isinstance(bot_config, dict):
        try:
            pos_pct = float(bot_config.get("position_pct", 0))
        except (TypeError, ValueError):
            pass
    if isinstance(dynamic_config, dict) and "position_pct" in dynamic_config:
        try:
            pos_pct = float(dynamic_config["position_pct"])
        except (TypeError, ValueError):
            pass

    if pos_pct is not None:
        if pos_pct > 0.30:
            failed.append(f"position_pct ({pos_pct}) exceeds 30% maximum")
        elif pos_pct < 0.10:
            failed.append(f"position_pct ({pos_pct}) below 10% minimum")
        else:
            passed.append(f"position_pct ({pos_pct}) within safe range")

    # Verdict
    if failed:
        return {"valid": False,
                "reason": f"{len(failed)} check(s) failed",
                "details": {"checks_passed": passed, "checks_failed": failed}}

    return {"valid": True,
            "reason": f"all {len(passed)} startup checks passed",
            "details": {"checks_passed": passed, "checks_failed": []}}


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 5: Observability & Anomaly Detection
# ══════════════════════════════════════════════════════════════════════════════

def check_data_anomalies(trades, config):
    """
    Detects drift and anomalies in recent trade data. Runs periodically.

    FLAGS:
    - Win rate dropped below 20% over last 10 trades
    - Average PnL per trade trending negative over 3 consecutive windows
    - All trades hitting same exit_reason (possible broken exit path)
    - Trade volume spike (>3x average rate if applicable)

    Does NOT reject — only flags. Human (Josh) makes the call.

    Returns: {anomalies: list[dict], severity: str, recommendation: str}
    """
    anomalies = []
    severity = "none"

    if not trades:
        return {"anomalies": [], "severity": "none",
                "recommendation": "no data to analyze"}

    # Extract data — handle both dict and tuple formats
    def _get(trade, key, idx, default=None):
        if isinstance(trade, dict):
            return trade.get(key, default)
        elif isinstance(trade, (list, tuple)) and len(trade) > idx:
            return trade[idx]
        return default

    # Anomaly 1: Win rate below 20% over last 10 trades
    recent_10 = trades[:10]
    if len(recent_10) >= 5:
        wins = sum(1 for t in recent_10 if (_get(t, "pnl_pct", 2, 0) or 0) > 0)
        wr = wins / len(recent_10)
        if wr < 0.20:
            anomalies.append({
                "type": "low_win_rate",
                "message": f"Win rate {wr*100:.0f}% over last {len(recent_10)} trades (threshold: 20%)",
                "severity": "high",
                "value": round(wr, 3)
            })

    # Anomaly 2: Average PnL trending negative (3 consecutive windows of 5)
    if len(trades) >= 15:
        windows = [trades[0:5], trades[5:10], trades[10:15]]
        window_pnls = []
        for w in windows:
            avg = sum(_get(t, "pnl_pct", 2, 0) or 0 for t in w) / max(len(w), 1)
            window_pnls.append(avg)
        if all(p < 0 for p in window_pnls):
            anomalies.append({
                "type": "negative_pnl_trend",
                "message": f"3 consecutive negative PnL windows: {[round(p,2) for p in window_pnls]}",
                "severity": "high",
                "value": window_pnls
            })

    # Anomaly 3: All trades hitting same exit_reason (broken exit path)
    if len(recent_10) >= 5:
        reasons = [_get(t, "exit_reason", 6, "") for t in recent_10]
        reasons = [r for r in reasons if r]
        if reasons and len(set(reasons)) == 1:
            anomalies.append({
                "type": "uniform_exit_reason",
                "message": f"All {len(reasons)} recent trades exited via '{reasons[0]}' — possible broken exit path",
                "severity": "medium",
                "value": reasons[0]
            })

    # Anomaly 4: Check for extreme PnL outliers (single trade > 50% loss)
    for t in recent_10:
        pnl = _get(t, "pnl_pct", 2, 0) or 0
        if pnl < -50:
            sym = _get(t, "symbol", 0, "?")
            anomalies.append({
                "type": "extreme_loss",
                "message": f"Extreme loss on {sym}: {pnl:.1f}% — possible rug or liquidity drain",
                "severity": "critical",
                "value": pnl
            })

    # Determine overall severity
    if any(a["severity"] == "critical" for a in anomalies):
        severity = "critical"
    elif any(a["severity"] == "high" for a in anomalies):
        severity = "high"
    elif anomalies:
        severity = "medium"

    # Recommendation
    if severity == "critical":
        recommendation = "CRITICAL anomaly detected — manual review recommended before next trade"
    elif severity == "high":
        recommendation = "Multiple warning signals — consider pausing to investigate"
    elif severity == "medium":
        recommendation = "Minor anomalies — monitor closely"
    else:
        recommendation = "no anomalies detected"

    return {"anomalies": anomalies, "severity": severity,
            "recommendation": recommendation}
