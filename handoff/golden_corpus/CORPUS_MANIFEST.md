# Moss Lane Golden Corpus Manifest

## What This Corpus Is

This corpus is a documentation-first validation set for Moss Lane. It mirrors the intent of the LLM project's golden corpus while staying grounded in Lazarus's real journey.

Each fixture captures:

- a real or realistic Moss Lane scenario
- the expected outcome
- why that outcome is correct
- which trust boundary, control, or decision rule it validates

## Outcome Classes

- `approve`: validated success or trustworthy readiness signal
- `reject`: clearly unacceptable state
- `escalate`: human decision required
- `adversarial`: malformed or misleading state that should fail closed
- `integration`: multi-layer control alignment

## Corpus Design Notes

- The corpus intentionally overrepresents data-integrity and truthfulness failures because those have been the most expensive failure class in Moss Lane so far.
- Some fixtures are runtime-oriented and some are documentation-oriented. Both matter because Moss Lane is both an operating system and a portfolio story.
- The current corpus is portable and handoff-friendly. It is not yet wired to an executable harness.

## Current Fixture Inventory

- approve: 3
- reject: 3
- escalate: 3
- adversarial: 4
- integration: 2

Total: 15
