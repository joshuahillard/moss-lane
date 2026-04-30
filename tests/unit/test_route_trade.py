"""
Test Suite for src/dispatcher/route_trade.py

Covers:
- Topology validation (ADR-005, ADR-006 invariants)
- Zero-key environment guard (ADR-007)
- Routing decision happy path (homogeneous burner load-balance)
- Forbidden-edge defenses (vault target, main target, out-of-pool target)
- Gate precondition (refuses signals where 12-point gate did not pass)
- Quarantine semantics
- Coordinator failure modes (None return, raised exception)

All tests use unittest. The downstream coordinator is faked so tests run
without the real ScannerCoordinator (and without solders / network).
"""

from __future__ import annotations

import logging
import unittest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    from route_trade import (
        RouteDecision,
        RouteRejection,
        RouteRejectionReason,
        TopologyError,
        TradeRouter,
        validate_no_keys_in_env,
        validate_topology,
    )
except ImportError:
    from src.dispatcher.route_trade import (
        RouteDecision,
        RouteRejection,
        RouteRejectionReason,
        TopologyError,
        TradeRouter,
        validate_no_keys_in_env,
        validate_topology,
    )


logging.getLogger("dispatcher.route_trade").setLevel(logging.WARNING)


# ════════════════════════════════════════════════════════════════════════════
# Test fixtures
# ════════════════════════════════════════════════════════════════════════════

@dataclass
class FakeSignal:
    """Mimics src/engine/lazarus.py::Signal shape."""
    symbol: str
    address: str
    score: float = 1.0
    source: str = "test"


@dataclass
class FakeRoutedSignal:
    """Mimics src/scanner/scanner_coordinator.py::RoutedSignal shape."""
    executor_address: str
    token_address: str = ""
    symbol: str = ""
    score: float = 0.0
    source: str = ""


class FakeCoordinator:
    """
    Minimal coordinator fake. Callers configure a script of return values;
    each .route() call pops the next entry. Use .raise_on_route to trigger
    an exception path.
    """

    def __init__(
        self,
        idle_count: int = 5,
        responses: Optional[List[Optional[FakeRoutedSignal]]] = None,
        raise_on_route: bool = False,
    ):
        self._idle = idle_count
        self._responses: List[Optional[FakeRoutedSignal]] = list(responses or [])
        self._raise = raise_on_route
        self.routed_called_with: List[Any] = []

    def get_idle_count(self) -> int:
        return self._idle

    def route(self, signal: Any) -> Optional[FakeRoutedSignal]:
        self.routed_called_with.append(signal)
        if self._raise:
            raise RuntimeError("simulated coordinator fault")
        if not self._responses:
            return None
        return self._responses.pop(0)


# Standard topology fixture — five homogeneous burners, distinct vault + main
BURNERS = [f"burner_{i}_pubkey" for i in range(1, 6)]
VAULT = "vault_pubkey_xyz"
MAIN = "main_pubkey_abc"


# ════════════════════════════════════════════════════════════════════════════
# validate_topology
# ════════════════════════════════════════════════════════════════════════════

class TestValidateTopology(unittest.TestCase):

    def test_valid_topology_does_not_raise(self):
        validate_topology(BURNERS, VAULT, MAIN)

    def test_valid_topology_without_main_or_vault(self):
        # vault_address and main_address are optional
        validate_topology(BURNERS, None, None)

    def test_empty_executor_pool_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_topology([], VAULT, MAIN)
        self.assertIn("empty", str(ctx.exception))

    def test_empty_string_address_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_topology(["burner_1", ""], VAULT, MAIN)
        self.assertIn("empty address", str(ctx.exception))

    def test_duplicate_executor_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_topology(["burner_1", "burner_1", "burner_2"], VAULT, MAIN)
        self.assertIn("duplicate", str(ctx.exception))

    def test_vault_in_executor_pool_raises(self):
        bad = list(BURNERS) + [VAULT]
        with self.assertRaises(TopologyError) as ctx:
            validate_topology(bad, VAULT, MAIN)
        self.assertIn("vault", str(ctx.exception).lower())

    def test_main_in_executor_pool_raises(self):
        bad = list(BURNERS) + [MAIN]
        with self.assertRaises(TopologyError) as ctx:
            validate_topology(bad, VAULT, MAIN)
        self.assertIn("main", str(ctx.exception).lower())

    def test_vault_equals_main_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_topology(BURNERS, "shared_addr", "shared_addr")
        self.assertIn("identical", str(ctx.exception).lower())


