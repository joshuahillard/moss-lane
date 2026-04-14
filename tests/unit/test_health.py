#!/usr/bin/env python3
"""
Unit tests for src/health/health_server.py

Covers:
  - SQLite DB probe: healthy (real trades table) and unhealthy (missing file,
    empty file without schema, nonexistent directory)
  - Connection cleanup: conn.close() called on all paths (no leaked handles)
  - Read-only probe: missing DB path does NOT create a file on disk
  - Postgres config: fail-closed when DB_BACKEND=postgres but DATABASE_URL empty
  - Process check: /proc scan, no pgrep dependency
  - Full payload: structure, version, service name, fail-closed aggregation
  - JSON round-trip: payload serializes and deserializes cleanly

Run:
  cd github-repo && pytest tests/unit/test_health.py -v
"""

import json
import os
import sqlite3
import tempfile
import shutil
import pytest

# Ensure env is set before importing the module under test
_tmpdir = tempfile.mkdtemp()
_test_db_path = os.path.join(_tmpdir, "lazarus.db")

# Create a real Lazarus-like DB with the trades table
_conn = sqlite3.connect(_test_db_path)
_conn.execute("""
    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT, symbol TEXT, token_address TEXT, wallet TEXT,
        entry_price_sol REAL, exit_price_sol REAL, pnl_usd REAL, pnl_pct REAL,
        size_usd REAL, paper INTEGER DEFAULT 0, source TEXT, exit_reason TEXT
    )
""")
_conn.commit()
_conn.close()

os.environ["DB_BACKEND"] = "sqlite"
os.environ["LAZARUS_DB_PATH"] = _test_db_path

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import src.health.health_server as hs


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_db_path():
    """Restore good DB path and backend after each test."""
    original = hs.SQLITE_PATH
    original_backend = hs.DB_BACKEND
    yield
    hs.SQLITE_PATH = original
    hs.DB_BACKEND = original_backend


@pytest.fixture(scope="session", autouse=True)
def cleanup_tmpdir():
    """Remove temp DB dir after all tests."""
    yield
    shutil.rmtree(_tmpdir, ignore_errors=True)


# ── SQLite DB Probe Tests ────────────────────────────────────────────────────

class TestCheckDb:

    def test_healthy_with_real_trades_table(self):
        """Real DB with trades table → healthy."""
        result = hs._check_db()
        assert result["status"] == "healthy"
        assert result["backend"] == "sqlite"
        assert result["latency_ms"] >= 0
        assert "error" not in result

    def test_unhealthy_nonexistent_directory(self):
        """Path in a directory that doesn't exist → unhealthy."""
        hs.SQLITE_PATH = "/nonexistent_dir_12345/bad.db"
        result = hs._check_db()
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert "not found" in result["error"].lower()

    def test_unhealthy_empty_db_no_trades_table(self):
        """
        SQLite file exists but has no trades table → unhealthy.
        SELECT COUNT(*) FROM trades fails because the table doesn't exist.
        """
        empty_db = os.path.join(_tmpdir, "empty.db")
        conn = sqlite3.connect(empty_db)
        conn.close()  # creates file with no tables
        hs.SQLITE_PATH = empty_db
        result = hs._check_db()
        assert result["status"] == "unhealthy"
        assert "error" in result
        assert "no such table" in result["error"].lower()
        os.unlink(empty_db)

    def test_unhealthy_nonexistent_file(self):
        """Nonexistent file → unhealthy with 'not found' error."""
        ghost_path = os.path.join(_tmpdir, "ghost_db_that_should_not_exist.db")
        if os.path.exists(ghost_path):
            os.unlink(ghost_path)
        hs.SQLITE_PATH = ghost_path
        result = hs._check_db()
        assert result["status"] == "unhealthy"
        assert "not found" in result["error"].lower()

    def test_probe_does_not_create_missing_db_file(self):
        """
        Probing a nonexistent DB path must NOT create the file on disk.
        sqlite3.connect() would create it — we must check existence first.
        """
        ghost_path = os.path.join(_tmpdir, "should_never_be_created.db")
        if os.path.exists(ghost_path):
            os.unlink(ghost_path)
        hs.SQLITE_PATH = ghost_path
        hs._check_db()
        assert not os.path.exists(ghost_path), \
            f"Probe created file at {ghost_path} — must be read-only"

    def test_connection_closed_on_healthy_probe(self):
        """After a healthy probe, the DB file must not be locked."""
        hs._check_db()
        # If conn was leaked, this second connect + write would hang or error
        conn = sqlite3.connect(_test_db_path, timeout=1)
        conn.execute("SELECT COUNT(*) FROM trades")
        conn.close()

    def test_connection_closed_on_unhealthy_probe(self):
        """After an unhealthy probe (bad schema), the DB file must not be locked."""
        empty_db = os.path.join(_tmpdir, "empty_lock_test.db")
        conn = sqlite3.connect(empty_db)
        conn.close()
        hs.SQLITE_PATH = empty_db
        hs._check_db()  # should fail on SELECT COUNT(*) FROM trades
        # Verify we can still delete the file (not locked by leaked handle)
        os.unlink(empty_db)
        assert not os.path.exists(empty_db)


