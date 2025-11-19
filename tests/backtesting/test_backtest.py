"""Tests for backtesting framework."""

import unittest
from datetime import datetime, timedelta
from tests.backtesting.backtest_engine import BacktestEngine, generate_synthetic_historical_data


class TestBacktestEngine(unittest.TestCase):
    """Test backtesting engine."""
    
    def test_historical_data_generation(self):
        """Test generating synthetic historical data."""
        data = generate_synthetic_historical_data(
            num_days=7,
            exchanges=['Kraken', 'Coinbase'],
            stablecoins=['USDT', 'USDC'],
            seed=42
        )
        
        # Should have 7 days × 24 hours = 168 timestamps
        self.assertEqual(len(data), 7 * 24)
        
        # Check structure
        first_timestamp = min(data.keys())
        first_prices = data[first_timestamp]
        
        # Should have prices for all exchange/coin combinations
        self.assertEqual(len(first_prices), 2 * 2)  # 2 exchanges × 2 coins
        
        # Check price format
        for key, price in first_prices.items():
            self.assertIsInstance(key, tuple)
            self.assertEqual(len(key), 2)  # (exchange, stablecoin)
            self.assertIsInstance(price, float)
            self.assertGreater(price, 0)
    
    def test_backtest_execution(self):
        """Test running a backtest."""
        # Generate small dataset
        data = generate_synthetic_historical_data(
            num_days=1,  # Just 1 day for speed
            exchanges=['Kraken', 'Coinbase'],
            stablecoins=['USDT'],
            seed=42
        )
        
        engine = BacktestEngine(data)
        results = engine.run_backtest(algorithm='astar', max_depth=3)
        
        # Should have results for each timestamp
        self.assertEqual(len(results), len(data))
        
        # Each result should have expected structure
        for result in results:
            self.assertIn('timestamp', result)
            self.assertIn('num_opportunities', result)
            self.assertIn('opportunities', result)
            self.assertIn('graph_stats', result)
    
    def test_backtest_metrics(self):
        """Test calculating backtest metrics."""
        data = generate_synthetic_historical_data(
            num_days=1,
            exchanges=['Kraken', 'Coinbase'],
            stablecoins=['USDT'],
            seed=42
        )
        
        engine = BacktestEngine(data)
        engine.run_backtest(algorithm='astar', max_depth=3)
        metrics = engine.calculate_metrics()
        
        # Should have all expected metrics
        self.assertIn('total_timestamps', metrics)
        self.assertIn('total_opportunities', metrics)
        self.assertIn('avg_opportunities_per_timestamp', metrics)
        self.assertIn('total_potential_profit', metrics)
        
        # Metrics should be reasonable
        self.assertGreaterEqual(metrics['total_timestamps'], 0)
        self.assertGreaterEqual(metrics['total_opportunities'], 0)


if __name__ == '__main__':
    unittest.main()

