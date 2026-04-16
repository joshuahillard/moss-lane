# Sprint 7 - Execution Log

**Sprint:** Sprint 7 - Cohort-of-record evidence (paper-mode)
**Charter:** `docs/sprints/SPRINT_7_COHORT_EVIDENCE.md`
**Started:** 2026-04-16
**Current status:** Gate 7A in progress
**Evidence cutoff for Gate 7B:** no sells before `2026-04-16 18:13:33 UTC` count toward the cohort-of-record gate

---

## Gate 7A.F1 - Failure evidence: runtime truth did not match intent

- **Outcome:** Gate 7A failed at startup-banner verification.
- **What was intended:** `original` runtime profile from bot_config.
- **What was observed:** after restart, the VPS process still advertised `chg 10.0-100.0% | liq >$30,000`, proving it was not actually running `original`.
- **Operational consequence:** Sprint 7 evidence collection remained paused; no sells could count toward Gate 7B.
- **Evidence:** startup banner output, bot_config snapshot, dynamic_config snapshot.

## Gate 7A.F2 - Diagnosis: deployment-parity blocker

- **Outcome:** VPS inspection showed deployed-code drift, not a DB-config mistake.
- **Findings:**
  - `/home/solbot/lazarus/lazarus.py` lacked `apply_startup_config_overrides`
  - `/home/solbot/lazarus/startup_config.py` was missing
  - deployed banner still used the old format
  - deployed `record_trade()` path did not write `filter_regime`
- **Interpretation:** the VPS runtime was materially behind the stabilized repo branch; Sprint 7 was blocked on deployment parity.
- **Decision:** choose full runtime sync over manual hotfix.

## Gate 7A.F3 - Parity restoration

- **Outcome:** runtime parity restored on the VPS for the files the service actually executes.
- **Synced files:**
  - `/home/solbot/lazarus/lazarus.py`
  - `/home/solbot/lazarus/startup_config.py`
- **Backup artifact:** `/home/solbot/lazarus/backup_runtime_sync_20260416_181311`
- **Verification:**
  - helper file present
  - startup override hook present
  - `record_trade()` now includes `filter_regime`
  - `py_compile` passed
  - service restarted healthy
- **Important note:** `config_defaults.py` was not deployed to the VPS runtime path; repo/default alignment remains a separate repo concern.

## Gate 7A.F4 - Startup parity proven; tagged-trade verification pending

- **Outcome:** startup logs now prove the runtime is operating on `original`.
- **Verified from logs:**
  - `Mode: PAPER`
  - `Startup config: min_hourly_vol=400`
  - `Startup config: min_chg_pct=10.0`
  - `Startup config: max_chg_pct=80.0`
  - `Startup config: min_liq=50000`
  - `Startup config: min_vmr=0.10`
  - `Startup config: filter_regime=original`
  - banner shows `Filters: vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original`
  - runtime line shows the same
- **Current status:** Gate 7A status is `startup parity restored; tagged-trade verification pending`
- **Remaining closure condition:** first post-restart trade row after `2026-04-16 18:13:33 UTC` must carry `filter_regime='original'`
- **Gate rule:** until that row exists, Gate 7B remains paused and no sells count toward the 20-sell cohort-of-record target.

## Pending next step

- Query for the first post-restart trade row:
  - `timestamp >= '2026-04-16T18:13:33'`
  - verify `filter_regime='original'`
- If true: Gate 7A closes and Gate 7B officially begins.
- If false: open a new Gate 7A failure branch specifically for trade-write/tagging mismatch.

## Gate 7A.F4.V1 - Runtime liveness + regime parity re-verified (no trade yet)

- **Outcome:** VPS runtime remains healthy and on `original`; no post-restart trade rows exist yet.
- **Evidence (VPS, 2026-04-16 18:13:32-18:28 UTC):**
  - `systemctl status lazarus`: active since `2026-04-16 18:13:32 UTC`
  - Startup log (`2026-04-16 18:13:33 UTC`): `filter_regime=original (bot_config)`; `Filters: vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original`; `Runtime filters: vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original`
  - Cycles 19-25: DexScreener evaluated ~200 cached addrs/cycle; filter funnel reduced `200->0` each cycle, dominated by `vol ~125-130` and `chg_low ~57-63`
  - Post-restart trade query (`timestamp >= '2026-04-16T18:13:33'`) returned `0` rows
- **Interpretation:** Gate 7A remains open - startup parity proven, tagged-trade verification pending because no post-restart trade rows exist yet. No tagging-mismatch failure has been observed, but the trade-write path is not yet end-to-end proven.
- **Action:** Re-run the post-restart trade-row query at the next checkpoint or immediately upon the first qualifying close.