# ════════════════════════════════════════════════════════════════════════════
# validate_no_keys_in_env
# ════════════════════════════════════════════════════════════════════════════

class TestValidateNoKeysInEnv(unittest.TestCase):

    def test_empty_env_passes(self):
        validate_no_keys_in_env({})

    def test_clean_env_passes(self):
        validate_no_keys_in_env({
            "PATH": "/usr/bin",
            "HOME": "/home/solbot",
            "TAX_VAULT_ADDRESS": "vault_pubkey",
            "RPC_URL": "https://api.mainnet.solana.com",
        })

    def test_exec_wallet_key_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_no_keys_in_env({"EXEC_WALLET_1_KEY": "abc123"})
        self.assertIn("EXEC_WALLET_1_KEY", str(ctx.exception))

    def test_tax_vault_key_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_no_keys_in_env({"TAX_VAULT_KEY": "abc123"})
        self.assertIn("TAX_VAULT_KEY", str(ctx.exception))

    def test_main_wallet_key_raises(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_no_keys_in_env({"MAIN_WALLET_KEY": "abc123"})
        self.assertIn("MAIN_WALLET_KEY", str(ctx.exception))

    def test_empty_value_does_not_raise(self):
        # Setting EXEC_WALLET_1_KEY="" is a no-op (variable present but empty).
        # We treat that as "not loaded" — fail-closed only when the key
        # actually has a value.
        validate_no_keys_in_env({"EXEC_WALLET_1_KEY": ""})

    def test_public_key_substring_allowed(self):
        # Vars with "PUBLIC" in the name are not signing material.
        validate_no_keys_in_env({"OPERATOR_PUBLIC_KEY": "vault_pubkey"})

    def test_address_suffix_allowed(self):
        validate_no_keys_in_env({"TAX_VAULT_ADDRESS": "abc"})

    def test_api_key_substring_allowed(self):
        # API keys are forbidden too in principle, but "API" in the name
        # marks it as a non-signing credential. The whitelist documents this.
        validate_no_keys_in_env({"BIRDEYE_API_KEY": "xyz"})

    def test_secret_suffix_raises(self):
        with self.assertRaises(TopologyError):
            validate_no_keys_in_env({"SOMETHING_SECRET": "abc"})

    def test_lowercase_var_name_still_caught(self):
        with self.assertRaises(TopologyError):
            validate_no_keys_in_env({"exec_wallet_1_key": "abc"})

    def test_collects_all_offenders(self):
        with self.assertRaises(TopologyError) as ctx:
            validate_no_keys_in_env({
                "EXEC_WALLET_1_KEY": "a",
                "EXEC_WALLET_2_KEY": "b",
                "TAX_VAULT_KEY": "c",
            })
        msg = str(ctx.exception)
        self.assertIn("EXEC_WALLET_1_KEY", msg)
        self.assertIn("EXEC_WALLET_2_KEY", msg)
        self.assertIn("TAX_VAULT_KEY", msg)

    def test_custom_forbidden_suffixes(self):
        with self.assertRaises(TopologyError):
            validate_no_keys_in_env(
                {"FOO_TOKEN": "abc"}, forbidden_suffixes=["_TOKEN"]
            )


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — construction
# ════════════════════════════════════════════════════════════════════════════

class TestTradeRouterConstruction(unittest.TestCase):

    def test_construction_with_valid_topology(self):
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=FakeCoordinator(),
        )
        self.assertEqual(router.get_status()["burner_count"], 5)

    def test_construction_with_vault_in_pool_raises(self):
        bad_pool = list(BURNERS) + [VAULT]
        with self.assertRaises(TopologyError):
            TradeRouter(
                executor_addresses=bad_pool,
                vault_address=VAULT,
                main_address=MAIN,
                coordinator=FakeCoordinator(),
            )

    def test_construction_with_empty_pool_raises(self):
        with self.assertRaises(TopologyError):
            TradeRouter(
                executor_addresses=[],
                vault_address=VAULT,
                main_address=MAIN,
                coordinator=FakeCoordinator(),
            )

    def test_construction_with_initial_quarantine(self):
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=FakeCoordinator(),
            quarantined=[BURNERS[0]],
        )
        self.assertTrue(router.is_quarantined(BURNERS[0]))
        self.assertFalse(router.is_quarantined(BURNERS[1]))


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — routing happy path
# ════════════════════════════════════════════════════════════════════════════

