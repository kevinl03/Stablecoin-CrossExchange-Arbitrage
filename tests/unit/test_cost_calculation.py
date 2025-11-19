"""Unit tests for cost function calculations."""

import unittest
from src.models import ExchangeNode, Edge, ArbitrageGraph


class TestCostCalculation(unittest.TestCase):
    """Test cost function calculations."""
    
    def test_edge_cost_components(self):
        """Test that edge cost includes fee and volatility."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target = ExchangeNode("Coinbase", "USDT", 1.01)
        
        fee = 0.002
        volatility_cost = 0.0005
        edge = Edge(source, target, fee, volatility_cost, 60.0)
        
        expected_total = fee + volatility_cost
        self.assertEqual(edge.weight, expected_total)
        self.assertEqual(edge.fee, fee)
        self.assertEqual(edge.volatility_cost, volatility_cost)
    
    def test_volatility_cost_calculation(self):
        """Test volatility cost based on price difference."""
        # Large price difference = higher volatility risk
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target1 = ExchangeNode("Coinbase", "USDT", 1.01)  # 1% diff
        target2 = ExchangeNode("Coinbase", "USDT", 1.05)  # 5% diff
        
        edge1 = Edge(source, target1, 0.001, 0.0, 60.0)
        edge2 = Edge(source, target2, 0.001, 0.0, 60.0)
        
        # Manually set volatility based on price diff
        price_diff1 = abs(source.price - target1.price)
        price_diff2 = abs(source.price - target2.price)
        
        volatility_factor = 0.1
        edge1.update_volatility_cost(price_diff1 * volatility_factor)
        edge2.update_volatility_cost(price_diff2 * volatility_factor)
        
        # Larger price diff should have higher volatility cost
        self.assertGreater(edge2.volatility_cost, edge1.volatility_cost)
    
    def test_path_cost_accumulation(self):
        """Test that path costs accumulate correctly."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Coinbase", "USDT", 1.01)
        graph.add_node("Kraken", "USDC", 0.99)
        
        # Create path: Kraken(USDT) -> Coinbase(USDT) -> Kraken(USDC)
        graph.add_edge("Kraken", "USDT", "Coinbase", "USDT", 0.001, 0.0001, 60.0)
        graph.add_edge("Coinbase", "USDT", "Kraken", "USDC", 0.0015, 0.0002, 90.0)
        
        node1 = graph.get_node("Kraken", "USDT")
        node2 = graph.get_node("Coinbase", "USDT")
        node3 = graph.get_node("Kraken", "USDC")
        
        # Calculate total cost along path
        total_cost = 0.0
        for edge in node1.edges:
            if edge.target == node2:
                total_cost += edge.weight
        for edge in node2.edges:
            if edge.target == node3:
                total_cost += edge.weight
        
        expected_cost = (0.001 + 0.0001) + (0.0015 + 0.0002)
        self.assertAlmostEqual(total_cost, expected_cost, places=6)
    
    def test_arbitrage_condition(self):
        """Test arbitrage opportunity detection condition."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Coinbase", "USDT", 1.01)  # Higher price
        
        # Low cost edge
        graph.add_edge("Kraken", "USDT", "Coinbase", "USDT", 0.0005, 0.0001, 60.0)
        
        node1 = graph.get_node("Kraken", "USDT")
        node2 = graph.get_node("Coinbase", "USDT")
        edge = node1.edges[0]
        
        # Price difference
        price_diff = node1.price - node2.price  # 1.00 - 1.01 = -0.01
        
        # For arbitrage, we want: target_price - source_price > cost
        # Or: source_price - target_price < -cost (negative means no opportunity)
        # Actually: we want to buy low, sell high
        # So: target_price - source_price > cost (buy at source, sell at target)
        profitable = (node2.price - node1.price) > edge.weight
        
        # In this case: 1.01 - 1.00 = 0.01 > 0.0006 = True (profitable!)
        self.assertTrue(profitable)
    
    def test_profit_calculation(self):
        """Test net profit calculation."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Coinbase", "USDT", 1.01)
        
        graph.add_edge("Kraken", "USDT", "Coinbase", "USDT", 0.0005, 0.0001, 60.0)
        
        node1 = graph.get_node("Kraken", "USDT")
        node2 = graph.get_node("Coinbase", "USDT")
        edge = node1.edges[0]
        
        amount = 100.0  # Trade $100 worth
        price_diff = (node2.price - node1.price) * amount  # Profit from price difference
        total_cost = edge.weight * amount  # Total transfer cost
        
        net_profit = price_diff - total_cost
        
        # Expected: (1.01 - 1.00) * 100 - (0.0006 * 100) = 1.0 - 0.06 = 0.94
        expected_profit = (1.01 - 1.00) * 100 - (0.0006 * 100)
        self.assertAlmostEqual(net_profit, expected_profit, places=2)


if __name__ == '__main__':
    unittest.main()

