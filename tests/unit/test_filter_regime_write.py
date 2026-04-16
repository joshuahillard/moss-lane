import importlib
import sqlite3
import sys
from pathlib import Path


def _load_db_adapter(monkeypatch, db_path: Path):
    monkeypatch.setenv("DB_BACKEND", "sqlite")
    monkeypatch.setenv("LAZARUS_DB_PATH", str(db_path))
    sys.modules.pop("src.data.db_adapter", None)
    import src.data.db_adapter as db_adapter

    return importlib.reload(db_adapter)


def test_record_trade_persists_explicit_filter_regime(tmp_path, monkeypatch):
    db_path = tmp_path / "filter_regime.db"
    db_adapter = _load_db_adapter(monkeypatch, db_path)
    db = db_adapter.DatabaseAdapter()

    db.record_trade(
        sym="TEST",
        addr="abc123",
        entry=1.0,
        exit_p=1.1,
        pnl_usd=5.0,
        pnl_pct=5.0,
        sol_spent=10.0,
        paper=True,
        source="unit",
        wallet="paper-wallet",
        filter_regime="v3.2_lowvol_epoch",
    )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT filter_regime FROM trades ORDER BY id DESC LIMIT 1").fetchone()
        migration = conn.execute("SELECT migration_id FROM schema_migrations").fetchone()
    finally:
        conn.close()
        db.conn.close()

    assert row[0] == "v3.2_lowvol_epoch"
    assert migration[0] == "0001_add_filter_regime.sql"


def test_record_trade_defaults_filter_regime_to_unknown(tmp_path, monkeypatch):
    db_path = tmp_path / "filter_regime_default.db"
    db_adapter = _load_db_adapter(monkeypatch, db_path)
    db = db_adapter.DatabaseAdapter()

    db.record_trade(
        sym="TEST",
        addr="abc123",
        entry=1.0,
        exit_p=0.9,
        pnl_usd=-2.0,
        pnl_pct=-2.0,
        sol_spent=10.0,
        paper=True,
        source="unit",
        wallet="paper-wallet",
    )

    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT filter_regime FROM trades ORDER BY id DESC LIMIT 1").fetchone()
    finally:
        conn.close()
        db.conn.close()

    assert row[0] == "unknown"
