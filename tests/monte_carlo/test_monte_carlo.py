"""Tests for Monte Carlo simulation."""

import unittest
from tests.monte_carlo.monte_carlo_engine import MonteCarloEngine, run_stress_test_scenario


class TestMonteCarloEngine(unittest.TestCase):
    """Test Monte Carlo simulation engine."""
    
    def test_simulation_execution(self):
        """Test running Monte Carlo simulation."""
        engine = MonteCarloEngine(num_simulations=10, seed=42)
        results = engine.run_simulation(
            num_exchanges=2,
            num_stablecoins=2,
            price_volatility=0.01,
            fee_range=(0.001, 0.005)
        )
        
        # Should have results for all simulations
        self.assertEqual(len(results), 10)
        
        # Each result should have expected structure
        for result in results:
            self.assertIn('simulation', result)
            self.assertIn('num_opportunities', result)
            self.assertIn('total_profit', result)
            self.assertIn('has_opportunities', result)
    
    def test_statistics_calculation(self):
        """Test calculating statistical metrics."""
        engine = MonteCarloEngine(num_simulations=20, seed=42)
        engine.run_simulation(
            num_exchanges=2,
            num_stablecoins=2,
            price_volatility=0.01
        )
        
        stats = engine.calculate_statistics()
        
        # Should have all expected metrics
        self.assertIn('num_simulations', stats)
        self.assertIn('success_rate', stats)
        self.assertIn('avg_profit', stats)
        self.assertIn('var_5_percentile', stats)
        
        # Metrics should be reasonable
        self.assertEqual(stats['num_simulations'], 20)
        self.assertGreaterEqual(stats['success_rate'], 0)
        self.assertLessEqual(stats['success_rate'], 1)
    
    def test_stress_scenario(self):
        """Test stress test scenario."""
        stats = run_stress_test_scenario(
            num_simulations=10,
            high_volatility=True,
            asymmetric_fees=True
        )
        
        # Should complete without errors
        self.assertIn('success_rate', stats)
        self.assertIn('avg_profit', stats)
        
        # Under stress conditions, success rate might be lower
        # but system should still function
        self.assertGreaterEqual(stats['success_rate'], 0)


if __name__ == '__main__':
    unittest.main()

