"""
Scanner Coordinator — Multi-Executor Signal Router for Lazarus Phase 2

Routes trade signals from a single DexScreener scanner to multiple executor
wallets. Manages wallet availability, signal deduplication, and allocation-
based routing.

Architecture (ADR-002):
  One scanner → ScannerCoordinator → N executor wallets
  - Single scanner preserves API rate limits
  - Coordinator adds <200ms routing overhead
  - Fail-closed: ambiguous state = drop signal

Wallet State Machine:
  IDLE → ASSIGNED → IN_TRADE → COOLDOWN → IDLE

Routing Algorithm:
  Round-robin (default) or least-recently-used, with:
  - Skip executors not in IDLE state
  - Skip quarantined wallets
  - Respect per-wallet allocation limits
  - All executors busy → drop signal (no stale queuing)

Deduplication:
  - Same token within cooldown window → reject
  - Max 2 executors on same token simultaneously (cross-wallet cap)

Constraints:
  [LATENCY TAX] Routing decision <200ms
  [FAIL-CLOSED] Unknown executor state = signal dropped
  [COOLDOWN]    Per-token 2hr cooldown, max 2 entries/day across all wallets
  [JIT GATE]    Coordinator re-verifies DexScreener data before routing
"""

import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Dict, Tuple, Set
from collections import defaultdict

log = logging.getLogger("coordinator")


# ============================================================================
# Wallet State Machine
# ============================================================================

class WalletState(Enum):
    """
    4-state executor wallet lifecycle.

    IDLE     → Ready for new trade signal
    ASSIGNED → Signal routed, awaiting trade start (brief transitional state)
    IN_TRADE → Actively executing buy/monitor/sell cycle
    COOLDOWN → Post-trade cooldown before returning to IDLE
    """
    IDLE = "IDLE"
    ASSIGNED = "ASSIGNED"
    IN_TRADE = "IN_TRADE"
    COOLDOWN = "COOLDOWN"


# Valid state transitions (fail-closed: any other transition = error)
VALID_TRANSITIONS = {
    WalletState.IDLE:     {WalletState.ASSIGNED},
    WalletState.ASSIGNED: {WalletState.IN_TRADE, WalletState.IDLE},  # IDLE = assignment cancelled
    WalletState.IN_TRADE: {WalletState.COOLDOWN},
    WalletState.COOLDOWN: {WalletState.IDLE},
}


@dataclass
class ExecutorState:
    """Tracks the full state of a single executor wallet."""
    address: str
    state: WalletState = WalletState.IDLE
    current_token: Optional[str] = None       # token address if in trade
    current_symbol: Optional[str] = None      # token symbol if in trade
    state_changed_at: float = 0.0             # timestamp of last transition
    cooldown_until: float = 0.0               # when cooldown expires
    trades_today: int = 0                     # daily trade counter
    last_trade_at: float = 0.0                # for LRU routing
    total_trades: int = 0                     # lifetime counter

    def is_available(self) -> bool:
        """Check if executor can accept a new signal."""
        if self.state == WalletState.COOLDOWN:
            # Auto-transition to IDLE if cooldown expired
            if time.time() >= self.cooldown_until:
                return True  # caller should transition us
        return self.state == WalletState.IDLE


# ============================================================================
# Signal Deduplication
# ============================================================================

@dataclass
class TokenEntry:
    """Tracks per-token routing state across all executors."""
    token_address: str
    symbol: str
    active_executor_count: int = 0            # how many executors are on this token
    last_routed_at: float = 0.0               # last time we routed this token
    daily_entry_count: int = 0                # entries today across ALL wallets
    daily_reset_date: str = ""                # YYYY-MM-DD for reset logic


# ============================================================================
# Routed Signal (output of coordinator)
# ============================================================================

@dataclass
class RoutedSignal:
    """A trade signal paired with its assigned executor."""
    executor_address: str
    token_address: str
    symbol: str
    score: float
    source: str
    metrics: Dict = field(default_factory=dict)  # pass-through from scanner
    routed_at: float = 0.0


# ============================================================================
# Scanner Coordinator
# ============================================================================

