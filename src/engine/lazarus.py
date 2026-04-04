#!/usr/bin/env python3
"""
Lazarus v3.0 — Unified Clean Rewrite
Goal: $20,000 from $250 via Solana momentum scalping

ARCHITECTURE:
  CFG dict           = single source of truth for all config
  EnvLoader          = custom .env reader (never use dotenv)
  curl_get()         = all external HTTP (never use aiohttp for external APIs)
  aiohttp            = only for RPC + Jupiter (internal Solana calls)
  Database           = all DB operations (thread-safe)
  BirdeyeScanner     = DexScreener-based token discovery + filtering
  SmartMoneyScanner  = copy-trading from known wallets
  SignalAggregator   = merges signals, deduplicates, applies cooldowns
  TradeExecutor      = buy/monitor/sell logic
  main()             = event loop

HOTFIX LOG:
  [1] aiohttp fails for external APIs -> always use curl_get()
  [2] dotenv breaks on quoted .env values -> use EnvLoader class
  [3] VersionedTransaction.sign() removed -> use VersionedTransaction(msg, [KP])
  [4] skipPreflight must be True for memecoin swaps
  [5] quote-api.jup.ag deprecated -> use public.jupiterapi.com
  [6] Birdeye Standard only returns large caps -> switched to DexScreener
"""

import asyncio
import aiohttp
import sqlite3
import logging
import json
import base64
import subprocess
import time
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional, List, Dict, Set
from collections import defaultdict

import base58
from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

# Data integrity validation (5-layer protection)
try:
    from data_integrity import (
        validate_epoch_query, validate_startup_config,
        check_data_anomalies, V31_EPOCH, PARAM_BOUNDS,
    )
    _DI = True
except ImportError:
    _DI = False
    V31_EPOCH = "2026-03-29T17:44:00"

# Optional modules (graceful degradation if missing)
try:
    from prepump_tracker import PrePumpTracker, FilterCounter, EARLY_ENTRY_FILTERS
    _tracker = PrePumpTracker()
    _fcount = FilterCounter()
except ImportError:
    _tracker = None
    _fcount = None

try:
    from dash_bridge import bridge
except ImportError:
    # Stub if dashboard not available
    class _Stub:
        def __getattr__(self, _): return lambda *a, **kw: None
    bridge = _Stub()


# ══════════════════════════════════════════════════════════════════════════════
# LOGGING — single setup, never duplicate
# ══════════════════════════════════════════════════════════════════════════════
os.makedirs("/home/solbot/lazarus/logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("/home/solbot/lazarus/logs/lazarus.log"),
    ],
)
log = logging.getLogger("fort_v2")


# ══════════════════════════════════════════════════════════════════════════════
# ENV LOADER — custom .env parser (handles all quote styles)
# ══════════════════════════════════════════════════════════════════════════════
class EnvLoader:
    def __init__(self, path: str = "/home/solbot/lazarus/.env"):
        self.data: Dict[str, str] = {}
        try:
            for raw in open(path).read().splitlines():
                line = raw.strip().strip("'").strip('"')
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                self.data[k.strip().strip("'\"")]  = v.strip().strip("'\"")
        except Exception as e:
            log.error(f"EnvLoader: {e}")

    def get(self, key: str, default: str = "") -> str:
        return self.data.get(key, default)


ENV = EnvLoader()


# ══════════════════════════════════════════════════════════════════════════════
# CONFIG — single source of truth (edit values HERE only)
# ══════════════════════════════════════════════════════════════════════════════
WSOL = "So11111111111111111111111111111111111111112"
DB_PATH = "/home/solbot/lazarus/logs/lazarus.db"

CFG: Dict = {
    # ── APIs ──────────────────────────────────────────────────────────────
    "birdeye_key":  ENV.get("BIRDEYE_API_KEY"),
    "rpc_url":      ENV.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com"),

    # ── Position sizing ───────────────────────────────────────────────────
    "position_pct":     0.15,       # 15% per trade (floor: 10%, ceiling: 30%)
    "max_positions":    1,          # one trade at a time
    "min_sol_balance":  0.05,       # never trade below this
    "paper_capital_usd": 10_000,    # virtual capital for paper mode ($10k)

    # ── Exit rules ────────────────────────────────────────────────────────
    "take_profit":      1.25,       # +25% TP
    "stop_loss":        0.92,       # -8% SL (wider to avoid noise, compensated by hard floor)
    "hard_floor":       0.85,       # -15% ABSOLUTE kill switch — no exceptions, any time
    "trail_arm":        1.08,       # arm trailing stop at +8%
    "trail_pct":        0.04,       # trail 4% below peak once armed
    "max_hold_sec":     600,        # 10min timeout for unarmed trades
    "monitor_interval": 3,          # 3s price checks
    "sniper_timeout_sec": 60,       # cut non-runners after 60s if < +1%

    # ── Scanner filters ───────────────────────────────────────────────────
    "min_hourly_vol":   800,        # minimum 1h volume USD
    "min_chg_pct":      10.0,       # lowered from 20 — opens the entry window
    "max_chg_pct":      80.0,       # raised from 60 — data shows 30-80% is the sweet spot
    "min_m5_pct":       0.5,        # 5-minute momentum must be positive
    "min_mc":           10_000,     # minimum market cap
    "max_mc":           10_000_000, # maximum market cap
    "min_liq":          50_000,     # minimum liquidity (sub-50K is graveyard)
    "min_vmr":          0.10,       # volume-to-MC ratio floor
    "min_pair_age_min": 60,         # pair must be at least 60 min old
    "scan_interval":    30,         # seconds between scan cycles

    # ── Cooldowns ─────────────────────────────────────────────────────────
    "cooldown_seconds":     7200,   # 2 HOURS per-token cooldown after exit
    "max_entries_per_token": 2,     # max 2 entries per token per day
    "daily_loss_limit_pct": 10.0,   # stop trading after losing 10% in a day

    # ── BTC/ETH market safety ─────────────────────────────────────────────
    "btc_crash_threshold":  -5.0,   # pause trading if BTC drops > 5% in 4h
    "eth_crash_threshold":  -7.0,   # pause trading if ETH drops > 7% in 4h

    # ── Smart money wallets ───────────────────────────────────────────────
    "smart_wallets": [
        "9WzDXwBbmkg8ZTbNMqUxvQRAyrZzDsGYdLVL9zYtAWWM",
        "ASTyfSima4LLAdDgoFGkgqoKowG1LZFDr9fAQrg7iaJZ",
        "GUfCR9mK6azb9vcpsxgXyj7XRPAaEqoGMxksMQFKbcGJ",
        "DfXygSm4jCyNCybVYYK6DwvWqjKee8pbDmJGcLWNDXjh",
        "7R3nxGFMaeMoKmVzA5UQrARzECkLQqCU7KBDMfbBPNDK",
    ],

    # ── Multi-wallet dispatcher (Phase 2) ────────────────────────────────
    "dispatcher_enabled":   False,      # Set True to activate multi-wallet routing
    "executor_addresses":   [],         # Populated from .env EXEC_WALLET_*_KEY
    "wallet_cooldown_sec":  60,         # Post-trade cooldown per executor wallet

    # ── Blacklisted tokens ────────────────────────────────────────────────
    "blacklist": {
        WSOL,
        "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
        "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",  # USDT
        "CphSpRKm3Ei6NzPWucLoMtqbQvomyXm8yEcLBERmFsnu",  # fake SOL
        "MwzZZYSx3bLyRuxr7D24qsZignd27heyXx1uggUbonk",   # moon — repeated SL hits
        "6XjY7mBgYNEV8tk6NxybMF1RdkSuWopCSHW9ejJ5DHwn",   # IMAGINE — repeated SL hits
    },
}

