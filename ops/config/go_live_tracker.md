# Lazarus Go-Live Tracker

## Decision Window (Lapsed): 2026-03-30 → 2026-04-07 (extended at Day 3 checkpoint)

**Objective:** Achieve Profit Factor >= 1.5 across 20+ paper trades before committing live capital.

**Current state as of 2026-04-16:** The April 7 decision window has lapsed. The tracker remains the on-disk source of truth for the last verified numbers (`7/20` sells, `PF 1.42`), but the final decision was never recorded and must not be inferred from memory or later narrative docs.

## Reset Rules — 2026-04-16

- The April 7 decision window is **lapsed**, not pending.
- Cloud Run work from April 8-14 is valid infrastructure progress, but it does not resolve the VPS go-live decision.
- The paper bot starvation observed on April 15-16 is an operating-state change, not proof that the Stoic Gate was cleared or failed.
- A new decision date will be set only after the legacy-safe query pack is run against the server DB and the current tracker numbers are reconciled.
- **Cohort-of-record rule:** any future go-live decision must be based on one explicitly named regime or inferred cohort, not a blended dataset across `original`, `wide_net_v1`, `wide_net_v2`, and `v3.2_lowvol_epoch`.

---

## Day 1 Baseline — 2026-03-30 (CORRECTED after epoch format fix)

> **Correction note:** Original baseline (logged ~14:30 UTC) used 7 trades including 2+ pre-epoch leaked trades caused by T-vs-space timestamp format bug. After the epoch format fix was deployed, the corrected dataset is 3 valid post-epoch trades. See `MD/trades/Trade_Autopsy_2026-03-30.md` and `MD/trades/Weekly_Performance_Analysis_2026-03-30.md` for full breakdown.

| Metric | Current | Target | Gap | Status |
|---|---|---|---|---|
| **Paper Trades (sells)** | 3 | 20 | 17 remaining | In Progress |
| **Win Rate** | 33.3% (1W / 2L) | > 40% | -6.7pp | Approaching |
| **Profit Factor** | 4.61 | >= 1.5 | +3.11 (above) | Above Target |
| **Gross Profit** | +$439.53 (+29.59%) | — | — | 1 trade (CLOWN) |
| **Gross Loss** | -$95.27 (-6.36%) | — | — | 2 trades (Clippy, CAT) |
| **Net PnL** | +$344.26 (+3.44%) | Positive | +3.44% | On Track |
| **Avg Win** | +$439.53 / +29.59% | — | — | Data Point |
| **Avg Loss** | -$47.64 / -3.18% | — | — | Data Point |
| **Reward:Risk** | 9.3:1 | — | — | Strong |
| **Virtual Capital** | $10,000 | — | — | Paper Mode |
| **Real Wallet** | ~$103 SOL | — | — | Standby |

### Distance-to-Target Summary

- **Trades to Stoic Gate:** 17 more sells needed (3/20)
- **PF Status:** Currently 4.61 — well above 1.5 target, but fragile at n=3
- **Win Rate Gap:** ~7 percentage points below 40% threshold — one more win closes this

### Key Observations (Day 1 — Corrected)

1. **Stop-loss is working.** 2 losses averaged -3.18% per trade vs v2's -17.23% avg slippage. The 7-tier exit chain and 3s monitor interval are containing losses.
2. **Winner quality is strong.** 1 winner (CLOWN, +29.59%) more than offset both losses combined. The bounded-loss / unbounded-win thesis is demonstrating correctly.
3. **Sample size is critical.** n=3 means PF could invert with a single large loss. The Stoic Gate (20 trades) exists exactly for this reason — no conclusions, no tuning.
4. **Trade frequency is low.** 3 trades in ~34 hours during Extreme Fear (F&G Index: 8). This is expected behavior — Lazarus should be quiet in thin markets.
5. **Epoch fix validated.** The T-vs-space bug was caught and fixed. All future queries use the corrected format.

---

## Projected Timeline (Updated Day 3 — Wednesday Checkpoint)

| Metric | Assumption | Projected Date | Confidence |
|---|---|---|---|
| **20 trades reached** | ~2.3 trades/day (revised down again) | ~April 6-7 | Low |
| **Stoic Gate unlocked** | 20 sells complete | ~April 6-7 | Low |
| **Go-Live decision** | Extended window | **April 7 (revised)** | Depends on market thaw |

