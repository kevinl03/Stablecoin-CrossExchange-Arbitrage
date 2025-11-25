"""Unit tests for optimized priority queue."""

import unittest
from src.models.exchange_node import ExchangeNode
from src.utils.optimized_heap import OptimizedPriorityQueue, OptimizedPriorityQueueWithPath


class TestOptimizedPriorityQueue(unittest.TestCase):
    """Test cases for OptimizedPriorityQueue."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.queue = OptimizedPriorityQueue()
        self.node1 = ExchangeNode("Kraken", "USDT", 1.0)
        self.node2 = ExchangeNode("Coinbase", "USDC", 1.0)
        self.node3 = ExchangeNode("Binance", "BUSD", 1.0)
    
    def test_push_pop(self):
        """Test basic push and pop operations."""
        self.queue.push(1.0, self.node1)
        self.queue.push(2.0, self.node2)
        self.queue.push(0.5, self.node3)
        
        priority, node = self.queue.pop()
        self.assertEqual(priority, 0.5)
        self.assertEqual(node, self.node3)
        
        priority, node = self.queue.pop()
        self.assertEqual(priority, 1.0)
        self.assertEqual(node, self.node1)
        
        priority, node = self.queue.pop()
        self.assertEqual(priority, 2.0)
        self.assertEqual(node, self.node2)
    
    def test_empty(self):
        """Test empty queue behavior."""
        self.assertTrue(self.queue.empty())
        self.assertEqual(len(self.queue), 0)
        
        self.queue.push(1.0, self.node1)
        self.assertFalse(self.queue.empty())
        self.assertEqual(len(self.queue), 1)
    
    def test_peek(self):
        """Test peek operation."""
        self.assertIsNone(self.queue.peek())
        
        self.queue.push(1.0, self.node1)
        self.queue.push(0.5, self.node2)
        
        priority, node = self.queue.peek()
        self.assertEqual(priority, 0.5)
        self.assertEqual(node, self.node2)
        # Queue should still have 2 items
        self.assertEqual(len(self.queue), 2)
    
    def test_clear(self):
        """Test clear operation."""
        self.queue.push(1.0, self.node1)
        self.queue.push(2.0, self.node2)
        self.assertEqual(len(self.queue), 2)
        
        self.queue.clear()
        self.assertTrue(self.queue.empty())
        self.assertEqual(len(self.queue), 0)
    
    def test_node_index_reuse(self):
        """Test that node indices are reused correctly."""
        self.queue.push(1.0, self.node1)
        self.queue.push(2.0, self.node1)  # Same node, different priority
        
        # Should have 2 entries in heap
        self.assertEqual(len(self.queue), 2)
        
        # Both should reference same node
        priority1, node1 = self.queue.pop()
        priority2, node2 = self.queue.pop()
        self.assertEqual(node1, node2)
        self.assertEqual(node1, self.node1)


class TestOptimizedPriorityQueueWithPath(unittest.TestCase):
    """Test cases for OptimizedPriorityQueueWithPath."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.queue = OptimizedPriorityQueueWithPath()
        self.node1 = ExchangeNode("Kraken", "USDT", 1.0)
        self.node2 = ExchangeNode("Coinbase", "USDC", 1.0)
        self.node3 = ExchangeNode("Binance", "BUSD", 1.0)
    
    def test_push_pop(self):
        """Test push and pop with path."""
        self.queue.push(1.0, 0.5, self.node1, [self.node1], 0)
        self.queue.push(2.0, 1.0, self.node2, [self.node1, self.node2], 1)
        self.queue.push(0.5, 0.2, self.node3, [self.node1, self.node3], 1)
        
        f_cost, total_cost, node, path, depth = self.queue.pop()
        self.assertEqual(f_cost, 0.5)
        self.assertEqual(total_cost, 0.2)
        self.assertEqual(node, self.node3)
        self.assertEqual(len(path), 2)
        self.assertEqual(depth, 1)
    
    def test_empty(self):
        """Test empty queue."""
        self.assertTrue(self.queue.empty())
        self.assertEqual(len(self.queue), 0)
    
    def test_path_preservation(self):
        """Test that paths are correctly preserved."""
        path = [self.node1, self.node2, self.node3]
        self.queue.push(1.0, 0.5, self.node3, path, 2)
        
        f_cost, total_cost, node, popped_path, depth = self.queue.pop()
        self.assertEqual(len(popped_path), 3)
        self.assertEqual(popped_path[0], self.node1)
        self.assertEqual(popped_path[1], self.node2)
        self.assertEqual(popped_path[2], self.node3)
        self.assertEqual(node, self.node3)


if __name__ == '__main__':
    unittest.main()

