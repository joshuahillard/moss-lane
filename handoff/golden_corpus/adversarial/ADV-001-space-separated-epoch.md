# ADV-001 Space-Separated Epoch

## Scenario

An epoch string uses a space separator instead of the ISO `T` format expected by the text-comparison logic.

## Evidence Basis

- `docs/MOSS_LANE_PROJECT_LEDGER.md`
- `github-repo/docs/build-log/2026-03-30-clown-trade-validation.md`

## Expected Outcome

`reject`

## Why

This looks small but is adversarial to correctness because it corrupts lexicographic comparison behavior. Moss Lane already paid for this lesson once.
