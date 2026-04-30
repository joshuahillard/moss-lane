#!/usr/bin/env python3
"""
Solana Wallet Generation Module for Lazarus Trading Bot — BURNERS ONLY

Generates and manages the 5 execution wallets (burners) for the Lazarus bot.

ADR-006 (deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md): the tax vault
keypair is NOT generated here and never written to the server `.env`. Vault
keypair generation is operator-side only — see src/finance/vault_keygen.py.
This module's `save_wallets_to_env` rejects any TAX_VAULT_KEY entry as a
defense-in-depth check.

Uses solders library for keypair generation and base58 encoding for private
key storage.

3-Layer Config Hierarchy:
1. Code defaults: WALLET_COUNT=5, allocation percentages
2. DB bot_config: runtime overrides from database (schema reference provided)
3. dynamic_config: future learning engine adjustments (placeholder)

Author: Lazarus Team
Date: 2026-03-31 (split into burners-only path 2026-04-29)
"""

import os
import sys
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

try:
    from solders.keypair import Keypair
    from solders.pubkey import Pubkey
except ImportError:
    print("ERROR: solders library not found. Install with: pip install solders")
    sys.exit(1)

try:
    import base58
except ImportError:
    print("ERROR: base58 library not found. Install with: pip install base58")
    sys.exit(1)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# CODE LAYER 1: DEFAULTS
# ============================================================================

WALLET_COUNT = 5
ALLOCATION_PERCENTAGES = {
    "EXEC_WALLET_1": 0.20,
    "EXEC_WALLET_2": 0.20,
    "EXEC_WALLET_3": 0.20,
    "EXEC_WALLET_4": 0.20,
    "EXEC_WALLET_5": 0.20,
}

ENV_FILE_PATH = "/home/solbot/lazarus/.env"


# ============================================================================
# EnvLoader: imported from src/utils/env_loader.py
# ============================================================================
# Custom .env handler lives in src/utils/env_loader.py (CLAUDE.md rule 3).
# Dual-import to support both deployed (flat) and repo-test (qualified) paths.

try:
    from env_loader import EnvLoader
except ImportError:
    from src.utils.env_loader import EnvLoader


# ============================================================================
# DATA CLASSES
# ============================================================================

@dataclass
class WalletConfig:
    """Configuration for a single wallet."""
    name: str
    pubkey: str
    private_key_base58: str
    env_var_name: str
    allocation_pct: float


@dataclass
class WalletSet:
    """Complete set of execution (burner) wallets. ADR-006: tax vault not included."""
    execution_wallets: List[WalletConfig]
    generated_at: str


# ============================================================================
# LAYER 2: DATABASE SCHEMA REFERENCE (not created here - for deployment docs)
# ============================================================================

"""
DATABASE SCHEMA REFERENCE - bot_config table
==============================================
This schema exists in lazarus.db and can override code defaults at runtime.

CREATE TABLE IF NOT EXISTS bot_config (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    config_key TEXT NOT NULL UNIQUE,
    config_value TEXT NOT NULL,
    config_type TEXT,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

WALLET-SPECIFIC ROWS:
- config_key='WALLET_COUNT', config_value='5', config_type='int'
- config_key='EXEC_WALLET_1_ALLOCATION', config_value='0.20', config_type='float'
- config_key='EXEC_WALLET_2_ALLOCATION', config_value='0.20', config_type='float'
- ... (WALLET_3 through WALLET_5)

Runtime flow:
1. Load code defaults (WALLET_COUNT=5, allocations)
2. Query bot_config for overrides
3. Merge overrides on top of defaults
4. Use final config for wallet operations

EXAMPLE UPDATE (SSH):
  sqlite3 /home/solbot/lazarus/lazarus.db <<'EOF'
  INSERT OR REPLACE INTO bot_config
  (config_key, config_value, config_type, description)
  VALUES
  ('WALLET_COUNT', '5', 'int', 'Number of execution wallets'),
  ('EXEC_WALLET_1_ALLOCATION', '0.25', 'float', 'Execution wallet 1 allocation %');
  EOF
"""


