.headers on
.mode column

-- Wide-Net v2 Query Pack (Post-Migration / v3.2)
-- Usage on server:
--   sqlite3 /home/solbot/lazarus/logs/lazarus.db < /path/to/WIDE_NET_V2_QUERY_PACK_V32.sql
--
-- Requires trades.filter_regime to exist and assumes runtime tagging is live.
-- Use WIDE_NET_V2_QUERY_PACK.sql or WIDE_NET_V2_QUERY_PACK_LEGACY.sql
-- before the v3.2 schema migration lands.
--
-- All queries are post-epoch, paper-mode only.

SELECT '=== MODE CHECK ===' AS section;
SELECT key, value
FROM bot_config
WHERE key IN ('min_hourly_vol','min_chg_pct','max_chg_pct','min_liq','min_vmr')
ORDER BY key;

SELECT '=== REGIME SUMMARY ===' AS section;
WITH sells AS (
  SELECT
    COALESCE(NULLIF(filter_regime, ''), 'unlabeled') AS regime,
    pnl_usd,
    pnl_pct
  FROM trades
  WHERE side='sell'
    AND paper=1
    AND timestamp >= '2026-03-29T17:44:00'
)
SELECT
  regime,
  COUNT(*) AS trades,
  ROUND(100.0 * AVG(CASE WHEN pnl_pct > 0 THEN 1.0 ELSE 0 END), 1) AS win_pct,
  ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
  ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
FROM sells
GROUP BY regime
ORDER BY total_pnl_usd DESC;

SELECT '=== BUCKET SUMMARY ===' AS section;
WITH sells AS (
  SELECT
    COALESCE(NULLIF(filter_regime, ''), 'unlabeled') AS regime,
    hourly,
    chg_pct,
    liq,
    pnl_usd,
    pnl_pct
  FROM trades
  WHERE side='sell'
    AND paper=1
    AND timestamp >= '2026-03-29T17:44:00'
)
SELECT metric, regime, bucket, trades, win_pct, avg_pnl_pct, total_pnl_usd
FROM (
  SELECT
    'chg_pct' AS metric,
    regime,
    CASE
      WHEN chg_pct < 10 THEN '<10'
      WHEN chg_pct < 30 THEN '10-30'
      WHEN chg_pct < 80 THEN '30-80'
      WHEN chg_pct < 100 THEN '80-100'
      WHEN chg_pct < 120 THEN '100-120'
      ELSE '120+'
    END AS bucket,
    COUNT(*) AS trades,
    ROUND(100.0 * AVG(CASE WHEN pnl_pct > 0 THEN 1.0 ELSE 0 END), 1) AS win_pct,
    ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
    ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
  FROM sells
  GROUP BY regime, bucket

  UNION ALL

  SELECT
    'liq' AS metric,
    regime,
    CASE
      WHEN liq < 30000 THEN '<30k'
      WHEN liq < 50000 THEN '30k-50k'
      WHEN liq < 100000 THEN '50k-100k'
      ELSE '100k+'
    END AS bucket,
    COUNT(*) AS trades,
    ROUND(100.0 * AVG(CASE WHEN pnl_pct > 0 THEN 1.0 ELSE 0 END), 1) AS win_pct,
    ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
    ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
  FROM sells
  GROUP BY regime, bucket

  UNION ALL

  SELECT
    'hourly_vol' AS metric,
    regime,
    CASE
      WHEN hourly < 400 THEN '<400'
      WHEN hourly < 800 THEN '400-800'
      WHEN hourly < 2000 THEN '800-2k'
      ELSE '2k+'
    END AS bucket,
    COUNT(*) AS trades,
    ROUND(100.0 * AVG(CASE WHEN pnl_pct > 0 THEN 1.0 ELSE 0 END), 1) AS win_pct,
    ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
    ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
  FROM sells
  GROUP BY regime, bucket
)
ORDER BY metric, regime, bucket;

SELECT '=== INFERRED V2 COHORT SUMMARY ===' AS section;
WITH sells AS (
  SELECT
    CASE
      WHEN chg_pct >= 10 AND chg_pct < 80 AND liq >= 50000 THEN 'original_window'
      WHEN chg_pct >= 10 AND chg_pct < 100 AND liq >= 30000 THEN 'wide_net_v2_expansion'
      ELSE 'outside_v2'
    END AS v2_cohort,
    pnl_usd,
    pnl_pct
  FROM trades
  WHERE side='sell'
    AND paper=1
    AND timestamp >= '2026-03-29T17:44:00'
)
SELECT
  v2_cohort,
  COUNT(*) AS trades,
  ROUND(100.0 * AVG(CASE WHEN pnl_pct > 0 THEN 1.0 ELSE 0 END), 1) AS win_pct,
  ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
  ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
FROM sells
GROUP BY v2_cohort
ORDER BY total_pnl_usd DESC;

SELECT '=== SNIPER TIMEOUT BY COHORT OVER TIME ===' AS section;
WITH sells AS (
  SELECT
    substr(timestamp, 1, 10) AS trade_day,
    CASE
      WHEN chg_pct >= 10 AND chg_pct < 80 AND liq >= 50000 THEN 'original_window'
      WHEN chg_pct >= 10 AND chg_pct < 100 AND liq >= 30000 THEN 'wide_net_v2_expansion'
      ELSE 'outside_v2'
    END AS v2_cohort,
    COALESCE(NULLIF(filter_regime, ''), 'unlabeled') AS regime,
    CASE
      WHEN chg_pct < 10 THEN '<10'
      WHEN chg_pct < 30 THEN '10-30'
      WHEN chg_pct < 80 THEN '30-80'
      WHEN chg_pct < 100 THEN '80-100'
      WHEN chg_pct < 120 THEN '100-120'
      ELSE '120+'
    END AS chg_bucket,
    exit_reason,
    pnl_usd,
    pnl_pct
  FROM trades
  WHERE side='sell'
    AND paper=1
    AND timestamp >= '2026-03-29T17:44:00'
)
SELECT
  trade_day,
  v2_cohort,
  regime,
  chg_bucket,
  COUNT(*) AS sniper_trades,
  ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
  ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
FROM sells
WHERE exit_reason='sniper_timeout'
GROUP BY trade_day, v2_cohort, regime, chg_bucket
ORDER BY trade_day DESC, v2_cohort, regime, chg_bucket;

SELECT '=== EXIT REASON MIX BY COHORT ===' AS section;
WITH sells AS (
  SELECT
    COALESCE(NULLIF(filter_regime, ''), 'unlabeled') AS regime,
    CASE
      WHEN chg_pct < 10 THEN '<10'
      WHEN chg_pct < 30 THEN '10-30'
      WHEN chg_pct < 80 THEN '30-80'
      WHEN chg_pct < 100 THEN '80-100'
      WHEN chg_pct < 120 THEN '100-120'
      ELSE '120+'
    END AS chg_bucket,
    exit_reason,
    pnl_usd,
    pnl_pct
  FROM trades
  WHERE side='sell'
    AND paper=1
    AND timestamp >= '2026-03-29T17:44:00'
)
SELECT
  regime,
  chg_bucket,
  exit_reason,
  COUNT(*) AS trades,
  ROUND(AVG(pnl_pct), 2) AS avg_pnl_pct,
  ROUND(SUM(pnl_usd), 2) AS total_pnl_usd
FROM sells
GROUP BY regime, chg_bucket, exit_reason
ORDER BY regime, chg_bucket, trades DESC, total_pnl_usd DESC;
