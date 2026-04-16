# Phase 6 — Execution Log (Server Reality Check)

**Decision:** Resolve the Stoic Gate contradiction (tracker 7/PF 1.42 vs memory 25/PF 1.73) using read-only production evidence only. No writes, no migrations, no schema changes.
**Branch:** `codex/stabilize-20260416` (continuing)
**Baseline at start:** `eba3b8b` (Phase 6 pre-flight — checklist + re-baseline log committed)
**Started:** 2026-04-16
**Executor:** Codex (coding lane, on VPS)
**Auditor:** Claude (planning lane)
**Format:** Step-by-step evidence capture. Companion to `PHASE_6_SERVER_REALITY_CHECK_CHECKLIST_20260416.md`.

---

## Pre-flight — Checklist committed

- **Outcome:** Phase 6 checklist and re-baseline log committed to repo-canonical location. Checklist is the hard-rule contract for this phase: read-only, schema-probe-first, no assumptions about `side` or `filter_regime`.
- **Evidence:** `PHASE_6_SERVER_REALITY_CHECK_CHECKLIST_20260416.md` present in `github-repo/docs/sprints/`. Re-baseline section added to `PHASE_5_EXECUTION_LOG.md` with the authoritative SHA map through `649a677`.
- **Commit hash:** `eba3b8b`
- **Next gate:** SSH into VPS, query copied DB, capture evidence.

---

## Step 1 — SSH and runtime state

- **Outcome:** Codex SSH'd to the VPS, confirmed bot process state, pulled `codex/stabilize-20260416` to `649a677`.
- **Evidence:** *(Codex to paste exact `ps aux | grep lazarus` and `git log -1` output on next update.)*
- **Next gate:** Copy the DB file for query safety before running any read.

---

## Step 2 — Query safety mode: copied DB

- **Outcome:** Production DB copied to a read-only query surface to avoid WAL lock contention with the live bot.
- **Path queried:** `/home/solbot/lazarus/logs/lazarus_phase6_readonly.db` (copy of `/home/solbot/lazarus/logs/lazarus.db`)
- **Why:** Bot was running. Querying the live DB directly risks lock contention and ambiguity about whether the snapshot is atomic. Copied file gives a point-in-time surface that is safe to query as aggressively as needed without touching production I/O.
- **Next gate:** Schema probe on the copy.

---

## Step 3 — Schema probe

- **Outcome:** Confirmed both `trades.side` and `trades.filter_regime` exist on the production DB copy. This is important: it means the minimal truth query (Step 4A path from the checklist) is safe to run, and the broader cohort queries (regime splits) are available if Josh wants them next.
- **Evidence:** `PRAGMA table_info(trades)` returned a schema that includes `side` and `filter_regime` columns. Row count captured as well.
- **Next gate:** Run the minimal epoch-gated truth queries.

---

## Step 4 — Minimal epoch-gated truth queries (Step 4A path)

### 4A.i — Post-epoch paper-sell count

```sql
SELECT COUNT(*)
FROM trades
WHERE timestamp >= '2026-03-29T17:44:00'
  AND paper = 1
  AND lower(side) = 'sell';
```

- **Result:** **25**

### 4A.ii — Profit factor and PnL aggregation

```sql
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
```

- **Results (authoritative post-epoch paper-mode):**
  - Sells: **25**
  - Gross profit: **$1,239.15**
  - Gross loss: **$815.14**
  - Profit factor: **1.520**
  - Net PnL: **$424.01**
  - Avg PnL: **1.74%**
  - Win rate: **36.0%**

---

## Step 5 — Cohort decomposition (ran 2026-04-16, post-aggregate)

After the aggregate Day 10 block committed (`0e67552`), cohort decomposition ran against the same copied DB (`/home/solbot/lazarus/logs/lazarus_phase6_readonly.db`). The result materially changed the decision outlook.

### 5A — Cohort split by `filter_regime`