# ============================================================================
# LAYER 3: DYNAMIC_CONFIG PLACEHOLDER
# ============================================================================

class DynamicConfig:
    """
    Placeholder for future learning engine adjustments to wallet allocations.
    Will integrate with ML pipeline to adjust trading weights based on historical performance.
    """

    @staticmethod
    def get_learning_adjustments() -> Dict[str, float]:
        """
        Placeholder for ML-based allocation adjustments.

        Returns:
            Dict of wallet_name -> adjustment_multiplier (e.g., 1.1 = +10% allocation)
        """
        # TODO: Integrate with learning engine
        return {}


# ============================================================================
# WALLET GENERATION FUNCTIONS
# ============================================================================

def generate_keypair() -> Tuple[str, str]:
    """
    Generate a Solana keypair using solders library.

    Returns:
        Tuple of (public_key_address, private_key_base58)
    """
    kp = Keypair()
    pubkey_str = str(kp.pubkey())
    privkey_bytes = bytes(kp)
    privkey_base58 = base58.b58encode(privkey_bytes).decode('utf-8')
    return pubkey_str, privkey_base58


def generate_wallets(wallet_count: int = WALLET_COUNT) -> WalletSet:
    """
    Generate execution (burner) wallets only.

    ADR-006: tax vault keypair generation lives in src/finance/vault_keygen.py
    and runs operator-side, not on the trading server.

    Args:
        wallet_count: Number of execution wallets to generate (default: 5)

    Returns:
        WalletSet object containing only execution wallets
    """
    logger.info(f"Generating {wallet_count} execution wallets (burners only)...")

    execution_wallets = []
    for i in range(1, wallet_count + 1):
        pubkey, privkey_b58 = generate_keypair()
        env_var_name = f"EXEC_WALLET_{i}_KEY"
        alloc_pct = ALLOCATION_PERCENTAGES.get(f"EXEC_WALLET_{i}", 0.0)

        wallet = WalletConfig(
            name=f"EXEC_WALLET_{i}",
            pubkey=pubkey,
            private_key_base58=privkey_b58,
            env_var_name=env_var_name,
            allocation_pct=alloc_pct
        )
        execution_wallets.append(wallet)
        logger.info(f"  Generated EXEC_WALLET_{i}: {pubkey[:8]}...")

    from datetime import datetime
    wallet_set = WalletSet(
        execution_wallets=execution_wallets,
        generated_at=datetime.utcnow().isoformat()
    )

    logger.info(f"Successfully generated {wallet_count} execution wallets")
    return wallet_set


_ADR006_VAULT_KEY_ERROR = (
    "ADR-006 violation: TAX_VAULT_KEY must not be written to server .env. "
    "Vault private key is operator-controlled, off-server. "
    "See deliverables/ADR_Multi_Wallet_Topology_2026-04-29.md."
)


def _assert_no_vault_key_in_env_updates(env_updates: Dict[str, str]) -> None:
    """
    Defense-in-depth guard: refuse to write TAX_VAULT_KEY to server .env.

    Case-insensitive — TAX_VAULT_KEY, Tax_Vault_Key, tax_vault_key all rejected.

    Raises:
        ValueError: if env_updates contains any TAX_VAULT_KEY variant.
    """
    for key in env_updates:
        if key.upper() == "TAX_VAULT_KEY":
            raise ValueError(_ADR006_VAULT_KEY_ERROR)


