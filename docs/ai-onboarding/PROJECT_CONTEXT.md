# Moss Lane — Project Context

> **Read this first.** This document gives any AI assistant the full context needed to work on Moss Lane without hallucinating, duplicating files, or breaking existing functionality. Upload this at session start if the task is non-trivial.

---

## What Is Moss Lane?

Moss Lane is the overall project (the journey, learning, personal growth) named after the area around Man City's old Maine Road ground — quiet confidence, no flash, just grinding. **Lazarus is the trading bot engine inside it** (the comeback, the fight), named for City's fall to the third division and resurrection, also an Oasis deep cut.

Lazarus is an autonomous Solana memecoin trading bot running in High-Velocity Paper Mode ($10k virtual capital). It scans new token listings, applies real-time filters (change %, liquidity), executes entry and exit logic with latency tracking, and learns from every trade to improve future decisions.

**It is also a portfolio piece.** Every architectural decision, test, and deployment choice is designed to be defensible in a technical interview for roles at Stripe, Datadog, Google, and similar companies.

---

## Owner

- **Name:** Josh Hillard
- **Location:** Boston, MA
- **Background:** 6+ years at Toast (Manager II, Technical Escalations). Identified firmware defects saving an estimated $12M. Recognized by CEO at company-wide event.
- **Current status:** Career transition (since Oct 2025). Building Moss Lane + Ceal (career signal engine) as portfolio projects targeting Google L5 TPM, Stripe/Datadog TSE.
- **Learning style:** Not code-literate. Needs paste-ready commands and clear "why" explanations. Every session is both delivery and learning.
- **Certifications:** Google AI Essentials (2026), Google PM cert (3/7 in progress)

---

## Repository

- **GitHub:** `https://github.com/joshuahillard/moss-lane`
- **Branch:** `main`
- **Local path:** `C:\Users\joshb\Documents\Claude\Projects\Moss-Lane\github-repo`
- **Language:** Python 3.12 (venv at `/home/solbot/lazarus/venv` on server)
- **Server:** Vultr NJ | IP: `64.176.214.96`
- **SSH:** `ssh -i $HOME\sol_new root@64.176.214.96`
- **Dashboard:** `https://64.176.214.96:8443`
- **Wallet:** `8ioMoqLiscTBqKJAYmVpNqy3iCSxXHYcbFfgBsiYJMdm`
- **RPC:** `https://mainnet.helius-rpc.com/?api-key=<HELIUS_API_KEY>` (loaded from .env)

---

## Current State (Snapshot as of April 4, 2026)

- **Mode:** PAPER (High-Velocity Paper Mode since 2026-03-29)
- **Version:** v3.1 — epoch 2026-03-29T17:44:00
- **Stoic Gate:** Cleared at 25 trades (PF 1.73, +43.54% cumulative)
- **Original filters:** 50% WR, +39.52% — the money maker
- **Wide-net filters:** 26.7% WR, +4.02% — high volume, marginal return
- **Learning engine:** Active — dynamic_config: stop_loss=0.94, position_pct=0.15
- **Virtual capital:** $10,000 | Real wallet: ~$103
- **Next milestone:** Revert to tight filters → Go-Live decision gate

---

## Architecture

### Server File Structure (`/home/solbot/lazarus/`)

The live engine runs flat — no src/ nesting on the server.

```
/home/solbot/lazarus/
├── lazarus.py              # ACTIVE Lazarus engine (v3.1) — surgical patches only
├── learning_engine.py      # Self-learning module — epoch-gated
├── self_regulation.py      # Regime switching — ALLOWED_KEYS whitelist
├── .env                    # Credentials (NEVER expose or read)
├── logs/
│   ├── lazarus.db          # SQLite trade database (WAL mode)
│   └── fort_v2.log         # Live log
└── backup_*/               # Pre-deploy backups (always created before patching)
```

### Local Project Structure (`Moss-Lane/`)

