#!/usr/bin/env python3
"""
Sol-Fortress v3.0 — Self-Regulation Module (Clean)

PURPOSE:
  - Detect losing streaks and pause trading temporarily
  - Cool down specific tokens that keep hitting stop losses
  - Track regime (normal / cautious / paused)

RULES:
  - NEVER override core filter values (max_chg_pct, min_liq, etc.)
    Those are set in fort_v2.py and tuned by data analysis. Self-regulation
    only controls WHETHER to trade, not HOW to filter.
  - Regime modes: normal (trade freely), cautious (reduce frequency), paused (stop)
  - Per-token cooldowns when a token hits SL 3+ times in 30 minutes
  - Auto-pause after 5 consecutive stop losses
  - Auto-recovery when win rate improves above 25% over 10 trades
"""

import sqlite3
import json
import time
import logging
import asyncio
from datetime import datetime, timedelta, timezone

log = logging.getLogger("self_reg")

# ── Constants ──
STREAK_WINDOW_MIN = 30      # look-back window for SL streaks
STREAK_SL_THRESHOLD = 3     # SL hits on same token → cooldown
REGIME_WINDOW = 10           # trades to evaluate regime
BAD_WINRATE = 0.25           # below this → cautious
PAUSE_WINRATE = 0.10         # below this → paused
CONSEC_SL_PAUSE = 5          # consecutive SLs → auto-pause
COOLDOWN_MINUTES = 120       # per-token cooldown (2 hours)
PAUSE_MINUTES = 15           # how long to pause trading
HEARTBEAT_SEC = 60           # regime check interval

_DB = ""


def init(db_path):
    global _DB
    _DB = db_path
    _ensure_tables()
    log.info("Self-regulation ready")


def _ensure_tables():
    """Create tables if they don't exist (idempotent)."""
    try:
        c = sqlite3.connect(_DB, timeout=5)
        c.executescript("""
            CREATE TABLE IF NOT EXISTS bot_config (
                key TEXT PRIMARY KEY, value TEXT,
                updated_at TEXT, reason TEXT
            );
            CREATE TABLE IF NOT EXISTS config_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                changed_at TEXT DEFAULT (datetime('now')),
                key TEXT, old_value TEXT, new_value TEXT,
                reason TEXT, triggered_by TEXT
            );
            CREATE TABLE IF NOT EXISTS token_cooldowns (
                address TEXT PRIMARY KEY, symbol TEXT, reason TEXT,
                sl_count INTEGER DEFAULT 0,
                blocked_at TEXT DEFAULT (datetime('now')),
                blocked_until TEXT, lifted_at TEXT, auto_lifted INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS trade_analysis (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                analyzed_at TEXT DEFAULT (datetime('now')),
                trade_timestamp TEXT, token_address TEXT, symbol TEXT,
                pnl_usd REAL, pnl_pct REAL, exit_reason TEXT,
                chg_pct_at_entry REAL, mc_at_entry REAL, liq_at_entry REAL,
                findings TEXT, actions_taken TEXT,
                regime_before TEXT, regime_after TEXT
            );
        """)
        c.commit()
        c.close()
    except Exception as e:
        log.error(f"Table creation: {e}")


def _conn():
    if not _DB:
        raise RuntimeError("Self-regulation not initialized")
    c = sqlite3.connect(_DB, timeout=5)
    c.row_factory = sqlite3.Row
    return c


# ══════════════════════════════════════════════════════════════════════════════
# REGIME DETECTION — determines trading mode based on recent performance
# ══════════════════════════════════════════════════════════════════════════════

def _get_recent_trades(n=20):
    try:
        c = _conn()
        rows = c.execute(
            "SELECT * FROM trades ORDER BY timestamp DESC LIMIT ?", (n,)
        ).fetchall()
        c.close()
        return [dict(r) for r in rows]
    except Exception as e:
        log.error(f"Recent trades query: {e}")
        return []


def _evaluate_regime(trades):
    """Determine trading regime based on recent performance."""
    if not trades:
        return {"mode": "normal", "win_rate": 0.5, "consec_sl": 0, "reason": "no data"}

    sample = trades[:REGIME_WINDOW]
    wins = sum(1 for t in sample if (t.get("pnl_usd") or 0) > 0)
    wr = wins / len(sample) if sample else 0.5

    # Count consecutive stop losses from most recent
    consec_sl = 0
    for t in trades:
        if t.get("exit_reason") == "stop_loss":
            consec_sl += 1
        else:
            break

    # Determine mode
    if wr < PAUSE_WINRATE or consec_sl >= CONSEC_SL_PAUSE:
        mode = "paused"
        reason = f"wr={wr:.0%} csl={consec_sl}"
    elif wr < BAD_WINRATE:
        mode = "cautious"
        reason = f"wr={wr:.0%} < {BAD_WINRATE:.0%}"
    else:
        mode = "normal"
        reason = f"wr={wr:.0%} ok"

    return {"mode": mode, "win_rate": round(wr, 3), "consec_sl": consec_sl,
            "wins": wins, "losses": len(sample) - wins, "reason": reason}


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG MUTATIONS — only regime-related, NEVER filter values
# ══════════════════════════════════════════════════════════════════════════════

