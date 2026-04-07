# Corpus Readme

## What This Page Is

This page connects the Moss Lane pipeline documentation to the golden corpus housed under `handoff/golden_corpus/`.

The corpus is documentation-first in the current project state. That means:

- the scenarios are curated and categorized
- the expected outcomes are explicit
- the corpus is meant to support decisions, reviews, and future test harnesses

It does not yet claim to be wired into an executable pipeline harness.

## Why This Still Matters

Moss Lane already has enough history that repeating the same lessons verbally is costly. The corpus exists to preserve those lessons in a more reusable format.

## Categories

The current corpus is organized into:

- `approve`
- `reject`
- `escalate`
- `adversarial`
- `integration`

## How To Use It

Use the corpus when:

- checking whether a new document or roadmap claim matches the known rules
- evaluating live-readiness arguments
- onboarding collaborators to the project's incident history
- deciding what future tests or dashboards should prove mechanically

## Design Intent

Over time, this pipeline/tests layer can evolve into:

- executable validation notebooks
- SQL-based verification packs
- deployment checklists
- regression tests for config, epoch, and mode logic

For now, its job is to keep the project's hard-earned truths portable and structured.
