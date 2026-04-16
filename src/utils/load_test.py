#!/usr/bin/env python3
"""
Lazarus Load Test — measures performance under high-frequency scanning.

PURPOSE:
  Simulates 100 rapid scan cycles against both SQLite and PostgreSQL backends.
  Measures latency, memory usage, DB write throughput, and error rate.
  Generates a comparison report.

WHAT IT SIMULATES:
  Each "cycle" performs the operations that happen in a real scan cycle:
  1. Write a trade record (INSERT into trades + daily_pnl)
  2. Record a signal result (INSERT/UPDATE signal_performance)
  3. Set a cooldown (INSERT/REPLACE into cooldowns)
  4. Check cooldown (SELECT from cooldowns)
  5. Get daily PnL (SELECT from daily_pnl)
  6. Get signal weights (SELECT from signal_performance)
  7. Clean expired cooldowns (DELETE from cooldowns)

  This is NOT a network load test — it measures database I/O throughput,
  which is the bottleneck in a trading bot that writes every cycle.

USAGE:
  SQLite only (no Postgres configured):
    python load_test.py

  Both backends (requires DATABASE_URL):
    export DATABASE_URL="postgresql://..."
    python load_test.py --include-postgres

  Custom cycle count:
    python load_test.py --cycles 200

OUTPUT:
  Prints a formatted comparison table and saves results to load_test_report.json
"""

import argparse
import json
import os
import random
import sqlite3
import sys
import time
import string
from typing import Dict, List

# ── Test data generators ─────────────────────────────────────────────────────

SOURCES = ["dexscreener_momentum", "smart_money", "combined"]
EXIT_REASONS = ["take_profit", "stop_loss", "trailing_stop", "hard_floor", "timeout", "sniper_timeout"]
TOKENS = [f"{''.join(random.choices(string.ascii_letters + string.digits, k=44))}" for _ in range(50)]
SYMBOLS = [f"TEST{i}" for i in range(50)]


def random_trade_kwargs() -> Dict:
    """Generate random but realistic trade data."""
    idx = random.randint(0, 49)
    pnl_pct = random.uniform(-15.0, 30.0)
    sol_spent = random.uniform(0.01, 0.5)
    pnl_usd = sol_spent * (pnl_pct / 100) * random.uniform(80, 140)

    return {
        "sym": SYMBOLS[idx],
        "addr": TOKENS[idx],
        "entry": random.uniform(0.0000001, 0.001),
        "exit_p": random.uniform(0.0000001, 0.001),
        "pnl_usd": pnl_usd,
        "pnl_pct": pnl_pct,
        "sol_spent": sol_spent,
        "paper": random.choice([True, False]),
        "source": random.choice(SOURCES),
        "wallet": "8ioMoqLiscTBqKJAYmVpNqy3iCSxXHYcbFfgBsiYJMdm",
        "exit_reason": random.choice(EXIT_REASONS),
        "score": random.uniform(1000, 500_000_000),
        "hourly": random.uniform(500, 5_000_000),
        "chg_pct": random.uniform(5, 180),
        "mc": random.uniform(10_000, 10_000_000),
        "liq": random.uniform(50_000, 500_000),
    }


# ── Memory measurement ───────────────────────────────────────────────────────

def get_memory_mb() -> float:
    """Get current process memory usage in MB."""
    try:
        import psutil
        return psutil.Process(os.getpid()).memory_info().rss / (1024 * 1024)
    except ImportError:
        # Fallback: read from /proc on Linux, estimate on Windows
        try:
            with open(f"/proc/{os.getpid()}/status") as f:
                for line in f:
                    if line.startswith("VmRSS:"):
                        return int(line.split()[1]) / 1024
        except (FileNotFoundError, ValueError):
            return 0.0
    return 0.0


# ── Run load test against a backend ──────────────────────────────────────────

