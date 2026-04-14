#!/usr/bin/env python3
"""
Lazarus Health Server — Cloud Run liveness probe endpoint.

PURPOSE:
  Provides a /health endpoint that Cloud Run's liveness probe hits to determine
  whether the container should receive traffic. Returns service status, uptime,
  version, and real database connectivity.

DESIGN:
  - FAIL-CLOSED: If any check fails, returns HTTP 503 (unhealthy).
    Cloud Run liveness probe restarts the container on repeated 503s.
  - NO MOCK DATA: The DB check verifies Lazarus's actual `trades` table
    exists and is queryable — not just that SQLite can create a file.
  - Process check reads /proc directly — no pgrep dependency (not in slim image).
  - Runs as a standalone HTTP server on $PORT, started by entrypoint.sh
    before lazarus.py launches.
  - /health  → JSON payload with full status (liveness probe target)
  - /        → bare "ok" (backward compat for startup/readiness)

USAGE:
  python -m src.health.health_server          # defaults to port 8080
  python -m src.health.health_server 8080     # explicit port
"""

import json
import os
import sys
import time
import sqlite3
import logging
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime, timezone

# ══════════════════════════════════════════════════════════════════════════════
# CONSTANTS
# ══════════════════════════════════════════════════════════════════════════════
VERSION = "3.1"
SERVICE_NAME = "lazarus"

# Database path — mirrors lazarus.py and db_adapter.py defaults
DB_BACKEND = os.environ.get("DB_BACKEND", "sqlite").lower()
SQLITE_PATH = os.environ.get(
    "LAZARUS_DB_PATH", "/home/solbot/lazarus/logs/lazarus.db"
)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# Track when the health server started (proxy for container uptime)
_START_TIME = time.time()

log = logging.getLogger("health_server")


# ══════════════════════════════════════════════════════════════════════════════
# DATABASE PROBE — real connection, no mocks
# ══════════════════════════════════════════════════════════════════════════════
def _check_db() -> dict:
    """
    Verify the configured database is present and contains Lazarus's schema.
    Returns a dict with status, backend, and latency.

    WHY fresh connection every time:
      A pooled/cached connection could appear alive while the actual DB file
      is deleted, locked, or the PG server is down. Fresh connection = real check.

    WHY query the trades table (not SELECT 1):
      sqlite3.connect() on a nonexistent path silently creates an empty file.
      SELECT 1 succeeds on that empty file. Querying `trades` proves the real
      Lazarus database exists with its schema intact.

    WHY fail-closed on postgres + empty DATABASE_URL:
      If DB_BACKEND=postgres but DATABASE_URL is blank, that's a broken config.
      Silently falling back to SQLite would mask it. We report unhealthy instead.

    WHY os.path.isfile() before sqlite3.connect():
      sqlite3.connect() creates an empty file when the path doesn't exist (if the
      parent dir is writable). A health probe must be read-only — it should never
      mutate disk. Checking the file exists first avoids the side effect entirely.
    """
    t0 = time.time()
    conn = None
    try:
        if DB_BACKEND == "postgres":
            if not DATABASE_URL:
                return {
                    "status": "unhealthy",
                    "backend": "postgres",
                    "latency_ms": 0.0,
                    "error": "DB_BACKEND=postgres but DATABASE_URL is empty",
                }
            import psycopg2
            conn = psycopg2.connect(DATABASE_URL, connect_timeout=3)
            cur = conn.cursor()
            cur.execute("SELECT COUNT(*) FROM trades")
            cur.fetchone()
            cur.close()
        else:
            # SQLite — verify the DB file exists on disk BEFORE connecting.
            # sqlite3.connect() creates an empty file if the path is missing,
            # and a health probe must not write to disk.
            if not os.path.isfile(SQLITE_PATH):
                latency_ms = round((time.time() - t0) * 1000, 1)
                return {
                    "status": "unhealthy",
                    "backend": "sqlite",
                    "latency_ms": latency_ms,
                    "error": f"database file not found: {SQLITE_PATH}",
                }
            conn = sqlite3.connect(SQLITE_PATH, timeout=3)
            conn.execute("SELECT COUNT(*) FROM trades")

        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "status": "healthy",
            "backend": DB_BACKEND,
            "latency_ms": latency_ms,
        }
    except Exception as e:
        latency_ms = round((time.time() - t0) * 1000, 1)
        return {
            "status": "unhealthy",
            "backend": DB_BACKEND,
            "latency_ms": latency_ms,
            "error": str(e),
        }
    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:
                pass


