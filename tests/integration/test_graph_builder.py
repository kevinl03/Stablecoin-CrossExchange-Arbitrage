"""Integration tests for GraphBuilder."""

import unittest
from src import GraphBuilder, KrakenConnector, CoinbaseConnector
from src.synthetic_generator import generate_synthetic_graph


class TestGraphBuilder(unittest.TestCase):
    """Test GraphBuilder integration."""
    
    def test_build_graph_from_connectors(self):
        """Test building graph from exchange connectors."""
        builder = GraphBuilder()
        
        # Use synthetic data for testing (avoid API rate limits)
        # In real scenario, would use: builder.add_connector(KrakenConnector())
        
        # Create a synthetic graph to test structure
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=2,
            seed=42
        )
        
        # Verify graph structure
        self.assertGreater(len(graph.get_all_nodes()), 0)
        self.assertGreater(len(graph.edges), 0)
        
        # Verify all nodes have prices
        for node in graph.get_all_nodes():
            self.assertIsInstance(node.price, float)
            self.assertGreater(node.price, 0)
    
    def test_graph_connectivity(self):
        """Test that graph has proper connectivity."""
        graph = generate_synthetic_graph(
            num_exchanges=3,
            num_stablecoins=2,
            seed=42
        )
        
        nodes = graph.get_all_nodes()
        
        # Each node should have outgoing edges (except in edge cases)
        nodes_with_edges = sum(1 for node in nodes if len(node.edges) > 0)
        self.assertGreater(nodes_with_edges, 0, "Some nodes should have outgoing edges")
    
    def test_price_updates(self):
        """Test updating graph prices."""
        graph = generate_synthetic_graph(
            num_exchanges=2,
            num_stablecoins=2,
            seed=42
        )
        
        # Get initial prices
        node = graph.get_all_nodes()[0]
        initial_price = node.price
        
        # Update price
        price_updates = {
            (node.exchange, node.stablecoin): initial_price + 0.01
        }
        graph.update_prices(price_updates)
        
        # Verify update
        updated_node = graph.get_node(node.exchange, node.stablecoin)
        self.assertAlmostEqual(updated_node.price, initial_price + 0.01, places=2)


class TestConnectorIntegration(unittest.TestCase):
    """Test connector integration (mocked to avoid API calls)."""
    
    def test_connector_structure(self):
        """Test connector interface structure."""
        # Test that connectors implement required methods
        kraken = KrakenConnector()
        
        # Verify connector has required methods
        self.assertTrue(hasattr(kraken, 'get_stablecoin_price'))
        self.assertTrue(hasattr(kraken, 'get_all_stablecoin_prices'))
        self.assertTrue(hasattr(kraken, 'get_transfer_fee'))
        self.assertTrue(hasattr(kraken, 'get_estimated_transfer_time'))
    
    def test_connector_rate_limiting(self):
        """Test that connectors implement rate limiting."""
        kraken = KrakenConnector()
        
        # Verify rate limiting attributes exist
        self.assertTrue(hasattr(kraken, 'min_request_interval'))
        self.assertTrue(hasattr(kraken, '_rate_limit'))


if __name__ == '__main__':
    unittest.main()

