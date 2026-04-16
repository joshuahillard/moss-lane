# Sprint 7 — Cohort-of-Record Evidence (Paper-Mode, Runtime-Truth-First)

**Opened:** 2026-04-16 (following Phase 6 cohort close-out commit on branch `codex/stabilize-20260416`)
**Closes on:** 2026-04-23 (decision-review date — not a go-live date)
**Interim operational-integrity checkpoint:** 2026-04-20
**Owner:** Josh Hillard
**Mode:** Paper only. No live capital. No strategy/feature work.
**Companion artifacts:** `PHASE_6_EXECUTION_LOG.md` (cohort section), `ops/config/go_live_tracker.md` (Day 10 cohort addendum), `docs/MOSS_LANE_PROJECT_LEDGER.md` (Phase 6 close-out fifth bullet)

---

## Charter sentence

> **Sprint 7 does not begin when we intend to run `original`; it begins only when runtime evidence proves `original` is the live paper-mode cohort-of-record.**

Secondary anchor:

> Sprint 7 exists to produce decision-grade evidence on a single verified cohort-of-record, starting with `original`, with `v3.2_lowvol_epoch` held as a starvation fallback rather than a co-equal primary gate.

---

## Why Sprint 7 exists

Phase 6 cohort decomposition on `lazarus_phase6_readonly.db` (copied from production) resolved the aggregate Stoic Gate, but also changed the conclusion:

| Cohort | Sells | PF | Net PnL | Avg PnL | WR | Verdict |
|---|---|---|---|---|---|---|
| `original` | 10 | 2.18 | +$443.82 | 3.95% | 50.0% | Decision-grade but below 20-sell gate when treated as cohort-of-record |
| `wide_net_v1` | 15 | 0.955 | -$19.81 | 0.27% | 26.7% | **Rejected for go-live** |
| `v3.2_lowvol_epoch` | 0 | — | — | — | — | **Unvalidated** — zero production evidence |

The aggregate PF 1.520 is carried by `original`. `wide_net_v1` is a net drag. `v3.2_lowvol_epoch` has no sells yet.

Treating the Stoic Gate as cleared at the aggregate level would be a lie of composition. Sprint 7 corrects this by re-asserting the 20-sell gate on a single, verified cohort-of-record.

The failure mode Sprint 7 is designed to prevent is **runtime drift**: the bot documented as running `original` but actually running something else because `bot_config`, `dynamic_config`, `CFG`, or `DEFAULTS` disagree. This is not hypothetical — the 2026-03-28 **DB Config Override Bug** (ref: `feedback_db_config_override`, `project_quiet_market_patch`) is the precedent: v3 code was deployed but `bot_config` still held stale v2 values, and the bot ran under the stale values for 8+ hours with zero candidates. Sprint 7 treats that risk as live.

---

## Cohort structure

- **Primary cohort-of-record:** `original`. Single primary. All gate arithmetic is cohort-scoped to `filter_regime = 'original'`.
- **Secondary / shadow:** `v3.2_lowvol_epoch`. Held in reserve as a starvation fallback only (Gate 7C). Not actively promoted. Not counted toward the primary gate. Promotion is a decision event, documented as a sprint action, not a silent state transition.
- **Rejected for go-live:** `wide_net_v1`. Formally rejected on 2026-04-16 evidence. Permitted to run in paper mode **only** as a negative-control cohort and regime-detection signal. Not eligible to anchor any live-capital decision. Reinstatement requires a new sprint decision — not running totals, not defaults drift, not implicit eligibility.

---

## Runtime target: `original` profile — concrete values

Source of truth for the `original` profile is `docs/reference/WIDE_NET_V2_PLAYBOOK.md`, Tight Execution Mode column (line 25+ in the parameter table). Reproduced here inline so Sprint 7 does not depend on the playbook being re-read at verification time:

| Parameter | `original` target value |
|---|---|
| `min_hourly_vol` | **400** |
| `min_chg_pct` | **10.0** |
| `max_chg_pct` | **80.0** |
| `min_liq` | **50000** |
| `min_vmr` | **0.10** |
| `cooldown_seconds` | **7200** |
| `filter_regime` | **`original`** |

No other runtime parameters are in scope for Sprint 7. If any deployment step tries to change other parameters alongside, that is a scope breach — stop and re-baseline.

---

## Current repo state is *not* `original` — explicit drift acknowledgement

