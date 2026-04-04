#!/usr/bin/env python3
"""
Lazarus Foundation Test — verifies the container is healthy.

WHAT THIS TESTS:
  1. curl binary exists and works (curl_get depends on it)
  2. Python dependencies import correctly (aiohttp, solders, base58)
  3. Secrets are present in the environment (.env loaded or env vars set)
  4. Database tables are created correctly (all 7 core tables)
  5. DexScreener API is reachable from inside the container
  6. RPC endpoint responds (Solana cluster is reachable)

HOW TO RUN:
  Local Docker:  docker exec lazarus-bot python test_foundation.py
  Cloud Run:     Build into the image, then check logs for results

EXIT CODES:
  0 = all tests passed
  1 = one or more tests failed
"""

import subprocess
import json
import sqlite3
import os
import sys
import importlib

# ── Test tracking ────────────────────────────────────────────────────────────
_passed = 0
_failed = 0

def test(name: str, condition: bool, detail: str = ""):
    """Record a test result."""
    global _passed, _failed
    if condition:
        _passed += 1
        print(f"  PASS  {name}")
    else:
        _failed += 1
        msg = f"  FAIL  {name}"
        if detail:
            msg += f" -- {detail}"
        print(msg)


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: curl binary
# ══════════════════════════════════════════════════════════════════════════════
print("\n[1/6] curl binary")
try:
    result = subprocess.run(["curl", "--version"], capture_output=True, timeout=5)
    test("curl is installed", result.returncode == 0)
except FileNotFoundError:
    test("curl is installed", False, "curl not found in PATH")
except Exception as e:
    test("curl is installed", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Python dependencies
# ══════════════════════════════════════════════════════════════════════════════
print("\n[2/6] Python dependencies")
for mod in ["aiohttp", "solders", "base58"]:
    try:
        importlib.import_module(mod)
        test(f"import {mod}", True)
    except ImportError as e:
        test(f"import {mod}", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Secrets / environment
# ══════════════════════════════════════════════════════════════════════════════
print("\n[3/6] Secrets")

# Check the .env file path (where EnvLoader reads from)
env_path = "/home/solbot/lazarus/.env"
env_exists = os.path.exists(env_path)
test(".env file exists", env_exists, f"looked at {env_path}")

if env_exists:
    content = open(env_path).read()
    test("SOLANA_PRIVATE_KEY in .env", "SOLANA_PRIVATE_KEY" in content)
    test("SOLANA_RPC_URL in .env", "SOLANA_RPC_URL" in content)
    test("BIRDEYE_API_KEY in .env", "BIRDEYE_API_KEY" in content)
else:
    # Fall back to checking environment variables (Cloud Run injects these)
    test("SOLANA_PRIVATE_KEY env var", bool(os.environ.get("SOLANA_PRIVATE_KEY")))
    test("SOLANA_RPC_URL env var", bool(os.environ.get("SOLANA_RPC_URL")))
    test("BIRDEYE_API_KEY env var", bool(os.environ.get("BIRDEYE_API_KEY")))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Database tables
# ══════════════════════════════════════════════════════════════════════════════
print("\n[4/6] Database tables")

db_path = "/home/solbot/lazarus/logs/test_foundation.db"
os.makedirs(os.path.dirname(db_path), exist_ok=True)

EXPECTED_TABLES = [
    "trades",
    "signal_performance",
    "wallet_activity",
    "cooldowns",
    "daily_pnl",
    "balance_snapshots",
    "btc_eth_pillars",
]

try:
    conn = sqlite3.connect(db_path)
    # Run the same CREATE TABLE statements as Database._init_tables()
    conn.executescript("""
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
    conn.commit()

    # Verify all tables exist
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    actual_tables = {row[0] for row in cursor.fetchall()}

    for table in EXPECTED_TABLES:
        test(f"table: {table}", table in actual_tables)

    conn.close()
    # Clean up test DB
    os.remove(db_path)

except Exception as e:
    test("database creation", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: DexScreener API reachable (curl_get pattern)
# ══════════════════════════════════════════════════════════════════════════════
print("\n[5/6] curl_get — DexScreener API")

try:
    out = subprocess.check_output(
        ["curl", "-s", "--max-time", "10",
         "https://api.dexscreener.com/latest/dex/search?q=SOL"],
        timeout=15,
        stderr=subprocess.DEVNULL,
    )
    data = json.loads(out)
    has_pairs = "pairs" in data and len(data["pairs"]) > 0
    test("DexScreener responds", True)
    test("DexScreener returns pairs", has_pairs,
         f"got {len(data.get('pairs', []))} pairs" if has_pairs else "no pairs in response")
except subprocess.TimeoutExpired:
    test("DexScreener responds", False, "curl timed out after 10s")
except json.JSONDecodeError:
    test("DexScreener responds", True)
    test("DexScreener returns pairs", False, "response was not valid JSON")
except Exception as e:
    test("DexScreener responds", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: RPC endpoint
# ══════════════════════════════════════════════════════════════════════════════
print("\n[6/6] Solana RPC")

# Try to read RPC URL from .env, fall back to env var, then default
rpc_url = "https://api.mainnet-beta.solana.com"
if env_exists:
    for line in open(env_path).read().splitlines():
        if line.startswith("SOLANA_RPC_URL="):
            rpc_url = line.split("=", 1)[1].strip().strip("'\"")
            break
elif os.environ.get("SOLANA_RPC_URL"):
    rpc_url = os.environ["SOLANA_RPC_URL"]

try:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "getHealth"})
    out = subprocess.check_output(
        ["curl", "-s", "--max-time", "10",
         "-X", "POST", "-H", "Content-Type: application/json",
         "-d", payload, rpc_url],
        timeout=15,
        stderr=subprocess.DEVNULL,
    )
    data = json.loads(out)
    healthy = data.get("result") == "ok"
    test("RPC responds", True)
    test("RPC cluster healthy", healthy,
         f"got: {data.get('result', data.get('error', 'unknown'))}")
except subprocess.TimeoutExpired:
    test("RPC responds", False, "curl timed out after 10s")
except Exception as e:
    test("RPC responds", False, str(e))


# ══════════════════════════════════════════════════════════════════════════════
# SUMMARY
# ══════════════════════════════════════════════════════════════════════════════
total = _passed + _failed
print(f"\n{'='*60}")
print(f"  RESULTS: {_passed}/{total} passed, {_failed} failed")
print(f"{'='*60}\n")

sys.exit(0 if _failed == 0 else 1)
