import sqlite3
from pathlib import Path

from src.engine.startup_config import apply_startup_config_overrides


class _Logger:
    def __init__(self):
        self.info_messages = []
        self.warning_messages = []

    def info(self, message):
        self.info_messages.append(message)

    def warning(self, message):
        self.warning_messages.append(message)


def _build_db(path: Path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE bot_config (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE dynamic_config (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO bot_config (key, value) VALUES
            ('min_hourly_vol', '250'),
            ('max_positions', '4'),
            ('ignored_key', '999');
        INSERT INTO dynamic_config (key, value) VALUES
            ('filter_regime', 'v3.2_lowvol_epoch'),
            ('take_profit', '1.35'),
            ('min_chg_pct', 'not-a-number');
        """
    )
    conn.commit()
    conn.close()


def test_apply_startup_overrides_coerces_types_and_ignores_unknown_keys(tmp_path):
    db_path = tmp_path / "startup.db"
    _build_db(db_path)
    logger = _Logger()
    cfg = {
        "min_hourly_vol": 400,
        "max_positions": 2,
        "filter_regime": "unknown",
        "take_profit": 1.25,
        "min_chg_pct": 10.0,
    }

    apply_startup_config_overrides(str(db_path), cfg, logger)

    assert cfg["min_hourly_vol"] == 250
    assert cfg["max_positions"] == 4
    assert cfg["filter_regime"] == "v3.2_lowvol_epoch"
    assert cfg["take_profit"] == 1.35
    assert cfg["min_chg_pct"] == 10.0
    assert any("min_hourly_vol=250" in msg for msg in logger.info_messages)
    assert any("parse failed for min_chg_pct" in msg for msg in logger.warning_messages)


def test_apply_startup_overrides_fails_safe_when_db_missing(tmp_path):
    logger = _Logger()
    cfg = {"min_hourly_vol": 400}

    apply_startup_config_overrides(str(tmp_path / "missing.db"), cfg, logger)

    assert cfg["min_hourly_vol"] == 400
    assert any("override load failed" in msg or "no such table" in msg for msg in logger.warning_messages)
