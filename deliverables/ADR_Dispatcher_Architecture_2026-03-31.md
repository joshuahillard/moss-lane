# Architecture Decision Record — Multi-Wallet Dispatcher

**Project:** Moss Lane
**Component:** Lazarus Engine — Phase 2 Dispatcher
**Author:** Josh Hillard (TPM), with SecOps & DevOps review
**Date:** 2026-03-31
**Status:** Accepted (design phase)
**Reviewers:** Principal Cloud & SecOps Engineer, DevOps / Release Engineer

---

## Executive Summary

This ADR documents three foundational architectural decisions for the Lazarus multi-wallet dispatcher — the system that will scale a single-process trading engine into a coordinated fleet of five independent wallet processes plus a tax vault. Each decision was evaluated against security, latency, operational complexity, and fund isolation requirements. The decisions below represent the tradeoff analysis performed during the Phase 2 architecture design sprint (2026-03-31).

---

## ADR-001: Independent Keypairs vs. HD Wallet Derivation

### Context

Lazarus Phase 2 requires five burner wallets plus a tax vault, each capable of executing trades independently on Solana mainnet. The system needs a key management strategy that balances security, operational simplicity, and recoverability.

Two approaches were evaluated:

- **Option A — Hierarchical Deterministic (HD) Derivation:** Generate all wallet keypairs from a single master seed using BIP-44 derivation paths (m/44'/501'/0'/0' through m/44'/501'/4'/0'). A single seed phrase recovers every wallet. This is the standard approach in consumer wallets (Phantom, Solflare) and multi-account DeFi tooling.

- **Option B — Independent Keypairs:** Generate six independent Ed25519 keypairs (five burners + one tax vault), each with its own private key stored in a separate, permission-isolated file on the server. No shared derivation path. Recovery requires all six keys individually.

### Decision

**Option B — Independent Keypairs.**

Each wallet process loads its own keypair from a dedicated file (`/home/solbot/lazarus/keys/wallet_N.json`) with `0600` permissions owned by the service user. No master seed exists on the server.

### Rationale

1. **Blast radius containment.** If a single wallet key is compromised (server breach, log leak, misconfigured permissions), the attacker gains access to one wallet's funds — not all six. With HD derivation, compromising the master seed compromises every derived wallet simultaneously. For a system holding real capital, the blast radius difference between "one wallet" and "all wallets" is the difference between a recoverable incident and total loss.

2. **No derivation library dependency.** HD derivation on Solana requires either `solders` BIP-44 support or a third-party library like `bip-utils`. Adding a derivation dependency introduces a supply chain attack surface and a maintenance burden. Independent keypairs use only `solders.Keypair.from_bytes()`, which is already battle-tested in the v3.0 codebase.

3. **Operational isolation.** Each wallet's systemd service loads only its own key. There is no shared secret that multiple processes reference. This means wallet quarantine (stopping one service) has zero risk of accidentally exposing or locking another wallet's credentials.

### Tradeoffs

- **Recovery complexity increases.** With HD derivation, a single 24-word seed phrase recovers everything. With independent keypairs, Josh must securely back up six separate key files. If any single backup is lost or corrupted, that wallet's funds are irrecoverable. This is a real operational burden — six points of failure instead of one.

- **No deterministic re-derivation.** If the server is destroyed, HD wallets can be re-derived on any machine from the seed phrase. Independent keypairs require the actual key files to be restored from backup. This makes disaster recovery slower and more error-prone.

- **Rotation is manual.** Rotating a compromised key requires generating a new keypair, transferring funds from the old wallet, updating the service configuration, and restarting. HD derivation allows incrementing the derivation index, which is marginally simpler but still requires fund transfer.

### Consequences

- A secure backup protocol must be established before deployment: encrypted key file export to an offline medium (USB drive, encrypted cloud vault), tested with a restore drill.
- The coordinator module must handle wallet identity by file path, not derivation index. Wallet discovery is file-based, not algorithmic.
- Adding a sixth burner wallet in a future phase requires generating a new keypair, deploying a new systemd service, and updating the coordinator's wallet registry — a manual process, not a config change.

---

## ADR-002: Single Scanner with Coordinator vs. Per-Wallet Scanners

### Context

The current Lazarus v3.0 architecture is a single-process system: one scanner discovers tokens, one decision engine evaluates them, one execution path buys and sells. Phase 2 introduces five wallet processes that need token signals. The question is how scanning and signal distribution should work.

Three approaches were evaluated:

- **Option A — Per-Wallet Scanners:** Each wallet process runs its own DexScreener scanner, independently discovering and evaluating tokens. Five wallets means five scanners hitting the DexScreener API in parallel.

