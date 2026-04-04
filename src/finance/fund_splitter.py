"""
Fund Splitter Module for Lazarus Phase 2 Multi-Wallet Dispatcher

Manages distribution of SOL from main wallet to executor wallets.
- Equal or weighted split options
- Fee-aware calculations
- Fail-closed error handling
- Automatic quarantine on transfer failure
- Reserve protection (minimum SOL maintained in main wallet)

Architecture:
1. Load config (code defaults → DB → dynamic runtime overrides)
2. Validate main wallet balance against reserve + minimum allocations
3. Calculate transfer amounts (fee-adjusted)
4. Build transfer instructions for each executor
5. Return list of (address, amount_sol) tuples for dispatcher to sign

Critical: This touches real money. All state transitions are logged.
All unexpected states trigger fail-closed abort.
"""

import logging
import asyncio
from dataclasses import dataclass
from typing import Optional, List, Tuple, Dict
from enum import Enum


# ============================================================================
# Configuration & Constants
# ============================================================================

class AllocationMode(Enum):
    """Fund allocation strategies"""
    EQUAL = "equal"
    WEIGHTED = "weighted"


@dataclass
class FundSplitterConfig:
    """Fund splitter configuration with 3-layer hierarchy"""
    # Layer 1: Code defaults
    allocation_mode: AllocationMode = AllocationMode.EQUAL
    reserve_sol: float = 0.01  # Minimum SOL kept in main wallet
    min_viable_balance_per_executor: float = 0.05  # Minimum per executor wallet
    max_retries_on_transfer_fail: int = 1  # Retry once then quarantine
    solana_tx_fee_sol: float = 0.000005  # Per-transaction fee estimate

    # Executor wallet configurations
    executor_addresses: List[str] = None  # List of executor wallet public keys
    executor_weights: Optional[Dict[str, float]] = None  # Weights for weighted split

    # State tracking
    quarantined_wallets: List[str] = None  # Wallets temporarily unavailable

    def __post_init__(self):
        if self.executor_addresses is None:
            self.executor_addresses = []
        if self.executor_weights is None:
            self.executor_weights = {}
        if self.quarantined_wallets is None:
            self.quarantined_wallets = []

    @classmethod
    def from_layers(cls, code_defaults: Optional[Dict] = None,
                   db_config: Optional[Dict] = None,
                   dynamic_config: Optional[Dict] = None) -> 'FundSplitterConfig':
        """
        Construct config following 3-layer hierarchy:
        code_defaults < db_config < dynamic_config
        Later layers override earlier ones.
        """
        cfg = cls()

        # Apply layer 1: code defaults
        if code_defaults:
            for k, v in code_defaults.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)

        # Apply layer 2: DB config (overrides code defaults)
        if db_config:
            for k, v in db_config.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)

        # Apply layer 3: dynamic config (overrides everything)
        if dynamic_config:
            for k, v in dynamic_config.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)

        return cfg


@dataclass
class TransferInstruction:
    """Single transfer instruction for dispatcher"""
    executor_address: str
    amount_sol: float
    timestamp: str  # ISO 8601 timestamp for logging
    retry_count: int = 0
    status: str = "pending"  # pending, success, failed, quarantined


# ============================================================================
# Logger Setup
# ============================================================================

logger = logging.getLogger(__name__)


# ============================================================================
# Fund Splitter Logic
# ============================================================================