As of Sprint 7 open (branch `codex/stabilize-20260416`, commit `0e67552`), the repo itself defaults to `v3.2_lowvol_epoch`, not `original`. This is verified directly against HEAD:

**`src/data/config_defaults.py`** (lines 11–16):

```python
    "min_hourly_vol": 250,
    "min_chg_pct": 10.0,
    "max_chg_pct": 120.0,
    "min_liq": 30_000,
    "min_vmr": 0.10,
    "filter_regime": "v3.2_lowvol_epoch",
```

**`src/engine/lazarus.py`** (CFG dict, lines 141–154):

```python
    "min_hourly_vol":   250,
    "min_chg_pct":      10.0,
    "max_chg_pct":      120.0,
    "min_liq":          30_000,
    "min_vmr":          0.10,
    "filter_regime":    "v3.2_lowvol_epoch",
    ...
    "cooldown_seconds":     7200,
```

This means Sprint 7 starts with a runtime config change **and** a repo-alignment check. No new strategy code is being introduced, but the code/default layer must not remain misleading. Leaving repo defaults at `v3.2_lowvol_epoch` while `bot_config` is flipped to `original` would plant the next drift incident — a future deploy or restart that sources from `DEFAULTS` or `CFG` would silently revert the live bot to `v3.2_lowvol_epoch` without any log-visible transition.

**Operational framing:** `bot_config` is runtime truth. `CFG` and `DEFAULTS` are drift-prevention surfaces. All three must match. Repo-alignment is part of Gate 7A, not a separate follow-up.

---

## Gates — in order

Gates are ordered. Evidence from a later gate does not count until the earlier one has passed.

### Gate 7A — Runtime truth (operational integrity)

**This is the center of gravity of the charter.** Everything that happens after Gate 7A is conditional on it closing cleanly. If Gate 7A is not closed, **Sprint 7 has not started** — regardless of what the calendar says.

#### Gate 7A status - 2026-04-16

**Status: `startup parity restored; tagged-trade verification pending`.**

Gate 7A execution history is recorded in `docs/sprints/SPRINT_7_EXECUTION_LOG.md` (F1 failure -> F2 diagnosis -> F3 parity restoration -> F4 startup parity proven). Summary:

- **7A.F1 - Failure:** Initial restart after `bot_config` was set to `original` produced a startup banner advertising `chg 10.0-100.0% | liq >$30,000`. Runtime truth did not match DB intent.
- **7A.F2 - Diagnosis:** VPS inspection found deployed-code drift, not a DB-config mistake. `/home/solbot/lazarus/lazarus.py` lacked `apply_startup_config_overrides`; `/home/solbot/lazarus/startup_config.py` was missing; deployed `record_trade()` did not write `filter_regime`. Decision recorded: full runtime sync over manual hotfix.
- **7A.F3 - Parity restoration:** Runtime sync of `/home/solbot/lazarus/lazarus.py` and `/home/solbot/lazarus/startup_config.py` completed at `2026-04-16 18:13:33 UTC`. Backup at `/home/solbot/lazarus/backup_runtime_sync_20260416_181311`. `py_compile` passed, service restarted healthy. Note: `config_defaults.py` was not deployed to the VPS runtime path; repo/default alignment remains a separate repo concern.
- **7A.F4 - Startup parity proven:** Post-sync banner now reports `Filters: vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original`. Startup-config log lines confirm all seven `original` parameters were read from `bot_config` and applied.

**Sprint 7 evidence cutoff:** No sells with `timestamp < '2026-04-16T18:13:33'` count toward Gate 7B, regardless of `filter_regime` tag.

**Residual closure condition:** Check 6 (first-trade tag verification) remains pending. Gate 7A is not fully closed until the first post-restart trade row after `2026-04-16 18:13:33 UTC` is shown to carry `filter_regime = 'original'`. Until that row exists and is logged, Gate 7B remains paused and no sells count toward the 20-sell cohort-of-record target.

If the first post-restart trade row carries any `filter_regime` other than `'original'`, that opens a new Gate 7A failure branch specifically for the trade-write path, and Sprint 7 re-pauses.


#### 7A required checks — all six must pass