> **Day 3 checkpoint revision:** Trade frequency declining further — 7 trades in ~76 hours = 2.3/day. Day 3 produced only 1 new trade (IRAN). Market remains in Extreme Fear with near-zero candidates per scan cycle. The Stoic Gate won't clear until April 6-7 at best. **Decision window extended from April 3 → April 7** per Wednesday decision matrix (trade count < 8 triggers extension). This is the correct call — making a go/no-go on n=7 would be premature and defeats the purpose of the 20-trade validation.

---

## Wednesday Checkpoint Criteria (April 1)

### What We'll Compare
| Metric | Day 2 Value | Wednesday Target | "Helped" | "Hurt" | "No Effect" |
|---|---|---|---|---|---|
| **Trade Count** | 6 | 10+ | 10+ trades | <8 trades | 8-9 trades |
| **Profit Factor** | 1.20 | >= 1.3 | PF rising toward 1.5 | PF < 1.0 | PF 1.0-1.3 |
| **Win Rate** | 16.7% | >= 25% | 2+ new wins | 0 new wins, 3+ losses | Mixed |
| **Avg Loss** | -4.76% | < -5% | Losses staying contained | Any loss > -10% | Stable |
| **Rug Containment** | 1 rug at -12% | No rugs > -15% | All exits above hard floor | Any hard floor hit | N/A |
| **Candidates/Cycle** | 0 | >0 on some cycles | Market waking up | Still frozen | — |

### Decision Matrix for Wednesday
- **If trade count >= 10 AND PF >= 1.3:** System is demonstrating. Stay the course. Stoic Gate continues.
- **If trade count >= 10 AND PF < 1.0:** System has negative expectancy. Begin diagnostic (exit reasons, entry quality). Still no tuning until 20.
- **If trade count < 8 (market dead):** Pivot discussion — consider extending decision window to April 6-7, OR begin dispatcher architecture work in parallel (productive use of dead market time).
- **If any loss > -15% (hard floor breach):** Emergency review of exit chain. This would be the only scenario that triggers a code change before Stoic Gate.

### What Constitutes "Enough Data" for Wednesday
The Stoic Gate (20 trades) remains the hard requirement for any parameter changes. Wednesday's checkpoint is about trajectory and system health, NOT about making tuning decisions. We're asking "is the system behaving correctly?" not "should we change settings?"

---

## Daily Log

### Day 1 — 2026-03-30 (corrected after epoch format fix)
- Trades: 3 | Wins: 1 | Losses: 2 | WR: 33.3% | PF: 4.61
- Net PnL: +$344.26 (+3.44%) | Avg Win: +29.59% | Avg Loss: -3.18%
- Notes: Baseline corrected — original 7-trade count included pre-epoch leaked trades from T-vs-space bug. System running clean. No tuning allowed (Stoic Gate active). Market in Extreme Fear (F&G: 8), low trade frequency expected.

