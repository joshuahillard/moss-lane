#!/usr/bin/env python3
"""
Minimal schema migration runner for Lazarus data stores.

Tracks applied migrations in schema_migrations and applies numbered SQL files
only when their target schema change is still missing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

MIGRATIONS_DIR = Path(__file__).with_name("migrations")
MIGRATIONS: list[tuple[str, str, str]] = [
    ("0001_add_filter_regime.sql", "trades", "filter_regime"),
]


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _ensure_registry_sql() -> str:
    return """
    CREATE TABLE IF NOT EXISTS schema_migrations (
        migration_id TEXT PRIMARY KEY,
        applied_at TEXT NOT NULL
    )
    """


def _sqlite_column_exists(conn, table: str, column: str) -> bool:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(row[1] == column for row in rows)


def _postgres_column_exists(conn, table: str, column: str) -> bool:
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_name = %s AND column_name = %s
            """,
            (table, column),
        )
        return cur.fetchone() is not None
    finally:
        cur.close()


def _execute(conn, backend: str, sql: str, params: tuple = ()) -> Iterable:
    if backend == "postgres":
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


def _close_cursor(cursor_or_result, backend: str) -> None:
    if backend == "postgres" and cursor_or_result is not None:
        cursor_or_result.close()


def _ensure_registry(conn, backend: str) -> None:
    cursor = _execute(conn, backend, _ensure_registry_sql())
    _close_cursor(cursor, backend)
    conn.commit()


def _applied_migrations(conn, backend: str) -> set[str]:
    cursor = _execute(conn, backend, "SELECT migration_id FROM schema_migrations")
    try:
        return {row[0] for row in cursor.fetchall()}
    finally:
        _close_cursor(cursor, backend)


def _record_migration(conn, backend: str, migration_id: str) -> None:
    cursor = _execute(
        conn,
        backend,
        "INSERT INTO schema_migrations (migration_id, applied_at) VALUES (?, ?)"
        if backend == "sqlite"
        else "INSERT INTO schema_migrations (migration_id, applied_at) VALUES (%s, %s)",
        (migration_id, _timestamp()),
    )
    _close_cursor(cursor, backend)


def apply_migrations(conn, backend: str, logger: Callable[[str], None] | None = None) -> list[str]:
    """
    Apply any unapplied migrations.

    For additive column migrations, the runner checks whether the target column
    already exists; if it does, the migration is simply marked as applied.
    """

    backend = backend.lower()
    if backend not in {"sqlite", "postgres"}:
        raise ValueError(f"Unsupported backend: {backend}")

    _ensure_registry(conn, backend)
    applied = _applied_migrations(conn, backend)
    applied_now: list[str] = []

    column_exists = _postgres_column_exists if backend == "postgres" else _sqlite_column_exists

    for migration_id, table, column in MIGRATIONS:
        if migration_id in applied:
            continue

        migration_path = MIGRATIONS_DIR / migration_id
        sql = migration_path.read_text(encoding="utf-8").strip()

        if not column_exists(conn, table, column):
            cursor = _execute(conn, backend, sql)
            _close_cursor(cursor, backend)
            if logger:
                logger(f"Applied migration {migration_id}")
        else:
            if logger:
                logger(f"Marked migration {migration_id} as already satisfied")

        _record_migration(conn, backend, migration_id)
        conn.commit()
        applied_now.append(migration_id)

    return applied_now