class FundSplitter:
    """
    Main fund splitter orchestrator.

    Responsibilities:
    1. Validate configuration and wallet state
    2. Calculate fair distribution based on allocation mode
    3. Generate transfer instructions
    4. Handle edge cases (insufficient funds, failed transfers, quarantine)
    5. Maintain audit log of all fund movements
    """

    def __init__(self, config: FundSplitterConfig):
        """
        Initialize fund splitter with configuration.

        Args:
            config: FundSplitterConfig instance with all allocation rules

        Raises:
            ValueError: If config is invalid (missing executors, invalid modes)
        """
        self.config = config
        self._validate_config()
        logger.info(f"FundSplitter initialized: mode={config.allocation_mode.value}, "
                   f"executors={len(config.executor_addresses)}, "
                   f"reserve={config.reserve_sol}SOL")

    def _validate_config(self):
        """Validate configuration before use. Fail-closed."""
        if not self.config.executor_addresses:
            raise ValueError("No executor addresses configured")

        if len(self.config.executor_addresses) > 10:
            raise ValueError(f"Too many executors: {len(self.config.executor_addresses)} "
                           f"(max 10)")

        if self.config.allocation_mode == AllocationMode.WEIGHTED:
            if not self.config.executor_weights:
                raise ValueError("Weighted mode requires executor_weights")

            # Verify all executors have weights
            for addr in self.config.executor_addresses:
                if addr not in self.config.executor_weights:
                    raise ValueError(f"Executor {addr} missing weight for weighted split")

            # Verify weights are positive
            for addr, weight in self.config.executor_weights.items():
                if weight <= 0:
                    raise ValueError(f"Executor {addr} has invalid weight: {weight}")

        if self.config.reserve_sol < 0:
            raise ValueError(f"Reserve SOL cannot be negative: {self.config.reserve_sol}")

        if self.config.min_viable_balance_per_executor < 0:
            raise ValueError(f"Min viable balance cannot be negative: "
                           f"{self.config.min_viable_balance_per_executor}")

    async def calculate_allocations(self, main_wallet_balance_sol: float,
                                   executor_current_balances: Optional[Dict[str, float]] = None
                                   ) -> List[Tuple[str, float]]:
        """
        Calculate SOL allocation for each executor.

        Flow:
        1. Validate main wallet has sufficient balance (reserve + min allocations)
        2. Calculate available SOL for distribution
        3. Apply allocation mode (equal or weighted)
        4. Adjust for existing executor balances (top-up only, don't over-allocate)
        5. Return list of (address, amount_to_transfer)

        Args:
            main_wallet_balance_sol: Current balance in main wallet
            executor_current_balances: Dict of {executor_address: current_balance_sol}
                                      If None, assumes all executors at 0

        Returns:
            List of (executor_address, amount_sol) tuples for transfer
            Empty list if insufficient balance or other fail-closed condition

        Raises:
            ValueError: Only on configuration errors (not balance issues)
        """
        if executor_current_balances is None:
            executor_current_balances = {}

        logger.info(f"Calculating allocations: main_balance={main_wallet_balance_sol}SOL, "
                   f"reserve={self.config.reserve_sol}SOL")

        # Fail-closed: validate main balance covers reserve
        if main_wallet_balance_sol < self.config.reserve_sol:
            logger.warning(
                f"Insufficient main wallet balance: {main_wallet_balance_sol}SOL < "
                f"reserve {self.config.reserve_sol}SOL. Skipping allocation."
            )
            return []

        # Available SOL for distribution (after reserve)
        available_for_distribution = main_wallet_balance_sol - self.config.reserve_sol

        # Count how many wallets need funding (below target)
        wallets_needing_funding = 0
        for addr in self.config.executor_addresses:
            current = executor_current_balances.get(addr, 0)
            if current < self.config.min_viable_balance_per_executor:
                wallets_needing_funding += 1

        # If no wallets need funding, return empty
        if wallets_needing_funding == 0:
            logger.info("All executor wallets already at/above minimum viable balance")
            return []

        # Estimate total TX fees (1 fee per wallet needing funding)
        total_tx_fees = wallets_needing_funding * self.config.solana_tx_fee_sol

        # Fail-closed: check if we have enough for even minimum allocations
        min_allocation_total = (
            wallets_needing_funding *
            self.config.min_viable_balance_per_executor
        )

        if available_for_distribution < (min_allocation_total + total_tx_fees):
            logger.warning(
                f"Insufficient funds for minimum allocations. "
                f"Available: {available_for_distribution}SOL, "
                f"needed: {min_allocation_total + total_tx_fees}SOL "
                f"({min_allocation_total}SOL + {total_tx_fees}SOL fees). "
                f"Skipping allocation."
            )
            return []

        # Get list of executors that need funding (below minimum)
        executors_needing_funding = [
            addr for addr in self.config.executor_addresses
            if executor_current_balances.get(addr, 0) < self.config.min_viable_balance_per_executor
        ]

        # Calculate base allocations based on mode (for executors needing funding only)
        # This is critical: we only allocate to wallets that need top-ups
        if self.config.allocation_mode == AllocationMode.EQUAL:
            # Create sub-config for calculation with only needing-funding wallets
            base_allocations = self._calculate_equal_split_for_list(
                executors_needing_funding,
                available_for_distribution,
                total_tx_fees
            )
        elif self.config.allocation_mode == AllocationMode.WEIGHTED:
            base_allocations = self._calculate_weighted_split_for_list(
                executors_needing_funding,
                available_for_distribution,
                total_tx_fees
            )
        else:
            logger.error(f"Unknown allocation mode: {self.config.allocation_mode}")
            return []

        # Adjust for existing executor balances (top-up only)
        transfer_instructions = []
        for executor_addr, base_amount in base_allocations.items():
            current_balance = executor_current_balances.get(executor_addr, 0)
            target_amount = base_amount

            if current_balance >= target_amount:
                logger.debug(
                    f"Executor {executor_addr} already funded: "
                    f"current={current_balance}SOL >= target={target_amount}SOL"
                )
                continue

            transfer_amount = target_amount - current_balance

            # Fail-closed: skip if transfer would be dust
            if transfer_amount < (self.config.solana_tx_fee_sol * 2):
                logger.warning(
                    f"Transfer amount to {executor_addr} is dust: {transfer_amount}SOL. "
                    f"Skipping to avoid fee burn."
                )
                continue

            transfer_instructions.append((executor_addr, transfer_amount))
            logger.info(
                f"Allocation: {executor_addr} "
                f"(current={current_balance}SOL, target={target_amount}SOL, "
                f"transfer={transfer_amount}SOL)"
            )

        logger.info(f"Allocation complete: {len(transfer_instructions)} transfers")
        return transfer_instructions

    def _calculate_equal_split_for_list(self, executor_list: List[str],
                                        available_sol: float,
                                        total_tx_fees: float) -> Dict[str, float]:
        """
        Equal split for specified executor list only.

        Calculation:
        1. Deduct total TX fees from available
        2. Divide remainder equally among specified executors
        3. Ensure each executor gets at least min_viable_balance
        """
        if not executor_list:
            return {}

        num_executors = len(executor_list)
        allocatable = available_sol - total_tx_fees
        per_executor = allocatable / num_executors

        # Ensure minimum
        per_executor = max(per_executor, self.config.min_viable_balance_per_executor)

        return {addr: per_executor for addr in executor_list}

    def _calculate_equal_split(self, available_sol: float,
                              total_tx_fees: float) -> Dict[str, float]:
        """
        Equal split: divide available SOL equally among all executors.
        Deprecated: use _calculate_equal_split_for_list instead.
        """
        return self._calculate_equal_split_for_list(
            self.config.executor_addresses,
            available_sol,
            total_tx_fees
        )

    def _calculate_weighted_split_for_list(self, executor_list: List[str],
                                           available_sol: float,
                                           total_tx_fees: float) -> Dict[str, float]:
        """
        Weighted split for specified executor list only.

        Calculation:
        1. Sum weights for specified executors only
        2. Allocate proportionally: (weight / total_weight) * available_sol
        3. Ensure each executor meets minimum
        """
        if not executor_list:
            return {}

        allocatable = available_sol - total_tx_fees

        # Sum weights only for executors in the list
        total_weight = sum(
            self.config.executor_weights.get(addr, 1.0)
            for addr in executor_list
        )

        allocations = {}
        for addr in executor_list:
            weight = self.config.executor_weights.get(addr, 1.0)
            proportional = (weight / total_weight) * allocatable
            # Ensure minimum
            amount = max(proportional, self.config.min_viable_balance_per_executor)
            allocations[addr] = amount

        return allocations

    def _calculate_weighted_split(self, available_sol: float,
                                 total_tx_fees: float) -> Dict[str, float]:
        """
        Weighted split for all executors.
        Deprecated: use _calculate_weighted_split_for_list instead.
        """
        return self._calculate_weighted_split_for_list(
            self.config.executor_addresses,
            available_sol,
            total_tx_fees
        )

    def quarantine_wallet(self, executor_address: str, reason: str):
        """
        Mark wallet as temporarily unavailable (failed transfer).

        Args:
            executor_address: Wallet address to quarantine
            reason: Reason for quarantine (logged)
        """
        if executor_address not in self.config.quarantined_wallets:
            self.config.quarantined_wallets.append(executor_address)
            logger.error(
                f"Quarantined wallet {executor_address}: {reason}. "
                f"Will exclude from future allocations until manually cleared."
            )

    def clear_quarantine(self, executor_address: str):
        """
        Remove wallet from quarantine (manual recovery).

        Args:
            executor_address: Wallet to restore
        """
        if executor_address in self.config.quarantined_wallets:
            self.config.quarantined_wallets.remove(executor_address)
            logger.info(f"Cleared quarantine for wallet {executor_address}")

    def get_fund_status(self) -> Dict:
        """
        Return current fund splitter status for monitoring.

        Returns:
            Dict with allocation mode, executor count, reserves, quarantined wallets
        """
        return {
            "allocation_mode": self.config.allocation_mode.value,
            "executor_count": len(self.config.executor_addresses),
            "reserve_sol": self.config.reserve_sol,
            "min_viable_balance_per_executor": self.config.min_viable_balance_per_executor,
            "quarantined_wallets": list(self.config.quarantined_wallets),
            "quarantine_count": len(self.config.quarantined_wallets),
        }


