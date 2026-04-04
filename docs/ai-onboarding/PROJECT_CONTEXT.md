# Moss Lane — Project Context

> **Read this first.** This document gives any AI assistant the full context needed to work on Moss Lane without hallucinating, duplicating files, or breaking existing functionality.

## What Is Moss Lane?

Moss Lane is the overall project (the journey, learning, personal growth) named after the area around Man City's old Maine Road ground. **Lazarus is the trading bot engine inside it** (the comeback, the fight), named for City's fall to the third division and resurrection.

Lazarus is an autonomous Solana memecoin trading bot running in High-Velocity Paper Mode ($10k virtual capital). It scans new token listings, applies real-time filters (change %, liquidity), executes entry and exit logic with latency tracking, and learns from every trade to improve future decisions.

**It is also a portfolio piece.** Every architectural decision, test, and deployment choice is designed to be defensible in a technical interview for roles at Stripe, Datadog, Google, and similar companies.

## Owner

- **Name**: Josh Hillard
- **Location**: Boston, MA
- **Background**: 6+ years at Toast (Manager II, Technical Escalations). Saved Toast an estimated $12M identifying firmware defects. Recognized by CEO at company-wide event.
- **Current status**: Career transition (since Oct 2025). Building Moss Lane + Céal (career signal engine) as portfolio projects.
- **Learning style**: Not code-literate. Needs paste-ready commands. Explain the "why" behind decisions. Treats every session as delivery + learning.
- **Certifications**: Google AI Essentials (2026), Google PM cert (3/7 in progress)

## Repository

- **GitHub**: `https://github.com/joshuahillard/moss-lane.git`
- **Branch**: `main`
- **Language**: Python 3.12 (venv at `/home/solbot/lazarus/venv` on server)
- **Server**: Vultr NJ | IP: `64.176.214.96`
- **SSH**: `ssh -i $HOME\sol_new root@64.176.214.96`
- **Dashboard**: `https://64.176.214.96:8443`
- **Wallet**: `8ioMoqLiscTBqKJAYmVpNqy3iCSxXHYcbFfgBsiYJMdm`
- **RPC**: `https://mainnet.helius-rpc.com/?api-key=<HELIUS_API_KEY>`

## Current Architecture (v3.1 Post-Stoic Gate)

### Server File Structure (/home/solbot/lazarus/)

```
/home/solbot/lazarus/
├── lazarus.py              # ACTIVE Lazarus engine (v3.1)
├── learning_engine.py      # Self-learning module (v3.0 clean)
├── self_regulation.py      # Regime switching (ALLOWED_KEYS whitelist)
├── .env                    # Credentials (NEVER expose)
├── logs/
│   ├── lazarus.db          # SQLite trade database
│   └── fort_v2.log         # Live log
└── backup_*/               # Pre-deploy backups
```

### Local Project Structure (C:\Users\joshb\Documents\Claude\Projects\Moss-Lane)

```
Moss-Lane/
├── docs/
│   └── ai-onboarding/      # ← YOU ARE HERE
├── github-repo/             # Git repo (syncs to GitHub)
│   ├── lazarus.py           # Clean copy of engine
│   ├── learning_engine.py
│   ├── self_regulation_clean.py
│   ├── db_adapter.py        # PostgreSQL adapter
│   ├── fund_splitter.py     # Multi-wallet dispatcher
│   ├── scanner_coordinator.py
│   ├── tax_vault.py
│   ├── whale_watcher.py     # Jupiter WS wallet scanner
│   ├── vertex_*.py          # Vertex AI ML pipeline (train/predict/extract)
│   ├── wallet_generator.py
│   ├── test_foundation.py
│   ├── test_fund_splitter.py
│   ├── Dockerfile
│   ├── docker-compose.yml
│   ├── entrypoint.sh
│   ├── requirements.txt
│   ├── engine/              # Engine package (lazarus, learning, self_reg)
│   └── docs/                # Architecture docs, brand book, build logs
├── PY/                      # Python source files (working copies)
├── Shell Script/            # Deployment scripts
├── MD/                      # Markdown docs (architecture, brand, handoffs, etc.)
├── trades/                  # Trade analysis files
├── logs/                    # Session logs
└── reports/                 # Performance reports
```

