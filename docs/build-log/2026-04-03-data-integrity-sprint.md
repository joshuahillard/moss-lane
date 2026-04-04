# Build Log: Data Integrity Sprint — 5-Layer Protection System

**Date:** 2026-04-03
**Author:** Josh Hillard + Claude (Opus 4.6)
**System:** Lazarus v3.1 (Paper Mode, $10K Virtual Capital)
**Status:** Deployed to production

---

## The Context

Between 2026-03-28 and 2026-04-03, four distinct data integrity incidents exposed a shared vulnerability class: data from the wrong time period, in the wrong format, or with the wrong bounds was reaching decision-making code without validation. Each incident was caught and fixed individually, but the fixes were point solutions — patching the specific query or the specific function that broke, without addressing the systemic pattern.

The incidents:

| Incident | Date | Impact | Root Cause |
|----------|------|--------|------------|
| DB Config Override | 2026-03-28 | Bot ran 8 hours with stale v2 config, 0 candidates found | Code updated but bot_config DB table still had v2 values |
| Ghost Trade Bug | 2026-03-29 | Learning engine poisoned by stale v2 data, self-regulation death spiral | No MIN_TRADES gate, no epoch filter on learning input |
| Epoch Format Mismatch | 2026-03-30 | 2 pre-epoch trades leaked into learning engine | T-format vs space-format ISO string comparison mismatch |
| Epoch Query Data Leak | 2026-04-03 | ALL 179 trades passed epoch filter instead of 25 | `strftime('%s',...)` returned unix integers that always string-compared TRUE against ISO text |

The common thread: **no validation layer existed between data sources and decision logic**. The learning engine trusted whatever the DB returned. The startup sequence trusted whatever config was present. Queries trusted whatever comparison operator the developer chose. Every incident was a case of garbage-in with no gate to catch it.

## The Design

The sprint implemented a defense-in-depth model with five independent validation layers. Each layer is a pure function — no side effects, no network calls, no DB writes. Each returns a structured result: `{valid: bool, reason: str, details: dict}`. Every layer fails closed: if uncertain, reject.

```
Layer 5: Observability Alerts         (flags drift for human review)
Layer 4: Runtime Assertion Checks     (catches config drift at startup)
Layer 3: Dynamic Config Output Bounds (prevents parameter poisoning)
Layer 2: Learning Engine Input Gate   (epoch + Stoic Gate + completeness)
Layer 1: Query-Level Epoch Gating     (blocks strftime anti-pattern)
```

The layers are independent — if one fails or is unavailable, the others still operate. This is the same principle behind redundant safety systems in aviation: no single failure should compromise the system.

### Layer 1: Query-Level Epoch Gating

**Location:** `data_integrity.py` / called via `safe_epoch_query()` in `lazarus.py`

Scans SQL query strings for epoch comparison anti-patterns before execution. Specifically rejects:
- `strftime('%s', ...)` anywhere in a query (the root cause of the 2026-04-03 data leak)
- Bare unix integer comparisons against the ISO text timestamp column
- Queries touching the trades table without any timestamp filter

This is a static analysis gate. It does not execute the query — it inspects the query text and rejects known-dangerous patterns. The approach was chosen over runtime result validation because the strftime bug produced *plausible-looking* results (a superset of the correct data), making it impossible to detect from output alone.

### Layer 2: Learning Engine Input Validation

**Location:** `data_integrity.py` / called at the start of `analyze_and_tune()` in `learning_engine.py`

Validates the trade dataset before the learning engine evaluates it:
- **Stoic Gate**: Rejects if fewer than 20 valid trades (prevents premature regime changes from small samples)
- **Epoch Filter**: Rejects any trade with `timestamp < V31_EPOCH` (prevents pre-epoch data poisoning)
- **Completeness**: Rejects trades missing required fields (`pnl_pct`, `exit_reason`, `timestamp`)

If validation fails, the learning engine returns without evaluating — no writes to `dynamic_config`, no parameter changes. This directly prevents the Ghost Trade Bug pattern where stale data poisoned position sizing.

### Layer 3: Dynamic Config Output Bounds

**Location:** `data_integrity.py` / called inside `_set_config()` in `learning_engine.py`

Validates every proposed `dynamic_config` write against hard bounds before it reaches the database:

| Parameter | Min | Max |
|-----------|-----|-----|
| position_pct | 0.10 (10%) | 0.30 (30%) |
| stop_loss | 0.85 (-15%) | 0.96 (-4%) |
| take_profit | 1.10 (+10%) | 1.50 (+50%) |
| trail_arm | 1.04 (+4%) | 1.15 (+15%) |
| min_chg_pct | 3.0% | 50.0% |
| max_chg_pct | 50.0% | 200.0% |
| min_liq | $20,000 | $200,000 |

Also rejects: unknown keys, None values, NaN, Inf, type mismatches. This is defense-in-depth against the learning engine writing values that would cause outsized harm — even if Layer 2 is bypassed or the input data is partially compromised, the output is still bounded.

### Layer 4: Runtime Assertion Checks

