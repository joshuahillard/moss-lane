# Build Log: Validating the Guardrail Pattern (The CLOWN Trade)

**Date:** 2026-03-30
**Author:** Josh Hillard
**System:** Lazarus v3.1 (Paper Mode, $10K Virtual Capital)
**Status:** Validated

---

## The Context

In the legacy v2 architecture, the system frequently bought "topped-out" tokens already up 100–700% and suffered a fatal -17.23% average slippage due to slow execution loops and unbounded entry filters. Post-mortems revealed five root causes: no hourly change ceiling, no per-token cooldown, a learning engine that poisoned its own position sizing, a self-regulation module that entered a death spiral on low win rates, and a sell-side bug that used SOL lamports instead of token output amounts.

The v3 rewrite was designed to eliminate all five by implementing a strict 9-point filter cascade (pair age, market cap floor/ceiling, liquidity floor, hourly change window 10–80%, 5-minute momentum floor, volume-to-MC ratio, blacklist check, cooldown gate, daily loss limit) and a 3-second I/O-multiplexed monitor loop feeding a deterministic 7-Tier Exit Priority Chain.

## The Execution

After 34 hours of rejecting hundreds of tokens in a quiet weekend market — including a correctly rejected ANIME token (chg1h = 9.7%, below the 10% floor) — the scanner identified the CLOWN token on DexScreener at 04:04:50 UTC on 2026-03-30.

**Filter cascade results at scan time:**

| Filter | Threshold | CLOWN Value | Result |
|--------|-----------|-------------|--------|
| Hourly Change Window | 10–80% | 46.31% | PASS (mid-window sweet spot) |
| Liquidity Floor | $50,000 | $58,081 | PASS |
| Market Cap Range | $10K–$10M | $507,340 | PASS |
| 5-Min Momentum | > +0.5% | Positive | PASS |
| JIT Final Gate (live re-check) | ≥ 10% chg1h | 45.6% | PASS |

Gate-to-execute latency: approximately 1 millisecond. The system committed capital within one monitor cycle of signal confirmation.

## The Result

The 7-Tier Exit Priority Chain evaluated the position state every 3 seconds. Here is what the state machine processed in real time:

| Time (UTC) | Elapsed | Price | PnL | Chain Evaluation |
|------------|---------|-------|-----|------------------|
| 04:04:50 | 0s | $0.0005073 | 0.0% | BUY executed |
| 04:05:25 | 35s | $0.0005566 | +9.7% | Tier 4 (Trail Stop) ARMED at +9.7% — threshold was +8% |
| 04:06:25 | 94s | $0.0006574 | +29.6% | Tier 3 (Take Profit) FIRED at +29.6% — threshold was +25% |

**The critical architectural detail:** Two exit conditions were simultaneously active — the armed Trail Stop (Tier 4, tracking 4% below peak) and the Take Profit threshold (Tier 3, fixed at +25%). Because the priority chain evaluates in strict numerical order on every 3-second cycle, Tier 3 always preempts Tier 4. The moment the position crossed +25%, Take Profit fired and the trail stop never triggered.

This is not incidental. The priority ordering is a deliberate design decision: Take Profit is a guaranteed capture at a known threshold, while Trail Stop is a dynamic approximation that can give back gains in volatile conditions. By placing TP higher in the chain, the system enforces a "bird in the hand" principle — when a position reaches the hard target, it locks the gain unconditionally rather than gambling on further upside through a trailing mechanism.

**Outcome:** +29.59% / +$439.53 in 94 seconds. Trail armed correctly, TP preempted correctly, priority chain validated.

## The Broader Validation

This single trade validated three architectural hypotheses simultaneously:

**Hypothesis 1 — The Guardrail Pattern works.** The 9-point filter cascade rejected hundreds of tokens over 34 hours (including a confirmed ANIME rejection at 9.7% chg1h). When CLOWN arrived at 46.31% hourly change — perfectly centered in the 10–80% target window — the system identified it instantly and executed within 1ms of gate clearance. The architecture is designed to be ruthlessly selective: reject 98% of market noise, then execute decisively on the 2% that pass every filter.

**Hypothesis 2 — The 7-Tier Exit Priority Chain is deterministic.** Two exit conditions competed (Trail Stop armed at +9.7%, Take Profit threshold at +25%). The chain resolved correctly: Tier 3 preempted Tier 4 because the evaluation loop checks conditions in strict priority order every 3 seconds. No ambiguity, no race condition, no manual intervention. The state machine produced the mathematically optimal outcome.

**Hypothesis 3 — One bounded winner erases controlled losses.** The post-epoch trade set tells the full story:

| Trade | Exit Reason | PnL | Exit Tier |
|-------|-------------|-----|-----------|
| Clippy | stale_timeout (price feed failure) | -$75.00 | Special (outside chain) |
| CAT | sniper_timeout (non-runner cut at 63s) | -$20.27 | Tier 5 |
| CLOWN | take_profit (deterministic TP) | +$439.53 | Tier 3 |
| **Net** | | **+$344.26** | **Profit Factor: 4.62** |

