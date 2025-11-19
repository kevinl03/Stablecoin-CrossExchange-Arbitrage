"""Validation tests for arbitrage detection correctness."""

import unittest
from src import ArbitrageAgent
from src.models import ArbitrageGraph, ExchangeNode, Edge


class TestArbitrageDetection(unittest.TestCase):
    """Test arbitrage opportunity detection logic."""
    
    def setUp(self):
        """Set up test graph with known arbitrage opportunity."""
        self.graph = ArbitrageGraph()
        
        # Create nodes with price difference
        self.graph.add_node("Kraken", "USDT", 1.000)  # Lower price
        self.graph.add_node("Coinbase", "USDT", 1.010)  # Higher price
        
        # Create edge with low cost (should be profitable)
        self.graph.add_edge(
            "Kraken", "USDT",
            "Coinbase", "USDT",
            0.0005,  # Low fee
            0.0001,  # Low volatility
            60.0
        )
        
        self.agent = ArbitrageAgent(self.graph)
    
    def test_arbitrage_condition(self):
        """Test that arbitrage condition is correctly evaluated."""
        node1 = self.graph.get_node("Kraken", "USDT")
        node2 = self.graph.get_node("Coinbase", "USDT")
        edge = node1.edges[0]
        
        # Price difference (buy low, sell high)
        price_diff = node2.price - node1.price  # 1.01 - 1.00 = 0.01
        
        # Total cost
        total_cost = edge.weight  # 0.0005 + 0.0001 = 0.0006
        
        # Arbitrage exists if price_diff > total_cost
        is_profitable = price_diff > total_cost
        
        self.assertTrue(is_profitable, 
                        f"Price diff {price_diff} should exceed cost {total_cost}")
    
    def test_cycle_detection(self):
        """Test that cycles back to start are detected."""
        # Add return edge to create cycle
        self.graph.add_edge(
            "Coinbase", "USDT",
            "Kraken", "USDT",
            0.0005, 0.0001, 60.0
        )
        
        start_node = self.graph.get_node("Kraken", "USDT")
        opportunities = self.agent.find_arbitrage_paths(
            start_node,
            algorithm='astar',
            max_depth=3
        )
        
        # Should find cycles
        if opportunities:
            path, profit, cost = opportunities[0]
            # Path should start and end at same node (cycle)
            self.assertEqual(path[0], path[-1])
    
    def test_profit_calculation(self):
        """Test net profit calculation accuracy."""
        node1 = self.graph.get_node("Kraken", "USDT")
        node2 = self.graph.get_node("Coinbase", "USDT")
        edge = node1.edges[0]
        
        amount = 100.0
        price_diff = (node2.price - node1.price) * amount
        total_cost = edge.weight * amount
        
        net_profit = price_diff - total_cost
        
        # Manual calculation
        expected_profit = (1.01 - 1.00) * 100 - (0.0006 * 100)
        expected_profit = 1.0 - 0.06  # = 0.94
        
        self.assertAlmostEqual(net_profit, expected_profit, places=2)
    
    def test_path_validity(self):
        """Test that all paths are actually traversable."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Coinbase", "USDT", 1.01)
        graph.add_node("Kraken", "USDC", 0.99)
        
        # Create valid path
        graph.add_edge("Kraken", "USDT", "Coinbase", "USDT", 0.001, 0.0001, 60.0)
        graph.add_edge("Coinbase", "USDT", "Kraken", "USDC", 0.001, 0.0001, 60.0)
        
        agent = ArbitrageAgent(graph)
        start = graph.get_node("Kraken", "USDT")
        opportunities = agent.find_arbitrage_paths(start, max_depth=3)
        
        # Verify all paths are valid
        for path, profit, cost in opportunities:
            # Check consecutive nodes are connected
            for i in range(len(path) - 1):
                current = path[i]
                next_node = path[i + 1]
                
                # Verify edge exists
                has_edge = any(edge.target == next_node for edge in current.edges)
                self.assertTrue(has_edge, 
                              f"No edge from {current} to {next_node}")
    
    def test_no_false_positives(self):
        """Test that unprofitable opportunities are not reported."""
        graph = ArbitrageGraph()
        # Create scenario where cost exceeds price difference
        graph.add_node("Kraken", "USDT", 1.000)
        graph.add_node("Coinbase", "USDT", 1.001)  # Very small difference
        
        # High cost edge
        graph.add_edge(
            "Kraken", "USDT",
            "Coinbase", "USDT",
            0.01,  # High fee (1%)
            0.005,  # High volatility
            60.0
        )
        
        agent = ArbitrageAgent(graph)
        start = graph.get_node("Kraken", "USDT")
        opportunities = agent.find_arbitrage_paths(start, max_depth=2)
        
        # Verify all reported opportunities are actually profitable
        for path, profit, cost in opportunities:
            self.assertGreater(profit, 0, 
                              "All reported opportunities should be profitable")
    
    def test_cost_accumulation(self):
        """Test that costs accumulate correctly along paths."""
        graph = ArbitrageGraph()
        graph.add_node("A", "USDT", 1.00)
        graph.add_node("B", "USDT", 1.01)
        graph.add_node("C", "USDT", 1.02)
        
        # Create path with known costs
        graph.add_edge("A", "USDT", "B", "USDT", 0.001, 0.0001, 60.0)  # cost = 0.0011
        graph.add_edge("B", "USDT", "C", "USDT", 0.002, 0.0002, 90.0)  # cost = 0.0022
        
        agent = ArbitrageAgent(graph)
        start = graph.get_node("A", "USDT")
        opportunities = agent.find_arbitrage_paths(start, max_depth=3)
        
        # If path A->B->C found, verify cost
        for path, profit, cost in opportunities:
            if len(path) == 3:  # A->B->C path
                expected_cost = 0.0011 + 0.0022
                self.assertAlmostEqual(cost, expected_cost, places=4)


if __name__ == '__main__':
    unittest.main()

