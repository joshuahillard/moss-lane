"""
Unit tests for src/data/data_integrity.py::assert_vault_topology.

ADR-006 startup assertion (extends Layer 4):
  (a) TAX_VAULT_ADDRESS must be present and non-empty.
  (b) TAX_VAULT_KEY must be absent or empty.

The env-scan portion delegates to src/utils/topology.py::validate_no_keys_in_env
so the suffix-list logic exists in exactly one place. These tests confirm
both the behavior and the delegation.
"""

from __future__ import annotations

import unittest
from unittest import mock

try:
    from data_integrity import assert_vault_topology
    from topology import TopologyError
except ImportError:
    from src.data.data_integrity import assert_vault_topology
    from src.utils.topology import TopologyError


class AssertVaultTopologyTests(unittest.TestCase):
    """Behavior of assert_vault_topology under various env shapes."""

    def test_passes_with_address_and_no_key(self) -> None:
        # Happy path: TAX_VAULT_ADDRESS present, TAX_VAULT_KEY absent.
        env = {"TAX_VAULT_ADDRESS": "Burner1Pubkey...abc"}
        # Must not raise.
        assert_vault_topology(env=env)

    def test_passes_with_address_and_legitimate_burner_keys(self) -> None:
        # Lazarus legitimately holds EXEC_WALLET_*_KEY; assert_vault_topology
        # must NOT flag those (only TAX_VAULT_KEY is forbidden in this layer).
        env = {
            "TAX_VAULT_ADDRESS": "VaultPubkey...abc",
            "EXEC_WALLET_1_KEY": "burner1_privkey",
            "EXEC_WALLET_2_KEY": "burner2_privkey",
            "SOLANA_PRIVATE_KEY": "main_wallet_privkey",
        }
        # Must not raise — these keys are valid for the lazarus process.
        assert_vault_topology(env=env)

    def test_fails_when_address_missing(self) -> None:
        env = {"OTHER_VAR": "value"}  # no TAX_VAULT_ADDRESS
        with self.assertRaises(TopologyError) as ctx:
            assert_vault_topology(env=env)
        self.assertIn("TAX_VAULT_ADDRESS", str(ctx.exception))
        self.assertIn("P0 ADR-006", str(ctx.exception))

    def test_fails_when_address_empty_string(self) -> None:
        env = {"TAX_VAULT_ADDRESS": ""}  # present but empty
        with self.assertRaises(TopologyError) as ctx:
            assert_vault_topology(env=env)
        self.assertIn("TAX_VAULT_ADDRESS", str(ctx.exception))

    def test_fails_when_address_whitespace_only(self) -> None:
        env = {"TAX_VAULT_ADDRESS": "   "}  # whitespace
        with self.assertRaises(TopologyError) as ctx:
            assert_vault_topology(env=env)
        self.assertIn("TAX_VAULT_ADDRESS", str(ctx.exception))

    def test_fails_when_tax_vault_key_present(self) -> None:
        env = {
            "TAX_VAULT_ADDRESS": "VaultPubkey...abc",
            "TAX_VAULT_KEY": "vault_privkey_should_not_be_here",
        }
        with self.assertRaises(TopologyError) as ctx:
            assert_vault_topology(env=env)
        msg = str(ctx.exception)
        self.assertIn("ROTATION PROCEDURE", msg)
        self.assertIn("TAX_VAULT_KEY", msg)
        self.assertIn("ADR-006", msg)

    def test_error_message_includes_full_rotation_procedure(self) -> None:
        env = {
            "TAX_VAULT_ADDRESS": "VaultPubkey...abc",
            "TAX_VAULT_KEY": "vault_privkey_should_not_be_here",
        }
        with self.assertRaises(TopologyError) as ctx:
            assert_vault_topology(env=env)
        msg = str(ctx.exception)
        # Spot-check key sections of the rotation procedure
        self.assertIn("python -m src.finance.vault_keygen", msg)
        self.assertIn("solana transfer", msg)
        self.assertIn("REMOVE the TAX_VAULT_KEY line entirely", msg)
        self.assertIn("Restart the service", msg)

    def test_uses_validate_no_keys_in_env(self) -> None:
        # Spec: confirm via mock that the topology validator is invoked,
        # not a duplicate implementation in data_integrity.
        env = {
            "TAX_VAULT_ADDRESS": "VaultPubkey...abc",
            # No TAX_VAULT_KEY — happy path through both checks
        }
        # Patch the symbol AS IMPORTED INTO data_integrity (not at the
        # source module). The import happened at module load time.
        try:
            import data_integrity as di
        except ImportError:
            from src.data import data_integrity as di
        with mock.patch.object(di, "validate_no_keys_in_env") as mock_validator:
            assert_vault_topology(env=env)
            mock_validator.assert_called_once()
            # Confirm the narrowed forbidden_suffixes list was passed
            _args, kwargs = mock_validator.call_args
            self.assertEqual(kwargs.get("forbidden_suffixes"), ["TAX_VAULT_KEY"])

    def test_default_env_is_os_environ(self) -> None:
        # If env=None, falls back to os.environ.
        with mock.patch.dict("os.environ", {"TAX_VAULT_ADDRESS": "addr"}, clear=True):
            assert_vault_topology()  # passes if reading os.environ correctly

        # Now set os.environ such that it would fail, and verify failure.
        with mock.patch.dict("os.environ",
                             {"TAX_VAULT_ADDRESS": "addr", "TAX_VAULT_KEY": "key"},
                             clear=True):
            with self.assertRaises(TopologyError):
                assert_vault_topology()


if __name__ == "__main__":
    unittest.main()
