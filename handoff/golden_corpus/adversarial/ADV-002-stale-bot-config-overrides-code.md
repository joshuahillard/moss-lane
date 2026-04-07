# ADV-002 Stale `bot_config` Overrides Code

## Scenario

A deployment changes code defaults, but stale DB-backed `bot_config` values continue to win at runtime.

## Evidence Basis

- `docs/MOSS_LANE_PROJECT_LEDGER.md`

## Expected Outcome

`reject`

## Why

This is a classic Moss Lane adversarial state because everything can look newly deployed while runtime behavior remains old.
