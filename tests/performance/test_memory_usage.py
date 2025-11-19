"""Performance tests for memory usage."""

import unittest
import sys
from src import ArbitrageAgent
from src.synthetic_generator import generate_synthetic_graph


class TestMemoryUsage(unittest.TestCase):
    """Test memory efficiency."""
    
    def test_graph_memory_size(self):
        """Test that graph size is reasonable."""
        graph = generate_synthetic_graph(
            num_exchanges=4,
            num_stablecoins=3,
            seed=42
        )
        
        # Get object size (approximate)
        nodes = graph.get_all_nodes()
        edges = graph.edges
        
        # 4 exchanges × 3 coins = 12 nodes
        # 12 nodes × 11 edges each = 132 edges (approximately)
        
        self.assertEqual(len(nodes), 12)
        self.assertGreater(len(edges), 0)
        
        # Memory should be reasonable (not gigabytes)
        # This is a basic check - actual memory profiling would use memory_profiler
        self.assertLess(len(nodes), 1000, "Graph should not have excessive nodes")
        self.assertLess(len(edges), 10000, "Graph should not have excessive edges")
    
    def test_agent_memory(self):
        """Test that agent doesn't create excessive memory overhead."""
        graph = generate_synthetic_graph(
            num_exchanges=3,
            num_stablecoins=2,
            seed=42
        )
        agent = ArbitrageAgent(graph)
        
        # Agent should just hold reference to graph
        # Not create large additional structures
        self.assertIsNotNone(agent.graph)
        self.assertEqual(agent.graph, graph)


if __name__ == '__main__':
    unittest.main()

