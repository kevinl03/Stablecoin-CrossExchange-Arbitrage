"""End-to-end integration tests."""

import unittest
from src import ArbitrageAgent, GraphBuilder
from src.synthetic_generator import generate_synthetic_graph


class TestEndToEnd(unittest.TestCase):
    """Test complete system workflow."""
    
    def test_complete_workflow(self):
        """Test: Graph → Agent → Opportunities."""
        # Step 1: Create graph
        graph = generate_synthetic_graph(
            num_exchanges=3,
            num_stablecoins=2,
            seed=42
        )
        
        # Step 2: Create agent
        agent = ArbitrageAgent(graph)
        
        # Step 3: Find opportunities
        opportunities = agent.find_all_opportunities(
            algorithm='astar',
            max_depth=5
        )
        
        # Step 4: Verify results structure
        self.assertIsInstance(opportunities, list)
        
        # If opportunities found, verify structure
        if opportunities:
            path, profit, cost, desc = opportunities[0]
            self.assertIsInstance(path, list)
            self.assertIsInstance(profit, float)
            self.assertIsInstance(cost, float)
            self.assertIsInstance(desc, str)
    
    def test_agent_statistics(self):
        """Test agent statistics gathering."""
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=3,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        
        stats = agent.get_statistics()
        
        self.assertIn('num_nodes', stats)
        self.assertIn('num_edges', stats)
        self.assertIn('num_exchanges', stats)
        self.assertIn('num_stablecoins', stats)
        self.assertIn('exchanges', stats)
        self.assertIn('stablecoins', stats)
        
        self.assertEqual(stats['num_exchanges'], 2)
        self.assertEqual(stats['num_stablecoins'], 3)
    
    def test_opportunity_evaluation(self):
        """Test opportunity evaluation with specific amounts."""
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        
        # Get a path (even if not profitable)
        nodes = graph.get_all_nodes()
        if len(nodes) >= 2:
            path = [nodes[0], nodes[1]]
            
            evaluation = agent.evaluate_opportunity(path, amount=100.0)
            
            self.assertIn('amount', evaluation)
            self.assertIn('net_profit', evaluation)
            self.assertIn('roi', evaluation)
            self.assertIn('profitable', evaluation)
    
    def test_graph_price_updates(self):
        """Test updating graph prices through agent."""
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        
        # Get initial price
        node = graph.get_all_nodes()[0]
        initial_price = node.price
        
        # Update through agent
        price_updates = {
            (node.exchange, node.stablecoin): initial_price + 0.01
        }
        agent.update_graph_prices(price_updates)
        
        # Verify update
        updated_node = graph.get_node(node.exchange, node.stablecoin)
        self.assertAlmostEqual(updated_node.price, initial_price + 0.01, places=2)


if __name__ == '__main__':
    unittest.main()

