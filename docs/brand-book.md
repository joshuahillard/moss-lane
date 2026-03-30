# Moss Lane — Master Brand Book
### The Complete Identity, Technical Spec, and Go-To-Market Playbook

**Version:** 1.0 | **Date:** March 28, 2026 | **Author:** Josh Hillard

> *"Quiet streets, loud comebacks."*

---

## I. Origin Story

After six years leading technical escalation teams at Toast — a FinTech company where I saved an estimated $12M identifying firmware defects and was recognized by the CEO at a company-wide kickoff — I left to prove I could build, not just manage. With zero coding experience, I taught myself Python, Linux, databases, APIs, and DevOps by building the hardest thing I could think of: an autonomous trading engine on the Solana blockchain.

I named the project **Moss Lane** after the streets around Manchester City's old Maine Road stadium — before the money, before the Etihad, when showing up meant something. I named the engine **Lazarus** because City fell to the third division and came back to become champions. I started with $103 and a terminal window. The goal is $20,000.

This isn't a crypto side project. It's a professional rebirth documented in code.

---

## II. Naming Architecture

| Layer | Name | Role | Tone |
|-------|------|------|------|
| **Project** | Moss Lane | The journey, the learning, the portfolio | Soft, understated, personal growth |
| **Engine** | Lazarus | The bot, the code, the technical system | Resilient, precise, relentless |
| **Tagline** | "Quiet streets, loud comebacks." | Footer, README, social bios | Understated confidence |

**Usage rules:** "Moss Lane" when talking about the project, the journey, or the brand. "Lazarus" when talking about the engine, the code, or the technical system. Together: "Moss Lane, powered by Lazarus."

---

## III. Visual Identity

### Color Palette — The "Maine Road" Suite

Evolved from the 1997-99 Kappa/Brother era sky blue into a digital-native palette. Every color has a name rooted in the source material.

| Role | Name | Hex | RGB | Usage |
|------|------|-----|-----|-------|
| Primary | **Kit Blue** | `#5DADE2` | 93, 173, 226 | Brand anchor. Headers, buttons, active states, chart lines. The actual Brother-kit sky blue energy — saturated and confident, not passive. |
| Primary Dark | **Maine Road Navy** | `#1A2332` | 26, 35, 50 | Dashboard backgrounds, terminal, dark mode base. Has warmth — not pure black. |
| Card Surface | **Tunnel** | `#1E2D3D` | 30, 45, 61 | Cards, panels, elevated surfaces in dark mode. Named for the Maine Road player tunnel. |
| Neutral Light | **Fog** | `#F0F3F5` | 240, 243, 245 | Light mode backgrounds, card surfaces. Manchester morning light. |
| Neutral Mid | **Kippax Stone** | `#D5D8DC` | 213, 216, 220 | Borders, dividers, inactive states. Named after the concrete terrace stand. |
| Success | **Pitch** | `#27AE60` | 39, 174, 96 | Profit, positive trades, wins. Muted green — not neon. |
| Danger | **Maroon Away** | `#C0392B` | 192, 57, 43 | Losses, errors, stop-loss triggers. Deep, controlled, not aggressive. |
| Warning | **Amber** | `#F39C12` | 243, 156, 18 | Caution states, sniper timeout, paper mode badge. |
| Accent | **Golden Goal** | `#F1C40F` | 241, 196, 15 | Highlights, CTAs, milestone celebrations. Used sparingly. |
| Text Primary | **Ink** | `#2C3E50` | 44, 62, 80 | Body text on light backgrounds. |
| Text Secondary | **Slate** | `#7F8C8D` | 127, 140, 141 | Timestamps, metadata, secondary labels. |

### CSS Design Tokens

```css
:root {
  --ml-kit-blue: #5DADE2;
  --ml-navy: #1A2332;
  --ml-tunnel: #1E2D3D;
  --ml-fog: #F0F3F5;
  --ml-stone: #D5D8DC;
  --ml-pitch: #27AE60;
  --ml-maroon: #C0392B;
  --ml-amber: #F39C12;
  --ml-gold: #F1C40F;
  --ml-ink: #2C3E50;
  --ml-slate: #7F8C8D;
}
```