# ── Postgres Config Fail-Closed ──────────────────────────────────────────────

class TestCheckDbPostgres:

    def test_unhealthy_postgres_empty_url(self):
        """DB_BACKEND=postgres but DATABASE_URL empty → unhealthy, not SQLite fallback."""
        hs.DB_BACKEND = "postgres"
        original_url = hs.DATABASE_URL
        hs.DATABASE_URL = ""
        result = hs._check_db()
        hs.DATABASE_URL = original_url
        assert result["status"] == "unhealthy"
        assert result["backend"] == "postgres"
        assert "DATABASE_URL" in result.get("error", "")


# ── Process Check Tests ──────────────────────────────────────────────────────

class TestCheckProcess:

    def test_returns_valid_structure(self):
        """Process check returns a dict with status field."""
        result = hs._check_process()
        assert "status" in result
        assert result["status"] in ("healthy", "unhealthy")

    def test_healthy_has_pid(self):
        """If healthy, pid must be an integer."""
        result = hs._check_process()
        if result["status"] == "healthy":
            assert isinstance(result["pid"], int)
            assert result["pid"] > 0

    def test_unhealthy_has_error(self):
        """If unhealthy, error field must be present."""
        result = hs._check_process()
        if result["status"] == "unhealthy":
            assert "error" in result

    def test_does_not_use_pgrep(self):
        """Verify the implementation doesn't shell out to pgrep."""
        import inspect
        source = inspect.getsource(hs._check_process)
        # Strip docstring to check only executable code
        lines = source.split("\n")
        in_docstring = False
        code_lines = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('"""'):
                in_docstring = not in_docstring
                if stripped.count('"""') == 2:
                    in_docstring = False
                continue
            if not in_docstring:
                code_lines.append(line)
        code_only = "\n".join(code_lines)
        assert "pgrep" not in code_only, "pgrep found in executable code"
        assert "os.popen" not in code_only, "os.popen found in executable code"
        assert "/proc" in code_only, "/proc scan not found in executable code"


# ── Full Payload Tests ───────────────────────────────────────────────────────

class TestBuildHealthPayload:

    def test_payload_structure(self):
        """All required fields present in payload."""
        payload, status_code = hs.build_health_payload()
        assert payload["service"] == "lazarus"
        assert payload["version"] == "3.1"
        assert isinstance(payload["uptime_seconds"], (int, float))
        assert "h" in payload["uptime_human"] and "m" in payload["uptime_human"]
        assert "T" in payload["timestamp"]
        assert "database" in payload["checks"]
        assert "process" in payload["checks"]
        assert payload["status"] in ("healthy", "unhealthy")
        assert status_code in (200, 503)

    def test_healthy_db_reflected_in_checks(self):
        """With good DB, checks.database.status == healthy."""
        payload, _ = hs.build_health_payload()
        assert payload["checks"]["database"]["status"] == "healthy"

    def test_fail_closed_bad_db(self):
        """Bad DB path → overall unhealthy, HTTP 503."""
        hs.SQLITE_PATH = "/nonexistent_dir_12345/bad.db"
        payload, status_code = hs.build_health_payload()
        assert status_code == 503
        assert payload["status"] == "unhealthy"
        assert payload["checks"]["database"]["status"] == "unhealthy"

    def test_fail_closed_empty_db(self):
        """Empty DB (no trades table) → overall unhealthy, HTTP 503."""
        empty_db = os.path.join(_tmpdir, "empty_payload_test.db")
        conn = sqlite3.connect(empty_db)
        conn.close()
        hs.SQLITE_PATH = empty_db
        payload, status_code = hs.build_health_payload()
        assert status_code == 503
        assert payload["status"] == "unhealthy"
        assert payload["checks"]["database"]["status"] == "unhealthy"
        os.unlink(empty_db)


# ── JSON Serialization ───────────────────────────────────────────────────────

class TestJsonSerialization:

    def test_round_trip(self):
        """Payload survives JSON serialize → deserialize."""
        payload, _ = hs.build_health_payload()
        json_str = json.dumps(payload, indent=2)
        reparsed = json.loads(json_str)
        assert reparsed == payload

    def test_unhealthy_payload_serializes(self):
        """Unhealthy payloads also serialize cleanly (error strings, etc.)."""
        hs.SQLITE_PATH = "/nonexistent_dir_12345/bad.db"
        payload, _ = hs.build_health_payload()
        json_str = json.dumps(payload, indent=2)
        reparsed = json.loads(json_str)
        assert reparsed["checks"]["database"]["status"] == "unhealthy"