- **Option B — Single Scanner with Message Queue:** A dedicated scanner process discovers tokens and publishes signals to a message broker (Redis Pub/Sub, ZeroMQ, or SQLite WAL). Each wallet process subscribes to the signal stream and independently decides whether to act.

- **Option C — Single Scanner with Coordinator Process:** A single scanner process discovers tokens and passes them to a coordinator module. The coordinator decides which wallet gets which signal based on routing rules (strategy assignment, balance availability, cooldown state). Wallets receive pre-routed instructions, not raw signals.

### Decision

**Option C — Single Scanner with Coordinator Process.**

A single `lazarus_coordinator.py` process owns the scanner loop. It evaluates tokens through the existing 9-point filter cascade, then routes qualifying signals to specific wallet processes via a lightweight IPC mechanism (SQLite WAL-mode shared database with a `signal_queue` table, polled by each wallet at 1-second intervals).

### Rationale

1. **API rate limit protection.** DexScreener's free API has undocumented rate limits. Running five independent scanners multiplies API calls by 5x, dramatically increasing the risk of rate limiting or IP-level blocking. A single scanner makes one set of API calls regardless of how many wallets consume the results. This is the same pattern used in market data distribution at institutional trading firms — one feed handler, many consumers.

2. **Signal consistency.** If five scanners each hit DexScreener at slightly different times, they may see different prices, different hourly change percentages, and different liquidity values for the same token. This creates a race condition where Wallet A buys at one price while Wallet B's scanner shows the token has already moved past the filter window. A single scanner produces one canonical view of the market per cycle, eliminating signal divergence.

3. **Routing intelligence.** The coordinator can implement strategy-level routing: Wallet 1 gets high-conviction signals (top-of-funnel, tightest filters), Wallet 5 gets experimental signals (wider filters, smaller position sizes). Per-wallet scanners would require duplicating and diverging the filter configuration across five processes — a maintenance nightmare and a source of configuration drift.

4. **Resource efficiency.** One scanner process uses ~50MB of memory and one set of network connections. Five scanners would consume ~250MB and five concurrent connection pools. On a $6/month VPS with 1GB RAM, this matters.

### Tradeoffs

- **Single point of failure.** If the coordinator crashes, all five wallets lose their signal source simultaneously. With per-wallet scanners, a single scanner crash only affects one wallet. This is the classic centralization tradeoff: efficiency vs. resilience. Mitigation: systemd auto-restart with a 5-second recovery window, plus a heartbeat check where wallets enter a "signal drought" safe mode if no signals arrive for 3 consecutive cycles.

- **Coordinator bottleneck.** All signal processing flows through one process. If the coordinator's scan cycle takes longer than expected (DexScreener latency spike, filter evaluation load), all wallets are delayed equally. Per-wallet scanners would degrade independently. At current scale (30-second scan cycles, ~200 tokens per cycle), this is not a practical concern — but it becomes one if we scale to sub-second scanning or 10+ wallets.

- **Added complexity.** The coordinator is a new process that didn't exist in v3.0. It requires its own systemd service, its own health monitoring, its own failure modes. This is net-new operational surface area. The alternative (per-wallet scanners) is architecturally simpler — just copy the existing bot five times with different keys.

- **IPC reliability.** SQLite WAL-mode polling is simple and battle-tested, but it's not a real message queue. There's no delivery guarantee, no acknowledgment, no retry. If a wallet misses a signal (slow poll cycle, momentary DB lock), that signal is gone. A proper message broker (Redis, ZeroMQ) would provide these guarantees but adds infrastructure dependencies to a $6/month VPS. We chose simplicity over delivery guarantees, accepting that missed signals are a tolerable failure mode — the market produces new signals every 30 seconds.

### Consequences

- The `lazarus_coordinator.py` module becomes the most critical process in the system. Its uptime directly determines the uptime of all trading activity. It must be the most thoroughly tested and monitored component.
- Wallet processes become simpler: they no longer need scanner logic, only execution logic. This separation of concerns makes each wallet process easier to test, deploy, and reason about.
- Scaling beyond five wallets requires only adding new wallet processes and updating the coordinator's routing table — the scanner itself doesn't change.
- Future migration to a real message broker (if scale demands it) requires changing only the IPC layer, not the scanner or wallet logic. The coordinator pattern provides this clean boundary.

---

## ADR-003: Tax Vault Skim Timing — Per-Trade vs. Batch vs. Threshold

### Context

The tax vault is a dedicated wallet that accumulates 15% of realized profits from every winning trade. Its purpose is fund preservation: it isolates gains from trading capital so that a drawdown in the burner wallets cannot consume profits already earned. The question is when and how the skim occurs.

