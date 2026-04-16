# Sprint 7 - Codex Handoff (Gate 7A trade-row verification)

**Date:** 2026-04-16
**Companion to:** `SPRINT_7_COHORT_EVIDENCE.md`, `SPRINT_7_EXECUTION_LOG.md`
**Audience:** Codex (execution lane) - what to run on the VPS to close Gate 7A

Codex executes. Claude records. Neither touches the other's lane.

---

## Current verified state (as of 2026-04-16 19:12 UTC)

- **Branch:** `codex/stabilize-20260416`; local and `origin` in sync at `c500cd2`.
- **VPS runtime parity:** restored via `backup_runtime_sync_20260416_181311`; `lazarus.py` and `startup_config.py` synced; service active since `2026-04-16 18:13:32 UTC`.
- **Startup evidence:** `filter_regime=original (bot_config)`; banner and runtime line both show `regime original`; regime re-confirmed at `18:13:33`, `18:30:47`, `18:48:27`, `19:06:16`.
- **Scanner health:** cycles 19 -> 100 in ~58 min; funnel `200 -> 0` per cycle; vol `~125-130` and chg_low `~57-63` dominant rejections.
- **Trade evidence:** post-restart trade query (`timestamp >= '2026-04-16T18:13:33'`) returns `0` rows. No tagged trade row exists yet. Gate 7A remains open.

**Gate rule:** no sells count toward the Gate 7B 20-sell cohort until a trade row with `filter_regime='original'` lands after `2026-04-16 18:13:33 UTC`.

---

## Single next action

Monitor the VPS for the first post-restart trade row and verify its `filter_regime` tag. Do not change scanner config, filter thresholds, or deployed code. The runtime is correct; we are waiting for `original` to clear a candidate.

### Decision rules

| Observation | Gate state | Next step |
|---|---|---|
| First post-restart trade row has `filter_regime='original'` | **Gate 7A closes.** Gate 7B officially begins (cohort-of-record clock starts on that row). | Append `Gate 7A.PASS` entry to `SPRINT_7_EXECUTION_LOG.md` with row timestamp + token. Start 20-sell cohort tally. |
| First post-restart trade row has a different `filter_regime` value (e.g. `wide_net`, `unknown`, empty) | **Gate 7A fails as F5 (trade-write/tagging mismatch).** | Do not restart. Capture the row, current `bot_config`, and current `dynamic_config`. Append `Gate 7A.F5` to `SPRINT_7_EXECUTION_LOG.md`. Page Claude for diagnosis. |
| Zero rows returned at checkpoint | **Gate 7A remains open (healthy-waiting).** | Append `Gate 7A.F4.V{N+1}` to `SPRINT_7_EXECUTION_LOG.md` with cycle count + 1 regime re-log sample + row count. |

---

## Copy-paste VPS bash

All commands run on the VPS (`/home/solbot/lazarus/`). Database path defaults to `/home/solbot/lazarus/logs/lazarus.db`.

### 1. Post-restart trade-row query (primary gate check)

```bash
sqlite3 /home/solbot/lazarus/logs/lazarus.db <<'SQL'
.headers on
.mode column
SELECT timestamp, token, action, filter_regime
FROM trades
WHERE timestamp >= '2026-04-16T18:13:33'
ORDER BY timestamp ASC
LIMIT 10;
SQL
```

### 2. Regime distribution (sanity check on tagging)

```bash
sqlite3 /home/solbot/lazarus/logs/lazarus.db <<'SQL'
.headers on
SELECT filter_regime, COUNT(*) AS n
FROM trades
WHERE timestamp >= '2026-04-16T18:13:33'
GROUP BY filter_regime;
SQL
```

### 3. Liveness + regime re-log sample

```bash
systemctl status lazarus --no-pager | head -20
journalctl -u lazarus -n 200 --no-pager | grep -E "filter_regime|Runtime filters|Filters:" | tail -10
```

### 4. Cycle advance check

```bash
journalctl -u lazarus -n 500 --no-pager | grep -oE "Cycle [0-9]+" | tail -5
```

---

## Boundaries (do not cross)

- **Do not edit Phase 6 artifacts.** Phase 6 is closed. Sprint 7 is additive.
- **`SPRINT_7_EXECUTION_LOG.md` is append-only.** Add new `Gate 7A.F{N}.V{N}` sections at the bottom; do not rewrite prior entries.
- **Do not touch `SPRINT_7_COHORT_EVIDENCE.md` body.** The narrative block at lines 107-125 is the agreed failure/restoration record. New evidence goes into the execution log.
- **Do not update `ops/config/go_live_tracker.md`** mid-sprint. The Day 10 addendum already reflects the Gate 7A pause. Next tracker edit is Sprint 7 close-out.
- **Environment separation:** local PowerShell for git/code/docs; VPS bash for runtime/service/DB. Do not run VPS queries from the local box (the DB there is stale or absent).
- **Restart discipline:** if the service is restarted for any reason, the Gate 7A cutoff timestamp resets. Log the new cutoff and reset the F4.V counter.
- **Do not change `filter_regime` in `bot_config` until Gate 7A closes.** A mid-sprint regime flip invalidates the cohort-of-record clock.

---

## Evidence locations

| Artifact | Path | Role |
|---|---|---|
| Sprint charter | `docs/sprints/SPRINT_7_COHORT_EVIDENCE.md` | Gate definitions, pass/fail criteria |
| Execution log | `docs/sprints/SPRINT_7_EXECUTION_LOG.md` | Append-only audit trail; one section per gate event |
| This handoff | `docs/sprints/SPRINT_7_CODEX_HANDOFF_20260416.md` | Operator runbook for Gate 7A closure |
| Go-live tracker | `ops/config/go_live_tracker.md` | Day 10 addendum records the pause |
| Runtime backup | VPS: `/home/solbot/lazarus/backup_runtime_sync_20260416_181311` | Pre-parity-restore snapshot |

---

## Cadence

Re-run the primary gate check (command 1) at every natural checkpoint - on your next VPS session, after any service event, or immediately when a `close` is observed in logs. If nothing has changed, a single-line `Gate 7A.F4.V{N+1}` entry with row count + cycle count is enough. If the row lands, promote to `Gate 7A.PASS` (or `Gate 7A.F5` if the tag is wrong) and stop; Claude will pick up from there.

---

**End of handoff. Runbook executes; execution log audits.**
