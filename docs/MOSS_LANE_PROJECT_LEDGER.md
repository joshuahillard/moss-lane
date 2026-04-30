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
- Ceal Sprint 6 shipped (Docker + Cloud SQL, 208 tests)

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

### Cloud Run Deployment (2026-04-08)

**Deployed:** 2026-04-08 15:23 UTC. Revision lazarus-00013-2nf serving on Cloud Run us-east1.
**What shipped:**
- Fresh Docker image (v3.1 tag) built and pushed to Artifact Registry (us-east1-docker.pkg.dev/moss-lane/lazarus/lazarus:v3.1)
- Cloud Run service deployed with Secret Manager references (SOLANA_PRIVATE_KEY, SOLANA_RPC_URL, BIRDEYE_API_KEY)
- CRLF line-ending fix added to Dockerfile (sed strip + chmod on entrypoint.sh) — self-healing for Windows→Linux builds
- Startup metrics: image import 1.22s, container healthy 2.95s, revision ready 4.84s
- Bot confirmed running: DexScreener scanned 205 tokens, 0 candidates passed filters (tight filters working)
- Scaled to min-instances=0 after verification (cost control — portfolio demo, not production)

**Issues found:**
- CRLF in entrypoint.sh caused first deploy attempt to fail (revision 00012). Fixed with Dockerfile sed line.
- Bot started in LIVE mode, not PAPER — PAPER_TRADING env var not picked up because lazarus.py reads mode from bot_config DB table (runtime source of truth), and Cloud Run has no persistent SQLite. Falls back to code default (LIVE). No trades executed ($2.66 wallet, 0 candidates). Needs fix before next Cloud Run session.
- Learning engine import failed: `No module named 'learning_engine'` — path changed to src.engine.learning_engine in package restructure. Non-critical for portfolio demo.

**Purpose:** Portfolio piece (Tier 2 credential: containerized service on GCP). VPS remains primary. Go-live still targets VPS.

**GCP infrastructure confirmed pre-existing:** Project moss-lane, Artifact Registry repo lazarus (us-east1), Secret Manager secrets (4 created 4/1-4/2), Cloud Run + AR + SM APIs enabled. All from prior 4/1 session.

**Effort:** Medium

**X-Y-Z:** "Deployed Lazarus trading engine to GCP Cloud Run, as measured by verified live revision with structured logging and 4.84s cold start, by containerizing the service with Secret Manager integration and Artifact Registry delivery."

**2026-04-15 — v3.2 Low-Volume Epoch Bump:**
- Service health check confirmed the bot was alive but filter-starved: `610` scan/candidate log lines in 6 hours, `0` entry lines, and no new trades since 2026-04-03
- Trade schema audit confirmed `trades.side` is the correct action field and that `filter_regime` is already stored on historical rows
- Live filter evidence showed persistent starvation at the first gate: roughly `118-123` of `200` tokens dying on `vol` and `62-66` dying on `chg_low` every cycle
- A legitimate runner was visibly clipped by the upper ceiling: `stoat hit 284.0% h1` while `max_chg_pct=100.0` was active
- New paper-only mini-epoch defined: `epoch_v32_lowvol` with runtime profile `min_hourly_vol=250`, `min_chg_pct=10.0`, `max_chg_pct=120.0`, `min_liq=30000`, `min_vmr=0.10`, `filter_regime=v3.2_lowvol_epoch`
- Deploy ceremony upgraded: backup + patch + py_compile + restart + health check + 2-hour rollback watch window if candidate flow stays frozen