### Day 2 — 2026-03-31
- Cumulative Trades: 6 | Wins: 1 | Losses: 5 | WR: 16.7% | PF: 1.20
- New Today: 3 trades (ANIME -12.05% emergency_rug, BULL -2.61% sniper_timeout, USDT -3.57% sniper_timeout)
- Net PnL: +$63.36 (+0.63% of $10k) | Virtual Balance: $10,063.36
- Notes: PF dropped from 4.61→1.20 as predicted at small sample size. ANIME rug was contained by emergency detector (-12% vs v2's -17%+). Zero candidates today — market still frozen, filter correctly rejecting all 200 scanned tokens. Stoic Gate at 6/20. **Tuning decision: NO CHANGE.** See `MD/trades/Tuning_Decision_2026-03-31.md` for full rationale.
- Data integrity note: Epoch query still leaks 2 pre-v3.1 trades (ai, BRUH) due to T-format timestamps in old records. Non-critical — affects reporting queries only, not bot behavior. Tracked for cleanup.

### Day 3 — 2026-04-01 (WEDNESDAY CHECKPOINT)
- Cumulative Trades: 7 | Wins: 2 | Losses: 5 | WR: 28.6% | PF: 1.42
- New Today: 1 trade (IRAN +6.29% timeout)
- Net PnL: +$158.26 (+1.58% of $10k) | Virtual Balance: ~$10,158
- Cohort Analysis: NO EFFECT verdict (no tuning was made, variance is noise at n=3 vs n=4)
- Stoic Gate: 7/20 (35%) — BEHIND PACE. At 2.3 trades/day, projected ~April 6-7.

**Wednesday Decision Matrix Result:** Trade count < 8 (market dead) → **EXTEND decision window to April 7.**

**Trend Assessment: AT RISK**
- PF recovered slightly (1.20 → 1.42) thanks to IRAN win, but still below 1.5 target
- Win rate improved (16.7% → 28.6%) — 2nd win is a healthy signal
- Trade frequency declining: Day 1 had 3, Day 2 had 3, Day 3 has 1 so far
- Market still frozen — zero candidates on most scan cycles
- No bugs, no hard floor breaches, no system failures
- Exit chain performing correctly across all 5 exit types triggered

**Key signals:**
1. PF trajectory: 4.61 → 1.20 → 1.42 (stabilizing around break-even after initial CLOWN outlier faded)
2. Loss containment holding: avg loss -4.66% (well within -8% SL), no hard floor hits
3. Emergency rug detector proven: ANIME caught at -12% (v2 would have been -17%+)
4. Sniper timeout doing its job: 3 non-runners cut at avg -2.51%
5. 1 profitable timeout exit (IRAN +6.29%) shows the system can hold moderate winners

**Recommendation:** Extend decision window to April 7. Continue paper validation. Begin dispatcher architecture build in parallel (productive use of dead market time). No tuning until Stoic Gate clears.

See `MD/trades/Cohort_Analysis_2026-04-01.md` for full statistical breakdown.

### Day 4 — 2026-04-01 (actual) / 2026-04-02 (calendar)
- Cumulative Trades: 7 | Wins: 2 | Losses: 5 | WR: 28.6% | PF: 1.42
- New Today: 0 trades — market completely frozen, zero candidates passing filters
- Net PnL: +$158.26 (+1.58% of $10k) | Virtual Balance: $10,158.26
- Stoic Gate: 7/20 (35%) — NO PROGRESS since Day 3

**Trend Assessment: AT RISK (unchanged)**
- Zero new trades in 10+ hours — market is dead, not the bot
- PF holds at 1.42 (below 1.5 target but positive expectancy)
- No bugs, no crashes, no hard floor breaches — system is healthy
- Lazarus is scanning every cycle and correctly rejecting everything
- Trade frequency declining: 3 → 3 → 1 → 0 per day

**Stoic Gate Projection (revised):**
- 7/20 after ~58 hours of runtime = 2.9 trades/day average
- But trend is decelerating: actual last-24h rate = 0 trades/day
- Optimistic: market thaws, 3+/day returns → April 5-6
- Realistic: current freeze continues → April 7-8
- Pessimistic: extended freeze → may need to revisit April 7 decision date

**Cohort Analysis: NOT APPLICABLE**
- No tuning was made between checkpoints
- No new trades generated to compare against
- Dataset is identical to Day 3 — n=7, PF=1.42, WR=28.6%

**Block 1 Verdict: NO NEW DATA — market frozen, system healthy**

**Exit Reason Health Check (cumulative):**
- sniper_timeout: 3 trades, avg -2.51% — working correctly, cutting non-runners
- stale_timeout: 1 trade, avg -5.00% — contained
- emergency_rug: 1 trade, avg -12.05% — caught ANIME, v2 would have been -17%+
- take_profit: 1 trade, +29.59% — CLOWN hit TP, strong
- timeout: 1 trade, +6.29% — IRAN held to max_hold profitably

**Recommendation:** No action. Market is the bottleneck, not the system. Continue paper validation. Dispatcher build proceeding in parallel.

### Day 5 — 2026-04-03 (original decision day)
- Trades: — | Wins: — | Losses: — | WR: — | PF: —
- Notes: (pending — decision window extended to April 7)

### Day 6 — 2026-04-04
- Trades: — | Wins: — | Losses: — | WR: — | PF: —
- Notes: (pending)

### Day 7 — 2026-04-05
- Trades: — | Wins: — | Losses: — | WR: — | PF: —
- Notes: (pending)

### Day 8 — 2026-04-06
- Trades: — | Wins: — | Losses: — | WR: — | PF: —
- Notes: (pending)

### Day 9 — 2026-04-08 (Cloud Run deployment day)
- Paper trading paused on VPS for Cloud Run validation sprints.
- Cloud Run deploy verified: revision lazarus-00013-2nf, 4.84s cold start, DexScreener scanning confirmed.
- /health endpoint built and tested (fail-closed with DB + process checks).
- Environment hardened: Secret Manager audit, PAPER_TRADING bridge fix (TD-007), HELIUS_API_KEY secret created.
- Entrypoint.sh expanded to bridge all EnvLoader vars.
- Deploy pipeline documented: `docs/DEPLOY_PIPELINE.md`
- Scaled to min-instances=0 after verification (cost control).
- **Go-live tracker note:** Cloud Run is a Tier 2 portfolio credential, not the go-live target. VPS remains primary for go-live decision. Stoic Gate status unchanged (last reading: 7/20 trades, PF 1.42).

### Day 10 — 2026-04-16 (Tracker reset, not a decision)
- Decision window status: **LAPSED**. No valid GO / NO-GO was recorded on April 7.
- Gap acknowledgment: April 8-14 focused on Cloud Run, Cloud SQL, and health-check work; those are portfolio and platform milestones, not paper-trading decision evidence.
- Market-state acknowledgment: April 15-16 logs show the scanner was alive but starved, which motivated the proposed `v3.2_lowvol_epoch` experiment.
- New decision date: **not set yet**. It will be assigned only after the server reality check runs on the repo-safe legacy query pack.
- Cohort-of-record rule: future decision metrics must cite one regime or inferred cohort explicitly; mixed-regime summaries are diagnostic only.

### Day 10 — 2026-04-16 (Server reality check, authoritative)

Read-only verification was run against a copied production SQLite DB file created from `/home/solbot/lazarus/logs/lazarus.db`. Schema probe confirmed `trades.side` and `trades.filter_regime` both exist on the server copy.

Authoritative post-epoch paper-mode result:
- 25 sells since `2026-03-29T17:44:00`
- Gross profit: $1239.15
- Gross loss: $815.14
- Profit factor: **1.520**
- Net PnL: $424.01
- Avg PnL: 1.74%
- Win rate: 36.0%

This resolves the prior contradiction:
- Tracker value "7 / PF 1.42" was stale / incorrect
- Memory value "25 / PF 1.73" was partially correct on trade count but incorrect on profit factor (most likely a drifted recollection of the 1.74% average PnL)

**Status:** Stoic Gate count threshold is confirmed cleared on production evidence. Any future decision note must cite PF 1.520, not 1.73.

### Day 10 — 2026-04-16 (Cohort-level Stoic Gate outcome, decision-grade)

The aggregate post-epoch result (25 sells / PF 1.520) cleared the Stoic Gate count threshold, but cohort decomposition on the same copied DB shows the aggregate is being carried by one regime, not earned evenly.

Cohort-level result from `/home/solbot/lazarus/logs/lazarus_phase6_readonly.db`:

| Cohort | Sells | PF | Net PnL | Avg PnL | WR | Confidence band |
|---|---|---|---|---|---|---|
| `original` | 10 | **2.18** | +$443.82 | 3.95% | 50.0% | Decision-grade (≥5-sell rule) |
| `wide_net_v1` | 15 | **0.955** | -$19.81 | 0.27% | 26.7% | Decision-grade (≥5-sell rule) |
| `v3.2_lowvol_epoch` | 0 | — | — | — | — | Unvalidated — zero production evidence |

Exit-reason distribution confirms the asymmetry:
- `original` take-profits landed 2 sells for +$710.41 (28.42% avg). Losses are concentrated in `sniper_timeout` (5 sells, -$99.50) and one `emergency_rug` (-$187.00).
- `wide_net_v1` `sniper_timeout` dominates: 10 sells for -$259.02. The single take-profit (+$314.27) does not offset accumulated losses.

**Interpretation:**
- The "Stoic Gate cleared" framing from the aggregate is true in the count-only sense but not in the decision-grade sense. The aggregate is carried by `original`.
- `original` looks genuinely promising (PF 2.18, WR 50.0%) but with only 10 sells is **below the 20-sell gate** if treated as the cohort-of-record. More evidence is needed before the gate clears on the right cohort.
- `wide_net_v1` is **formally rejected for go-live purposes** on this evidence. It remains permitted in paper mode only as a negative-control cohort and regime-detection signal. Reinstatement as a go-live candidate requires a new sprint decision — it cannot be reinstated by running totals alone and cannot be reinstated implicitly by being left in the default config.
- `v3.2_lowvol_epoch` remains unvalidated — zero production-evidence trades. It is held as a starvation fallback, not a co-equal primary.

**Decision:**
- No go-live date is being set on this evidence.
- Sprint 7 (cohort-of-record evidence, paper-mode) opens 2026-04-16 with runtime-truth-first discipline.
- Primary cohort-of-record: `original`. Secondary / shadow: `v3.2_lowvol_epoch`, held as a starvation fallback.
- Gate order: (7A) runtime truth verification before any evidence counts; (7B) 20-sell / PF ≥ 1.5 gate on `original`; (7C) fallback promotion of `v3.2_lowvol_epoch` only on ≥24h starvation.
- Interim operational-integrity checkpoint: **2026-04-20**.
- Decision-review date: **2026-04-23**. This is explicitly a decision-review date, not a go-live date. Sprint 7 does not close by silent fade — only by explicit decision recorded in the charter.

Authoritative records: `github-repo/docs/sprints/PHASE_6_EXECUTION_LOG.md` (aggregate and cohort queries, Step 5), commit `0e67552` (aggregate reconciliation), forthcoming Phase 6 cohort close-out commit, and `github-repo/docs/sprints/SPRINT_7_COHORT_EVIDENCE.md` (Sprint 7 charter).

### Day 10 addendum - 2026-04-16 Gate 7A execution status

**Gate 7A status: `startup parity restored; tagged-trade verification pending`.**

Blocker class: operational integrity (deployment parity), not strategy quality. Full execution narrative - failure evidence, deploy-drift diagnosis, sync-over-hotfix decision, parity restoration - is recorded in `docs/sprints/SPRINT_7_EXECUTION_LOG.md`.

- **Pre-sync state:** Restart with `bot_config` set to `original` produced a banner advertising `chg 10.0-100.0% | liq >$30,000`. Runtime did not match DB intent.
- **Root cause:** VPS runtime drift. `/home/solbot/lazarus/lazarus.py` lacked `apply_startup_config_overrides`; `/home/solbot/lazarus/startup_config.py` was missing; deployed `record_trade()` did not write `filter_regime`.
- **Remediation:** Full runtime sync of `/home/solbot/lazarus/lazarus.py` and `/home/solbot/lazarus/startup_config.py` from `codex/stabilize-20260416`. Backup at `/home/solbot/lazarus/backup_runtime_sync_20260416_181311`. `config_defaults.py` was not deployed to the VPS runtime path - repo/default alignment is a separate repo concern.
- **Post-sync state:** Startup banner now reports `Filters: vol >=400 | chg 10.0-80.0% | liq >$50,000 | regime original`. Five of six Gate 7A checks pass.
- **Sprint 7 evidence cutoff:** `2026-04-16 18:13:33 UTC`. No sells before that timestamp count toward Gate 7B.
- **Residual closure condition:** First post-restart trade row after `2026-04-16 18:13:33 UTC` must carry `filter_regime = 'original'`. Until that row exists, Gate 7B remains paused and no sells count toward the 20-sell cohort-of-record target.

### DECISION DAY — 2026-04-07 (extended from April 3)
- Final Trades: — | Final WR: — | Final PF: —
- **GO / NO-GO:** Lapsed without recorded decision
- Rationale: The calendar date passed before the tracker was reconciled with later claims, and no final server-side reality check was captured on disk.

---

## Go-Live Gate Checklist

### Metrics Gate (must all pass)
- [ ] Profit Factor >= 1.5 across 20+ trades
- [ ] Execution latency < 200ms (baseline: ~1ms)
- [ ] Stop-loss slippage < 2% (v2 was -17.23%)
- [ ] Filter rejection rate 96-98%
- [ ] No critical bugs in 4-day window
- [ ] Learning engine stable (Stoic Gate = no tuning until 20 trades)

### Josh's Gut Check (final authority)
- [ ] Does the data feel right? Any patterns that concern you beyond the numbers?
- [ ] Are you comfortable risking real capital (~$103) based on what you've seen?
- [ ] If PF is close (1.3-1.5): consider conditional go-live with tighter limits (smaller position, lower daily loss cap)

**Decision rule:** Metrics must pass first. If they do, Josh makes the final human call. If metrics fail, it's an automatic NO-GO regardless of gut feel. If metrics pass but gut says no, we don't go — trust the instinct and investigate what's bothering you.

---

*Tracker maintained by TPM Meta-Persona. Updated at decision checkpoints and evidence resets.*
*QA Validation Architect signs off on metric trustworthiness before Go-Live.*

---

### Day 11 — 2026-04-24 — Sprint 7 restart event and Gate 7A verdict under strict charter

- **Runtime event:** Lazarus restarted cleanly at `2026-04-24 06:17:16 UTC`. Clean systemd shutdown; no crash, no OOM. `fail2ban-client: Shutdown successful` at `06:17:17 UTC` suggests a system-level event; `unattended-upgrades` is a plausible inference but is not directly logged in the inspected window.
- **Gate 7A cutoff:** resets per charter §150. New cutoff of record: `2026-04-24 06:17:16 UTC`. The prior `2026-04-16 18:13:33 UTC` cutoff is retired.
- **Audit-gap note:** no checkpoint entries were made between 2026-04-17 and 2026-04-24 (~8 days). The gap is acknowledged, not reconstructed.
- **Six-check scorecard under strict charter:**
  - Check 1 (bot_config) — **PASS**: 7/7 keys match `original` (`min_hourly_vol=400`, `min_chg_pct=10.0`, `max_chg_pct=80.0`, `min_liq=50000`, `min_vmr=0.10`, `cooldown_seconds=7200`, `filter_regime=original`).
  - Check 2 (dynamic_config) — **PASS**: SELECT on the seven gate keys returned zero rows; only `position_pct=0.15` and `stop_loss=0.94` are present (outside the filter set).
  - Check 3 (deployed `lazarus.py` CFG literal) — **FAIL**: 4 of 7 keys still at `v3.2_lowvol_epoch` values on deployed `/home/solbot/lazarus/lazarus.py` (vol 250, chg 120.0, liq 30_000, regime `v3.2_lowvol_epoch`). `apply_startup_config_overrides` masks the drift at runtime but does not satisfy the charter's code-layer check.
  - Check 4 (`config_defaults.py` DEFAULTS) — **FAIL**: no `config_defaults.py` and no `.git` working tree found on the searched `/home/solbot` server surface.
  - Check 5 (startup banner / runtime re-logs) — **PASS**: banner plus 26 `Runtime filters:` lines (initial line plus 25 re-log samples) all show `original` with no drift.
  - Check 6 (first post-restart trade tagged `filter_regime='original'`) — **PENDING**: zero post-`06:17:16 UTC` trade rows.
- **Verdict:** Gate 7A does not close. Two checks FAIL on code-layer alignment; one remains PENDING on the first tagged trade. Sprint 7 stays open; Gate 7B evidence collection remains paused; no sells count toward the 20-sell cohort-of-record target.
- **Strict-charter adjudication:** the charter-vs-execution-log contradiction on Check 3/4 scope was resolved in favor of the charter. See `docs/sprints/SPRINT_7_EXECUTION_LOG.md` under the `Strict-charter adjudication - 2026-04-24` section for the full ruling.
- **Next actions (tracked separately):** (1) align deployed `lazarus.py` CFG literal to `original`; (2) port `config_defaults.py` onto the server working tree; (3) wait for the first post-`06:17:16 UTC` trade row and verify its `filter_regime` tag.
- **Evidence location:** `docs/sprints/SPRINT_7_EXECUTION_LOG.md` under `Gate 7A.F4.R1` and `Gate 7A.F4.R1.V1`.
- **Next tracker edit:** Sprint 7 close-out only.
