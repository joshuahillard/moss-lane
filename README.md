# Moss Lane

**An autonomous Solana momentum trading engine, built from scratch by a non-developer to prove that systems thinking scales across domains.**

> *"Quiet streets, loud comebacks."*

---

## What This Is

Moss Lane is a solo project where I taught myself Python, Linux, databases, APIs, and DevOps by building the hardest thing I could think of: a real-time autonomous trading engine on the Solana blockchain.

After six years leading technical escalation teams at Toast — where I saved an estimated $12M identifying firmware defects and was recognized by the CEO at a company-wide kickoff — I left to prove I could build, not just manage.

The engine is called **Lazarus**. It scans the Solana memecoin market in real time, filters thousands of tokens through a 12-point fail-closed gate, executes trades via Jupiter aggregator, and manages positions with a 7-tier exit priority chain. It learns from its own results and self-regulates during losing streaks.

I started with $103 and a terminal window.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                    DATA INGESTION                        │
│  DexScreener API · Helius RPC · Birdeye Price Feeds     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                  DUAL-SOURCE SCANNING                    │
│  BirdeyeScanner (momentum)  ·  SmartMoneyScanner (copy) │
│  16 search queries + 3 endpoints → batch → 12-pt filter │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│               SIGNAL AGGREGATION                         │
│  Merge · Deduplicate by address · Apply learned weights  │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                   SAFETY GATES                           │
│  Daily loss limit · BTC/ETH crash detection              │
│  Self-regulation regime · Token cooldowns                │
│  JIT final gate (re-verify at execution time)            │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                TRADE EXECUTION                           │
│  Jupiter quote → swap → sign → send                     │
│  VersionedTransaction · skipPreflight for memecoins      │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│              POSITION MONITORING                         │
│  3-second price loop · 7-tier exit priority chain:       │
│  hard floor → emergency rug → take profit → trail stop   │
│  → sniper exit → stop loss → timeout                     │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│                 ADAPTIVE LAYER                           │
│  Learning Engine: win-rate → position sizing (10-25%)    │
│  Self-Regulation: regime detection (normal/cautious/halt)│
│  Rug blacklist · Condition performance tracking          │
└─────────────────────────────────────────────────────────┘
```

For the full system diagram (Mermaid), see [docs/architecture.md](docs/architecture.md).

---

## Key Engineering Decisions

**Fail-closed filter chain.** Every signal initializes as rejected. A token must explicitly pass all 12 filters to reach execution. This is the opposite of most trading bots, which start with "buy everything" and try to filter out the bad ones.

**curl subprocess over aiohttp for external APIs.** After debugging silent failures with aiohttp on DexScreener and Birdeye endpoints, I built a `curl_get()` wrapper that shells out to curl. aiohttp is reserved for RPC and Jupiter calls where connection pooling matters. This is documented as Hotfix #1.

**Custom .env loader over python-dotenv.** python-dotenv breaks on quoted values in certain configurations. Rather than work around the library, I wrote a 15-line `EnvLoader` class that handles all quote styles. Documented as Hotfix #2.

**7-tier exit priority chain.** Position exits are evaluated in strict priority order every 3 seconds: hard floor (absolute loss cap) → emergency rug detection → take profit → trailing stop → sniper timeout (cut non-runners at 60s) → stop loss → time-based timeout. The ordering prevents a trailing stop from overriding a rug detection.

**Self-regulation without filter mutation.** The self-regulation module controls *whether* to trade (regime switching: normal → cautious → paused), but never touches *how* to filter. Earlier versions had a death spiral where bad performance loosened filters, which found worse tokens, which caused worse performance.

**JIT final gate.** Even after a token passes all filters, the execution layer re-fetches live data from DexScreener at the moment of trade. Cached scanner data can be 30+ seconds stale — in memecoins, that's a lifetime.

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.12 |
| Async Runtime | asyncio + aiohttp |
| Blockchain | Solana (solders, base58) |
| DEX Aggregator | Jupiter v6 (VersionedTransaction) |
| Data Sources | DexScreener, Birdeye, Helius RPC |
| Database | SQLite (thread-safe with locking) |
| Infrastructure | Linux VPS, systemd, journalctl |
| Monitoring | Custom dashboard (port 8443) |

---

## Project Structure

```
moss-lane/
├── engine/
│   ├── lazarus.py              # Main trading engine (~1,250 lines)
│   ├── learning_engine.py      # Self-learning module (trade analysis, position sizing)
│   └── self_regulation.py      # Regime switching (streak detection, auto-pause)
├── docs/
│   ├── architecture.md         # Full system architecture with Mermaid diagrams
│   ├── brand-book.md           # Project identity and design system
│   └── team-architecture.md    # AI persona engineering framework
└── .env.example                # Required environment variables
```

---

## Configuration

The engine is configured through a single `CFG` dictionary at the top of `lazarus.py`. Key parameters:

| Parameter | Value | Purpose |
|-----------|-------|---------|
| `position_pct` | 15% | Per-trade position size (floor 10%, ceiling 30%) |
| `take_profit` | +25% | Take-profit threshold |
| `stop_loss` | -8% | Stop-loss threshold |
| `hard_floor` | -15% | Absolute kill switch — no exceptions |
| `trail_arm` / `trail_pct` | +8% / 4% | Trailing stop activation and distance |
| `sniper_timeout_sec` | 60s | Cut non-runners under +1% |
| `min_chg_pct` / `max_chg_pct` | 10-80% | Hourly change filter window |
| `min_liq` | $50,000 | Minimum liquidity floor |
| `cooldown_seconds` | 7,200 (2hr) | Per-token cooldown after exit |
| `daily_loss_limit_pct` | 10% | Portfolio drawdown halt |

---

## What I Learned Building This

This project taught me more than any course or certification could have. Specific skills developed through direct implementation:

- **Python** — async/await patterns, dataclasses, thread-safe SQLite, subprocess management, custom configuration parsing
- **Linux/DevOps** — systemd service management, journalctl, SSH key management, VPS administration
- **Databases** — SQLite schema design, conflict resolution (`ON CONFLICT DO UPDATE`), performance queries, migration patterns
- **APIs** — REST consumption (DexScreener, Birdeye, Helius), rate limiting, retry logic, timeout handling
- **Blockchain** — Solana transaction signing, Jupiter DEX integration, VersionedTransaction construction, RPC methods
- **Systems Design** — fail-closed architectures, regime-based self-regulation, adaptive parameter tuning with safety bounds
- **Debugging** — root-cause analysis on silent failures, latency auditing, production incident response

---

## Naming

**Moss Lane** is named after the streets around Manchester City's old Maine Road stadium — before the money, before the Etihad, when showing up meant something.

**Lazarus** is named for City's fall to the third division and resurrection back to champions. Also an Oasis deep cut.

Together: *Moss Lane, powered by Lazarus.*

---

## Status

This is an active, evolving project. The engine runs on a VPS and has gone through three major versions, each informed by real trade data and post-mortem analysis. Current version (v3.0) is in paper trading validation.

---

## Author

**Josh Hillard**
- 8+ years in technical operations and escalation management
- Google AI Certified
- Building in public to demonstrate that strong systems thinking transfers across domains

---

## License

This project is shared for educational and portfolio purposes. The code demonstrates real engineering decisions made under real constraints. If you're building something similar, I hope it's useful.

MIT License — see [LICENSE](LICENSE) for details.
