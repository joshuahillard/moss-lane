# Program Management for Trading Infrastructure

## What This Page Is

This page explains how program management applies to Moss Lane as a trading-infrastructure project rather than a simple coding project. It translates the architecture, incidents, and sprint history into a delivery discipline that is specific to Lazarus and the surrounding Moss Lane portfolio.

For this project, PM is not an administrative wrapper around engineering. It is the mechanism that keeps the work honest:

- shipped vs. planned
- profitable vs. merely interesting
- deployable vs. portfolio-ready
- evidence-backed vs. aspirational

## Current Validated Baseline

As of April 7, 2026, the workspace supports the following baseline statements:

- the active code repo lives under `github-repo/`
- Lazarus v3.1 paper-mode architecture is documented and represented in the codebase
- the 5-layer data integrity system is implemented in `src/data/data_integrity.py`
- the project ledger and build logs record a clear incident-driven evolution from March 28 through April 4
- dispatcher, Whale Watcher, Docker, GCP, and Vertex AI work exist in the repo but are not yet evidenced as deployed runtime capability
- local test execution is not fully green: `pytest` is interrupted by `tests/unit/test_foundation.py` exiting during collection, and the local environment lacks at least `solders`, `base58`, and the server-side secrets expected by that script

The latest evidenced operational metrics in the workspace come from documents dated April 4, 2026 and report on data through April 3, 2026. That distinction matters. The repo is current as of April 7; the last checked-in operational snapshot is slightly older.

## Why PM Matters Here

Trading infrastructure fails when sequencing is sloppy.

Common failure patterns:

- strategy changes outrun the integrity layer
- portfolio-facing infrastructure work is mistaken for trading-readiness work
- built-but-undeployed modules create false confidence
- strong paper results are generalized beyond the filter regime that produced them
- delivery effort drifts toward breadth when the next real bottleneck is safety, observability, or proof

Program management prevents Moss Lane from becoming a collection of impressive artifacts that do not resolve the actual next decision.

## What the Program Is Actually Trying to Do

At the portfolio level, Moss Lane is proving that Josh Hillard can design, ship, and reason about real infrastructure under uncertainty.

At the product level, Lazarus is trying to become a trustworthy, bounded Solana momentum engine that can graduate from paper evidence to carefully governed live trading.

That means the program has two parallel obligations:

1. build the system well enough to operate safely
2. document and stage the work well enough that the journey itself is legible and defensible

Neither obligation can be ignored.

## Phase Model

### Phase 0: Inception

Goal:

- build a functioning autonomous trading engine while climbing the learning curve in Python, Linux, databases, APIs, and deployments

Evidence already present:

- README narrative
- project ledger Phase 0 entry
- v2 retrospective rooted in five failure modes

### Phase 1: Rewrite and Stabilization

Goal:

- replace the fragile v2 path with a cleaner v3 architecture

Evidence already present:

- `deploy_v3.sh`
- `src/engine/lazarus.py`
- `src/engine/learning_engine.py`
- `src/engine/self_regulation.py`
- architecture docs and build logs

### Phase 2: Paper-Mode Validation

Goal:

- establish evidence under virtual capital with fail-closed logic, Stoic Gate protection, and bounded learning behavior

Evidence already present:

- v3.1 paper-mode changes in the ledger
- trade autopsy and epoch-fix build log
- data-integrity sprint log

### Phase 3: Decision Gate

Goal:

- decide whether the project is ready for limited real-capital exposure, and under what exact operating assumptions

Status:

- still open

Why still open:

- the workspace strongly suggests this was the next planned step, but it does not contain fresh post-April-4 decision evidence closing the loop
- mixed-regime learning, observability expectations, and sequencing against infrastructure migration are still active concerns in the documented backlog

### Phase 4: Controlled Live Operation

Goal:

- prove the system can handle real slippage, real fees, and real operator risk without abandoning the protective architecture

Status:

- not yet evidenced in this workspace snapshot

### Phase 5: Scale and Platform Expansion

Goal:

- move beyond the single-wallet VPS core into dispatcher, cloud, and ML-enhanced variants without breaking trust in the primary engine

Status:

- partially built in repo, not yet proven operationally

## Moss Lane Sequencing Logic

The next sequence should prioritize decision quality over artifact count.

### Sequence A: Close the live-readiness truth gap

1. Segment performance by filter regime and epoch.
2. Decide whether `dynamic_config` should be reset, segmented, or made regime-aware before live use.
3. Record the go/no-go brief with explicit reasoning.

Why first:

- this resolves the most important ambiguity between paper performance and future live behavior

### Sequence B: Tighten operational readiness

1. revert to the intended live filters if wide-net is only for exploration
2. confirm paper/live accounting paths stay separate
3. add lightweight anomaly alerting if live trading is imminent

Why second:

- it hardens the exact path the project intends to use next

### Sequence C: Offensive improvement after readiness

1. tiered take-profit
2. further execution/latency instrumentation
3. live-vs-paper divergence analysis

Why third:

- these improve returns only after the control path is trustworthy

### Sequence D: Resume portfolio infrastructure expansion

1. Docker and Cloud Run
2. dispatcher deployment and integration
3. Cloud SQL / PostgreSQL migration path
4. Vertex AI experimentation

Why fourth:

- these are meaningful, but none of them should outrank a clean live-readiness decision for the core engine

## Definition of Done for This Project

In Moss Lane, "done" cannot mean "code exists."

A roadmap item should only be marked complete when all of the following are true:

- the code path exists in the repo
- the claim matches actual state: built, deployed, or planned
- the failure mode it was meant to fix is named and demonstrably addressed
- the result has evidence in tests, logs, deployment verification, or documented analysis
- the decision is reflected in durable documentation, not only in chat memory

For live-path items, add two more gates:

- the change has a rollback path
- the change does not blur the line between experimental and trusted operating state

## Current Delivery Risks

### Risk 1: Documentation outruns runtime truth

The workspace already contains strong storytelling. That is a strength, but only if every claim keeps the deployed/built/planned distinction intact.

### Risk 2: Mixed-regime evidence contaminates decisions

The most valuable near-term PM question is whether wide-net data is helping validation or muddying the live case.

### Risk 3: Test maturity lags architecture maturity

The codebase has meaningful test assets, especially around `fund_splitter`, but the current local test flow is not clean enough to present as frictionless operational readiness.

### Risk 4: Too many parallel futures

Dispatcher, Whale Watcher, Docker, GCP, Cloud SQL, and Vertex AI all matter, but they are not equally urgent. PM has to keep the immediate bottleneck visible.

## Evidence Model for Status Reporting

Every future sprint or milestone update should distinguish four evidence classes:

- `runtime verified`: observed in deployed logs or operational reports
- `repo verified`: implemented in the current codebase
- `documented but unverified`: claimed in docs without fresh code or runtime confirmation
- `planned`: intentionally future-state

This simple framing will keep Moss Lane honest while still letting it tell an ambitious story.

## What "Next" Means Right Now

The most useful next-step framing for Moss Lane is:

- close the decision gate on the core engine first
- make the live path truthful and bounded
- only then treat expansion modules as the main storyline

That sequencing preserves both profit logic and portfolio credibility.