```
Moss-Lane/
├── docs/                        # Human-facing docs (not model input)
│   ├── ai-onboarding/           # ← YOU ARE HERE
│   │   ├── PROJECT_CONTEXT.md   # Architecture, file tree, schema (this file)
│   │   ├── RULES.md             # All engineering rules with incident history
│   │   ├── PERSONAS.md          # 7 stakeholder personas
│   │   ├── CLAUDE_SYSTEM_PROMPT.md
│   │   ├── CODEX_SYSTEM_PROMPT.md
│   │   └── GEMINI_SYSTEM_PROMPT.md
│   ├── prompts/                 # Runtime prompt system
│   │   ├── MOSS_LANE_MASTER_PROMPT.md  # ← Unified instruction block (paste into project)
│   │   ├── RUNTIME_PROMPTS.md          # Core Contract + Task Cards + Mode Packs
│   │   ├── MASTER_PROMPT_ARCHITECTURE.md
│   │   ├── PORTABLE_PERSONA_LIBRARY.md
│   │   └── PROMPT_REGISTRY.md
│   ├── templates/
│   │   ├── SPRINT_TEMPLATE.md
│   │   ├── PROJECT_LEDGER_TEMPLATE.md
│   │   └── DEBRIEF_TEMPLATE.md
│   ├── session_notes/           # Morning briefings, standups, weekly reviews
│   ├── sprints/                 # Sprint docs
│   └── MOSS_LANE_PROJECT_LEDGER.md  # Canonical timeline and decision log
├── github-repo/                 # Git repo — syncs to GitHub
│   └── (see GitHub Repo Structure below)
├── career/                      # Resumes, cover letters, job applications
├── deliverables/                # Finished outputs for sharing
├── brand/                       # Brand book, brand assets
├── ops/
│   ├── handoffs/                # Session handoff docs
│   ├── briefings/               # Morning briefings
│   ├── trades/                  # Trade analysis files
│   ├── config/                  # Config snapshots
│   ├── reports/                 # Performance reports
│   └── logs/                    # Session logs
├── deploy/                      # Deployment scripts (Windows-side copies)
└── archive/                     # Retired docs and scripts
```

### GitHub Repo Structure (`github-repo/`)

```
moss-lane/
├── src/
│   ├── engine/
│   │   ├── lazarus.py               # Engine — canonical reference copy
│   │   ├── learning_engine.py       # Self-learning module
│   │   ├── self_regulation.py       # Regime switching
│   │   └── fort_v2_clean.py         # Pre-v3 archive (reference only)
│   ├── scanner/
│   │   ├── scanner_coordinator.py   # 4-state wallet lifecycle, round-robin routing
│   │   └── whale_watcher.py         # Jupiter WS wallet scanner (20k+ wallets)
│   ├── finance/
│   │   ├── fund_splitter.py         # Multi-wallet capital distribution
│   │   ├── tax_vault.py             # 15% profit skim, accumulate-and-batch
│   │   └── wallet_generator.py      # 5 executor keypairs + tax vault
│   ├── data/
│   │   ├── db_adapter.py            # PostgreSQL adapter (Cloud SQL)
│   │   ├── data_integrity.py        # 5-layer startup assertions
│   │   └── migrate_sqlite_to_pg.py  # SQLite → PostgreSQL migration
│   ├── ml/
│   │   ├── vertex_train.py          # Vertex AI training pipeline
│   │   ├── vertex_predict.py        # Prediction pipeline
│   │   └── vertex_feature_extract.py
│   └── utils/
│       └── load_test.py
├── tests/
│   ├── unit/
│   │   ├── test_foundation.py       # Engine unit tests
│   │   └── test_fund_splitter.py    # 36 tests — all passing
│   └── integration/                 # DB-backed integration tests (planned)
├── deploy/                          # 14 deployment scripts (base64-embedded)
│   ├── lazarus_deploy_template.sh   # Master deploy template — all patches use this
│   ├── deploy_v3.sh                 # v3.0 initial deploy
│   ├── deploy_phase2.sh             # v3.1 Phase 2 deploy
│   ├── deploy_data_integrity.sh     # 5-layer integrity deploy
│   ├── deploy_dispatcher_modules.sh # Dispatcher pipeline deploy
│   └── (9 more)
├── docs/
│   ├── ai-onboarding/               # MODEL INPUT — upload at session start
│   ├── prompts/                     # Runtime prompt system
│   ├── templates/                   # Sprint, ledger, debrief templates
│   ├── build-log/                   # Sprint retrospectives
│   ├── architecture.md
│   ├── brand-book.md
│   └── team-architecture.md
├── CLAUDE.md                        # Claude Code custom instructions
├── README.md
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── requirements.txt
├── lazarus_model.json               # Vertex AI model artifact
└── lazarus_model_meta.json
```

---

## What's Shipped vs. Planned

