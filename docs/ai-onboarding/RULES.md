# Lazarus — Engineering Rules

> These rules apply to ALL AI assistants working on Lazarus (Claude, Codex, Gemini). They exist because each one was learned the hard way.

## Non-Negotiable Rules

### 1. READ before WRITE
Before modifying ANY file, read it first. Never assume file contents. Files may have been modified by another AI assistant or by Josh since your last session.

### 2. No Full File Rewrites
Never overwrite lazarus.py, learning_engine.py, or self_regulation.py wholesale. Always patch with targeted changes. Use deployment scripts with backup → patch → syntax check → restart → health check → rollback on failure.

### 3. Python 3.12 Target
The server venv is Python 3.12 at `/home/solbot/lazarus/venv`. Use `/home/solbot/lazarus/venv/bin/python3 -m py_compile [filename]` to verify syntax after every patch.

### 4. EnvLoader — Never python-dotenv
Always use the custom EnvLoader class. `python-dotenv` breaks on quoted `.env` values. The `.env` file uses the EnvLoader pattern already in lazarus.py.

### 5. curl_get() for External HTTP
All external API calls (DexScreener, Birdeye, CoinGecko, etc.) MUST use the `curl_get()` subprocess wrapper. `aiohttp` fails silently for external APIs. `aiohttp` is ONLY for RPC calls (Helius) and Jupiter internal Solana calls.

### 6. VersionedTransaction Signing
Use `VersionedTransaction(tx.message, [KP])` — the `.sign()` method was removed from the solders library. This will cause silent failures if done wrong.

### 7. skipPreflight Must Be True
For all memecoin swap transactions via Jupiter, `skipPreflight` must be set to `True`. Preflight simulation rejects many legitimate memecoin transactions.

### 8. Jupiter Endpoint
Use `public.jupiterapi.com` — the old `quote-api.jup.ag` is deprecated and will return errors.

### 9. DexScreener for Scanning
Use DexScreener free API for token scanning. Birdeye Standard plan only returns 20 large caps and is rate-limited. DexScreener has no key requirement.

### 10. Three-Place Config Update
Any configuration change must be updated in THREE places:
1. `CFG` dict in lazarus.py (code defaults)
2. `bot_config` table in lazarus.db (runtime source of truth)
3. `DEFAULTS` dict in config_reader if it exists

The bot_config DB table overrides code defaults at runtime. The dynamic_config table (written by learning engine) overrides bot_config.

### 11. Fail-Closed Scanner
All signals must initialize as `fail = "unchecked"`. Rejection is the default. Access to the trade execution loop requires explicit, successful validation through every filter.

### 12. JIT Final Gate
All "Buy" logic must include a Just-In-Time (JIT) re-verification of DexScreener data at the millisecond of execution. Never trust cached scanner data.

### 13. Stoic Gate
MIN_TRADES = 20. No "Logic Shifts" or "Regime Changes" in the Learning Engine until a 20-trade sample is reached. Currently cleared (25+ trades as of 2026-04-03).

### 14. Latency Tax Audit
Every proposed network call or logic loop must be analyzed for millisecond cost. If a fix adds >200ms of blocking delay, propose an asynchronous alternative.

### 15. No Secrets in Code
Never hardcode API keys, wallet private keys, or credentials. All secrets load from `.env` via EnvLoader. The `.env` file path is `/home/solbot/lazarus/.env`. NEVER expose its contents.

### 16. Deployment Script Template
All patches must use the `lazarus_deploy_template.sh` pattern: Backup → patch → syntax check (py_compile) → restart service → health check (30s log) → rollback on failure. No bare patches.

### 17. Timestamp Format
The trades table stores timestamps as ISO text with timezone (e.g., `2026-04-03T21:20:10.705648+00:00`). The V3.1 epoch is `2026-03-29T17:44:00`. All epoch comparisons must use text comparison against this format, NOT `strftime('%s',...)` which converts to unix integers and breaks against ISO text.

## Rules Learned from Incidents

### The DB Config Override Bug
**What happened**: v3 deploy updated hardcoded CFG values but not the bot_config DB table. Bot ran with stale v2 values for 8+ hours (0 candidates).
**Rule**: Always check and update bot_config table when changing configuration. DB is runtime source of truth, not code.

### The Epoch Format Mismatch
**What happened**: V3.1 epoch was set in space format (`2026-03-29 17:44:00`) but DB writes T-format ISO timestamps. In SQLite string comparison, T (0x54) > space (0x20), causing 2 pre-epoch trades to leak into learning engine.
**Rule**: All epoch/timestamp comparisons must use T-format ISO to match what the DB writes.

### The Ghost Trade Bug
**What happened**: Learning engine had no MIN_TRADES gate, kept poisoning dynamic_config from stale v2 data. Self-regulation entered death spiral (wr=0% from 5 trades → immediate pause on every restart).
**Rule**: Ghost Trap (CFG type verification at startup) + Stoic Gate (20-trade minimum) + epoch filter prevent data poisoning.

### The aiohttp Silent Failure
**What happened**: `aiohttp` returned empty responses for external API calls without raising exceptions. Caused 80% of trades to exit as stale_timeout.
**Rule**: All external HTTP must use curl_get() subprocess. aiohttp is ONLY for RPC + Jupiter.

### The DexScreener Price Fallback
**What happened**: Birdeye Standard plan doesn't cover small memecoins, returning price=0. Caused 80% of trades to exit as stale_timeout at -5%.
**Rule**: DexScreener price fallback when Birdeye returns 0, every 3rd check.

### The Epoch Query Data Leak (2026-04-03)
**What happened**: SQL queries used `strftime('%s','2026-03-29 17:44:00')` to compare against the timestamp column. Since timestamp stores ISO text strings starting with "2026..." and strftime returns unix integers starting with "1743...", the string comparison "2026..." >= "1743..." was always TRUE, matching ALL 179 trades instead of just the 25 post-epoch trades.
**Rule**: NEVER use `strftime('%s',...)` against ISO text timestamp columns. Use direct text comparison: `timestamp >= '2026-03-29T17:44:00'`.

## Files That Must Not Be Modified Without Explicit Permission

These files are architecturally load-bearing. Changing them without understanding the full dependency chain will break downstream systems:

| File | Why |
|------|-----|
| lazarus.py | Core engine — 1,800+ lines, surgical patches only |
| learning_engine.py | Self-learning module — affects dynamic_config |
| self_regulation.py | Regime switching — ALLOWED_KEYS whitelist prevents parameter poisoning |
| .env | Credentials — NEVER read, expose, or modify |

## Protected Server Files
- `/home/solbot/lazarus/lazarus.py` — ACTIVE engine
- `/home/solbot/lazarus/learning_engine.py` — self-learning
- `/home/solbot/lazarus/self_regulation.py` — regime switching
- `/home/solbot/lazarus/.env` — credentials
- `/home/solbot/lazarus/logs/lazarus.db` — trade database (backup before any schema change)