def save_wallets_to_env(wallet_set: WalletSet, env_path: str = ENV_FILE_PATH) -> None:
    """
    Save burner wallet private keys to .env file using EnvLoader.

    ADR-006: refuses to write TAX_VAULT_KEY. The vault private key never
    touches the server `.env`; only TAX_VAULT_ADDRESS (the public address)
    is provisioned to the trading server, by the operator, after running
    src/finance/vault_keygen.py off-server.

    Args:
        wallet_set: WalletSet object with execution wallets only
        env_path: Path to .env file

    Raises:
        ValueError: if any key in the resolved env_updates dict is
            TAX_VAULT_KEY (case-insensitive).
    """
    env_updates: Dict[str, str] = {}

    for wallet in wallet_set.execution_wallets:
        env_updates[wallet.env_var_name] = wallet.private_key_base58

    _assert_no_vault_key_in_env_updates(env_updates)

    EnvLoader.write(env_path, env_updates, backup=True)
    logger.info(f"Saved {len(env_updates)} private keys to {env_path}")


def load_wallets_from_env(env_path: str = ENV_FILE_PATH) -> Dict[str, str]:
    """
    Load existing burner wallet private keys from .env file.

    ADR-006: only EXEC_WALLET_*_KEY entries are loaded. TAX_VAULT_KEY
    is forbidden on the server; the startup assertion in
    src/data/data_integrity.py::assert_vault_topology fails closed
    if it is present.

    Args:
        env_path: Path to .env file

    Returns:
        Dictionary mapping env_var_name -> private_key_base58 (burners only)
    """
    env_vars = EnvLoader.load(env_path)

    wallet_keys: Dict[str, str] = {}
    for i in range(1, WALLET_COUNT + 1):
        key_name = f"EXEC_WALLET_{i}_KEY"
        if key_name in env_vars:
            wallet_keys[key_name] = env_vars[key_name]

    logger.info(f"Loaded {len(wallet_keys)} private keys from {env_path}")
    return wallet_keys


# ============================================================================
# VERIFICATION FUNCTIONS
# ============================================================================

def verify_wallet_validity(private_key_base58: str, expected_pubkey: Optional[str] = None) -> bool:
    """
    Verify that a private key is valid and can derive a public key.

    Args:
        private_key_base58: Base58-encoded private key
        expected_pubkey: Optional expected public key to verify against

    Returns:
        True if valid, False otherwise
    """
    try:
        privkey_bytes = base58.b58decode(private_key_base58)
        kp = Keypair.from_bytes(privkey_bytes)
        pubkey_str = str(kp.pubkey())

        if expected_pubkey and pubkey_str != expected_pubkey:
            logger.warning(f"Public key mismatch: got {pubkey_str}, expected {expected_pubkey}")
            return False

        return True
    except Exception as e:
        logger.error(f"Wallet verification failed: {e}")
        return False


def verify_all_wallets(wallet_set: WalletSet) -> bool:
    """
    Verify that all wallets in a set are valid.

    Args:
        wallet_set: WalletSet object

    Returns:
        True if all wallets are valid, False otherwise
    """
    logger.info("Verifying all wallets...")

    all_valid = True
    for wallet in wallet_set.execution_wallets:
        if not verify_wallet_validity(wallet.private_key_base58, wallet.pubkey):
            logger.error(f"Verification failed for {wallet.name}")
            all_valid = False
        else:
            logger.info(f"  ✓ {wallet.name} verified")

    return all_valid


def verify_env_wallets(env_path: str = ENV_FILE_PATH) -> bool:
    """
    Verify all wallets currently stored in .env file.

    Args:
        env_path: Path to .env file

    Returns:
        True if all wallets are valid, False otherwise
    """
    logger.info(f"Verifying wallets from {env_path}...")

    env_vars = EnvLoader.load(env_path)
    all_valid = True

    for i in range(1, WALLET_COUNT + 1):
        key_name = f"EXEC_WALLET_{i}_KEY"
        if key_name not in env_vars:
            logger.warning(f"Missing {key_name} in .env")
            all_valid = False
            continue

        if not verify_wallet_validity(env_vars[key_name]):
            logger.error(f"Verification failed for {key_name}")
            all_valid = False
        else:
            logger.info(f"  ✓ {key_name} verified")

    return all_valid