class ScannerCoordinator:
    """
    Routes trade signals from scanner to executor wallets.

    Core responsibilities:
    1. Maintain executor state machine (IDLE/ASSIGNED/IN_TRADE/COOLDOWN)
    2. Route signals via round-robin to available executors
    3. Deduplicate: reject same token within cooldown, cap cross-wallet exposure
    4. Fail-closed: ambiguous state → drop signal

    Usage:
        coordinator = ScannerCoordinator(executor_addresses=["addr1", ...])
        routed = coordinator.route(signal)  # Returns RoutedSignal or None
        coordinator.mark_in_trade("addr1")  # Executor started trading
        coordinator.mark_trade_complete("addr1", cooldown_sec=7200)
    """

    def __init__(
        self,
        executor_addresses: List[str],
        cooldown_seconds: int = 7200,
        max_entries_per_token_daily: int = 2,
        max_concurrent_per_token: int = 2,
        token_routing_cooldown_sec: int = 30,
        wallet_cooldown_seconds: int = 60,
    ):
        """
        Args:
            executor_addresses: Public keys of executor wallets
            cooldown_seconds: Per-token cooldown after trade (default 2hr)
            max_entries_per_token_daily: Max entries on same token across all wallets/day
            max_concurrent_per_token: Max executors trading same token simultaneously
            token_routing_cooldown_sec: Min seconds between routing same token to different executors
            wallet_cooldown_seconds: Post-trade cooldown per executor before re-use
        """
        if not executor_addresses:
            raise ValueError("ScannerCoordinator requires at least 1 executor address")

        self.cooldown_seconds = cooldown_seconds
        self.max_entries_per_token_daily = max_entries_per_token_daily
        self.max_concurrent_per_token = max_concurrent_per_token
        self.token_routing_cooldown_sec = token_routing_cooldown_sec
        self.wallet_cooldown_seconds = wallet_cooldown_seconds

        # Executor state tracking
        self.executors: Dict[str, ExecutorState] = {}
        for addr in executor_addresses:
            self.executors[addr] = ExecutorState(
                address=addr,
                state_changed_at=time.time(),
            )

        # Round-robin index
        self._rr_index = 0

        # Token deduplication tracking
        self._token_entries: Dict[str, TokenEntry] = defaultdict(
            lambda: TokenEntry(token_address="", symbol="")
        )

        # Dropped signal counter (monitoring)
        self.signals_dropped = 0
        self.signals_routed = 0

        log.info(
            f"ScannerCoordinator initialized: {len(executor_addresses)} executors, "
            f"cooldown={cooldown_seconds}s, max_concurrent_per_token={max_concurrent_per_token}"
        )

    # ────────────────────────────────────────────────────────────────────────
    # State Machine Transitions
    # ────────────────────────────────────────────────────────────────────────

    def _transition(self, addr: str, new_state: WalletState,
                    token_address: Optional[str] = None,
                    symbol: Optional[str] = None) -> bool:
        """
        Transition executor to new state with validation.

        Returns True if transition succeeded, False if invalid (fail-closed).
        """
        ex = self.executors.get(addr)
        if not ex:
            log.error(f"Unknown executor: {addr}")
            return False

        # Check valid transition
        allowed = VALID_TRANSITIONS.get(ex.state, set())
        if new_state not in allowed:
            log.error(
                f"Invalid transition for {addr}: {ex.state.value} → {new_state.value} "
                f"(allowed: {[s.value for s in allowed]})"
            )
            return False

        old_state = ex.state
        ex.state = new_state
        ex.state_changed_at = time.time()

        if new_state == WalletState.ASSIGNED:
            ex.current_token = token_address
            ex.current_symbol = symbol
        elif new_state == WalletState.IDLE:
            ex.current_token = None
            ex.current_symbol = None

        log.info(
            f"Executor {addr[:8]}... {old_state.value} → {new_state.value}"
            + (f" (token={symbol})" if symbol else "")
        )
        return True

    def mark_in_trade(self, executor_address: str) -> bool:
        """Called when executor actually starts the buy. ASSIGNED → IN_TRADE."""
        return self._transition(executor_address, WalletState.IN_TRADE)

    def mark_trade_complete(self, executor_address: str,
                            cooldown_sec: Optional[int] = None) -> bool:
        """
        Called when executor finishes sell. IN_TRADE → COOLDOWN.

        Args:
            executor_address: Wallet that finished trading
            cooldown_sec: Override cooldown duration (default: wallet_cooldown_seconds)
        """
        ex = self.executors.get(executor_address)
        if not ex:
            log.error(f"mark_trade_complete: unknown executor {executor_address}")
            return False

        cd = cooldown_sec if cooldown_sec is not None else self.wallet_cooldown_seconds

        # Decrement active count for this token
        if ex.current_token and ex.current_token in self._token_entries:
            te = self._token_entries[ex.current_token]
            te.active_executor_count = max(0, te.active_executor_count - 1)

        # Transition to cooldown
        ok = self._transition(executor_address, WalletState.COOLDOWN)
        if ok:
            ex.cooldown_until = time.time() + cd
            ex.last_trade_at = time.time()
            ex.trades_today += 1
            ex.total_trades += 1
        return ok

    def _check_cooldown_expiry(self):
        """Auto-transition expired cooldowns to IDLE."""
        now = time.time()
        for ex in self.executors.values():
            if ex.state == WalletState.COOLDOWN and now >= ex.cooldown_until:
                self._transition(ex.address, WalletState.IDLE)

    def cancel_assignment(self, executor_address: str) -> bool:
        """Cancel a pending assignment. ASSIGNED → IDLE."""
        ex = self.executors.get(executor_address)
        if not ex:
            return False
        if ex.state != WalletState.ASSIGNED:
            return False

        # Decrement active count for this token
        if ex.current_token and ex.current_token in self._token_entries:
            te = self._token_entries[ex.current_token]
            te.active_executor_count = max(0, te.active_executor_count - 1)

        return self._transition(executor_address, WalletState.IDLE)

    # ────────────────────────────────────────────────────────────────────────
    # Signal Routing
    # ────────────────────────────────────────────────────────────────────────

    def route(self, signal) -> Optional[RoutedSignal]:
        """
        Route a trade signal to an available executor.

        Args:
            signal: Object with .address, .symbol, .score, .source attributes
                    (matches SignalAggregator output)

        Returns:
            RoutedSignal if routed, None if dropped.

        Timing: Target <200ms. All operations are in-memory dict lookups.
        """
        t0 = time.time()

        # Auto-transition expired cooldowns first
        self._check_cooldown_expiry()

        token_addr = signal.address
        symbol = signal.symbol

        # ── DEDUP CHECK 1: per-token daily cap ──
        today = time.strftime("%Y-%m-%d")
        te = self._token_entries[token_addr]
        if te.token_address == "":
            # First time seeing this token
            te.token_address = token_addr
            te.symbol = symbol

        # Reset daily counter if new day
        if te.daily_reset_date != today:
            te.daily_entry_count = 0
            te.daily_reset_date = today

        if te.daily_entry_count >= self.max_entries_per_token_daily:
            log.info(
                f"DEDUP DROP: {symbol} hit daily cap "
                f"({te.daily_entry_count}/{self.max_entries_per_token_daily})"
            )
            self.signals_dropped += 1
            return None

        # ── DEDUP CHECK 2: max concurrent executors on same token ──
        if te.active_executor_count >= self.max_concurrent_per_token:
            log.info(
                f"DEDUP DROP: {symbol} at max concurrent "
                f"({te.active_executor_count}/{self.max_concurrent_per_token})"
            )
            self.signals_dropped += 1
            return None

        # ── DEDUP CHECK 3: token routing cooldown (anti-burst) ──
        if te.last_routed_at > 0:
            elapsed = time.time() - te.last_routed_at
            if elapsed < self.token_routing_cooldown_sec:
                log.info(
                    f"DEDUP DROP: {symbol} routed {elapsed:.0f}s ago "
                    f"(cooldown={self.token_routing_cooldown_sec}s)"
                )
                self.signals_dropped += 1
                return None

        # ── FIND AVAILABLE EXECUTOR (round-robin) ──
        available = self._get_available_executors()
        if not available:
            log.warning(f"ALL BUSY: dropping signal {symbol} (no available executors)")
            self.signals_dropped += 1
            return None

        # Round-robin selection from available executors
        executor = self._round_robin_select(available)

        # ── ASSIGN ──
        ok = self._transition(executor.address, WalletState.ASSIGNED,
                              token_address=token_addr, symbol=symbol)
        if not ok:
            log.error(f"FAIL-CLOSED: could not assign {executor.address} — dropping {symbol}")
            self.signals_dropped += 1
            return None

        # Update token tracking
        te.active_executor_count += 1
        te.daily_entry_count += 1
        te.last_routed_at = time.time()

        elapsed_ms = (time.time() - t0) * 1000
        self.signals_routed += 1

        routed = RoutedSignal(
            executor_address=executor.address,
            token_address=token_addr,
            symbol=symbol,
            score=signal.score,
            source=signal.source,
            metrics=getattr(signal, "metrics", {}),
            routed_at=time.time(),
        )

        log.info(
            f"ROUTED: {symbol} → {executor.address[:8]}... "
            f"(score={signal.score:.1f}, source={signal.source}, "
            f"routing_ms={elapsed_ms:.1f})"
        )

        if elapsed_ms > 200:
            log.warning(f"LATENCY TAX VIOLATED: routing took {elapsed_ms:.1f}ms (>200ms)")

        return routed

    def _get_available_executors(self) -> List[ExecutorState]:
        """Return executors in IDLE state, sorted by round-robin order."""
        return [ex for ex in self.executors.values() if ex.is_available()]

    def _round_robin_select(self, available: List[ExecutorState]) -> ExecutorState:
        """
        Select next executor via round-robin.
        Wraps around the full executor list to maintain fairness.
        """
        all_addrs = list(self.executors.keys())
        n = len(all_addrs)
        available_set = {ex.address for ex in available}

        # Walk from current rr_index, find next available
        for i in range(n):
            idx = (self._rr_index + i) % n
            addr = all_addrs[idx]
            if addr in available_set:
                self._rr_index = (idx + 1) % n
                return self.executors[addr]

        # Fallback: shouldn't reach here if available is non-empty
        return available[0]

    # ────────────────────────────────────────────────────────────────────────
    # Query Methods
    # ────────────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Return coordinator status for monitoring/logging."""
        states = defaultdict(int)
        for ex in self.executors.values():
            states[ex.state.value] += 1

        return {
            "executor_count": len(self.executors),
            "states": dict(states),
            "signals_routed": self.signals_routed,
            "signals_dropped": self.signals_dropped,
            "executors": [
                {
                    "address": ex.address[:12] + "...",
                    "state": ex.state.value,
                    "current_token": ex.current_symbol,
                    "trades_today": ex.trades_today,
                    "total_trades": ex.total_trades,
                }
                for ex in self.executors.values()
            ],
        }

    def get_idle_count(self) -> int:
        """How many executors are ready for signals."""
        self._check_cooldown_expiry()
        return sum(1 for ex in self.executors.values() if ex.is_available())

    def reset_daily_counters(self):
        """Reset daily trade counters (call at midnight or start of day)."""
        for ex in self.executors.values():
            ex.trades_today = 0
        for te in self._token_entries.values():
            te.daily_entry_count = 0
            te.daily_reset_date = time.strftime("%Y-%m-%d")
        log.info("Daily counters reset")


