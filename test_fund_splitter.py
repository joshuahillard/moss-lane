"""
Test Suite for Fund Splitter Module

Tests cover:
- Equal and weighted allocation modes
- Fee-aware calculations
- Edge cases (insufficient balance, dust amounts, quarantine)
- Reserve protection
- Existing balance top-ups
- Configuration validation

All tests mock RPC calls - no real network requests.
Uses unittest framework for isolation and reproducibility.
"""

import unittest
import asyncio
import logging
from unittest.mock import Mock, patch, AsyncMock
from fund_splitter import (
    FundSplitter,
    FundSplitterConfig,
    AllocationMode,
    RpcFundTransfer,
    build_fund_split_instructions,
)


# Suppress debug logs during testing
logging.getLogger('fund_splitter').setLevel(logging.WARNING)


class TestFundSplitterConfig(unittest.TestCase):
    """Test configuration loading and 3-layer hierarchy"""

    def test_default_config(self):
        """Test that defaults load correctly"""
        cfg = FundSplitterConfig()
        self.assertEqual(cfg.allocation_mode, AllocationMode.EQUAL)
        self.assertEqual(cfg.reserve_sol, 0.01)
        self.assertEqual(cfg.min_viable_balance_per_executor, 0.05)
        self.assertEqual(len(cfg.executor_addresses), 0)

    def test_from_layers_code_defaults(self):
        """Test layer 1: code defaults"""
        code_defaults = {
            "executor_addresses": ["wallet1", "wallet2"],
            "allocation_mode": AllocationMode.WEIGHTED,
        }
        cfg = FundSplitterConfig.from_layers(code_defaults=code_defaults)

        self.assertEqual(cfg.executor_addresses, ["wallet1", "wallet2"])
        self.assertEqual(cfg.allocation_mode, AllocationMode.WEIGHTED)
        # Non-overridden defaults should remain
        self.assertEqual(cfg.reserve_sol, 0.01)

    def test_from_layers_db_overrides_code(self):
        """Test layer 2: DB config overrides code defaults"""
        code_defaults = {"reserve_sol": 0.01}
        db_config = {"reserve_sol": 0.02}

        cfg = FundSplitterConfig.from_layers(
            code_defaults=code_defaults,
            db_config=db_config
        )
        self.assertEqual(cfg.reserve_sol, 0.02)

    def test_from_layers_dynamic_overrides_all(self):
        """Test layer 3: dynamic config overrides everything"""
        code_defaults = {"reserve_sol": 0.01}
        db_config = {"reserve_sol": 0.02}
        dynamic_config = {"reserve_sol": 0.05}

        cfg = FundSplitterConfig.from_layers(
            code_defaults=code_defaults,
            db_config=db_config,
            dynamic_config=dynamic_config
        )
        self.assertEqual(cfg.reserve_sol, 0.05)


class TestFundSplitterValidation(unittest.TestCase):
    """Test configuration validation (fail-closed)"""

    def test_validate_no_executors(self):
        """Should fail if no executors configured"""
        cfg = FundSplitterConfig()
        with self.assertRaises(ValueError) as ctx:
            FundSplitter(cfg)
        self.assertIn("No executor addresses", str(ctx.exception))

    def test_validate_too_many_executors(self):
        """Should fail if more than 10 executors"""
        cfg = FundSplitterConfig(
            executor_addresses=[f"wallet_{i}" for i in range(11)]
        )
        with self.assertRaises(ValueError) as ctx:
            FundSplitter(cfg)
        self.assertIn("Too many executors", str(ctx.exception))

    def test_validate_weighted_missing_weights(self):
        """Should fail if weighted mode but no weights"""
        cfg = FundSplitterConfig(
            allocation_mode=AllocationMode.WEIGHTED,
            executor_addresses=["wallet1", "wallet2"]
        )
        with self.assertRaises(ValueError) as ctx:
            FundSplitter(cfg)
        self.assertIn("mode requires", str(ctx.exception))

    def test_validate_weighted_missing_executor_weight(self):
        """Should fail if executor missing weight in weighted mode"""
        cfg = FundSplitterConfig(
            allocation_mode=AllocationMode.WEIGHTED,
            executor_addresses=["wallet1", "wallet2"],
            executor_weights={"wallet1": 1.0}  # wallet2 missing
        )
        with self.assertRaises(ValueError) as ctx:
            FundSplitter(cfg)
        self.assertIn("wallet2 missing weight", str(ctx.exception))

    def test_validate_negative_reserve(self):
        """Should fail if negative reserve"""
        cfg = FundSplitterConfig(
            executor_addresses=["wallet1"],
            reserve_sol=-0.01
        )
        with self.assertRaises(ValueError) as ctx:
            FundSplitter(cfg)
        self.assertIn("cannot be negative", str(ctx.exception))


