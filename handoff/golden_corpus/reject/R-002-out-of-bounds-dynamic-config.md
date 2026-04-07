# R-002 Out-of-Bounds Dynamic Config

## Scenario

The learning layer attempts to write a value outside approved safety bounds, such as a 3% position size or other invalid parameter state.

## Evidence Basis

- `github-repo/src/data/data_integrity.py`
- `github-repo/docs/build-log/2026-04-03-data-integrity-sprint.md`

## Expected Outcome

`reject`

## Why

Adaptive output is only trustworthy when bounded. An out-of-bounds write is not a tuning detail. It is a control-plane rejection.
