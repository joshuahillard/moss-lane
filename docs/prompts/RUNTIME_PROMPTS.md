# Moss Lane Runtime Prompts
**Copy-paste blocks for AI sessions. This file is model input, not human documentation.**
*Version: 1.0 | April 4, 2026*

---

## CORE CONTRACT

Paste once at session start. Stable across sprints.

```
MOSS LANE CORE v1.0

Project: Moss Lane is an autonomous Solana memecoin trading system.
Engine: Lazarus — momentum-based trading engine with self-learning.
Server: Vultr VPS (NJ), systemd-managed, SQLite trade database.

Stack: Python 3.12, asyncio, aiohttp (RPC/Jupiter only), curl_get (external),
Jupiter public API, DexScreener, SQLite (WAL), Docker, GCP Artifact Registry.

Architecture:
- engine/ — core trading logic (lazarus.py, learning_engine.py, self_regulation.py)
- scanner/ — token discovery (scanner_coordinator.py, whale_watcher.py)
- finance/ — position sizing (fund_splitter.py, tax_vault.py, wallet_generator.py)
- data/ — database layer (db_adapter.py, data_integrity.py)
- ml/ — Vertex AI integration (vertex_train.py, vertex_predict.py)
- deploy/ — deployment scripts (base64-embedded, self-contained)

Rules:
- Never overwrite lazarus.py wholesale — targeted patches only.
- Always verify Python syntax before restarting service.
- Use EnvLoader, never python-dotenv (breaks on quoted values).
- External HTTP must use curl_get() — aiohttp only for RPC + Jupiter.
- VersionedTransaction signing: VersionedTransaction(tx.message, [KP]).
- skipPreflight must be True for memecoin swaps.
- Jupiter endpoint: public.jupiterapi.com (quote-api.jup.ag deprecated).
- DexScreener for scanning (Birdeye Standard only returns 20 large caps).
- Check DB for trade results before suggesting strategy changes.
- Keep diffs minimal and local to the task.
- Ask one brief question only if ambiguity creates material risk.

Key paths:
- Engine: src/engine/ (lazarus.py, learning_engine.py, self_regulation.py)
- Scanner: src/scanner/ (scanner_coordinator.py, whale_watcher.py)
- Finance: src/finance/ (fund_splitter.py, tax_vault.py)
- Data: src/data/ (db_adapter.py, data_integrity.py)
- Tests: tests/unit/, tests/integration/
- Docs: docs/ai-onboarding/
```

---

## TASK CARD TEMPLATE

One per unit of work. Fill in and paste after the Core Contract.

```
TASK: [short title]
SCOPE: [which files to touch — use path::symbol references]
OUT OF SCOPE: [what NOT to change]
INSPECT FIRST: [files/symbols to read before editing]
ACCEPT: [measurable done criteria]
VERIFY: [specific commands to run after]
```

---

## MODE PACKS

Activate one per session if the task has domain-specific rules.

### MODE: engine
```
- All parameter changes must go through bot_config table, not hardcoded.
- 7-tier exit system must not be modified without explicit approval.
- Paper trading mode must be maintained until Stoic Gate clears.
- Any filter change requires before/after trade comparison.
```

### MODE: deploy
```
- Cowork CANNOT SSH to the server — scripts must be self-contained.
- Use base64-embedded deployment scripts following lazarus_deploy_template.sh.
- Always backup target files before patching.
- Syntax check -> restart -> health check -> rollback on failure.
```

### MODE: data
```
- DB writes must be idempotent (ON CONFLICT).
- All timestamps in UTC ISO 8601 format.
- Never modify bot_config/dynamic_config tables directly — use deploy scripts.
- Data integrity checks: 5-layer protection (schema, constraint, runtime, cross-table, temporal).
```

### MODE: ml
```
- Feature extraction must match training schema exactly.
- Model files (lazarus_model.json) are versioned artifacts.
- Predictions are advisory — never auto-execute trades from ML output alone.
```

### MODE: infra
```
- Docker builds target Python 3.12-slim.
- GCP Artifact Registry for image storage.
- systemd manages lazarus and lazarus-dashboard services.
- Dashboard runs on port 8443 (HTTPS).
```

---
*Modeled after Ceal Runtime Prompts pattern*
