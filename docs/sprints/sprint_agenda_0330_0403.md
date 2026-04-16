# Moss Lane Sprint Agenda — Week of 2026-03-30 → 2026-04-03

**Sprint Goal:** Reach Stoic Gate (20 trades), validate Lazarus v3.1 paper performance, and make Go/No-Go decision on April 3.

**Daily Structure (same every day):**
- 6:00–6:15 AM ET — Morning Standup
- 6:15–8:30 AM ET — Deep Work Block 1 (Moss Lane)
- 8:30–9:00 AM — Break
- 9:00 AM–12:00 PM ET — Deep Work Block 2 (Moss Lane)
- 12:00–1:00 PM — Lunch (HARD STOP on Moss Lane)
- 1:00–3:00 PM ET — PM Cert + Applications (FIXED — not swappable)
- 3:00–3:30 PM — Break
- 3:30–7:00 PM ET — Deep Work Block 4 (Career Strategy / Overflow)
- 7:00 PM — Evening Wrap-Up

---

## Monday 3/30 — v3.1 Autopsy & Integrity Check

**Block 1 (6:15–8:30 AM):** State Management & First Autopsies
- IMMEDIATE: Fix stale v2 config → `UPDATE bot_config SET value='0.15' WHERE key='position_pct';`
- Pull Phase 2 trades strictly after epoch 2026-03-29T17:44:00
- If trades exist: run First Trade Autopsy (Latency → Exit Reason → Entry Quality)
- If zero: document market context and move on

**Block 2 (9:00 AM–12:00 PM):** Performance Analysis & Build Logging
- Deep analysis of scanner behavior, filter hit rates, 10–80% window effectiveness
- Document DexScreener fallback patch as GitHub Build Log entry ("Why I Killed aiohttp")
- Update go_live_tracker.md with Day 1 actuals

**Block 4 (3:30–7:00 PM):** Career Strategy
- PM Cert Course 4 study
- LinkedIn / application pipeline

**Deliverables:** Trade autopsy report, corrected go-live tracker baseline, build log entry

---

## Tuesday 3/31 — Checkpoint & Pivot Rule

**Block 1 (6:15–8:30 AM):** Daily Checkpoint
- Pull fresh trade data from server: count sells, calculate running PF and WR
- Review EU/US overlap volume from Monday overnight
- If 10–80% filters caught runners: document what worked
- Update go_live_tracker.md Day 2

**Block 2 (9:00 AM–12:00 PM):** Architecture OR Tuning (Pivot Rule)
- **IF** market active and trades flowing → analyze trade quality, identify any single-variable tuning candidate
- **IF** market dead and zero valid trades since Monday → PIVOT immediately to Phase 2 architecture:
  - Multi-Wallet Dispatcher design (Mermaid diagrams, flow charts)
  - 5-burner wallet strategy split
  - 15% Tax Vault routing logic
- Either way, this is portfolio-grade documentation work

**Block 4 (3:30–7:00 PM):** Career Strategy
- PM Cert continuation
- Application follow-ups

**Deliverables:** Day 2 tracker update, dispatcher architecture draft (if pivoted), or tuning analysis

---

## Wednesday 4/1 — Stoic Gate Watch + Build

**Block 1 (6:15–8:30 AM):** Stoic Gate Progress
- Expected: ~14–21 total trades by now (7/day pace)
- Pull fresh SQL, update tracker Day 3
- If Stoic Gate (20 trades) reached: unlock learning engine analysis, document first adaptive cycle
- If not: patience — document trade frequency trend

**Block 2 (9:00 AM–12:00 PM):** Architecture Build
- Continue Multi-Wallet Dispatcher design regardless of gate status
- Define wallet routing logic: which wallet gets which strategy
- Draft fee-aware sizing rules for small wallets (wallets 4–5 need 50–100% position sizes)
- Begin coordinator module spec

**Block 4 (3:30–7:00 PM):** Career Strategy
- PM Cert Course 4 completion target
- Portfolio polish — integrate Moss Lane case study updates

**Deliverables:** Day 3 tracker update, dispatcher architecture v1, wallet strategy matrix

---

## Thursday 4/2 — Coordinator + Tax Vault Design

**Block 1 (6:15–8:30 AM):** Pre-Decision Data Pull
- Full performance snapshot: PF, WR, avg win, avg loss, max drawdown
- Compare against Day 1 baseline — is the trend improving, flat, or declining?
- Update go_live_tracker.md Day 4 with final pre-decision numbers
- Prepare decision brief with both scenarios (GO and NO-GO)

**Block 2 (9:00 AM–12:00 PM):** Tax Vault + Coordinator
- Design 15% profit skim mechanism (triggers, routing, accounting)
- Coordinator module: how the main engine dispatches across wallets
- Risk controls for multi-wallet: per-wallet limits, aggregate exposure cap
- Document everything as portfolio-ready architecture docs

**Block 4 (3:30–7:00 PM):** Career Strategy
- Final PM Cert push for the week
- Update resume/portfolio with week's engineering work

**Deliverables:** Day 4 tracker, decision brief, tax vault architecture, coordinator spec

---

## Friday 4/3 — DECISION DAY

**Block 1 (6:15–8:30 AM):** Go/No-Go Review
- Final trade data pull from server
- Complete go_live_tracker.md with DECISION DAY row
- Run the gate checklist:
  - [ ] PF >= 1.5 across 20+ trades?
  - [ ] Execution latency < 200ms?
  - [ ] Stop-loss slippage < 2%?
  - [ ] Filter rejection rate 96–98%?
  - [ ] No critical bugs in 4-day window?
  - [ ] Learning engine stable?
- **Josh's gut check:** Does the data feel right? Any concerns beyond the numbers?

**Block 2 (9:00 AM–12:00 PM):** Execute Decision
- **IF GO:** Plan live deployment — switch PAPER=false, set initial live position size (conservative), document go-live runbook
- **IF NO-GO:** Document what failed, define specific fix targets, set new validation window
- **IF CLOSE (PF 1.3–1.5):** Consider conditional go-live with tighter risk limits (smaller position size, lower daily loss limit)
- Either way: produce a Go-Live Decision Document (portfolio-grade)

**Block 4 (3:30–7:00 PM):** Week Wrap
- Weekly performance review
- Update Asana with next week's tasks
- Evening handoff document
- Celebrate the week's progress regardless of decision

**Deliverables:** Go-Live Decision Document, updated tracker, weekly handoff, next-week plan

---

## Sprint Success Criteria

1. **Stoic Gate reached** (20+ paper trades analyzed)
2. **Go/No-Go decision made** with data backing (not emotion)
3. **Multi-Wallet Dispatcher architecture documented** (regardless of go-live outcome)
4. **PM Cert progress** (Course 4 completion or near-completion)
5. **All documentation validated** and accurate to actual project state

---

*Sprint managed by TPM Meta-Persona. Daily standups at 6 AM ET, evening wrap-ups at 7 PM ET.*
*Quiet streets, loud comebacks.*
