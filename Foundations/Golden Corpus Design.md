# Golden Corpus Design

## What This Page Is

This page defines how a Moss Lane golden corpus should work. In this project, the golden corpus is not a collection of marketing wins. It is a curated set of representative scenarios with known expected outcomes so the team can test judgment, controls, and regressions mechanically.

For Moss Lane, the corpus should cover:

- real incidents
- real design validations
- real decision gates
- adversarial forms of stale or misleading state

## Why a Golden Corpus Matters Here

Moss Lane is already rich in anecdotes:

- the CLOWN trade validated the exit chain
- the DB config override bug explained a silent runtime failure
- epoch-format mismatches and `strftime('%s')` bugs broke analysis integrity
- paper-mode daily loss math surfaced a mode-boundary problem

Those stories are valuable, but they become more durable when turned into reusable fixtures with expected outcomes.

The corpus converts "what happened once" into "what the system must continue to handle."

## Corpus Design Principles

### Principle 1: Use real project history first

The strongest early fixtures should come from Moss Lane's actual journey, not invented edge cases.

### Principle 2: Separate approval, rejection, escalation, and adversarial paths

The project needs examples of:

- what should clearly count as a validated success
- what should clearly be rejected
- what should be escalated because the answer depends on human judgment
- what should fail closed because the state itself is dangerous

### Principle 3: Distinguish runtime truth from roadmap truth

Some fixtures test operating logic.
Some test documentation and decision hygiene.
Both matter in Moss Lane.

### Principle 4: Keep the corpus connected to next-step decisions

The corpus should not only preserve history. It should make future choices easier by clarifying:

- go-live readiness
- learning hygiene
- deploy truth
- config discipline

## Recommended Categories

### Approve

Use when the observed outcome should be considered a validated success.

Examples:

- exit-chain behavior that worked exactly as designed
- startup assertions passing after a hardening sprint
- original-filter performance supporting a revert case

### Reject

Use when the state should be treated as clearly not acceptable.

Examples:

- out-of-bounds config writes
- epoch-query anti-patterns
- go-live claims that still depend on wide-net evidence without cleanup

### Escalate

Use when the code may be functional but the decision should remain human-owned.

Examples:

- whether to migrate to GCP before proving live profitability
- whether dispatcher should be deployed now
- whether mixed-regime learning data is good enough for the next phase

### Adversarial

Use when the input or state is specifically designed to stress trust boundaries.

Examples:

- stale DB config overriding newer code
- timestamp strings in the wrong shape
- test success claims without required dependencies
- built-but-undeployed modules being presented as active

### Integration

Use when the real question is whether multiple layers stay aligned.

Examples:

- three-layer config changes across code, DB, and defaults
- paper/live accounting separation
- deployment plus health-check plus rollback flow

## Current Corpus Position

The workspace does not yet contain an executable Moss Lane corpus harness comparable to the LLM project's validator harness. This documentation set therefore establishes a documentation-first corpus that can later be bound to tests, checklists, or SQL/analysis notebooks.

That is an honest starting point and matches current project reality.

## Minimum Early Coverage

The first Moss Lane corpus should overrepresent the project's real historical failure modes:

- stale config
- epoch errors
- wrong query semantics
- mixed-regime evidence
- mode-boundary math

The project has learned the hard way that quiet integrity bugs are more dangerous than obvious crashes.

## What the Corpus Should Enable Next

Once adopted, the corpus should make it easier to:

- evaluate live-readiness claims consistently
- preserve the logic behind hard-earned rules
- brief future collaborators without retelling the entire project verbally
- connect incident history to operational policy
