"""
CI-style structural guards enforcing ADR-006/007 invariants across the codebase.

These tests AST-walk src/ and pattern-check module surfaces. They are designed
to catch a class of regression that unit tests cannot: a future PR that
re-introduces a forbidden capability (e.g., writing TAX_VAULT_KEY to .env,
adding an outbound transfer to TaxVault, or coupling vault_keygen to disk).

Per spec:
  1. test_no_tax_vault_key_writes_in_src
  2. test_tax_vault_module_has_no_outbound_signing
  3. test_wallet_generator_does_not_create_vault
  4. test_vault_keygen_does_not_write_disk

Limitations: AST analysis catches obvious patterns (literal + write call in
same function body, including string-concat obfuscation). It cannot evaluate
arbitrary runtime indirection (e.g., a key name passed in via a parameter).
That's why these guards are belt-and-suspenders alongside the runtime
startup assertion in src/data/data_integrity.py::assert_vault_topology.
"""

from __future__ import annotations

import ast
import io
import os
import tempfile
import unittest
from pathlib import Path
from typing import List, Optional
from unittest import mock


# ════════════════════════════════════════════════════════════════════════════
# Repo root resolution (works for both flat-import and qualified-import styles)
# ════════════════════════════════════════════════════════════════════════════

def _find_src_root() -> Path:
    """Return the absolute Path to the github-repo/src/ directory."""
    here = Path(__file__).resolve()
    # tests/unit/test_*.py → repo_root is two parents up
    candidate = here.parent.parent.parent / "src"
    if candidate.is_dir():
        return candidate
    raise RuntimeError(f"Could not locate src/ relative to {here}")


SRC_ROOT = _find_src_root()


# ════════════════════════════════════════════════════════════════════════════
# AST helpers
# ════════════════════════════════════════════════════════════════════════════

_VAULT_KEY_LITERAL = "TAX_VAULT_KEY"