| # | Check | Method | Pass condition | Evidence to capture |
|---|---|---|---|---|
| 1 | `bot_config` reflects `original` | `SELECT key, value FROM bot_config ORDER BY key;` on `/home/solbot/lazarus/logs/lazarus.db` | All seven parameters (`min_hourly_vol=400`, `min_chg_pct=10.0`, `max_chg_pct=80.0`, `min_liq=50000`, `min_vmr=0.10`, `cooldown_seconds=7200`, `filter_regime='original'`) present and exact | Raw SQL output, pasted into sprint log |
| 2 | `dynamic_config` is not masking | `SELECT key, value FROM dynamic_config;` | No entry for any of the seven parameters that would override `bot_config` back to v3.2 values or any wide-net value | Raw SQL output, pasted into sprint log |
| 3 | `lazarus.py` CFG dict matches | Read `src/engine/lazarus.py` lines ~141–154 on the **server working tree** (not just repo HEAD) | Exact match to `original` profile | File diff or direct line quote |
| 4 | `config_defaults.py` DEFAULTS dict matches | Read `src/data/config_defaults.py` lines ~11–16 on the **server working tree** | Exact match to `original` profile | File diff or direct line quote |
| 5 | Startup banner verification | Restart `lazarus.service` (`systemctl restart lazarus`), then `journalctl -u lazarus --since "1 minute ago"` | Banner line logs `vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original` exactly | First 60s of log output, pasted into sprint log |
| 6 | First-trade tag verification | Wait for first new paper entry after restart, then `SELECT timestamp, token_symbol, filter_regime FROM trades ORDER BY id DESC LIMIT 1;` | `filter_regime = 'original'` on the first post-restart entry | Raw SQL output, pasted into sprint log |

All six must pass **in the same deploy window**. If any one fails, stop, fix it, and re-verify all six from the top. Partial passes do not count.

Note on check 3 and 4: the server's working tree must be checked, not just repo HEAD. A `git pull` on the server is required before these checks if the branch has not been synced. If the server is running from a different branch or a detached commit, that is itself a Gate 7A failure and must be reconciled before continuing.

#### 7A close-out condition

Gate 7A is closed when all six checks pass and their evidence is pasted into the sprint log and committed. At that point — and only at that point — Sprint 7 has begun, and trade sells tagged `filter_regime = 'original'` from the post-restart timestamp onward are eligible Gate 7B evidence.

#### What Gate 7A is not

- Not a code change — no new features, no refactors.
- Not a filter invention — the `original` profile already exists in the playbook and the pre-v3.2 history.
- Not an optimization — if `original` underperforms, that is Gate 7B's verdict, not Gate 7A's problem.
- Not a one-time check — if `lazarus.service` is restarted during Sprint 7 for any reason, Gate 7A must be re-verified before counting further evidence.

---

### Gate 7B — Cohort-of-record evidence (the gate that actually matters)

Starts only after Gate 7A closes. All metrics are scoped to `filter_regime = 'original'` **and** `timestamp` after the Gate 7A close-out restart timestamp.

| Metric | Target |
|---|---|
| Post-7A sells tagged `filter_regime = 'original'` | **≥ 20** |
| Running profit factor across those ≥20 sells | **≥ 1.5** |
| Running win rate | **≥ 40%** (soft — PF is the primary signal) |
| Drop-dead hold condition | If running PF falls below **1.0** at any point where N ≥ 10 `original` sells, pause the sprint immediately. Do not continue collecting. |

**Why PF ≥ 1.5, not ≥ 1.7:** the 1.73 figure in retired memory was a drifted recollection of the 1.74% avg PnL, not a real profit factor. Raising the threshold to 1.7 on that basis would be arbitrary. 1.5 is a clean "meaningfully profitable after edge decay" threshold consistent with what the aggregate actually produced on mixed cohorts (1.520) — `original` alone should comfortably exceed it (on Phase 6 evidence, `original` was at PF 2.18 on N=10).

**Why 20 sells, not more:** re-asserting the same gate the project already committed to. Raising it post-hoc would look like goalpost-moving; lowering it would undermine the Phase 6 correction.

---

### Gate 7C — Fallback promotion (only if 7B cannot progress)

Triggered only by **starvation**, not by outcome.

| Condition | Action |
|---|---|
| After Gate 7A closes, `original` produces **zero new entries** (not sells — entries) for **≥ 24 consecutive hours** | Halt `original`. Flip runtime to `v3.2_lowvol_epoch`. Re-run Gate 7A for the new cohort (same six-check ceremony, same concrete-value discipline). Record the promotion as a formal sprint decision: starvation evidence (scan volume, candidate count, filter-dying reasons from live logs), the new primary cohort, the Gate 7A evidence for the new cohort, and the date/time of switch. |
| After promotion: `v3.2_lowvol_epoch` **also starves** for ≥24 consecutive hours | Halt the sprint. This is an upstream market signal, not a filter problem. Raise for architectural review. Do not reopen `wide_net_v1` as a substitute. |