### Typography

| Use | Font | Weight | Size (Base) | Why |
|-----|------|--------|-------------|-----|
| Display / Headings | **Archivo** | Black (900) | 28-36px | Industrial, grounded, 90s energy without being retro |
| Subheadings | **Archivo** | Semi-Bold (600) | 18-22px | Same family, lighter for hierarchy |
| Body / UI | **Inter** | Regular (400) / Medium (500) | 14-16px | Best screen readability, professional, warm |
| Code / Data / Terminal | **JetBrains Mono** | Regular (400) | 13-14px | Engineer credibility, ligatures, excellent at small sizes |
| Dashboard Numbers | **JetBrains Mono** | Bold (700) | 16-24px | P&L figures, balances — must be monospaced to prevent jitter on live updates |

**The Jitter Rule (from Gemini):** All numerical data in the dashboard must use JetBrains Mono. Standard sans-serif fonts have variable character widths; when prices update in real-time, the text shifts horizontally. Monospaced numbers stay pinned — a hallmark of professional trading terminals.

**Significant Figures Rule:** Show `$0.00002412` not `$0.00002`. Precision proves the system handles the "dust" required for low-cap Solana tokens. Never round below 4 significant figures in the dashboard.

### Logo Concepts

**Concept A: "The Street Sign" (Moss Lane)**
A horizontal wordmark inside a soft-cornered rectangle, mimicking classic white-on-blue UK street signs. "MOSS LANE" in uppercase Inter Semi-Bold, white on Kit Blue background. Below the rectangle, "est. 2026" in small caps Slate. Works at avatar size (32px) and hero size (full-width). This is the project identity.

**Concept B: "The Signal" (Lazarus)**
An abstract mark: a single continuous line in Kit Blue that starts as a flat heartbeat pulse, spikes into a sharp price-chart peak, then levels out. Represents finding the signal in the noise. Below the mark, "LAZARUS" in JetBrains Mono, uppercase, wide letter-spacing, white on dark. This is the engine identity — dashboard, terminal banner, technical docs.

**Concept C: "The Full Lockup" (Combined)**
Top line: "MOSS LANE" in Archivo Black, Kit Blue. Center: The Signal mark as a horizontal divider. Bottom line: "Powered by Lazarus" in JetBrains Mono Regular, Slate, 60% size. This is the full brand signature for README headers, portfolio pages, and social banners.

### Design Principles — "The Brother Kit Rules"

1. **Would it look right on a sky blue kit?** If it feels like 2024 Crypto Twitter, it's wrong. If it feels like a 1998 match day programme, it's right.
2. **Quiet confidence over loud claims.** No gradients, no glows, no "TO THE MOON." Flat colors, clean lines, generous whitespace.
3. **The data speaks.** Numbers and charts are the hero. Design frames them, never competes.
4. **Earned, not bought.** Every element should feel built by hand, not pulled from a template.
5. **The 2% texture rule (from Gemini).** On portfolio and dashboard backgrounds, use a 2% opacity noise texture. It mimics the fabric of those late-90s polyester kits — tactile rather than digital.

---

## IV. Dashboard — Technical Product Specification

### Philosophy

The Lazarus dashboard should look like a fintech operations center that happens to be built by one person. Not a hobby project, not a crypto Twitter flex. Think "Bloomberg Terminal for the People."

### Layout Architecture

