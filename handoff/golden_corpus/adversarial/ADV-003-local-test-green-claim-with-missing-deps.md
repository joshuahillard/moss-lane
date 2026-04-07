# ADV-003 Local Test Green Claim with Missing Dependencies

## Scenario

A reviewer claims the local test layer is green even though the environment lacks required packages or secrets and `pytest` cannot collect cleanly.

## Evidence Basis

- local `pytest -q` run in `github-repo/` on April 7, 2026
- `github-repo/tests/unit/test_foundation.py`

## Expected Outcome

`reject`

## Why

This is a truthfulness failure. The correct response is to reject the claim and document the conditional nature of the current test posture.
