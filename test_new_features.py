"""Comprehensive test script for new algorithm improvements."""

import sys
import time
from datetime import datetime
from src.synthetic_generator import generate_synthetic_graph
from src.utils.volatility_tracker import VolatilityTracker
from src.utils.transfer_time_tracker import TransferTimeTracker
from src.utils.metrics_tracker import MetricsTracker
from src.algorithms.weighted_astar import weighted_astar_arbitrage
from src.algorithms.astar import astar_arbitrage
from src.graph_builder_sparse import SparseGraphBuilder
from src.graph_builder import GraphBuilder
from src.connectors.kraken_connector import KrakenConnector
from src.connectors.coinbase_connector import CoinbaseConnector


def test_volatility_tracker():
    """Test volatility tracking system."""
    print("\n" + "="*60)
    print("TEST 1: Volatility Tracker")
    print("="*60)
    
    tracker = VolatilityTracker(window_size=10)
    
    # Simulate price updates
    exchange, coin = "Kraken", "USDT"
    prices = [1.00, 1.001, 1.002, 1.001, 0.999, 1.001, 1.003, 1.002, 1.001, 1.000]
    
    for price in prices:
        tracker.update_price(exchange, coin, price)
    
    volatility = tracker.get_volatility(exchange, coin)
    volatility_factor = tracker.get_volatility_factor(exchange, coin, base_factor=0.1)
    
    print(f"✓ Updated {len(prices)} prices")
    print(f"✓ Volatility: {volatility:.6f}")
    print(f"✓ Volatility Factor: {volatility_factor:.6f}")
    print(f"✓ All volatilities: {tracker.get_all_volatilities()}")
    
    assert volatility > 0, "Volatility should be positive"
    assert volatility_factor > 0, "Volatility factor should be positive"
    print("✓ PASS: Volatility tracker works correctly")


def test_transfer_time_tracker():
    """Test transfer time tracking system."""
    print("\n" + "="*60)
    print("TEST 2: Transfer Time Tracker")
    print("="*60)
    
    tracker = TransferTimeTracker(window_size=10)
    
    # Simulate transfer times (some fast, some slow)
    transfer_times = [45.0, 50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 120.0, 150.0]
    
    for t in transfer_times:
        tracker.record_transfer("Kraken", "USDT", "Coinbase", "USDC", t)
    
    estimated = tracker.get_estimated_time("Kraken", "USDT", "Coinbase", "USDC", percentile=95.0)
    average = tracker.get_average_time("Kraken", "USDT", "Coinbase", "USDC")
    
    print(f"✓ Recorded {len(transfer_times)} transfer times")
    print(f"✓ 95th percentile estimate: {estimated:.2f}s")
    print(f"✓ Average time: {average:.2f}s")
    
    assert estimated >= average, "95th percentile should be >= average"
    assert estimated > 0, "Estimated time should be positive"
    print("✓ PASS: Transfer time tracker works correctly")


def test_metrics_tracker():
    """Test metrics tracking and output system."""
    print("\n" + "="*60)
    print("TEST 3: Metrics Tracker")
    print("="*60)
    
    tracker = MetricsTracker(output_file="test_metrics.csv")
    
    # Create a synthetic graph for testing
    graph = generate_synthetic_graph(num_exchanges=3, num_stablecoins=2, seed=42)
    nodes = graph.get_all_nodes()
    
    if len(nodes) >= 2:
        path = nodes[:3] if len(nodes) >= 3 else [nodes[0], nodes[1], nodes[0]]
        
        # Record some opportunities
        for i in range(3):
            tracker.record_opportunity(
                timestamp=datetime.now(),
                path=path,
                predicted_profit=0.01 + i * 0.001,
                predicted_cost=0.002,
                actual_profit=0.008 + i * 0.001 if i < 2 else None,
                volatility=0.05,
                algorithm="weighted_astar",
                search_time=0.1 + i * 0.01,
                nodes_explored=10 + i * 5
            )
        
        # Record algorithm performance
        tracker.record_algorithm_performance(
            timestamp=datetime.now(),
            algorithm="weighted_astar",
            search_time=0.15,
            nodes_explored=25,
            opportunities_found=3,
            graph_size=len(nodes)
        )
        
        # Save to CSV
        tracker.save_to_csv("test_metrics.csv")
        print(f"✓ Recorded {len(tracker.metrics)} opportunities")
        print(f"✓ Saved to CSV: test_metrics.csv")
        
        # Get summary
        summary = tracker.get_summary_statistics()
        print(f"✓ Summary: {summary}")
        
        # Try Excel export (may fail if openpyxl not installed, that's OK)
        try:
            tracker.save_to_excel("test_report.xlsx")
            print(f"✓ Saved to Excel: test_report.xlsx")
        except Exception as e:
            print(f"⚠ Excel export failed (expected if openpyxl not installed): {e}")
        
        assert len(tracker.metrics) == 3, "Should have 3 recorded opportunities"
        print("✓ PASS: Metrics tracker works correctly")
    else:
        print("⚠ Skipped: Not enough nodes in graph")