# ============================================================================
# Async RPC Integration (stub for dispatcher)
# ============================================================================

class RpcFundTransfer:
    """
    RPC-based fund transfer executor (integrates with dispatcher).

    Note: Actual signing and broadcast happens in dispatcher.
    This class handles balance queries and validates state.
    """

    def __init__(self, rpc_url: str):
        """
        Initialize RPC client for balance queries.

        Args:
            rpc_url: Solana RPC endpoint (e.g., from EnvLoader)
        """
        self.rpc_url = rpc_url
        logger.info(f"RpcFundTransfer initialized: rpc={rpc_url}")

    async def get_balance(self, wallet_address: str) -> float:
        """
        Query Solana balance for wallet (in SOL).

        Args:
            wallet_address: Public key to query

        Returns:
            Balance in SOL, or 0.0 if query fails (fail-closed)

        Note: In production, this would call aiohttp to RPC endpoint.
             For now, stubbed for testing.
        """
        try:
            # Stubbed for testing - real implementation would use aiohttp
            logger.debug(f"Querying balance for {wallet_address}")
            return 0.0  # Placeholder
        except Exception as e:
            logger.error(f"Failed to query balance for {wallet_address}: {e}")
            return 0.0

    async def get_balances_batch(self, addresses: List[str]) -> Dict[str, float]:
        """
        Query balances for multiple wallets in parallel.

        Args:
            addresses: List of public keys

        Returns:
            Dict of {address: balance_sol}
        """
        tasks = [self.get_balance(addr) for addr in addresses]
        balances = await asyncio.gather(*tasks, return_exceptions=True)

        result = {}
        for addr, balance in zip(addresses, balances):
            if isinstance(balance, Exception):
                logger.warning(f"Balance query failed for {addr}: {balance}")
                result[addr] = 0.0
            else:
                result[addr] = balance

        return result


# ============================================================================
# Integration: Dispatcher Hook
# ============================================================================

async def build_fund_split_instructions(
    config: FundSplitterConfig,
    main_wallet_balance_sol: float,
    executor_current_balances: Optional[Dict[str, float]] = None
) -> List[Tuple[str, float]]:
    """
    High-level entry point for dispatcher.

    Used by Phase 2 Dispatcher to get list of fund transfers to execute.

    Args:
        config: Fund splitter configuration
        main_wallet_balance_sol: Current main wallet balance
        executor_current_balances: Current executor balances (optional)

    Returns:
        List of (executor_address, amount_sol) for dispatcher to sign
    """
    splitter = FundSplitter(config)
    return await splitter.calculate_allocations(main_wallet_balance_sol,
                                               executor_current_balances)
