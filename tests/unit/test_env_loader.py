"""
Contract-preservation tests for src/utils/env_loader.py.

The EnvLoader class was extracted from src/finance/wallet_generator.py
in the ADR-006 slice (2026-04-30). Behavior was preserved verbatim;
these tests codify the contract so future refactors cannot regress it.

Covers:
- load() returns dict shape with all key=value pairs
- Quoted-value handling: single quotes, double quotes, unquoted
- Empty / missing-file handling
- write() with backup=True creates .backup file
- write() merges with existing keys
"""

from __future__ import annotations

import os
import tempfile
import unittest

try:
    from env_loader import EnvLoader
except ImportError:
    from src.utils.env_loader import EnvLoader


class EnvLoaderLoadTests(unittest.TestCase):
    """load() — contract preservation."""

    def test_load_missing_file_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = os.path.join(tmp, "does_not_exist.env")
            self.assertEqual(EnvLoader.load(missing), {})

    def test_load_empty_file_returns_empty_dict(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            empty = os.path.join(tmp, "empty.env")
            with open(empty, "w") as f:
                f.write("")
            self.assertEqual(EnvLoader.load(empty), {})

    def test_load_returns_dict_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("FOO=bar\nBAZ=qux\n")
            result = EnvLoader.load(path)
            self.assertIsInstance(result, dict)
            self.assertEqual(result, {"FOO": "bar", "BAZ": "qux"})

    def test_load_strips_double_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write('KEY="value with spaces"\n')
            self.assertEqual(EnvLoader.load(path), {"KEY": "value with spaces"})

    def test_load_strips_single_quotes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("KEY='single quoted'\n")
            self.assertEqual(EnvLoader.load(path), {"KEY": "single quoted"})

    def test_load_preserves_unquoted_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("KEY=plain_value\n")
            self.assertEqual(EnvLoader.load(path), {"KEY": "plain_value"})

    def test_load_skips_comments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("# this is a comment\nKEY=value\n# another\n")
            self.assertEqual(EnvLoader.load(path), {"KEY": "value"})

    def test_load_skips_empty_lines(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("\n\nKEY=value\n\n")
            self.assertEqual(EnvLoader.load(path), {"KEY": "value"})

    def test_load_skips_lines_without_equals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("not_a_kv_line\nKEY=value\n")
            self.assertEqual(EnvLoader.load(path), {"KEY": "value"})

    def test_load_handles_value_with_equals_sign(self) -> None:
        # split('=', 1) ensures embedded '=' stays in the value
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("URL=https://example.com/path?a=b&c=d\n")
            self.assertEqual(
                EnvLoader.load(path),
                {"URL": "https://example.com/path?a=b&c=d"},
            )


class EnvLoaderWriteTests(unittest.TestCase):
    """write() — contract preservation."""

    def test_write_creates_file_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            EnvLoader.write(path, {"FOO": "bar"}, backup=False)
            self.assertTrue(os.path.exists(path))
            self.assertEqual(EnvLoader.load(path), {"FOO": "bar"})

    def test_write_with_backup_creates_backup_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("OLD=keep\n")
            EnvLoader.write(path, {"NEW": "value"}, backup=True)
            self.assertTrue(os.path.exists(path + ".backup"))
            with open(path + ".backup") as f:
                self.assertIn("OLD=keep", f.read())

    def test_write_with_backup_false_no_backup_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("OLD=keep\n")
            EnvLoader.write(path, {"NEW": "value"}, backup=False)
            self.assertFalse(os.path.exists(path + ".backup"))

    def test_write_merges_with_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("EXISTING=preserved\n")
            EnvLoader.write(path, {"ADDED": "new"}, backup=False)
            result = EnvLoader.load(path)
            self.assertEqual(result, {"EXISTING": "preserved", "ADDED": "new"})

    def test_write_overwrites_existing_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, ".env")
            with open(path, "w") as f:
                f.write("KEY=original\n")
            EnvLoader.write(path, {"KEY": "updated"}, backup=False)
            self.assertEqual(EnvLoader.load(path), {"KEY": "updated"})


if __name__ == "__main__":
    unittest.main()