class TestEqualSplit(unittest.IsolatedAsyncioTestCase):
    """Test equal allocation mode"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1", "wallet2", "wallet3", "wallet4", "wallet5"],
            reserve_sol=0.01,
            min_viable_balance_per_executor=0.05,
            solana_tx_fee_sol=0.000005,
        )
        self.splitter = FundSplitter(self.config)

    async def test_equal_split_sufficient_balance(self):
        """5 wallets get equal allocation from sufficient balance"""
        # Start: 1.0 SOL
        # Reserve: 0.01 SOL
        # Available: 0.99 SOL
        # Fees: 5 * 0.000005 = 0.000025 SOL
        # Per executor: 0.99 / 5 = 0.198 SOL (minus fees)
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        self.assertEqual(len(allocations), 5)
        for addr, amount in allocations:
            self.assertIn(addr, self.config.executor_addresses)
            self.assertGreater(amount, 0)
            # All should be roughly equal (within rounding)
            self.assertAlmostEqual(amount, allocations[0][1], places=6)

    async def test_equal_split_all_wallets_present(self):
        """All 5 executors should be in allocation"""
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        allocated_addrs = [addr for addr, _ in allocations]
        self.assertEqual(set(allocated_addrs), set(self.config.executor_addresses))


class TestWeightedSplit(unittest.IsolatedAsyncioTestCase):
    """Test weighted allocation mode"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.WEIGHTED,
            executor_addresses=["wallet_high", "wallet_low"],
            executor_weights={"wallet_high": 3.0, "wallet_low": 1.0},
            reserve_sol=0.01,
            min_viable_balance_per_executor=0.05,
            solana_tx_fee_sol=0.000005,
        )
        self.splitter = FundSplitter(self.config)

    async def test_weighted_split_proportional(self):
        """Weighted allocation distributes correctly"""
        # high:low = 3:1
        # high should get ~3x as much as low
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        alloc_dict = {addr: amount for addr, amount in allocations}
        high_amount = alloc_dict["wallet_high"]
        low_amount = alloc_dict["wallet_low"]

        # Ratio should be roughly 3:1
        ratio = high_amount / low_amount
        self.assertGreater(ratio, 2.5)  # Allow small variance
        self.assertLess(ratio, 3.5)

    async def test_weighted_split_both_wallets_present(self):
        """Both executors should be allocated"""
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        allocated_addrs = [addr for addr, _ in allocations]
        self.assertIn("wallet_high", allocated_addrs)
        self.assertIn("wallet_low", allocated_addrs)


class TestInsufficientBalance(unittest.IsolatedAsyncioTestCase):
    """Test graceful degradation with low balances"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1", "wallet2", "wallet3"],
            reserve_sol=0.01,
            min_viable_balance_per_executor=0.05,
        )
        self.splitter = FundSplitter(self.config)

    async def test_insufficient_main_balance_below_reserve(self):
        """Main wallet below reserve → empty list"""
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=0.005  # Below 0.01 reserve
        )
        self.assertEqual(allocations, [])

    async def test_insufficient_for_minimum_allocations(self):
        """Balance insufficient for minimum per-executor → empty list"""
        # 3 executors * 0.05 min = 0.15 SOL needed
        # Available: 0.10 SOL - insufficient
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=0.11  # Barely over reserve
        )
        self.assertEqual(allocations, [])

    async def test_partial_fill_only_viable_wallets(self):
        """Return allocation only if min_viable_balance can be met"""
        # With small balance, should either fill all or none
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=0.20
        )
        # Either all 3 executors allocated or none
        self.assertIn(len(allocations), [0, 3])


class TestReserveProtection(unittest.IsolatedAsyncioTestCase):
    """Test that main wallet reserve is never violated"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1"],
            reserve_sol=0.1,  # High reserve
            min_viable_balance_per_executor=0.05,
        )
        self.splitter = FundSplitter(self.config)

    async def test_reserve_never_allocated(self):
        """Reserve SOL never appears in allocations"""
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=0.2
        )

        # With 0.2 SOL main and 0.1 SOL reserve:
        # Only 0.1 SOL available for allocation
        # Should be able to allocate (1 executor * 0.05 min < 0.1)
        self.assertEqual(len(allocations), 1)
        _, amount = allocations[0]

        # Total allocated + reserve should not exceed main balance
        self.assertLessEqual(amount + self.config.reserve_sol, 0.2)


