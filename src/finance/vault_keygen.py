#!/usr/bin/env python3
"""
Tax Vault Keypair Generation — OPERATOR-SIDE ONLY (ADR-006)

Generates a single Solana Ed25519 keypair for the tax vault. Designed to
run on the operator's own machine, NEVER on the trading server.

ADR-006 (deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md):
  - The tax vault private key must never be present on the production VPS.
  - Only the public address (TAX_VAULT_ADDRESS) is provisioned to the server.
  - Vault outbound transfers are operator actions, signed off-server.

This module:
  * Imports no .env handler — reads no .env, writes no .env.
  * Writes nothing to disk — the private key is printed to stdout once
    and is never persisted by this script.
  * Refuses to run on machines that look like the trading server, via
    a layered reverse guard (allow-list flag is primary; presence of
    burner keys or `/home/solbot/lazarus/` is defense-in-depth).
  * Prompts for explicit operator confirmation that the printed private
    key has been recorded on offline encrypted storage.

Invocation (from a clean operator laptop):
  MOSS_LANE_OPERATOR_MACHINE=true python -m src.finance.vault_keygen

The MOSS_LANE_OPERATOR_MACHINE flag should be set in the operator's shell
profile, not in any .env file that touches the server. Server-side
environments will never set this flag.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime
from typing import List, Optional, Tuple

try:
    from solders.keypair import Keypair
except ImportError:
    print("ERROR: solders library not found. Install with: pip install solders",
          file=sys.stderr)
    sys.exit(1)

try:
    import base58
except ImportError:
    print("ERROR: base58 library not found. Install with: pip install base58",
          file=sys.stderr)
    sys.exit(1)


# ════════════════════════════════════════════════════════════════════════════
# Reverse guard — refuse to run on anything that smells like the server
# ════════════════════════════════════════════════════════════════════════════

OPERATOR_ALLOW_LIST_VAR = "MOSS_LANE_OPERATOR_MACHINE"
SERVER_LAZARUS_PATH = "/home/solbot/lazarus/"
_BURNER_KEY_PATTERN = re.compile(r"^EXEC_WALLET_\d+_KEY$")


def _reverse_guard_check() -> Optional[str]:
    """
    Layered guard against running this script on the trading server.

    Returns None if all guards pass. Returns a single P0 error string
    listing ALL tripped guards (not just the first), so an operator
    fixing setup gets the full picture in one run.

    Layers checked:
      (c) Allow-list flag MOSS_LANE_OPERATOR_MACHINE must be 'true' [primary]
      (a) No EXEC_WALLET_*_KEY env var may be present and non-empty [defense]
      (b) Path /home/solbot/lazarus/ must not exist [defense]
    """
    failures: List[str] = []

    # (c) Primary: explicit operator allow-list
    flag = os.environ.get(OPERATOR_ALLOW_LIST_VAR, "").strip().lower()
    if flag != "true":
        failures.append(
            f"  - {OPERATOR_ALLOW_LIST_VAR}='true' is required. This flag "
            "must be set on the operator's machine only — never on the "
            "trading server. Set it in your shell profile and re-run."
        )

    # (a) Defense in depth: burner keys would only be present on the server
    burner_offenders = sorted(
        var_name for var_name, value in os.environ.items()
        if value and _BURNER_KEY_PATTERN.match(var_name)
    )
    if burner_offenders:
        failures.append(
            "  - Burner wallet keys present in environment: "
            f"{burner_offenders}. This script must not run on a machine "
            "that holds burner wallet keys."
        )

    # (b) Defense in depth: server filesystem layout
    if os.path.exists(SERVER_LAZARUS_PATH):
        failures.append(
            f"  - {SERVER_LAZARUS_PATH} exists on this filesystem. "
            "This script must not run on the trading server."
        )

    if failures:
        return (
            "P0 ADR-006: refusing to run. The following guards tripped:\n"
            + "\n".join(failures)
            + "\n\nGenerate the vault keypair on a clean operator machine."
        )
    return None


# ════════════════════════════════════════════════════════════════════════════
# Keypair generation
# ════════════════════════════════════════════════════════════════════════════

def _generate_vault_keypair() -> Tuple[str, str, str]:
    """
    Generate a single Ed25519 keypair via solders.

    Returns:
        Tuple of (public_address_base58, private_key_base58, fingerprint).
        Fingerprint is "<first 4 chars>...<last 4 chars>" of the pubkey.
    """
    kp = Keypair()
    pubkey = str(kp.pubkey())
    privkey_bytes = bytes(kp)
    privkey = base58.b58encode(privkey_bytes).decode("utf-8")
    fingerprint = f"{pubkey[:4]}...{pubkey[-4:]}"
    return pubkey, privkey, fingerprint


def _emit_keypair(pubkey: str, privkey: str, fingerprint: str,
                  timestamp: str) -> None:
    """
    Print the keypair to stdout in copy-paste-friendly format.

    The private key is printed exactly once, here. No code path in this
    module re-prints it after this call.
    """
    print(f"====== VAULT KEYPAIR GENERATED {timestamp} ======")
    print()
    print("PUBLIC ADDRESS (copy this to server .env):")
    print(f"TAX_VAULT_ADDRESS={pubkey}")
    print()
    print("PRIVATE KEY (DO NOT SAVE TO DISK; record on offline encrypted medium):")
    print(privkey)
    print()
    print("FINGERPRINT (record this in your offline log for audit reference):")
    print(fingerprint)
    print("=========================================================")


# ════════════════════════════════════════════════════════════════════════════
# Operator confirmation
# ════════════════════════════════════════════════════════════════════════════

CONFIRMATION_PROMPT = (
    "Have you recorded the private key on offline encrypted storage? [yes/no]: "
)


def _confirm_offline_recorded() -> bool:
    """
    Block until the operator confirms the key has been recorded.

    Returns True only if the response is exactly 'yes' (case-insensitive,
    whitespace-stripped). Anything else returns False — including empty
    input, 'y', 'YES, sort of', etc. The strictness is deliberate.
    """
    try:
        response = input(CONFIRMATION_PROMPT)
    except EOFError:
        # No stdin available (e.g., piped invocation) — treat as no confirmation
        return False
    return response.strip().lower() == "yes"


# ════════════════════════════════════════════════════════════════════════════
# Entry point
# ════════════════════════════════════════════════════════════════════════════

def main() -> int:
    """
    Entry point: run reverse guard, generate keypair, prompt for confirmation.

    Returns shell exit code: 0 on success, 1 on any failure or refusal.
    """
    err = _reverse_guard_check()
    if err:
        print(err, file=sys.stderr)
        return 1

    timestamp = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    pubkey, privkey, fingerprint = _generate_vault_keypair()
    _emit_keypair(pubkey, privkey, fingerprint, timestamp)

    if not _confirm_offline_recorded():
        print(
            "P0: Confirmation not received — operator must record the "
            "private key on offline encrypted storage before continuing. "
            "Exiting non-zero. Re-run when ready.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
