"""Validation tests for A* heuristic function."""

import unittest
from src.models import ExchangeNode, Edge
from src.algorithms.astar import volatility_heuristic


class TestAStarHeuristic(unittest.TestCase):
    """Test A* heuristic function correctness."""
    
    def test_heuristic_components(self):
        """Test that heuristic includes time and volatility risk."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target = ExchangeNode("Coinbase", "USDT", 1.01)
        edge = Edge(source, target, 0.001, 0.0001, 120.0)  # 2 minutes
        
        heuristic = volatility_heuristic(source, target, edge, volatility_factor=0.1)
        
        # Heuristic should have two components:
        # 1. Time risk: transfer_time * 0.001 = 120 * 0.001 = 0.12
        # 2. Volatility risk: price_diff * 0.1 = 0.01 * 0.1 = 0.001
        # Total: ~0.121
        
        self.assertGreater(heuristic, 0, "Heuristic should be positive")
        self.assertLess(heuristic, 1.0, "Heuristic should be reasonable")
    
    def test_time_risk_increases_with_time(self):
        """Test that longer transfer times increase heuristic."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target = ExchangeNode("Coinbase", "USDT", 1.01)
        
        edge_short = Edge(source, target, 0.001, 0.0001, 30.0)  # 30 seconds
        edge_long = Edge(source, target, 0.001, 0.0001, 300.0)  # 5 minutes
        
        heuristic_short = volatility_heuristic(source, target, edge_short, 0.1)
        heuristic_long = volatility_heuristic(source, target, edge_long, 0.1)
        
        # Longer time should have higher heuristic
        self.assertGreater(heuristic_long, heuristic_short)
    
    def test_volatility_risk_increases_with_price_diff(self):
        """Test that larger price differences increase volatility risk."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target1 = ExchangeNode("Coinbase", "USDT", 1.01)  # 1% diff
        target2 = ExchangeNode("Coinbase", "USDT", 1.05)  # 5% diff
        
        edge1 = Edge(source, target1, 0.001, 0.0001, 60.0)
        edge2 = Edge(source, target2, 0.001, 0.0001, 60.0)
        
        heuristic1 = volatility_heuristic(source, target1, edge1, 0.1)
        heuristic2 = volatility_heuristic(source, target2, edge2, 0.1)
        
        # Larger price diff should have higher volatility risk
        self.assertGreater(heuristic2, heuristic1)


if __name__ == '__main__':
    unittest.main()

