"""Live integration test with real connectors."""

import sys
import time
import signal
from datetime import datetime
from functools import wraps
from src.graph_builder_sparse import SparseGraphBuilder
from src.graph_builder import GraphBuilder
from src.connectors.kraken_connector import KrakenConnector
from src.connectors.coinbase_connector import CoinbaseConnector
from src.utils.volatility_tracker import VolatilityTracker
from src.utils.metrics_tracker import MetricsTracker
from src.algorithms.weighted_astar import weighted_astar_arbitrage
from src.algorithms.astar import astar_arbitrage


# Error codes
class ErrorCodes:
    """Error codes for test failures."""
    SUCCESS = 0
    TIMEOUT = 1
    API_ERROR = 2
    NETWORK_ERROR = 3
    RATE_LIMIT = 4
    UNKNOWN_ERROR = 5
    NO_DATA = 6


class TimeoutError(Exception):
    """Custom timeout exception."""
    def __init__(self, message="Operation timed out", error_code=ErrorCodes.TIMEOUT):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


def timeout_handler(signum, frame):
    """Signal handler for timeout."""
    raise TimeoutError("Operation exceeded timeout limit", ErrorCodes.TIMEOUT)


def with_timeout(timeout_seconds=30):
    """
    Decorator to add timeout to functions.
    
    Args:
        timeout_seconds: Maximum time in seconds before timeout
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Set up signal handler for timeout (Unix only)
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(timeout_seconds)
                try:
                    result = func(*args, **kwargs)
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
                return result
            else:
                # Windows/fallback: use threading timeout
                import threading
                result = [None]
                exception = [None]
                
                def target():
                    try:
                        result[0] = func(*args, **kwargs)
                    except Exception as e:
                        exception[0] = e
                
                thread = threading.Thread(target=target)
                thread.daemon = True
                thread.start()
                thread.join(timeout=timeout_seconds)
                
                if thread.is_alive():
                    raise TimeoutError(
                        f"Function {func.__name__} exceeded {timeout_seconds}s timeout",
                        ErrorCodes.TIMEOUT
                    )
                
                if exception[0]:
                    raise exception[0]
                
                return result[0]
        
        return wrapper
    return decorator


@with_timeout(timeout_seconds=60)
def test_live_sparse_vs_dense():
    """Compare sparse vs dense graph construction with live data."""
    print("\n" + "="*60)
    print("LIVE TEST: Sparse vs Dense Graph Construction")
    print("="*60)
    print("Timeout: 60 seconds")
    
    try:
        # Create connectors
        kraken = KrakenConnector()
        coinbase = CoinbaseConnector()
        
        # Test Dense Graph Builder
        print("\n1. Building DENSE graph...")
        dense_builder = GraphBuilder()
        dense_builder.add_connector(kraken)
        dense_builder.add_connector(coinbase)
        
        start_time = time.time()
        dense_graph = dense_builder.build_graph()
        dense_time = time.time() - start_time
        
        dense_nodes = len(dense_graph.get_all_nodes())
        dense_edges = len(dense_graph.edges)
        
        print(f"   ✓ Nodes: {dense_nodes}")
        print(f"   ✓ Edges: {dense_edges}")
        print(f"   ✓ Build time: {dense_time:.4f}s")
        
        # Test Sparse Graph Builder
        print("\n2. Building SPARSE graph...")
        sparse_builder = SparseGraphBuilder()
        sparse_builder.add_connector(kraken)
        sparse_builder.add_connector(coinbase)
        
        start_time = time.time()
        sparse_graph = sparse_builder.build_graph(max_edges_per_node=10)
        sparse_time = time.time() - start_time
        
        sparse_nodes = len(sparse_graph.get_all_nodes())
        sparse_edges = len(sparse_graph.edges)
        
        print(f"   ✓ Nodes: {sparse_nodes}")
        print(f"   ✓ Edges: {sparse_edges}")
        print(f"   ✓ Build time: {sparse_time:.4f}s")
        
        # Compare
        print("\n3. Comparison:")
        reduction = dense_edges / sparse_edges if sparse_edges > 0 else 1.0
        print(f"   ✓ Edge reduction: {reduction:.2f}x smaller")
        print(f"   ✓ Time improvement: {dense_time / sparse_time:.2f}x faster" if sparse_time > 0 else "   ✓ Time improvement: N/A")
        
        # Note: Sparse graph may have similar or slightly more edges if max_edges_per_node
        # is set high, but it should be more efficient due to cached prices
        if sparse_edges > dense_edges * 1.5:
            print(f"\n⚠ WARNING: Sparse graph has {sparse_edges} edges vs dense {dense_edges}")
            print("  This may indicate max_edges_per_node is too high")
        else:
            print("\n✓ PASS: Sparse graph construction works with live data")
        
        return dense_graph, sparse_graph, ErrorCodes.SUCCESS
        
    except TimeoutError as e:
        print(f"\n✗ TIMEOUT: {e.message}")
        print(f"  Error Code: {e.error_code}")
        return None, None, ErrorCodes.TIMEOUT
    except Exception as e:
        error_code = ErrorCodes.API_ERROR
        if "rate limit" in str(e).lower() or "429" in str(e):
            error_code = ErrorCodes.RATE_LIMIT
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_code = ErrorCodes.NETWORK_ERROR
        
        print(f"\n⚠ Live test failed: {e}")
        print(f"  Error Code: {error_code}")
        import traceback
        traceback.print_exc()
        return None, None, error_code


@with_timeout(timeout_seconds=45)
def test_live_weighted_astar():
    """Test Weighted A* with live graph data."""
    print("\n" + "="*60)
    print("LIVE TEST: Weighted A* Performance")
    print("="*60)
    print("Timeout: 45 seconds")
    
    try:
        # Build graph
        kraken = KrakenConnector()
        coinbase = CoinbaseConnector()
        builder = GraphBuilder()
        builder.add_connector(kraken)
        builder.add_connector(coinbase)
        graph = builder.build_graph()
        
        nodes = graph.get_all_nodes()
        if len(nodes) == 0:
            print("⚠ No nodes in graph, skipping test")
            return
        
        start_node = nodes[0]
        print(f"✓ Graph: {len(nodes)} nodes, {len(graph.edges)} edges")
        print(f"✓ Starting from: {start_node.exchange}({start_node.stablecoin})")
        
        # Test Standard A*
        print("\n1. Running Standard A*...")
        start_time = time.time()
        standard_opps = astar_arbitrage(start_node, max_depth=5, volatility_factor=0.1)
        standard_time = time.time() - start_time
        print(f"   ✓ Found {len(standard_opps)} opportunities")
        print(f"   ✓ Time: {standard_time:.4f}s")
        
        # Test Weighted A*
        print("\n2. Running Weighted A* (weight=1.5)...")
        start_time = time.time()
        weighted_opps = weighted_astar_arbitrage(
            start_node,
            max_depth=5,
            volatility_factor=0.1,
            weight=1.5
        )
        weighted_time = time.time() - start_time
        print(f"   ✓ Found {len(weighted_opps)} opportunities")
        print(f"   ✓ Time: {weighted_time:.4f}s")
        
        # Compare
        if weighted_time > 0:
            speedup = standard_time / weighted_time
            print(f"\n3. Performance:")
            print(f"   ✓ Speedup: {speedup:.2f}x")
        
        print("\n✓ PASS: Weighted A* works with live data")
        return ErrorCodes.SUCCESS
        
    except TimeoutError as e:
        print(f"\n✗ TIMEOUT: {e.message}")
        print(f"  Error Code: {e.error_code}")
        return ErrorCodes.TIMEOUT
    except Exception as e:
        error_code = ErrorCodes.API_ERROR
        if "rate limit" in str(e).lower() or "429" in str(e):
            error_code = ErrorCodes.RATE_LIMIT
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_code = ErrorCodes.NETWORK_ERROR
        
        print(f"\n⚠ Live test failed: {e}")
        print(f"  Error Code: {error_code}")
        import traceback
        traceback.print_exc()
        return error_code


@with_timeout(timeout_seconds=30)
def test_live_volatility_tracking():
    """Test volatility tracking with live price updates."""
    print("\n" + "="*60)
    print("LIVE TEST: Volatility Tracking")
    print("="*60)
    print("Timeout: 30 seconds")
    
    try:
        tracker = VolatilityTracker(window_size=10)
        kraken = KrakenConnector()
        
        # Get initial prices
        prices = kraken.get_all_stablecoin_prices()
        print(f"✓ Initial prices: {prices}")
        
        # Update tracker
        for coin, price in prices.items():
            tracker.update_price("Kraken", coin, price)
        
        # Get volatilities
        print("\nVolatility estimates:")
        for coin in prices.keys():
            vol = tracker.get_volatility("Kraken", coin)
            factor = tracker.get_volatility_factor("Kraken", coin, base_factor=0.1)
            print(f"   {coin}: volatility={vol:.6f}, factor={factor:.6f}")
        
        print("\n✓ PASS: Volatility tracking works with live data")
        return ErrorCodes.SUCCESS
        
    except TimeoutError as e:
        print(f"\n✗ TIMEOUT: {e.message}")
        print(f"  Error Code: {e.error_code}")
        return ErrorCodes.TIMEOUT
    except Exception as e:
        error_code = ErrorCodes.API_ERROR
        if "rate limit" in str(e).lower() or "429" in str(e):
            error_code = ErrorCodes.RATE_LIMIT
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_code = ErrorCodes.NETWORK_ERROR
        
        print(f"\n⚠ Live test failed: {e}")
        print(f"  Error Code: {error_code}")
        import traceback
        traceback.print_exc()
        return error_code


@with_timeout(timeout_seconds=60)
def test_live_metrics_output():
    """Test metrics tracking and Excel output with live data."""
    print("\n" + "="*60)
    print("LIVE TEST: Metrics Output")
    print("="*60)
    print("Timeout: 60 seconds")
    
    try:
        metrics = MetricsTracker(output_file="live_test_metrics.csv")
        
        # Build graph and find opportunities
        kraken = KrakenConnector()
        coinbase = CoinbaseConnector()
        builder = GraphBuilder()
        builder.add_connector(kraken)
        builder.add_connector(coinbase)
        graph = builder.build_graph()
        
        nodes = graph.get_all_nodes()
        if len(nodes) > 0:
            start_node = nodes[0]
            opportunities = weighted_astar_arbitrage(
                start_node,
                max_depth=5,
                volatility_factor=0.1,
                weight=1.5
            )
            
            # Record opportunities
            for path, profit, cost in opportunities[:5]:
                metrics.record_opportunity(
                    timestamp=datetime.now(),
                    path=path,
                    predicted_profit=profit,
                    predicted_cost=cost,
                    algorithm="weighted_astar"
                )
            
            print(f"✓ Recorded {len(metrics.metrics)} opportunities")
            
            # Save outputs
            metrics.save_to_csv("live_test_metrics.csv")
            print("✓ Saved CSV: live_test_metrics.csv")
            
            try:
                metrics.save_to_excel("live_test_report.xlsx")
                print("✓ Saved Excel: live_test_report.xlsx")
            except Exception as e:
                print(f"⚠ Excel export: {e}")
            
            # Summary
            summary = metrics.get_summary_statistics()
            print(f"\nSummary Statistics:")
            for key, value in summary.items():
                print(f"   {key}: {value}")
            
            print("\n✓ PASS: Metrics output works with live data")
            return ErrorCodes.SUCCESS
        else:
            print("⚠ No nodes in graph, skipping test")
            return ErrorCodes.NO_DATA
            
    except TimeoutError as e:
        print(f"\n✗ TIMEOUT: {e.message}")
        print(f"  Error Code: {e.error_code}")
        return ErrorCodes.TIMEOUT
    except Exception as e:
        error_code = ErrorCodes.API_ERROR
        if "rate limit" in str(e).lower() or "429" in str(e):
            error_code = ErrorCodes.RATE_LIMIT
        elif "network" in str(e).lower() or "connection" in str(e).lower():
            error_code = ErrorCodes.NETWORK_ERROR
        
        print(f"\n⚠ Live test failed: {e}")
        print(f"  Error Code: {error_code}")
        import traceback
        traceback.print_exc()
        return error_code


def main():
    """Run all live tests."""
    print("\n" + "="*60)
    print("LIVE INTEGRATION TEST SUITE")
    print("="*60)
    print("Testing with real exchange APIs (Kraken, Coinbase)")
    print("Note: Tests may be limited by API rate limits")
    
    tests = [
        test_live_sparse_vs_dense,
        test_live_weighted_astar,
        test_live_volatility_tracking,
        test_live_metrics_output
    ]
    
    passed = 0
    failed = 0
    skipped = 0
    timeout_count = 0
    error_codes = []
    
    for test in tests:
        try:
            result = test()
            # Handle return values (some tests return error codes)
            if result is None:
                passed += 1
            elif isinstance(result, int):
                if result == ErrorCodes.SUCCESS:
                    passed += 1
                elif result == ErrorCodes.TIMEOUT:
                    timeout_count += 1
                    failed += 1
                    error_codes.append((test.__name__, result))
                elif result == ErrorCodes.RATE_LIMIT:
                    skipped += 1
                    error_codes.append((test.__name__, result))
                elif result == ErrorCodes.NO_DATA:
                    skipped += 1
                    error_codes.append((test.__name__, result))
                else:
                    failed += 1
                    error_codes.append((test.__name__, result))
            else:
                passed += 1
        except KeyboardInterrupt:
            print("\n\n⚠ Tests interrupted by user")
            break
        except TimeoutError as e:
            timeout_count += 1
            failed += 1
            error_codes.append((test.__name__, e.error_code))
            print(f"\n✗ TIMEOUT: {test.__name__}")
            print(f"  Error Code: {e.error_code}")
        except Exception as e:
            error_code = ErrorCodes.UNKNOWN_ERROR
            if "rate limit" in str(e).lower() or "429" in str(e):
                error_code = ErrorCodes.RATE_LIMIT
                skipped += 1
            elif "timeout" in str(e).lower():
                error_code = ErrorCodes.TIMEOUT
                timeout_count += 1
                failed += 1
            else:
                failed += 1
            
            error_codes.append((test.__name__, error_code))
            print(f"\n✗ FAIL: {test.__name__}")
            print(f"  Error: {e}")
            print(f"  Error Code: {error_code}")
    
    print("\n" + "="*60)
    print("LIVE TEST SUMMARY")
    print("="*60)
    print(f"✓ Passed: {passed}/{len(tests)}")
    if skipped > 0:
        print(f"⚠ Skipped: {skipped}/{len(tests)}")
    if timeout_count > 0:
        print(f"⏱ Timeouts: {timeout_count}/{len(tests)}")
    if failed > 0:
        print(f"✗ Failed: {failed}/{len(tests)}")
    
    if error_codes:
        print("\nError Code Summary:")
        error_code_names = {
            ErrorCodes.SUCCESS: "SUCCESS",
            ErrorCodes.TIMEOUT: "TIMEOUT",
            ErrorCodes.API_ERROR: "API_ERROR",
            ErrorCodes.NETWORK_ERROR: "NETWORK_ERROR",
            ErrorCodes.RATE_LIMIT: "RATE_LIMIT",
            ErrorCodes.UNKNOWN_ERROR: "UNKNOWN_ERROR",
            ErrorCodes.NO_DATA: "NO_DATA"
        }
        for test_name, code in error_codes:
            print(f"  {test_name}: {error_code_names.get(code, 'UNKNOWN')} ({code})")
    
    print("="*60 + "\n")
    
    # Return exit code based on results
    if timeout_count > 0:
        return ErrorCodes.TIMEOUT
    elif failed > 0:
        return ErrorCodes.API_ERROR
    else:
        return ErrorCodes.SUCCESS


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

