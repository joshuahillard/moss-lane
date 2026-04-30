"""
EnvLoader — Custom .env Handler (NEVER python-dotenv)

Extracted from src/finance/wallet_generator.py (Phase 3 Slice 3, 2026-04-29)
to enable use without dragging in the wallet-generation surface area.

Public API (preserved verbatim from the wallet_generator.py original):
    EnvLoader.load(env_path: str) -> Dict[str, str]
    EnvLoader.write(env_path: str, updates: Dict[str, str], backup: bool = True) -> None

Per CLAUDE.md rule 3: this is the canonical custom .env loader. python-dotenv
breaks on certain quote formats; this implementation handles single, double,
and unquoted values consistently.

Note on duplication: src/engine/lazarus.py and src/engine/fort_v2_clean.py
each define their own `class EnvLoader` for historical reasons. Those copies
are left untouched in this slice (CLAUDE.md rule 1: never overwrite lazarus.py
wholesale). Future cleanup tracked in
deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md follow-ups.
"""

from __future__ import annotations

import logging
import os
from typing import Dict

logger = logging.getLogger(__name__)


class EnvLoader:
    """
    Custom environment loader that safely handles quoted values in .env files.
    Avoids python-dotenv which breaks on certain quote formats.
    """

    @staticmethod
    def load(env_path: str) -> Dict[str, str]:
        """
        Load all key=value pairs from .env file into a dict.
        Handles quoted values correctly.

        Args:
            env_path: Path to .env file

        Returns:
            Dictionary of environment variables
        """
        env_vars: Dict[str, str] = {}
        if not os.path.exists(env_path):
            logger.warning(f"ENV file not found: {env_path}")
            return env_vars

        try:
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # Skip comments and empty lines
                    if not line or line.startswith('#'):
                        continue

                    if '=' not in line:
                        continue

                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Remove surrounding quotes if present
                    if (value.startswith('"') and value.endswith('"')) or \
                       (value.startswith("'") and value.endswith("'")):
                        value = value[1:-1]

                    env_vars[key] = value

            logger.info(f"Loaded {len(env_vars)} variables from {env_path}")
        except Exception as e:
            logger.error(f"Failed to load .env file: {e}")
            raise

        return env_vars

    @staticmethod
    def write(env_path: str, updates: Dict[str, str], backup: bool = True) -> None:
        """
        Append new key=value pairs to .env file (or update existing keys).
        Creates file if it doesn't exist. Optionally backs up original.

        Args:
            env_path: Path to .env file
            updates: Dictionary of key=value pairs to add/update
            backup: If True, create backup of original .env before writing
        """
        # Backup existing file if it exists
        if backup and os.path.exists(env_path):
            backup_path = f"{env_path}.backup"
            try:
                with open(env_path, 'r') as src:
                    with open(backup_path, 'w') as dst:
                        dst.write(src.read())
                logger.info(f"Backed up .env to {backup_path}")
            except Exception as e:
                logger.error(f"Failed to backup .env: {e}")
                raise

        # Load existing content
        existing: Dict[str, str] = {}
        if os.path.exists(env_path):
            existing = EnvLoader.load(env_path)

        # Merge updates
        existing.update(updates)

        # Write all key=value pairs (overwrite file)
        try:
            with open(env_path, 'w') as f:
                for key, value in existing.items():
                    f.write(f"{key}={value}\n")
            logger.info(f"Wrote {len(updates)} new/updated variables to {env_path}")
        except Exception as e:
            logger.error(f"Failed to write .env file: {e}")
            raise
