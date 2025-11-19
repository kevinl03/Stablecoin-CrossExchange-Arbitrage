"""Performance tests for algorithm efficiency."""

import unittest
import time
from src import ArbitrageAgent
from src.synthetic_generator import generate_synthetic_graph


class TestAlgorithmPerformance(unittest.TestCase):
    """Test algorithm performance and scalability."""
    
    def test_dijkstra_performance_small(self):
        """Test Dijkstra performance on small graph."""
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        start_node = graph.get_all_nodes()[0]
        
        start_time = time.time()
        opportunities = agent.find_arbitrage_paths(
            start_node,
            algorithm='dijkstra',
            max_depth=5
        )
        elapsed = time.time() - start_time
        
        # Small graph should complete quickly
        self.assertLess(elapsed, 1.0, "Small graph should complete in < 1 second")
        self.assertIsInstance(opportunities, list)
    
    def test_astar_performance_small(self):
        """Test A* performance on small graph."""
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        start_node = graph.get_all_nodes()[0]
        
        start_time = time.time()
        opportunities = agent.find_arbitrage_paths(
            start_node,
            algorithm='astar',
            max_depth=5
        )
        elapsed = time.time() - start_time
        
        # A* should be comparable or faster than Dijkstra
        self.assertLess(elapsed, 1.0, "A* should complete in < 1 second")
        self.assertIsInstance(opportunities, list)
    
    def test_medium_graph_performance(self):
        """Test performance on medium-sized graph."""
        graph = generate_synthetic_graph(
            num_exchanges=4,
            num_stablecoins=3,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        
        start_time = time.time()
        opportunities = agent.find_all_opportunities(
            algorithm='astar',
            max_depth=5
        )
        elapsed = time.time() - start_time
        
        # Medium graph: 4 exchanges × 3 coins = 12 nodes
        # Should complete in reasonable time
        self.assertLess(elapsed, 10.0, "Medium graph should complete in < 10 seconds")
        self.assertIsInstance(opportunities, list)
    
    def test_algorithm_comparison(self):
        """Compare Dijkstra vs A* performance."""
        graph = generate_synthetic_graph(
            num_exchanges=3,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        start_node = graph.get_all_nodes()[0]
        
        # Test Dijkstra
        start_time = time.time()
        dijkstra_opps = agent.find_arbitrage_paths(
            start_node,
            algorithm='dijkstra',
            max_depth=5
        )
        dijkstra_time = time.time() - start_time
        
        # Test A*
        start_time = time.time()
        astar_opps = agent.find_arbitrage_paths(
            start_node,
            algorithm='astar',
            max_depth=5
        )
        astar_time = time.time() - start_time
        
        # Both should complete
        self.assertIsInstance(dijkstra_opps, list)
        self.assertIsInstance(astar_opps, list)
        
        # Performance should be reasonable for both
        self.assertLess(dijkstra_time, 5.0)
        self.assertLess(astar_time, 5.0)
    
    def test_scalability(self):
        """Test performance with increasing graph size."""
        sizes = [
            (2, 2),  # 4 nodes
            (3, 2),  # 6 nodes
            (4, 2),  # 8 nodes
        ]
        
        times = []
        for num_exchanges, num_stablecoins in sizes:
            graph = generate_synthetic_graph(
                num_exchanges=num_exchanges,
                num_stablecoins=num_stablecoins,
                seed=42
            )
            agent = ArbitrageAgent(graph)
            start_node = graph.get_all_nodes()[0]
            
            start_time = time.time()
            opportunities = agent.find_arbitrage_paths(
                start_node,
                algorithm='astar',
                max_depth=5
            )
            elapsed = time.time() - start_time
            times.append(elapsed)
        
        # Performance should scale reasonably (not exponentially)
        # Times should increase but not dramatically
        if len(times) >= 2:
            # Second size shouldn't take 10x longer than first
            self.assertLess(times[1], times[0] * 10, 
                          "Performance should scale reasonably")
    
    def test_two_level_search_performance(self):
        """Test two-level search performance."""
        graph = generate_synthetic_graph(
            num_exchanges=3,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        
        start_time = time.time()
        opportunities = agent.find_all_opportunities(
            algorithm='astar',
            max_depth=5
        )
        elapsed = time.time() - start_time
        
        # Two-level search explores more combinations
        # Should still complete in reasonable time
        self.assertLess(elapsed, 15.0, 
                       "Two-level search should complete in < 15 seconds")
        self.assertIsInstance(opportunities, list)


if __name__ == '__main__':
    unittest.main()

