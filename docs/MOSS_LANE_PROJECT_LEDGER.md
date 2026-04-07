# Moss Lane Project Ledger
**Canonical Timeline, Decision Log & Sprint Retrospectives**
*Owner: Josh Hillard | Created: April 4, 2026 | Living document — update after every sprint*

---

## How to Use This Document

This is the single source of truth for Moss Lane's history, decisions, and lessons learned. Update after every sprint: append a timeline entry, log any architectural decisions, add a retrospective. If a previous decision is reversed, update the original entry with a "Superseded by" note rather than deleting it.

---

## Project Timeline

### Phase 0 — Project Inception (Early March 2026)

**What happened:** Josh Hillard, transitioning from 6+ years at Toast (Manager II, Technical Escalations), started building an autonomous Solana memecoin trading bot as a portfolio project. The original project was called "Sol-Fortress" running as fort_v2.py. The goal: turn ~$250 starting capital into $20,000 while building demonstrable technical skills in Python, Linux, databases, APIs, and DevOps for career targeting (Google L5 TPM, Stripe/Datadog TSE).

**Infrastructure:** Vultr NJ VPS, Python 3.12, SQLite, DexScreener + Jupiter + Birdeye APIs. Dashboard on port 8443.

**Initial approach:** DexScreener momentum scanning + copy trading + self-learning signal weights.

### v2 Era — The Five Root Causes (March 2026)

**What went wrong:** The original v2 engine had five compounding failure modes:
1. Buying tokens already up 100-700% (filter window too high)
2. Re-entering losers repeatedly (no proper cooldown)
3. Learning engine writing 3% position sizes (killed trade profitability)
4. Self-regulation death spiral (recovery mode opened filters to garbage tokens)
5. Live sell bug (used SOL lamports instead of token outAmount)

**Lesson:** Every one of these is now a named rule or gate in v3. The failures were diagnostic, not emotional.

### Lazarus v3.0 — The Clean Rewrite (2026-03-28)

**Deployed:** 2026-03-28 04:53 UTC via deploy_v3.sh (base64-embedded deployment script).
**What shipped:**
- lazarus.py (1,254 lines) — clean rewrite with unified monitor loop, address-based tracking, hard floor
- learning_engine.py (164 lines) — fixed position sizing (10-25% range), no auto-execute on import
- self_regulation.py (386 lines) — ALLOWED_KEYS whitelist, can only modify regime_mode and scan_pause_until
- Old files backed up to /home/solbot/lazarus/backup_20260328_045326

**Mode:** PAPER. 24-hour validation window started.
**Effort:** Very High

### Project Rebrand — Moss Lane / Lazarus (2026-03-28)

**What happened:** Sol-Fortress rebranded to reflect Josh's identity and values.
- **Moss Lane** = the overall project (the journey, learning, personal growth). Named after the area around Man City's old Maine Road ground — quiet confidence, no flash, just grinding.
- **Lazarus** = the trading bot engine (the comeback, the fight). Named for City's fall to the third division and resurrection, also an Oasis deep cut.

**Server paths updated:** /home/solbot/fortress → /home/solbot/lazarus. Service: lazarus. DB: lazarus.db. Entry: lazarus.py.

### Hotfixes & Tuning (2026-03-28)

**What shipped:**
- 60s sniper exit deployed (cuts non-runners early)
- 3s monitor interval (from 5s)
- min_chg 20%, min_liq $50k deployed to all 3 config layers
- DB Config Override Bug discovered and fixed (bot_config table was overriding v3 code with stale v2 values)
- Epoch Format Mismatch discovered (space vs T-format in timestamps)

**Incident — DB Config Override:**
v3 deploy updated hardcoded CFG values but not the bot_config DB table. Bot ran with stale v2 values for 8+ hours (0 candidates). Rule established: bot_config DB is runtime source of truth. Always update all 3 layers.

**Artifacts:** Master Brand Book, Lazarus Architecture document completed.

