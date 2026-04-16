"""
Tax Vault Module — 15% Profit Skim for Lazarus Phase 2

On every profitable sell, skims 15% of the PROFIT (not principal) to a
reserve wallet. Accumulates small skims and batches transfers when the
accumulated amount exceeds the minimum threshold (ADR-003).

Architecture:
  TradeExecutor → sell completes → tax_vault.calculate_skim()
  If accumulated_skim >= min_skim_sol → execute transfer to TAX_VAULT_KEY

Key Rules:
  - 15% of PROFIT only. Never touch principal.
  - Accumulate small amounts (< min_skim_sol) for batch transfer later
  - Transfer failure → retry once, then log for manual review
  - Tax vault is receive-only from executors (no outbound except manual)

Constraints:
  [TAX ACCURACY]  15% of profit, never principal
  [PRAGMATISM]    aiohttp for RPC transfers (internal Solana calls)
  [FAIL-CLOSED]   Transfer failure logged, never blocks trade flow
"""

import logging
import time
import sqlite3
from dataclasses import dataclass
from typing import Optional, Dict

log = logging.getLogger("tax_vault")


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class TaxVaultConfig:
    """Tax vault configuration (3-layer compatible)."""
    skim_pct: float = 0.15               # 15% of profit
    min_skim_sol: float = 0.005          # minimum transfer threshold (ADR-003: 0.1 for mainnet)
    tax_vault_address: str = ""           # TAX_VAULT public key (from .env)
    max_retry: int = 1                    # retry once on transfer failure
    enabled: bool = True                  # kill switch

    @classmethod
    def from_layers(cls, code_defaults: Optional[Dict] = None,
                   db_config: Optional[Dict] = None,
                   dynamic_config: Optional[Dict] = None) -> 'TaxVaultConfig':
        cfg = cls()
        for layer in (code_defaults, db_config, dynamic_config):
            if layer:
                for k, v in layer.items():
                    if hasattr(cfg, k):
                        setattr(cfg, k, v)
        return cfg


# ============================================================================
# Tax Vault
# ============================================================================