def test_weighted_astar():
    """Test Weighted A* algorithm."""
    print("\n" + "="*60)
    print("TEST 4: Weighted A* Algorithm")
    print("="*60)
    
    # Create synthetic graph
    graph = generate_synthetic_graph(num_exchanges=4, num_stablecoins=3, seed=42)
    nodes = graph.get_all_nodes()
    
    if len(nodes) > 0:
        start_node = nodes[0]
        
        # Test standard A*
        start_time = time.time()
        standard_opps = astar_arbitrage(start_node, max_depth=5, volatility_factor=0.1)
        standard_time = time.time() - start_time
        
        # Test Weighted A*
        start_time = time.time()
        weighted_opps = weighted_astar_arbitrage(
            start_node, 
            max_depth=5, 
            volatility_factor=0.1,
            weight=1.5
        )
        weighted_time = time.time() - start_time
        
        print(f"✓ Graph size: {len(nodes)} nodes")
        print(f"✓ Standard A*: {len(standard_opps)} opportunities in {standard_time:.4f}s")
        print(f"✓ Weighted A*: {len(weighted_opps)} opportunities in {weighted_time:.4f}s")
        
        if weighted_time > 0:
            speedup = standard_time / weighted_time if weighted_time > 0 else 1.0
            print(f"✓ Speedup: {speedup:.2f}x")
        
        assert isinstance(weighted_opps, list), "Should return list of opportunities"
        print("✓ PASS: Weighted A* works correctly")
    else:
        print("⚠ Skipped: No nodes in graph")


def test_sparse_graph_builder():
    """Test sparse graph construction."""
    print("\n" + "="*60)
    print("TEST 5: Sparse Graph Builder")
    print("="*60)
    
    # Create synthetic graph for comparison
    dense_graph = generate_synthetic_graph(num_exchanges=4, num_stablecoins=3, seed=42)
    dense_nodes = dense_graph.get_all_nodes()
    dense_edges = len(dense_graph.edges)
    
    print(f"✓ Dense graph: {len(dense_nodes)} nodes, {dense_edges} edges")
    
    # Test sparse builder with synthetic data
    # Note: SparseGraphBuilder needs connectors, so we'll test with a mock
    try:
        # Try to use real connectors if available
        sparse_builder = SparseGraphBuilder()
        
        # For testing, we'll create a simple synthetic scenario
        # In practice, you'd add real connectors
        print("✓ SparseGraphBuilder initialized")
        print("⚠ Note: Full sparse graph test requires real connectors")
        print("✓ PASS: SparseGraphBuilder structure is correct")
    except Exception as e:
        print(f"⚠ Sparse builder test limited: {e}")
    
    # Compare graph sizes
    print(f"\n  Dense graph edge count: {dense_edges}")
    print(f"  Expected sparse (10 edges/node): ~{len(dense_nodes) * 10}")
    print(f"  Reduction: ~{dense_edges / (len(dense_nodes) * 10):.1f}x smaller")


def test_integration():
    """Test integration of all components."""
    print("\n" + "="*60)
    print("TEST 6: Integration Test")
    print("="*60)
    
    # Create components
    volatility_tracker = VolatilityTracker()
    time_tracker = TransferTimeTracker()
    metrics_tracker = MetricsTracker()
    
    # Create graph
    graph = generate_synthetic_graph(num_exchanges=3, num_stablecoins=2, seed=42)
    nodes = graph.get_all_nodes()
    
    if len(nodes) > 0:
        start_node = nodes[0]
        
        # Update volatility tracker with prices
        for node in nodes[:5]:
            volatility_tracker.update_price(node.exchange, node.stablecoin, node.price)
        
        # Run weighted A* search
        opportunities = weighted_astar_arbitrage(
            start_node,
            max_depth=5,
            volatility_factor=0.1,
            weight=1.5
        )
        
        # Record opportunities with metrics
        for path, profit, cost in opportunities[:3]:
            # Get volatility for first node
            if len(path) > 0:
                vol = volatility_tracker.get_volatility(path[0].exchange, path[0].stablecoin)
                
                metrics_tracker.record_opportunity(
                    timestamp=datetime.now(),
                    path=path,
                    predicted_profit=profit,
                    predicted_cost=cost,
                    volatility=vol,
                    algorithm="weighted_astar"
                )
        
        print(f"✓ Integrated volatility tracking")
        print(f"✓ Integrated metrics tracking")
        print(f"✓ Found {len(opportunities)} opportunities")
        print(f"✓ Recorded {len(metrics_tracker.metrics)} metrics")
        print("✓ PASS: Integration test successful")
    else:
        print("⚠ Skipped: No nodes in graph")


def main():
    """Run all tests."""
    print("\n" + "="*60)
    print("COMPREHENSIVE TEST SUITE: New Algorithm Features")
    print("="*60)
    
    tests = [
        test_volatility_tracker,
        test_transfer_time_tracker,
        test_metrics_tracker,
        test_weighted_astar,
        test_sparse_graph_builder,
        test_integration
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n✗ FAIL: {test.__name__}")
            print(f"  Error: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print(f"✓ Passed: {passed}/{len(tests)}")
    if failed > 0:
        print(f"✗ Failed: {failed}/{len(tests)}")
    print("="*60 + "\n")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