# ============================================================================
# PUBLIC KEY LOGGING (NEVER LOG PRIVATE KEYS)
# ============================================================================

def log_wallet_summary(wallet_set: WalletSet) -> None:
    """
    Log a summary of all wallet public keys (NEVER private keys).

    Args:
        wallet_set: WalletSet object
    """
    logger.info("=" * 80)
    logger.info("WALLET GENERATION SUMMARY (PUBLIC KEYS ONLY)")
    logger.info("=" * 80)

    total_allocation = 0.0
    for wallet in wallet_set.execution_wallets:
        logger.info(f"{wallet.name:20} | {wallet.pubkey} | Allocation: {wallet.allocation_pct:.1%}")
        total_allocation += wallet.allocation_pct

    logger.info("=" * 80)
    logger.info(f"Total Trading Allocation: {total_allocation:.1%}")
    logger.info(f"Generated At: {wallet_set.generated_at}")
    logger.info("=" * 80)
    logger.info("WARNING: Private keys have been stored in .env file - KEEP SECURE")
    logger.info("=" * 80)


# ============================================================================
# INTEGRATION FUNCTIONS (for lazarus.py engine)
# ============================================================================

def get_wallet_pubkey(wallet_name: str, env_path: str = ENV_FILE_PATH) -> Optional[str]:
    """
    Get the public key for a wallet by deriving it from the stored private key.
    Used by lazarus.py engine.

    Args:
        wallet_name: Name of wallet (e.g., 'EXEC_WALLET_1')
        env_path: Path to .env file

    Returns:
        Public key address or None if wallet not found/invalid
    """
    env_vars = EnvLoader.load(env_path)
    key_var = f"{wallet_name}_KEY"

    if key_var not in env_vars:
        logger.error(f"Wallet {wallet_name} not found in {env_path}")
        return None

    try:
        privkey_bytes = base58.b58decode(env_vars[key_var])
        kp = Keypair.from_bytes(privkey_bytes)
        return str(kp.pubkey())
    except Exception as e:
        logger.error(f"Failed to derive public key for {wallet_name}: {e}")
        return None


def get_wallet_keypair(wallet_name: str, env_path: str = ENV_FILE_PATH) -> Optional[Keypair]:
    """
    Get the full Keypair object for a wallet.
    Used by lazarus.py engine for transaction signing.

    Args:
        wallet_name: Name of wallet (e.g., 'EXEC_WALLET_1')
        env_path: Path to .env file

    Returns:
        Keypair object or None if wallet not found/invalid
    """
    env_vars = EnvLoader.load(env_path)
    key_var = f"{wallet_name}_KEY"

    if key_var not in env_vars:
        logger.error(f"Wallet {wallet_name} not found in {env_path}")
        return None

    try:
        privkey_bytes = base58.b58decode(env_vars[key_var])
        return Keypair.from_bytes(privkey_bytes)
    except Exception as e:
        logger.error(f"Failed to load keypair for {wallet_name}: {e}")
        return None


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """
    Main entry point for standalone wallet generation.
    Generates new wallets and saves to .env file.
    """
    logger.info("Lazarus Phase 2 Multi-Wallet Dispatcher - Generation Module")
    logger.info(f"Target .env: {ENV_FILE_PATH}")

    # Generate wallets
    wallet_set = generate_wallets(wallet_count=WALLET_COUNT)

    # Verify all wallets are valid
    if not verify_all_wallets(wallet_set):
        logger.error("Wallet verification failed!")
        sys.exit(1)

    # Save to .env file
    save_wallets_to_env(wallet_set, env_path=ENV_FILE_PATH)

    # Log summary (public keys only)
    log_wallet_summary(wallet_set)

    # Final verification from .env
    if not verify_env_wallets(env_path=ENV_FILE_PATH):
        logger.error("Final verification of saved wallets failed!")
        sys.exit(1)

    logger.info("All wallets generated, verified, and saved successfully!")


if __name__ == "__main__":
    main()