class TaxVault:
    """
    Manages profit skim calculations and accumulated skim balances.

    The vault tracks per-executor accumulated skims. When the accumulated
    amount exceeds min_skim_sol, it returns a transfer instruction. The
    actual RPC transfer is handled by the caller (dispatcher/main loop).

    Usage:
        vault = TaxVault(config, db_path)
        skim = vault.calculate_skim(executor_addr, pnl_sol)
        if skim and skim.transfer_now:
            # Execute SOL transfer: executor_addr → tax_vault_address
            success = await do_transfer(skim.amount_sol, executor_addr, vault_addr)
            vault.record_transfer(executor_addr, skim.amount_sol, success)
    """

    def __init__(self, config: TaxVaultConfig, db_path: str):
        self.config = config
        self.db_path = db_path

        # Per-executor accumulated skim (not yet transferred)
        self._accumulated: Dict[str, float] = {}

        self._init_db()

        log.info(
            f"TaxVault initialized: skim={config.skim_pct*100:.0f}%, "
            f"min_transfer={config.min_skim_sol}SOL, "
            f"vault={config.tax_vault_address[:12]}..."
            if config.tax_vault_address else "TaxVault initialized (no vault address)"
        )

    def _init_db(self):
        """Create tax_vault_ledger table if not exists."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tax_vault_ledger (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    executor_address TEXT NOT NULL,
                    skim_amount_sol REAL NOT NULL,
                    accumulated_before REAL NOT NULL,
                    transfer_attempted INTEGER DEFAULT 0,
                    transfer_success INTEGER DEFAULT 0,
                    tx_signature TEXT,
                    notes TEXT
                )
            """)
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"TaxVault DB init failed: {e}")

    # ────────────────────────────────────────────────────────────────────────
    # Skim Calculation
    # ────────────────────────────────────────────────────────────────────────

    @dataclass
    class SkimResult:
        """Result of a skim calculation."""
        skim_sol: float           # Amount skimmed from this trade's profit
        accumulated_sol: float    # Total accumulated (including this skim)
        transfer_now: bool        # True if accumulated >= min_skim_sol
        amount_sol: float         # Amount to transfer (= accumulated if transfer_now)
        executor_address: str

    def calculate_skim(self, executor_address: str, pnl_sol: float) -> Optional['TaxVault.SkimResult']:
        """
        Calculate skim for a completed trade.

        Args:
            executor_address: Which executor completed the trade
            pnl_sol: Profit/loss in SOL (positive = profit)

        Returns:
            SkimResult if profitable trade, None if loss or disabled
        """
        if not self.config.enabled:
            return None

        if not self.config.tax_vault_address:
            log.warning("TaxVault: no vault address configured — skipping skim")
            return None

        # Only skim on profitable trades
        if pnl_sol <= 0:
            return None

        # Calculate 15% of PROFIT (not principal)
        skim = pnl_sol * self.config.skim_pct

        # Accumulate
        prev = self._accumulated.get(executor_address, 0.0)
        new_total = prev + skim
        self._accumulated[executor_address] = new_total

        # Should we transfer now?
        transfer_now = new_total >= self.config.min_skim_sol

        log.info(
            f"TAX SKIM: {executor_address[:8]}... | "
            f"profit={pnl_sol:.6f}SOL | skim={skim:.6f}SOL | "
            f"accumulated={new_total:.6f}SOL | "
            f"{'TRANSFER' if transfer_now else 'accumulating'}"
        )

        return TaxVault.SkimResult(
            skim_sol=skim,
            accumulated_sol=new_total,
            transfer_now=transfer_now,
            amount_sol=new_total if transfer_now else 0.0,
            executor_address=executor_address,
        )

    def record_transfer(self, executor_address: str, amount_sol: float,
                        success: bool, tx_signature: Optional[str] = None):
        """
        Record a skim transfer attempt in the ledger.

        Args:
            executor_address: Source executor
            amount_sol: Amount transferred
            success: Whether the transfer succeeded
            tx_signature: Transaction signature if successful
        """
        accumulated_before = self._accumulated.get(executor_address, 0.0)

        try:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                """INSERT INTO tax_vault_ledger
                   (timestamp, executor_address, skim_amount_sol,
                    accumulated_before, transfer_attempted, transfer_success,
                    tx_signature, notes)
                   VALUES (?, ?, ?, ?, 1, ?, ?, ?)""",
                (
                    time.time(),
                    executor_address,
                    amount_sol,
                    accumulated_before,
                    1 if success else 0,
                    tx_signature or "",
                    "auto_skim" if success else "transfer_failed",
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            log.error(f"TaxVault ledger write failed: {e}")

        if success:
            # Reset accumulated for this executor
            self._accumulated[executor_address] = 0.0
            log.info(
                f"TAX TRANSFER OK: {executor_address[:8]}... → vault | "
                f"{amount_sol:.6f}SOL | tx={tx_signature[:16] if tx_signature else 'n/a'}..."
            )
        else:
            # Keep accumulated — will retry next profitable trade
            log.error(
                f"TAX TRANSFER FAILED: {executor_address[:8]}... → vault | "
                f"{amount_sol:.6f}SOL — will retry on next profit"
            )

    # ────────────────────────────────────────────────────────────────────────
    # Status & Monitoring
    # ────────────────────────────────────────────────────────────────────────

    def get_status(self) -> Dict:
        """Return vault status for monitoring."""
        total_accumulated = sum(self._accumulated.values())

        # Query total transferred from DB
        total_transferred = 0.0
        try:
            conn = sqlite3.connect(self.db_path)
            row = conn.execute(
                "SELECT COALESCE(SUM(skim_amount_sol), 0) "
                "FROM tax_vault_ledger WHERE transfer_success = 1"
            ).fetchone()
            total_transferred = row[0] if row else 0.0
            conn.close()
        except Exception:
            pass

        return {
            "enabled": self.config.enabled,
            "skim_pct": self.config.skim_pct,
            "vault_address": self.config.tax_vault_address[:12] + "..." if self.config.tax_vault_address else "NOT SET",
            "pending_accumulated_sol": total_accumulated,
            "total_transferred_sol": total_transferred,
            "per_executor": {
                addr[:12] + "...": amt
                for addr, amt in self._accumulated.items()
                if amt > 0
            },
        }

    def get_accumulated(self, executor_address: str) -> float:
        """Get pending accumulated skim for an executor."""
        return self._accumulated.get(executor_address, 0.0)