class TestTradeRouterHappyPath(unittest.TestCase):

    def setUp(self):
        # Coordinator will return burner_3 for any signal it receives
        self.coord = FakeCoordinator(
            responses=[FakeRoutedSignal(executor_address=BURNERS[2])]
        )
        self.router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=self.coord,
        )

    def test_route_returns_decision_when_gate_passed(self):
        sig = FakeSignal(symbol="DOGE", address="token_a", score=42.0, source="birdeye")
        result = self.router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteDecision)
        self.assertEqual(result.executor_address, BURNERS[2])
        self.assertEqual(result.signal_address, "token_a")
        self.assertEqual(result.signal_symbol, "DOGE")
        self.assertEqual(result.signal_score, 42.0)
        self.assertEqual(result.signal_source, "birdeye")
        self.assertGreater(result.routed_at, 0)

    def test_route_increments_routed_counter(self):
        sig = FakeSignal(symbol="DOGE", address="token_a")
        self.router.route(sig, gate_passed=True)
        self.assertEqual(self.router.get_status()["routed_total"], 1)

    def test_coordinator_receives_the_signal(self):
        sig = FakeSignal(symbol="DOGE", address="token_a")
        self.router.route(sig, gate_passed=True)
        self.assertEqual(len(self.coord.routed_called_with), 1)
        self.assertIs(self.coord.routed_called_with[0], sig)


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — gate precondition
# ════════════════════════════════════════════════════════════════════════════

class TestGatePrecondition(unittest.TestCase):

    def setUp(self):
        self.coord = FakeCoordinator(
            responses=[FakeRoutedSignal(executor_address=BURNERS[0])]
        )
        self.router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=self.coord,
        )

    def test_gate_not_passed_rejects(self):
        sig = FakeSignal(symbol="X", address="token_x")
        result = self.router.route(sig, gate_passed=False)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.GATE_NOT_PASSED)

    def test_gate_not_passed_does_not_call_coordinator(self):
        sig = FakeSignal(symbol="X", address="token_x")
        self.router.route(sig, gate_passed=False)
        # Coordinator must not be invoked when the gate did not pass —
        # this is what guarantees the dispatcher cannot bypass the gate.
        self.assertEqual(len(self.coord.routed_called_with), 0)

    def test_gate_rejection_does_not_consume_coordinator_response(self):
        # A GATE_NOT_PASSED signal followed by a gate_passed=True signal
        # should see the coordinator's first scripted response on the SECOND
        # call, proving the first never reached the coordinator.
        sig_bad = FakeSignal(symbol="X", address="token_x")
        sig_ok = FakeSignal(symbol="Y", address="token_y")

        self.router.route(sig_bad, gate_passed=False)
        result = self.router.route(sig_ok, gate_passed=True)
        self.assertIsInstance(result, RouteDecision)
        self.assertEqual(result.executor_address, BURNERS[0])


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — forbidden-target defenses
# ════════════════════════════════════════════════════════════════════════════

class TestForbiddenTargets(unittest.TestCase):

    def _build(self, response: Optional[FakeRoutedSignal]) -> TradeRouter:
        return TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=FakeCoordinator(responses=[response] if response else []),
        )

    def test_target_not_in_pool_rejects(self):
        # Coordinator hands back an unknown address. Defense in depth catches it.
        router = self._build(FakeRoutedSignal(executor_address="unknown_addr"))
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.FORBIDDEN_TARGET)

    def test_vault_target_rejects(self):
        # Construct a router with vault NOT in the pool (so construction passes),
        # then have the coordinator improperly return the vault address.
        # Topology check at construction prevented vault from being in the pool,
        # but this exercises the runtime defense.
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=FakeCoordinator(
                responses=[FakeRoutedSignal(executor_address=VAULT)]
            ),
        )
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        # FORBIDDEN_TARGET — could be "vault" or "not in pool" depending on which
        # check fires first; both are valid forbidden-edge rejections.
        self.assertEqual(result.reason, RouteRejectionReason.FORBIDDEN_TARGET)

    def test_main_target_rejects(self):
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=FakeCoordinator(
                responses=[FakeRoutedSignal(executor_address=MAIN)]
            ),
        )
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.FORBIDDEN_TARGET)

    def test_missing_executor_address_field_rejects(self):
        router = self._build(FakeRoutedSignal(executor_address=""))
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.COORDINATOR_DROPPED)


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — coordinator failure modes
# ════════════════════════════════════════════════════════════════════════════

