"""Unit tests for wallet manager."""

import unittest
from src.models.exchange_node import ExchangeNode
from src.utils.wallet_manager import WalletManager


class TestWalletManager(unittest.TestCase):
    """Test cases for WalletManager."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.manager = WalletManager()
        self.node1 = ExchangeNode("Kraken", "USDT", 1.0)
        self.node2 = ExchangeNode("Coinbase", "USDC", 1.0)
        self.node3 = ExchangeNode("Binance", "BUSD", 1.0)
    
    def test_set_get_balance(self):
        """Test setting and getting balances."""
        self.manager.set_balance("Kraken", "USDT", 1000.0)
        self.assertEqual(self.manager.get_balance("Kraken", "USDT"), 1000.0)
        self.assertEqual(self.manager.get_balance("Kraken", "USDC"), 0.0)
    
    def test_default_fee_schedule(self):
        """Test default volume-based fee schedule."""
        # Small volume: 0.1%
        self.assertAlmostEqual(self.manager.get_effective_fee("Kraken", 500), 0.001, places=4)
        
        # Medium volume: 0.05%
        self.assertAlmostEqual(self.manager.get_effective_fee("Kraken", 5000), 0.0005, places=4)
        
        # Large volume: 0.02%
        self.assertAlmostEqual(self.manager.get_effective_fee("Kraken", 50000), 0.0002, places=4)
        
        # Very large volume: 0.01%
        self.assertAlmostEqual(self.manager.get_effective_fee("Kraken", 200000), 0.0001, places=4)
    
    def test_custom_fee_schedule(self):
        """Test custom fee schedule."""
        def custom_fee(volume: float) -> float:
            return 0.002 if volume < 5000 else 0.001
        
        self.manager.set_fee_schedule("Coinbase", custom_fee)
        self.assertEqual(self.manager.get_effective_fee("Coinbase", 1000), 0.002)
        self.assertEqual(self.manager.get_effective_fee("Coinbase", 10000), 0.001)
    
    def test_can_execute(self):
        """Test can_execute method."""
        path = [self.node1, self.node2, self.node3]
        
        # No balances set
        self.assertFalse(self.manager.can_execute(path, 100.0))
        
        # Set balances
        self.manager.set_balance("Kraken", "USDT", 1000.0)
        self.manager.set_balance("Coinbase", "USDC", 500.0)
        self.manager.set_balance("Binance", "BUSD", 2000.0)
        
        # Can execute with 500
        self.assertTrue(self.manager.can_execute(path, 500.0))
        
        # Cannot execute with 600 (Coinbase only has 500)
        self.assertFalse(self.manager.can_execute(path, 600.0))
    
    def test_get_max_executable_amount(self):
        """Test get_max_executable_amount."""
        path = [self.node1, self.node2, self.node3]
        
        # No balances
        self.assertEqual(self.manager.get_max_executable_amount(path), 0.0)
        
        # Set balances
        self.manager.set_balance("Kraken", "USDT", 1000.0)
        self.manager.set_balance("Coinbase", "USDC", 500.0)
        self.manager.set_balance("Binance", "BUSD", 2000.0)
        
        # Should return minimum (500)
        self.assertEqual(self.manager.get_max_executable_amount(path), 500.0)
    
    def test_optimize_volume(self):
        """Test volume optimization."""
        path = [self.node1, self.node2]
        
        # Set balances
        self.manager.set_balance("Kraken", "USDT", 10000.0)
        self.manager.set_balance("Coinbase", "USDC", 10000.0)
        
        # Optimize volume with profit rate 0.001, cost rate 0.0005
        optimal_volume, net_profit = self.manager.optimize_volume(
            path, 0.001, 0.0005, 10000.0
        )
        
        # Should find a positive volume
        self.assertGreater(optimal_volume, 0)
        self.assertGreater(net_profit, 0)
    
    def test_evaluate_opportunity(self):
        """Test evaluate_opportunity method."""
        path = [self.node1, self.node2]
        
        # No funds
        result = self.manager.evaluate_opportunity(path, 0.001, 0.0005)
        self.assertFalse(result['executable'])
        self.assertFalse(result['can_execute'])
        
        # With funds
        self.manager.set_balance("Kraken", "USDT", 1000.0)
        self.manager.set_balance("Coinbase", "USDC", 1000.0)
        
        result = self.manager.evaluate_opportunity(path, 0.001, 0.0005)
        self.assertTrue(result['can_execute'])
        self.assertGreaterEqual(result['max_amount'], 0)
        self.assertGreaterEqual(result['optimal_volume'], 0)
    
    def test_get_summary(self):
        """Test get_summary method."""
        self.manager.set_balance("Kraken", "USDT", 1000.0)
        self.manager.set_balance("Coinbase", "USDC", 500.0)
        self.manager.set_balance("Binance", "BUSD", 2000.0)
        
        summary = self.manager.get_summary()
        self.assertEqual(summary['total_balance'], 3500.0)
        self.assertEqual(summary['num_positions'], 3)
        self.assertIn('Kraken', summary['exchange_totals'])
        self.assertEqual(summary['exchange_totals']['Kraken'], 1000.0)


if __name__ == '__main__':
    unittest.main()