def _get_config(key):
    try:
        c = _conn()
        row = c.execute("SELECT value FROM bot_config WHERE key=?", (key,)).fetchone()
        c.close()
        return row["value"] if row else None
    except Exception:
        return None


def _set_config(key, value, reason):
    """Update bot_config with audit trail. Only for regime/pause keys."""
    # SAFETY: Never allow self-regulation to touch filter parameters
    ALLOWED_KEYS = {"regime_mode", "scan_pause_until"}
    if key not in ALLOWED_KEYS:
        log.warning(f"BLOCKED: self_regulation tried to modify {key} — not allowed")
        return

    try:
        c = _conn()
        old = c.execute("SELECT value FROM bot_config WHERE key=?", (key,)).fetchone()
        old_val = old["value"] if old else None

        if old_val == value:
            c.close()
            return

        c.execute("""
            INSERT OR REPLACE INTO bot_config (key, value, updated_at, reason)
            VALUES (?, ?, datetime('now'), ?)""", (key, value, reason))
        c.execute("""
            INSERT INTO config_audit_log (key, old_value, new_value, reason, triggered_by)
            VALUES (?, ?, ?, ?, 'self_regulation')""", (key, old_val, value, reason))
        c.commit()
        c.close()
        log.info(f"CFG {key}: {old_val!r} -> {value!r} [{reason}]")
    except Exception as e:
        log.error(f"Config update {key}: {e}")


def _apply_regime(regime, current_mode):
    """Apply regime changes — ONLY modifies regime_mode and scan_pause_until."""
    mode = regime["mode"]
    reason = regime["reason"]
    actions = []

    if mode == "paused" and current_mode != "paused":
        pause_until = int(time.time() + PAUSE_MINUTES * 60)
        _set_config("scan_pause_until", str(pause_until), f"auto_pause:{reason}")
        _set_config("regime_mode", "paused", f"regime->paused:{reason}")
        actions.append("paused")
        log.warning(f"PAUSE TRADING: {reason} (for {PAUSE_MINUTES} min)")

    elif mode == "normal" and current_mode in ("cautious", "paused"):
        _set_config("scan_pause_until", "0", "recovery")
        _set_config("regime_mode", "normal", f"regime->normal:{reason}")
        actions.append("recovered")
        log.info(f"RECOVERY: {reason}")

    elif mode == "cautious" and current_mode == "normal":
        _set_config("regime_mode", "cautious", f"regime->cautious:{reason}")
        actions.append("cautious")
        log.warning(f"CAUTIOUS MODE: {reason}")

    return actions


# ══════════════════════════════════════════════════════════════════════════════
# PER-TOKEN COOLDOWNS — blocks re-entry on tokens hitting repeated SLs
# ══════════════════════════════════════════════════════════════════════════════

def _check_token_streak(address, symbol):
    """Check if a token has hit SL too many times recently."""
    try:
        cutoff = (datetime.now(timezone.utc) - timedelta(minutes=STREAK_WINDOW_MIN)).isoformat()
        c = _conn()
        rows = c.execute("""
            SELECT * FROM trades
            WHERE (address=? OR token_address=?) AND timestamp>?
            ORDER BY timestamp DESC""", (address, address, cutoff)).fetchall()
        c.close()

        sl_count = sum(1 for r in rows if dict(r).get("exit_reason") == "stop_loss")
        return {"sl_count": sl_count, "needs_cooldown": sl_count >= STREAK_SL_THRESHOLD}
    except Exception as e:
        log.error(f"Token streak check: {e}")
        return {"sl_count": 0, "needs_cooldown": False}