PAPER = ENV.get("PAPER_TRADING", "false").lower() == "true"

# ── Dispatcher config from .env ──────────────────────────────────────────
_disp = ENV.get("DISPATCHER_ENABLED", "false").lower() == "true"
if _disp:
    # Load executor addresses from .env keys (EXEC_WALLET_1_KEY ... EXEC_WALLET_5_KEY)
    _exec_addrs = []
    for i in range(1, 6):
        pk = ENV.get(f"EXEC_WALLET_{i}_KEY", "")
        if pk:
            try:
                kp = Keypair.from_base58_string(pk)
                _exec_addrs.append(str(kp.pubkey()))
            except Exception as e:
                log.warning(f"Invalid EXEC_WALLET_{i}_KEY: {e}")
    if _exec_addrs:
        CFG["dispatcher_enabled"] = True
        CFG["executor_addresses"] = _exec_addrs
        log.info(f"Dispatcher: {len(_exec_addrs)} executors loaded")
    else:
        log.warning("DISPATCHER_ENABLED=true but no valid executor keys found — disabled")
del _disp

log.info(f"Birdeye key : {CFG['birdeye_key'][:8]}... len={len(CFG['birdeye_key'])}")
log.info(f"RPC         : {CFG['rpc_url'][:50]}")
log.info(f"Mode        : {'PAPER' if PAPER else 'LIVE'}")


# ══════════════════════════════════════════════════════════════════════════════
# KEYPAIR
# ══════════════════════════════════════════════════════════════════════════════
def load_keypair() -> Keypair:
    raw = ENV.get("SOLANA_PRIVATE_KEY").strip()
    if not raw:
        raise SystemExit("FATAL: SOLANA_PRIVATE_KEY missing from .env")
    if raw.startswith("["):
        return Keypair.from_bytes(bytes(json.loads(raw)))
    return Keypair.from_bytes(base58.b58decode(raw))

KP = load_keypair()
WALLET = str(KP.pubkey())
log.info(f"Wallet      : {WALLET}")


# ══════════════════════════════════════════════════════════════════════════════
# HTTP — curl_get() for ALL external APIs, no exceptions
# ══════════════════════════════════════════════════════════════════════════════
def curl_get(url: str, headers: Dict = None, timeout: int = 30) -> Dict:
    cmd = ["curl", "-s", "--max-time", str(timeout)]
    if headers:
        for k, v in headers.items():
            cmd += ["-H", f"{k}: {v}"]
    cmd.append(url)
    try:
        out = subprocess.check_output(cmd, timeout=timeout + 5, stderr=subprocess.DEVNULL)
        return json.loads(out)
    except subprocess.TimeoutExpired:
        log.warning(f"curl timeout: {url[:70]}")
    except json.JSONDecodeError as e:
        log.warning(f"curl json error: {e} url={url[:70]}")
    except Exception as e:
        log.warning(f"curl error: {e}")
    return {}


