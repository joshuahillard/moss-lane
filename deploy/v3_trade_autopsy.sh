#!/bin/bash
# ============================================================
# Lazarus v3 Trade Autopsy — Full Diagnostic
# Run on server via SSH: bash /tmp/v3_trade_autopsy.sh
# ============================================================

DB="/home/solbot/lazarus/logs/lazarus.db"

echo "============================================================"
echo "  LAZARUS v3 TRADE AUTOPSY"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "============================================================"
echo ""

# 1. All v3 trades (paper=1, after v3 deploy ~2026-03-28 05:00 UTC)
echo "=== ALL V3 TRADES (since 2026-03-28 05:00 UTC) ==="
echo ""
sqlite3 -header -column "$DB" "
SELECT
    id,
    timestamp,
    symbol,
    side,
    entry_price_sol,
    exit_price_sol,
    size_usd,
    pnl_pct,
    pnl_usd,
    exit_reason,
    latency_ms,
    paper
FROM trades
WHERE timestamp >= '2026-03-28 05:00'
ORDER BY timestamp ASC;
"
echo ""

# 2. Filter values at scan time — what did the bot see when it decided to buy?
echo "=== FILTER VALUES AT ENTRY (what the bot saw) ==="
echo ""
sqlite3 -header -column "$DB" "
SELECT
    id,
    symbol,
    token_address,
    chg_pct AS hourly_chg,
    liq AS liquidity,
    mc AS market_cap,
    score,
    source,
    hourly
FROM trades
WHERE timestamp >= '2026-03-28 05:00'
ORDER BY timestamp ASC;
"
echo ""

# 3. Stale timeout deep dive — these are the problem trades
echo "=== STALE_TIMEOUT TRADES — DEEP DIVE ==="
echo ""
sqlite3 -header -column "$DB" "
SELECT
    id,
    symbol,
    timestamp,
    entry_price_sol,
    exit_price_sol,
    pnl_pct,
    peak_pnl_pct,
    latency_ms,
    chg_pct AS hourly_chg_at_entry,
    liq,
    mc
FROM trades
WHERE timestamp >= '2026-03-28 05:00'
  AND exit_reason = 'stale_timeout'
ORDER BY timestamp ASC;
"
echo ""

# 4. Check if side column is truly empty or null
echo "=== SIDE COLUMN CHECK ==="
sqlite3 -header -column "$DB" "
SELECT
    id,
    symbol,
    side,
    typeof(side) as side_type,
    length(side) as side_length
FROM trades
WHERE timestamp >= '2026-03-28 05:00'
LIMIT 10;
"
echo ""

# 5. Total v3 stats
echo "=== V3 SUMMARY STATS ==="
sqlite3 -header -column "$DB" "
SELECT
    COUNT(*) as total_trades,
    SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as winners,
    SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) as losers,
    ROUND(AVG(pnl_pct), 2) as avg_pnl_pct,
    ROUND(MIN(pnl_pct), 2) as worst_pnl_pct,
    ROUND(MAX(pnl_pct), 2) as best_pnl_pct,
    ROUND(SUM(pnl_usd), 4) as total_pnl_usd,
    ROUND(AVG(latency_ms), 0) as avg_latency_ms
FROM trades
WHERE timestamp >= '2026-03-28 05:00';
"
echo ""

# 6. Current balance
echo "=== CURRENT BALANCE ==="
sqlite3 -header -column "$DB" "
SELECT * FROM balance_snapshots ORDER BY ts DESC LIMIT 1;"
echo ""

# 7. Check bot_config for current filter settings (runtime source of truth)
echo "=== CURRENT BOT_CONFIG (runtime filters) ==="
sqlite3 -header -column "$DB" "
SELECT key, value FROM bot_config ORDER BY key;"
echo ""

# 8. Check dynamic_config (learning engine overrides)
echo "=== DYNAMIC_CONFIG (learning engine state) ==="
sqlite3 -header -column "$DB" "SELECT key, value FROM dynamic_config ORDER BY key;"
echo ""

# 9. Last 20 log lines for context
echo "=== LAST 20 LOG LINES ==="
journalctl -u lazarus --no-pager -n 20
echo ""

echo "============================================================"
echo "  AUTOPSY COMPLETE — Copy all output and paste to Claude"
echo "============================================================"
