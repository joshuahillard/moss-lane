# Runtime Validation for Adaptive Output

## What This Page Is

This page is the Moss Lane analogue to schema validation in the LLM project. Moss Lane does not primarily validate model JSON. It validates whether adaptive runtime behavior is safe enough to influence the engine.

The core question is:

**When Lazarus changes behavior based on data, what proves that the change is still inside the operating contract?**

## Why This Matters

Several of the project's most important failures were not syntax failures. They were validation failures:

- stale config was accepted as current truth
- wrong trades entered learning windows
- wrong timestamp comparisons looked plausible
- paper-mode risk math used the wrong capital base

The lesson is that runtime safety depends on validation at the moment behavior changes, not only on code quality at rest.

## Current Validation Stack

The repo currently contains a meaningful validation layer in `src/data/data_integrity.py`.

### Validation layer 1: query-level epoch gating

Purpose:

- prevent known-bad query patterns
- block timestamp anti-patterns before they distort analysis

### Validation layer 2: learning-input validation

Purpose:

- enforce epoch relevance
- enforce sample-size discipline through Stoic Gate
- enforce field completeness

### Validation layer 3: config-write bounds

Purpose:

- stop learning output from poisoning runtime behavior

### Validation layer 4: startup assertions

Purpose:

- catch bad runtime config before the engine starts trading

### Validation layer 5: anomaly detection

Purpose:

- surface drift and suspicious patterns for human review

## What Counts as Adaptive Output in Moss Lane

Adaptive output includes:

- `dynamic_config` writes
- learning-engine recommendations implied through changed stop-loss or position-sizing values
- self-regulation state changes such as pauses and cooldown logic
- performance summaries used to justify strategic changes

These are the outputs that need validation because they influence future actions rather than just recording history.

## Validation Invariants

1. Adaptive output must be bounded before it is authoritative.
2. Input validation must happen before output validation can be trusted.
3. Mode-specific calculations must use mode-specific inputs.
4. A valid-looking result is not enough if its source window is wrong.
5. Human review remains required for strategy changes that exceed local bounded tuning.

## Current Strengths

- the codebase contains an explicit validation module rather than scattered one-off guards
- the project documents the incidents that motivated each layer
- bounds are conservative and intentionally fail closed
- startup assertions show a preference for refusing to trade over trading under ambiguity

## Current Gaps

### Gap 1: regime-aware learning is not yet a closed-loop guarantee

The workspace documents this as an important next-step concern. That means output may be bounded but still shaped by a dataset that is not strategically clean for the next phase.

### Gap 2: local test ergonomics are not mature

The test suite contains useful assets, but collection and dependency assumptions still make local validation uneven.

### Gap 3: integration-grade proof is thinner than unit-grade proof

The project has strong incident narratives and some targeted tests, but fewer end-to-end proofs covering deploy, runtime, and post-trade audit in one flow.

## Required Future Standard

For adaptive output to be trusted in a live-ready Moss Lane phase, it should meet all of the following:

- input window is correct
- active regime is explicit
- bounds are enforced
- output is attributable to a dated evidence set
- a rollback path exists if the output proves harmful

## Why This Foundation Matters for the Story

This is one of the strongest themes in Moss Lane's journey. The project did not become more trustworthy because it added more adaptation. It became more trustworthy because it learned to distrust adaptation until it was bounded and evidenced.
