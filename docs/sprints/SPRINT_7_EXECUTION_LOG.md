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

## Gate 7A.F4.V2 - Checkpoint at ~58min post-restart (continued healthy-waiting)

- **Outcome:** Continued healthy-waiting. No post-restart trade rows yet; runtime remains on `original` with no drift across four re-log samples.
- **Evidence (VPS, 2026-04-16 19:12 UTC):**
  - `systemctl status lazarus`: active since `2026-04-16 18:13:32 UTC`; 58 min uptime
  - Runtime `regime original` re-confirmed at `18:13:33`, `18:30:47`, `18:48:27`, `19:06:16` - banner format preserved across all four samples
  - Cycle count advanced from 25 (F4.V1) to 100; ~75 cycles in ~45 min
  - Filter funnel stable: `200 -> 0` per cycle; vol `~125-130` and chg_low `~57-63` dominant rejections
  - Post-restart trade query (`timestamp >= '2026-04-16T18:13:33'`) returned `0` rows; regime distribution query returned `0` rows
- **Origin parity:** `c500cd2` pushed to `origin/codex/stabilize-20260416`; local and origin in sync.
- **Interpretation:** Gate 7A remains open. Same interpretation as F4.V1; no new failure signal. `original` regime is selective enough that zero candidates have cleared the funnel in 58 min. Scanner health and regime stability independently re-verified.
- **Action:** Re-run the post-restart trade-row query at the next checkpoint or immediately upon the first qualifying close. Codex handoff for this gate: `docs/sprints/SPRINT_7_CODEX_HANDOFF_20260416.md`.

## Audit gap - 2026-04-17 through 2026-04-24

- **Span:** approximately 8 days between the last recorded checkpoint (`Gate 7A.F4.V2`, `2026-04-16 19:12 UTC`) and the next verified runtime observation (`2026-04-24 06:17:16 UTC`).
- **Status:** no checkpoint entries were made in this window. No runtime re-verification, no trade-row query, no scanner-health sample is on file for the gap.
- **Discipline:** the gap is acknowledged, not reconstructed. Any claim about runtime behavior between 2026-04-17 and 2026-04-24 must be sourced from fresh VPS evidence at the time of inspection, not inferred from the surrounding entries.
- **Consequence for Gate 7A:** the charter's restart-resets rule still applies. Because a service restart is confirmed at `2026-04-24 06:17:16 UTC` (see `Gate 7A.F4.R1` below), the pre-restart cutoff `2026-04-16 18:13:33 UTC` is retired and Gate 7A re-evaluates against the new cutoff regardless of what happened during the gap.

## Gate 7A.F4.R1 - Service restart 2026-04-24 06:17:16 UTC; Gate 7A cutoff resets

- **Outcome:** the Sprint 7 service was stopped and restarted cleanly at `2026-04-24 06:17:16 UTC`. Per the charter (`SPRINT_7_COHORT_EVIDENCE.md:150`) and the Codex handoff (`SPRINT_7_CODEX_HANDOFF_20260416.md:89`), the Gate 7A cutoff timestamp resets; the F4.V counter resets for this new cutoff.
- **Pre-shutdown event:** at `2026-04-24 06:17:07 UTC` the learning engine wrote `position_pct=0.15` and `stop_loss=0.94` to `dynamic_config`, based on a 25-trade aggregate (WR=36.0%, avg=$16.9605). These two keys sit outside the seven Gate 7A filter keys; the write does not affect Check 2.
- **Shutdown signature:** clean systemd stop; 3h 20min 8.453s CPU, 116.1M memory peak; no OOM, no crash. `fail2ban-client: Shutdown successful` at `06:17:17 UTC` suggests a system-level event. `unattended-upgrades` is a plausible inference, but the cause is not directly logged in the inspected window.
- **New cutoff of record:** `2026-04-24 06:17:16 UTC`. All subsequent Gate 7A evidence is measured against this timestamp.

## Gate 7A.F4.R1.V1 - Six-check ceremony under the new cutoff (strict-charter reading)

This entry re-runs the charter's six Gate 7A checks (`SPRINT_7_COHORT_EVIDENCE.md:128-136`) against the runtime state that emerged from the `2026-04-24 06:17:16 UTC` restart. The strict-charter reading applies: all six checks - including Check 3 (deployed `lazarus.py` CFG) and Check 4 (`config_defaults.py` DEFAULTS) on the server working tree - must pass before Gate 7A closes. See the strict-charter adjudication section below for the scope disposition of the prior F3 note at line 43 of this log.

### Check 1 - bot_config

**Source:** VPS `/home/solbot/lazarus/logs/lazarus.db`, `bot_config` table.

**Query:**

```sql
SELECT key, value FROM bot_config
WHERE key IN (
  'min_hourly_vol', 'min_chg_pct', 'max_chg_pct',
  'min_liq', 'min_vmr', 'cooldown_seconds', 'filter_regime'
);
```

**Output:** 7 rows, all matching the `original` profile exactly:

- `min_hourly_vol=400`
- `min_chg_pct=10.0`
- `max_chg_pct=80.0`
- `min_liq=50000`
- `min_vmr=0.10`
- `cooldown_seconds=7200`
- `filter_regime=original`

**Verdict: PASS.** `bot_config` reflects the `original` profile on all seven gate keys.

### Check 2 - dynamic_config

**Source:** VPS `/home/solbot/lazarus/logs/lazarus.db`, `dynamic_config` table.

