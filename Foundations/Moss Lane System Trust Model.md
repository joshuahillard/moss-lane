# Moss Lane System Trust Model

## What This Page Is

This page defines the trust model for Moss Lane and Lazarus. In this project, the trust problem is not only "can the code run?" It is "what parts of the system are allowed to influence capital, configuration, and strategic decisions without additional validation?"

Moss Lane mixes:

- deterministic code
- noisy external market data
- mutable runtime configuration
- documented human analysis
- undeployed future modules

The trust model exists to stop those categories from being treated as equally authoritative.

## The Core Trust Question

For Moss Lane, the central question is:

**Which system outputs can be acted on directly, and which must be validated, bounded, or escalated before they influence money, risk, or project claims?**

If that question is answered clearly, the project stays governable.
If it is answered poorly, Moss Lane can still look sophisticated while quietly making weak decisions.

## Deterministic vs. Non-Deterministic Components

### Deterministic components

These should behave consistently for the same inputs:

- checked-in Python modules
- SQL query text
- config bounds in `data_integrity.py`
- startup assertions
- deployment scripts
- local docs that record a specific dated state
- file and folder structure in the workspace

These are where replayability and auditability come from.

### Non-deterministic or unstable components

These are useful but not self-certifying:

- market conditions
- DexScreener, Birdeye, Helius, and Jupiter responses
- slippage and execution timing
- learning-engine suggestions that depend on recent trades
- paper-performance conclusions generalized to future live conditions

These components can inform decisions, but they cannot be treated as truth without boundaries.

## Trusted Inputs

Inputs are trusted here only if they are controlled and mechanically inspectable.

Examples:

- checked-in source files under `github-repo/src/`
- deploy scripts under `deploy/` and `github-repo/deploy/`
- the project ledger and build logs when used as dated evidence rather than timeless truth
- bounded config rules in `src/data/data_integrity.py`
- explicit git history under `github-repo`

These are trusted because they are versioned or directly inspectable.

## Untrusted Inputs

Untrusted does not mean malicious. It means the system must validate before acting.

Examples:

- external API responses
- on-chain market conditions
- raw database contents before epoch and completeness checks
- stale `bot_config` values that may override code
- any runtime claim that is newer than the last documented evidence
- portfolio-facing summaries that flatten built and deployed states together

This is one of Moss Lane's recurring lessons: many failures came from trusting stale or mismatched state, not from missing code.

## Context-Locked State

Some data is only trustworthy inside the exact context that produced it.

Examples:

- paper-mode profitability claims tied to a specific epoch and filter regime
- `dynamic_config` values produced from a specific training window
- incident reports tied to a specific code and deployment state
- readiness assessments tied to the operating mode in force at the time

This matters because Moss Lane already documented one of the classic context failures: using the wrong timestamp format or the wrong denominator can make a valid-looking result meaningless.

## What "Trust-Nothing" Means in Moss Lane

For this project, "trust-nothing" means:

- do not trust config just because it exists in a database
- do not trust performance claims unless they are epoch-scoped
- do not trust mixed-regime results as direct evidence for a tighter live regime
- do not trust undeployed code as operational capability
- do not trust a local green-looking test story when required packages or secrets are missing
- do not trust strategy changes that outrun the integrity and rollback path

The project has already earned these rules through real incidents.

## Where Final Authority Lives

The final authority boundary in Moss Lane is simple:

- automation may operate inside its current bounds
- Josh decides whether those bounds change

That includes:

- paper vs. live
- capital exposure
- filter-regime changes
- deployment of new modules
- interpretation of performance evidence

The learning engine is therefore advisory inside hard rails, not sovereign.

## Trust by Layer

### Layer 1: Code and policy

Most trusted, but still subject to review and deployment truth.

### Layer 2: Runtime state

Trusted only after validation:

- config
- trade windows
- epoch-scoped analysis
- anomaly warnings

### Layer 3: External market and service data

Valuable but inherently unstable. Requires retries, fallback thinking, and execution-time rechecks.

### Layer 4: Strategic interpretation

Least mechanically provable. This is where human review is required most often, especially around go-live and expansion sequencing.

## Accountability Chain

Moss Lane should be explainable from any important claim back to its artifacts.

Examples:

- a paper-performance claim should trace to the trade DB, the epoch rule, the filter regime, and the analysis doc
- a config decision should trace to code defaults, `bot_config`, `dynamic_config`, and the bounds layer
- a deployment claim should trace to a deploy script, backup path, compile/health check, and service outcome

If that chain breaks, the project may still operate, but it stops being defensible.

## What This Trust Model Protects Against

- stale state masquerading as current truth
- mixed evidence being used for sharp decisions
- portfolio polish outrunning operational readiness
- adaptive code silently exceeding safe bounds
- claims of production capability unsupported by deployment evidence