| Component | Status | Notes |
|-----------|--------|-------|
| Lazarus v3.0 Engine | ✅ Live on server | Full rewrite, deployed 2026-03-28 |
| v3.1 Phase 2 Paper Mode | ✅ Live on server | $10k virtual, Stoic Gate, Ghost Trap, fail-closed |
| Wide-Net Data Collection | ✅ Live on server | filter_regime tagging, chg 5-120%, liq $30k |
| 5-Layer Data Integrity | ✅ Live on server | All 6 startup assertions pass |
| Dispatcher Pipeline (5 modules) | ✅ Built, not deployed | scanner_coordinator, fund_splitter, tax_vault, wallet_generator, lazarus patches |
| Whale Watcher | ✅ Built, not deployed | Jupiter WS, 20k+ wallets, zero API cost |
| Docker | ✅ Built, not deployed | Dockerfile, docker-compose, entrypoint.sh |
| Vertex AI ML Pipeline | ✅ Built, not deployed | Feature extract, train, predict |
| Tiered Take Profit | 📋 Planned | Sell half at +25%, trail rest — post-Stoic Gate upgrade |
| Dev Wallet Analysis | 📋 Planned | Rug pull pre-filter |
| Market Regime Detection | 📋 Planned | Ties to Vertex AI |
| GCP Cloud Run | 📋 Planned | Apr 5-9 target |
| Go-Live (real money) | 📋 Planned | After tight-filter revert + GCP validation |

---

## Database Schema (SQLite — `lazarus.db`)

**Config hierarchy (highest wins):** `dynamic_config` → `bot_config` → hardcoded `CFG` dict

**Core tables:**

`trades` — Every buy and sell event
- Key columns: `id`, `timestamp` (TEXT, ISO T-format e.g. `2026-04-03T21:20:10.705648+00:00`), `symbol`, `token_address`, `wallet`, `side`, `entry_price_sol`, `exit_price_sol`, `size_usd`, `pnl_usd`, `pnl_pct`, `exit_reason`, `latency_ms`, `paper`, `filter_regime`

`bot_config` — Runtime configuration (overrides hardcoded CFG at startup)
`dynamic_config` — Learning engine overrides (overrides bot_config; ALLOWED_KEYS whitelist enforced)
`balance_snapshots` — Portfolio tracking over time
`tax_vault_ledger` — Tax vault accumulation log (dispatcher, not yet deployed)

**Critical query rule:** Always use text comparison for epoch filtering:
```sql
WHERE timestamp >= '2026-03-29T17:44:00'
```
Never use `strftime('%s', ...)` against ISO text columns — it always returns TRUE.

---

## Current Configuration (from `bot_config` + `dynamic_config` as of 2026-04-03)

| Parameter | bot_config | dynamic_config override | Notes |
|-----------|-----------|------------------------|-------|
| `min_chg_pct` | 5.0 | — | Wide-net (tight: 10-20) |
| `max_chg_pct` | 120.0 | — | Wide-net (tight: 80) |
| `min_liq` | 30,000 | — | Wide-net (tight: 50,000) |
| `stop_loss` | 0.92 | 0.94 | Learning engine tightened |
| `take_profit` | 1.25 | — | +25% |
| `trail_arm` | 1.08 | — | +8% |
| `position_pct` | 0.15 | 0.15 | 15% of virtual capital |

---

## Services (systemd on server)

- **lazarus** — auto-restarts, runs Lazarus engine (`lazarus.py`)
- **sol-fortress-dashboard** — runs on port 8443 (TD-001: rebrand pending)

---

## Deployment Model

- **Cowork / Claude in browser:** CANNOT SSH to server. Creates self-contained deployment scripts (base64-embedded). Josh runs SCP from PowerShell, then executes on server via SSH.
- **Claude Code / Codex:** Can work directly on `github-repo/` via git.
- **All server patches:** Must follow `deploy/lazarus_deploy_template.sh` pattern: backup → patch → py_compile → restart → health check → rollback on failure.
- **Three-place config rule:** Any config change goes in CFG dict (code) + bot_config table (DB) + DEFAULTS dict.

---

## Key Docs (upload at session start when relevant)

| File | Purpose | When to upload |
|------|---------|---------------|
| `docs/ai-onboarding/PROJECT_CONTEXT.md` | This file — architecture overview | Non-trivial tasks |
| `docs/ai-onboarding/RULES.md` | Engineering rules + incident history | Engine/deploy tasks |
| `docs/prompts/MOSS_LANE_MASTER_PROMPT.md` | Unified instruction block | New AI sessions |
| `docs/prompts/RUNTIME_PROMPTS.md` | Core Contract + Task Cards + Mode Packs | Claude Code sessions |
| `docs/prompts/PORTABLE_PERSONA_LIBRARY.md` | Full persona definitions | Planning mode |
| `docs/MOSS_LANE_PROJECT_LEDGER.md` | Timeline, decisions, retrospectives | Strategy sessions |

---

## Goal

$20,000 from current ~$103 real balance. Paper mode validation active. Go-Live target: April 26-28 on GCP Cloud Run.