def _set_token_cooldown(address, symbol, reason, sl_count=0):
    """Block a token from re-entry for COOLDOWN_MINUTES."""
    blocked_until = (datetime.now(timezone.utc) + timedelta(minutes=COOLDOWN_MINUTES)).isoformat()
    try:
        c = _conn()
        c.execute("""
            INSERT OR REPLACE INTO token_cooldowns
            (address, symbol, reason, sl_count, blocked_at, blocked_until, lifted_at, auto_lifted)
            VALUES (?, ?, ?, ?, datetime('now'), ?, NULL, 0)
        """, (address, symbol, reason, sl_count, blocked_until))
        c.commit()
        c.close()
        log.warning(f"COOLDOWN: {symbol} ({address[:8]}) for {COOLDOWN_MINUTES}min — {reason}")
    except Exception as e:
        log.error(f"Set cooldown: {e}")


def _lift_expired_cooldowns():
    """Auto-lift cooldowns that have expired."""
    try:
        c = _conn()
        c.execute("""
            UPDATE token_cooldowns
            SET lifted_at = datetime('now'), auto_lifted = 1
            WHERE blocked_until <= datetime('now')
              AND lifted_at IS NULL
              AND blocked_until < '2090-01-01'""")
        c.commit()
        c.close()
    except Exception as e:
        log.debug(f"Lift cooldowns: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def on_trade_closed(trade):
    """Called after every trade exit. Evaluates regime + token cooldowns."""
    if not _DB:
        return

    try:
        address = trade.get("token_address") or trade.get("address", "")
        symbol = trade.get("symbol", "?")
        current_mode = _get_config("regime_mode") or "normal"

        # Check if this token needs a cooldown
        if address and trade.get("exit_reason") == "stop_loss":
            diag = _check_token_streak(address, symbol)
            if diag["needs_cooldown"]:
                _set_token_cooldown(address, symbol,
                    f"sl_streak:{diag['sl_count']}x", diag["sl_count"])

        # Evaluate regime
        trades = _get_recent_trades(20)
        regime = _evaluate_regime(trades)
        actions = _apply_regime(regime, current_mode)

        # Record analysis
        new_mode = _get_config("regime_mode") or "normal"
        _record_analysis(trade, regime, actions, current_mode, new_mode)

    except Exception as e:
        log.error(f"on_trade_closed: {e}")


def run_cycle(last_trade=None):
    """Periodic regime check (called from heartbeat)."""
    if not _DB:
        return {"error": "not initialized"}

    try:
        _lift_expired_cooldowns()
        trades = _get_recent_trades(20)
        regime = _evaluate_regime(trades)
        current_mode = _get_config("regime_mode") or "normal"
        actions = _apply_regime(regime, current_mode)

        result = {
            "regime": regime["mode"], "wr": regime["win_rate"],
            "consec_sl": regime["consec_sl"], "actions": len(actions)
        }
        if actions:
            log.info(f"SR cycle: {result}")
        return result

    except Exception as e:
        log.error(f"run_cycle: {e}", exc_info=True)
        return {"error": str(e)}


def _record_analysis(trade, regime, actions, before, after):
    """Store trade analysis for review."""
    try:
        c = _conn()
        c.execute("""
            INSERT INTO trade_analysis
            (trade_timestamp, token_address, symbol, pnl_usd, pnl_pct,
             exit_reason, chg_pct_at_entry, mc_at_entry, liq_at_entry,
             findings, actions_taken, regime_before, regime_after)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (trade.get("timestamp"),
             trade.get("token_address") or trade.get("address"),
             trade.get("symbol"), trade.get("pnl_usd"), trade.get("pnl_pct"),
             trade.get("exit_reason"), trade.get("chg_pct"),
             trade.get("mc"), trade.get("liq"),
             json.dumps({"regime": regime}, default=str),
             json.dumps(actions), before, after))
        c.commit()
        c.close()
    except Exception as e:
        log.error(f"Record analysis: {e}")


async def heartbeat_loop(interval=HEARTBEAT_SEC):
    """Periodic regime evaluation."""
    log.info(f"SR heartbeat every {interval}s")
    while True:
        try:
            run_cycle()
        except Exception as e:
            log.error(f"Heartbeat: {e}")
        await asyncio.sleep(interval)


def is_scan_paused():
    """Check if trading is paused (used by main loop)."""
    try:
        val = _get_config("scan_pause_until")
        return float(val or 0) > time.time()
    except Exception:
        return False


def is_token_blocked(address):
    """Check if a specific token is on cooldown."""
    if not _DB or not address:
        return False, ""
    try:
        c = _conn()
        row = c.execute("""
            SELECT reason FROM token_cooldowns
            WHERE address=? AND blocked_until > datetime('now') AND lifted_at IS NULL
        """, (address,)).fetchone()
        c.close()
        return (True, row["reason"]) if row else (False, "")
    except Exception as e:
        log.debug(f"Token blocked check: {e}")
        return False, ""
