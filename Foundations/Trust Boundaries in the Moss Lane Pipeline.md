# Trust Boundaries in the Moss Lane Pipeline

## What This Page Is

This page explains the major trust boundaries in Moss Lane. A trust boundary is any point where information crosses from a lower-confidence zone into a higher-authority zone and must be checked before the system continues.

In Moss Lane, those boundaries are not limited to code execution. They also exist between:

- market data and trade decisions
- database state and learning behavior
- documented evidence and strategic claims
- built modules and deployed capability

## Why Moss Lane Needs Multiple Boundaries

The project has already seen several categories of drift:

- stale database config overriding newer code
- timestamp-format mismatches leaking bad rows into analysis
- query anti-patterns turning every trade into a false match
- paper-mode risk math using real-wallet capital

These were not failures of ambition. They were failures at boundaries.

## Boundary 1: External Data Ingestion

Inputs:

- DexScreener
- Birdeye
- Helius RPC
- Jupiter

Assumptions that must not be made:

- that responses are complete
- that timing is stable
- that stale data is still decision-safe

Required posture:

- treat every response as useful but untrusted
- re-check critical trade data at execution time
- prefer fail-closed rejection over speculative acceptance

## Boundary 2: Query and Time-Window Selection

This is one of the most important boundaries in the entire project because so many decisions depend on "the right subset of trades."

What must be validated:

- timestamp comparisons use consistent ISO text behavior
- epoch scoping is explicit
- known-dangerous patterns such as `strftime('%s')` are rejected

Current evidence:

- this boundary is now represented directly in `src/data/data_integrity.py`

Why it matters:

- when this boundary failed, learning and reporting both became untrustworthy

## Boundary 3: Runtime Configuration

Three config layers exist in the documented Lazarus architecture:

- code defaults
- `bot_config`
- `dynamic_config`

This means config presence is not enough. The system must validate:

- which layer currently wins
- whether the resulting values are sane
- whether the values belong to the current regime and mode

This boundary is critical because stale config can silently defeat a correct deployment.

## Boundary 4: Learning Input

The learning engine should never treat "all recent trades" as automatically valid input.

It must validate:

- epoch scope
- minimum sample size
- field completeness
- regime relevance when regime-specific decisions are being made

Current state:

- epoch, Stoic Gate, and completeness have explicit validation support
- filter-regime-aware learning is still a documented next-step concern rather than a clearly finished control

## Boundary 5: Learning Output

Adaptive systems are risky when they can write directly into operational state.

What must be checked:

- keys are allowed
- values are numeric and sane
- values stay inside hard bounds

Current state:

- this boundary is materially implemented via config-write validation

## Boundary 6: Paper vs. Live Capital Logic

Mode changes are a trust boundary because the same trade logic is not the same risk logic.

What must be checked:

- paper mode uses virtual-capital accounting
- live mode uses real-capital accounting
- daily-loss calculations use the correct denominator
- readiness claims are explicit about which mode produced them

This boundary already produced one meaningful fix and therefore deserves first-class status in the documentation.

## Boundary 7: Deployment Truth

There is a difference between:

- code in the repo
- code deployed on the server
- code verified in runtime

Moss Lane currently contains modules in all three categories. This boundary should stop the project from overstating what is active.

Required rule:

- a capability is only "operational" after deployment and verification, not after code completion alone

## Boundary 8: Strategic Decision-Making

This is where human review matters most.

Examples of decisions that cross this boundary:

- whether wide-net evidence justifies future live settings
- whether VPS-first or GCP-first is the right next move
- whether the dispatcher should stay feature-flagged
- whether live trading should wait for alerts and regime-aware learning

These are not pure code questions. They are judgment questions informed by code and evidence.

## Boundary 9: Local Test Interpretation

Tests are a boundary between "this should work" and "this ran in this environment."

Current validated gap:

- `pytest` does not cleanly collect because `tests/unit/test_foundation.py` exits the process
- the local environment used here is missing at least `solders`, `base58`, and server-style secrets for that script

That means the codebase has test assets, but local test confidence is conditional rather than universal.

## Design Principle

At each boundary, Moss Lane should prefer one of three responses:

- validate and continue
- reject or pause
- escalate to human review

What it should not do is continue silently under ambiguity.
