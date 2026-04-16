#!/usr/bin/env python3
"""
Apply tracked Lazarus schema migrations to SQLite or PostgreSQL.
"""

from __future__ import annotations

import argparse
import os
import sqlite3

try:
    from .migration_runner import apply_migrations
except ImportError:
    from migration_runner import apply_migrations


def _sqlite_connection(path: str):
    return sqlite3.connect(path, timeout=10)


def _postgres_connection(database_url: str):
    import psycopg2

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    return conn


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply tracked Lazarus schema migrations")
    parser.add_argument(
        "--backend",
        choices=("sqlite", "postgres"),
        default=os.environ.get("DB_BACKEND", "sqlite").lower(),
        help="Database backend to migrate",
    )
    parser.add_argument(
        "--sqlite-path",
        default=os.environ.get("LAZARUS_DB_PATH", "/home/solbot/lazarus/logs/lazarus.db"),
        help="SQLite path when backend=sqlite",
    )
    parser.add_argument(
        "--database-url",
        default=os.environ.get("DATABASE_URL", ""),
        help="PostgreSQL connection string when backend=postgres",
    )
    args = parser.parse_args()

    if args.backend == "postgres" and not args.database_url:
        raise SystemExit("DATABASE_URL is required when backend=postgres")

    if args.backend == "postgres":
        conn = _postgres_connection(args.database_url)
    else:
        conn = _sqlite_connection(args.sqlite_path)

    try:
        applied = apply_migrations(conn, args.backend, print)
        if not applied:
            print("No pending migrations.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
