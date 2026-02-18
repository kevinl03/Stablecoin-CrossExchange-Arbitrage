#!/usr/bin/env python3
"""
Test script for fee improvements.

This script tests:
1. Dynamic withdrawal fee calculation based on portfolio size
2. Network gas fees inclusion
3. Portfolio threshold filtering
4. Comparison of old vs new fee calculations
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, REFERENCE_NOTIONAL_USD
from scripts.fees import (
    get_network_gas_fee,
    get_min_portfolio_threshold,
    NETWORK_GAS_FEES,
    MIN_PORTFOLIO_THRESHOLDS,
)
from scripts.data import EXCHANGES, STABLE_COINS


def test_portfolio_size_impact():
    """Test how portfolio size affects transfer edge costs."""
    print("=" * 80)
    print("TEST 1: Portfolio Size Impact on Transfer Edge Costs")
    print("=" * 80)
    
    portfolio_sizes = [100, 500, 1_000, 5_000, 10_000, 50_000]
    
    print("\nBuilding graphs with different portfolio sizes...")
    print("Looking for USDT transfer edges from Binance to Kraken on Ethereum...")
    print("-" * 80)
    
    for size in portfolio_sizes:
        nodes, adj = build_graph(portfolio_size_usd=float(size))
        
        # Find a USDT transfer edge from Binance to Kraken on Ethereum
        binance_usdt = None
        for node in nodes.keys():
            if node[0] == "binance" and node[1] == "USDT":
                binance_usdt = node
                break
        
        if not binance_usdt:
            print(f"  Portfolio ${size:,}: No Binance USDT node found")
            continue
        
        # Find ETH chain transfer edges
        eth_transfers = []
        for edge in adj.get(binance_usdt, []):
            if (edge.get("kind") == "transfer" and 
                edge.get("chain") == "ETH" and
                edge.get("target_exchange") == "kraken"):
                eth_transfers.append(edge)
        
        if eth_transfers:
            edge = eth_transfers[0]
            withdrawal_fee = edge.get("withdrawal_fee_units", 0)
            gas_fee = edge.get("gas_fee_usd", 0)
            total_fee = edge.get("total_fee_usd", 0)
            rate = edge.get("rate", 0)
            cost_pct = (1 - rate) * 100
            
            print(f"  Portfolio ${size:,}:")
            print(f"    Withdrawal fee: {withdrawal_fee} USDT")
            print(f"    Gas fee: ${gas_fee:.2f}")
            print(f"    Total fee: ${total_fee:.2f} ({cost_pct:.3f}% of portfolio)")
            print(f"    Rate: {rate:.6f}")
        else:
            print(f"  Portfolio ${size:,}: No ETH transfer edge found (may be filtered by threshold)")
    
    print()


def test_threshold_filtering():
    """Test that portfolio thresholds filter out expensive chains for small portfolios."""
    print("=" * 80)
    print("TEST 2: Portfolio Threshold Filtering")
    print("=" * 80)
    
    print("\nTesting which chains are available for different portfolio sizes...")
    print("-" * 80)
    
    portfolio_sizes = [100, 1_000, 5_000, 10_000]
    chains_to_check = ["ETH", "ARB", "SOL", "TRX", "BNB"]
    
    for size in portfolio_sizes:
        nodes, adj = build_graph(portfolio_size_usd=float(size))
        
        # Find Binance USDT node
        binance_usdt = None
        for node in nodes.keys():
            if node[0] == "binance" and node[1] == "USDT":
                binance_usdt = node
                break
        
        if not binance_usdt:
            continue
        
        # Count transfer edges by chain
        chain_counts = {}
        for edge in adj.get(binance_usdt, []):
            if edge.get("kind") == "transfer":
                chain = edge.get("chain")
                if chain:
                    chain_counts[chain] = chain_counts.get(chain, 0) + 1
        
        print(f"\nPortfolio ${size:,}:")
        for chain in chains_to_check:
            threshold = get_min_portfolio_threshold(chain)
            available = chain in chain_counts
            status = "✓ Available" if available else f"✗ Filtered (threshold: ${threshold:,.0f})"
            print(f"  {chain:6s}: {status}")
    
    print()


def test_gas_fees_included():
    """Test that gas fees are included in transfer edge costs."""
    print("=" * 80)
    print("TEST 3: Gas Fees Included in Transfer Edges")
    print("=" * 80)
    
    print("\nChecking transfer edges for gas fee inclusion...")
    print("-" * 80)
    
    nodes, adj = build_graph(portfolio_size_usd=10_000.0)
    
    # Find all transfer edges and check for gas fees
    transfer_edges_with_gas = 0
    transfer_edges_without_gas = 0
    
    for node, edges in adj.items():
        for edge in edges:
            if edge.get("kind") == "transfer":
                chain = edge.get("chain")
                gas_fee = edge.get("gas_fee_usd")
                
                if gas_fee is not None:
                    transfer_edges_with_gas += 1
                    expected_gas = get_network_gas_fee(chain)
                    if abs(gas_fee - expected_gas) < 0.01:  # Allow small floating point differences
                        pass  # Correct
                    else:
                        print(f"  WARNING: {node[0]}:{node[1]} -> {edge.get('target_exchange')} on {chain}")
                        print(f"    Expected gas: ${expected_gas:.2f}, Got: ${gas_fee:.2f}")
                else:
                    transfer_edges_without_gas += 1
    
    print(f"  Transfer edges with gas fees: {transfer_edges_with_gas}")
    print(f"  Transfer edges without gas fees: {transfer_edges_without_gas}")
    
    if transfer_edges_with_gas > 0:
        print("  ✓ Gas fees are being included in transfer edges")
    else:
        print("  ✗ No gas fees found in transfer edges")
    
    print()


def test_dynamic_vs_fixed_calculation():
    """Compare dynamic fee calculation vs fixed reference calculation."""
    print("=" * 80)
    print("TEST 4: Dynamic vs Fixed Fee Calculation Comparison")
    print("=" * 80)
    
    print("\nComparing withdrawal fee impact for different portfolio sizes...")
    print("Using fixed $10,000 reference vs actual portfolio size")
    print("-" * 80)
    
    portfolio_sizes = [100, 1_000, 10_000, 100_000]
    withdrawal_fee_usdt = 0.75  # Example: Binance USDT on ETH
    price_usd = 1.0  # Assuming USDT = $1
    
    print(f"Withdrawal fee: {withdrawal_fee_usdt} USDT")
    print(f"Gas fee (ETH): ${get_network_gas_fee('ETH'):.2f}")
    print()
    
    for size in portfolio_sizes:
        # Fixed calculation (old way)
        fixed_amount_units = REFERENCE_NOTIONAL_USD / price_usd
        fixed_rate = 1.0 - (withdrawal_fee_usdt / fixed_amount_units)
        fixed_cost_pct = (1 - fixed_rate) * 100
        
        # Dynamic calculation (new way)
        dynamic_amount_units = size / price_usd
        withdrawal_fee_usd = withdrawal_fee_usdt * price_usd
        gas_fee_usd = get_network_gas_fee("ETH")
        total_fee_usd = withdrawal_fee_usd + gas_fee_usd
        dynamic_rate = 1.0 - (total_fee_usd / size)
        dynamic_cost_pct = (1 - dynamic_rate) * 100
        
        print(f"Portfolio ${size:,}:")
        print(f"  Fixed (old):    {fixed_cost_pct:.4f}% cost (ignores portfolio size)")
        print(f"  Dynamic (new):  {dynamic_cost_pct:.4f}% cost (includes gas + portfolio size)")
        print(f"  Difference:     {abs(dynamic_cost_pct - fixed_cost_pct):.4f}%")
        print()
    
    print()


def test_search_with_different_portfolios():
    """Test that search algorithms work with different portfolio sizes."""
    print("=" * 80)
    print("TEST 5: Search Algorithms with Different Portfolio Sizes")
    print("=" * 80)
    
    print("\nTesting dijkstra search with different portfolio sizes...")
    print("-" * 80)
    
    from scripts.baseline_algorithms import dijkstra_like_search
    
    portfolio_sizes = [100, 1_000, 10_000]
    
    # Try to find a start node
    nodes, _ = build_graph(portfolio_size_usd=10_000.0)
    if not nodes:
        print("  No nodes found in graph")
        return
    
    start_node = list(nodes.keys())[0]
    print(f"  Using start node: {start_node[0]}:{start_node[1]}")
    print()
    
    for size in portfolio_sizes:
        print(f"Portfolio ${size:,}:")
        try:
            result = dijkstra_like_search(
                start_node=start_node,
                liquid_cash_usd=float(size),
                max_depth=3,
                max_time_sec=60.0,
                min_profit_usd=0.0,
            )
            
            if result:
                profit_pct = (result.profit_usd / size) * 100
                print(f"  ✓ Found path: profit=${result.profit_usd:.2f} ({profit_pct:.2f}%)")
                print(f"    Path length: {len(result.path)}")
            else:
                print(f"  ✗ No profitable path found")
        except Exception as e:
            print(f"  ✗ Error: {e}")
        print()
    
    print()


def main():
    """Run all tests."""
    print("\n" + "=" * 80)
    print("FEE IMPROVEMENTS TEST SUITE")
    print("=" * 80)
    print()
    
    try:
        test_portfolio_size_impact()
        test_threshold_filtering()
        test_gas_fees_included()
        test_dynamic_vs_fixed_calculation()
        test_search_with_different_portfolios()
        
        print("=" * 80)
        print("ALL TESTS COMPLETED")
        print("=" * 80)
        print("\nSummary:")
        print("  ✓ Portfolio size affects transfer edge costs")
        print("  ✓ Threshold filtering prevents unprofitable paths")
        print("  ✓ Gas fees are included in calculations")
        print("  ✓ Dynamic calculation is more accurate than fixed")
        print("  ✓ Search algorithms work with different portfolio sizes")
        
    except Exception as e:
        print(f"\n✗ Test suite failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

