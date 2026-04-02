#!/usr/bin/env python3
"""
Lazarus Vertex AI — Feature Extraction

PURPOSE:
  Pulls trade history from SQLite or PostgreSQL and builds a training-ready
  dataset for the profitability prediction model.

FEATURES EXTRACTED (all available at ENTRY time, before outcome is known):
  - score:       composite scanner signal strength
  - chg_pct:     1h price change % at entry
  - mc:          market cap at entry
  - liq:         liquidity at entry
  - hourly:      1h volume at entry
  - hour_utc:    hour of day (0-23)
  - day_of_week: day (0=Monday, 6=Sunday)
  - smart_money: whether smart money confirmed the signal (0/1)
  - rug_risk:    encoded as 0 (low) or 1 (high)
  - source_enc:  signal source encoded as integer

TARGET:
  - profitable:  1 if pnl_pct > 0, else 0

USAGE:
  From SQLite:
    python vertex_feature_extract.py --sqlite-path ./lazarus.db --output features.csv

  From PostgreSQL:
    export DATABASE_URL="postgresql://..."
    python vertex_feature_extract.py --backend postgres --output features.csv
"""

import argparse
import csv
import os
import sqlite3
import sys
import logging
from typing import List, Dict, Tuple

log = logging.getLogger("vertex_features")

# Feature columns to extract (must exist in trades table)
FEATURE_QUERY = """
    SELECT
        score, chg_pct, mc, liq, hourly,
        hour_utc, day_of_week, smart_money_confirmed,
        rug_risk, source, pnl_pct
    FROM trades
    WHERE score IS NOT NULL
      AND mc IS NOT NULL
      AND liq IS NOT NULL
      AND pnl_pct IS NOT NULL
"""

# Source encoding — maps signal source strings to integers
SOURCE_MAP = {
    "dexscreener_momentum": 0,
    "smart_money": 1,
    "combined": 2,
}

FEATURE_COLUMNS = [
    "score", "chg_pct", "mc", "liq", "hourly",
    "hour_utc", "day_of_week", "smart_money", "rug_risk_enc", "source_enc",
    "liq_mc_ratio", "vol_liq_ratio", "trading_session",
]

TARGET_COLUMN = "profitable"


def _trading_session(hour_utc: int) -> int:
    """Bin UTC hour into trading sessions.
    0 = Asia (00-07), 1 = Europe (08-13), 2 = US (14-21), 3 = Off-hours (22-23)
    """
    if hour_utc < 8:
        return 0   # Asia
    elif hour_utc < 14:
        return 1   # Europe
    elif hour_utc < 22:
        return 2   # US / overlap
    else:
        return 3   # Off-hours


def encode_row(row: tuple) -> Dict:
    """Convert a raw DB row to a feature dict with encodings."""
    score, chg_pct, mc, liq, hourly, hour_utc, dow, sm_conf, rug_risk, source, pnl_pct = row

    mc_f = float(mc or 0)
    liq_f = float(liq or 0)
    hourly_f = float(hourly or 0)
    hour_i = int(hour_utc or 0)

    return {
        "score": float(score or 0),
        "chg_pct": float(chg_pct or 0),
        "mc": mc_f,
        "liq": liq_f,
        "hourly": hourly_f,
        "hour_utc": hour_i,
        "day_of_week": int(dow or 0),
        "smart_money": int(sm_conf or 0),
        "rug_risk_enc": 1 if rug_risk == "high" else 0,
        "source_enc": SOURCE_MAP.get(source, 0),
        # Derived features — sharper edges for the model
        "liq_mc_ratio": liq_f / mc_f if mc_f > 0 else 0,       # rug pull signal
        "vol_liq_ratio": hourly_f / liq_f if liq_f > 0 else 0,  # demand pressure
        "trading_session": _trading_session(hour_i),              # Asia/Europe/US/Off
        "profitable": 1 if (pnl_pct or 0) > 0 else 0,
    }


def extract_from_sqlite(db_path: str) -> List[Dict]:
    """Extract features from SQLite database."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(FEATURE_QUERY).fetchall()
    conn.close()
    return [encode_row(r) for r in rows]


def extract_from_postgres(database_url: str) -> List[Dict]:
    """Extract features from PostgreSQL database."""
    try:
        import psycopg2
    except ImportError:
        log.error("psycopg2 not installed. Run: pip install psycopg2-binary")
        sys.exit(1)
    conn = psycopg2.connect(database_url)
    cursor = conn.cursor()
    cursor.execute(FEATURE_QUERY)
    rows = cursor.fetchall()
    cursor.close()
    conn.close()
    return [encode_row(r) for r in rows]


def write_csv(features: List[Dict], output_path: str):
    """Write feature dicts to CSV."""
    columns = FEATURE_COLUMNS + [TARGET_COLUMN]
    with open(output_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(features)


def print_stats(features: List[Dict]):
    """Print dataset statistics."""
    total = len(features)
    wins = sum(1 for f in features if f["profitable"] == 1)
    losses = total - wins

    print(f"\nDataset statistics:")
    print(f"  Total trades:  {total}")
    print(f"  Profitable:    {wins} ({wins/total*100:.1f}%)")
    print(f"  Unprofitable:  {losses} ({losses/total*100:.1f}%)")
    print(f"  Features:      {len(FEATURE_COLUMNS)}")

    # Feature ranges
    print(f"\nFeature ranges:")
    for col in FEATURE_COLUMNS:
        vals = [f[col] for f in features]
        print(f"  {col:.<20} min={min(vals):>12.2f}  max={max(vals):>12.2f}  "
              f"mean={sum(vals)/len(vals):>12.2f}")


def main():
    parser = argparse.ArgumentParser(description="Extract training features from Lazarus trade history")
    parser.add_argument("--backend", choices=["sqlite", "postgres"], default="sqlite")
    parser.add_argument("--sqlite-path", default="/home/solbot/lazarus/logs/lazarus.db")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL", ""))
    parser.add_argument("--output", default="features.csv")
    args = parser.parse_args()

    if args.backend == "postgres":
        if not args.database_url:
            print("ERROR: Set DATABASE_URL or pass --database-url")
            sys.exit(1)
        features = extract_from_postgres(args.database_url)
    else:
        if not os.path.exists(args.sqlite_path):
            print(f"ERROR: SQLite file not found: {args.sqlite_path}")
            sys.exit(1)
        features = extract_from_sqlite(args.sqlite_path)

    if not features:
        print("ERROR: No valid trades found for feature extraction")
        sys.exit(1)

    print_stats(features)
    write_csv(features, args.output)
    print(f"\nFeatures written to: {args.output}")


if __name__ == "__main__":
    main()