**Query:**

```sql
SELECT key, value FROM dynamic_config
WHERE key IN (
  'min_hourly_vol', 'min_chg_pct', 'max_chg_pct',
  'min_liq', 'min_vmr', 'cooldown_seconds', 'filter_regime'
);
```

**Output:** zero rows.

**Startup-echo confirmation:** at `2026-04-24 06:17:16 UTC` the `Startup config` block echoed all seven gate keys sourced from `bot_config`; no `dynamic_config` override was present for any of them. The only rows currently in `dynamic_config` are `position_pct=0.15` and `stop_loss=0.94`, both outside the Gate 7A filter key set.

**Verdict: PASS.** `dynamic_config` holds no override for any of the seven gate keys; the runtime resolves each to its `bot_config` value, which Check 1 has verified aligns to `original`.

### Check 3 - deployed lazarus.py CFG literal

**Source:** deployed `/home/solbot/lazarus/lazarus.py`, CFG dict at lines 141-154.

**Evidence:** grep of the seven gate keys against the deployed file shows drift from `original`:

- `min_hourly_vol`: **250** (expected 400)
- `min_chg_pct`: 10.0 (matches)
- `max_chg_pct`: **120.0** (expected 80.0)
- `min_liq`: **30_000** (expected 50000)
- `min_vmr`: 0.10 (matches)
- `filter_regime`: **`v3.2_lowvol_epoch`** (expected `original`)
- `cooldown_seconds`: 7200 (matches)

`apply_startup_config_overrides` mutates the CFG dict in place at startup by reading `bot_config`, so runtime behavior resolves to the `original` profile despite the deployed literal. Startup banner and runtime re-logs (Check 5) confirm the override is effective.

**Verdict: FAIL.** Four of the seven CFG keys remain at `v3.2_lowvol_epoch` values in the deployed code. Under the strict-charter reading, the override hook does not satisfy Check 3 - the code layer must itself match `original`. Runtime-truth is preserved by the hook, but the drift-prevention surface is not aligned.

### Check 4 - config_defaults.py DEFAULTS alignment

**Source:** VPS `/home/solbot/` directory tree.

**Evidence:** `find /home/solbot -name config_defaults.py` returned no matches within the searched depth. `find /home/solbot -name .git -type d` returned no matches within the searched depth.

**Verdict: FAIL.** No `config_defaults.py` and no `.git` working tree were found on the searched `/home/solbot` server surface. The charter's check 4 cannot be satisfied from the current server evidence.

### Check 5 - startup banner and runtime re-logs

**Source:** `journalctl -u lazarus` from `2026-04-24 06:17:16 UTC` forward.

**Evidence:**

- Startup banner at `06:17:16 UTC`: `Filters: vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original`
- 26 `Runtime filters:` lines in the inspected window (initial line at startup plus 25 subsequent re-log samples), all identical to the banner. No drift across the sampled period.

**Verdict: PASS.** Startup banner and every sampled `Runtime filters:` line in the inspected window advertise `original`. No runtime drift observed.

### Check 6 - first post-restart trade tagged `filter_regime='original'`

**Source:** VPS `/home/solbot/lazarus/logs/lazarus.db`, `trades` table.

**Query:**

```sql
SELECT timestamp, symbol, side, filter_regime
FROM trades
WHERE timestamp >= '2026-04-24T06:17:16'
ORDER BY timestamp ASC
LIMIT 10;
```

**Output:** zero rows.

**Verdict: PENDING.** No trade row has been written after the `2026-04-24 06:17:16 UTC` cutoff. Check 6 cannot resolve PASS or FAIL until the first post-restart trade row exists. Until then, Gate 7B remains paused and no sells count toward the 20-sell cohort-of-record target.

### Scorecard

| Check | Verdict |
|---|---|
| 1 - bot_config | PASS |
| 2 - dynamic_config | PASS |
| 3 - deployed lazarus.py CFG | FAIL |
| 4 - config_defaults.py DEFAULTS | FAIL |
| 5 - startup banner / runtime re-logs | PASS |
| 6 - first-trade tag | PENDING |

**Gate 7A status:** does not close. Two code-layer checks FAIL; one tagged-trade check is PENDING. Sprint 7 remains open under the strict-charter reading.

## Strict-charter adjudication - 2026-04-24

A contradiction existed between two Sprint 7 records:

- The charter (`SPRINT_7_COHORT_EVIDENCE.md:96-97`) explicitly includes repo/default alignment inside Gate 7A ("All three must match. Repo-alignment is part of Gate 7A, not a separate follow-up.").
- The prior entry at line 43 of this log (under Gate 7A.F3 parity restoration) noted `config_defaults.py was not deployed to the VPS runtime path; repo/default alignment remains a separate repo concern`.

The F3 note, read strictly, removes Check 4 from the gate. The charter treats Check 4 as in-scope.

**Adjudication:** the charter governs. Checks 3 and 4 apply in full on the server working tree. The F3 note stands as historical record of Phase F3's scope of work (what F3 synced during parity restoration) but does not modify the Gate 7A close-out condition.

**Implication for Gate 7A.F4.R1.V1:** Check 3 and Check 4 are evaluated against the strict charter above. Their FAIL verdicts stand. Alignment of the deployed `lazarus.py` CFG literal to `original`, and placement of `config_defaults.py` on the server working tree, are prerequisite work for Gate 7A closure and are out of scope for this block.
