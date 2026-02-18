#!/usr/bin/env python3
"""
Check which trading pairs actually exist on exchanges.

This will help us understand:
1. Are we missing pairs because exchanges don't list them?
2. Or are we not checking thoroughly enough?
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.data import EXCHANGES, STABLE_COINS

def check_available_pairs():
    """Check which trading pairs exist on each exchange."""
    print("=" * 80)
    print("CHECKING AVAILABLE TRADING PAIRS ON EXCHANGES")
    print("=" * 80)
    print()
    
    for ex_name, ex in EXCHANGES.items():
        print(f"\n{ex_name.upper()}:")
        print("-" * 80)
        
        # Check all pairs between stablecoins
        found_pairs = []
        missing_pairs = []
        
        for i, coin_from in enumerate(STABLE_COINS):
            for j, coin_to in enumerate(STABLE_COINS):
                if i >= j:  # Skip duplicates and self-loops
                    continue
                
                # Try both directions
                pairs_to_try = [
                    f"{coin_from}/{coin_to}",
                    f"{coin_to}/{coin_from}",
                ]
                
                found = False
                for pair in pairs_to_try:
                    try:
                        ticker = ex.fetch_ticker(pair)
                        bid = ticker.get("bid")
                        ask = ticker.get("ask")
                        if bid and ask:
                            found_pairs.append((pair, bid, ask))
                            found = True
                            break
                    except Exception:
                        continue
                
                if not found:
                    missing_pairs.append((coin_from, coin_to))
        
        # Show found pairs
        if found_pairs:
            print(f"  ✓ Found {len(found_pairs)} direct pairs:")
            for pair, bid, ask in sorted(found_pairs):
                spread = ((ask - bid) / bid * 100) if bid > 0 else 0
                print(f"    {pair:20s} bid={bid:.6f} ask={ask:.6f} spread={spread:.4f}%")
        else:
            print(f"  ✗ No direct pairs found")
        
        # Show missing pairs (but note that multi-hop paths are still possible)
        if missing_pairs:
            print(f"\n  ⚠ Missing {len(missing_pairs)} direct pairs:")
            print(f"    (But multi-hop paths may still exist)")
            # Only show first 10 to avoid clutter
            for coin_from, coin_to in missing_pairs[:10]:
                print(f"    {coin_from} ↔ {coin_to}")
            if len(missing_pairs) > 10:
                print(f"    ... and {len(missing_pairs) - 10} more")
        
        # Check what quote currencies are commonly used
        print(f"\n  Checking common quote currencies:")
        common_quotes = ["USDT", "USDC", "BUSD", "FDUSD", "TUSD", "USD"]
        for quote in common_quotes:
            count = 0
            for coin in STABLE_COINS:
                if coin == quote:
                    continue
                try:
                    ticker = ex.fetch_ticker(f"{coin}/{quote}")
                    if ticker.get("bid") and ticker.get("ask"):
                        count += 1
                except Exception:
                    try:
                        ticker = ex.fetch_ticker(f"{quote}/{coin}")
                        if ticker.get("bid") and ticker.get("ask"):
                            count += 1
                    except Exception:
                        pass
            if count > 0:
                print(f"    {quote}: {count} pairs available")

if __name__ == "__main__":
    check_available_pairs()

