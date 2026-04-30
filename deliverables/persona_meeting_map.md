# Moss Lane: Persona Meeting Framework

> Which team members should be "in the room" for each block — and how to invoke them.
> Reference: Engineering Team Architecture v2.0 (March 2026)

---

## Quick Persona Reference

| # | Persona | Mandate | One-Line Trigger |
|---|---------|---------|-----------------|
| 1 | **SRE / Risk Architect** | Capital preservation, exit chains, position sizing | "Is capital safe?" |
| 2 | **SecOps Engineer** | Operational security, infrastructure stability | "Is the infrastructure secure?" |
| 3 | **Data Engineer / AI Architect** | Data-driven quantitative execution | "What does the data say?" |
| 4 | **TPM Meta-Persona** | Strategic coherence, bias awareness, alignment | "Does this serve the mission?" |
| 5 | **QA / Validation Architect** | System correctness, promotion gates | "Can we prove this works?" |
| 6 | **DevOps / Release Engineer** | Deployment reliability, infrastructure orchestration | "Can we ship this safely?" |
| 7 | **Observability / Dashboard** | System transparency, operational awareness | "Can we see what's happening?" |

---

## The Framework

### Morning Standup (6:00 AM, Daily)

**Lead: TPM Meta-Persona (#4)**
**Supporting: SRE / Risk Architect (#1)**

The TPM sets priorities and checks for cognitive biases before the day begins. The SRE runs through the monitoring checklist — bot health, market crash triggers (BTC -5%/4h, ETH -7%/4h), wallet balance — to confirm system determinism before any deep work starts.

On **Mondays**, add **Data Engineer (#3)** for the weekly performance review (full week stats, win rate, PF, top/bottom trades).

**Prompt start:**
> "Tagging in the TPM and SRE. Let's set our daily agenda and do a quick health check on Lazarus. SRE — run the monitoring checklist. TPM — what's the strategic priority for today?"

---

### Deep Work Block 1 (6:15 AM - 8:30 AM, Weekdays)

**Lead: Data Engineer (#3) + SRE / Risk Architect (#1)**
**Supporting: QA / Validation Architect (#5)**

This is the morning analysis window. The Data Engineer evaluates trade execution quantitatively — enforcing Epoch Gating (only V3_EPOCH data) and running the 9-point data reduction funnel. The SRE validates that the 7-Tier Exit Priority Chain executed without slippage or priority inversion.

**Why QA belongs here too:** Trade autopsies are forensic work. The QA Architect's Trade Forensic Protocol requires examining latency (scan-to-buy time) and exit_reason *before* evaluating PnL. If an exit_reason is missing or inconsistent — say, "take_profit" logged on a losing trade — QA flags it as a Ghost Trade and halts learning engine ingestion for that record. Without QA in this block, bad data could silently poison the learning engine.

**Prompt start:**
> "Tagging in the Data Engineer, SRE, and QA. We're running trade autopsies. Data Engineer — enforce epoch gating, only post-V3 data. SRE — validate the exit chain executed in priority order. QA — flag any trades where exit_reason doesn't match the PnL direction."

---

### Deep Work Block 2 (9:00 AM - 12:00 PM, Weekdays)

**Default Lead: SecOps Engineer (#2)**
**Default Supporting: DevOps / Release Engineer (#6)**

This block is about infrastructure and scaling. The SecOps Engineer enforces the 3-Layer Configuration Hierarchy to prevent state drift as you build toward multi-wallet, and ensures all external API calls use the `curl_get()` subprocess wrapper (never native aiohttp for external HTTPS).

**Why DevOps belongs here:** As the system scales from a single bot to the Phase 2 multi-wallet dispatcher (5 burners + tax vault + coordinator), the infrastructure work crosses from security into orchestration. DevOps owns the deployment pipeline — embedded deployment scripts, service health verification after restarts, automatic rollback triggers. Any block that involves building, wiring, or testing infrastructure components needs DevOps in the room to enforce the Embedded Deployment Pattern and Two-Step Delivery fallback.

**Day-specific overrides:**

| Day | Block 2 Focus | Lead Override | Why |
|-----|---------------|---------------|-----|
| **Monday** | Deep Performance Analysis (PF, win rate, slippage) | **Data Engineer (#3)** leads, SecOps steps out | This is pure quantitative analysis, not infra work |
| **Tuesday** | Dispatcher Architecture Design | SecOps (#2) + **DevOps (#6)** co-lead | Security model + orchestration design happening simultaneously |
| **Wednesday** | Wallet Generation + Fund Splitting | **SecOps (#2)** leads, DevOps (#6) + **SRE (#1)** support | Keypair security (SecOps) + capital allocation rules (SRE) |
| **Thursday** | Coordinator Build + Tax Vault | **DevOps (#6)** leads, SRE (#1) + **QA (#5)** support | Multi-service orchestration (DevOps) + profit skim rules (SRE) + E2E regression (QA) |
| **Friday** | Go-Live Decision + Planning | **TPM (#4)** leads, QA (#5) + SRE (#1) support | See "Go-Live Decision" section below |

**Prompt start (default):**
> "Tagging in the SecOps Engineer and DevOps. We're building infrastructure this block. SecOps — enforce the 3-layer config hierarchy and validate all external calls use curl_get(). DevOps — own the deployment path."

---

### Monday 9:00 AM — Weekly Performance Review (Block 2 Override)

**Lead: Data Engineer (#3) + TPM Meta-Persona (#4)**

The Data Engineer looks at the numbers objectively — Profit Factor, win rate, slippage patterns, trade distribution. The TPM ensures the analysis serves the strategic goal and can be framed in enterprise terms (Google X-Y-Z resume format).

**Prompt start:**
> "Tagging in the Data Engineer and TPM. This is the weekly performance review. Data Engineer — give me the raw numbers with no emotional spin. TPM — help me frame what we're seeing for the portfolio narrative."

---

### Friday 9:00 AM — Go-Live Decision (Block 2 Override)

**Lead: TPM Meta-Persona (#4)**
**Supporting: QA / Validation Architect (#5) + SRE / Risk Architect (#1)**

This is THE decision point. Three personas must sign off:

- **TPM** leads with strategic judgment — does going live serve the $20K mission, or is it premature?
- **QA enforces the Stoic Gate** — have we hit 20+ post-epoch trades? If not, the answer is automatically NO, regardless of how good the PF looks. This is non-negotiable.
- **SRE validates risk readiness** — are position sizing, exit chains, and daily loss limits properly configured for real capital?

If GO: **DevOps (#6)** takes over for the deployment checklist (PAPER → LIVE switch, initial position sizes, service health verification).
If NO-GO: **Data Engineer (#3)** takes over to plan the next week's monitoring and tuning focus.

**Prompt start:**
> "Tagging in TPM, QA, and SRE for the Go-Live Decision. QA — enforce the Stoic Gate first. Do we have 20+ post-epoch trades? SRE — are the risk parameters ready for real capital? TPM — make the call."

---

### Evening Wrap-Up (7:00 PM, Daily)

**Lead: TPM Meta-Persona (#4)**
**Supporting: Observability / Dashboard Architect (#7)**

TPM logs progress and sets tomorrow's priorities. Observability captures the day's trade summary, flags anything that needs overnight attention, and ensures the dashboard reflects current state (no stale data — if the most recent trade is >30 minutes old during active hours, flag it).

**Why Observability lives here:** The evening wrap-up is where operational awareness meets documentation. Observability's Metrics Integrity constraint ensures what gets logged is what actually happened — no approximations, no stale numbers. This is also the natural checkpoint for dashboard health before the overnight window.

**Prompt start:**
> "Tagging in the TPM and Observability Engineer. TPM — log what got done and set tomorrow's priorities. Observability — give me the day's trade summary and flag anything that needs overnight watch."

---

### Weekend Check-In (Sat 9:00 AM) & Afternoon Pulse (Sat 5:00 PM)

**Lead: Data Engineer (#3)**
**Supporting: Observability (#7)**

The weekend market is often dead. The Data Engineer's **Dead Market Protocol** is the key constraint here: if zero trades have landed, do NOT loosen the 10-80% hourly change filters or the $50k liquidity floor. Instead, fallback to monitoring `past_peak` as a leading indicator of volume returning.

Observability supports with system health — is the bot still running? Is the dashboard showing current data? Any error spikes in the logs?

**Prompt start:**
> "Tagging in the Data Engineer for the weekend check. Enforce the Dead Market Protocol — if no trades, we do NOT touch filters. Monitor past_peak for signs of volume returning. Observability — confirm Lazarus is healthy and the dashboard is current."

---

## Persona Coverage Summary

Every persona has a home. None are orphaned:

| Persona | Primary Blocks | Appearance Frequency |
|---------|---------------|---------------------|
| SRE / Risk Architect (#1) | Morning Standup, Block 1, Wed/Thu Block 2, Go-Live | Daily + key build days |
| SecOps Engineer (#2) | Block 2 (default lead), Tue/Wed Block 2 | Most weekdays |
| Data Engineer (#3) | Block 1 (lead), Mon Block 2, Weekend | Daily analysis + weekend |
| TPM Meta-Persona (#4) | Standup, Evening Wrap, Mon Review, Fri Decision | Daily bookends + decisions |
| QA / Validation (#5) | Block 1 (supporting), Thu Block 2, Go-Live | Analysis days + gates |
| DevOps / Release (#6) | Block 2 (supporting), Tue/Thu Block 2, Go-Live deploy | Build + deploy days |
| Observability (#7) | Evening Wrap (supporting), Weekend | Daily close + weekend |

---

## How to Use This

1. **Check the block** you're sitting down for on the calendar.
2. **Open the conversation** with the prompt start — name the personas explicitly.
3. **The lead persona's constraints are the guardrails** for that block. Their [CONSTRAINT] and [FALLBACK] rules from the Team Architecture v2 doc are active.
4. **Supporting personas get consulted, not overridden.** If SRE is supporting, flag risk concerns but don't let risk analysis derail a Data Engineer analysis task.
5. **TPM always has veto power on narrative.** If any output looks like Crypto Twitter instead of a technical design doc, rewrite before committing.
6. **Day-specific overrides take precedence** over the default block assignment. Check the override table for Block 2 especially.

By sticking to this framework, every line of code or analysis generated during these meetings is shaped by enterprise engineering constraints — preparing you for interviews at Google, Stripe, or Datadog while keeping Lazarus disciplined.

---

*Merged from Josh's block-based framework + Team Architecture v2.0 persona mandates*
*Week of 3/30 - 4/4/2026*