### v3.1 Phase 2 — High-Velocity Paper Mode (2026-03-29)

**Deployed:** 2026-03-29 via combined patch.
**What shipped:**
- $10,000 virtual capital (up from real wallet)
- Self-regulation disabled in paper mode
- Stoic Gate (MIN_TRADES = 20) — no logic shifts until sample size reached
- Fail-closed scanner, Ghost Trap (CFG type verification at startup)
- DexScreener price fallback, persistent paper balance
- V3.1 epoch set: 2026-03-29T17:44:00

**Incident — Epoch Format Mismatch:**
V3.1 epoch was stored with space format ("2026-03-29 17:44:00") but DB writes T-format ISO timestamps. In SQLite string comparison, "T" (0x54) > " " (0x20), causing 2 pre-epoch trades to leak into learning engine. Fixed across all 3 files.

**Effort:** High

### Week Sprint: Mar 30 – Apr 3

**2026-03-30:**
- Weekly review + performance analysis
- Epoch format fix deployed across all 3 files
- Standup system established

**2026-03-31:**
- 5 job applications shipped
- Ceal sprint accelerated by 4 weeks
- Lazarus Day 3 in watch mode
- Evening wrap-up protocol established

**2026-04-01 — Wide-Net Paper Mode:**
- Scanner widened (chg 5-120%, liq $30k, cooldown 1hr) for data collection
- filter_regime tagging added (original vs wide_net_v1)
- Exit chain untouched (locked)
- Roadmap reordered: Infrastructure (Docker/GCP) before Go-Live
- Whale Watcher architecture designed (Jupiter WS, 20k+ wallets)
- Google CE application submitted

**2026-04-02 — Dispatcher Pipeline:**
- Full 5-module pipeline built: scanner_coordinator, fund_splitter, tax_vault, wallet_generator, lazarus.py patches
- 36 tests for fund_splitter (all passing)
- Feature-flagged, not yet deployed
- Ceal Sprint 4 shipped (Docker + Jobs fix, 208 tests)

**2026-04-03 — Stoic Gate Cleared:**
- 25 post-epoch sells confirmed. PF 1.73, +43.54% cumulative
- Original filters: 50% WR, +39.52% (the money maker)
- Wide-net filters: 26.7% WR, +4.02% (marginal)
- Learning engine activated: dynamic_config now has stop_loss=0.94
- 3 job applications (WHOOP, Avoca, Meta)

**Incident — Epoch Query Data Leak (2026-04-03):**
SQL queries used strftime('%s','2026-03-29T17:44:00') to compare against the timestamp column. Since timestamp stores ISO text strings starting with "2026..." and strftime returns unix integers starting with "1743...", the string comparison was always TRUE — matching ALL 179 trades instead of just 25 post-epoch. Made performance look like -690% instead of real +43.54%. Rule established: NEVER use strftime('%s') against ISO text columns.

**2026-04-04 — Documentation & Architecture:**
- 5-layer data integrity protection deployed to server (all 6 startup assertions passed)
- Prompt Architecture v1.0 adopted (Core Contract + Task Card + Mode Pack)
- 8-Pillar sprint framework migrated from Ceal to Moss Lane
- Moss Lane folder restructured (career/, deliverables/, brand/, ops/, deploy/, archive/)
- Full doc suite created (this ledger, unified instruction block, persona library)

**2026-04-07 — Framework Backfill & Truth Audit:**
- Governance, Program-Management, Foundations, design-docs, pipeline, and handoff golden corpus framework backfilled for Moss Lane using the LLM Model project structure
- New strategy kit created for Moss Lane
- Documentation explicitly separated `deployed`, `repo-built`, and `planned` capability so the project story matches runtime truth
- Local validation gap recorded: `pytest` collection currently breaks because `test_foundation.py` exits during collection and expects dependencies/secrets not present in the local environment
- Current-state docs anchored to the latest available workspace evidence rather than inferred future status

