#!/usr/bin/env python3
"""
Lazarus v3.0 — Self-Learning Engine (Clean)

PURPOSE:
  - Analyze recent trade performance
  - Auto-blacklist rug tokens
  - Suggest position sizing within sane bounds
  - Track entry condition effectiveness

RULES:
  - Position sizing: 10-25% range (never below 10%, never above 25%)
  - Stop loss: 0.88-0.95 range
  - Only blacklists tokens that lost > 15% (confirmed rugs, not normal SL)
  - Learns from BOTH paper and live trades (paper=0 OR paper=1)
"""

import sqlite3
from datetime import datetime, timezone

V3_EPOCH = "2026-03-28T04:53:00"  # Only learn from v3 trades

DB_PATH = "/home/solbot/lazarus/logs/lazarus.db"


def upgrade_db():
    """Create learning tables if they don't exist."""
    c = sqlite3.connect(DB_PATH)
    c.executescript("""
        CREATE TABLE IF NOT EXISTS entry_conditions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, symbol TEXT, chg_h1 REAL, chg_m5 REAL,
            mc REAL, liq REAL, hourly_vol REAL, buy_pressure REAL,
            outcome TEXT, pnl_pct REAL
        );
        CREATE TABLE IF NOT EXISTS condition_performance (
            bucket TEXT PRIMARY KEY, wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0, avg_pnl REAL DEFAULT 0,
            last_updated TEXT
        );
        CREATE TABLE IF NOT EXISTS rug_blacklist (
            address TEXT PRIMARY KEY, symbol TEXT, ts TEXT, loss_pct REAL
        );
        CREATE TABLE IF NOT EXISTS dynamic_config (
            key TEXT PRIMARY KEY, value TEXT, reason TEXT, updated TEXT
        );
    """)
    c.commit()
    return c


def analyze_and_tune(c):
    """Analyze recent trades and update dynamic config with sane bounds."""

    # Learn from ALL trades (paper + live) — we need the data
    trades = c.execute("""
        SELECT symbol, token_address, pnl_pct, pnl_usd, source,
               timestamp, exit_reason, chg_pct, liq
        FROM trades WHERE timestamp >= ?
        ORDER BY timestamp DESC LIMIT 50
    """, (V3_EPOCH,)).fetchall()

    if not trades:
        print("No trades to learn from")
        return

    wins = [t for t in trades if (t[2] or 0) > 0]
    losses = [t for t in trades if (t[2] or 0) <= 0]
    wr = len(wins) / max(len(trades), 1)
    avg_pnl = sum(t[3] or 0 for t in trades) / max(len(trades), 1)
    now = datetime.now(timezone.utc).isoformat()

    print(f"Learning: {len(trades)} trades | WR={wr*100:.1f}% | avg=${avg_pnl:.4f}")

    # ── Auto-blacklist: only confirmed rugs (> 15% loss), not normal SLs ──
    for t in losses:
        pnl = t[2] or 0
        exit_reason = t[6] or ""
        addr = t[1]
        if pnl < -15.0 and addr and exit_reason in ("emergency_rug", "hard_floor", "stop_loss"):
            c.execute("""
                INSERT OR REPLACE INTO rug_blacklist (address, symbol, ts, loss_pct)
                VALUES (?,?,?,?)
            """, (addr, t[0], now, pnl))
            print(f"  BLACKLISTED: {t[0]} ({pnl:.1f}%) — {exit_reason}")

    # ── Position sizing — sane bounds: 10% to 25% ──
    #
    # Kelly-inspired: bet more when winning, less when losing
    # But never go below 10% (too small to matter) or above 25% (too risky)
    #
    if wr >= 0.55:
        new_pos = 0.25      # winning consistently → full size
        reason = f"WR={wr*100:.1f}% above 55% — full size"
    elif wr >= 0.45:
        new_pos = 0.20      # decent → standard size
        reason = f"WR={wr*100:.1f}% — standard size"
    elif wr >= 0.35:
        new_pos = 0.15      # struggling → reduced but meaningful
        reason = f"WR={wr*100:.1f}% — reduced size"
    else:
        new_pos = 0.10      # bad run → minimum viable size
        reason = f"WR={wr*100:.1f}% below 35% — minimum size"

    _set_config(c, "position_pct", str(new_pos), reason, now)
    print(f"  SIZE: {new_pos*100:.0f}% | {reason}")

    # ── Stop loss — based on average loss depth ──
    if losses:
        avg_loss = sum(t[2] or 0 for t in losses) / len(losses)
        if avg_loss < -15:
            new_sl = 0.90       # huge losses → tighter SL
            reason = f"avg_loss={avg_loss:.1f}% — tighter stop"
        elif avg_loss < -10:
            new_sl = 0.92       # moderate losses → standard
            reason = f"avg_loss={avg_loss:.1f}% — standard stop"
        else:
            new_sl = 0.94       # small losses → wider to avoid noise
            reason = f"avg_loss={avg_loss:.1f}% — wider stop (avoiding noise)"

        _set_config(c, "stop_loss", str(new_sl), reason, now)
        print(f"  SL: {(1-new_sl)*100:.0f}% | {reason}")

    # ── Entry condition analysis (for future optimization) ──
    _analyze_entry_conditions(c, trades)

    c.commit()


def _set_config(c, key, value, reason, now):
    c.execute("""
        INSERT OR REPLACE INTO dynamic_config (key, value, reason, updated)
        VALUES (?,?,?,?)
    """, (key, value, reason, now))


def _analyze_entry_conditions(c, trades):
    """Track which entry conditions (chg%, liq, mc) lead to wins vs losses."""
    now = datetime.now(timezone.utc).isoformat()

    # Bucket trades by chg_pct ranges
    buckets = {"chg_0_30": [], "chg_30_80": [], "chg_80_plus": []}
    for t in trades:
        chg = t[7] or 0  # chg_pct column
        pnl = t[2] or 0
        if chg < 30:
            buckets["chg_0_30"].append(pnl)
        elif chg < 80:
            buckets["chg_30_80"].append(pnl)
        else:
            buckets["chg_80_plus"].append(pnl)

    for bucket, pnls in buckets.items():
        if not pnls:
            continue
        wins = sum(1 for p in pnls if p > 0)
        losses = len(pnls) - wins
        avg = sum(pnls) / len(pnls)
        c.execute("""
            INSERT OR REPLACE INTO condition_performance (bucket, wins, losses, avg_pnl, last_updated)
            VALUES (?,?,?,?,?)
        """, (bucket, wins, losses, avg, now))


# NOTE: Do NOT auto-run on import. The bot calls these functions explicitly.
# This prevents the "writes 0.03 at import time" bug from the old version.
