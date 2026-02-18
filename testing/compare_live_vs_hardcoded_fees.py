#!/usr/bin/env python3
"""
Compare live fees (from CCXT) vs hardcoded fees.

This script:
1. Fetches live trading fees from exchanges
2. Fetches live withdrawal fees for common coins/chains
3. Compares them to hardcoded fees
4. Logs differences and calculates impact
5. Optionally tests graph building with both fee sources
"""

import sys
import time
from pathlib import Path
from typing import Dict, Optional, Tuple
from datetime import datetime

# Make sure we can import from the project root
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.data import EXCHANGES, STABLE_COINS
from scripts.fees import (
    TRADING_FEES_TAKER,
    TRADING_FEES_MAKER,
    WITHDRAWAL_FEES,
    NETWORK_GAS_FEES,
    get_taker_fee,
    get_maker_fee,
    get_network_gas_fee,
    fetch_live_trading_fees,
    fetch_live_withdrawal_fees,
)
from scripts.graph import build_graph, fetch_price_snapshot


def format_percentage(value: float) -> str:
    """Format a decimal as percentage."""
    return f"{value * 100:.4f}%"


def format_fee(value: Optional[float], unit: str = "") -> str:
    """Format a fee value."""
    if value is None:
        return "N/A"
    return f"{value:.6f}{unit}"


def compare_trading_fees() -> Dict[str, Dict]:
    """Compare live vs hardcoded trading fees."""
    print("=" * 80)
    print("TRADING FEES COMPARISON")
    print("=" * 80)
    print()
    
    results = {}
    
    for ex_name, ex_obj in EXCHANGES.items():
        print(f"Exchange: {ex_name.upper()}")
        print("-" * 80)
        
        # Hardcoded fees
        hardcoded_taker = get_taker_fee(ex_name) or 0.0
        hardcoded_maker = get_maker_fee(ex_name) or 0.0
        
        # Try to fetch live fees
        live_fees = fetch_live_trading_fees(ex_name, ex_obj)
        live_taker = live_fees.get('taker') if live_fees else None
        live_maker = live_fees.get('maker') if live_fees else None
        
        # Taker fee comparison
        print(f"  Taker Fee:")
        print(f"    Hardcoded: {format_percentage(hardcoded_taker)}")
        if live_taker is not None:
            print(f"    Live:      {format_percentage(live_taker)}")
            diff = live_taker - hardcoded_taker
            diff_pct = (diff / hardcoded_taker * 100) if hardcoded_taker > 0 else 0
            print(f"    Difference: {format_percentage(diff)} ({diff_pct:+.2f}% relative)")
            if abs(diff) > 0.0001:  # More than 0.01% difference
                print(f"    ⚠️  Significant difference detected!")
        else:
            print(f"    Live:      ❌ Could not fetch (using hardcoded)")
            live_taker = hardcoded_taker  # Use hardcoded as fallback
        
        # Maker fee comparison
        print(f"  Maker Fee:")
        print(f"    Hardcoded: {format_percentage(hardcoded_maker)}")
        if live_maker is not None:
            print(f"    Live:      {format_percentage(live_maker)}")
            diff = live_maker - hardcoded_maker
            diff_pct = (diff / hardcoded_maker * 100) if hardcoded_maker > 0 else 0
            print(f"    Difference: {format_percentage(diff)} ({diff_pct:+.2f}% relative)")
        else:
            print(f"    Live:      ❌ Could not fetch (using hardcoded)")
            live_maker = hardcoded_maker
        
        results[ex_name] = {
            'taker': {
                'hardcoded': hardcoded_taker,
                'live': live_taker,
                'available': live_taker is not None,
            },
            'maker': {
                'hardcoded': hardcoded_maker,
                'live': live_maker,
                'available': live_maker is not None,
            },
        }
        print()
    
    return results