Three approaches were evaluated:

- **Option A — Per-Trade Skim:** Immediately after every profitable sell, the wallet transfers 15% of the realized gain to the tax vault. The skim happens in the same transaction flow as the trade exit.

- **Option B — Batch Skim (Time-Based):** Profits accumulate in each burner wallet. A scheduled job (every 4 hours, or once daily) calculates total unrealized skims and executes batch transfers to the tax vault.

- **Option C — Threshold Skim:** Profits accumulate until a wallet's skim-eligible balance exceeds a threshold (e.g., 0.5 SOL). Once the threshold is met, the full skim amount is transferred.

### Decision

**Option C — Threshold Skim with a floor of 0.1 SOL per transfer.**

Each wallet process tracks cumulative unrealized skim in a local counter (persisted in its database partition). When the accumulated skim exceeds 0.1 SOL, the wallet initiates a transfer to the tax vault address. The coordinator monitors skim status across wallets for observability, but does not initiate transfers — each wallet owns its own skim execution.

### Rationale

1. **Transaction fee efficiency.** Solana transaction fees are ~0.000005 SOL per transfer, which is negligible in absolute terms. However, on small wallets holding 0.5–2.0 SOL, a per-trade skim of 15% on a +25% gain from a 15% position yields ~0.0094 SOL. The transaction fee is 0.05% of that skim — small but non-zero, and it compounds across hundreds of trades. Threshold skimming batches these micro-transfers into fewer, larger transfers, reducing cumulative fee drag.

2. **Execution simplicity.** Per-trade skimming requires adding a transfer instruction to the sell transaction flow. This means the sell confirmation must wait for both the swap confirmation AND the skim transfer confirmation before the trade is considered complete. If the skim transfer fails (network congestion, insufficient rent-exempt balance), the system enters an ambiguous state: the trade succeeded but the skim didn't. Threshold skimming decouples the skim from the trade — the trade closes cleanly, and the skim is a separate, independent operation.

3. **Latency preservation.** The sell-to-scan cycle time matters. After closing a position, the wallet should immediately be available for the next signal. Per-trade skimming adds 400-800ms of blocking latency (transfer submission + confirmation) to every profitable exit. Threshold skimming can run asynchronously between scan cycles, adding zero latency to the critical trading path.

4. **Auditability.** Threshold skimming creates a clean audit trail: each skim transfer is a discrete, timestamped event with a known amount. The `skim_log` table records: wallet_id, amount, timestamp, tx_signature. Per-trade skimming would produce hundreds of micro-transfers that are harder to reconcile.

### Tradeoffs

- **Delayed fund isolation.** Profits sit in the burner wallet until the threshold is met. If the wallet suffers a catastrophic loss (rug pull on the next trade, flash crash) before the skim threshold is reached, those profits are lost. Per-trade skimming provides immediate isolation — the moment a profit is realized, 15% is protected. The threshold approach accepts a window of vulnerability in exchange for operational simplicity. Mitigation: the 0.1 SOL threshold is deliberately low to minimize the maximum unprotected profit at any given time.

- **Counter state management.** Each wallet must persist its cumulative skim counter across restarts. If the counter is lost (DB corruption, bad restart), the wallet either double-skims (if the counter resets to zero and skims are recalculated from trade history) or under-skims (if the counter resets and no reconciliation runs). Mitigation: the skim counter is stored in the wallet's SQLite database with a reconciliation query that can rebuild it from the `trades` table if needed.

- **No real-time tax vault balance accuracy.** Because skims are batched, the tax vault balance at any given moment doesn't reflect the true "earned and owed" amount. There's always a lag between profit realization and vault deposit. For reporting and observability, the coordinator must sum both the vault balance AND the pending skim counters across all wallets to show the true "protected profit" number.

- **Threshold tuning risk.** If the threshold is set too high (e.g., 1.0 SOL), small wallets may never trigger a skim — their individual trades don't generate enough profit to clear the bar. If set too low (e.g., 0.01 SOL), the system loses the batching benefit and approaches per-trade behavior. The 0.1 SOL floor is calibrated to current wallet sizes (0.5–2.0 SOL per burner) and expected win sizes, but it will need adjustment as wallet balances grow.

### Consequences

- Each wallet process includes a `skim_manager` module that tracks cumulative owed skim and triggers transfers when the threshold is met.
- The coordinator's observability layer must display both realized vault balance and pending skim amounts for accurate profit reporting.
- The threshold value (0.1 SOL) should be stored in the `bot_config` table — not hardcoded — so it can be tuned as wallet balances scale without code changes.
- If a wallet is quarantined (stopped due to loss limit breach), any pending skim must be transferred as part of the quarantine procedure, not abandoned.