```
+------------------------------------------------------------------+
|  LAZARUS v3.0              [PAPER]           1.2454 SOL  $103.83  |
|  Moss Lane Engine        Regime: CAUTIOUS              Kit Blue .  |
+------------------------------------------------------------------+
|                          |                                        |
|   BALANCE HISTORY        |     ACTIVE POSITION                    |
|   (Area chart)           |     Token: BONK/SOL                    |
|   Fill: Kit Blue @20%    |     Entry: $0.00002412                  |
|   Line: Kit Blue solid   |     Current: +4.2% (Pitch)             |
|   30-day window          |     Hold: 45s                          |
|   Axes: Slate            |     Trail: NOT ARMED (Slate)           |
|                          |     Size: 0.19 SOL (15.2%)             |
+------------------------------------------------------------------+
|                                                                    |
|   TRADE LOG (Last 20)                                              |
|   ┃ Time     │ Token    │ Side │ PnL%   │ Exit Reason              |
|   ┃ 2m ago   │ BONK/SOL │ SELL │ +4.2%  │ trail_stop               |
|   ┃ 8m ago   │ WIF/SOL  │ SELL │ -7.8%  │ stop_loss                |
|   ┃ 14m ago  │ POPCAT   │ SELL │ +1.2%  │ sniper_timeout           |
|   3px left-border: Pitch for profit, Maroon Away for loss          |
|                                                                    |
+------------------------------------------------------------------+
|   ENGINE STATUS              |   SESSION STATS                     |
|   Regime: Cautious (Amber)   |   Trades: 14                       |
|   Cycle: 847                 |   Win Rate: 42.8%                  |
|   Candidates: 3              |   Best: +18.2%                     |
|   Last scan: 2s ago          |   Worst: -7.8%                     |
|   Uptime: 14h 22m            |   Net P&L: +$4.12                  |
|   Market Regime: VOLATILE    |   Avg Hold: 67s                    |
+------------------------------------------------------------------+
|   Quiet streets, loud comebacks.                    Moss Lane 2026 |
+------------------------------------------------------------------+
```

### Component Specifications

**Header Bar**
- Background: Tunnel (`#1E2D3D`)
- Left: "LAZARUS v3.0" in JetBrains Mono Bold, Kit Blue
- Center: Mode pill badge — `PAPER` on Amber bg, `LIVE` on Pitch bg, `PAUSED` on Slate bg. Rounded corners, 6px padding.
- Right: Balance in JetBrains Mono Bold, white. Dollar equivalent in Slate.
- Far right: Heartbeat dot — 8px circle, Kit Blue, CSS pulse animation (1s ease-in-out infinite). Proves the engine is alive.

**Market Regime Indicator (Gemini addition)**
A small status component in Engine Status panel:
- If SOL 1h volatility > threshold → `VOLATILE` in Amber
- If 24h volume trending down → `STAGNANT` in Slate
- Normal conditions → `ACTIVE` in Pitch
- This proves to employers you built a system that contextualizes data before acting, not just "spray and pray."

**Balance Chart**
- Type: Area chart
- Fill: Kit Blue at 20% opacity
- Line: Kit Blue solid, 2px
- Background: Maine Road Navy
- Grid lines: Kippax Stone at 10% opacity
- Axes labels: Slate, JetBrains Mono Regular 12px
- Time range: 30 days default, toggleable to 7d / 24h

**Trade Log Table**
- Alternating rows: Maine Road Navy / Tunnel
- Left border: 3px, Pitch for profit rows, Maroon Away for loss rows
- Font: JetBrains Mono Regular 13px
- Timestamps: Relative ("2m ago" not "14:54:08 UTC")
- PnL: Pitch if positive, Maroon Away if negative
- Exit reasons in Slate italic

**Session Stats**
- All numbers in JetBrains Mono Bold
- Win rate > 50%: Pitch. Win rate < 40%: Maroon Away. Between: Amber.
- Net P&L follows same color logic

### Terminal Output Specification

**Startup Banner:**
```
    __
   / /  ____ _____  ____ ______  _______
  / /  / __ `/_  / / __ `/ ___/ / __ `/ / ___/
 / /__/ /_/ / / /_/ /_/ / /  / /_/ /  (__  )
/_____|__,_/ /___/\__,_/_/   \__,_/  /____/

 v3.0 | PAPER MODE | Moss Lane Engine
 Target: $20,000 | Balance: 1.2454 SOL
 ─────────────────────────────────────────