def compare_withdrawal_fees() -> Dict[str, Dict]:
    """Compare live vs hardcoded withdrawal fees."""
    print("=" * 80)
    print("WITHDRAWAL FEES COMPARISON")
    print("=" * 80)
    print()
    
    results = {}
    
    # Test common coins and chains
    test_cases = [
        ("USDT", ["ETH", "TRX", "SOL", "BNB"]),
        ("USDC", ["ETH", "TRX", "SOL", "BNB", "ARB", "BASE"]),
        ("DAI", ["ETH", "BNB", "ARB"]),
    ]
    
    for coin, chains in test_cases:
        print(f"Coin: {coin}")
        print("-" * 80)
        
        coin_results = {}
        
        for ex_name, ex_obj in EXCHANGES.items():
            # Check if exchange has this coin configured
            ex_withdraw_cfg = WITHDRAWAL_FEES.get(ex_name, {}).get(coin)
            if not ex_withdraw_cfg:
                continue
            
            print(f"  Exchange: {ex_name.upper()}")
            
            # Try to fetch live withdrawal fees
            live_fees = fetch_live_withdrawal_fees(ex_name, ex_obj, coin)
            
            ex_results = {}
            
            for chain in chains:
                # Hardcoded fee
                hardcoded_fee = ex_withdraw_cfg.get(chain)
                if hardcoded_fee is None:
                    continue
                
                # Live fee
                live_fee = None
                if live_fees:
                    # Try different chain name formats
                    live_fee = live_fees.get(chain.upper())
                    if live_fee is None:
                        # Try without case sensitivity
                        for k, v in live_fees.items():
                            if k.upper() == chain.upper():
                                live_fee = v
                                break
                
                print(f"    {chain:10} | Hardcoded: {format_fee(hardcoded_fee, f' {coin}')} | ", end="")
                
                if live_fee is not None:
                    print(f"Live: {format_fee(live_fee, f' {coin}')} | ", end="")
                    diff = live_fee - hardcoded_fee
                    diff_pct = (diff / hardcoded_fee * 100) if hardcoded_fee > 0 else 0
                    print(f"Diff: {format_fee(diff, f' {coin}')} ({diff_pct:+.2f}%)")
                    
                    if abs(diff) > 0.1:  # More than 0.1 coin units difference
                        print(f"      ⚠️  Significant difference!")
                else:
                    print(f"Live: ❌ N/A")
                    live_fee = hardcoded_fee  # Use hardcoded as fallback
                
                ex_results[chain] = {
                    'hardcoded': hardcoded_fee,
                    'live': live_fee,
                    'available': live_fee is not None and live_fee != hardcoded_fee,
                }
            
            coin_results[ex_name] = ex_results
            print()
        
        results[coin] = coin_results
        print()
    
    return results


def test_graph_impact(
    portfolio_size_usd: float = 10_000.0,
    sample_edges: int = 5,
) -> None:
    """Test the impact of live fees on graph edges."""
    print("=" * 80)
    print("GRAPH IMPACT TEST")
    print("=" * 80)
    print()
    print(f"Portfolio size: ${portfolio_size_usd:,.2f}")
    print(f"Comparing graph edges with hardcoded vs live fees...")
    print()
    
    # Build graph with hardcoded fees
    print("Building graph with HARDCODED fees...")
    nodes_hc, adj_hc = build_graph(
        force_refresh=True,
        portfolio_size_usd=portfolio_size_usd,
        use_live_fees=False,
    )
    print(f"  Nodes: {len(nodes_hc)}, Edges: {sum(len(v) for v in adj_hc.values())}")
    
    # Build graph with live fees
    print("Building graph with LIVE fees...")
    nodes_live, adj_live = build_graph(
        force_refresh=True,
        portfolio_size_usd=portfolio_size_usd,
        use_live_fees=True,
    )
    print(f"  Nodes: {len(nodes_live)}, Edges: {sum(len(v) for v in adj_live.values())}")
    print()
    
    # Compare sample trade edges
    print("TRADE EDGE COMPARISON (first few examples):")
    print("-" * 80)
    trade_count = 0
    for node, edges in adj_hc.items():
        for edge in edges:
            if edge.get("kind") == "trade" and trade_count < sample_edges:
                to_node = edge["to"]
                
                # Find corresponding edge in live graph
                live_edge = None
                if node in adj_live:
                    for e in adj_live[node]:
                        if e.get("to") == to_node and e.get("kind") == "trade":
                            live_edge = e
                            break
                
                if live_edge:
                    hc_rate = edge.get("rate", 0)
                    live_rate = live_edge.get("rate", 0)
                    hc_cost = edge.get("cost", 0)
                    live_cost = live_edge.get("cost", 0)
                    
                    rate_diff = live_rate - hc_rate
                    cost_diff = live_cost - hc_cost
                    
                    print(f"  {node[0]}:{node[1]} → {to_node[0]}:{to_node[1]}")
                    print(f"    Rate:  {hc_rate:.8f} (hardcoded) vs {live_rate:.8f} (live) | Diff: {rate_diff:+.8f}")
                    print(f"    Cost:  {hc_cost:.8f} (hardcoded) vs {live_cost:.8f} (live) | Diff: {cost_diff:+.8f}")
                    
                    if abs(rate_diff) > 0.0001:
                        print(f"    ⚠️  Rate difference detected!")
                    print()
                    
                    trade_count += 1
                    if trade_count >= sample_edges:
                        break
        if trade_count >= sample_edges:
            break
    
    # Compare sample transfer edges
    print("TRANSFER EDGE COMPARISON (first few examples):")
    print("-" * 80)
    transfer_count = 0
    for node, edges in adj_hc.items():
        for edge in edges:
            if edge.get("kind") == "transfer" and transfer_count < sample_edges:
                to_node = edge["to"]
                
                # Find corresponding edge in live graph
                live_edge = None
                if node in adj_live:
                    for e in adj_live[node]:
                        if e.get("to") == to_node and e.get("kind") == "transfer" and e.get("chain") == edge.get("chain"):
                            live_edge = e
                            break
                
                if live_edge:
                    hc_rate = edge.get("rate", 0)
                    live_rate = live_edge.get("rate", 0)
                    hc_total_fee = edge.get("total_fee_usd", 0)
                    live_total_fee = live_edge.get("total_fee_usd", 0)
                    
                    rate_diff = live_rate - hc_rate
                    fee_diff = live_total_fee - hc_total_fee
                    
                    print(f"  {node[0]}:{node[1]} → {to_node[0]}:{to_node[1]} ({edge.get('chain', 'N/A')})")
                    print(f"    Rate:      {hc_rate:.8f} (hardcoded) vs {live_rate:.8f} (live) | Diff: {rate_diff:+.8f}")
                    print(f"    Total Fee: ${hc_total_fee:.4f} (hardcoded) vs ${live_total_fee:.4f} (live) | Diff: ${fee_diff:+.4f}")
                    
                    if abs(rate_diff) > 0.0001:
                        print(f"    ⚠️  Rate difference detected!")
                    print()
                    
                    transfer_count += 1
                    if transfer_count >= sample_edges:
                        break
        if transfer_count >= sample_edges:
            break


