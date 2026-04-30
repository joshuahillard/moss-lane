"""
Regression: skim path must work without TAX_VAULT_KEY in the environment.

ADR-006 removes TAX_VAULT_KEY from the trading server. The skim path is
signed by the BURNER (not the vault — the vault is the receiver), so the
vault private key is not needed for skim calculation. This test confirms
that TaxVault.calculate_skim functions correctly when only
TAX_VAULT_ADDRESS is configured.

If this test fails, it means the refactor accidentally coupled the skim
calculation to vault-key presence — which would make the new vault
topology break the skim flow on every properly-configured server.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
import unittest

try:
    from tax_vault import TaxVault, TaxVaultConfig
except ImportError:
    from src.finance.tax_vault import TaxVault, TaxVaultConfig


# A valid-looking base58 string for the address. TaxVaultConfig accepts any
# non-empty string for tax_vault_address; the receive path doesn't validate.
_TEST_VAULT_ADDRESS = "VaultPubkey1111111111111111111111111111111"
_TEST_EXECUTOR_ADDRESS = "Burner1Pubkey11111111111111111111111111111"


class SkimPathWithoutVaultPrivateKeyTests(unittest.TestCase):
    """Skim works with TAX_VAULT_ADDRESS only, no TAX_VAULT_KEY required."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test_lazarus.db")
        # Ensure no TAX_VAULT_KEY in env during the test
        self._saved_env = os.environ.pop("TAX_VAULT_KEY", None)

    def tearDown(self) -> None:
        if self._saved_env is not None:
            os.environ["TAX_VAULT_KEY"] = self._saved_env
        self.tmp.cleanup()

    def test_skim_works_without_vault_private_key(self) -> None:
        # ADR-006 setup: address-only configuration.
        cfg = TaxVaultConfig(
            tax_vault_address=_TEST_VAULT_ADDRESS,
            min_skim_sol=0.005,
            enabled=True,
        )
        vault = TaxVault(cfg, db_path=self.db_path)

        # Profitable trade — skim should fire.
        result = vault.calculate_skim(
            executor_address=_TEST_EXECUTOR_ADDRESS,
            pnl_sol=1.0,  # 1.0 SOL profit
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.executor_address, _TEST_EXECUTOR_ADDRESS)
        # 15% of 1.0 SOL = 0.15 SOL
        self.assertAlmostEqual(result.skim_sol, 0.15, places=6)
        self.assertAlmostEqual(result.accumulated_sol, 0.15, places=6)
        self.assertTrue(result.transfer_now)  # 0.15 >= min_skim_sol (0.005)
        self.assertAlmostEqual(result.amount_sol, 0.15, places=6)

    def test_skim_returns_none_on_loss(self) -> None:
        # Even without TAX_VAULT_KEY, calculate_skim must short-circuit on losses.
        cfg = TaxVaultConfig(tax_vault_address=_TEST_VAULT_ADDRESS, enabled=True)
        vault = TaxVault(cfg, db_path=self.db_path)
        result = vault.calculate_skim(
            executor_address=_TEST_EXECUTOR_ADDRESS,
            pnl_sol=-0.5,
        )
        self.assertIsNone(result)

    def test_skim_returns_none_when_disabled(self) -> None:
        cfg = TaxVaultConfig(tax_vault_address=_TEST_VAULT_ADDRESS, enabled=False)
        vault = TaxVault(cfg, db_path=self.db_path)
        result = vault.calculate_skim(
            executor_address=_TEST_EXECUTOR_ADDRESS,
            pnl_sol=1.0,
        )
        self.assertIsNone(result)

    def test_skim_returns_none_when_address_unset(self) -> None:
        # If TAX_VAULT_ADDRESS is empty, the skim path correctly skips.
        cfg = TaxVaultConfig(tax_vault_address="", enabled=True)
        vault = TaxVault(cfg, db_path=self.db_path)
        result = vault.calculate_skim(
            executor_address=_TEST_EXECUTOR_ADDRESS,
            pnl_sol=1.0,
        )
        self.assertIsNone(result)


class SkimLedgerWritesUnchangedTests(unittest.TestCase):
    """The tax_vault_ledger table writes still occur as before."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "test_lazarus.db")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_record_transfer_inserts_row(self) -> None:
        cfg = TaxVaultConfig(tax_vault_address=_TEST_VAULT_ADDRESS, enabled=True)
        vault = TaxVault(cfg, db_path=self.db_path)

        # Drive a skim so accumulated > 0
        vault.calculate_skim(executor_address=_TEST_EXECUTOR_ADDRESS, pnl_sol=1.0)
        # Record a successful transfer
        vault.record_transfer(
            executor_address=_TEST_EXECUTOR_ADDRESS,
            amount_sol=0.15,
            success=True,
            tx_signature="test_tx_sig_abcdef",
        )

        # Verify ledger row exists
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                "SELECT executor_address, skim_amount_sol, transfer_attempted, "
                "transfer_success, tx_signature FROM tax_vault_ledger"
            ).fetchone()
        finally:
            conn.close()

        self.assertIsNotNone(row)
        self.assertEqual(row[0], _TEST_EXECUTOR_ADDRESS)
        self.assertAlmostEqual(row[1], 0.15, places=6)
        self.assertEqual(row[2], 1)  # transfer_attempted
        self.assertEqual(row[3], 1)  # transfer_success
        self.assertEqual(row[4], "test_tx_sig_abcdef")

    def test_record_transfer_failure_keeps_accumulated(self) -> None:
        # Failed transfer should leave the accumulated balance untouched
        # so the next profitable trade retries.
        cfg = TaxVaultConfig(tax_vault_address=_TEST_VAULT_ADDRESS, enabled=True)
        vault = TaxVault(cfg, db_path=self.db_path)

        vault.calculate_skim(executor_address=_TEST_EXECUTOR_ADDRESS, pnl_sol=1.0)
        before = vault.get_accumulated(_TEST_EXECUTOR_ADDRESS)
        self.assertAlmostEqual(before, 0.15, places=6)

        vault.record_transfer(
            executor_address=_TEST_EXECUTOR_ADDRESS,
            amount_sol=0.15,
            success=False,
        )
        after = vault.get_accumulated(_TEST_EXECUTOR_ADDRESS)
        self.assertAlmostEqual(after, before, places=6)


if __name__ == "__main__":
    unittest.main()
