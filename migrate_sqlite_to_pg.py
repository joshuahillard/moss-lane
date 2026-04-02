#!/usr/bin/env python3
"""
Lazarus SQLite → PostgreSQL Migration Script

PURPOSE:
  Copies all trade history and runtime data from the VPS SQLite database
  to Cloud SQL PostgreSQL. Run once to seed Postgres with historical data.

USAGE:
  1. Copy lazarus.db from the VPS to your local machine:
     scp solbot@64.176.214.96:/home/solbot/lazarus/logs/lazarus.db ./lazarus.db

  2. Set the Postgres connection string:
     export DATABASE_URL="postgresql://lazarus:PASSWORD@IP:5432/lazarus"

  3. Run the migration:
     python migrate_sqlite_to_pg.py --sqlite-path ./lazarus.db

  4. Verify with:
     python migrate_sqlite_to_pg.py --sqlite-path ./lazarus.db --verify-only

SAFETY:
  - This script only INSERTS data — it never deletes from SQLite
  - If a table already has data in Postgres, it skips that table (no duplicates)
  - Run with --dry-run to see what would happen without writing anything
"""

import argparse
import sqlite3
import sys
import os

# Tables to migrate, in dependency order
TABLES = [
    "trades",
    "signal_performance",
    "wallet_activity",
    "cooldowns",
    "daily_pnl",
    "balance_snapshots",
    "btc_eth_pillars",
]


def get_pg_connection(database_url: str):
    """Connect to PostgreSQL."""
    try:
        import psycopg2
    except ImportError:
        print("ERROR: psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    return psycopg2.connect(database_url)


def get_table_columns(sqlite_conn, table: str) -> list:
    """Get column names for a table from SQLite."""
    cursor = sqlite_conn.execute(f"PRAGMA table_info({table})")
    return [row[1] for row in cursor.fetchall()]


def count_rows(conn, table: str, is_pg: bool = False) -> int:
    """Count rows in a table."""
    if is_pg:
        cursor = conn.cursor()
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        result = cursor.fetchone()[0]
        cursor.close()
        return result
    else:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def migrate_table(sqlite_conn, pg_conn, table: str, dry_run: bool = False) -> int:
    """Migrate a single table from SQLite to PostgreSQL. Returns row count."""
    columns = get_table_columns(sqlite_conn, table)

    # Skip the 'id' column — Postgres SERIAL auto-generates it
    data_columns = [c for c in columns if c != "id"]

    # Check if Postgres table already has data
    pg_count = count_rows(pg_conn, table, is_pg=True)
    if pg_count > 0:
        print(f"  SKIP  {table} — already has {pg_count} rows in Postgres")
        return 0

    # Read all rows from SQLite (excluding id column)
    col_list = ", ".join(data_columns)
    rows = sqlite_conn.execute(f"SELECT {col_list} FROM {table}").fetchall()

    if not rows:
        print(f"  SKIP  {table} — empty in SQLite")
        return 0

    if dry_run:
        print(f"  DRY   {table} — would migrate {len(rows)} rows")
        return len(rows)

    # Insert into Postgres
    placeholders = ", ".join(["%s"] * len(data_columns))
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES ({placeholders})"

    cursor = pg_conn.cursor()
    for row in rows:
        cursor.execute(insert_sql, row)
    pg_conn.commit()
    cursor.close()

    print(f"  DONE  {table} — migrated {len(rows)} rows")
    return len(rows)


def verify(sqlite_conn, pg_conn):
    """Compare row counts between SQLite and Postgres."""
    print("\nVerification — row counts:")
    print(f"  {'Table':<25} {'SQLite':>8} {'Postgres':>10} {'Match':>7}")
    print(f"  {'-'*25} {'-'*8} {'-'*10} {'-'*7}")

    all_match = True
    for table in TABLES:
        try:
            sq_count = count_rows(sqlite_conn, table)
        except Exception:
            sq_count = 0
        try:
            pg_count = count_rows(pg_conn, table, is_pg=True)
        except Exception:
            pg_count = 0

        match = "YES" if sq_count == pg_count else "NO"
        if sq_count != pg_count:
            all_match = False
        print(f"  {table:<25} {sq_count:>8} {pg_count:>10} {match:>7}")

    print()
    if all_match:
        print("  All tables match.")
    else:
        print("  WARNING: Some tables have mismatched row counts.")
    return all_match


def main():
    parser = argparse.ArgumentParser(description="Migrate Lazarus SQLite → PostgreSQL")
    parser.add_argument("--sqlite-path", required=True, help="Path to lazarus.db")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""),
                        help="PostgreSQL connection string (or set DATABASE_URL env var)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be migrated without writing")
    parser.add_argument("--verify-only", action="store_true",
                        help="Only compare row counts, don't migrate")
    args = parser.parse_args()

    if not args.database_url:
        print("ERROR: Set DATABASE_URL env var or pass --database-url")
        sys.exit(1)

    if not os.path.exists(args.sqlite_path):
        print(f"ERROR: SQLite file not found: {args.sqlite_path}")
        sys.exit(1)

    # Connect to both databases
    sqlite_conn = sqlite3.connect(args.sqlite_path)
    pg_conn = get_pg_connection(args.database_url)

    if args.verify_only:
        verify(sqlite_conn, pg_conn)
    else:
        print(f"\nMigrating from {args.sqlite_path} → PostgreSQL")
        if args.dry_run:
            print("(DRY RUN — no data will be written)\n")
        else:
            print()

        total = 0
        for table in TABLES:
            try:
                total += migrate_table(sqlite_conn, pg_conn, table, args.dry_run)
            except Exception as e:
                print(f"  ERROR {table} — {e}")
                pg_conn.rollback()

        print(f"\nTotal rows {'would be ' if args.dry_run else ''}migrated: {total}")

        if not args.dry_run:
            print("\nRunning verification...")
            verify(sqlite_conn, pg_conn)

    sqlite_conn.close()
    pg_conn.close()


if __name__ == "__main__":
    main()
