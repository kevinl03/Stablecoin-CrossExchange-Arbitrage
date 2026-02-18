#!/usr/bin/env python3
"""
Debug script to understand where profits are coming from.

Check if:
1. Bid/ask pricing is actually being used
2. Or if we're falling back to normalized prices (which could create false spreads)
3. What the actual price differences are
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, _fetch_actual_trading_pair_rate
from scripts.data import EXCHANGES

def debug_profit_source():
    """Check where profits are actually coming from."""
    print("=" * 70)
    print("DEBUGGING PROFIT SOURCE")
    print("=" * 70)
    print()
    
    # Check if we can get actual trading pair rates
    print("1. Checking if BUSD/TUSD trading pair exists on Binance:")
    print("-" * 70)
    
    binance = EXCHANGES.get("binance")
    if binance:
        # Try to get actual rate
        rate = _fetch_actual_trading_pair_rate("binance", "BUSD", "TUSD")
        if rate:
            print(f"   ✓ Found actual trading pair rate: {rate:.6f}")
            print(f"   This uses BID price (conservative)")
        else:
            print(f"   ✗ No direct trading pair - will use normalized prices")
            print(f"   This could create false spreads!")
        
        # Also check the ticker directly
        try:
            ticker = binance.fetch_ticker("BUSD/TUSD")
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            mid = (bid + ask) / 2.0 if bid and ask else None
            print(f"   Ticker: bid={bid}, ask={ask}, mid={mid}")
            if bid and ask:
                spread = ((ask - bid) / bid) * 100 if bid > 0 else 0
                print(f"   Bid-ask spread: {spread:.4f}%")
        except Exception as e:
            print(f"   Error fetching ticker: {e}")
    
    print()
    print("2. Building graph to see what rates are used:")
    print("-" * 70)
    
    nodes, adj = build_graph(force_refresh=True, portfolio_size_usd=100.0)
    
    # Find BUSD -> TUSD edge on binance
    binance_busd = ("binance", "BUSD")
    binance_tusd = ("binance", "TUSD")
    
    if binance_busd in adj:
        for edge in adj[binance_busd]:
            if edge.get("to") == binance_tusd and edge.get("kind") == "trade":
                rate = edge.get("rate")
                uses_actual = edge.get("uses_actual_pair", False)
                taker_fee = edge.get("taker_fee", 0.0)
                
                print(f"   Edge: BUSD -> TUSD on binance")
                print(f"   Rate: {rate:.6f}")
                print(f"   Uses actual pair: {uses_actual}")
                print(f"   Taker fee: {taker_fee:.4f} ({taker_fee*100:.2f}%)")
                
                # Calculate what this means
                initial = 100.0
                after_rate = initial * rate
                print(f"   $100 × {rate:.6f} = ${after_rate:.2f}")
                print(f"   Profit: ${after_rate - initial:.2f}")
                
                if not uses_actual:
                    print(f"   ⚠️  WARNING: Using normalized prices (fallback)")
                    print(f"   This could create false arbitrage opportunities!")
                    print(f"   Normalized prices assume all stablecoins = $1.00")
                    print(f"   But small price differences create false spreads")
    
    print()
    print("3. Analysis:")
    print("-" * 70)
    print("If 'uses_actual_pair' is False:")
    print("  - The system is using normalized USD prices")
    print("  - This assumes BUSD = $1.00 and TUSD = $1.00")
    print("  - But if there's a tiny real difference (e.g., BUSD=$0.9998, TUSD=$1.0002)")
    print("  - This creates a false 0.04% spread")
    print()
    print("If 'uses_actual_pair' is True:")
    print("  - The system is using actual bid/ask prices")
    print("  - Profits are more likely to be real")
    print("  - But still very small (0.03-0.04%)")

if __name__ == "__main__":
    debug_profit_source()