def run_load_test(backend: str, cycles: int, database_url: str = "") -> Dict:
    """
    Run N cycles of simulated scanner operations against a database backend.

    Returns a dict with timing, throughput, memory, and error metrics.
    """
    # Import adapter
    os.environ["DB_BACKEND"] = backend
    if backend == "postgres" and database_url:
        os.environ["DATABASE_URL"] = database_url

    # Use a temp SQLite path for testing (don't touch the real DB)
    if backend == "sqlite":
        test_db_path = os.path.join(os.path.dirname(__file__) or ".", "load_test_temp.db")
        os.environ["LAZARUS_DB_PATH"] = test_db_path

    # Import fresh each time to pick up env changes
    # We use db_adapter directly instead of re-importing
    from db_adapter import DatabaseAdapter
    db = DatabaseAdapter()

    cycle_times: List[float] = []
    write_times: List[float] = []
    read_times: List[float] = []
    errors = 0
    mem_start = get_memory_mb()

    print(f"\n  Running {cycles} cycles against {backend}...")

    total_start = time.time()

    for i in range(cycles):
        cycle_start = time.time()

        try:
            # ── Writes ───────────────────────────────────────────────────
            w_start = time.time()

            # 1. Record a trade
            kwargs = random_trade_kwargs()
            db.record_trade(**kwargs)

            # 2. Record signal result
            db.record_signal_result(
                source=random.choice(SOURCES),
                won=random.random() > 0.7,
                pnl=random.uniform(-5.0, 15.0),
            )

            # 3. Set a cooldown
            idx = random.randint(0, 49)
            db.set_cooldown(TOKENS[idx], SYMBOLS[idx], random.randint(60, 7200))

            w_elapsed = time.time() - w_start
            write_times.append(w_elapsed)

            # ── Reads ────────────────────────────────────────────────────
            r_start = time.time()

            # 4. Check cooldown
            db.is_on_cooldown(TOKENS[random.randint(0, 49)])

            # 5. Get daily PnL
            db.get_daily_pnl()

            # 6. Get signal weights
            db.get_signal_weights()

            # 7. Clean expired cooldowns (every 10th cycle)
            if i % 10 == 0:
                db.clean_expired_cooldowns()

            r_elapsed = time.time() - r_start
            read_times.append(r_elapsed)

        except Exception as e:
            errors += 1
            if errors <= 3:
                print(f"    Error on cycle {i}: {e}")

        cycle_elapsed = time.time() - cycle_start
        cycle_times.append(cycle_elapsed)

        # Progress indicator
        if (i + 1) % 25 == 0:
            avg = sum(cycle_times) / len(cycle_times) * 1000
            print(f"    Cycle {i+1}/{cycles} — avg {avg:.1f}ms/cycle")

    total_elapsed = time.time() - total_start
    mem_end = get_memory_mb()

    # Cleanup
    db.close()
    if backend == "sqlite":
        try:
            os.remove(test_db_path)
        except OSError:
            pass

    # Compile results
    results = {
        "backend": backend,
        "cycles": cycles,
        "total_seconds": round(total_elapsed, 3),
        "avg_cycle_ms": round(sum(cycle_times) / len(cycle_times) * 1000, 2),
        "min_cycle_ms": round(min(cycle_times) * 1000, 2),
        "max_cycle_ms": round(max(cycle_times) * 1000, 2),
        "p50_cycle_ms": round(sorted(cycle_times)[len(cycle_times) // 2] * 1000, 2),
        "p95_cycle_ms": round(sorted(cycle_times)[int(len(cycle_times) * 0.95)] * 1000, 2),
        "p99_cycle_ms": round(sorted(cycle_times)[int(len(cycle_times) * 0.99)] * 1000, 2),
        "avg_write_ms": round(sum(write_times) / len(write_times) * 1000, 2) if write_times else 0,
        "avg_read_ms": round(sum(read_times) / len(read_times) * 1000, 2) if read_times else 0,
        "writes_per_sec": round(len(write_times) / total_elapsed, 1),
        "reads_per_sec": round(len(read_times) / total_elapsed, 1),
        "errors": errors,
        "error_rate_pct": round(errors / cycles * 100, 2),
        "memory_start_mb": round(mem_start, 1),
        "memory_end_mb": round(mem_end, 1),
        "memory_delta_mb": round(mem_end - mem_start, 1),
    }

    return results


# ── Report formatting ────────────────────────────────────────────────────────

def print_report(results: List[Dict]):
    """Print a formatted comparison table."""
    print(f"\n{'='*70}")
    print(f"  LAZARUS LOAD TEST REPORT")
    print(f"{'='*70}")

    # Header
    backends = [r["backend"] for r in results]
    header = f"  {'Metric':<30}"
    for b in backends:
        header += f" {b:>15}"
    print(header)
    print(f"  {'-'*30}" + f" {'-'*15}" * len(backends))

    # Rows
    metrics = [
        ("Cycles", "cycles", ""),
        ("Total time", "total_seconds", "s"),
        ("Avg cycle latency", "avg_cycle_ms", "ms"),
        ("Min cycle latency", "min_cycle_ms", "ms"),
        ("Max cycle latency", "max_cycle_ms", "ms"),
        ("P50 latency", "p50_cycle_ms", "ms"),
        ("P95 latency", "p95_cycle_ms", "ms"),
        ("P99 latency", "p99_cycle_ms", "ms"),
        ("Avg write latency", "avg_write_ms", "ms"),
        ("Avg read latency", "avg_read_ms", "ms"),
        ("Write throughput", "writes_per_sec", "/s"),
        ("Read throughput", "reads_per_sec", "/s"),
        ("Errors", "errors", ""),
        ("Error rate", "error_rate_pct", "%"),
        ("Memory start", "memory_start_mb", "MB"),
        ("Memory end", "memory_end_mb", "MB"),
        ("Memory delta", "memory_delta_mb", "MB"),
    ]

    for label, key, unit in metrics:
        row = f"  {label:<30}"
        for r in results:
            val = r.get(key, "N/A")
            if isinstance(val, float):
                row += f" {val:>12.2f}{unit:>3}"
            else:
                row += f" {val:>12}{unit:>3}"
        print(row)

    # Comparison (if multiple backends)
    if len(results) > 1:
        print(f"\n  {'— Comparison —':^70}")
        sqlite_avg = next(r["avg_cycle_ms"] for r in results if r["backend"] == "sqlite")
        pg_avg = next(r["avg_cycle_ms"] for r in results if r["backend"] == "postgres")
        if pg_avg > 0 and sqlite_avg > 0:
            ratio = pg_avg / sqlite_avg
            faster = "SQLite" if ratio > 1 else "Postgres"
            factor = ratio if ratio > 1 else 1 / ratio
            print(f"  {faster} is {factor:.1f}x faster per cycle on average")
            print(f"  (Expected: SQLite is faster for single-node, Postgres")
            print(f"   scales better for multi-instance and concurrent writes)")

    print(f"\n{'='*70}")


def main():
    parser = argparse.ArgumentParser(description="Lazarus database load test")
    parser.add_argument("--cycles", type=int, default=100, help="Number of scan cycles to simulate")
    parser.add_argument("--include-postgres", action="store_true",
                        help="Also test against PostgreSQL (requires DATABASE_URL)")
    parser.add_argument("--output", default="load_test_report.json",
                        help="Path to save JSON report")
    args = parser.parse_args()

    results = []

    # Always test SQLite
    sqlite_results = run_load_test("sqlite", args.cycles)
    results.append(sqlite_results)

    # Optionally test Postgres
    if args.include_postgres:
        database_url = os.environ.get("DATABASE_URL", "")
        if not database_url:
            print("\n  WARNING: DATABASE_URL not set, skipping Postgres test")
        else:
            pg_results = run_load_test("postgres", args.cycles, database_url)
            results.append(pg_results)

    # Print report
    print_report(results)

    # Save JSON
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n  Full report saved to: {args.output}")


if __name__ == "__main__":
    main()