# ══════════════════════════════════════════════════════════════════════════════
# SIGNAL DATA TYPE
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Signal:
    symbol:   str
    address:  str
    price:    float
    source:   str
    score:    float = 0.0
    hourly:   float = 0.0
    chg_pct:  float = 0.0
    mc:       float = 0.0
    liq:      float = 0.0
    extra:    Dict  = field(default_factory=dict)


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE — thread-safe, all tables in one place
# ══════════════════════════════════════════════════════════════════════════════
class Database:
    def __init__(self, path: str = DB_PATH):
        self.conn = sqlite3.connect(path, check_same_thread=False, timeout=10)
        self._lock = threading.Lock()
        self._init_tables()

    def _init_tables(self):
        self.conn.executescript("""
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
        """)
        self.conn.commit()

    def record_trade(self, sym, addr, entry, exit_p, pnl_usd, pnl_pct,
                     sol_spent, paper, source, exit_reason="unknown",
                     tx_buy=None, tx_sell=None, **kwargs):
        with self._lock:
            now = datetime.now(timezone.utc)
            self.conn.execute("""
                INSERT INTO trades
                (timestamp, symbol, token_address, wallet, entry_price_sol, exit_price_sol,
                 pnl_usd, pnl_pct, size_usd, paper, source, exit_reason,
                 score, hourly, chg_pct, mc, liq, rug_risk,
                 trailing_tp_activated, smart_money_confirmed,
                 hour_utc, day_of_week, address, entry, tx_buy, tx_sell, peak_pnl_pct)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (now.isoformat(), sym, addr, WALLET, entry, exit_p,
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
            # Update daily PnL tracker
            today = now.strftime("%Y-%m-%d")
            self.conn.execute("""
                INSERT INTO daily_pnl (date, total_pnl, trade_count)
                VALUES (?, ?, 1)
                ON CONFLICT(date) DO UPDATE SET
                    total_pnl = total_pnl + ?, trade_count = trade_count + 1""",
                (today, pnl_usd, pnl_usd))
            self.conn.commit()

    def record_signal_result(self, source: str, won: bool, pnl: float):
        with self._lock:
            now = datetime.now(timezone.utc).isoformat()
            self.conn.execute("""
                INSERT INTO signal_performance (source, wins, losses, total_pnl, last_updated)
                VALUES (?,?,?,?,?)
                ON CONFLICT(source) DO UPDATE SET
                    wins = wins + ?, losses = losses + ?,
                    total_pnl = total_pnl + ?, last_updated = ?""",
                (source, int(won), int(not won), pnl, now,
                 int(won), int(not won), pnl, now))
            self.conn.commit()

    def get_signal_weights(self) -> Dict[str, float]:
        rows = self.conn.execute(
            "SELECT source, wins, losses, total_pnl FROM signal_performance"
        ).fetchall()
        weights = {}
        for source, wins, losses, pnl in rows:
            total = wins + losses
            weights[source] = (wins / total * (1 + pnl / 100)) if total >= 5 else 0.5
        return weights

    def get_daily_pnl(self) -> float:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT total_pnl FROM daily_pnl WHERE date=?", (today,)
        ).fetchone()
        return row[0] if row else 0.0

    def get_token_entry_count_today(self, address: str) -> int:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        row = self.conn.execute(
            "SELECT COUNT(*) FROM trades WHERE token_address=? AND timestamp LIKE ?",
            (address, f"{today}%")
        ).fetchone()
        return row[0] if row else 0

    def set_cooldown(self, address: str, symbol: str, duration_sec: int):
        with self._lock:
            self.conn.execute("""
                INSERT OR REPLACE INTO cooldowns (token_address, symbol, expires_at, entry_count)
                VALUES (?, ?, ?, COALESCE(
                    (SELECT entry_count + 1 FROM cooldowns WHERE token_address = ?), 1
                ))""", (address, symbol, time.time() + duration_sec, address))
            self.conn.commit()

    def is_on_cooldown(self, address: str) -> bool:
        row = self.conn.execute(
            "SELECT expires_at FROM cooldowns WHERE token_address=? AND expires_at > ?",
            (address, time.time())
        ).fetchone()
        return row is not None

    def clean_expired_cooldowns(self):
        with self._lock:
            self.conn.execute("DELETE FROM cooldowns WHERE expires_at <= ?", (time.time(),))
            self.conn.commit()

    def print_summary(self):
        t = self.conn.execute("""
            SELECT COUNT(*), SUM(pnl_usd),
                   SUM(CASE WHEN pnl_usd > 0 THEN 1 ELSE 0 END), AVG(pnl_pct)
            FROM trades WHERE paper=?""", (1 if PAPER else 0,)).fetchone()
        if t[0]:
            mode = "PAPER" if PAPER else "LIVE"
            log.info(f"[{mode}] trades={t[0]} | pnl=${t[1] or 0:.2f} | wins={t[2]} | avg={t[3] or 0:.1f}%")


# ══════════════════════════════════════════════════════════════════════════════
# LAYER 1: SAFE EPOCH QUERY — validates epoch queries before execution
# ══════════════════════════════════════════════════════════════════════════════
def safe_epoch_query(db_conn, query, params=None):
    """Wrapper that validates epoch queries before execution (Layer 1)."""
    if _DI:
        query_check = validate_epoch_query(query)
        if not query_check["valid"]:
            log.error(f"[QUERY] BLOCKED unsafe epoch query: {query_check['reason']}")
            raise ValueError(f"Unsafe epoch query: {query_check['reason']}")
    return db_conn.execute(query, params or [])


# ══════════════════════════════════════════════════════════════════════════════
# BTC/ETH MARKET SAFETY — pause trading during broad market crashes
# ══════════════════════════════════════════════════════════════════════════════
_market_cache = {"btc": 0.0, "eth": 0.0, "btc_4h": 0.0, "eth_4h": 0.0, "ts": 0}

def check_market_safety() -> tuple:
    """Returns (is_safe: bool, reason: str). Checks BTC/ETH for crashes."""
    now = time.time()
    if now - _market_cache["ts"] < 300:  # cache 5 min
        btc_chg = _market_cache["btc_4h"]
        eth_chg = _market_cache["eth_4h"]
    else:
        try:
            # BTC price from DexScreener (BTC/USDT on Solana or use CoinGecko-style)
            btc_data = curl_get(
                "https://api.dexscreener.com/latest/dex/search?q=BTC%20USDT", timeout=8
            )
            eth_data = curl_get(
                "https://api.dexscreener.com/latest/dex/search?q=ETH%20USDT", timeout=8
            )
            btc_pairs = [p for p in btc_data.get("pairs", [])
                         if p.get("baseToken", {}).get("symbol", "").upper() in ("BTC", "WBTC")
                         and float(p.get("liquidity", {}).get("usd", 0) or 0) > 1_000_000]
            eth_pairs = [p for p in eth_data.get("pairs", [])
                         if p.get("baseToken", {}).get("symbol", "").upper() in ("ETH", "WETH")
                         and float(p.get("liquidity", {}).get("usd", 0) or 0) > 1_000_000]

            btc_chg = float(btc_pairs[0].get("priceChange", {}).get("h6", 0) or 0) if btc_pairs else 0
            eth_chg = float(eth_pairs[0].get("priceChange", {}).get("h6", 0) or 0) if eth_pairs else 0
            btc_price = float(btc_pairs[0].get("priceUsd", 0) or 0) if btc_pairs else 0
            eth_price = float(eth_pairs[0].get("priceUsd", 0) or 0) if eth_pairs else 0

            _market_cache.update({"btc": btc_price, "eth": eth_price,
                                  "btc_4h": btc_chg, "eth_4h": eth_chg, "ts": now})
        except Exception as e:
            log.warning(f"Market safety check failed: {e}")
            btc_chg = eth_chg = 0

    if btc_chg < CFG["btc_crash_threshold"]:
        return False, f"BTC crash: {btc_chg:.1f}% (threshold: {CFG['btc_crash_threshold']}%)"
    if eth_chg < CFG["eth_crash_threshold"]:
        return False, f"ETH crash: {eth_chg:.1f}% (threshold: {CFG['eth_crash_threshold']}%)"
    return True, "ok"


# ══════════════════════════════════════════════════════════════════════════════
# SOL PRICE + BALANCE
# ══════════════════════════════════════════════════════════════════════════════
_sol_price_cache = {"price": 140.0, "ts": 0}

def get_sol_price() -> float:
    now = time.time()
    if now - _sol_price_cache["ts"] < 60:
        return _sol_price_cache["price"]
    try:
        r = curl_get(
            "https://api.dexscreener.com/latest/dex/pairs/solana/"
            "8sLbNZoA1cfnvMJLPfp98ZLAnFSYCFApfJKMbiXNLwxj", timeout=8)
        price = float((r.get("pair") or {}).get("priceUsd") or 0)
        if price > 10:
            _sol_price_cache.update({"price": price, "ts": now})
            return price
    except Exception:
        pass
    return _sol_price_cache["price"]

_balance_cache = {"value": 0.0}

async def rpc_get_balance(session: aiohttp.ClientSession) -> float:
    try:
        p = {"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [WALLET]}
        async with session.post(CFG["rpc_url"], json=p,
                                timeout=aiohttp.ClientTimeout(total=10)) as r:
            d = await r.json()
            bal = d.get("result", {}).get("value", 0) / 1e9
            if bal > 0:
                _balance_cache["value"] = bal
            return bal
    except Exception as e:
        log.error(f"get_balance failed: {e} — using cached {_balance_cache['value']:.4f} SOL")
        return _balance_cache["value"]

async def birdeye_price(session: aiohttp.ClientSession, addr: str) -> float:
    try:
        hdrs = {"X-API-KEY": CFG["birdeye_key"]}
        url = f"https://public-api.birdeye.so/defi/price?address={addr}"
        async with session.get(url, headers=hdrs,
                               timeout=aiohttp.ClientTimeout(total=10)) as r:
            d = await r.json()
            return d.get("data", {}).get("value", 0) or 0.0
    except Exception:
        return 0.0


# ══════════════════════════════════════════════════════════════════════════════
# SCANNERS — each returns List[Signal]
# ══════════════════════════════════════════════════════════════════════════════
class BirdeyeScanner:
    """DexScreener-based momentum scanner. No API key needed."""
    SOURCE_ID = "dexscreener_momentum"

    def __init__(self):
        self._addr_cache: Dict = {"addrs": [], "cycle": 0}
        self._last_chg: Dict[str, float] = {}

    def _discover_tokens(self) -> List[str]:
        """Multi-source token discovery via DexScreener."""
        # Use cache for 3 cycles to reduce API load
        if self._addr_cache["addrs"] and self._addr_cache["cycle"] < 3:
            self._addr_cache["cycle"] += 1
            log.info(f"DexScreener: cached {len(self._addr_cache['addrs'])} addrs "
                     f"(cycle {self._addr_cache['cycle']}/3)")
            return self._addr_cache["addrs"]
        self._addr_cache["cycle"] = 0

        addrs, seen = [], set()
        skip_syms = {"SOL", "WSOL", "USDC", "USDT", "WBTC", "ETH"}

        def add(addr):
            if addr and addr not in seen and addr != WSOL and addr not in CFG["blacklist"]:
                seen.add(addr); addrs.append(addr)

        def add_from_pairs(pairs):
            for p in pairs:
                if p.get("chainId") != "solana":
                    continue
                base = p.get("baseToken", {})
                if base.get("symbol", "").upper() not in skip_syms:
                    add(base.get("address", ""))

        # Source 1: Search queries (broad memecoin coverage)
        queries = ["pump", "pepe", "dog", "cat", "ape", "moon", "elon",
                   "ai", "trump", "maga", "doge", "inu", "frog", "bonk", "wif", "sol"]
        for q in queries:
            data = curl_get(f"https://api.dexscreener.com/latest/dex/search?q={q}", timeout=8)
            add_from_pairs(data.get("pairs", []))
            time.sleep(0.3)

        # Source 2: Token profiles
        time.sleep(0.5)
        for endpoint in ["token-profiles/latest/v1", "token-boosts/latest/v1",
                         "token-boosts/top/v1"]:
            data = curl_get(f"https://api.dexscreener.com/{endpoint}", timeout=8)
            if isinstance(data, list):
                for t in data:
                    if t.get("chainId") == "solana":
                        add(t.get("tokenAddress", ""))
            time.sleep(0.5)

        log.info(f"DexScreener: {len(addrs)} Solana tokens found")
        self._addr_cache["addrs"] = addrs[:200]
        return addrs[:200]

    def _batch_fetch_pairs(self, addresses: List[str]) -> Dict[str, Dict]:
        """Batch fetch: 30 tokens per API call."""
        result = {}
        for i in range(0, len(addresses), 30):
            batch = addresses[i:i+30]
            url = f"https://api.dexscreener.com/tokens/v1/solana/{','.join(batch)}"
            data = curl_get(url, timeout=10)
            if not data:
                time.sleep(0.5); continue

            pairs = data if isinstance(data, list) else data.get("pairs", [])
            by_addr = defaultdict(list)
            for p in pairs:
                if p.get("chainId") == "solana":
                    addr = p.get("baseToken", {}).get("address", "")
                    if addr:
                        by_addr[addr].append(p)

            for addr, addr_pairs in by_addr.items():
                result[addr] = max(addr_pairs,
                    key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0)
            time.sleep(0.3)
        return result

    def scan(self, db: Database) -> List[Signal]:
        addrs = self._discover_tokens()
        if not addrs:
            log.warning("DexScreener returned no addresses")
            return []

        all_pairs = self._batch_fetch_pairs(addrs)
        if _fcount:
            _fcount.reset()
            _fcount.total_in = len(all_pairs)

        signals = []
        for addr, pair in all_pairs.items():
            try:
                sym = pair.get("baseToken", {}).get("symbol", "?").strip()
                price = float(pair.get("priceUsd", 0) or 0)
                if price <= 0 or addr in CFG["blacklist"]:
                    continue

                vol = pair.get("volume", {})
                chg = pair.get("priceChange", {})
                liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                mc = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
                v1h = float(vol.get("h1", 0) or 0)
                v24h = float(vol.get("h24", 0) or 0)
                c1h = float(chg.get("h1", 0) or 0)
                c5m = float(chg.get("m5", 0) or 0)
                buys = pair.get("txns", {}).get("h1", {}).get("buys", 0) or 0
                sells = pair.get("txns", {}).get("h1", {}).get("sells", 0) or 0
                hourly = v1h if v1h > 0 else v24h / 24.0

                # Update tracker if available
                if _tracker:
                    _tracker.snapshot({"address": addr, "symbol": sym, "mc": mc,
                        "volume_h1": v1h, "chg_h1": c1h, "chg_m5": c5m,
                        "liquidity": liq, "buys_h1": buys, "sells_h1": sells,
                        "txns_h1": buys + sells, "price": price})
                    _tracker.update_peak(addr, chg_h1=c1h, mc=mc)

                # ── FILTER CHAIN (fail-closed: must pass ALL) ──
                fail = None
                if hourly < CFG["min_hourly_vol"]:
                    fail = "vol"
                elif c1h <= CFG["min_chg_pct"]:
                    fail = "chg_low"
                elif c1h >= CFG["max_chg_pct"]:
                    fail = "chg_high"
                elif mc <= CFG["min_mc"]:
                    fail = "mc_low"
                elif mc >= CFG["max_mc"]:
                    fail = "mc_high"
                elif liq < CFG["min_liq"]:
                    fail = "liq"
                elif mc > 0 and (hourly / mc) < CFG["min_vmr"]:
                    fail = "vmr_low"
                elif c5m < max(CFG["min_m5_pct"], c1h * 0.15):
                    fail = "velocity_trap"
                elif sym in self._last_chg and c1h < self._last_chg[sym] - 5.0:
                    fail = "chg_fading"

                # Past-peak check
                if not fail and _tracker:
                    snap = _tracker._snapshots.get(addr)
                    if snap and snap.get("peak_chg_h1") is not None:
                        if snap["peak_chg_h1"] > c1h + 10.0:
                            fail = "past_peak"

                # Rug ratio check
                if not fail and mc > 100_000:
                    rug_ratio = liq / mc if mc > 0 else 0
                    if rug_ratio < 0.02:
                        fail = "rug_risk"

                # Pair age check
                if not fail:
                    pair_created = pair.get("pairCreatedAt", 0)
                    if pair_created:
                        age_min = (time.time() * 1000 - pair_created) / 60000
                        if age_min < CFG["min_pair_age_min"]:
                            fail = "too_young"

                # Skip ungraduated pump.fun tokens (Jupiter error 6014)
                if not fail and pair.get("dexId") == "pumpfun":
                    fail = "pumpfun"

                # Cooldown check (unified — one system, one check)
                if not fail and db.is_on_cooldown(addr):
                    fail = "cooldown"

                # Max entries per token per day
                if not fail and db.get_token_entry_count_today(addr) >= CFG["max_entries_per_token"]:
                    fail = "max_entries"

                if fail:
                    if _fcount:
                        _fcount.skip(fail)
                    continue

                # ── PASSED ALL FILTERS ──
                score = min(
                    (hourly / max(mc, 1)) * (1 + c1h / 200) *
                    (1 + c5m / 50) * (1 + buys / 10) * 1_000_000,
                    500_000_000
                )
                self._last_chg[sym] = c1h

                signals.append(Signal(
                    symbol=sym, address=addr, price=price,
                    source=self.SOURCE_ID, score=score,
                    hourly=hourly, chg_pct=c1h, mc=mc, liq=liq,
                ))

                if _fcount:
                    _fcount.passed()
                if _tracker:
                    _tracker.mark_candidate(addr)

                log.info(f"  CANDIDATE: {sym:12s} score={score:.2f} "
                         f"1h_vol=${v1h:,.0f} chg1h={c1h:.1f}% mc=${mc:,.0f} liq=${liq:,.0f}")

            except Exception as e:
                log.warning(f"Pair error {addr[:12]}: {e}")

        signals.sort(key=lambda s: s.score, reverse=True)
        log.info(f"DexScreener candidates: {len(signals)}")
        if _fcount:
            _fcount.log_summary()

        # Dashboard bridge update
        bridge.set_funnel({
            "scanned": len(all_pairs),
            "candidates": len(signals),
        })
        bridge.scan_ended()
        bridge.write_state()
        return signals


class SmartMoneyScanner:
    """Copy trading: mirrors recent buys from known profitable wallets."""

    def __init__(self):
        self._last_chg: Dict[str, float] = {}

    def scan(self, db: Database) -> List[Signal]:
        signals = []
        for wallet in CFG["smart_wallets"]:
            source_id = f"copy_{wallet[:8]}"
            try:
                url = (f"https://api.helius.xyz/v0/addresses/{wallet}/transactions"
                       f"?api-key={CFG.get('helius_key', '')}&limit=5&type=SWAP")
                txs = curl_get(url, headers={"X-API-KEY": CFG["birdeye_key"]})
                if not isinstance(txs, list):
                    txs = []

                for tx in txs:
                    if time.time() - (tx.get("blockTime") or 0) > 120:
                        continue

                    # Find token received by wallet (= buy)
                    token_addr = None
                    for change in (tx.get("tokenTransfers") or []):
                        if change.get("toUserAccount") == wallet:
                            token_addr = change.get("mint", "")
                            if token_addr:
                                break
                    if not token_addr or token_addr in CFG["blacklist"]:
                        continue
                    if db.is_on_cooldown(token_addr):
                        continue

                    pd = curl_get(f"https://api.dexscreener.com/latest/dex/tokens/{token_addr}", timeout=8)
                    pairs = pd.get("pairs", [])
                    if not pairs:
                        continue
                    pair = max(pairs, key=lambda p: p.get("liquidity", {}).get("usd", 0) or 0)
                    price = float(pair.get("priceUsd", 0) or 0)
                    mc = float(pair.get("marketCap", 0) or pair.get("fdv", 0) or 0)
                    liq = float(pair.get("liquidity", {}).get("usd", 0) or 0)
                    sym = pair.get("baseToken", {}).get("symbol", token_addr[:8]).strip()
                    c1h = float(pair.get("priceChange", {}).get("h1", 0) or 0)

                    if price <= 0 or not (CFG["min_mc"] < mc < CFG["max_mc"]):
                        continue
                    if liq < CFG["min_liq"]:
                        continue
                    if c1h < CFG["min_chg_pct"]:
                        continue

                    # Age gate
                    pair_created = pair.get("pairCreatedAt", 0)
                    if pair_created:
                        if (time.time() * 1000 - pair_created) / 60000 < CFG["min_pair_age_min"]:
                            continue

                    log.info(f"COPY SIGNAL: wallet={wallet[:8]} token={sym} "
                             f"liq=${liq:.0f} chg1h={c1h:.1f}%")

                    signals.append(Signal(
                        symbol=sym, address=token_addr, price=price,
                        source=source_id, score=90.0,
                        mc=mc, liq=liq, chg_pct=c1h,
                    ))
                    db.conn.execute(
                        "INSERT INTO wallet_activity VALUES (NULL,?,?,?,?,?)",
                        (datetime.now(timezone.utc).isoformat(), wallet,
                         token_addr, sym, "buy"))
                    db.conn.commit()
            except Exception as e:
                log.warning(f"SmartMoney {wallet[:8]}: {e}")
        return signals


class SignalAggregator:
    """Merges all signals, deduplicates, weights by performance."""

    def __init__(self):
        self.birdeye = BirdeyeScanner()
        self.smart = SmartMoneyScanner()

    def get_signals(self, db: Database, active_addrs: Set[str]) -> List[Signal]:
        weights = db.get_signal_weights()

        # Collect from all sources
        all_signals = self.smart.scan(db) + self.birdeye.scan(db)

        # Deduplicate by ADDRESS (not symbol — multiple tokens can share names)
        seen_addr = set()
        unique = []
        for sig in all_signals:
            if sig.address in seen_addr or sig.address in active_addrs:
                continue
            seen_addr.add(sig.address)
            # Apply self-learning weight
            w = weights.get(sig.source, 0.5)
            sig.score *= (0.5 + w)
            unique.append(sig)

        unique.sort(key=lambda s: s.score, reverse=True)
        return unique


# ══════════════════════════════════════════════════════════════════════════════
# JUPITER EXECUTION
# ══════════════════════════════════════════════════════════════════════════════
class Jupiter:
    async def quote(self, session, inp, out, lamports) -> Optional[Dict]:
        try:
            params = {"inputMint": inp, "outputMint": out,
                      "amount": str(lamports), "slippageBps": "1500"}
            async with session.get("https://public.jupiterapi.com/quote",
                                   params=params,
                                   timeout=aiohttp.ClientTimeout(total=15)) as r:
                if r.status != 200:
                    log.error(f"Jupiter quote HTTP {r.status}"); return None
                data = await r.json()
                if data.get("error") or data.get("errorCode"):
                    log.warning(f"Jupiter quote error: {data.get('error')}"); return None
                if not data.get("outAmount") or int(data.get("outAmount", 0)) == 0:
                    log.warning("Jupiter quote returned 0 output"); return None
                return data
        except Exception as e:
            log.error(f"Jupiter quote: {e}"); return None

    async def swap(self, session, quote) -> Optional[Dict]:
        try:
            payload = {
                "quoteResponse": quote, "userPublicKey": WALLET,
                "wrapAndUnwrapSol": True, "skipUserAccountsRpcCalls": True,
                "dynamicComputeUnitLimit": True,
                "prioritizationFeeLamports": "auto",
                "dynamicSlippage": {"maxBps": 1500},
            }
            async with session.post("https://public.jupiterapi.com/swap",
                                    json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)) as r:
                if r.status != 200:
                    log.error(f"Jupiter swap HTTP {r.status}"); return None
                return await r.json()
        except Exception as e:
            log.error(f"Jupiter swap: {e}"); return None

    async def send(self, session, swap_resp) -> Optional[str]:
        try:
            tx = VersionedTransaction.from_bytes(
                base64.b64decode(swap_resp["swapTransaction"]))
            signed = VersionedTransaction(tx.message, [KP])
            payload = {
                "jsonrpc": "2.0", "id": 1, "method": "sendTransaction",
                "params": [base64.b64encode(bytes(signed)).decode(),
                           {"encoding": "base64", "skipPreflight": True, "maxRetries": 3}]
            }
            async with session.post(CFG["rpc_url"], json=payload,
                                    timeout=aiohttp.ClientTimeout(total=30)) as r:
                d = await r.json()
                if "error" in d:
                    log.error(f"TX error: {d['error']}"); return None
                return d.get("result")
        except Exception as e:
            log.error(f"Jupiter send: {e}"); return None


# ══════════════════════════════════════════════════════════════════════════════
# TRADE EXECUTOR — all buy/monitor/sell logic
# ══════════════════════════════════════════════════════════════════════════════
class TradeExecutor:
    def __init__(self, db: Database):
        self.db = db
        self.jup = Jupiter()

    async def _monitor_position(self, session, sym, addr, entry, sig, start_time):
        """
        Unified monitor loop for both paper and live.
        Returns (exit_price, exit_reason, peak_price, trail_armed).
        """
        exit_p, exit_reason = entry, "timeout"
        peak = entry
        trail_armed = False
        zero_streak = 0
        check_count = 0

        while True:
            await asyncio.sleep(CFG["monitor_interval"])
            check_count += 1
            elapsed = time.time() - start_time

            # Heartbeat every ~2 min
            if check_count % 40 == 0:
                log.info(f"[HEARTBEAT] {sym} | checks={check_count} | "
                         f"elapsed={elapsed:.0f}s | trail={'ON' if trail_armed else 'off'}")

            # Price fetch with 5s timeout
            try:
                cur = await asyncio.wait_for(birdeye_price(session, addr), timeout=5.0)
            except asyncio.TimeoutError:
                log.warning(f"{sym} price timeout — skipping cycle")
                if elapsed > 3600:
                    return entry * 0.95, "stale_timeout", peak, trail_armed
                continue

            if cur <= 0:
                zero_streak += 1
                if zero_streak >= 18 or elapsed > 3600:
                    return entry * 0.95, "stale_timeout", peak, trail_armed
                continue
            zero_streak = 0

            pct = (cur - entry) / entry
            if cur > peak:
                peak = cur

            # Arm trailing stop
            if not trail_armed and cur >= entry * CFG["trail_arm"]:
                trail_armed = True
                log.info(f"  {sym} | TRAIL ARMED @ ${cur:.8f} ({pct*100:+.1f}%)")

            trail_floor = peak * (1 - CFG["trail_pct"]) if trail_armed else 0

            log.info(f"  {sym} | ${cur:.8f} | {pct*100:+.1f}% | "
                     f"peak={peak:.8f} | trail={'ON' if trail_armed else 'off'} | {elapsed:.0f}s")

            # Dashboard update
            bridge.set_positions([{
                "symbol": sym, "address": addr, "entry": entry, "current": cur,
                "pnl_pct": round(pct * 100, 2),
                "peak_pnl_pct": round((peak - entry) / entry * 100, 2) if entry > 0 else 0,
                "trail_armed": trail_armed, "hold_sec": int(elapsed),
                "source": sig.source}])
            bridge.write_state()

            # ── EXIT CHECKS (ordered by priority) ──

            # 1. HARD FLOOR — absolute max loss, ANY time (prevents -34% disasters)
            if cur <= entry * CFG["hard_floor"]:
                log.warning(f"HARD FLOOR HIT {sym}: {pct*100:+.1f}%")
                return cur, "hard_floor", peak, trail_armed

            # 2. EMERGENCY RUG — fast drop in first 30s
            if elapsed < 30 and cur <= entry * 0.88:
                log.warning(f"EMERGENCY RUG {sym}: {((entry-cur)/entry)*100:.1f}% in {elapsed:.0f}s")
                return cur, "emergency_rug", peak, trail_armed

            # 3. TAKE PROFIT
            if cur >= entry * CFG["take_profit"]:
                return cur, "take_profit", peak, trail_armed

            # 4. TRAILING STOP
            if trail_armed and cur <= trail_floor:
                return cur, "trail_stop", peak, trail_armed

            # 5. SNIPER EXIT — cut non-runners at 60s
            if (not trail_armed
                    and elapsed >= CFG["sniper_timeout_sec"]
                    and pct < 0.01):
                log.info(f"  SNIPER EXIT {sym} | {elapsed:.0f}s, pnl={pct*100:+.1f}%")
                return cur, "sniper_timeout", peak, trail_armed

            # 6. STOP LOSS
            if cur <= entry * CFG["stop_loss"]:
                return cur, "stop_loss", peak, trail_armed

            # 7. TIMEOUT
            effective_timeout = (900 if trail_armed
                                 else 600 if pct > 0.01
                                 else CFG["max_hold_sec"])
            if elapsed >= effective_timeout:
                return cur, "timeout", peak, trail_armed

    async def execute(self, session, sig: Signal, sol_balance: float):
        sym, addr, entry = sig.symbol, sig.address, sig.price
        sol_price = get_sol_price()

        if sol_balance < CFG["min_sol_balance"]:
            log.warning(f"Balance too low ({sol_balance:.4f} SOL) — skip {sym}")
            return

        # Sanity check balance
        if sol_balance < 0.1 and _balance_cache["value"] > sol_balance:
            log.warning(f"Low balance read ({sol_balance:.4f}), using cache ({_balance_cache['value']:.4f})")
            sol_balance = _balance_cache["value"]

        sol_amt = sol_balance * CFG["position_pct"]
        lam = int(sol_amt * 1e9)

        # ── FINAL GATE: JIT momentum re-check ──
        try:
            jit = curl_get(f"https://api.dexscreener.com/latest/dex/tokens/{addr}", timeout=8)
            jit_pairs = jit.get("pairs") or []
            if jit_pairs:
                jit_c1h = float(jit_pairs[0].get("priceChange", {}).get("h1", 0) or 0)
                if jit_c1h < CFG["min_chg_pct"]:
                    log.warning(f"[FINAL-GATE] ABORT {sym}: live chg1h={jit_c1h:.1f}% < floor {CFG['min_chg_pct']:.0f}%")
                    return
                log.info(f"[FINAL-GATE] PASS {sym}: live chg1h={jit_c1h:.1f}%")
        except Exception as e:
            log.warning(f"[FINAL-GATE] check failed: {e} — proceeding")

        mode = "PAPER" if PAPER else "LIVE"
        log.info(f"[{mode}] BUY {sym} @ ${entry:.8f} | {sol_amt:.4f} SOL | source={sig.source}")

        # ── PAPER MODE ────────────────────────────────────────────────────
        if PAPER:
            start = time.time()
            exit_p, exit_reason, peak, trail_armed = await self._monitor_position(
                session, sym, addr, entry, sig, start)
            elapsed = time.time() - start

        # ── LIVE MODE ─────────────────────────────────────────────────────
        else:
            # Buy
            quote = await self.jup.quote(session, WSOL, addr, lam)
            if not quote:
                log.warning(f"No Jupiter route for {sym}"); return
            swap = await self.jup.swap(session, quote)
            if not swap:
                log.error(f"Swap build failed for {sym}"); return
            tx_buy = await self.jup.send(session, swap)
            if not tx_buy:
                log.error(f"BUY TX failed for {sym}"); return

            # Save the token amount received for selling later
            tokens_received = int(quote.get("outAmount", 0))
            log.info(f"BUY {sym} | tx={tx_buy[:20]}... | tokens={tokens_received}")

            start = time.time()
            exit_p, exit_reason, peak, trail_armed = await self._monitor_position(
                session, sym, addr, entry, sig, start)
            elapsed = time.time() - start

            # Sell — use TOKEN amount, not SOL amount
            tx_sell = None
            if tokens_received > 0:
                sell_q = await self.jup.quote(session, addr, WSOL, int(tokens_received * 0.98))
                if sell_q:
                    sell_s = await self.jup.swap(session, sell_q)
                    if sell_s:
                        tx_sell = await self.jup.send(session, sell_s)
                        if tx_sell:
                            log.info(f"SELL {sym} | tx={tx_sell[:20]}...")
                        else:
                            log.error(f"SELL TX failed for {sym} — CHECK WALLET")
                else:
                    log.error(f"No sell quote for {sym} — CHECK WALLET")

        # ── RECORD RESULTS ────────────────────────────────────────────────
        pnl_pct = (exit_p - entry) / entry * 100
        peak_pnl_pct = (peak - entry) / entry if entry > 0 else 0
        pnl_usd = sol_amt * sol_price * (pnl_pct / 100)
        won = pnl_usd > 0

        log.info(f"[{mode}] EXIT {sym} | reason={exit_reason} | pnl={pnl_pct:+.1f}% "
                 f"${pnl_usd:+.2f} | peak={peak_pnl_pct*100:.1f}%")

        bridge.record_event("EXIT", {"symbol": sym, "pnl_pct": pnl_pct,
                                     "exit_reason": exit_reason, "peak": peak_pnl_pct})
        bridge.remove_position(sym)
        bridge.write_state()

        if _tracker:
            try:
                _tracker.record_outcome(addr, pnl_pct, elapsed, exit_reason)
            except Exception:
                pass

        self.db.record_trade(
            sym, addr, entry, exit_p, pnl_usd, pnl_pct,
            sol_amt * sol_price, PAPER, sig.source, exit_reason,
            tx_buy=locals().get("tx_buy"), tx_sell=locals().get("tx_sell"),
            score=sig.score, hourly=sig.hourly, chg_pct=sig.chg_pct,
            mc=sig.mc, liq=sig.liq, trailing_tp=trail_armed,
            smart_money=sig.source.startswith("copy_"),
            peak_pnl_pct=peak_pnl_pct)
        self.db.record_signal_result(sig.source, won, pnl_usd)

        # Set cooldown for this token
        self.db.set_cooldown(addr, sym, CFG["cooldown_seconds"])

        # Tax vault skim (Phase 2 — only on profitable trades in dispatcher mode)
        if _tax_vault and pnl_usd > 0 and not PAPER:
            try:
                pnl_sol = pnl_usd / sol_price if sol_price > 0 else 0
                skim = _tax_vault.calculate_skim(
                    # Use the executor wallet that made this trade, or main wallet
                    getattr(self, '_current_executor_address', str(WALLET)),
                    pnl_sol,
                )
                # Actual transfer is handled by dispatcher loop (not here)
                # This just accumulates and logs
            except Exception as e:
                log.warning(f"Tax vault skim error: {e}")

        total = self.db.conn.execute(
            "SELECT COUNT(*), SUM(pnl_usd) FROM trades WHERE paper=?",
            (1 if PAPER else 0,)).fetchone()
        log.info(f"  Total: {total[0]} trades | ${total[1] or 0:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# LEARNING ENGINE (optional)
# ══════════════════════════════════════════════════════════════════════════════
_learn_fn = None
_learn_db = None
try:
    from learning_engine import upgrade_db, analyze_and_tune
    _learn_db = upgrade_db()
    _learn_fn = analyze_and_tune
    log.info("Learning engine loaded")
except Exception as e:
    log.warning(f"Learning engine not available: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# SELF-REGULATION (optional)
# ══════════════════════════════════════════════════════════════════════════════
_SR = False
try:
    import config_reader as CR
    import self_regulation as SR
    CR.init(DB_PATH)
    SR.init(DB_PATH)
    _SR = True
    log.info("Self-regulation loaded")
except Exception:
    CR = SR = None


# ══════════════════════════════════════════════════════════════════════════════
# SCANNER COORDINATOR (Phase 2 — optional)
# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# TAX VAULT (Phase 2 — optional)
# ══════════════════════════════════════════════════════════════════════════════
_tax_vault = None
if CFG["dispatcher_enabled"]:
    try:
        from tax_vault import TaxVault, TaxVaultConfig
        _tv_addr = ""
        _tv_key = ENV.get("TAX_VAULT_KEY", "")
        if _tv_key:
            try:
                _tv_kp = Keypair.from_base58_string(_tv_key)
                _tv_addr = str(_tv_kp.pubkey())
            except Exception as e:
                log.warning(f"Invalid TAX_VAULT_KEY: {e}")
        if _tv_addr:
            _tax_vault = TaxVault(
                TaxVaultConfig(tax_vault_address=_tv_addr),
                db_path=DB_PATH,
            )
            log.info(f"TaxVault loaded: vault={_tv_addr[:12]}...")
        else:
            log.warning("TAX_VAULT_KEY not configured — tax vault disabled")
    except Exception as e:
        log.warning(f"TaxVault not available: {e}")


_coordinator = None
if CFG["dispatcher_enabled"] and CFG["executor_addresses"]:
    try:
        from scanner_coordinator import ScannerCoordinator
        _coordinator = ScannerCoordinator(
            executor_addresses=CFG["executor_addresses"],
            cooldown_seconds=CFG["cooldown_seconds"],
            max_entries_per_token_daily=CFG["max_entries_per_token"],
            max_concurrent_per_token=2,
            wallet_cooldown_seconds=CFG["wallet_cooldown_sec"],
        )
        log.info("ScannerCoordinator loaded — multi-wallet routing active")
    except Exception as e:
        log.error(f"ScannerCoordinator failed to load: {e} — using single-wallet mode")
        CFG["dispatcher_enabled"] = False


# ══════════════════════════════════════════════════════════════════════════════
# MAIN LOOP
# ══════════════════════════════════════════════════════════════════════════════
async def _trade_wrapper(session, executor, sig, bal, active_addrs, db,
                         coordinator=None, executor_address=None):
    """Run a trade and clean up active set on completion."""
    try:
        # Coordinator: ASSIGNED → IN_TRADE
        if coordinator and executor_address:
            coordinator.mark_in_trade(executor_address)
        await executor.execute(session, sig, bal)
    except Exception as e:
        log.error(f"Trade error {sig.symbol}: {e}")
    finally:
        active_addrs.discard(sig.address)
        # Coordinator: IN_TRADE → COOLDOWN (or cancel if never started)
        if coordinator and executor_address:
            ex = coordinator.executors.get(executor_address)
            if ex and ex.state.value == "IN_TRADE":
                coordinator.mark_trade_complete(executor_address)
            elif ex and ex.state.value == "ASSIGNED":
                coordinator.cancel_assignment(executor_address)


async def main():
    log.info("=" * 60)
    log.info("  Lazarus v3.0 — Target: $20,000")
    log.info(f"  Wallet : {WALLET}")
    log.info(f"  Mode   : {'PAPER' if PAPER else 'LIVE'}")
    log.info(f"  Filters: chg {CFG['min_chg_pct']}-{CFG['max_chg_pct']}% | "
             f"liq >${CFG['min_liq']:,.0f} | SL {(1-CFG['stop_loss'])*100:.0f}% | "
             f"hard floor {(1-CFG['hard_floor'])*100:.0f}%")
    log.info("=" * 60)

    bridge.update_stat("mode", "PAPER" if PAPER else "LIVE")
    bridge.set_config(CFG)
    bridge.write_state(force=True)

    # ── Layer 4: Startup assertions — catch config drift before any trades ──
    if _DI:
        try:
            _startup_db = sqlite3.connect(DB_PATH, timeout=5)
            _bc_rows = _startup_db.execute("SELECT key, value FROM bot_config").fetchall()
            _dc_rows = _startup_db.execute("SELECT key, value FROM dynamic_config").fetchall()
            _startup_db.close()
            _bot_cfg = {k: v for k, v in _bc_rows}
            _dyn_cfg = {k: v for k, v in _dc_rows}
            startup_check = validate_startup_config(_bot_cfg, _dyn_cfg, epoch=V31_EPOCH)
            if not startup_check["valid"]:
                log.critical(f"[STARTUP] ASSERTION FAILED: {startup_check['reason']}")
                for fail in startup_check["details"]["checks_failed"]:
                    log.critical(f"[STARTUP]   FAIL: {fail}")
                log.critical("[STARTUP] Lazarus will NOT start until this is resolved.")
                import sys
                sys.exit(1)
            log.info(f"[STARTUP] All assertions passed ({len(startup_check['details']['checks_passed'])} checks)")
            for p in startup_check["details"]["checks_passed"]:
                log.info(f"[STARTUP]   OK: {p}")
        except SystemExit:
            raise
        except Exception as e:
            log.warning(f"[STARTUP] Assertion check error (non-fatal): {e}")
    else:
        log.warning("[STARTUP] data_integrity not available — skipping startup assertions")

    db = Database()
    executor = TradeExecutor(db)
    aggregator = SignalAggregator()
    active_addrs: Set[str] = set()  # track by ADDRESS not symbol
    cycle = 0

    if _SR:
        try:
            asyncio.create_task(SR.heartbeat_loop(60))
        except Exception:
            pass

    async with aiohttp.ClientSession() as session:
        bal = await rpc_get_balance(session)
        log.info(f"Starting balance: {bal:.4f} SOL (~${bal * get_sol_price():.2f})")

        while True:
            cycle += 1
            bridge.scan_started(cycle)

            try:
                bal = await rpc_get_balance(session)
                sol_price = get_sol_price()
                log.info(f"[Cycle {cycle}] {bal:.4f} SOL (${bal * sol_price:.2f}) | "
                         f"open={len(active_addrs)}/{CFG['max_positions']}")

                # ── SAFETY CHECKS ──
                # 1. Daily loss limit
                daily_pnl = db.get_daily_pnl()
                portfolio_usd = CFG["paper_capital_usd"] if PAPER else bal * sol_price
                if portfolio_usd > 0 and abs(daily_pnl) / portfolio_usd * 100 > CFG["daily_loss_limit_pct"]:
                    log.warning(f"DAILY LOSS LIMIT: ${daily_pnl:.2f} "
                                f"({abs(daily_pnl)/portfolio_usd*100:.1f}%) — pausing")
                    bridge.scan_ended()
                    await asyncio.sleep(CFG["scan_interval"])
                    continue

                # 2. BTC/ETH market safety
                market_safe, market_reason = check_market_safety()
                if not market_safe:
                    log.warning(f"MARKET UNSAFE: {market_reason} — pausing")
                    bridge.scan_ended()
                    await asyncio.sleep(CFG["scan_interval"])
                    continue

                # 3. Self-regulation check
                if _SR:
                    try:
                        if CR.is_scan_paused():
                            log.info("SCAN PAUSED by self-regulation")
                            bridge.scan_ended()
                            await asyncio.sleep(CFG["scan_interval"])
                            continue
                    except Exception:
                        pass

                # Clean expired cooldowns periodically
                if cycle % 20 == 0:
                    db.clean_expired_cooldowns()
                    if _tracker:
                        _tracker.flush_snapshots()

                # ── SCAN + TRADE ──
                if CFG["dispatcher_enabled"] and _coordinator:
                    # Multi-wallet mode: coordinator routes to available executors
                    idle_slots = _coordinator.get_idle_count()
                    if idle_slots > 0:
                        signals = aggregator.get_signals(db, active_addrs)
                        for sig in signals[:idle_slots]:
                            if sig.address not in active_addrs:
                                routed = _coordinator.route(sig)
                                if routed:
                                    active_addrs.add(sig.address)
                                    log.info(
                                        f"Opening: {sig.symbol} | score={sig.score:.2f} | "
                                        f"source={sig.source} | executor={routed.executor_address[:8]}..."
                                    )
                                    asyncio.create_task(
                                        _trade_wrapper(
                                            session, executor, sig, bal, active_addrs, db,
                                            coordinator=_coordinator,
                                            executor_address=routed.executor_address,
                                        )
                                    )
                else:
                    # Single-wallet mode: original behavior, no coordinator
                    if len(active_addrs) < CFG["max_positions"]:
                        signals = aggregator.get_signals(db, active_addrs)
                        slots = CFG["max_positions"] - len(active_addrs)
                        for sig in signals[:slots]:
                            if sig.address not in active_addrs:
                                active_addrs.add(sig.address)
                                log.info(f"Opening: {sig.symbol} | score={sig.score:.2f} | "
                                         f"source={sig.source}")
                                asyncio.create_task(
                                    _trade_wrapper(session, executor, sig, bal, active_addrs, db))

                bridge.scan_ended()

            except Exception as e:
                log.error(f"Main loop error: {e}")

            # Learning engine every 10 cycles
            if cycle % 10 == 0 and _learn_fn and _learn_db:
                try:
                    _learn_fn(_learn_db)
                    dc = _learn_db.execute("SELECT key, value FROM dynamic_config").fetchall()
                    for k, v in dc:
                        if k in CFG:
                            try:
                                val = float(v)
                                # Apply with safety floors
                                if k == "stop_loss":
                                    CFG[k] = max(0.90, min(0.97, val))   # 3-10% SL range
                                elif k == "position_pct":
                                    CFG[k] = max(0.10, min(0.30, val))   # 10-30% size range
                                elif k == "max_positions":
                                    CFG[k] = min(2, max(1, int(val)))    # 1-2 positions
                                elif k == "trail_arm":
                                    CFG[k] = max(1.05, min(1.15, val))   # 5-15% trail arm
                                else:
                                    CFG[k] = val
                                log.info(f"Dynamic config: {k}={CFG[k]}")
                            except ValueError:
                                pass
                except Exception as e:
                    log.warning(f"Learning cycle error: {e}")

            # ── Layer 5: Anomaly detection every 20 cycles ──
            if cycle % 20 == 0 and _DI:
                try:
                    _anom_db = sqlite3.connect(DB_PATH, timeout=5)
                    _recent = _anom_db.execute(
                        "SELECT symbol, token_address, pnl_pct, pnl_usd, source, "
                        "timestamp, exit_reason, chg_pct, liq "
                        "FROM trades WHERE timestamp >= ? AND side='sell' "
                        "ORDER BY timestamp DESC LIMIT 30",
                        (V31_EPOCH,)
                    ).fetchall()
                    _anom_db.close()
                    if _recent:
                        _recent_dicts = [
                            {"symbol": r[0], "token_address": r[1], "pnl_pct": r[2],
                             "pnl_usd": r[3], "source": r[4], "timestamp": r[5],
                             "exit_reason": r[6], "chg_pct": r[7], "liq": r[8]}
                            for r in _recent
                        ]
                        anomaly_check = check_data_anomalies(_recent_dicts, CFG)
                        if anomaly_check["anomalies"]:
                            for anomaly in anomaly_check["anomalies"]:
                                log.warning(f"[ANOMALY] {anomaly['type']}: {anomaly['message']} "
                                            f"(severity: {anomaly['severity']})")
                            if anomaly_check["severity"] == "critical":
                                log.critical(f"[ANOMALY] CRITICAL — {anomaly_check['recommendation']}")
                except Exception as e:
                    log.warning(f"[ANOMALY] Check error: {e}")

            bridge.heartbeat(balance_usd=bal * get_sol_price(), balance_sol=bal)
            bridge.write_state()
            await asyncio.sleep(CFG["scan_interval"])


if __name__ == "__main__":
    asyncio.run(main())
