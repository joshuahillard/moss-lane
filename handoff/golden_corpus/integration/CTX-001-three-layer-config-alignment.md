# CTX-001 Three-Layer Config Alignment

## Scenario

A meaningful runtime configuration change is only considered complete when code defaults, `bot_config`, and `dynamic_config` truth are aligned or intentionally overridden with evidence.

## Evidence Basis

- `docs/MOSS_LANE_PROJECT_LEDGER.md`
- `github-repo/src/engine/lazarus.py`
- `github-repo/src/data/data_integrity.py`

## Expected Outcome

`approve`

## Why

This integration fixture validates one of Moss Lane's most important control-plane lessons: runtime truth is layered and must be treated that way during changes.
