"""
Topology primitives — shared error class and env-scanner.

Extracted from src/dispatcher/route_trade.py (Phase 3 ADR-006 slice,
2026-04-30) so both src/data/data_integrity.py and src/dispatcher/route_trade.py
can import from a single source of truth.

Contents:
    TopologyError              — raised when capital-flow topology invariants fail
    validate_no_keys_in_env    — env scanner that flags forbidden signing keys

What stayed in route_trade.py:
    validate_topology(...) — dispatcher-specific runtime config check on the
        executor pool composition. Lives where it's used.

Backwards compatibility:
    src/dispatcher/route_trade.py re-imports both symbols, so
    `from route_trade import TopologyError, validate_no_keys_in_env`
    continues to resolve. This protects existing test imports.
"""

from __future__ import annotations

import os
from typing import Dict, List, Optional


class TopologyError(Exception):
    """
    Raised when capital-flow topology invariants would be violated.

    Examples:
      - executor address overlaps the vault address (ADR-006)
      - executor address overlaps the main wallet address (ADR-005)
      - executor pool is empty (no homogeneous burner fleet to route into)
      - duplicate executor address (ambiguous routing target)
      - forbidden signing-key env var present in a process that should not hold one
    """


def validate_no_keys_in_env(
    env: Optional[Dict[str, str]] = None,
    *,
    forbidden_suffixes: Optional[List[str]] = None,
) -> None:
    """
    Enforce ADR-007: a process must not have any signing keypair loadable
    from its environment.

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
        - Callers narrowing the suffix list (e.g., assert_vault_topology
          passing ["TAX_VAULT_KEY"]) get a focused check without touching
          legitimate keys held by other processes.
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
            "process has forbidden signing-key env vars: "
            f"{sorted(offenders)} — ADR-007 requires zero keys here. Move "
            "signing material to the burner-process env (and TAX_VAULT_KEY "
            "off-server entirely per ADR-006)."
        )
