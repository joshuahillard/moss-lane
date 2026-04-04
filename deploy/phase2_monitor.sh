#!/bin/bash
# ============================================================
# LAZARUS PHASE 2 — MONITORING DASHBOARD
# Run anytime: bash /tmp/phase2_monitor.sh
# Or paste individual sections into SSH
# ============================================================

DB="/home/solbot/lazarus/logs/lazarus.db"

echo "============================================================"
echo "  LAZARUS v3.1 — PHASE 2 MONITORING"
echo "  $(date -u '+%Y-%m-%d %H:%M UTC')"
echo "============================================================"
echo ""

# 1. Service health
echo "=== SERVICE STATUS ==="
systemctl is-active lazarus && echo "  Lazarus: RUNNING" || echo "  Lazarus: DOWN!"
echo ""

# 2. Trade count + basic stats (v3+ only)
echo "=== TRADE SUMMARY (v3+ trades since 2026-03-28) ==="
sqlite3 -header -column "$DB" "
SELECT
    COUNT(*) as total,
    SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) as wins,
    SUM(CASE WHEN pnl_pct <= 0 THEN 1 ELSE 0 END) as losses,
    CASE WHEN COUNT(*) > 0
        THEN ROUND(100.0 * SUM(CASE WHEN pnl_pct > 0 THEN 1 ELSE 0 END) / COUNT(*), 1)
        ELSE 0 END as win_pct,
    ROUND(SUM(pnl_usd), 2) as total_pnl_usd,
    ROUND(AVG(pnl_pct), 2) as avg_pnl_pct,
    ROUND(AVG(latency_ms), 0) as avg_latency
FROM trades WHERE timestamp >= '2026-03-28 05:00';
"
echo ""

# 3. Profit Factor
echo "=== PROFIT FACTOR ==="
sqlite3 -header -column "$DB" "
SELECT
    ROUND(SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END), 2) as gross_wins,
    ROUND(ABS(SUM(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE 0 END)), 2) as gross_losses,
    CASE WHEN ABS(SUM(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE 0 END)) > 0
        THEN ROUND(SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) /
             ABS(SUM(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE 0 END)), 2)
        ELSE 0 END as profit_factor
FROM trades WHERE timestamp >= '2026-03-28 05:00';
"
echo ""

# 4. PnL Leakage (Peak vs Final) — THE KEY METRIC
echo "=== PNL LEAKAGE (Peak vs Final — last 12h) ==="
sqlite3 -header -column "$DB" "
SELECT
    id,
    symbol,
    ROUND(pnl_pct, 2) as final_pnl_pct,
    ROUND(peak_pnl_pct * 100, 2) as peak_pnl_pct,
    ROUND(peak_pnl_pct * 100 - pnl_pct, 2) as leakage_pct,
    exit_reason,
    CASE WHEN trailing_tp = 1 THEN 'YES' ELSE 'no' END as trail_armed
FROM trades
WHERE timestamp >= datetime('now', '-12 hours')
  AND timestamp >= '2026-03-28 05:00'
ORDER BY timestamp DESC;
"
echo ""

# 5. Average leakage
echo "=== AVERAGE LEAKAGE ==="
sqlite3 -header -column "$DB" "
SELECT
    COUNT(*) as trades,
    ROUND(AVG(peak_pnl_pct * 100), 2) as avg_peak_pct,
    ROUND(AVG(pnl_pct), 2) as avg_final_pct,
    ROUND(AVG(peak_pnl_pct * 100 - pnl_pct), 2) as avg_leakage_pct
FROM trades
WHERE timestamp >= '2026-03-28 05:00'
  AND peak_pnl_pct IS NOT NULL;
"
echo ""

# 6. Exit reason breakdown
echo "=== EXIT REASONS ==="
sqlite3 -header -column "$DB" "
SELECT
    exit_reason,
    COUNT(*) as count,
    ROUND(AVG(pnl_pct), 2) as avg_pnl,
    ROUND(SUM(pnl_usd), 2) as total_usd
FROM trades
WHERE timestamp >= '2026-03-28 05:00'
GROUP BY exit_reason
ORDER BY count DESC;
"
echo ""

# 7. Stoic Learner status
echo "=== STOIC LEARNER STATUS ==="
TRADE_COUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM trades WHERE timestamp >= '2026-03-28 05:00';")
echo "  v3+ trades: $TRADE_COUNT / 20 minimum for learning"
if [ "$TRADE_COUNT" -ge 20 ]; then
    echo "  STATUS: Learning engine ACTIVE (config writes enabled)"
else
    echo "  STATUS: Stoic gate HOLDING (blacklist only, no config writes)"
fi
echo ""

# 8. Dynamic config (should be empty until 20 trades)
echo "=== DYNAMIC_CONFIG ==="
sqlite3 -header -column "$DB" "SELECT key, value, reason FROM dynamic_config ORDER BY key;"
DCOUNT=$(sqlite3 "$DB" "SELECT COUNT(*) FROM dynamic_config;")
if [ "$DCOUNT" -eq 0 ]; then
    echo "  (empty — Stoic gate holding)"
fi
echo ""

# 9. Current bot_config (runtime values)
echo "=== BOT_CONFIG (key values) ==="
sqlite3 -header -column "$DB" "
SELECT key, value FROM bot_config
WHERE key IN ('position_pct','stop_loss','regime_mode','scan_pause_until',
              'min_chg_pct','max_chg_pct','min_liq','min_hourly_vol')
ORDER BY key;
"
echo ""

# 10. Last 15 log lines
echo "=== RECENT LOGS ==="
journalctl -u lazarus --no-pager -n 15
echo ""

echo "============================================================"
echo "  Go-Live Criteria:"
echo "    Win Rate > 40%    |  Current: check above"
echo "    Profit Factor > 2 |  Current: check above"
echo "    Trades >= 20      |  Current: $TRADE_COUNT"
echo "============================================================"
