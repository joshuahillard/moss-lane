# Moss Lane — Claude Code Instructions

## Project Overview
Moss Lane is an autonomous Solana memecoin trading system. The trading engine is called **Lazarus** — a momentum-based scalper with self-learning, regime switching, and a 7-tier exit system. Currently in paper trading mode (v3.1).

## Directory Structure
```
src/
├── engine/        — Core trading logic (lazarus.py, learning_engine.py, self_regulation.py)
├── scanner/       — Token discovery (scanner_coordinator.py, whale_watcher.py)
├── finance/       — Position sizing (fund_splitter.py, tax_vault.py, wallet_generator.py)
├── data/          — Database layer (db_adapter.py, data_integrity.py)
├── ml/            — Vertex AI integration (vertex_train.py, vertex_predict.py)
└── utils/         — Shared utilities
tests/
├── unit/          — Unit tests
└── integration/   — Integration tests
deploy/            — Deployment scripts (base64-embedded, self-contained)
docs/
├── ai-onboarding/ — System prompts for Claude, Codex, Gemini
├── prompts/       — Runtime prompt system (registry, mode packs)
├── templates/     — Sprint and debrief templates
├── session_notes/ — Timestamped session logs
└── build-log/     — Build validation records
```

## Critical Rules
1. **Never overwrite lazarus.py wholesale** — always patch with targeted changes
2. **Always verify Python syntax** before restarting the service
3. **Use EnvLoader** — never use python-dotenv (breaks on quoted .env values)
4. **External HTTP must use curl_get()** — aiohttp only for RPC + Jupiter
5. **VersionedTransaction signing:** `VersionedTransaction(tx.message, [KP])`
6. **skipPreflight must be True** for memecoin swaps
7. **Jupiter endpoint:** public.jupiterapi.com (quote-api.jup.ag deprecated)
8. **DexScreener for scanning** (Birdeye Standard only returns 20 large caps)
9. **Check DB for trade results** before suggesting strategy changes
10. **Deployment scripts must be self-contained** — Cowork cannot SSH to server

## Testing
```bash
pytest tests/ --tb=short -q
```

## Linting
```bash
ruff check src/
```

## Key Conventions
- **Naming:** Moss Lane = project, Lazarus = engine
- **Stack:** Python 3.12, asyncio, aiohttp (RPC/Jupiter only), SQLite
- **Config:** All runtime config through bot_config DB table, not hardcoded
- **Commits:** Conventional commits (`feat`, `fix`, `refactor`, `docs`, `chore`)