```

**Trade Notifications:**
```
[14:54:11] BUY  → BONK/SOL | Size: 0.19 SOL (15.2%) | Entry: $0.00002412
[14:55:07] SELL → BONK/SOL | +4.2% | Trail triggered at peak +8.1% | Hold: 56s
[14:55:07] NET  → +$0.008 SOL | Session: +$4.12 (14 trades, 42.8% WR)
```

**Cycle Heartbeat:**
```
[14:56:11] [Cycle 847] 1.2462 SOL ($103.89) | open=0/1 | candidates=3 | regime=cautious
```

---

## V. GitHub Repository — The Public Face

### README Badges (Brand-Consistent Hex Codes)

```markdown
![Python](https://img.shields.io/badge/Python-3.12-5DADE2?style=flat-square&logo=python&logoColor=white)
![Solana](https://img.shields.io/badge/Solana-Mainnet-1A2332?style=flat-square&logo=solana&logoColor=white)
![SQLite](https://img.shields.io/badge/SQLite-Database-5DADE2?style=flat-square&logo=sqlite&logoColor=white)
![Linux](https://img.shields.io/badge/Linux-Ubuntu_22-1A2332?style=flat-square&logo=linux&logoColor=white)
![Status](https://img.shields.io/badge/Status-Paper_Trading-F39C12?style=flat-square)
```

### README Structure

```markdown
<!-- Header banner: Full Lockup logo on Maine Road Navy, 1200x300 -->

# Moss Lane
> From zero code to autonomous trading. A self-taught engineering journey.

[Badges row]

---

## What Is This?

I left a 6-year career in FinTech technical leadership and taught myself
to code by building the hardest thing I could think of.

Moss Lane is an autonomous decision engine for Solana DeFi. At its core
is **Lazarus** — a Python-based trading engine that scans decentralized
exchanges in real time, identifies momentum opportunities through layered
filters, executes trades via Jupiter aggregator, and manages risk through
a multi-tiered exit system including trailing stops, hard floors, and
adaptive position sizing.

Built from scratch. Self-taught. Running 24/7 on cloud infrastructure.

## Architecture

<!-- Mermaid.js diagram -->
DexScreener API → Filter Engine → Jupiter Swap → Monitor Loop → Exit Logic
         ↓                                              ↓
   Regime Detection                          Learning Engine ← Trade DB

## The Stack

| Layer | Technology |
|-------|-----------|
| Language | Python 3.12, asyncio |
| Data | SQLite, DexScreener API, Birdeye API |
| Execution | Jupiter Aggregator, Solana RPC (Helius) |
| Infrastructure | Vultr VPS (Ubuntu 22), systemd |
| Risk | Multi-layer exits, regime switching, adaptive sizing |

## The Build Log

Real engineering problems I solved building this system. No sugar-coating.

- [The Ghost Trade Bug](docs/build-log/ghost-trade.md) — When your sell
  logic reads the wrong API field
- [The Three-Layer Config Trap](docs/build-log/config-trap.md) — When your
  code is right but the database disagrees
- [Why I Killed aiohttp](docs/build-log/killed-aiohttp.md) — When the
  "right" tool is the wrong tool
- [The Silent Rewrite](docs/build-log/v3-rewrite.md) — Rebuilding 1,200
  lines from scratch after finding 5 root causes
- [Incident: The Midnight RPC Timeout](docs/build-log/rpc-incident.md) —
  A post-mortem in proper format

## Performance

<!-- Screenshot of Lazarus dashboard or table of results -->
<!-- Transparency builds trust -->

## What I Learned

Six years of managing engineers taught me how to prioritize, communicate
under pressure, and see systems from the top down. Six months of building
Lazarus taught me what happens at the bottom — where the bugs live, where
the logic breaks, and why the best architecture in the world fails without
good error handling.

Both perspectives matter. That's what I bring.

---

*Quiet streets, loud comebacks.*
```

---

## VI. The Build Log — Detailed Templates

### Standard Entry Format

```markdown
# [Title]
**Date:** YYYY-MM-DD | **Severity:** Low / Medium / High | **Time to resolve:** Xh

## Problem
What was happening. What the symptoms looked like.

## Investigation
How you found the root cause. What you checked. What led you astray.

## Root Cause
The actual bug / misconfiguration / design flaw.

## Fix
What you changed. Include a code snippet if relevant (keep it short).

## Lesson
The transferable takeaway. What you'd do differently. What this taught
you about engineering in general.
```

### Incident Retrospective Format (The "Kill Shot" — from Gemini)

This format is specifically designed to demonstrate to hiring managers that you can handle production incidents as an engineer, not just as a manager. It bridges your Toast escalation leadership experience with your new engineering skills.

```markdown
# Incident Retrospective: [Title]
**Date:** YYYY-MM-DD
**Duration:** Detection → Resolution
**Severity:** P1 / P2 / P3
**Impact:** What was affected

## Timeline
- **HH:MM** — First anomaly detected (what triggered the alert)
- **HH:MM** — Initial diagnosis attempted (what you checked first)
- **HH:MM** — Root cause identified
- **HH:MM** — Fix deployed
- **HH:MM** — System confirmed stable

## Detection
How you noticed. What metric, log line, or behavior flagged it.

## Containment
Immediate actions to stop the bleeding.

## Root Cause
The actual failure. Technical detail.

## Resolution
The fix. What was deployed.

## Prevention
What was put in place to ensure this never happens again.
Monitoring, guards, tests, process changes.

## Impact Assessment
- Trades affected: X
- Financial impact: $Y
- Downtime: Zm

## What I'd Do Differently
Honest reflection.
```

### Pre-Written Entries Ready to Publish

**Entry 1: "The Ghost Trade Bug"**
- Severity: High
- The sell logic was using SOL lamports instead of token `outAmount`, creating phantom P&L calculations
- Lesson: API response schemas need to be validated against actual use cases. Documentation doesn't always match real-world payloads.

**Entry 2: "The Three-Layer Config Trap"**
- Severity: Medium
- Runtime config loads from `bot_config` SQLite table, overriding hardcoded defaults. v3 deploy updated code but not the database. Additionally, `dynamic_config` table had stale learning engine overrides.
- Lesson: Configuration hierarchy needs to be documented and enforced. "It works in my code" ≠ "it works at runtime."

**Entry 3: "Why I Killed aiohttp"**
- Severity: Medium
- External API calls failing silently due to async event loop collisions. Replaced with subprocess `curl_get()` wrapper.
- Lesson: Sometimes the "right" tool (native async HTTP) is worse than the "wrong" tool (subprocess curl) in a specific context. Pragmatism over purity.

**Entry 4: "The Silent Rewrite" (v2 → v3)**
- Severity: Critical
- Five root causes found in v2: buying topped-out tokens, re-entering losers, learning engine writing 3% position sizes, self-regulation death spiral, and the sell bug. All five required a ground-up rewrite.
- Lesson: When the root causes are architectural, patches create new bugs. Sometimes you tear it down and rebuild.

**Entry 5: "Incident — The Midnight RPC Timeout" (Post-Mortem Format)**
- Written in the Incident Retrospective format above
- Demonstrates production incident management skills
- Bridges your Toast escalation leadership with engineering execution

---

## VII. Portfolio & Hiring Strategy

### The Narrative Frame

Never call it a "crypto trading bot." Call it what it is:

> "A self-built autonomous decision engine with real-time data processing, risk management, and adaptive learning — deployed on cloud infrastructure and validated through iterative testing cycles."

That sentence hits every keyword an ATS and hiring manager scan for: autonomous systems, real-time processing, risk management, adaptive learning, cloud infrastructure, iterative testing.

### Skills Matrix

| Skill Category | What You Built | Industry Translation |
|---------------|----------------|---------------------|
| Python Engineering | 1,200+ line async engine with error handling, retry logic, modular architecture | Production-grade Python development |
| Database Design | SQLite schema for trade logging, balance snapshots, config management, learning state | Data engineering, schema design |
| API Integration | Jupiter (swaps), DexScreener (market data), Helius (RPC), Birdeye (analytics) | Third-party API integration, REST/async |
| Linux Administration | VPS provisioning, systemd services, SSH/SCP deployment, log analysis | DevOps, server administration |
| Risk Management | Multi-layer exits (SL, hard floor, trailing stop, sniper timeout, daily limit) | Financial systems, safety-critical logic |
| Adaptive Systems | Self-learning position sizing, regime-based filter adjustment, dynamic config | ML-adjacent systems, feedback loops |
| Deployment & CI | Base64-embedded deploy scripts, syntax verification gates, backup-before-deploy | CI/CD thinking, release engineering |
| Incident Response | Traced config override bug across 3 layers, diagnosed in production under pressure | Production debugging, root cause analysis |
| Product Management | Defined roadmap, prioritized by impact, managed scope across v1 → v2 → v3 | Product thinking, technical decision-making |
| Brand & Communication | Full rebrand with design system, documentation, and go-to-market strategy | Technical communication, design thinking |

### The Interview Answer

**Q: "Why did you leave leadership to do this?"**

**A:** "I spent 6 years managing the 'what' and the 'who.' I built Moss Lane because I needed to master the 'how.' Now, I don't just understand the lifecycle of a technical escalation — I understand the line of code that caused it. I'm looking to bring that full-stack perspective to your team."

**Q: "Tell me about yourself."**

**A:** "I spent six years leading technical teams at a FinTech company. When I left, I taught myself to code by building an autonomous trading system from scratch — Python, Linux, databases, cloud deployment, the works. I named it Moss Lane. The engine at the center is called Lazarus because it's a comeback story. I started with $103 and a terminal window. I learned more about engineering in six months of building than in six years of leading engineers. Both perspectives make me dangerous."

**Q: "What's the hardest bug you've ever fixed?"**

**A:** "I deployed a major rewrite of my trading engine and it ran for 8 hours finding zero trading candidates. The code was correct — I verified it line by line. Turned out the system loads runtime configuration from a SQLite table that overrides the code defaults, and a secondary table where the learning engine writes dynamic overrides. I had three layers of configuration, and only the first was updated. Took me 2 hours to trace the full config hierarchy. Now every deployment has a checklist: update code, update bot_config DB, clear dynamic_config. Configuration management is trust management."

### LinkedIn Positioning

**Headline:**
`Technical Leader → Self-Taught Engineer | Building autonomous trading systems in Python | Ex-Toast (6yr)`

**About section opener:**
"I spent six years leading technical escalation teams at Toast, where I managed complex customer-facing incidents, saved the company an estimated $12M identifying firmware defects, and was recognized by the CEO at a company-wide kickoff. Then I left to learn how to build."

### Portfolio Case Study Structure

1. **The Challenge** — "After 6 years leading technical teams, I wanted to prove I could build, not just manage."
2. **The Approach** — Stack choices, learning path, iteration cycles (v1 → v2 → v3)
3. **The Hard Parts** — The 5 root causes, the config trap, the aiohttp discovery
4. **The Results** — Paper trading performance, 1,200+ lines of code, 24/7 cloud deployment, 9 API integrations, full brand system
5. **The Takeaway** — "I learned more about engineering in 6 months of building than in 6 years of leading engineers. Both perspectives make me dangerous."

---

## VIII. Content Strategy — Build in Public

### Platform Strategy

| Platform | Content Type | Frequency | Purpose |
|----------|-------------|-----------|---------|
| **Twitter/X** | Short updates, screenshots, one-liners | 3-4x per week | Build following, tech community |
| **GitHub** | Code, README, build log entries | Ongoing | Prove technical skill |
| **LinkedIn** | Longer posts, case study updates | 1-2x per week | Job search, professional network |
| **Dev.to** | Full technical articles | 2x per month | SEO, deep technical credibility |

### Content Calendar — First 30 Days

**Week 1: The Introduction**
- LinkedIn: "I left my job 6 months ago. Here's what I built instead."
- Twitter: Screenshot of Lazarus terminal banner + "Meet Lazarus."
- GitHub: Push `moss-lane` repo with branded README

**Week 2: The Technical Deep Dive**
- Dev.to: "Why I replaced aiohttp with subprocess curl — and why that's not crazy"
- Twitter: Dashboard screenshot with Kit Blue theme
- GitHub: Publish build log entry: The Three-Layer Config Trap

**Week 3: The Human Story**
- LinkedIn: "What managing technical escalations at a FinTech taught me about building software"
- Twitter: Paper trading results update with commentary
- Twitter: "The name Moss Lane comes from..." — the heritage post

**Week 4: The Lessons**
- LinkedIn/Dev.to: "5 things I wish I knew before building my first Python project"
- Twitter: Architecture diagram thread
- All platforms: "Here's what Lazarus did in its first month"

### Voice Rules

- Write like you talk. No corporate speak.
- Show failures as much as wins. "The bot lost 40% before I found the bug" > "My bot is profitable."
- Reference the Man City / Oasis connection when natural, never forced.
- Every post should make someone think: "This person can solve hard problems."
- Footer on every post: *Quiet streets, loud comebacks.*

---

## IX. Execution Roadmap

### Phase 1: Foundation (Week of March 28)
- [x] Project naming: Moss Lane + Lazarus
- [x] Mission statement written
- [x] Server rebrand deployed
- [x] Project instructions updated
- [x] Brand book created (this document)
- [ ] Generate logo assets (AI tools or Fiverr commission)
- [ ] Set up color palette as CSS variables
- [ ] Create `moss-lane` GitHub repo with branded README
- [ ] Write first 2 build log entries

### Phase 2: Dashboard Rebrand (Week of April 4)
- [ ] Redesign Lazarus dashboard with Maine Road theme
- [ ] Implement dark mode with the color palette
- [ ] Add Market Regime indicator
- [ ] Apply JetBrains Mono for all numerical data (jitter rule)
- [ ] Add ASCII banner to terminal output
- [ ] Screenshot everything for portfolio

### Phase 3: Go Public (Week of April 11)
- [ ] First LinkedIn post: the introduction
- [ ] First Twitter post: terminal screenshot
- [ ] First Dev.to article
- [ ] Update LinkedIn headline and profile
- [ ] Publish build log entries on GitHub

### Phase 4: Portfolio Assembly (Week of April 18)
- [ ] Build portfolio page (GitHub Pages)
- [ ] Write the Moss Lane case study
- [ ] Prepare interview talking-points doc
- [ ] Start applying to roles with portfolio link

### Phase 5: Product Evolution (Ongoing)
- [ ] Validate Lazarus v3 paper trading results
- [ ] Multi-wallet dispatcher (5 burners + tax vault)
- [ ] Go live after validation
- [ ] Document the $103 → $20K journey in real-time

---

## X. System Architecture

The full technical architecture — Mermaid.js diagrams, filter cascade, exit chain, config hierarchy, database schema, tech stack, and an honest comparison of what Gemini suggested vs. what actually exists in the code — lives in a dedicated document:

**[Lazarus_Architecture.md](Lazarus_Architecture.md)**

This is the centerpiece of the GitHub README and the document that proves engineering depth to hiring managers. It was built by reading the actual running codebase, not by inventing what sounds impressive.

Key sections interviewers will care about: the Three-Layer Config Trap (state management), the `curl_get()` decision (pragmatism), the 7-Tier Exit Chain (risk engineering), and the "What Gemini Suggested vs. Reality" table (intellectual honesty).

---

## XI. File Reference

| File | Location | Purpose |
|------|----------|---------|
| This document | `Moss_Lane_Master_Brand_Book.md` | The definitive brand + strategy reference |
| Project instructions | `PROJECT_INSTRUCTIONS.md` | Technical project config and deployment rules |
| Rebrand handoff | `Rebrand_Handoff_20260328.md` | Record of the server rebrand session |
| Gemini prompt (round 1) | `Gemini_Brand_Prompt.md` | Initial brand identity prompt |
| Gemini visual prompt | `Gemini_Followup_Visual_Prompt.md` | Visual asset generation prompt |
| Resume | `Josh_Hillard_Resume.docx` | Current resume |
| Architecture doc | `Lazarus_Architecture.md` | Full system architecture with Mermaid diagrams |
| Career strategy | `Career_Strategy_Handoff.pdf` | Career planning reference |

---

*You are no longer "between jobs." You are the Founder and Lead Engineer of Moss Lane.*