The two losses were architecturally bounded: Clippy was a price-feed failure capped at -5% by the stale penalty, and CAT was a non-runner sniped at -1.36% after 63 seconds by the Tier 5 sniper exit. Neither loss was a surprise or an uncontrolled drawdown. The system's risk boundaries held on every trade.

## The TPM Lesson

Lazarus is a risk engine that occasionally trades, not a trading engine that occasionally manages risk. The Guardrail Pattern enforces strict architectural boundaries at every stage: entry filters reject noise, the JIT Final Gate re-validates at the millisecond of execution, and the 7-Tier Exit Priority Chain deterministically manages every position from open to close.

The result is a system where losses are bounded by design (sniper exits, stop losses, hard floors) and wins are captured by a priority-ordered state machine that selects the mathematically optimal exit condition on every evaluation cycle. When the right signal finally breaches the gates, the architecture manages the momentum — not the operator.

This is the core principle: you do not need to predict the market. You need to engineer boundaries tight enough that when randomness delivers a runner, your system captures it deterministically. CLOWN was not luck. CLOWN was the architecture working exactly as designed.

---

**Technical Artifacts:**
- Full autopsy report: `Trade_Autopsy_2026-03-30.pdf`
- Exit chain source: `lazarus.py`, lines 934–970 (`_monitor_position()`)
- Filter cascade source: `lazarus.py`, CFG dict lines 108–166

**Open Items:**
- ~~Epoch gate T-vs-space timestamp format bug (discovered during this autopsy, fix pending)~~ **RESOLVED** — see below
- Scan-to-gate latency not instrumented (only gate-to-execute measured at ~1ms)
- Trade count: 3/20 toward Stoic Gate threshold — no logic changes until 20 reached

---

## Addendum: Epoch Gate Data Leak — Discovery & Fix

**Date:** 2026-03-30 12:17 UTC
**Severity:** HIGH — affected data integrity across learning engine and self-regulation
**Status:** RESOLVED

### The Bug

During the trade autopsy, the QA persona flagged that a `WHERE timestamp >= '2026-03-29 17:44:00'` query returned 5 trades instead of the expected 3. Two pre-epoch trades (ai at 03:43 UTC, BRUH at 06:10 UTC) leaked through — both were stale_timeout losers from pre-v3.1 code.

### Root Cause

A timestamp format mismatch between the database and the epoch string. The DB writes ISO 8601 timestamps with a `T` separator (`2026-03-29T03:43:37`), but the epoch was stored with a space separator (`2026-03-29 17:44:00`). In ASCII, `T` (0x54) is greater than space (0x20), so SQLite string comparison evaluated `2026-03-29T03:43:37 >= 2026-03-29 17:44:00` as TRUE — even though 03:43 is 14 hours *before* the 17:44 epoch.

This is a textbook example of implicit type coercion in string-based datetime comparisons. SQLite has no native datetime type; it relies on consistent string formatting for correct lexicographic ordering.

### Impact

The learning engine (`learning_engine.py`) and self-regulation module (`self_regulation.py`) were both evaluating pre-v3.1 trades in their decision windows. Both leaked trades were stale_timeout exits with -5.0% PnL from the old 0.95 stale penalty — artificially depressing the system's performance metrics and potentially influencing regime evaluations.

The paper balance calculation in `lazarus.py` (2 occurrences) was also affected, summing pre-epoch PnL into the running virtual balance.

### The Fix

Surgical string replacement across 3 files, 4 locations:

| File | Line | Old Value | New Value |
|------|------|-----------|-----------|
| `learning_engine.py` | 21 | `V3_EPOCH = "2026-03-29 17:44:00"` | `V3_EPOCH = "2026-03-29T17:44:00"` |
| `self_regulation.py` | 27 | `V3_EPOCH = "2026-03-29 17:44:00"` | `V3_EPOCH = "2026-03-29T17:44:00"` |
| `lazarus.py` | 1190 | `timestamp >= '2026-03-29 17:44:00'` | `timestamp >= '2026-03-29T17:44:00'` |
| `lazarus.py` | 1206 | `timestamp >= '2026-03-29 17:44:00'` | `timestamp >= '2026-03-29T17:44:00'` |

All 3 files passed `py_compile` verification. Service restarted cleanly at 12:17 UTC.

### The TPM Lesson

This bug was invisible in normal operation — Lazarus kept trading, kept logging, kept running. It only surfaced under forensic analysis when the QA persona enforced epoch gating on the raw trade data and counted discrepancies. The fix was a 4-character change (`T` replacing a space) in 4 locations, but the diagnostic process that found it — cross-referencing SQL output against log timestamps, understanding ASCII ordering in SQLite string comparisons — is the kind of systems thinking that separates "it works" from "it works correctly." In production systems at scale, these silent data integrity bugs are the ones that compound into catastrophic drift.