**Location:** `data_integrity.py` / called at the start of `main()` in `lazarus.py`

Runs once at Lazarus startup, before any trades execute. Six checks:

1. `bot_config` has all required keys (catches the DB Config Override pattern)
2. `dynamic_config` values are within Layer 3 bounds
3. `dynamic_config` epoch is not stale
4. `stop_loss < take_profit` (sanity cross-check)
5. `position_pct` within 10-30% safe range
6. Configuration is internally consistent

**If any check fails, Lazarus exits with code 1.** This is a hard stop — the bot will not trade with bad config. The systemd service will attempt a restart, but the same assertion will fail again, preventing a loop of bad trades.

This is the layer that would have caught the 2026-03-28 DB Config Override Bug immediately instead of 8 hours later.

### Layer 5: Observability and Anomaly Detection

**Location:** `data_integrity.py` / called every 20 scan cycles in `lazarus.py`

Periodic drift detection that flags anomalies without auto-stopping:
- Win rate below 20% over last 10 trades
- Average PnL negative across 3 consecutive 5-trade windows
- All trades hitting the same exit reason (possible broken exit path)
- Extreme single-trade loss (> 50%)

This layer **logs warnings but does not halt trading**. The decision to pause or investigate belongs to the human operator (Josh). The layer's value is in surfacing patterns that would otherwise only be caught during manual DB inspection — converting reactive discovery into proactive alerting.

## The Hotfix: Paper Mode Daily Loss Limit

During deployment verification, a pre-existing bug surfaced: the daily loss limit check was dividing paper mode PnL ($412) by the real on-chain wallet balance ($2.57) instead of the $10K virtual capital. This produced a 16,035% loss figure against a 10% threshold, falsely pausing the bot.

**Fix:** Added `paper_capital_usd = 10_000` to CFG and used it as the denominator when `PAPER = True`. The actual daily loss was 4.1% of virtual capital — well under the 10% limit.

This is a good example of why the sprint's observability focus matters: the bug existed before this sprint, but was only noticed because the deployment forced a restart that surfaced it in logs.

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `data_integrity.py` | **NEW** — standalone validation module with all 5 layers | 280 |
| `learning_engine.py` | Added Layer 2 (input) + Layer 3 (output) integration | +30 |
| `lazarus.py` | Added Layer 1 (query) + Layer 4 (startup) + Layer 5 (anomaly) + paper capital fix | +82 |

Total: 1 new file, 2 modified files, ~392 lines added.

## Deployment

Deployed via `lazarus_deploy_data_integrity.sh` following the standard template:
1. SCP 3 Python files + deploy script to `/tmp/`
2. Backup existing files to `/home/solbot/lazarus/backup_data_integrity_5layer_20260403_235520/`
3. Copy, syntax check, import test
4. Restart service, 30-second health check
5. Startup assertions logged `PASSED` (6/6 checks)
6. Paper capital hotfix deployed separately with inline backup/restart

## Verification

**Startup assertions (from production logs):**
```
[STARTUP] All assertions passed (6 checks)
[STARTUP]   OK: bot_config has all required keys
[STARTUP]   OK: dynamic_config.position_pct=0.15 in bounds
[STARTUP]   OK: dynamic_config.stop_loss=0.94 in bounds
[STARTUP]   OK: dynamic_config epoch is current or not set
[STARTUP]   OK: stop_loss (0.94) < take_profit (1.25) — sane
[STARTUP]   OK: position_pct (0.15) within safe range
```

**Inline validation tests (all passed):**
- `strftime('%s',...)` query correctly rejected
- Direct text comparison query correctly accepted
- Out-of-bounds config write (3% position) correctly blocked
- In-bounds config write (15% position) correctly accepted
- Unknown key write correctly rejected
- Pre-epoch trades correctly filtered
- Stoic Gate correctly enforced at 20-trade minimum

## Interview Framing

This sprint demonstrates several patterns that map directly to enterprise infrastructure roles:

**Defense-in-depth validation architecture.** The 5-layer model mirrors how production financial systems handle data integrity — not with a single check, but with independent validation gates at every boundary. Each layer can be tested, deployed, and failed independently. This is the same principle behind circuit breakers in microservices and safety interlocks in trading systems.

**Fail-closed by default.** Every validation function defaults to rejection. This is the opposite of the "fail-open" pattern that caused the original incidents — where missing checks meant data flowed through unchallenged. In the context of a Stripe or Datadog interview, this maps to the principle that safety-critical systems must require explicit proof of correctness, not absence of proof of failure.

**Pure validation functions.** No layer has side effects. Each takes data in, returns a verdict. This makes them trivially testable, composable, and safe to add or remove without affecting system behavior. The pattern is borrowed from functional programming and applies directly to data pipeline validation at scale.

**Incident-driven design.** Every layer exists because a specific incident proved it was needed. The architecture is not speculative — it is a direct response to observed failure modes, with each layer mapped to the incident it prevents. This is the blameless postmortem loop in practice: incident occurs, root cause identified, systemic fix implemented, verification confirms coverage.