**2026-04-16 — Phase 0 Repo Stabilization (close-out):**
- **Repo stabilized.** CRLF-only churn was removed from the working tree and isolated into a single normalization commit (`57342ab`, 16 files, zero semantic change). Line-ending policy is now enforced by `.gitattributes`.
- **Old backlog pushed.** The pre-existing local `main` commit backlog was pushed to `origin/main` (landing at `1d96c69`) before any new work resumed, so the v3.2 stabilization work sits on top of a clean base.
- **v3.2 work separated into focused commits.** Engine/runtime support (`lazarus.py`, `db_adapter.py`, `config_defaults.py` — commit `f6cd79f`) and deploy artifacts + research docs (`lazarus_deploy_v32_lowvol_epoch.sh`, two supporting wide-net deploy scripts, `WIDE_NET_V2_PLAYBOOK.md`, `WIDE_NET_V2_QUERY_PACK.sql`, repo-side ledger — commit `b816e0e`) are now independently reviewable rather than mixed into line-ending noise.
- **Canonical source-of-truth edits deferred.** No ledger-body or tracker-body edits about v3.2 performance, Stoic Gate reconciliation, or cohort numbers land in Phase 0. The repo-vs-root documentation canonicalization decision is Phase 1; the server reality check (tracker contradiction at 7/20 PF 1.42 vs memory's 25/1.73) is Phase 6; the query pack `filter_regime` schema-compatibility split is Phase 2.
- **Working branch:** `codex/stabilize-20260416` (published on origin). Snapshot preserved at `snapshot/pre-stabilize-20260416`.
- **Execution artifacts:** `docs/sprints/PHASE_0_STABILIZE_CHECKLIST_20260416.md` (Codex), `docs/sprints/PHASE_0_DOC_HANDOFF.md` (Claude cadence), `docs/sprints/PHASE_0_EXECUTION_LOG.md` (commit-by-commit audit trail).

**2026-04-16 — Phase 6 Server Reality Check (close-out):**
- **Stoic Gate contradiction resolved from production evidence.** Read-only query against a copied production SQLite DB (`/home/solbot/lazarus/logs/lazarus_phase6_readonly.db`, copied from `lazarus.db`) returned the authoritative post-epoch paper-mode result: **25 sells** since `2026-03-29T17:44:00`, gross profit **$1,239.15**, gross loss **$815.14**, **profit factor 1.520**, **net PnL $424.01**, **avg PnL 1.74%**, **win rate 36.0%**. Phase 6 pre-flight (checklist + re-baseline) committed as `eba3b8b`.
- **Schema confirmed safe for v3.2 cohort analysis.** `trades.side` and `trades.filter_regime` both exist on the production DB copy. Two Phase 1 risk-register items (query pack `filter_regime` assumption; sell-side labeling compatibility) are now closed by evidence, not assumption.
- **Tracker + memory reconciled.** `ops/config/go_live_tracker.md` gained a Day 10 2026-04-16 authoritative block citing PF 1.520. Stale memories (`project_stoic_gate_cleared.md` claiming PF 1.73, `project_stoic_gate_unverified.md` flagging the contradiction) were retired and replaced by a single `project_stoic_gate_verified.md`. The 1.73 figure was a drifted recollection of the 1.74% avg PnL; the +43.54% cumulative figure was never corroborated and is retired. Any future go-live decision note must cite PF 1.520, never 1.73.
- **Read-only boundary held.** Unlike Phase 5's commit `649a677` (which bundled a `startup_config.py` refactor inside a "test unblocking" commit), Phase 6 executed inside its scope: no writes, no migrations, no schema changes to production. Stoic Gate count threshold (20) is cleared at 25 — next gate is a go-live decision date, not more tuning. Execution artifacts: `docs/sprints/PHASE_6_SERVER_REALITY_CHECK_CHECKLIST_20260416.md` (checklist), `docs/sprints/PHASE_6_EXECUTION_LOG.md` (evidence + reconciliation audit trail). Open debt: Phase 1 SHA back-fill (port + redirect-stub commits still carry `<port commit hash — pending>` placeholders in `PHASE_1_EXECUTION_LOG.md`).
- **Cohort decomposition changed the conclusion — Sprint 7 opens under runtime-truth-first discipline.** Follow-up read-only cohort query on `lazarus_phase6_readonly.db` split the 25 sells by `filter_regime`: `original` = 10 sells / PF 2.18 / WR 50.0% / +$443.82 net, `wide_net_v1` = 15 sells / PF 0.955 / WR 26.7% / -$19.81 net, `v3.2_lowvol_epoch` = 0 sells (unvalidated). The aggregate PF 1.520 is carried by `original`; `wide_net_v1` is a net drag and is **formally rejected for go-live purposes** (permitted in paper only as a negative-control signal, not reinstatable by running totals alone). No go-live date is being set. Sprint 7 (cohort-of-record evidence, paper-mode) opens on 2026-04-16 with `original` as the single primary cohort, `v3.2_lowvol_epoch` as starvation fallback, and a gate order of runtime-truth verification (7A, six-check ceremony covering `bot_config` + `dynamic_config` + `lazarus.py` CFG + `config_defaults.py` DEFAULTS + startup banner + first-tagged-trade) → 20-sell / PF ≥ 1.5 on `original` (7B) → fallback promotion of `v3.2_lowvol_epoch` only on ≥24h starvation (7C). Current repo defaults still point at `v3.2_lowvol_epoch` (`src/data/config_defaults.py` line 11-16, `src/engine/lazarus.py` line 141-154) — Gate 7A treats repo alignment as part of the ceremony, not a follow-up. Interim operational-integrity checkpoint 2026-04-20; decision-review date 2026-04-23 (not a go-live date). Evidence: `PHASE_6_EXECUTION_LOG.md` cohort section (Step 5); Sprint 7 charter at `docs/sprints/SPRINT_7_COHORT_EVIDENCE.md`.

**2026-04-24 — Sprint 7 Gate 7A restart-and-reverify event (strict-charter adjudication):**
- **Runtime event:** Lazarus service restarted cleanly at `2026-04-24 06:17:16 UTC`; Gate 7A cutoff resets per charter. Clean systemd shutdown; no crash, no OOM. `fail2ban-client: Shutdown successful` at `06:17:17 UTC` suggests a system-level event; `unattended-upgrades` is a plausible inference but is not directly logged in the inspected window.
- **Audit gap acknowledged, not reconstructed.** No checkpoint entries were made between 2026-04-17 and 2026-04-24 (~8 days). Any claim about runtime behavior in that window must be sourced from fresh VPS evidence at the time of inspection, not inferred from surrounding entries.
- **Strict-charter adjudication (see ADR-14).** A contradiction between the Sprint 7 charter (`SPRINT_7_COHORT_EVIDENCE.md:96-97`, repo/default alignment is part of Gate 7A) and the execution log (`SPRINT_7_EXECUTION_LOG.md:43`, F3 note calling repo/default alignment a separate repo concern) was resolved in favor of the charter. Checks 3 and 4 apply in full on the server working tree.
- **Six-check ceremony under new cutoff:** 1 (bot_config) PASS, 2 (dynamic_config) PASS, 3 (deployed `lazarus.py` CFG) FAIL, 4 (`config_defaults.py` DEFAULTS) FAIL, 5 (startup banner + 26 runtime re-log samples) PASS, 6 (first-trade tag) PENDING. Sprint 7 remains open; Gate 7B evidence collection remains paused; no sells count toward the 20-sell cohort-of-record target.
- **Next actions tracked separately:** (1) align deployed `lazarus.py` CFG literal to `original`; (2) port `config_defaults.py` onto the server working tree (see TD-010); (3) await first post-`06:17:16 UTC` trade row and verify `filter_regime` tag.
- **Evidence location:** `docs/sprints/SPRINT_7_EXECUTION_LOG.md` under `Audit gap - 2026-04-17 through 2026-04-24`, `Gate 7A.F4.R1`, `Gate 7A.F4.R1.V1`, and `Strict-charter adjudication - 2026-04-24`. Tracker mirror at `ops/config/go_live_tracker.md` Day 11. Cohort-evidence appendix at `docs/sprints/SPRINT_7_COHORT_EVIDENCE.md` (Appendix - Gate 7A scope adjudication).

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
| ADR-12 | Dockerfile sed fix for CRLF (self-healing) | 2026-04-08 | Windows Git writes CRLF to entrypoint.sh, Linux container can't parse \r | .gitattributes eol=lf, manual dos2unix | Active |
| ADR-13 | Cloud Run min-instances=0 for portfolio demo | 2026-04-08 | Always-on instance ~$36/mo for a demo is wasteful | min-instances=1 (always on), scale manually | Active |
| ADR-14 | Strict-charter reading of Gate 7A — code-layer alignment is in-scope | 2026-04-24 | Contradiction between Sprint 7 charter (repo/default alignment is part of Gate 7A, `SPRINT_7_COHORT_EVIDENCE.md:96-97`) and execution log (F3 note at `SPRINT_7_EXECUTION_LOG.md:43` calling it a separate repo concern) | Narrow reading (exclude Checks 3 and 4, close Gate 7A on runtime-only evidence); documentation rewrite of the charter | Active |

---

## Technical Debt Tracker

| ID | Item | Sprint Added | Severity | Status | Notes |
|----|------|-------------|----------|--------|-------|
| TD-001 | Dashboard service still named sol-fortress-dashboard | 2026-03-28 | Low | Open | Cosmetic — works fine |
| TD-002 | Old folder references in some deploy scripts | 2026-04-04 | Medium | Open | PY/ and Shell Script/ folders eliminated in restructure |
| TD-003 | Dispatcher modules not deployed or integration-tested | 2026-04-02 | High | Open | 5 modules built locally, server only has single-wallet engine |
| TD-004 | Wide-net filters active in bot_config | 2026-04-01 | High | Open | Must revert to tight filters before Go-Live |
| TD-005 | No Alembic/migration system | 2026-03 | Medium | Open | Schema changes are manual SQL |
| TD-006 | `lazarus.py` hardcoded `min_hourly_vol=800` disagrees with playbook (`400`) and DB runtime truth | 2026-04-15 | High | Open | Reconcile the engine, repo defaults, and operating docs to one authoritative default path |
| TD-007 | fort_v2.log still named with old convention | 2026-03-28 | Low | Open | Log file name not rebranded |
| TD-008 | Cloud Run PAPER_TRADING env var not respected | 2026-04-08 | High | Open | Bot reads mode from bot_config DB (no persistent SQLite on CR). Need code-level env var override or init script. |
| TD-009 | Learning engine import path broken in Docker | 2026-04-08 | Medium | Open | `import learning_engine` fails — needs `from src.engine import learning_engine` or sys.path fix |
| TD-010 | `config_defaults.py` not on VPS server working tree | 2026-04-24 | High | Open | Gate 7A Check 4 FAIL under strict charter (2026-04-24). `find /home/solbot -name config_defaults.py` returned no matches; `find /home/solbot -name .git -type d` returned no matches within the searched depth. Must be placed on the server working tree to satisfy Gate 7A closure. Evidence: `docs/sprints/SPRINT_7_EXECUTION_LOG.md` under `Gate 7A.F4.R1.V1` Check 4. |

---

## Incident Log

| Date | Name | Impact | Resolution | Rule Created |
|------|------|--------|------------|-------------|
| 2026-03-28 | DB Config Override Bug | 8+ hours zero candidates | Update all 3 config layers | Rule #10 (Three-Place Config) |
| 2026-03-29 | Epoch Format Mismatch | 2 pre-epoch trades leaked into learning | T-format ISO across all files | Rule #17 (Timestamp Format) |
| 2026-03-29 | Ghost Trade Bug | Learning engine poisoned, self-reg death spiral | Stoic Gate + Ghost Trap + epoch filter | Rule #13 (Stoic Gate) |
| 2026-04-03 | Epoch Query Data Leak | Reported -690% instead of +43.54% | Text comparison, not strftime | Rule #17 addendum |
| 2026-04-08 | CRLF Entrypoint Crash | Cloud Run revision failed startup — bash couldn't parse \r | Dockerfile sed -i 's/\r$//' + chmod | Self-healing build step (ADR-12) |

---
*Modeled after Ceal Project Ledger pattern*