def _evaluate_string_node(node: ast.AST) -> Optional[str]:
    """
    Try to evaluate an AST node to a string at static-analysis time.

    Handles:
      - ast.Constant with a string value
      - ast.BinOp(Add) of two evaluable string nodes (e.g., 'TAX_' + 'VAULT_KEY')

    Returns the resolved string, or None if the node isn't a static string.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        left = _evaluate_string_node(node.left)
        right = _evaluate_string_node(node.right)
        if left is not None and right is not None:
            return left + right
    return None


def _strip_docstring(body: List[ast.stmt]) -> List[ast.stmt]:
    """If the first statement is a docstring, return body[1:]."""
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        return body[1:]
    return body


def _is_vault_key_literal(node: ast.AST) -> bool:
    """True if the node statically resolves to the exact string TAX_VAULT_KEY."""
    return _evaluate_string_node(node) == _VAULT_KEY_LITERAL


def _is_suspicious_write_call(node: ast.AST) -> bool:
    """
    True if the node is a Call that could write to disk:
      - open(path, 'w'/'wb'/'a'/'a+'/...)
      - EnvLoader.write(...)
      - <anything>.write_text(...)
    """
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    # open(path, 'w' | 'wb' | 'a' | ...)
    if isinstance(func, ast.Name) and func.id == "open":
        if len(node.args) >= 2:
            mode = _evaluate_string_node(node.args[1])
            if mode and any(c in mode for c in ("w", "a", "x")):
                return True
        return False
    if isinstance(func, ast.Attribute):
        # EnvLoader.write(...)
        if (isinstance(func.value, ast.Name)
                and func.value.id == "EnvLoader"
                and func.attr == "write"):
            return True
        # <expr>.write_text(...)
        if func.attr == "write_text":
            return True
    return False


# ════════════════════════════════════════════════════════════════════════════
# Test 1 — no TAX_VAULT_KEY writes anywhere in src/
# ════════════════════════════════════════════════════════════════════════════

class NoTaxVaultKeyWritesInSrcTests(unittest.TestCase):
    """Guard 1: no function in src/ both names TAX_VAULT_KEY and writes to disk."""

    def test_no_tax_vault_key_writes_in_src(self) -> None:
        violations: List[str] = []
        for py_file in SRC_ROOT.rglob("*.py"):
            try:
                tree = ast.parse(
                    py_file.read_text(encoding="utf-8"),
                    filename=str(py_file),
                )
            except SyntaxError:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                body = _strip_docstring(node.body)

                has_literal = False
                has_write = False
                for stmt in body:
                    for child in ast.walk(stmt):
                        if not has_literal and _is_vault_key_literal(child):
                            has_literal = True
                        if not has_write and _is_suspicious_write_call(child):
                            has_write = True
                        if has_literal and has_write:
                            break
                    if has_literal and has_write:
                        break

                if has_literal and has_write:
                    rel = py_file.relative_to(SRC_ROOT.parent)
                    violations.append(f"{rel}:{node.lineno}:{node.name}")

        self.assertEqual(
            violations, [],
            "ADR-006 violation: function(s) in src/ contain both a literal "
            "'TAX_VAULT_KEY' string and a disk-write call. The vault key must "
            f"never be written to disk.\nViolations: {violations}",
        )


# ════════════════════════════════════════════════════════════════════════════
# Test 2 — TaxVault module has no outbound signing capability
# ════════════════════════════════════════════════════════════════════════════

class TaxVaultNoOutboundSigningTests(unittest.TestCase):
    """Guard 2: TaxVault is receive-only by construction (ADR-005, ADR-006)."""

    @classmethod
    def setUpClass(cls) -> None:
        try:
            import tax_vault as tv_module  # noqa: F401
        except ImportError:
            from src.finance import tax_vault as tv_module
        cls.tv_module = tv_module

    def test_no_outbound_method_attributes(self) -> None:
        # (a) No callable attribute named transfer_out, withdraw, send, drain,
        #     sweep, or starting with 'spend_'.
        forbidden = {"transfer_out", "withdraw", "send", "drain", "sweep"}
        TaxVault = getattr(self.tv_module, "TaxVault")
        for name in dir(TaxVault):
            if name in forbidden:
                self.fail(
                    f"TaxVault must not define '{name}' — vault is receive-only"
                )
            if name.startswith("spend_"):
                self.fail(
                    f"TaxVault must not define '{name}' — vault is receive-only"
                )

    def test_no_signing_substrings_in_source(self) -> None:
        # (b) Module source contains no string match for VersionedTransaction,
        #     sendTransaction, jupiter, or rpc_send (case-insensitive).
        source = Path(self.tv_module.__file__).read_text(encoding="utf-8").lower()
        for forbidden in ("versionedtransaction", "sendtransaction",
                          "jupiter", "rpc_send"):
            self.assertNotIn(
                forbidden, source,
                f"tax_vault.py must not reference '{forbidden}' — would imply "
                "outbound signing capability",
            )

    def test_no_imports_from_engine(self) -> None:
        # (c) AST-walk: no import of jupiter, no import of any module under
        #     src/engine/ that handles signing.
        tree = ast.parse(Path(self.tv_module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn(
                        "jupiter", alias.name.lower(),
                        "tax_vault.py must not import jupiter modules",
                    )
                    self.assertFalse(
                        alias.name.startswith("src.engine"),
                        f"tax_vault.py must not import {alias.name} — engine "
                        "module imports imply signing-path access",
                    )
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                self.assertNotIn(
                    "jupiter", module.lower(),
                    "tax_vault.py must not import jupiter modules",
                )
                # Disallow `from src.engine.X import Y` and `from engine.X import Y`
                self.assertFalse(
                    module.startswith("src.engine") or module.startswith("engine."),
                    f"tax_vault.py must not import from {module} — engine "
                    "module imports imply signing-path access",
                )


# ════════════════════════════════════════════════════════════════════════════
# Test 3 — wallet_generator does not create the vault
# ════════════════════════════════════════════════════════════════════════════

class WalletGeneratorNoVaultTests(unittest.TestCase):
    """Guard 3: server-side wallet generation produces burners only (ADR-006)."""

    def test_walletset_has_no_tax_vault_field(self) -> None:
        try:
            from wallet_generator import WalletSet, generate_wallets, ALLOCATION_PERCENTAGES
        except ImportError:
            from src.finance.wallet_generator import (
                WalletSet, generate_wallets, ALLOCATION_PERCENTAGES,
            )
        from dataclasses import fields

        # WalletSet dataclass has no tax_vault field
        field_names = {f.name for f in fields(WalletSet)}
        self.assertNotIn("tax_vault", field_names)

        # ALLOCATION_PERCENTAGES has no TAX_VAULT entry
        self.assertNotIn("TAX_VAULT", ALLOCATION_PERCENTAGES)

        # generate_wallets returns a WalletSet without a tax_vault attr
        result = generate_wallets(5)
        self.assertFalse(hasattr(result, "tax_vault"))


# ════════════════════════════════════════════════════════════════════════════
# Test 4 — vault_keygen does not write to disk
# ════════════════════════════════════════════════════════════════════════════

class VaultKeygenNoDiskWriteTests(unittest.TestCase):
    """Guard 4: vault_keygen prints to stdout only — never persists to disk."""

    def test_vault_keygen_does_not_write_disk(self) -> None:
        try:
            import vault_keygen
        except ImportError:
            from src.finance import vault_keygen

        # Snapshot listings of /tmp, ~, cwd before/after main() runs.
        # main() must produce no new files.
        with tempfile.TemporaryDirectory() as tmp:
            home = os.path.expanduser("~")
            cwd_orig = os.getcwd()
            os.chdir(tmp)
            try:
                tmp_listing_before = sorted(os.listdir(tmp))
                home_listing_before = sorted(os.listdir(home)) if os.path.isdir(home) else []

                env = {"MOSS_LANE_OPERATOR_MACHINE": "true"}
                with mock.patch.dict(os.environ, env, clear=True), \
                     mock.patch("os.path.exists",
                                side_effect=lambda p: p in (home, tmp) or os.path.isfile(p)
                                if not p.startswith("/home/solbot") else False), \
                     mock.patch("builtins.input", return_value="yes"), \
                     mock.patch("sys.stdout", new_callable=io.StringIO):
                    rc = vault_keygen.main()

                self.assertEqual(rc, 0)

                tmp_listing_after = sorted(os.listdir(tmp))
                home_listing_after = sorted(os.listdir(home)) if os.path.isdir(home) else []

                self.assertEqual(
                    tmp_listing_before, tmp_listing_after,
                    "vault_keygen must not create files in tmp directory",
                )
                self.assertEqual(
                    home_listing_before, home_listing_after,
                    "vault_keygen must not create files in home directory",
                )
            finally:
                os.chdir(cwd_orig)


if __name__ == "__main__":
    unittest.main()