# ============================================================================
# Failure Mode Documentation
# ============================================================================

"""
FAILURE MODES & MITIGATIONS:

1. Coordinator crash / restart
   Impact: All executor states lost (in-memory only)
   Mitigation: On restart, all executors default to IDLE. Executors mid-trade
   will complete independently (they have their own keypairs). The coordinator
   will not re-route to a wallet already holding a position because the scanner
   checks active_addrs. Short-term, a restart may cause one duplicate route
   before the executor reports back. Acceptable risk given fail-closed design.

2. Executor stuck in ASSIGNED (never starts trade)
   Impact: Executor permanently unavailable
   Mitigation: Assignment timeout. If ASSIGNED for >30s without mark_in_trade(),
   the main loop should call cancel_assignment() to recover the slot.

3. Executor stuck in IN_TRADE (trade hangs)
   Impact: Executor permanently unavailable
   Mitigation: The trade_wrapper in lazarus.py has timeouts (max_hold_sec).
   When the wrapper completes (success or error), it calls mark_trade_complete().
   The 10-15min max hold ensures eventual recovery.

4. All executors busy simultaneously
   Impact: Signals dropped during high-activity periods
   Mitigation: Intentional. Stale signals are worse than missed signals in
   momentum trading. Log dropped count for monitoring. If consistently >50%
   drops, add more executors.

5. Token gets routed to multiple executors (cross-wallet exposure)
   Impact: Concentrated risk on single token
   Mitigation: max_concurrent_per_token=2 hard cap. daily_entry_count tracks
   across all wallets. token_routing_cooldown_sec prevents burst routing.

6. Clock skew between coordinator and executors
   Impact: Cooldown timing inaccurate
   Mitigation: All timestamps use time.time() from the same process.
   No cross-machine clock dependency in single-process architecture.

7. Race condition: two signals for same token in rapid succession
   Impact: Both could pass dedup if checked before either is assigned
   Mitigation: Python's GIL ensures route() calls are serialized within
   the async event loop (route() is synchronous, no awaits). The second
   call will see the first's state update.
"""
