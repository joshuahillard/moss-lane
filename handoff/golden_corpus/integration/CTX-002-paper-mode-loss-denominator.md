# CTX-002 Paper-Mode Loss Denominator

## Scenario

Daily-loss logic in paper mode uses virtual capital rather than the much smaller real wallet balance.

## Evidence Basis

- `github-repo/docs/build-log/2026-04-03-data-integrity-sprint.md`
- `docs/reference/2026-04-04_Moss_Lane_Sprint_Overview.md`

## Expected Outcome

`approve`

## Why

This fixture validates that mode-aware accounting is now treated as a real control, not a reporting detail.