## What's Shipped vs. What's Planned

| Component | Status | Notes |
|-----------|--------|-------|
| Lazarus v3.0 Engine | ✅ Shipped | Full rewrite from v2, deployed 2026-03-28 |
| v3.1 Phase 2 (Paper Mode) | ✅ Shipped | $10k virtual, Stoic Gate, Ghost Trap, fail-closed |
| Wide-Net Data Collection | ✅ Shipped | Wider filters for paper mode data, filter_regime tagging |
| Sniper Exit (60s) | ✅ Shipped | Cuts non-runners early |
| Epoch Gate Filter | ✅ Shipped | Prevents pre-v3 data from poisoning learning |
| Dispatcher Pipeline | ✅ Built (not deployed) | 5 modules: scanner_coordinator, fund_splitter, tax_vault, wallet_generator, lazarus patches |
| Whale Watcher | ✅ Built (not deployed) | Jupiter WS wallet scanner, 20k+ wallets |
| Docker + GCP | ✅ Built (not deployed) | Dockerfile, docker-compose, Cloud Run prep |
| Vertex AI ML | ✅ Built (not deployed) | Feature extraction, training, prediction pipeline |
| Tiered Take Profit | 📋 Planned | Sell half at +25%, trail rest (post-Stoic Gate #1) |
| Dev Wallet Analysis | 📋 Planned | Rug pull pre-filter (post-Stoic Gate #2) |
| Market Regime Detection | 📋 Planned | Ties to Vertex AI (post-Stoic Gate #3) |
| Go-Live (real money) | 📋 Planned | After validation + tight filter revert |

## Database Schema (SQLite — lazarus.db)

**Core tables**:

- **trades**: `id`, `timestamp` (TEXT ISO format), `symbol`, `token_address`, `wallet`, `side`, `entry_price_sol`, `exit_price_sol`, `size_usd`, `pnl_usd`, `pnl_pct`, `tax_swept_usd`, `exit_reason`, `latency_ms`, `session`, `paper`, `hour_utc`, `day_of_week`, `address`, `source`, `score`, `hourly`, `chg_pct`, `mc`, `liq`, `peak_pnl_pct`, `filter_regime`
- **bot_config**: Key/value config (runtime source of truth, overrides hardcoded CFG)
- **dynamic_config**: Learning engine overrides (overrides bot_config)
- **balance_snapshots**: Portfolio tracking

## Current Mode

- **PAPER**: True (High-Velocity Paper Mode since 2026-03-29)
- **Virtual Capital**: $10,000
- **Real Wallet**: ~$103
- **V3.1 Epoch**: 2026-03-29T17:44:00

## Current Configuration (from bot_config as of 2026-04-03)

| Parameter | Value | Notes |
|-----------|-------|-------|
| `min_chg_pct` | 5.0 | Wide-net (original: 10–20) |
| `max_chg_pct` | 120.0 | Wide-net (original: 80) |
| `min_liq` | 30,000 | Wide-net (original: 50,000) |
| `stop_loss` | 0.92 | −8% (dynamic_config overrides to 0.94 = −6%) |
| `take_profit` | 1.25 | +25% |
| `trail_arm` | 1.08 | +8% |
| `position_pct` | 0.15 | 15% of virtual capital |

## Services (systemd on server)

- **lazarus** — auto-restarts, runs Lazarus engine (lazarus.py)
- **sol-fortress-dashboard** — runs on port 8443

## Deployment Model

- Cowork/Claude Code creates deployment scripts or direct patches
- Claude Code and Codex can work on the github-repo directly (git-based)
- For server changes: deployment scripts with backup → patch → syntax check → restart → health check → rollback on failure
- Server deployment template: `Shell Script/lazarus_deploy_template.sh`

## Goal

$20,000 from current ~$103 real balance. Paper mode validation in progress.