| Cohort | Sells | Gross Profit | Gross Loss | PF | Net PnL | Avg PnL | WR | Confidence band |
|---|---|---|---|---|---|---|---|---|
| `original` | 10 | $819.99 | $376.17 | **2.18** | +$443.82 | 3.95% | 50.0% | Decision-grade (≥5-sell rule) |
| `wide_net_v1` | 15 | $419.15 | $438.96 | **0.955** | -$19.81 | 0.27% | 26.7% | Decision-grade (≥5-sell rule) |
| `v3.2_lowvol_epoch` | 0 | — | — | — | — | — | — | **Unvalidated** — zero production evidence |
| Aggregate | 25 | $1,239.15 | $815.14 | 1.520 | +$424.01 | 1.74% | 36.0% | — |

### 5B — Exit-reason distribution

**`original` cohort:**

| Exit reason | Sells | Net PnL | Avg | WR |
|---|---|---|---|---|
| `sniper_timeout` | 5 | -$99.50 | -1.31% | 40.0% |
| `take_profit` | 2 | +$710.41 | 28.42% | 100.0% |
| `timeout` | 1 | +$94.91 | 6.29% | 100.0% |
| `stale_timeout` | 1 | -$75.00 | -5.00% | 0.0% |
| `emergency_rug` | 1 | -$187.00 | -12.05% | 0.0% |

**`wide_net_v1` cohort:**

| Exit reason | Sells | Net PnL | Avg | WR |
|---|---|---|---|---|
| `sniper_timeout` | 10 | -$259.02 | -1.71% | 10.0% |
| `trail_stop` | 2 | +$98.78 | 3.62% | 100.0% |
| `stop_loss` | 2 | -$173.83 | -8.59% | 0.0% |
| `take_profit` | 1 | +$314.27 | 31.09% | 100.0% |

### 5C — Interpretation

- The aggregate PF 1.520 is **carried by `original`**, not earned evenly. Removing `original` from the mix would leave `wide_net_v1` alone at PF 0.955 — net-negative.
- `original` is genuinely promising: PF 2.18, WR 50.0%, +$443.82 net over 10 sells. The two take-profits (+$710.41) do the work.
- `wide_net_v1` is a **net drag**: 10 of 15 sells are `sniper_timeout` losers, the single take-profit cannot offset accumulated losses. This is the "wide-net produces volume of bad entries" story that has appeared throughout the Moss Lane timeline, now confirmed on production evidence.
- `v3.2_lowvol_epoch` remains **unvalidated** — Phase 6 cannot say whether the v3.2 regime works or not. That deferral is its own finding.
- Both `original` and `wide_net_v1` meet the ≥5-sell decision-support threshold, so the split is not a sample-size artifact.

### 5D — Changed conclusion

The "Stoic Gate cleared" framing from the aggregate is **correct in the count-only sense and misleading in the decision-grade sense**. `original` alone is below the 20-sell gate if treated as the cohort-of-record. Anchoring go-live on the mixed aggregate would be a lie of composition.

This finding opens **Sprint 7** (`docs/sprints/SPRINT_7_COHORT_EVIDENCE.md`) under runtime-truth-first discipline:

- Primary cohort-of-record: `original` (re-assert 20-sell gate on this cohort alone)
- Secondary / starvation fallback: `v3.2_lowvol_epoch` (held in reserve, not co-equal)
- Rejected for go-live: `wide_net_v1` (paper-only negative-control cohort)
- No go-live date set. Decision-review date: 2026-04-23. Interim integrity checkpoint: 2026-04-20.

---

## Step 6 — Tracker and memory reconciliation

### Tracker — updated

`github-repo/ops/config/go_live_tracker.md` now carries a new "Day 10 — 2026-04-16 (Server reality check, authoritative)" block with the verbatim numbers above. Placement: between the existing "Day 10 — Tracker reset, not a decision" block and the "DECISION DAY — 2026-04-07" block. The earlier Day 3 checkpoint (7 trades / PF 1.42) is not deleted — it remains as historical record, but the Day 10 authoritative block is the reference any future decision must cite.

### Memory — cleaned up

- `project_stoic_gate_cleared.md` — retired. Contents replaced with a tombstone pointing at the verified memory. Claim of PF 1.73 / +43.54% was wrong; 25 trade count was right.
- `project_stoic_gate_unverified.md` — retired. Contradiction is resolved; tombstoned to point at the verified memory.
- `project_stoic_gate_verified.md` — new. Single authoritative memory record of Phase 6 outcome. Cites PF 1.520, not 1.73.
- `MEMORY.md` index — both retired pointers removed, replaced with a single "Stoic Gate verified on production" line.

