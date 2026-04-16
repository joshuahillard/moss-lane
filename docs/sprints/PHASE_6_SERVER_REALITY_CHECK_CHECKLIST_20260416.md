# Phase 6 Server Reality Check Checklist

Date: 2026-04-16
Branch baseline: `codex/stabilize-20260416` @ `649a677`
Mode: read-only diagnostics only

## Purpose

Resolve the Stoic Gate contradiction from production evidence, not memory:

- Tracker on disk: `7/20`, `PF 1.42`
- Memory claim: `25 trades`, `PF 1.73`

Phase 6 answers one question first:

`How many post-epoch paper sells exist in the production trades table, and what is their profit factor?`

Do not broaden scope until that number is on paper.

## Hard Rules

- No writes to production during Phase 6.
- No schema changes.
- No config changes.
- No `INSERT`, `UPDATE`, `DELETE`, or migration commands.
- Do not assume `filter_regime` exists.
- Do not assume the sell-side marker column is `side`; probe the schema first.
- Use epoch text comparison only:
  - `timestamp >= '2026-03-29T17:44:00'`
- If a backup is taken for query safety, query the backup copy, not the live DB.

## Step 0 — Dashboard Pre-Check

Optional but useful.

- Open the dashboard on port `8443`.
- Record the displayed trade count and PF.
- Treat this as a sanity check only, not the source of truth.

## Step 1 — SSH and Identify Runtime State

```bash
ssh <vps-host>
cd <repo-path>
git fetch origin
git checkout codex/stabilize-20260416
git pull --ff-only origin codex/stabilize-20260416
ps aux | grep lazarus
```

Record:

- repo path
- whether the bot is running
- current branch / commit if helpful

## Step 2 — Choose Query Safety Mode

If the bot is running and you want zero lock risk:

```bash
cp /home/solbot/lazarus/logs/lazarus.db /home/solbot/lazarus/logs/lazarus_phase6_readonly.db
DB_PATH=/home/solbot/lazarus/logs/lazarus_phase6_readonly.db
```

Otherwise:

```bash
DB_PATH=/home/solbot/lazarus/logs/lazarus.db
```

Recommended default: query the copied DB file.

## Step 3 — Schema Probe

Run these first:

```bash
sqlite3 "$DB_PATH" "PRAGMA table_info(trades);"
sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM trades;"
```

Record:

- whether `filter_regime` exists
- whether `side` exists
- total row count

## Step 4 — Minimal Epoch-Gated Truth Queries

### 4A. If `side` exists on `trades`

```bash
sqlite3 "$DB_PATH" "
SELECT COUNT(*)
FROM trades
WHERE timestamp >= '2026-03-29T17:44:00'
  AND paper = 1
  AND lower(side) = 'sell';
"
```

```bash
sqlite3 "$DB_PATH" "
WITH sells AS (
  SELECT pnl_usd
  FROM trades
  WHERE timestamp >= '2026-03-29T17:44:00'
    AND paper = 1
    AND lower(side) = 'sell'
)
SELECT
  COUNT(*) AS sells,
  ROUND(SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END), 2) AS gross_profit_usd,
  ROUND(ABS(SUM(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE 0 END)), 2) AS gross_loss_usd,
  CASE
    WHEN ABS(SUM(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE 0 END)) = 0 THEN NULL
    ELSE ROUND(
      SUM(CASE WHEN pnl_usd > 0 THEN pnl_usd ELSE 0 END) /
      ABS(SUM(CASE WHEN pnl_usd < 0 THEN pnl_usd ELSE 0 END)),
      3
    )
  END AS profit_factor
FROM sells;
"
```

### 4B. If `side` does not exist on `trades`

Do not guess. Probe sample rows first:

```bash
sqlite3 "$DB_PATH" "
SELECT *
FROM trades
WHERE timestamp >= '2026-03-29T17:44:00'
LIMIT 3;
"
```

Then inspect nearby tables that might carry action labels:

```bash
sqlite3 "$DB_PATH" "PRAGMA table_info(wallet_txns);"
sqlite3 "$DB_PATH" "
SELECT *
FROM wallet_txns
ORDER BY rowid DESC
LIMIT 5;
"
```

If the schema does not expose a reliable sell marker, stop and document the ambiguity before running any broader pack.

## Step 5 — Only After the Minimal Truth Query

If and only if the schema is clearly understood:

- use the legacy pack for wider read-only analysis when the queried columns exist
- use the v3.2 pack only if `filter_regime` exists and sell-side labeling is confirmed compatible

The first authoritative update is based on the minimal truth query, not the wider pack.

## Step 6 — Capture for Tracker and Ledger

Paste these into the Phase 6 execution log:

- dashboard snapshot result
- `PRAGMA table_info(trades)` output
- `SELECT COUNT(*) FROM trades;`
- post-epoch paper-sell count query output
- PF query output
- whether the DB file queried was live or copied

## Step 7 — Documentation Rule

Update tracker and memory from the server output only.

If the number is:

- `7 / PF 1.42`: tracker was right, memory was wrong
- `25 / PF 1.73`: memory was right, tracker was stale
- anything else: both prior references must be corrected explicitly with timestamped notes

## Known Corrections to Earlier Guidance

- Do not run `python src/data/migrate.py` as part of Phase 6.
  - Phase 6 is read-only diagnostics.
- Do not assume the query packs are safe first-pass tools.
  - Current packs still need schema compatibility checks.
- The migration CLI uses `--sqlite-path`, not `--db-path`.

