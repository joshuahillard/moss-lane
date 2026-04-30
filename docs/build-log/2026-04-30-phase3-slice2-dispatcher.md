# Build Log: Phase 3 Slice 2 — Trade Routing Dispatcher

**Date:** 2026-04-30
**Author:** Josh Hillard (TPM #4), DevOps #6 lead, with SecOps #2 / SRE #1 review
**Sprint:** Phase 3 (Apr 25–May 7), slice 2 of 3
**Predecessor:** [deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md](../../deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md) (slice 1)
**Status:** Repo-built (not yet deployed; integration with `lazarus.py` main loop is slice 3)

---

## What Was Built

A new `dispatcher` package implementing the routing-decision layer that yesterday's ADR called for. The module sits *above* the existing `src/scanner/scanner_coordinator.py::ScannerCoordinator` and adds the topology invariants that ADR-005, ADR-006, and ADR-007 introduced.

### New files

- [src/dispatcher/__init__.py](../../src/dispatcher/__init__.py) — package init, public surface
- [src/dispatcher/route_trade.py](../../src/dispatcher/route_trade.py) — `TradeRouter`, `RouteDecision`, `RouteRejection`, `validate_topology`, `validate_no_keys_in_env`
- [tests/unit/test_route_trade.py](../../tests/unit/test_route_trade.py) — 42 unit tests, no network/solders/disk dependencies

### What it does

`TradeRouter.route(signal, gate_passed=...)` produces a routing decision. It does not sign. It does not hold keys. It hands a `RouteDecision` back to the caller, who is responsible for invoking the burner-process executor.

The router enforces the four ADR invariants from slice 1:

1. **ADR-004 (homogeneous burners):** the router treats the burner pool as fungible. It does not reason about per-wallet filter regimes or position sizes.
2. **ADR-005 (allowed/forbidden edges):** topology validation refuses construction with vault or main address inside the burner pool. Runtime defense in depth re-checks every coordinator output against the burner pool.
3. **ADR-006 (vault is receive-only):** routing to the vault address is structurally impossible — the validator at construction prevents it, and a runtime check catches any coordinator regression.
4. **ADR-007 (coordinator zero-key invariant):** `validate_no_keys_in_env` raises `TopologyError` if the dispatcher process environment contains any `*_KEY` / `*_SECRET` / `*_PRIVATE_KEY` variable. Designed to be called at process startup so the process refuses to start when the invariant is violated.

### What it does NOT do

- Does not call `solders` or any signing library. By design — defense in depth means the dispatcher process should not even have the *ability* to sign.
- Does not re-implement the 12-point fail-closed gate at [src/engine/lazarus.py:677-734](../../src/engine/lazarus.py). The gate runs upstream in the scanner. The router takes a `gate_passed: bool` precondition; `gate_passed=False` is rejected without calling the coordinator. This is what guarantees no bypass path exists.
- Does not re-implement the 7-tier exit priority chain at [src/engine/lazarus.py:1008-1044](../../src/engine/lazarus.py). Exits remain in the burner-process executor. Each homogeneous burner reuses the existing chain.
- Does not modify `lazarus.py`. The integration point will be added in slice 3 once the burner-process executor scaffolding is in place.

---

## FMEA Delta

Yesterday's ADR (slice 1) listed five new failure modes from the topology design. Today's build closes three of them via structural enforcement and validates the controls with tests:

| Failure Mode (from slice 1) | Slice 1 Status | Slice 2 Status |
|------------------------------|----------------|------------------|
| Vault private key leaked to trading server | Planned: startup assertion | ✅ Implemented in `validate_no_keys_in_env`; covered by `test_tax_vault_key_raises` |
| Coordinator gains a wallet key in a future PR | Planned: startup assertion | ✅ Implemented in `validate_no_keys_in_env`; covered by `test_exec_wallet_key_raises`, `test_main_wallet_key_raises` |
| Forbidden edge (Burner→Burner direct) added | Planned: topology validator | ✅ Implemented in `validate_topology`; covered by `test_vault_in_executor_pool_raises`, `test_main_in_executor_pool_raises`, `test_target_not_in_pool_rejects` |
| Quarantine sweep races with in-flight trade | Pending slice 3 — sweep not yet implemented | Unchanged |
| Vault drain cadence forgotten | Operator process discipline; no code | Unchanged |

### One new failure mode surfaced during the build

**Coordinator raises an exception mid-route.** The existing `scanner_coordinator.py` docstring describes graceful drop on cooldown / dedup / all-busy paths, but does not specify behavior if the coordinator itself raises (e.g., dictionary corruption, unexpected exception in `_transition`). This was not in the slice 1 FMEA.

- **Effect:** signal could leak through unhandled if the dispatcher does not catch it.
- **Control:** `TradeRouter.route` wraps the coordinator call in a try/except and labels the rejection as `COORDINATOR_DROPPED`. Counters increment for monitoring.
- **Test:** `test_coordinator_raises_rejects_fail_closed` validates the path.
- **Residual gap:** if the coordinator's internal state is corrupted (not just raising — silently returning wrong addresses), the FORBIDDEN_TARGET defense-in-depth check catches it. Validated by `test_target_not_in_pool_rejects` and `test_vault_target_rejects`.

---

## Test Results

```
$ python -m pytest tests/unit/test_route_trade.py -v
============================= 42 passed in 0.09s ==============================

$ python -m pytest tests/unit/ -q
============================= 100 passed in 0.63s =============================
```

All 42 new tests pass. The pre-existing 58-test suite still passes — no regressions in `test_fund_splitter.py`, `test_filter_regime_write.py`, `test_health.py`, or `test_startup_overrides.py`.

### Test coverage breakdown

- **Topology validation (8 tests):** valid topology accepted; empty pool, duplicate, vault-in-pool, main-in-pool, vault==main, empty-string address all rejected.
- **Zero-key env guard (13 tests):** clean envs accepted; `EXEC_WALLET_*_KEY`, `TAX_VAULT_KEY`, `MAIN_WALLET_KEY`, `_SECRET` all caught; `_ADDRESS`, `PUBLIC`, `API`, `URL` whitelisted; lowercase variants caught; multiple offenders all reported.
- **Construction (4 tests):** valid topology builds; vault-in-pool blocks construction; empty pool blocks construction; initial quarantine list honored.
- **Happy path (3 tests):** gate-passed signal routes; `RouteDecision` fields populated; counters increment; coordinator receives the signal.
- **Gate precondition (3 tests):** `gate_passed=False` rejects; coordinator is *not called* (proves no-bypass invariant); failed call does not consume scripted coordinator response.
- **Forbidden-target defenses (4 tests):** vault target, main target, out-of-pool target, missing-executor-address all rejected.
- **Coordinator failure modes (2 tests):** None return rejected; raised exception rejected fail-closed.
- **Quarantine semantics (4 tests):** all-quarantined short-circuits without calling coordinator; coordinator picking quarantined target rejected; clear restores; quarantining unknown is no-op.
- **Observability (1 test):** rejection counters bucket correctly by reason.

---

## Golden Corpus Assurance

| Item | Status |
|------|--------|
| CLAUDE.md + ADR read first | ✅ Both anchored before writing code; CLAUDE.md rule "Never overwrite lazarus.py wholesale" honored — this build adds a new module rather than modifying lazarus.py. |
| Tests pass; 5-layer data integrity intact | ✅ 100/100 unit tests pass. The new module does not touch `data_integrity.py`; its routing validation is orthogonal to the data integrity layers. |
| FMEA updated if new mode found | ✅ One new mode (coordinator-raises) recorded above; three slice-1 modes upgraded from "planned" to "implemented". |
| systemd service definitions consistent | N/A for this slice — the dispatcher is a library module, not yet a separate process. Slice 3 may add a systemd unit if the integration in `lazarus.py` warrants splitting; for now the routing decision happens inside the existing scanner-side process. |

---

## What's Deployed vs. Repo-Built (per *Trust Boundaries* boundary 7)

- **Deployed:** nothing from this slice. No production server change. No systemd unit added. The existing `lazarus.py` integration with `ScannerCoordinator` is unchanged.
- **Repo-built:** the new `src/dispatcher/` package and tests. Importable, fully tested, no network or solders dependency.
- **Planned (slice 3):** wire `TradeRouter` into `lazarus.py` main loop alongside the existing `_coordinator`, with the gate-passed precondition driven from the existing 12-point gate result. Add startup invocation of `validate_no_keys_in_env` and `validate_topology` to the dispatcher's process init.

---

## Stop Reason

Hit the 90-minute build ceiling per sprint segment directive. Module + tests complete; no in-progress work. Ready for SecOps #2 review on the env-key suffix list and DevOps #6 review on the integration boundary with the scanner-side coordinator before slice 3 wires it into `lazarus.py`.

*Quiet streets, loud comebacks.*
