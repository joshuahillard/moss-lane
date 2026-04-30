"""
Tests for src/finance/vault_keygen.py — operator-side vault keypair generator.

Covers (per ADR-006 slice spec):
- Reverse guard refuses when allow-list flag missing
- Reverse guard refuses when EXEC_WALLET_*_KEY present
- Reverse guard refuses when /home/solbot/lazarus/ exists
- Reverse guard reports ALL failures at once (per Stage 4 gate decision)
- Operator path produces vault keypair output (no file writes)
- Operator path refuses on 'no' confirmation (no extra private-key output)
- EOFError on stdin treated as no confirmation

All stdin interaction is mocked via unittest.mock.patch — no subprocess use.
"""

from __future__ import annotations

import io
import os
import tempfile
import unittest
from unittest import mock

try:
    import vault_keygen
except ImportError:
    from src.finance import vault_keygen


def _clear_burner_env(env_dict: dict) -> dict:
    """Drop any EXEC_WALLET_*_KEY entries from a dict copy."""
    return {k: v for k, v in env_dict.items() if not k.startswith("EXEC_WALLET_")}


class ReverseGuardTests(unittest.TestCase):
    """The reverse guard is the primary structural defense for ADR-006."""

    def test_refuses_when_allow_list_flag_missing(self) -> None:
        clean_env = _clear_burner_env({})  # no MOSS_LANE_OPERATOR_MACHINE
        with mock.patch.dict(os.environ, clean_env, clear=True), \
             mock.patch("os.path.exists", return_value=False):
            err = vault_keygen._reverse_guard_check()
        self.assertIsNotNone(err)
        self.assertIn("MOSS_LANE_OPERATOR_MACHINE", err)
        self.assertIn("P0 ADR-006", err)

    def test_refuses_when_exec_wallet_key_present(self) -> None:
        # Allow-list flag SET, but a burner key is also present (defense in depth).
        env = {
            "MOSS_LANE_OPERATOR_MACHINE": "true",
            "EXEC_WALLET_1_KEY": "anything",
        }
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.exists", return_value=False):
            err = vault_keygen._reverse_guard_check()
        self.assertIsNotNone(err)
        self.assertIn("EXEC_WALLET_1_KEY", err)

    def test_refuses_when_solbot_path_exists(self) -> None:
        env = {"MOSS_LANE_OPERATOR_MACHINE": "true"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.exists", return_value=True):
            err = vault_keygen._reverse_guard_check()
        self.assertIsNotNone(err)
        self.assertIn("/home/solbot/lazarus", err)

    def test_passes_when_allow_list_flag_set_clean(self) -> None:
        env = {"MOSS_LANE_OPERATOR_MACHINE": "true"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.exists", return_value=False):
            err = vault_keygen._reverse_guard_check()
        self.assertIsNone(err)

    def test_reports_all_failures_at_once(self) -> None:
        # Stage 4 gate decision: collect all failures, don't stop at first.
        env = {"EXEC_WALLET_1_KEY": "burner"}  # missing flag AND burner present
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.exists", return_value=True):  # also path
            err = vault_keygen._reverse_guard_check()
        self.assertIsNotNone(err)
        self.assertIn("MOSS_LANE_OPERATOR_MACHINE", err)
        self.assertIn("EXEC_WALLET_1_KEY", err)
        self.assertIn("/home/solbot/lazarus", err)

    def test_allow_list_accepts_uppercase_true(self) -> None:
        # Decision 2 from gate: only literal "true" word, any caps.
        env = {"MOSS_LANE_OPERATOR_MACHINE": "TRUE"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.exists", return_value=False):
            err = vault_keygen._reverse_guard_check()
        self.assertIsNone(err)

    def test_allow_list_rejects_yes(self) -> None:
        # Strictness check: "yes" should NOT count as truthy.
        env = {"MOSS_LANE_OPERATOR_MACHINE": "yes"}
        with mock.patch.dict(os.environ, env, clear=True), \
             mock.patch("os.path.exists", return_value=False):
            err = vault_keygen._reverse_guard_check()
        self.assertIsNotNone(err)


class GenerateVaultKeypairTests(unittest.TestCase):
    """The keygen helper produces a valid keypair and a fingerprint."""

    def test_returns_three_strings(self) -> None:
        pubkey, privkey, fp = vault_keygen._generate_vault_keypair()
        self.assertIsInstance(pubkey, str)
        self.assertIsInstance(privkey, str)
        self.assertIsInstance(fp, str)

    def test_fingerprint_format(self) -> None:
        pubkey, _privkey, fp = vault_keygen._generate_vault_keypair()
        self.assertEqual(fp, f"{pubkey[:4]}...{pubkey[-4:]}")

    def test_keypair_is_unique_per_call(self) -> None:
        pk1, _, _ = vault_keygen._generate_vault_keypair()
        pk2, _, _ = vault_keygen._generate_vault_keypair()
        self.assertNotEqual(pk1, pk2)


class ConfirmationPromptTests(unittest.TestCase):
    """Operator must explicitly confirm offline storage."""

    def test_yes_returns_true(self) -> None:
        with mock.patch("builtins.input", return_value="yes"):
            self.assertTrue(vault_keygen._confirm_offline_recorded())

    def test_yes_with_whitespace_returns_true(self) -> None:
        with mock.patch("builtins.input", return_value="  yes  "):
            self.assertTrue(vault_keygen._confirm_offline_recorded())

    def test_yes_uppercase_returns_true(self) -> None:
        with mock.patch("builtins.input", return_value="YES"):
            self.assertTrue(vault_keygen._confirm_offline_recorded())

    def test_no_returns_false(self) -> None:
        with mock.patch("builtins.input", return_value="no"):
            self.assertFalse(vault_keygen._confirm_offline_recorded())

    def test_y_alone_returns_false(self) -> None:
        # Strictness: single 'y' must NOT count.
        with mock.patch("builtins.input", return_value="y"):
            self.assertFalse(vault_keygen._confirm_offline_recorded())

    def test_empty_returns_false(self) -> None:
        with mock.patch("builtins.input", return_value=""):
            self.assertFalse(vault_keygen._confirm_offline_recorded())

    def test_eoferror_returns_false(self) -> None:
        # No-keyboard scenario (EOFError) must default to no-confirmation.
        with mock.patch("builtins.input", side_effect=EOFError()):
            self.assertFalse(vault_keygen._confirm_offline_recorded())


class MainEntryPointTests(unittest.TestCase):
    """End-to-end main() flow with mocked stdin."""

    def _operator_env(self) -> dict:
        # Clean env: only the allow-list flag, no burner keys.
        return {"MOSS_LANE_OPERATOR_MACHINE": "true"}

    def test_main_zero_exit_on_yes(self) -> None:
        with mock.patch.dict(os.environ, self._operator_env(), clear=True), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch("builtins.input", return_value="yes"), \
             mock.patch("sys.stdout", new_callable=io.StringIO):
            rc = vault_keygen.main()
        self.assertEqual(rc, 0)

    def test_main_nonzero_exit_on_no(self) -> None:
        with mock.patch.dict(os.environ, self._operator_env(), clear=True), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch("builtins.input", return_value="no"), \
             mock.patch("sys.stdout", new_callable=io.StringIO), \
             mock.patch("sys.stderr", new_callable=io.StringIO):
            rc = vault_keygen.main()
        self.assertEqual(rc, 1)

    def test_main_nonzero_exit_when_guard_fails(self) -> None:
        # No allow-list flag → guard trips → return 1 BEFORE any keygen.
        with mock.patch.dict(os.environ, {}, clear=True), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            rc = vault_keygen.main()
        self.assertEqual(rc, 1)
        self.assertIn("P0 ADR-006", stderr.getvalue())

    def test_main_prints_address_and_privkey_on_success_path(self) -> None:
        with mock.patch.dict(os.environ, self._operator_env(), clear=True), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch("builtins.input", return_value="yes"), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as stdout:
            vault_keygen.main()
        out = stdout.getvalue()
        self.assertIn("TAX_VAULT_ADDRESS=", out)
        self.assertIn("PUBLIC ADDRESS", out)
        self.assertIn("PRIVATE KEY", out)
        self.assertIn("FINGERPRINT", out)

    def test_main_does_not_write_any_file(self) -> None:
        # Spec: "vault_keygen.py NEVER writes the private key to any file."
        with tempfile.TemporaryDirectory() as tmp:
            cwd_before = os.listdir(tmp)
            cwd_orig = os.getcwd()
            try:
                os.chdir(tmp)
                with mock.patch.dict(os.environ, self._operator_env(), clear=True), \
                     mock.patch("os.path.exists", return_value=False), \
                     mock.patch("builtins.input", return_value="yes"), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):
                    vault_keygen.main()
                cwd_after = os.listdir(tmp)
            finally:
                os.chdir(cwd_orig)
            self.assertEqual(cwd_before, cwd_after)

    def test_main_no_extra_privkey_output_after_no_confirmation(self) -> None:
        # Spec: "assert no further output containing the private key beyond
        # the warning" — captured stdout sees the privkey once (during emit),
        # stderr sees the refusal warning which must not contain the privkey.
        with mock.patch.dict(os.environ, self._operator_env(), clear=True), \
             mock.patch("os.path.exists", return_value=False), \
             mock.patch("builtins.input", return_value="no"), \
             mock.patch("sys.stdout", new_callable=io.StringIO) as stdout, \
             mock.patch("sys.stderr", new_callable=io.StringIO) as stderr:
            rc = vault_keygen.main()
        self.assertEqual(rc, 1)
        # The warning is on stderr; it must NOT echo the private key line.
        # Find the printed privkey from stdout, then confirm it's not on stderr.
        stdout_lines = stdout.getvalue().splitlines()
        # The privkey is the line directly after "PRIVATE KEY (...)" in the emit.
        privkey_line_idx = next(
            i for i, line in enumerate(stdout_lines)
            if line.startswith("PRIVATE KEY (")
        )
        privkey_value = stdout_lines[privkey_line_idx + 1].strip()
        self.assertNotIn(privkey_value, stderr.getvalue())


class StructuralGuaranteesTests(unittest.TestCase):
    """Defense-in-depth structural checks on the module surface."""

    def test_module_has_no_envloader_import(self) -> None:
        # ADR-006: vault_keygen must never import EnvLoader.
        with open(vault_keygen.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("EnvLoader", source)
        self.assertNotIn("env_loader", source)

    def test_module_has_no_open_or_write_to_disk(self) -> None:
        # The module must not call open() in write mode anywhere.
        # Allow open() in tests, but not in production source.
        with open(vault_keygen.__file__, encoding="utf-8") as f:
            source = f.read()
        self.assertNotIn("open(", source)
        self.assertNotIn(".write(", source)
        self.assertNotIn(".write_text", source)

    def test_module_has_no_outbound_signing_capability(self) -> None:
        # No transfer / send / spend / withdraw / drain functions.
        with open(vault_keygen.__file__, encoding="utf-8") as f:
            source = f.read()
        for forbidden in ("transfer_out", "withdraw", "send_transaction",
                          "drain", "sweep_out", "spend"):
            self.assertNotIn(
                forbidden, source,
                f"vault_keygen must not define a `{forbidden}` capability",
            )


if __name__ == "__main__":
    unittest.main()