class TestMinimumViableBalance(unittest.IsolatedAsyncioTestCase):
    """Test minimum balance enforcement per executor"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1", "wallet2"],
            reserve_sol=0.01,
            min_viable_balance_per_executor=0.1,
            solana_tx_fee_sol=0.000005,
        )
        self.splitter = FundSplitter(self.config)

    async def test_all_executors_above_minimum(self):
        """All executors should meet minimum"""
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        for _, amount in allocations:
            self.assertGreaterEqual(
                amount,
                self.config.min_viable_balance_per_executor
            )

    async def test_insufficient_for_minimum_returns_empty(self):
        """If balance too low for minimums, return empty"""
        # 2 executors * 0.1 min = 0.2 SOL needed
        # Only 0.15 SOL total - insufficient
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=0.15
        )
        self.assertEqual(allocations, [])


class TestFeeAwareSizing(unittest.IsolatedAsyncioTestCase):
    """Test that transaction fees are properly deducted"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1", "wallet2"],
            reserve_sol=0.01,
            min_viable_balance_per_executor=0.01,
            solana_tx_fee_sol=0.000005,
        )
        self.splitter = FundSplitter(self.config)

    async def test_fees_deducted_from_allocation(self):
        """Fees should reduce per-executor amounts"""
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        # Without fees: (1.0 - 0.01) / 2 = 0.495 SOL each
        # With 2 * 0.000005 = 0.00001 SOL fees:
        # (0.99 - 0.00001) / 2 = 0.494995 SOL each
        total_allocated = sum(amount for _, amount in allocations)
        total_fees = len(allocations) * self.config.solana_tx_fee_sol

        # Allocated + fees + reserve should equal or be less than balance
        self.assertLessEqual(
            total_allocated + total_fees + self.config.reserve_sol,
            1.0
        )