---

## Architecture Decision Log

| # | Decision | Date | Context | Alternatives Considered | Status |
|---|----------|------|---------|------------------------|--------|
| ADR-1 | DexScreener over Birdeye for scanning | 2026-03 | Birdeye Standard only returns 20 large caps | Birdeye Pro ($$$), CoinGecko | Active |
| ADR-2 | curl_get() for external HTTP | 2026-03 | aiohttp fails silently for non-RPC calls | httpx, requests | Active |
| ADR-3 | EnvLoader over python-dotenv | 2026-03 | dotenv breaks on quoted .env values | dotenv with preprocessing | Active |
| ADR-4 | Three-place config (CFG + bot_config + DEFAULTS) | 2026-03-28 | DB Config Override Bug — stale values | Single source (code or DB) | Active |
| ADR-5 | Stoic Gate (MIN_TRADES = 20) | 2026-03-29 | Ghost Trade Bug — learning from bad data | No gate (original), 10-trade gate | Active |
| ADR-6 | ISO T-format text comparison for epochs | 2026-03-30 | Epoch Format Mismatch — T vs space in SQLite | Unix epoch integers | Active |
| ADR-7 | Infrastructure before Go-Live | 2026-04-01 | No point going live on VPS then migrating under live capital | Go-Live first, migrate later | Active |
| ADR-8 | Wide-net paper filters with regime tagging | 2026-04-01 | Need data volume to clear Stoic Gate | Keep tight filters (slower) | Active — revert to tight before Go-Live |
| ADR-9 | Feature-flagged dispatcher | 2026-04-02 | Build ahead while market frozen, zero risk | Wait for Go-Live to start | Active |
| ADR-10 | Three-layer prompt architecture | 2026-04-04 | Old sprint prompts were 5-20KB of repeated context | Single monolithic prompt | Active |
| ADR-11 | Runtime-truth labeling (`deployed` vs `repo-built` vs `planned`) | 2026-04-07 | Project now contains meaningful future-state modules that can blur current capability if not labeled clearly | Let docs imply capability from code presence alone | Active |

---

## Technical Debt Tracker

| ID | Item | Sprint Added | Severity | Status | Notes |
|----|------|-------------|----------|--------|-------|
| TD-001 | Dashboard service still named sol-fortress-dashboard | 2026-03-28 | Low | Open | Cosmetic — works fine |
| TD-002 | Old folder references in some deploy scripts | 2026-04-04 | Medium | Open | PY/ and Shell Script/ folders eliminated in restructure |
| TD-003 | Dispatcher modules not deployed or integration-tested | 2026-04-02 | High | Open | 5 modules built locally, server only has single-wallet engine |
| TD-004 | Wide-net filters active in bot_config | 2026-04-01 | High | Open | Must revert to tight filters before Go-Live |
| TD-005 | No Alembic/migration system | 2026-03 | Medium | Open | Schema changes are manual SQL |
| TD-006 | fort_v2.log still named with old convention | 2026-03-28 | Low | Open | Log file name not rebranded |

---

## Incident Log

| Date | Name | Impact | Resolution | Rule Created |
|------|------|--------|------------|-------------|
| 2026-03-28 | DB Config Override Bug | 8+ hours zero candidates | Update all 3 config layers | Rule #10 (Three-Place Config) |
| 2026-03-29 | Epoch Format Mismatch | 2 pre-epoch trades leaked into learning | T-format ISO across all files | Rule #17 (Timestamp Format) |
| 2026-03-29 | Ghost Trade Bug | Learning engine poisoned, self-reg death spiral | Stoic Gate + Ghost Trap + epoch filter | Rule #13 (Stoic Gate) |
| 2026-04-03 | Epoch Query Data Leak | Reported -690% instead of +43.54% | Text comparison, not strftime | Rule #17 addendum |

---
*Modeled after Ceal Project Ledger pattern*
