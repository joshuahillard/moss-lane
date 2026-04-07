# Moss Lane Control Plane Review

This document is a build-facing review artifact for the current Moss Lane architecture. It is not a marketing overview. It is a source of truth for:

- control-plane boundaries
- file responsibilities
- invariants that must remain true
- deployed vs. built vs. planned distinctions
- implementation order for the next stage

---

## Review Outcome

The proposed and partially shipped Moss Lane architecture is strongest where it already learned from real pain:

- fail-closed selection
- bounded autonomy
- three-layer config awareness
- paper-mode validation discipline
- documented rollback-minded deployment
- explicit data-integrity protections

The main remaining risk is no longer "can this person write code?" The risk is control-plane ambiguity across these layers:

1. runtime config truth
2. epoch- and regime-scoped analysis truth
3. deployment truth
4. readiness claims vs. actual operating evidence

That is a healthier risk profile than the v2 starting point.

---

## Recommended File Inventory

These files and areas are the current v1 control-plane surface for Moss Lane:

```text
github-repo/
├── src/engine/
│   ├── lazarus.py
│   ├── learning_engine.py
│   └── self_regulation.py
├── src/data/
│   ├── data_integrity.py
│   ├── db_adapter.py
│   └── migrate_sqlite_to_pg.py
├── src/scanner/
│   ├── scanner_coordinator.py
│   └── whale_watcher.py
├── src/finance/
│   ├── fund_splitter.py
│   ├── tax_vault.py
│   └── wallet_generator.py
├── deploy/
└── docs/build-log/
```

Operational state is then evidenced through:

```text
docs/
├── MOSS_LANE_PROJECT_LEDGER.md
├── ai-onboarding/
├── reference/
└── session_notes/

ops/
├── briefings/
├── handoffs/
├── reports/
└── trades/
```

---

## Critical Invariants

### 1. Config truth is layered, not singular

Runtime behavior is determined by:

- code defaults
- `bot_config`
- `dynamic_config`

Any work touching strategy or safety must account for all three.

### 2. Learning output is advisory inside hard rails

The learning engine may influence runtime only through bounded writes validated by `data_integrity.py`.

### 3. Epoch and regime scope are not optional metadata

Performance claims, learning windows, and go-live decisions must preserve the exact scope that produced them.

### 4. Paper and live are different control states

Paper-mode accounting, evidence, and readiness logic must remain separate from live-capital logic.

### 5. Built does not mean deployed

Dispatcher, Whale Watcher, Docker, GCP, Cloud SQL, and Vertex AI work remain non-operational until deployment evidence exists.

### 6. Deployment must stay rollbackable

The deploy pattern of backup, patch, compile, restart, and health check is part of the control plane, not a convenience.

---

## Reviewed Design Shape

### `src/engine/lazarus.py`

Responsibilities:

- main async trading loop
- scanning and trade-execution orchestration
- monitor loop and exit-chain enforcement
- paper/live balance handling
- integration points for integrity checks and learning runs

Review notes:

- this is the system center of gravity
- any change here should be treated as control-plane work, not just feature work

### `src/engine/learning_engine.py`

Responsibilities:

- analyze trade outcomes
- propose bounded config changes
- persist adaptive output

Review notes:

- strategically important, but must remain subordinate to the integrity layer

### `src/engine/self_regulation.py`

Responsibilities:

- regime evaluation
- scan pauses
- token cooldown logic

Review notes:

- should continue to be constrained to a narrow authority boundary

### `src/data/data_integrity.py`

Responsibilities:

- query validation
- learning-input validation
- config-write validation
- startup assertion checks
- anomaly detection

Review notes:

- this is one of the most important trust anchors in the current repo

### `src/scanner/*`

Responsibilities:

- next-phase discovery and routing logic

Review notes:

- meaningful repo assets
- not yet operational truth for the live system unless separately deployed

### `src/finance/*`

Responsibilities:

- multi-wallet capital routing
- tax-vault logic
- wallet generation support

Review notes:

- strong next-phase story
- still requires deployment and integration proof before being treated as runtime capability

### `src/ml/*`

Responsibilities:

- data extraction
- training
- prediction support

Review notes:

- useful platform expansion path
- currently should be framed as repo-built capability, not active engine logic

---

## Verified Gaps

### Gap 1: local test collection is not yet control-plane clean

`pytest` currently fails to collect cleanly because `tests/unit/test_foundation.py` exits the process and expects dependencies/secrets not present locally.

### Gap 2: regime-aware learning is still a next-step item

The documentation strongly implies this matters before go-live, but the current repo does not present it as a fully closed loop.

### Gap 3: one operational-state index is still missing

The truth is available across docs, but not yet centralized into one matrix that labels each subsystem as deployed, repo-built, or planned.

---

## Recommended Implementation Order

1. close live-readiness ambiguity for the core engine
2. harden test and validation ergonomics
3. add lightweight alerting for critical anomalies
4. deploy offensive upgrades such as tiered take-profit
5. only then promote dispatcher/cloud/ML work to the front of the program

---

## Final Assessment

Moss Lane is no longer a loose bot script project. It is a real control-plane story with a credible core engine, documented incidents, and visible next risks.

The next job is not to invent more architecture. It is to close the remaining truth gaps between what the system can do, what it has done, and what it is ready to do next.
