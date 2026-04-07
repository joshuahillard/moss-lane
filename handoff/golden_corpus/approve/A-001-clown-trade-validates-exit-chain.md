# A-001 CLOWN Trade Validates Exit Chain

## Scenario

A real paper trade reaches trailing-stop arming and then hits take-profit. The system exits through the higher-priority take-profit rule.

## Evidence Basis

- `github-repo/docs/build-log/2026-03-30-clown-trade-validation.md`

## Expected Outcome

`approve`

## Why

This fixture validates that the exit chain is deterministic, priority-ordered, and able to convert a qualifying runner into a captured gain without ambiguity.
