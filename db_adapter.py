#!/usr/bin/env python3
"""
Lazarus Database Adapter — SQLite or PostgreSQL via environment config.

PURPOSE:
  Provides a unified Database interface that works with either SQLite (VPS/local)
  or PostgreSQL (Cloud SQL). The bot code calls the same methods regardless of
  which backend is active.

CONFIGURATION:
  Set DB_BACKEND env var to choose the backend:
    DB_BACKEND=sqlite   → uses SQLite at DB_PATH (default, matches VPS behavior)
    DB_BACKEND=postgres → uses PostgreSQL via DATABASE_URL

  For PostgreSQL, set:
    DATABASE_URL=postgresql://user:password@host:5432/lazarus

DESIGN:
  - SQLite path is unchanged from lazarus.py — this module wraps it
  - PostgreSQL uses psycopg2 (the standard Python Postgres driver)
  - Both backends expose identical methods: record_trade, get_daily_pnl, etc.
  - The adapter is a DROP-IN replacement for the Database class in lazarus.py
  - SQLite remains the fallback — if DB_BACKEND is unset, SQLite is used
"""

import os
import sqlite3
import threading
import time
import logging
from datetime import datetime, timezone
from typing import Dict, Optional, List

log = logging.getLogger("fort_v2")

DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").lower()
DATABASE_URL = os.environ.get("DATABASE_URL", "")
SQLITE_PATH = os.environ.get("LAZARUS_DB_PATH", "/home/solbot/lazarus/logs/lazarus.db")

# ══════════════════════════════════════════════════════════════════════════════
# POSTGRESQL SCHEMA — translated from SQLite in lazarus.py
#
# Key differences from SQLite:
#   - INTEGER PRIMARY KEY AUTOINCREMENT → SERIAL PRIMARY KEY
#   - REAL → DOUBLE PRECISION
#   - INSERT OR REPLACE → INSERT ... ON CONFLICT ... DO UPDATE
#   - No executescript() — use execute() with multi-statement strings
# ══════════════════════════════════════════════════════════════════════════════
PG_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id SERIAL PRIMARY KEY,
    timestamp TEXT, symbol TEXT, token_address TEXT, wallet TEXT,
    entry_price_sol DOUBLE PRECISION, exit_price_sol DOUBLE PRECISION,
    pnl_usd DOUBLE PRECISION, pnl_pct DOUBLE PRECISION,
    size_usd DOUBLE PRECISION, paper INTEGER DEFAULT 0, source TEXT,
    exit_reason TEXT, score DOUBLE PRECISION, hourly DOUBLE PRECISION,
    chg_pct DOUBLE PRECISION, mc DOUBLE PRECISION, liq DOUBLE PRECISION,
    rug_risk TEXT, trailing_tp_activated INTEGER DEFAULT 0,
    smart_money_confirmed INTEGER DEFAULT 0, hour_utc INTEGER,
    day_of_week INTEGER, address TEXT, entry DOUBLE PRECISION,
    tx_buy TEXT, tx_sell TEXT, peak_pnl_pct DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS signal_performance (
    source TEXT PRIMARY KEY, wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0, total_pnl DOUBLE PRECISION DEFAULT 0.0,
    last_updated TEXT
);

CREATE TABLE IF NOT EXISTS wallet_activity (
    id SERIAL PRIMARY KEY,
    ts TEXT, wallet TEXT, token_addr TEXT, token_sym TEXT, action TEXT
);

CREATE TABLE IF NOT EXISTS cooldowns (
    token_address TEXT PRIMARY KEY,
    symbol TEXT, expires_at DOUBLE PRECISION, entry_count INTEGER DEFAULT 1
);

