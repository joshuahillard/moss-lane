"""
Trade Routing Decision Layer — Phase 3 Slice 2 Build

Implements the dispatcher's routing-decision contract per the
2026-04-29 multi-wallet topology ADR (deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md):

  ADR-004 — Homogeneous burners (no per-wallet filter or sizing divergence)
  ADR-005 — Allowed-edge enforcement (only route to burner pool)
  ADR-006 — Vault is receive-only (vault address forbidden as routing target)
  ADR-007 — Coordinator holds zero keys, signs zero transactions

This module sits ABOVE src/scanner/scanner_coordinator.py::ScannerCoordinator.
It does not replace round-robin routing or state-machine bookkeeping —
those remain in ScannerCoordinator. This module adds the topology
invariants that ADR-005..007 introduced and that did not exist anywhere
in code yet.

Critical preservation rules from CLAUDE.md and the predecessor ADRs:

  1. The 12-point fail-closed gate at github-repo/src/engine/lazarus.py:677-734
     MUST run upstream of this router. Callers pass `gate_passed=True` only
     after the gate has accepted the signal. This module refuses to route
     `gate_passed=False` signals.

  2. The 7-tier exit priority chain at github-repo/src/engine/lazarus.py:1008-1044
     is REUSED by each burner process — it is not re-implemented here.
     The dispatcher hands off the routing decision; the burner runs exits.

  3. The dispatcher signs nothing. RouteDecision is a data record. Signing
     is the burner-process's responsibility (ADR-007).

The topology validator and zero-key validator at module scope are intended
to be invoked from process startup (e.g., scanner-side coordinator service
init). Both fail-closed: any ambiguity raises rather than degrades.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol, Set

log = logging.getLogger("dispatcher.route_trade")


# ════════════════════════════════════════════════════════════════════════════
# Public errors
# ════════════════════════════════════════════════════════════════════════════

class TopologyError(Exception):
    """
    Raised when capital-flow topology invariants would be violated.

    Examples:
      - executor address overlaps the vault address (ADR-006)
      - executor address overlaps the main wallet address (ADR-005)
      - executor pool is empty (no homogeneous burner fleet to route into)
      - duplicate executor address (ambiguous routing target)
    """


# ════════════════════════════════════════════════════════════════════════════
# Signal protocol — duck-typed so we don't import lazarus.py
# ════════════════════════════════════════════════════════════════════════════

class _SignalLike(Protocol):
    """
    Duck-typed signal. Matches the shape of
    github-repo/src/engine/lazarus.py::Signal (line 274) and the
    output of github-repo/src/engine/lazarus.py::SignalAggregator.get_signals.
    """
    symbol: str
    address: str
    score: float
    source: str


# ════════════════════════════════════════════════════════════════════════════
# Routing decision data records
# ════════════════════════════════════════════════════════════════════════════

class RouteRejectionReason(Enum):
    """
    Enumerated reasons the router declined to issue a RouteDecision.
    Used for monitoring and FMEA traceability — every drop has a labelled cause.
    """
    GATE_NOT_PASSED = "gate_not_passed"           # 12-point gate did not accept upstream
    NO_AVAILABLE_EXECUTORS = "no_available_executors"
    EXECUTOR_QUARANTINED = "executor_quarantined"
    DUPLICATE_TOKEN = "duplicate_token"           # signal already active on another burner
    COORDINATOR_DROPPED = "coordinator_dropped"   # downstream coordinator returned None
    FORBIDDEN_TARGET = "forbidden_target"         # downstream returned vault/main — should never happen


@dataclass(frozen=True)
class RouteDecision:
    """
    A routing decision produced by TradeRouter.route().

    A RouteDecision is a *data record*, not a transaction. It tells the
    caller which burner address should execute the given signal. The caller
    is responsible for invoking the burner-process executor with this
    decision and for the burner's keypair-side signing (ADR-007).
    """
    executor_address: str
    signal_address: str
    signal_symbol: str
    signal_score: float
    signal_source: str
    routed_at: float


@dataclass(frozen=True)
class RouteRejection:
    """A negative routing outcome — why the router declined to route."""
    reason: RouteRejectionReason
    signal_address: str
    signal_symbol: str
    detail: str = ""


# ════════════════════════════════════════════════════════════════════════════
# Module-level validators — called at startup, fail-closed
# ════════════════════════════════════════════════════════════════════════════

def validate_topology(
    executor_addresses: List[str],
    vault_address: Optional[str],
    main_address: Optional[str],
) -> None:
    """
    Enforce the ADR-005 / ADR-006 capital-flow topology invariants on a
    proposed executor address set.

    Raises TopologyError if any invariant fails. Returns None on success.

    Invariants:
      1. Executor pool is non-empty.
      2. No duplicate executor addresses.
      3. Vault address (if provided) is NOT in the executor pool.
         The vault is a receive-only ratchet. Routing trades to it would
         violate ADR-006.
      4. Main address (if provided) is NOT in the executor pool.
         Main is the funding wallet, not a trading wallet. Routing trades
         to it would violate ADR-005's allowed-edge list.
      5. Vault and main are distinct addresses (defensive).
    """
    if not executor_addresses:
        raise TopologyError(
            "executor pool is empty — homogeneous burner fleet (ADR-004) "
            "requires at least one executor"
        )

    seen: Set[str] = set()
    for addr in executor_addresses:
        if not addr:
            raise TopologyError("executor pool contains an empty address")
        if addr in seen:
            raise TopologyError(
                f"duplicate executor address in pool: {addr[:12]}..."
            )
        seen.add(addr)

    if vault_address and vault_address in seen:
        raise TopologyError(
            f"vault address {vault_address[:12]}... appears in executor "
            "pool — violates ADR-006 (vault is receive-only)"
        )

    if main_address and main_address in seen:
        raise TopologyError(
            f"main wallet address {main_address[:12]}... appears in "
            "executor pool — violates ADR-005 (main funds, never trades)"
        )

    if vault_address and main_address and vault_address == main_address:
        raise TopologyError(
            "vault address and main address are identical — capital "
            "flow topology requires distinct roles"
        )


def validate_no_keys_in_env(
    env: Optional[Dict[str, str]] = None,
    *,
    forbidden_suffixes: Optional[List[str]] = None,
) -> None:
    """
    Enforce ADR-007: the dispatcher process must not have any signing
    keypair loadable from its environment.

    This is a structural check, not a heuristic. Callers should invoke
    this at process startup; it raises TopologyError if any forbidden
    key is present so the process refuses to start.

    Args:
        env: Mapping to check. Defaults to os.environ.
        forbidden_suffixes: Substring patterns that mark a value as a
            signing key. Defaults to a Moss-Lane-specific list:
            ("_KEY", "_PRIVATE_KEY", "_SECRET").

    Raises:
        TopologyError: if any matching env var is present and non-empty.

    Notes:
        - We deliberately match by *variable name suffix*, not by attempting
          to parse the value with solders.Keypair.from_bytes. The dispatcher
          should not import solders at all (defense in depth — no signing
          library means no signing path).
        - TAX_VAULT_KEY is the canonical forbidden var. EXEC_WALLET_N_KEY
          and MAIN_WALLET_KEY are also forbidden in the dispatcher env.
        - PUBLIC_KEY-suffixed vars are explicitly allowed; we check for
          private-key markers only.
    """
    if env is None:
        env = dict(os.environ)

    if forbidden_suffixes is None:
        forbidden_suffixes = ["_KEY", "_PRIVATE_KEY", "_SECRET"]

    # Whitelist substrings that should NOT be flagged even if they end in _KEY
    # (e.g., API endpoint names). Conservative: anything with PUBLIC, ADDRESS,
    # API, or URL in the name is treated as non-signing.
    allowed_substrings = {"PUBLIC", "ADDRESS", "API", "URL", "ENDPOINT", "PATH"}

    offenders: List[str] = []
    for var_name, value in env.items():
        if not value:
            continue
        upper_name = var_name.upper()
        if any(allowed in upper_name for allowed in allowed_substrings):
            continue
        for suffix in forbidden_suffixes:
            if upper_name.endswith(suffix.upper()):
                offenders.append(var_name)
                break

    if offenders:
        raise TopologyError(
            "dispatcher process has forbidden signing-key env vars: "
            f"{sorted(offenders)} — ADR-007 requires zero keys. Move "
            "signing material to the burner-process env (and TAX_VAULT_KEY "
            "off-server entirely per ADR-006)."
        )


# ════════════════════════════════════════════════════════════════════════════
# Coordinator interface — duck-typed wrapper around ScannerCoordinator
# ════════════════════════════════════════════════════════════════════════════

class _CoordinatorLike(Protocol):
    """
    Minimum surface the TradeRouter needs from a downstream coordinator.

    The default implementation in this codebase is
    src/scanner/scanner_coordinator.py::ScannerCoordinator. The duck-type
    here keeps the dispatcher decoupled (and lets tests inject a fake).
    """

    def route(self, signal: Any) -> Optional[Any]:
        """Return a coordinator-specific routed-signal object or None on drop."""

    def get_idle_count(self) -> int:
        """Return the number of executors currently in IDLE state."""


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter
# ════════════════════════════════════════════════════════════════════════════

class TradeRouter:
    """
    The routing-decision producer for the multi-wallet topology.

    Responsibilities:
      1. Validate topology at construction (allowed-edge invariants).
      2. Refuse signals that have not passed the upstream 12-point gate.
      3. Delegate available-executor selection + per-token dedup to the
         downstream coordinator (ScannerCoordinator).
      4. Validate that the coordinator's chosen target is in the burner pool
         (defense in depth — re-checks ADR-005 on every output).
      5. Emit RouteDecision records. Sign nothing, hold no keys.

    Construction:
        router = TradeRouter(
            executor_addresses=["burner1", ..., "burner5"],
            vault_address="vault_pubkey",
            main_address="main_pubkey",
            coordinator=ScannerCoordinator(...),
        )

    Hot path:
        decision = router.route(signal, gate_passed=True)
        if isinstance(decision, RouteDecision):
            # Hand decision to burner-process executor (which signs).
        elif isinstance(decision, RouteRejection):
            # Log decision.reason for monitoring; drop signal.
    """

    def __init__(
        self,
        executor_addresses: List[str],
        vault_address: Optional[str],
        main_address: Optional[str],
        coordinator: _CoordinatorLike,
        *,
        quarantined: Optional[List[str]] = None,
    ):
        # Topology check fails closed.
        validate_topology(executor_addresses, vault_address, main_address)

        self._executor_pool: Set[str] = set(executor_addresses)
        self._vault_address = vault_address
        self._main_address = main_address
        self._coordinator = coordinator
        self._quarantined: Set[str] = set(quarantined or [])

        # Observability counters (rejection-cause buckets)
        self._rejection_counts: Dict[RouteRejectionReason, int] = {
            r: 0 for r in RouteRejectionReason
        }
        self._routed_count = 0

        log.info(
            "TradeRouter ready: %d burners, vault=%s, main=%s, quarantined=%d",
            len(self._executor_pool),
            (vault_address[:12] + "...") if vault_address else "<unset>",
            (main_address[:12] + "...") if main_address else "<unset>",
            len(self._quarantined),
        )

    # ────────────────────────────────────────────────────────────────────
    # Quarantine management (companion to ADR-005 quarantine-sweep concept)
    # ────────────────────────────────────────────────────────────────────

    def quarantine(self, executor_address: str, reason: str = "") -> None:
        """
        Temporarily exclude an executor from routing decisions.

        This does NOT sweep capital — that is a separate operator action
        (ADR-005's Burner→Main edge). Quarantine here only blocks new
        routes; in-flight trades continue under the burner's own control.
        """
        if executor_address not in self._executor_pool:
            log.warning(
                "quarantine: %s not in executor pool — ignored", executor_address
            )
            return
        self._quarantined.add(executor_address)
        log.warning(
            "QUARANTINE %s%s",
            executor_address[:12] + "...",
            f" ({reason})" if reason else "",
        )

    def clear_quarantine(self, executor_address: str) -> None:
        """Restore a quarantined executor to the active pool (operator action)."""
        if executor_address in self._quarantined:
            self._quarantined.discard(executor_address)
            log.info("QUARANTINE CLEARED %s", executor_address[:12] + "...")

    def is_quarantined(self, executor_address: str) -> bool:
        return executor_address in self._quarantined

    # ────────────────────────────────────────────────────────────────────
    # Hot path
    # ────────────────────────────────────────────────────────────────────

    def route(self, signal: _SignalLike, *, gate_passed: bool):
        """
        Produce a routing decision for a signal.

        Args:
            signal: A signal-like object with .address, .symbol, .score, .source.
            gate_passed: True iff the upstream 12-point fail-closed gate
                accepted this signal. False signals are rejected — the
                dispatcher will never re-evaluate or bypass the gate.

        Returns:
            RouteDecision when a burner is selected and topology is satisfied.
            RouteRejection (with a labelled reason) otherwise.
        """
        # ── Precondition: gate must have passed upstream ──
        if not gate_passed:
            return self._reject(
                RouteRejectionReason.GATE_NOT_PASSED,
                signal,
                detail="caller passed gate_passed=False",
            )

        # ── Quick check: do we have anyone idle at all? ──
        # The coordinator does its own IDLE check, but this lets us short-
        # circuit and label the rejection cleanly when EVERY burner is
        # quarantined or busy.
        idle_pool = [
            a for a in self._executor_pool if a not in self._quarantined
        ]
        if not idle_pool:
            return self._reject(
                RouteRejectionReason.EXECUTOR_QUARANTINED,
                signal,
                detail="all burners quarantined",
            )

        # ── Delegate selection to the downstream coordinator ──
        try:
            routed = self._coordinator.route(signal)
        except Exception as e:  # noqa: BLE001 — fail-closed on coordinator faults
            log.error("coordinator.route raised: %s — dropping signal", e)
            return self._reject(
                RouteRejectionReason.COORDINATOR_DROPPED,
                signal,
                detail=f"coordinator exception: {type(e).__name__}",
            )

        if routed is None:
            return self._reject(
                RouteRejectionReason.COORDINATOR_DROPPED,
                signal,
                detail="coordinator returned None (likely dedup or all-busy)",
            )

        target_addr = getattr(routed, "executor_address", None)
        if not target_addr:
            return self._reject(
                RouteRejectionReason.COORDINATOR_DROPPED,
                signal,
                detail="coordinator returned routed signal with no executor_address",
            )

        # ── Defense in depth: re-validate the chosen target ──
        if target_addr not in self._executor_pool:
            log.error(
                "FORBIDDEN_TARGET: coordinator picked %s, not in burner pool — "
                "this should be impossible. Investigate coordinator state.",
                target_addr,
            )
            return self._reject(
                RouteRejectionReason.FORBIDDEN_TARGET,
                signal,
                detail=f"target {target_addr[:12]}... not in burner pool",
            )

        if target_addr in self._quarantined:
            # Coordinator chose a quarantined wallet — race condition where
            # quarantine arrived after the coordinator's IDLE check. Reject
            # rather than route.
            return self._reject(
                RouteRejectionReason.EXECUTOR_QUARANTINED,
                signal,
                detail=f"target {target_addr[:12]}... is quarantined",
            )

        if self._vault_address and target_addr == self._vault_address:
            # Should be unreachable given topology validation at construction,
            # but check anyway. ADR-006 forbids routing trades to the vault.
            log.error(
                "FORBIDDEN_TARGET: vault address selected — ADR-006 violation"
            )
            return self._reject(
                RouteRejectionReason.FORBIDDEN_TARGET,
                signal,
                detail="vault address selected",
            )

        if self._main_address and target_addr == self._main_address:
            log.error(
                "FORBIDDEN_TARGET: main address selected — ADR-005 violation"
            )
            return self._reject(
                RouteRejectionReason.FORBIDDEN_TARGET,
                signal,
                detail="main address selected",
            )

        # ── Emit decision ──
        decision = RouteDecision(
            executor_address=target_addr,
            signal_address=signal.address,
            signal_symbol=signal.symbol,
            signal_score=getattr(signal, "score", 0.0),
            signal_source=getattr(signal, "source", "unknown"),
            routed_at=time.time(),
        )
        self._routed_count += 1
        log.info(
            "ROUTE OK %s → %s... (score=%.1f, source=%s)",
            decision.signal_symbol,
            decision.executor_address[:12],
            decision.signal_score,
            decision.signal_source,
        )
        return decision

    # ────────────────────────────────────────────────────────────────────
    # Observability
    # ────────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict[str, Any]:
        """Return a snapshot of routing-decision counters for monitoring."""
        return {
            "burner_count": len(self._executor_pool),
            "quarantined_count": len(self._quarantined),
            "quarantined": sorted(self._quarantined),
            "routed_total": self._routed_count,
            "rejections_by_reason": {
                r.value: c for r, c in self._rejection_counts.items()
            },
        }

    # ────────────────────────────────────────────────────────────────────
    # Internal
    # ────────────────────────────────────────────────────────────────────

    def _reject(
        self,
        reason: RouteRejectionReason,
        signal: _SignalLike,
        *,
        detail: str = "",
    ) -> RouteRejection:
        self._rejection_counts[reason] += 1
        log.info(
            "ROUTE DROP %s reason=%s%s",
            getattr(signal, "symbol", "?"),
            reason.value,
            f" detail={detail}" if detail else "",
        )
        return RouteRejection(
            reason=reason,
            signal_address=getattr(signal, "address", ""),
            signal_symbol=getattr(signal, "symbol", ""),
            detail=detail,
        )
