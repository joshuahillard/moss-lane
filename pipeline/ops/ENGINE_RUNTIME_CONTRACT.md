# Engine Runtime Contract

## What This Page Is

This page defines the current runtime contract for Lazarus. It is not a line-by-line code explainer. It describes the operating states the engine is allowed to enter, the conditions that trigger those states, and the safeguards that must hold before the engine continues.

## Runtime Loop Contract

The documented runtime loop is:

1. fetch balance or operating capital context
2. check daily loss limit
3. check broader market safety
4. check self-regulation pause state
5. check slot availability
6. scan for candidates
7. execute eligible candidates
8. monitor open positions through the exit chain
9. periodically run learning/anomaly logic

## Allowed Runtime States

### `scan_active`

The engine may scan and evaluate candidates.

### `scan_paused_daily_loss`

The engine must stop opening new positions when the daily-loss rule is breached under the current mode's accounting.

### `scan_paused_market`

The engine must stop opening new positions when broader crash logic activates.

### `scan_paused_self_regulation`

The engine must stop opening new positions when self-regulation requires a pause.

### `position_monitoring`

Once in a trade, the engine must continue monitoring under the exit-chain contract until exit conditions resolve the position.

### `learning_review`

Periodic learning and anomaly logic may run, but only inside bounded authority.

## Exit-Chain Contract

The current documented priority order is:

1. hard floor
2. emergency rug
3. take profit
4. trailing stop
5. sniper timeout
6. stop loss
7. timeout

Contract rule:

- higher-priority exits preempt lower-priority exits when both are true

This rule is one of the most important runtime invariants in Moss Lane because it turns exit behavior into something deterministic and explainable.

## Learning Contract

The learning engine may:

- analyze recent valid trades
- suggest bounded parameter changes
- write approved values into `dynamic_config`

The learning engine may not:

- bypass epoch gating
- write out-of-bounds values
- decide go-live
- silently redefine the active strategic regime

## Mode Contract

### Paper mode

Requirements:

- use virtual-capital accounting where the logic depends on capital size
- preserve paper/live distinction in claims and reports

### Live mode

Requirements:

- use real-capital accounting
- keep the same bounded safety logic
- maintain clearer operator observability because losses are real

## Deployment Contract

Any server-side patch should preserve the project's documented deploy discipline:

- backup first
- patch surgically
- compile or syntax-check
- restart service
- health-check
- rollback on failure

This contract matters because runtime trust depends on being able to reverse bad changes quickly.

## Runtime Gaps to Track

- regime-aware learning is not yet documented as fully closed
- real-time alerting is still light for a future live mode
- local test collection is not yet a clean one-command proof

These are not reasons to dismiss the current architecture. They are reasons to keep the contract explicit.
