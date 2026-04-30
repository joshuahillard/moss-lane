"""
Tests for the burners-only split of src/finance/wallet_generator.py.

Covers (per ADR-006 slice spec):
- Server path produces burners only — no TAX_VAULT in WalletSet
- WalletSet dataclass has no tax_vault field
- ALLOCATION_PERCENTAGES has no TAX_VAULT entry
- save_wallets_to_env raises ValueError on TAX_VAULT_KEY (case-insensitive)
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import fields

try:
    from wallet_generator import (
        ALLOCATION_PERCENTAGES,
        WalletConfig,
        WalletSet,
        _ADR006_VAULT_KEY_ERROR,
        _assert_no_vault_key_in_env_updates,
        generate_wallets,
        save_wallets_to_env,
    )
except ImportError:
    from src.finance.wallet_generator import (
        ALLOCATION_PERCENTAGES,
        WalletConfig,
        WalletSet,
        _ADR006_VAULT_KEY_ERROR,
        _assert_no_vault_key_in_env_updates,
        generate_wallets,
        save_wallets_to_env,
    )


class WalletGeneratorBurnersOnlyTests(unittest.TestCase):
    """ADR-006: server-side path no longer generates the tax vault."""

    def test_walletset_dataclass_has_no_tax_vault_field(self) -> None:
        field_names = {f.name for f in fields(WalletSet)}
        self.assertNotIn("tax_vault", field_names)
        self.assertEqual(field_names, {"execution_wallets", "generated_at"})

    def test_allocation_percentages_has_no_tax_vault(self) -> None:
        self.assertNotIn("TAX_VAULT", ALLOCATION_PERCENTAGES)
        self.assertEqual(set(ALLOCATION_PERCENTAGES.keys()), {
            "EXEC_WALLET_1", "EXEC_WALLET_2", "EXEC_WALLET_3",
            "EXEC_WALLET_4", "EXEC_WALLET_5",
        })

    def test_generate_wallets_returns_burners_only(self) -> None:
        result = generate_wallets(wallet_count=5)
        self.assertIsInstance(result, WalletSet)
        self.assertEqual(len(result.execution_wallets), 5)
        # WalletSet has no tax_vault attribute at all (not just None)
        self.assertFalse(hasattr(result, "tax_vault"))
        # Every produced wallet is an execution wallet
        for w in result.execution_wallets:
            self.assertIsInstance(w, WalletConfig)
            self.assertTrue(w.env_var_name.startswith("EXEC_WALLET_"))
            self.assertTrue(w.env_var_name.endswith("_KEY"))
            self.assertNotEqual(w.env_var_name, "TAX_VAULT_KEY")

    def test_server_path_save_only_writes_burner_keys(self) -> None:
        result = generate_wallets(wallet_count=5)
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            save_wallets_to_env(result, env_path=env_path)
            with open(env_path) as f:
                content = f.read()
            self.assertNotIn("TAX_VAULT_KEY", content)
            for i in range(1, 6):
                self.assertIn(f"EXEC_WALLET_{i}_KEY=", content)


class SaveWalletsToEnvVaultKeyGuardTests(unittest.TestCase):
    """ADR-006: save_wallets_to_env refuses to write TAX_VAULT_KEY."""

    def test_assert_helper_raises_on_canonical_vault_key(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _assert_no_vault_key_in_env_updates({"TAX_VAULT_KEY": "abc"})
        self.assertIn("ADR-006", str(ctx.exception))

    def test_assert_helper_raises_on_lowercase_vault_key(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _assert_no_vault_key_in_env_updates({"tax_vault_key": "abc"})
        self.assertIn("ADR-006", str(ctx.exception))

    def test_assert_helper_raises_on_titlecase_vault_key(self) -> None:
        with self.assertRaises(ValueError) as ctx:
            _assert_no_vault_key_in_env_updates({"Tax_Vault_Key": "abc"})
        self.assertIn("ADR-006", str(ctx.exception))

    def test_assert_helper_raises_on_mixed_with_burners(self) -> None:
        # Even if burner keys are also present, the vault key trips the guard.
        with self.assertRaises(ValueError):
            _assert_no_vault_key_in_env_updates({
                "EXEC_WALLET_1_KEY": "burner1",
                "TAX_VAULT_KEY": "abc",
                "EXEC_WALLET_2_KEY": "burner2",
            })

    def test_assert_helper_passes_with_burners_only(self) -> None:
        # No raise when the dict only contains burner keys.
        _assert_no_vault_key_in_env_updates({
            "EXEC_WALLET_1_KEY": "burner1",
            "EXEC_WALLET_2_KEY": "burner2",
        })

    def test_save_wallets_to_env_raises_on_tampered_walletset(self) -> None:
        # Construct a tampered WalletSet whose execution_wallets contain an
        # entry with env_var_name='TAX_VAULT_KEY'. save_wallets_to_env must
        # refuse to write rather than silently let the vault key through.
        tampered = WalletSet(
            execution_wallets=[
                WalletConfig(
                    name="EXEC_WALLET_1",
                    pubkey="abc",
                    private_key_base58="defghi",
                    env_var_name="TAX_VAULT_KEY",  # tampered
                    allocation_pct=0.20,
                ),
            ],
            generated_at="2026-04-30T00:00:00",
        )
        with tempfile.TemporaryDirectory() as tmp:
            env_path = os.path.join(tmp, ".env")
            with self.assertRaises(ValueError) as ctx:
                save_wallets_to_env(tampered, env_path=env_path)
            self.assertIn("ADR-006", str(ctx.exception))
            # The .env file must not have been created with the vault key
            if os.path.exists(env_path):
                with open(env_path) as f:
                    self.assertNotIn("TAX_VAULT_KEY", f.read())

    def test_error_message_constant_references_adr006(self) -> None:
        # Defensive: the error constant carries the ADR pointer.
        self.assertIn("ADR-006", _ADR006_VAULT_KEY_ERROR)
        self.assertIn("TAX_VAULT_KEY", _ADR006_VAULT_KEY_ERROR)


if __name__ == "__main__":
    unittest.main()