Promotion is **reversible** if `original` regains signal later, but only by another formal decision with the same evidence-and-ceremony discipline.

---

## Decision-review cadence — interim + final

| Date | Purpose | Pass/fail question |
|---|---|---|
| **2026-04-20** (interim, 4 days out) | Operational integrity checkpoint | Did Gate 7A close cleanly? Are `original`-tagged entries accruing? If no entries, is starvation established yet or do we need more time before triggering 7C? |
| **2026-04-23** (decision-review, 1 week out) | Cohort-of-record evidence review | Has Gate 7B closed? If not, why — starvation (→ Gate 7C already triggered), Gate 7A regression (drift found mid-sprint), or just insufficient time? |

The decision-review on 2026-04-23 is explicitly **not** a go-live date. The only outputs it can produce are:

1. **`original` gate cleared.** Move to a separate go-live decision note with its own date, its own criteria, and its own audit trail. That note is not authored inside Sprint 7.
2. **`original` starved → `v3.2_lowvol_epoch` was promoted.** Evaluate the promoted cohort's evidence instead. If the promoted cohort's gate has also cleared, same disposition as option 1. If not, extend.
3. **Neither cohort produced decision-grade evidence.** Extend Sprint 7 by one week with a named, documented reason for the extension. Extensions are not indefinite — a second extension requires architectural review.

Option 4 on that list ("go live on current state") does not exist.

---

## Non-goals (explicit, to prevent scope creep)

- No tiered-TP work
- No dev-wallet analysis
- No regime-detection implementation beyond the `filter_regime` tag already in place
- No live deploy under any circumstances
- No new filter invention — the cohorts in play are `original` and `v3.2_lowvol_epoch`. No third candidate is eligible during Sprint 7.
- No re-opening of `wide_net_v1` for anything beyond paper regime-detection observation
- No bundling of Sprint 7 runtime changes with any other work (the Phase 5 `startup_config.py` scope-expansion lesson holds)

---

## Audit trail

- **This file** (`docs/sprints/SPRINT_7_COHORT_EVIDENCE.md`) is the charter. Append sections as gates are approached, attempted, and closed or reset.
- **Gate close-out notes** follow the 5-line format used in Phase 0–6: Outcome / Evidence / Files / SHA / Next gate. Append to this file.
- **Cohort queries** re-run on each checkpoint day against a **fresh copy** of `/home/solbot/lazarus/logs/lazarus.db` (never the live DB). Query outputs pasted into this file.
- **Starvation episodes** logged with scan volume, candidate count, dominant filter-dying reasons, and duration. Not just "no trades" — the *why*.
- **Promotion events** (Gate 7C) logged as formal sprint decisions, including the new cohort's Gate 7A evidence.

Commit cadence: same as Phase 0–6. Focused commits per closed gate, not one giant end-of-sprint dump.

---

## Risks and hold conditions

| Risk | Hold condition |
|---|---|
| Paper-mode starvation on `original` (the same v3.2-triggering issue) | ≥24h zero entries → Gate 7C triggered |
| Runtime drift during sprint (bot restart re-loading v3.2 DEFAULTS because repo wasn't aligned) | Any restart must re-verify Gate 7A before sells count again |
| Three-layer config slippage (DB right, code wrong, or vice versa) | Gate 7A checks 3 and 4 cover this — explicit pass requirement, not inferred |
| Server-vs-repo branch drift (server running a different commit than the branch HEAD we assume) | Gate 7A checks 3 and 4 check the **server working tree**, not repo HEAD alone |
| Phase 1 SHA back-fill still open (`<port commit hash — pending>` in `PHASE_1_EXECUTION_LOG.md`) | Not a Sprint 7 blocker, but flag for the next Codex window to back-fill before opening anything new |

---

## Sprint 7 close-out criteria

Sprint 7 closes when one of these is true:

- Gate 7B cleared on `original` or the promoted cohort → decision-review on 2026-04-23 produces option 1 or option 2. Sprint 7 closes. A separate go-live decision sprint opens.
- Second extension would be needed → architectural review is raised instead. Sprint 7 closes into that review.
- Hard-stop condition triggered (PF < 1.0 at N ≥ 10 on the cohort-of-record, or both cohorts starved) → sprint closes with a named negative result. That is still decision-grade information.

Sprint 7 does not close by silent fade. It closes by an explicit decision recorded in this file.