class TestCoordinatorFailureModes(unittest.TestCase):

    def test_coordinator_returns_none_rejects(self):
        coord = FakeCoordinator(responses=[None])
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=coord,
        )
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.COORDINATOR_DROPPED)

    def test_coordinator_raises_rejects_fail_closed(self):
        coord = FakeCoordinator(raise_on_route=True)
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=coord,
        )
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.COORDINATOR_DROPPED)


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — quarantine semantics
# ════════════════════════════════════════════════════════════════════════════

class TestQuarantine(unittest.TestCase):

    def test_all_burners_quarantined_short_circuits(self):
        coord = FakeCoordinator()  # no scripted responses needed
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=coord,
            quarantined=list(BURNERS),
        )
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.EXECUTOR_QUARANTINED)
        # Coordinator must not be called when all burners are quarantined.
        self.assertEqual(len(coord.routed_called_with), 0)

    def test_coordinator_picks_quarantined_target_rejects(self):
        # Race condition: coordinator's IDLE check ran before quarantine
        # was applied at the dispatcher level. Defense in depth catches it.
        coord = FakeCoordinator(
            responses=[FakeRoutedSignal(executor_address=BURNERS[0])]
        )
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=coord,
        )
        router.quarantine(BURNERS[0], reason="test")
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteRejection)
        self.assertEqual(result.reason, RouteRejectionReason.EXECUTOR_QUARANTINED)

    def test_clear_quarantine_restores(self):
        coord = FakeCoordinator(
            responses=[FakeRoutedSignal(executor_address=BURNERS[0])]
        )
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=coord,
        )
        router.quarantine(BURNERS[0], reason="test")
        router.clear_quarantine(BURNERS[0])
        self.assertFalse(router.is_quarantined(BURNERS[0]))
        sig = FakeSignal(symbol="X", address="token_x")
        result = router.route(sig, gate_passed=True)
        self.assertIsInstance(result, RouteDecision)

    def test_quarantine_unknown_address_is_noop(self):
        # Quarantining something not in the pool should not corrupt state.
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=FakeCoordinator(),
        )
        router.quarantine("not_in_pool", reason="test")
        self.assertFalse(router.is_quarantined("not_in_pool"))


# ════════════════════════════════════════════════════════════════════════════
# TradeRouter — observability counters
# ════════════════════════════════════════════════════════════════════════════

class TestObservability(unittest.TestCase):

    def test_status_tracks_rejections_by_reason(self):
        coord = FakeCoordinator(
            responses=[
                None,  # first call drops
                FakeRoutedSignal(executor_address=BURNERS[0]),  # second routes
            ]
        )
        router = TradeRouter(
            executor_addresses=BURNERS,
            vault_address=VAULT,
            main_address=MAIN,
            coordinator=coord,
        )

        # 1 gate-not-passed
        router.route(FakeSignal(symbol="A", address="a"), gate_passed=False)
        # 1 coordinator-dropped (None)
        router.route(FakeSignal(symbol="B", address="b"), gate_passed=True)
        # 1 routed
        router.route(FakeSignal(symbol="C", address="c"), gate_passed=True)

        status = router.get_status()
        self.assertEqual(status["routed_total"], 1)
        rej = status["rejections_by_reason"]
        self.assertEqual(rej["gate_not_passed"], 1)
        self.assertEqual(rej["coordinator_dropped"], 1)
        # Remaining buckets stay zero
        self.assertEqual(rej["forbidden_target"], 0)
        self.assertEqual(rej["executor_quarantined"], 0)


if __name__ == "__main__":
    unittest.main()