---

## Decision Matrix Summary

| Decision | Choice | Primary Driver | Biggest Sacrifice |
|----------|--------|---------------|-------------------|
| ADR-001: Key Management | Independent Keypairs | Blast radius containment | Recovery complexity (6 keys vs. 1 seed) |
| ADR-002: Signal Distribution | Single Scanner + Coordinator | API rate protection + signal consistency | Single point of failure |
| ADR-003: Tax Vault Skim | Threshold (0.1 SOL floor) | Latency preservation + fee efficiency | Delayed fund isolation window |

---

## Cross-Cutting Concerns

### Observability

All three decisions create observability requirements that didn't exist in the single-process v3.0:

- Key management: log which wallet executed which trade (wallet_id in every trade record)
- Coordinator: monitor signal distribution latency, queue depth, per-wallet signal acceptance rate
- Skim manager: track pending vs. transferred skim, alert if any wallet's pending skim exceeds 2x the threshold

### Failure Modes

Each decision introduces a unique failure mode:

- ADR-001: Key loss → permanent fund loss for that wallet (mitigated by backup protocol)
- ADR-002: Coordinator crash → all wallets blind (mitigated by systemd auto-restart + safe mode)
- ADR-003: Counter corruption → skim accounting drift (mitigated by reconciliation query)

### Security Boundaries

The independent keypair decision (ADR-001) establishes the security foundation for the other two decisions. The coordinator (ADR-002) never holds private keys — it routes signals, not funds. The skim manager (ADR-003) executes transfers using only its own wallet's keypair, never accessing another wallet's key material. No process in the system requires access to more than one private key.

---

## Appendix: Interview Framing

### Resume Bullets (X-Y-Z Format)

1. **Designed multi-wallet trading dispatcher architecture** handling concurrent execution across 5 independent wallets as measured by documented tradeoff analysis across security, latency, and fund isolation, by evaluating 9+ design alternatives and authoring 3 Architecture Decision Records with enterprise-grade documentation standards.

2. **Architected signal distribution system** that reduced API call volume by 80% (5x to 1x) as measured by single-scanner coordinator pattern with SQLite WAL-mode IPC, by evaluating centralized vs. distributed scanning tradeoffs against rate limiting, signal consistency, and resource constraints on a $6/month VPS.

3. **Engineered fund isolation mechanism** protecting realized trading profits via threshold-triggered vault transfers as measured by zero-latency impact on the critical trading path, by decoupling profit skimming from trade execution with configurable threshold, persistent state tracking, and automated reconciliation.

### Interview Talking Points: "Tell Me About a Time You Designed a Distributed System"

**Setup (30 seconds):**
"I was building an automated trading system on Solana that started as a single-process bot. When we needed to scale to multiple wallets executing concurrently, I had to design the transition from monolith to distributed — specifically, how to split scanning, execution, and fund management across independent processes while maintaining consistency and fault tolerance."

**Key Decisions (60 seconds):**
"Three decisions defined the architecture. First, key management: I chose independent keypairs over HD wallet derivation to contain blast radius — if one wallet is compromised, the others are unaffected. Second, signal distribution: instead of running parallel scanners that would multiply our API calls and create signal divergence, I designed a single-scanner coordinator that routes signals to wallets through a SQLite-based IPC layer. Third, fund isolation: I implemented threshold-triggered profit skimming that decouples capital preservation from the hot execution path, avoiding the 400-800ms latency hit that per-trade skimming would introduce."

**Tradeoffs (30 seconds):**
"Each decision has a real cost. Independent keypairs mean six backup points instead of one — that's operational burden I accepted for security. The coordinator is a single point of failure — I mitigated with systemd auto-restart and a 'signal drought' safe mode where wallets stop trading if they lose their signal source. And threshold skimming means there's always a small window where profits aren't yet isolated — I kept the threshold low to minimize that exposure."

**What I'd Do Differently at Scale (30 seconds):**
"At current scale — five wallets on a single VPS — SQLite IPC is appropriate. If this needed to support 50+ wallets across multiple servers, I'd replace the SQLite signal queue with Redis Pub/Sub or a proper message broker, and I'd move the coordinator behind a load balancer. The architecture was designed with that migration path in mind — the coordinator pattern provides a clean boundary between signal production and consumption."

---

*Document authored under the Moss Lane Hardened Fortress Protocol. All tradeoff sections reviewed for intellectual honesty by the SecOps persona.*

*Quiet streets, loud comebacks.*
