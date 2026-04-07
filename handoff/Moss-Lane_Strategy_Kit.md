# Moss Lane Strategy Kit

**Rev 1.1 — April 7, 2026**

PRD | ADR | Roadmap | FMEA | Decision Gate

Prepared for: Josh Hillard  
Status: Framework backfill complete. Core engine decision gate still open.

---

## Executive Summary

Moss Lane is the project. Lazarus is the trading engine inside it.

The core story is now clear:

- Lazarus is no longer just a trading bot. It is a bounded trading control plane.
- The strongest part of the project is not feature count. It is the hardening work around exits, config truth, data integrity, and operating discipline.
- The current repo contains both credible active-engine work and meaningful future-state modules. The strategy kit treats those separately on purpose.
- The next milestone is not "build more." It is to close the live-readiness decision gate honestly.

As of April 7, 2026, the validated workspace state is:

- active implementation repo: `github-repo/`
- current documented engine path: Lazarus v3.1
- 5-layer data integrity controls exist in `src/data/data_integrity.py`
- latest checked-in operating evidence is dated April 4, 2026 and reports through April 3, 2026
- dispatcher, Whale Watcher, Docker, Cloud/GCP, and Vertex AI are repo-built but not evidenced as deployed runtime
- local test posture is not fully clean because `pytest` currently breaks collection through `test_foundation.py`, and the local environment used here is missing expected dependencies/secrets for that path

---

## Part 1: PRD

### Product Definition

The product is a bounded, auditable Solana momentum-trading infrastructure that:

- discovers candidates
- rejects most of them through fail-closed logic
- executes and exits deterministically
- adapts inside hard limits
- preserves enough evidence to justify both past decisions and next decisions

### Problem

The real problem Moss Lane solved was never just signal discovery. It was trust under volatility.

The project history already proved the main failure classes:

- bad filters can buy exhausted tokens
- stale or mis-scoped data can poison learning
- DB config can silently override correct code
- paper/live logic can diverge in dangerous ways
- documentation can overstate what the runtime is actually doing

### Goals

- Deterministic risk handling
- Strong data-integrity discipline
- Honest deployed-vs-built staging
- Decision-grade documentation
- Portfolio-grade legibility without inflation

### Non-Goals

- treating repo-complete modules as operational by default
- scaling before the live path is governed
- prioritizing platform polish over core control-path truth
- allowing the learning layer to become unbounded strategy authority

### Primary Stakeholders

- Josh Hillard: owner, operator, final authority
- Lazarus runtime: bounded autonomous engine
- Future reviewer/interviewer/collaborator: needs a truthful map of what is live, what is built, and what still needs proof

### Must-Have Requirements

| ID | Requirement | Current State |
| --- | --- | --- |
| P0-1 | Fail-closed scan and safety path | Present |
| P0-2 | Deterministic exit hierarchy | Present |
| P0-3 | Three-layer config awareness | Present |
| P0-4 | Bounded learning output | Present |
| P0-5 | Epoch-safe analysis rules | Present |
| P0-6 | Paper/live accounting separation | Present, must stay monitored |
| P0-7 | Truthful deployed-vs-built distinction | Partial |
| P0-8 | Clean go-live decision gate | Not yet closed |

### Near-Term Success Metrics

Near-term success should be measured by trust, not breadth:

- no recurrence of known epoch/query/config integrity failures
- one explicit regime-specific live-readiness brief
- clear subsystem status labeling
- bounded learning preserved over time
- no silent drift into live mode

---

## Part 2: ADR

### ADR-001: Trust-Bounded Trading Control Plane

**Status:** Active  
**Date:** Backfilled April 7, 2026

#### Decision

Treat Lazarus as a trust-bounded control plane rather than a "smart bot."

That means:

- runtime autonomy stays bounded
- config truth is layered and validated
- data integrity is a first-class control problem
- paper and live are separate governance states
- built-but-undeployed modules stay non-authoritative until deployment evidence exists

#### Why This Was the Right Choice

The alternative was effectively feature-first buildout: faster visible growth, weaker operational truth. Moss Lane already has enough incident history to show where that path leads.

#### Consequence

The next strategic move is not to widen the system. It is to close the decision gate on the core engine before shifting the center of gravity to expansion modules.

---

## Part 3: Roadmap

### NOW: Decision Integrity

1. Segment performance by epoch and filter regime.
2. Decide how `dynamic_config` should relate to the intended live regime.
3. Write the explicit go/no-go memo.

Done means:

- one evidence-backed readiness memo exists
- the intended live regime is stated plainly
- mixed-regime ambiguity is either resolved or consciously escalated

### NEXT: Go-Live Prep

1. Revert to the intended live filter set if wide-net was exploratory only.
2. Add lightweight critical alerting.
3. Verify the paper/live checklist and rollback path.

Done means:

- the live candidate state is truthful and bounded
- no unresolved denominator/config/regime ambiguity remains on the core path

### THEN: Controlled Live Trial

1. Enable limited real-capital trading.
2. Monitor early trades closely.
3. Compare live behavior to paper expectations.

Done means:

- the system survives first live exposure without violating its own contract
- evidence is clean enough to support the next decision

### LATER: Offensive and Expansion Work

1. Tiered take-profit
2. Dispatcher deployment
3. Docker / Cloud Run / Cloud SQL
4. Vertex AI experiments

Rule:

- each item moves from `repo-built` to `deployed` only with evidence

---

## Part 4: FMEA Snapshot

| Failure Mode | Effect | Current Controls | Residual Gap |
| --- | --- | --- | --- |
| Wrong epoch/query logic | bad learning and false reporting | query validation, explicit rules | needs ongoing discipline and future harnessing |
| Stale DB config overrides code | runtime diverges from deploy intent | startup assertions, three-layer awareness | still depends on disciplined change management |
| Mixed-regime evidence drives live decision | wrong strategy assumptions | risk already identified in project docs | still needs explicit resolution |
| Paper/live denominator confusion | false halt or false safety | paper-capital fix | should remain a standing checklist item |
| Undeployed module framed as active | inflated readiness | new framework docs distinguish state | still needs one central state matrix |
| Local tests treated as universally green | false confidence | gap now explicitly documented | test ergonomics still need cleanup |

---

## Part 5: Delivery Contract

For Moss Lane, a deliverable is only complete if it states:

- what changed
- whether it is `deployed`, `repo-built`, or `planned`
- what failure mode it addresses
- what evidence supports it
- what decision it unlocks next

That is what keeps the project cohesive instead of merely well-described.

---

## Part 6: Decision Gate

The immediate question is:

**Is the current core engine ready for a bounded first live phase, and if not, what exact truth gap still blocks that move?**

Based on the April 7, 2026 workspace snapshot:

- the core architecture is credible
- the data-integrity story is materially strong
- the next-step path is visible
- the go-live gate is still open because regime-specific evidence and operational-readiness decisions remain unresolved in the checked-in record

That is not a weakness. It is the correct validated answer.

---

## Part 7: Crosswalk

This strategy kit is supported by:

- `Governance/`
- `Program-Management/`
- `Foundations/`
- `design-docs/`
- `pipeline/`
- `handoff/golden_corpus/`

The strategy kit is now the fast-read layer. The framework docs beneath it are the deep reference layer.
