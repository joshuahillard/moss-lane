# Human-in-the-Loop Governance

## What This Page Is

This document defines the binding governance contract between automated decision-making inside Moss Lane and final human authority held by Josh Hillard as operator, owner, and deployment authority.

It is not a generic statement that "humans should stay involved." It specifies exactly where Lazarus may act autonomously, where it must fail closed, where undeployed code has no operational authority, and which decisions must remain human-owned even if the automation has enough code to attempt them.

This page is a control-plane contract for the current Moss Lane system as evidenced by the workspace on April 7, 2026. It is grounded in the shipped Lazarus v3.1 paper-trading engine, the 5-layer data integrity module, the documented incidents from March 28 through April 4, and the present codebase under `github-repo/`.

## Governance Invariants

1. Lazarus may discover signals, reject candidates, record trades, update bounded runtime state, and pause itself for safety.
2. Lazarus may not decide when the project exits paper mode. `PAPER=false` is a human authorization event.
3. The learning engine may suggest parameter changes only inside bounded ranges enforced by `src/data/data_integrity.py`.
4. Undeployed modules are design assets, not runtime facts. Dispatcher, Whale Watcher, Docker, GCP, and Vertex AI work are not allowed to be represented as live production capability until actually deployed and verified.
5. Any human override of runtime behavior must be attributable through code, config, deployment artifacts, or documented ops history. Silent overrides are governance failures.
6. A profitable paper result is evidence, not permission. Go-live remains a human decision gated by explicit review of strategy, data integrity, and operating readiness.
7. Operational safety outranks experimentation. When paper/live state, epoch scope, config source of truth, or loss calculations are ambiguous, the system must fail closed or pause.

## Authority Boundary

### What automation is allowed to decide

Automation may:

- scan markets and reject most candidates through fail-closed filters
- open and close paper or live trades only within the currently authorized mode and bounded config
- pause scanning for daily-loss, market-crash, self-regulation, or cooldown reasons
- write `dynamic_config` values inside approved bounds
- emit logs, DB writes, build artifacts, and anomaly warnings
- preserve evidence needed for retrospectives, trade autopsies, and future tuning

### What automation is not allowed to decide

Automation may not:

- switch from paper mode to live mode
- widen safety bounds beyond the hard limits enforced in code
- deploy undeployed modules simply because they exist in the repo
- redefine the active filter regime without operator approval
- treat mixed-regime analysis as sufficient proof for go-live without explicit review
- erase or obscure incidents, stale config, or bad decisions from the historical record

### What humans decide

Human authority covers:

- go-live approval and real-capital enablement
- filter-regime changes that materially alter trade quality
- deployment of dispatcher, Whale Watcher, Docker, Cloud Run, Cloud SQL, or Vertex AI paths
- acceptance of paper-mode evidence as sufficient for the next stage
- rollback, pause, or retirement decisions after incident review
- how much capital is exposed and under what risk envelope

## Governed State Model

Moss Lane currently operates across a small number of meaningful control states.

### `paper_validation`

The engine is allowed to trade with virtual capital while validating architecture, filters, and monitoring logic.

Required conditions:

- `PAPER=true`
- virtual-capital accounting is used for paper-specific risk math
- trade analysis is epoch-scoped
- config changes are bounded and attributable

### `paper_observe`

The engine continues to run, but no new strategic claims should be made without fresh review. This state is appropriate after a data-integrity fix, regime shift, or major patch when the team needs additional evidence.

### `go_live_candidate`

This is a human review state, not an engine state. It means the project has enough evidence to assemble a decision brief, not that the system has permission to flip to live.

Minimum evidence should include:

- stable paper-mode performance under the intended filter regime
- validated daily-loss math for the intended mode
- explicit treatment of mixed-regime learning data
- an operator decision on observability expectations

### `live_limited`

The engine is authorized to trade with real capital under a narrow risk envelope. This is the likely first live state for Moss Lane given the documented real-wallet size of roughly $103.

### `paused_by_governance`

This state is entered when data integrity, config truth, deployment truth, or risk calculations are materially ambiguous. The engine may still exist, but claims of readiness stop until the ambiguity is resolved.

## Override and Attribution Contract

Human overrides are allowed, but they are not silent.

Examples of governed override actions:

- manually reverting from wide-net to original filters
- clearing or rewriting `dynamic_config`
- deciding not to trust learning output produced from mixed-regime trades
- choosing VPS-first go-live instead of GCP-first migration
- delaying dispatcher deployment despite code completeness

Every such override should leave evidence in at least one of these places:

- a checked-in code or config change
- a deployment script or rollback artifact
- the project ledger
- an ops handoff, briefing, or report
- the golden corpus as a corrected scenario

## Evidence Contract

Moss Lane governance depends on keeping a clean distinction between what is:

- deployed and verified
- built locally but not deployed
- planned but not yet built
- inferred from analysis but not yet validated in runtime

The current project already contains both live runtime components and portfolio-forward modules. Governance requires these be kept separate.

### Deployed and evidenced

As of the latest workspace evidence:

- Lazarus v3.1 paper mode
- learning engine with bounded writes
- self-regulation module
- 5-layer data integrity protections
- deploy template and surgical patch workflow

### Built but not yet operationally authoritative

- dispatcher pipeline modules
- Whale Watcher
- Docker artifacts
- Cloud/GCP path
- Vertex AI pipeline

These may influence roadmap planning, but they do not carry runtime authority until deployment and verification are complete.

## Safety Escalation Rules

The system must escalate to human review instead of silently continuing when:

- epoch filtering is ambiguous or known-bad patterns appear
- paper-mode accounting uses live-wallet denominators or vice versa
- config values disagree across code, `bot_config`, and `dynamic_config`
- undeployed modules are assumed in architecture claims or decision-making
- local tests are presented as green while their dependencies or secrets are missing
- performance claims mix regimes without explicit segmentation

## Go-Live Governance Gate

Go-live is not a single metric. It is a governance checkpoint that should answer five questions explicitly:

1. Are the intended live filters the same filters that produced the supporting performance claim?
2. Is the learning engine training on the same regime that will govern live trading?
3. Are anomaly and incident paths observable enough for real capital, even if initially lightweight?
4. Is the deployment target stable enough that migration is not being attempted under live stress?
5. Is the capital exposure consistent with the documented risk model and current wallet reality?

If any answer is "not yet" or "unclear," the correct state is `go_live_candidate` or `paused_by_governance`, not `live_limited`.

## Failure Modes This Contract Is Meant to Prevent

- paper results being treated as auto-permission for live capital
- the learning engine silently drifting on mixed-regime data
- undeployed architecture being mistaken for shipped capability
- config truth drifting across code and database layers
- mode-specific math using the wrong capital denominator
- silent human overrides that cannot be reconstructed later
