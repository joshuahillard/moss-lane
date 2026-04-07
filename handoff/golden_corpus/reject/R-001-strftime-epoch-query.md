# R-001 `strftime('%s')` Epoch Query

## Scenario

A query compares ISO text timestamps in `trades.timestamp` against unix-integer output from `strftime('%s', ...)`.

## Evidence Basis

- `github-repo/docs/build-log/2026-03-30-clown-trade-validation.md`
- `github-repo/docs/build-log/2026-04-03-data-integrity-sprint.md`

## Expected Outcome

`reject`

## Why

This pattern already caused a major data leak in Moss Lane. It must be rejected outright because it makes the analysis window untrustworthy.
