"""Unit tests for data models (ExchangeNode, Edge, Graph)."""

import unittest
from src.models import ExchangeNode, Edge, ArbitrageGraph


class TestExchangeNode(unittest.TestCase):
    """Test ExchangeNode data model."""
    
    def test_node_creation(self):
        """Test creating an ExchangeNode."""
        node = ExchangeNode("Kraken", "USDT", 1.00)
        self.assertEqual(node.exchange, "Kraken")
        self.assertEqual(node.stablecoin, "USDT")
        self.assertEqual(node.price, 1.00)
        self.assertEqual(len(node.edges), 0)
    
    def test_node_equality(self):
        """Test node equality based on exchange and stablecoin."""
        node1 = ExchangeNode("Kraken", "USDT", 1.00)
        node2 = ExchangeNode("Kraken", "USDT", 1.01)  # Different price
        node3 = ExchangeNode("Coinbase", "USDT", 1.00)  # Different exchange
        
        self.assertEqual(node1, node2)  # Same exchange/coin
        self.assertNotEqual(node1, node3)  # Different exchange
    
    def test_node_hash(self):
        """Test node hashing."""
        node1 = ExchangeNode("Kraken", "USDT", 1.00)
        node2 = ExchangeNode("Kraken", "USDT", 1.01)
        
        # Same exchange/coin should have same hash
        self.assertEqual(hash(node1), hash(node2))
        
        # Can be used in sets
        node_set = {node1, node2}
        self.assertEqual(len(node_set), 1)  # Only one unique node
    
    def test_add_edge(self):
        """Test adding edges to a node."""
        node1 = ExchangeNode("Kraken", "USDT", 1.00)
        node2 = ExchangeNode("Coinbase", "USDT", 1.01)
        edge = Edge(node1, node2, 0.001, 0.0001, 60.0)
        
        node1.add_edge(edge)
        self.assertEqual(len(node1.edges), 1)
        self.assertEqual(node1.edges[0], edge)


class TestEdge(unittest.TestCase):
    """Test Edge data model."""
    
    def test_edge_creation(self):
        """Test creating an Edge."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target = ExchangeNode("Coinbase", "USDT", 1.01)
        edge = Edge(source, target, 0.001, 0.0001, 60.0)
        
        self.assertEqual(edge.source, source)
        self.assertEqual(edge.target, target)
        self.assertEqual(edge.fee, 0.001)
        self.assertEqual(edge.volatility_cost, 0.0001)
        self.assertEqual(edge.transfer_time, 60.0)
        self.assertEqual(edge.weight, 0.0011)  # fee + volatility_cost
    
    def test_edge_weight_calculation(self):
        """Test edge weight is sum of fee and volatility."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target = ExchangeNode("Coinbase", "USDT", 1.01)
        edge = Edge(source, target, 0.002, 0.0005, 120.0)
        
        expected_weight = 0.002 + 0.0005
        self.assertEqual(edge.weight, expected_weight)
    
    def test_update_volatility_cost(self):
        """Test updating volatility cost recalculates weight."""
        source = ExchangeNode("Kraken", "USDT", 1.00)
        target = ExchangeNode("Coinbase", "USDT", 1.01)
        edge = Edge(source, target, 0.001, 0.0001, 60.0)
        
        initial_weight = edge.weight
        edge.update_volatility_cost(0.0005)
        
        self.assertEqual(edge.volatility_cost, 0.0005)
        self.assertEqual(edge.weight, 0.001 + 0.0005)
        self.assertNotEqual(edge.weight, initial_weight)


class TestArbitrageGraph(unittest.TestCase):
    """Test ArbitrageGraph data structure."""
    
    def test_graph_creation(self):
        """Test creating an empty graph."""
        graph = ArbitrageGraph()
        self.assertEqual(len(graph.nodes), 0)
        self.assertEqual(len(graph.edges), 0)
    
    def test_add_node(self):
        """Test adding nodes to graph."""
        graph = ArbitrageGraph()
        node = graph.add_node("Kraken", "USDT", 1.00)
        
        self.assertEqual(len(graph.nodes), 1)
        self.assertEqual(graph.get_node("Kraken", "USDT"), node)
        self.assertEqual(node.price, 1.00)
    
    def test_update_node_price(self):
        """Test updating existing node price."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        node = graph.add_node("Kraken", "USDT", 1.01)  # Update price
        
        self.assertEqual(len(graph.nodes), 1)  # Still one node
        self.assertEqual(node.price, 1.01)  # Price updated
    
    def test_add_edge(self):
        """Test adding edges between nodes."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Coinbase", "USDT", 1.01)
        
        edge = graph.add_edge(
            "Kraken", "USDT",
            "Coinbase", "USDT",
            0.001, 0.0001, 60.0
        )
        
        self.assertEqual(len(graph.edges), 1)
        self.assertEqual(edge.source.exchange, "Kraken")
        self.assertEqual(edge.target.exchange, "Coinbase")
    
    def test_add_edge_invalid_nodes(self):
        """Test adding edge with non-existent nodes raises error."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        # Don't add Coinbase node
        
        with self.assertRaises(ValueError):
            graph.add_edge(
                "Kraken", "USDT",
                "Coinbase", "USDT",
                0.001, 0.0001, 60.0
            )
    
    def test_update_prices(self):
        """Test bulk price updates."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Coinbase", "USDT", 1.01)
        
        price_updates = {
            ("Kraken", "USDT"): 1.02,
            ("Coinbase", "USDT"): 1.03
        }
        graph.update_prices(price_updates)
        
        self.assertEqual(graph.get_node("Kraken", "USDT").price, 1.02)
        self.assertEqual(graph.get_node("Coinbase", "USDT").price, 1.03)
    
    def test_get_all_nodes(self):
        """Test retrieving all nodes."""
        graph = ArbitrageGraph()
        graph.add_node("Kraken", "USDT", 1.00)
        graph.add_node("Kraken", "USDC", 0.99)
        graph.add_node("Coinbase", "USDT", 1.01)
        
        nodes = graph.get_all_nodes()
        self.assertEqual(len(nodes), 3)


if __name__ == '__main__':
    unittest.main()

