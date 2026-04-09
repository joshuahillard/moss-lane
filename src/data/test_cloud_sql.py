#!/usr/bin/env python3
"""
Cloud SQL Connection Test — verifies PostgreSQL is reachable and schema is correct.

USAGE (local with Cloud SQL Auth Proxy running):
  DB_BACKEND=postgres DATABASE_URL="postgresql://lazarus:PASSWORD@/lazarus?host=/cloudsql/moss-lane:us-east1:lazarus-db" \
    python -m src.data.test_cloud_sql

USAGE (on Cloud Run — secrets injected by Secret Manager):
  python -m src.data.test_cloud_sql

WHAT IT CHECKS:
  1. Connection to PostgreSQL via DATABASE_URL
  2. All 11 tables exist with correct column counts
  3. Epoch gating query works (text comparison, NOT strftime)
  4. INSERT + SELECT round-trip on trades table
  5. Cleanup of test data
"""

import os
import sys
import time

# Expected tables and their minimum column counts
EXPECTED_TABLES = {
    "trades": 27,
    "signal_performance": 5,
    "wallet_activity": 6,
    "cooldowns": 4,
    "daily_pnl": 3,
    "balance_snapshots": 11,
    "btc_eth_pillars": 8,
    "bot_config": 4,
    "config_audit_log": 7,
    "dynamic_config": 4,
    "rug_blacklist": 4,
}

V3_EPOCH = "2026-03-29T17:44:00"


def test_connection():
    """Test 1: Can we connect at all?"""
    database_url = os.environ.get("DATABASE_URL", "")
    if not database_url:
        print("FAIL  No DATABASE_URL set")
        return None

    try:
        import psycopg2
    except ImportError:
        print("FAIL  psycopg2 not installed (pip install psycopg2-binary)")
        return None

    try:
        conn = psycopg2.connect(database_url)
        conn.autocommit = False
        print("PASS  Connected to PostgreSQL")
        return conn
    except Exception as e:
        print(f"FAIL  Connection failed: {e}")
        return None


def test_tables(conn):
    """Test 2: Do all 11 tables exist with correct schemas?"""
    cursor = conn.cursor()
    all_ok = True

    for table, min_cols in EXPECTED_TABLES.items():
        cursor.execute("""
            SELECT column_name FROM information_schema.columns
            WHERE table_name = %s ORDER BY ordinal_position
        """, (table,))
        columns = [row[0] for row in cursor.fetchall()]

        if not columns:
            print(f"FAIL  Table '{table}' does not exist")
            all_ok = False
        elif len(columns) < min_cols:
            print(f"FAIL  Table '{table}' has {len(columns)} columns, expected >= {min_cols}")
            all_ok = False
        else:
            print(f"PASS  Table '{table}' — {len(columns)} columns")

    cursor.close()
    return all_ok


def test_epoch_gating(conn):
    """Test 3: Epoch gating query uses text comparison (not strftime)."""
    cursor = conn.cursor()
    try:
        # This query must work with ISO text comparison — the way Lazarus filters
        cursor.execute(
            "SELECT COUNT(*) FROM trades WHERE timestamp >= %s",
            (V3_EPOCH,)
        )
        count = cursor.fetchone()[0]
        print(f"PASS  Epoch gating query works (text comparison) — {count} post-epoch trades")
        cursor.close()
        return True
    except Exception as e:
        print(f"FAIL  Epoch gating query failed: {e}")
        conn.rollback()
        cursor.close()
        return False


def test_round_trip(conn):
    """Test 4: INSERT + SELECT + DELETE round-trip."""
    cursor = conn.cursor()
    test_ts = "2099-01-01T00:00:00+00:00"  # Far-future timestamp for easy cleanup

    try:
        # Insert test row
        cursor.execute("""
            INSERT INTO trades (timestamp, symbol, token_address, wallet, pnl_usd, paper)
            VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING id
        """, (test_ts, "TEST_TOKEN", "test_addr_000", "test_wallet", 0.0, 1))
        row_id = cursor.fetchone()[0]
        conn.commit()

        # Read it back
        cursor.execute("SELECT symbol FROM trades WHERE id = %s", (row_id,))
        result = cursor.fetchone()
        if result and result[0] == "TEST_TOKEN":
            print(f"PASS  Round-trip INSERT/SELECT (id={row_id})")
        else:
            print(f"FAIL  Round-trip SELECT returned unexpected: {result}")
            return False

        # Cleanup
        cursor.execute("DELETE FROM trades WHERE id = %s", (row_id,))
        conn.commit()
        print(f"PASS  Cleanup — deleted test row id={row_id}")
        cursor.close()
        return True

    except Exception as e:
        print(f"FAIL  Round-trip test failed: {e}")
        conn.rollback()
        cursor.close()
        return False


def main():
    print("=" * 60)
    print("Lazarus Cloud SQL Connection Test")
    print("=" * 60)
    print()

    # Test 1: Connection
    conn = test_connection()
    if not conn:
        print("\nABORT — cannot proceed without a database connection")
        sys.exit(1)

    print()

    # Test 2: Schema
    tables_ok = test_tables(conn)
    print()

    # Test 3: Epoch gating
    epoch_ok = test_epoch_gating(conn)
    print()

    # Test 4: Round-trip
    rt_ok = test_round_trip(conn)
    print()

    # Summary
    print("=" * 60)
    passed = sum([True, tables_ok, epoch_ok, rt_ok])
    total = 4
    if passed == total:
        print(f"ALL {total} TESTS PASSED — Cloud SQL is ready")
        sys.exit(0)
    else:
        print(f"{passed}/{total} tests passed — see failures above")
        sys.exit(1)


if __name__ == "__main__":
    main(