CREATE TABLE IF NOT EXISTS daily_pnl (
    date TEXT PRIMARY KEY, total_pnl DOUBLE PRECISION DEFAULT 0.0,
    trade_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS balance_snapshots (
    id SERIAL PRIMARY KEY,
    timestamp TEXT, portfolio_usd DOUBLE PRECISION, deposited_usd DOUBLE PRECISION,
    growth_usd DOUBLE PRECISION, tax_vault_usd DOUBLE PRECISION,
    btc_bridged_usd DOUBLE PRECISION, eth_bridged_usd DOUBLE PRECISION,
    net_worth_usd DOUBLE PRECISION, daily_stake_usd DOUBLE PRECISION,
    weekly_crawl_multiplier DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS btc_eth_pillars (
    id SERIAL PRIMARY KEY,
    timestamp TEXT, btc_price DOUBLE PRECISION, eth_price DOUBLE PRECISION,
    btc_change_4h DOUBLE PRECISION, eth_change_4h DOUBLE PRECISION,
    crash_active INTEGER DEFAULT 0, dip_buy_active INTEGER DEFAULT 0
);
"""

# SQLite schema — identical to lazarus.py Database._init_tables()
SQLITE_SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, symbol TEXT, token_address TEXT, wallet TEXT,
    entry_price_sol REAL, exit_price_sol REAL, pnl_usd REAL, pnl_pct REAL,
    size_usd REAL, paper INTEGER DEFAULT 0, source TEXT, exit_reason TEXT,
    score REAL, hourly REAL, chg_pct REAL, mc REAL, liq REAL,
    rug_risk TEXT, trailing_tp_activated INTEGER DEFAULT 0,
    smart_money_confirmed INTEGER DEFAULT 0, hour_utc INTEGER,
    day_of_week INTEGER, address TEXT, entry REAL,
    tx_buy TEXT, tx_sell TEXT, peak_pnl_pct REAL
);
CREATE TABLE IF NOT EXISTS signal_performance (
    source TEXT PRIMARY KEY, wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0, total_pnl REAL DEFAULT 0.0,
    last_updated TEXT
);
CREATE TABLE IF NOT EXISTS wallet_activity (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, wallet TEXT, token_addr TEXT, token_sym TEXT, action TEXT
);
CREATE TABLE IF NOT EXISTS cooldowns (
    token_address TEXT PRIMARY KEY,
    symbol TEXT, expires_at REAL, entry_count INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS daily_pnl (
    date TEXT PRIMARY KEY, total_pnl REAL DEFAULT 0.0, trade_count INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS balance_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, portfolio_usd REAL, deposited_usd REAL,
    growth_usd REAL, tax_vault_usd REAL, btc_bridged_usd REAL,
    eth_bridged_usd REAL, net_worth_usd REAL, daily_stake_usd REAL,
    weekly_crawl_multiplier REAL
);
CREATE TABLE IF NOT EXISTS btc_eth_pillars (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT, btc_price REAL, eth_price REAL,
    btc_change_4h REAL, eth_change_4h REAL,
    crash_active INTEGER DEFAULT 0, dip_buy_active INTEGER DEFAULT 0
);
"""


class DatabaseAdapter:
    """
    Unified database interface — same methods, swappable backend.

    Usage:
        db = DatabaseAdapter()  # reads DB_BACKEND env var
        db.record_trade(...)    # works on both SQLite and Postgres
    """

    def __init__(self):
        self.backend = DB_BACKEND
        self._lock = threading.Lock()

        if self.backend == "postgres":
            self._init_postgres()
        else:
            self._init_sqlite()

        self._init_tables()
        log.info(f"Database adapter: using {self.backend}")

    # ── Backend initialization ───────────────────────────────────────────

    def _init_sqlite(self):
        os.makedirs(os.path.dirname(SQLITE_PATH), exist_ok=True)
        self.conn = sqlite3.connect(SQLITE_PATH, check_same_thread=False, timeout=10)

    def _init_postgres(self):
        try:
            import psycopg2
            self.conn = psycopg2.connect(DATABASE_URL)
            self.conn.autocommit = False
        except ImportError:
            log.error("psycopg2 not installed — falling back to SQLite")
            self.backend = "sqlite"
            self._init_sqlite()
        except Exception as e:
            log.error(f"Postgres connection failed: {e} — falling back to SQLite")
            self.backend = "sqlite"
            self._init_sqlite()

    def _init_tables(self):
        if self.backend == "postgres":
            cursor = self.conn.cursor()
            cursor.execute(PG_SCHEMA)
            self.conn.commit()
            cursor.close()
        else:
            self.conn.executescript(SQLITE_SCHEMA)
            self.conn.commit()

    # ── Query helpers (handle ? vs %s placeholder difference) ────────────

    def _ph(self, sql: str) -> str:
        """Convert SQLite ? placeholders to Postgres %s if needed."""
        if self.backend == "postgres":
            return sql.replace("?", "%s")
        return sql

    def _execute(self, sql: str, params: tuple = ()):
        """Execute a query with backend-appropriate placeholders."""
        sql = self._ph(sql)
        if self.backend == "postgres":
            cursor = self.conn.cursor()
            cursor.execute(sql, params)
            return cursor
        else:
            return self.conn.execute(sql, params)

    def _commit(self):
        self.conn.commit()

    # ── Trade recording ──────────────────────────────────────────────────

    def record_trade(self, sym: str, addr: str, entry: float, exit_p: float,
                     pnl_usd: float, pnl_pct: float, sol_spent: float,
                     paper: bool, source: str, wallet: str,
                     exit_reason: str = "unknown",
                     tx_buy: str = None, tx_sell: str = None, **kwargs):
        with self._lock:
            now = datetime.now(timezone.utc)
            self._execute("""
                INSERT INTO trades
                (timestamp, symbol, token_address, wallet, entry_price_sol, exit_price_sol,
                 pnl_usd, pnl_pct, size_usd, paper, source, exit_reason,
                 score, hourly, chg_pct, mc, liq, rug_risk,
                 trailing_tp_activated, smart_money_confirmed,
                 hour_utc, day_of_week, address, entry, tx_buy, tx_sell, peak_pnl_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (now.isoformat(), sym, addr, wallet, entry, exit_p,
                 pnl_usd, pnl_pct, sol_spent, 1 if paper else 0,
                 source, exit_reason,
                 kwargs.get("score", 0), kwargs.get("hourly", 0),
                 kwargs.get("chg_pct", 0), kwargs.get("mc", 0),
                 kwargs.get("liq", 0),
                 "low" if kwargs.get("liq", 0) > 50000 else "high",
                 1 if kwargs.get("trailing_tp") else 0,
                 1 if kwargs.get("smart_money") else 0,
                 now.hour, now.weekday(), addr, entry,
                 tx_buy, tx_sell, kwargs.get("peak_pnl_pct")))

            today = now.strftime("%Y-%m-%d")
            if self.backend == "postgres":
                self._execute("""
                    INSERT INTO daily_pnl (date, total_pnl, trade_count)
                    VALUES (%s, %s, 1)
                    ON CONFLICT(date) DO UPDATE SET
                        total_pnl = daily_pnl.total_pnl + %s,
                        trade_count = daily_pnl.trade_count + 1""",
                    (today, pnl_usd, pnl_usd))
            else:
                self._execute("""
                    INSERT INTO daily_pnl (date, total_pnl, trade_count)
                    VALUES (?, ?, 1)
                    ON CONFLICT(date) DO UPDATE SET
                        total_pnl = total_pnl + ?, trade_count = trade_count + 1""",
                    (today, pnl_usd, pnl_usd))
            self._commit()

    # ── Signal performance ───────────────────────────────────────────────

    def record_signal_result(self, source: str, won: bool, pnl: float):
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            if self.backend == "postgres":
                self._execute("""
                    INSERT INTO signal_performance (source, wins, losses, total_pnl, last_updated)
                    VALUES (%s,%s,%s,%s,%s)
                    ON CONFLICT(source) DO UPDATE SET
                        wins = signal_performance.wins + %s,
                        losses = signal_performance.losses + %s,
                        total_pnl = signal_performance.total_pnl + %s,
                        last_updated = %s""",
                    (source, int(won), int(not won), pnl, now,
                     int(won), int(not won), pnl, now))
            else:
                self._execute("""
                    INSERT INTO signal_performance (source, wins, losses, total_pnl, last_updated)
                    VALUES (?,?,?,?,?)
                    ON CONFLICT(source) DO UPDATE SET
                        wins = wins + ?, losses = losses + ?,
                        total_pnl = total_pnl + ?, last_updated = ?""",
                    (source, int(won), int(not won), pnl, now,
                     int(won), int(not won), pnl, now))
            self._commit()

    def get_signal_weights(self) -> Dict[str, float]:
        rows = self._execute(
            "SELECT source, wins, losses, total_pnl FROM signal_performance"
        ).fetchall()
        weights = {}
        for source, wins, losses, pnl in rows:
            total = wins + losses
            weights[source] = (wins / total * (1 + pnl / 100)) if total >= 5 else 0.5
        return weights

    # ── Daily PnL ────────────────────────────────────────────────────────

    def get_daily_pnl(self) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._execute(
            "SELECT total_pnl FROM daily_pnl WHERE date=?", (today,)
        ).fetchone()
        return row[0] if row else 0.0

    # ── Token tracking ───────────────────────────────────────────────────

    def get_token_entry_count_today(self, address: str) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self._execute(
            "SELECT COUNT(*) FROM trades WHERE token_address=? AND timestamp LIKE ?",
            (address, f"{today}%")
        ).fetchone()
        return row[0] if row else 0

    # ── Cooldowns ────────────────────────────────────────────────────────

    def set_cooldown(self, address: str, symbol: str, duration_sec: int):
        with self._lock:
            if self.backend == "postgres":
                self._execute("""
                    INSERT INTO cooldowns (token_address, symbol, expires_at, entry_count)
                    VALUES (%s, %s, %s, 1)
                    ON CONFLICT(token_address) DO UPDATE SET
                        symbol = %s, expires_at = %s,
                        entry_count = cooldowns.entry_count + 1""",
                    (address, symbol, time.time() + duration_sec,
                     symbol, time.time() + duration_sec))
            else:
                self._execute("""
                    INSERT OR REPLACE INTO cooldowns (token_address, symbol, expires_at, entry_count)
                    VALUES (?, ?, ?, COALESCE(
                        (SELECT entry_count + 1 FROM cooldowns WHERE token_address = ?), 1
                    ))""", (address, symbol, time.time() + duration_sec, address))
            self._commit()

    def is_on_cooldown(self, address: str) -> bool:
        row = self._execute(
            "SELECT expires_at FROM cooldowns WHERE token_address=? AND expires_at > ?",
            (address, time.time())
        ).fetchone()
        return row is not None

    def clean_expired_cooldowns(self):
        with self._lock:
            self._execute("DELETE FROM cooldowns WHERE expires_at <= ?", (time.time(),))
            self._commit()

    # ── Summary ──────────────────────────────────────────────────────────

    def print_summary(self, paper: bool):
        row = self._execute("""
            SELECT COUNT(*), SUM(pnl_usd),
                   SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END), AVG(pnl_pct)
            FROM trades WHERE paper=?""", (1 if paper else 0,)).fetchone()
        if row[0]:
            mode = "PAPER" if paper else "LIVE"
            log.info(f"[{mode}] trades={row[0]} | pnl=${row[1] or 0:.2f} | "
                     f"wins={row[2]} | avg={row[3] or 0:.1f}%")

    # ── Cleanup ──────────────────────────────────────────────────────────

    def close(self):
        self.conn.close()