class TestExistingBalance(unittest.IsolatedAsyncioTestCase):
    """Test top-up behavior for already-funded wallets"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1", "wallet2"],
            reserve_sol=0.01,
            min_viable_balance_per_executor=0.1,
        )
        self.splitter = FundSplitter(self.config)

    async def test_already_funded_wallet_excluded(self):
        """Wallet at/above target balance excluded from allocation"""
        current_balances = {
            "wallet1": 0.15,  # Already above min_viable_balance (0.1)
            "wallet2": 0.0,
        }

        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0,
            executor_current_balances=current_balances
        )

        allocated_addrs = [addr for addr, _ in allocations]
        # wallet1 is already funded, so should be excluded
        self.assertNotIn("wallet1", allocated_addrs)
        # wallet2 needs funding
        self.assertIn("wallet2", allocated_addrs)

    async def test_underfunded_wallet_topped_up(self):
        """Wallet below minimum receives top-up (delta only)"""
        current_balances = {
            "wallet1": 0.05,  # Below min_viable (0.1)
            "wallet2": 0.0,   # Below min_viable
        }

        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0,
            executor_current_balances=current_balances
        )

        # Should include both wallets (both need funding to reach 0.1 minimum)
        self.assertEqual(len(allocations), 2)

        # Find allocation for wallet1
        wallet1_alloc = next(
            (amount for addr, amount in allocations if addr == "wallet1"),
            None
        )
        self.assertIsNotNone(wallet1_alloc)
        # Transfer should be delta (target - current)
        # target is roughly (available-fees)/2, current is 0.05
        # So transfer < target
        target = (1.0 - 0.01 - (2 * 0.000005)) / 2  # Available / 2
        self.assertAlmostEqual(wallet1_alloc, target - 0.05, places=5)

    async def test_no_current_balances_assumes_zero(self):
        """If no current balances provided, assume all zero"""
        # With no current_balances dict, should assume all executors at 0
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        self.assertEqual(len(allocations), 2)


class TestDustProtection(unittest.IsolatedAsyncioTestCase):
    """Test that dust amounts are skipped"""

    async def asyncSetUp(self):
        self.config = FundSplitterConfig(
            allocation_mode=AllocationMode.EQUAL,
            executor_addresses=["wallet1"],
            reserve_sol=0.999,  # Very high reserve
            min_viable_balance_per_executor=0.00001,
            solana_tx_fee_sol=0.000005,
        )
        self.splitter = FundSplitter(self.config)

    async def test_dust_amount_skipped(self):
        """Transfer < 2x fee gets skipped"""
        # With high reserve, transfer amount may be very small
        allocations = await self.splitter.calculate_allocations(
            main_wallet_balance_sol=1.0
        )

        for _, amount in allocations:
            # All transfers should be at least 2x fee (dust threshold)
            self.assertGreaterEqual(
                amount,
                self.config.solana_tx_fee_sol * 2
            )


class TestQuarantine(unittest.TestCase):
    """Test wallet quarantine for failed transfers"""

    def setUp(self):
        self.config = FundSplitterConfig(
            executor_addresses=["wallet1", "wallet2", "wallet3"]
        )
        self.splitter = FundSplitter(self.config)

    def test_quarantine_wallet(self):
        """Quarantine marks wallet unavailable"""
        self.splitter.quarantine_wallet("wallet1", "Transfer failed")
        self.assertIn("wallet1", self.config.quarantined_wallets)

    def test_clear_quarantine(self):
        """Clear quarantine restores wallet"""
        self.splitter.quarantine_wallet("wallet1", "Transfer failed")
        self.splitter.clear_quarantine("wallet1")
        self.assertNotIn("wallet1", self.config.quarantined_wallets)

    def test_quarantine_already_quarantined(self):
        """Quarantine idempotent (no duplicates)"""
        self.splitter.quarantine_wallet("wallet1", "Failed 1")
        self.splitter.quarantine_wallet("wallet1", "Failed 2")
        self.assertEqual(self.config.quarantined_wallets.count("wallet1"), 1)

    def test_quarantine_nonexistent_wallet(self):
        """Quarantine non-existent wallet (no error)"""
        self.splitter.quarantine_wallet("unknown_wallet", "Test")
        self.assertIn("unknown_wallet", self.config.quarantined_wallets)

    def test_get_fund_status_includes_quarantine(self):
        """Fund status reports quarantined wallets"""
        self.splitter.quarantine_wallet("wallet1", "Test")
        status = self.splitter.get_fund_status()
        self.assertEqual(status["quarantine_count"], 1)
        self.assertIn("wallet1", status["quarantined_wallets"])


class TestEmptyWalletList(unittest.IsolatedAsyncioTestCase):
    """Test handling of empty executor list"""

    async def test_no_executors_raises_on_init(self):
        """Empty executor list should fail at init"""
        config = FundSplitterConfig(executor_addresses=[])
        with self.assertRaises(ValueError):
            FundSplitter(config)


class TestGetFundStatus(unittest.TestCase):
    """Test status reporting"""

    def test_status_structure(self):
        """Status dict has all required fields"""
        config = FundSplitterConfig(executor_addresses=["wallet1"])
        splitter = FundSplitter(config)
        status = splitter.get_fund_status()

        required_keys = [
            "allocation_mode",
            "executor_count",
            "reserve_sol",
            "min_viable_balance_per_executor",
            "quarantined_wallets",
            "quarantine_count",
        ]
        for key in required_keys:
            self.assertIn(key, status)

    def test_status_values_correct(self):
        """Status values match config"""
        config = FundSplitterConfig(
            executor_addresses=["w1", "w2"],
            allocation_mode=AllocationMode.EQUAL,
            reserve_sol=0.05,
        )
        splitter = FundSplitter(config)
        status = splitter.get_fund_status()

        self.assertEqual(status["executor_count"], 2)
        self.assertEqual(status["allocation_mode"], "equal")
        self.assertEqual(status["reserve_sol"], 0.05)


class TestIntegrationHighLevel(unittest.IsolatedAsyncioTestCase):
    """Integration tests using high-level dispatcher hook"""

    async def test_build_fund_split_instructions(self):
        """High-level entry point works end-to-end"""
        config = FundSplitterConfig(
            executor_addresses=["wallet1", "wallet2"],
            allocation_mode=AllocationMode.EQUAL,
        )

        instructions = await build_fund_split_instructions(
            config=config,
            main_wallet_balance_sol=1.0
        )

        self.assertIsInstance(instructions, list)
        self.assertEqual(len(instructions), 2)
        for addr, amount in instructions:
            self.assertIn(addr, ["wallet1", "wallet2"])
            self.assertGreater(amount, 0)


class TestRpcFundTransfer(unittest.IsolatedAsyncioTestCase):
    """Test RPC integration stub"""

    async def test_rpc_init(self):
        """RPC client initializes"""
        rpc = RpcFundTransfer("https://api.mainnet-beta.solana.com")
        self.assertIsNotNone(rpc)

    async def test_get_balance_stub(self):
        """Balance query stub returns 0 (to be implemented)"""
        rpc = RpcFundTransfer("https://api.mainnet-beta.solana.com")
        balance = await rpc.get_balance("11111111111111111111111111111111")
        self.assertEqual(balance, 0.0)

    async def test_get_balances_batch(self):
        """Batch balance query works"""
        rpc = RpcFundTransfer("https://api.mainnet-beta.solana.com")
        balances = await rpc.get_balances_batch([
            "11111111111111111111111111111111",
            "22222222222222222222222222222222",
        ])

        self.assertIsInstance(balances, dict)
        self.assertEqual(len(balances), 2)


# ============================================================================
# Test Runner
# ============================================================================

if __name__ == "__main__":
    # Run all tests
    unittest.main(verbosity=2)