def _check_process() -> dict:
    """
    Check whether the lazarus trading engine process is running.

    WHY /proc instead of pgrep:
      python:3.12-slim does not include pgrep (procps package). The /proc
      filesystem is always available in Linux containers. We scan
      /proc/[pid]/cmdline directly — zero external dependencies.
    """
    target = "src.engine.lazarus"
    my_pid = os.getpid()
    try:
        for entry in os.listdir("/proc"):
            if not entry.isdigit():
                continue
            pid = int(entry)
            if pid == my_pid:
                continue
            try:
                with open(f"/proc/{pid}/cmdline", "rb") as f:
                    cmdline = f.read().decode("utf-8", errors="replace")
                if target in cmdline:
                    return {"status": "healthy", "pid": pid}
            except (PermissionError, FileNotFoundError, ProcessLookupError):
                # Process exited between listdir and open, or we lack perms — skip
                continue
        return {"status": "unhealthy", "error": "lazarus process not found"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# ══════════════════════════════════════════════════════════════════════════════
# HEALTH PAYLOAD BUILDER
# ══════════════════════════════════════════════════════════════════════════════
def build_health_payload() -> tuple[dict, int]:
    """
    Build the full health check JSON payload.
    Returns (payload_dict, http_status_code).
    """
    uptime_sec = round(time.time() - _START_TIME, 1)
    hours = int(uptime_sec // 3600)
    minutes = int((uptime_sec % 3600) // 60)
    seconds = int(uptime_sec % 60)

    db_check = _check_db()
    process_check = _check_process()

    # FAIL-CLOSED: any unhealthy check → overall unhealthy → 503
    all_healthy = (
        db_check["status"] == "healthy"
        and process_check["status"] == "healthy"
    )

    payload = {
        "status": "healthy" if all_healthy else "unhealthy",
        "service": SERVICE_NAME,
        "version": VERSION,
        "uptime_seconds": uptime_sec,
        "uptime_human": f"{hours}h {minutes:02d}m {seconds:02d}s",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "checks": {
            "database": db_check,
            "process": process_check,
        },
    }

    status_code = 200 if all_healthy else 503
    return payload, status_code


# ══════════════════════════════════════════════════════════════════════════════
# HTTP HANDLER
# ══════════════════════════════════════════════════════════════════════════════
class HealthHandler(BaseHTTPRequestHandler):
    """
    Minimal HTTP handler with two routes:
      GET /health  → full JSON health payload (liveness probe target)
      GET /        → bare "ok" (backward compat)
      GET /*       → 404
    """

    def do_GET(self):
        if self.path == "/health":
            payload, status_code = build_health_payload()
            body = json.dumps(payload, indent=2).encode("utf-8")
            self.send_response(status_code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/":
            # Backward compat — startup/readiness probes may still hit /
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        else:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"not found")

    def log_message(self, format, *args):
        """Suppress default access logs — they clutter bot output."""
        pass


# ══════════════════════════════════════════════════════════════════════════════
# MAIN — run as standalone server
# ══════════════════════════════════════════════════════════════════════════════
def serve(port: int = 8080):
    """Start the health check HTTP server (blocking)."""
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    log.info(f"Health server listening on :{port}")
    server.serve_forever()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    port = int(sys.argv[1]) if len(sys.argv) > 1 else int(os.environ.get("PORT", 8080))
    serve(port)
