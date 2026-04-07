# Moss Lane Pipeline

## What This Folder Is

This folder documents the Moss Lane operating pipeline using the same structural intent as the LLM project's `pipeline/` area. In Moss Lane, the pipeline is not a separate content-validator stack. It is the end-to-end trading control path that turns external market data into bounded decisions, trade lifecycle management, learning signals, and operator-facing evidence.

This folder is documentation-first. It does not claim that Moss Lane currently has a standalone pipeline package separate from the code under `github-repo/src/`. Its purpose is to make the control flow legible and reusable.

## Current Pipeline Shape

At a high level, the present Moss Lane pipeline is:

1. external data ingestion
2. candidate discovery
3. fail-closed filtering
4. safety gating
5. execution
6. monitoring and exit-chain enforcement
7. persistence and reporting
8. bounded learning and self-regulation
9. human review for strategic transitions

## Current vs. Planned Lanes

### Current lane

The current lane is the single-engine Lazarus paper/live path centered on:

- `src/engine/lazarus.py`
- `src/engine/learning_engine.py`
- `src/engine/self_regulation.py`
- `src/data/data_integrity.py`

### Planned lane

The planned lane adds:

- dispatcher coordination
- multi-wallet finance routing
- cloud/database migration
- ML-assisted expansion

These are important, but they should be read as next-stage lanes until deployment evidence exists.

## Folder Map

- `ops/ENGINE_RUNTIME_CONTRACT.md`
  Describes runtime states, safety transitions, and the current operating contract.
- `policy_engine/OPERATOR_POLICY_BUNDLE.md`
  Captures the project-level policy rules that should govern acceptance, rejection, escalation, and go-live decisions.
- `tests/CORPUS_README.md`
  Connects the pipeline to the documentation-first golden corpus housed under `handoff/golden_corpus/`.

## Design Rule

This folder should remain faithful to actual project state. If the runtime changes, the docs here should change with it. If a future subsystem is still only repo-built, the pipeline docs should say so explicitly.