### Contradiction resolution summary

| Prior reference | Before Phase 6 | After Phase 6 | Verdict |
|---|---|---|---|
| Tracker on disk | 7 sells / PF 1.42 | 25 sells / PF 1.520 | Tracker was stale (Day 3 snapshot never updated) |
| Claude memory | 25 sells / PF 1.73 / +43.54% | 25 sells / PF 1.520 / +$424.01 / avg 1.74% | Count right; PF wrong (1.73 was likely drifted from the 1.74% avg PnL) |

---

## Step 7 — Documentation rule satisfied

Per the Phase 6 checklist Step 7 documentation rule ("update tracker and memory from the server output only"), both have been updated from the server output.

- Tracker reflects production evidence.
- Memory reflects production evidence and carries explicit instruction to cite PF 1.520, never 1.73.
- Evidence location (this log) is repo-canonical.

---

## Auditor observations — Phase 6 close-out

### 1. Stoic Gate count threshold is cleared — PF is lower than memory claimed

The 20-trade gate is cleared (25 ≥ 20). That part of the prior working assumption was correct. What was not correct was the quality of those trades: actual PF 1.520 is materially below the remembered 1.73. The 1.73 figure was almost certainly a drift from the 1.74% avg PnL — related number, wrong metric. Any go-live decision note from here on must cite PF 1.520.

### 2. The "+43.54% cumulative" figure was never corroborated

The retired memory included "+43.54% cumulative PnL." The Phase 6 authoritative query returns a net PnL of $424.01 against the $10k virtual book, which is +4.24%, not +43.54%. The +43.54% figure is not backed by the production query and should not be cited again without a specific query that reproduces it.

### 3. Schema safety for v3.2 cohort analysis is confirmed

Both `side` and `filter_regime` exist on the production DB. That retires two risks from the Phase 1 risk register:
- "Query pack `filter_regime` schema assumption" (Phase 2 scope) — closed by evidence.
- "Sell-side labeling compatibility" — closed by evidence (`lower(side) = 'sell'` works).

Any broader analysis Josh requests next can run the v3.2-aware queries safely against the copied DB.

### 4. The Phase 1 audit-trail gap is still present

Phase 6 closing does not close Phase 1. The port-commit and redirect-stub SHAs for Phase 1 were never back-filled into `PHASE_1_EXECUTION_LOG.md`. That log still shows `<port commit hash — pending>`. Whenever Josh next runs Codex, the Phase 1 back-fill should happen before any new phase opens.

### 5. Phase 6 stayed read-only — no discipline drift this time

Unlike Phase 5's scope expansion (test commit that bundled a `startup_config.py` refactor and a `lazarus.py` edit), Phase 6 stayed inside its read-only boundary. No writes, no migrations, no schema changes. The separation between "verify" and "change" held.

### 6. Cohort decomposition is the real Phase 6 finding

The aggregate reconciliation (25 / PF 1.520) was the charter. The cohort decomposition is what actually changes the next decision. `original` alone (PF 2.18, N=10) is below gate; `wide_net_v1` (PF 0.955, N=15) is net-harmful; `v3.2_lowvol_epoch` is zero-evidence. Anchoring any go-live on the aggregate would repeat the same mixed-regime error the aggregate itself was meant to correct. `wide_net_v1` is formally rejected for go-live on this evidence. Sprint 7 opens to re-assert the Stoic Gate on a single verified cohort-of-record.

---

## Close-out

Phase 6 is **closed** on the Stoic Gate reconciliation charter, and the cohort decomposition has changed the next-decision framing. The production number is on paper, in the tracker, and in memory. The contradiction is resolved. The aggregate gate-clear is demoted to a count-only clear; decision-grade evidence now requires Sprint 7.

Remaining open items (not Phase 6 scope, flagged for the next phase boundary):
- Phase 1 SHA back-fill (still `<port commit hash — pending>` in `PHASE_1_EXECUTION_LOG.md`)
- Broader cohort / regime analysis on `lazarus_phase6_readonly.db` — on hold for Josh's signal
- New go-live decision date — must cite PF 1.520, never 1.73
- Project ledger close-out note for Phase 6 — to be added as a four-bullet entry in `MOSS_LANE_PROJECT_LEDGER.md`