def generate_summary_report(
    trading_results: Dict,
    withdrawal_results: Dict,
    output_file: Optional[Path] = None,
) -> None:
    """Generate a summary report."""
    print("=" * 80)
    print("SUMMARY REPORT")
    print("=" * 80)
    print()
    
    # Trading fees summary
    print("Trading Fees Availability:")
    for ex_name, data in trading_results.items():
        taker_avail = "✓" if data['taker']['available'] else "✗"
        maker_avail = "✓" if data['maker']['available'] else "✗"
        print(f"  {ex_name:10} | Taker: {taker_avail} | Maker: {maker_avail}")
    print()
    
    # Withdrawal fees summary
    print("Withdrawal Fees Availability:")
    for coin, ex_data in withdrawal_results.items():
        for ex_name, chain_data in ex_data.items():
            available_chains = sum(1 for c in chain_data.values() if c.get('available', False))
            total_chains = len(chain_data)
            print(f"  {coin:6} on {ex_name:10} | {available_chains}/{total_chains} chains have live data")
    print()
    
    # Save to file if requested
    if output_file:
        with open(output_file, 'w') as f:
            f.write(f"Live vs Hardcoded Fees Comparison Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            
            f.write("TRADING FEES:\n")
            for ex_name, data in trading_results.items():
                f.write(f"  {ex_name}:\n")
                f.write(f"    Taker: {data['taker']['hardcoded']:.6f} (hardcoded) vs ")
                if data['taker']['live'] is not None:
                    f.write(f"{data['taker']['live']:.6f} (live)\n")
                else:
                    f.write("N/A (live)\n")
                f.write(f"    Maker: {data['maker']['hardcoded']:.6f} (hardcoded) vs ")
                if data['maker']['live'] is not None:
                    f.write(f"{data['maker']['live']:.6f} (live)\n")
                else:
                    f.write("N/A (live)\n")
            f.write("\n")
            
            f.write("WITHDRAWAL FEES:\n")
            for coin, ex_data in withdrawal_results.items():
                f.write(f"  {coin}:\n")
                for ex_name, chain_data in ex_data.items():
                    f.write(f"    {ex_name}:\n")
                    for chain, data in chain_data.items():
                        f.write(f"      {chain}: {data['hardcoded']:.6f} (hardcoded) vs ")
                        if data.get('live') is not None:
                            f.write(f"{data['live']:.6f} (live)\n")
                        else:
                            f.write("N/A (live)\n")
        
        print(f"Report saved to: {output_file}")


def main():
    """Main function."""
    print("=" * 80)
    print("LIVE VS HARDCODED FEES COMPARISON")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Compare trading fees
    trading_results = compare_trading_fees()
    
    # Compare withdrawal fees
    withdrawal_results = compare_withdrawal_fees()
    
    # Test graph impact
    try:
        test_graph_impact(portfolio_size_usd=10_000.0)
    except Exception as e:
        print(f"⚠️  Graph impact test failed: {e}")
        print("  (This is okay - some exchanges may not support live fee fetching)")
        print()
    
    # Generate summary
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = results_dir / f"live_vs_hardcoded_fees_{timestamp}.txt"
    
    generate_summary_report(trading_results, withdrawal_results, output_file)
    
    print()
    print("=" * 80)
    print("COMPARISON COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()

