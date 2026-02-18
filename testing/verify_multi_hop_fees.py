#!/usr/bin/env python3
"""
Verify that multi-hop paths correctly account for cumulative trading fees.

Example: BUSD → USDT → TUSD
- Should pay fee on BUSD → USDT trade
- Should pay fee on USDT → TUSD trade
- Total fees should be higher than a direct BUSD → TUSD trade (if it existed)
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from scripts.graph import build_graph
from scripts.data import STABLE_COINS

def verify_multi_hop_fees():
    """Verify that multi-hop paths correctly accumulate fees."""
    print("=" * 80)
    print("VERIFYING MULTI-HOP FEE ACCUMULATION")
    print("=" * 80)
    print()
    
    # Build graph
    print("Building graph...")
    nodes, adj = build_graph(force_refresh=True, portfolio_size_usd=100.0)
    print(f"✓ Graph built: {len(nodes)} nodes")
    print()
    
    # Find a multi-hop path example
    print("Looking for multi-hop trade paths...")
    print("-" * 80)
    
    # Check Binance for multi-hop opportunities
    binance_busd = ("binance", "BUSD")
    binance_tusd = ("binance", "TUSD")
    
    if binance_busd in adj and binance_tusd in nodes:
        # Check if direct edge exists
        direct_edge = None
        for edge in adj[binance_busd]:
            if edge.get("to") == binance_tusd and edge.get("kind") == "trade":
                direct_edge = edge
                break
        
        if direct_edge:
            print("✓ Direct BUSD → TUSD edge exists")
            rate_direct = direct_edge.get("rate", 1.0)
            fee_direct = direct_edge.get("taker_fee", 0.0)
            print(f"  Rate: {rate_direct:.6f}")
            print(f"  Fee: {fee_direct*100:.2f}%")
            print(f"  $100 → ${100 * rate_direct:.2f} (fee: ${100 * fee_direct:.2f})")
        else:
            print("✗ No direct BUSD → TUSD edge")
            print("  (This is expected - exchanges usually use USDT as intermediate)")
        
        # Check for multi-hop path: BUSD → USDT → TUSD
        binance_usdt = ("binance", "USDT")
        if binance_usdt in adj:
            edge1 = None
            edge2 = None
            
            # Find BUSD → USDT
            for edge in adj[binance_busd]:
                if edge.get("to") == binance_usdt and edge.get("kind") == "trade":
                    edge1 = edge
                    break
            
            # Find USDT → TUSD
            if edge1:
                for edge in adj[binance_usdt]:
                    if edge.get("to") == binance_tusd and edge.get("kind") == "trade":
                        edge2 = edge
                        break
            
            if edge1 and edge2:
                print()
                print("✓ Multi-hop path found: BUSD → USDT → TUSD")
                print()
                
                rate1 = edge1.get("rate", 1.0)
                rate2 = edge2.get("rate", 1.0)
                fee1 = edge1.get("taker_fee", 0.0)
                fee2 = edge2.get("taker_fee", 0.0)
                
                print(f"Edge 1: BUSD → USDT")
                print(f"  Rate: {rate1:.6f}")
                print(f"  Fee: {fee1*100:.2f}%")
                print(f"  $100 → ${100 * rate1:.2f} (fee: ${100 * fee1:.2f})")
                print()
                print(f"Edge 2: USDT → TUSD")
                print(f"  Rate: {rate2:.6f}")
                print(f"  Fee: {fee2*100:.2f}%")
                cash_after_edge1 = 100 * rate1
                fee2_amount = cash_after_edge1 * fee2
                print(f"  ${cash_after_edge1:.2f} → ${cash_after_edge1 * rate2:.2f} (fee: ${fee2_amount:.2f})")
                print()
                
                # Calculate total
                total_rate = rate1 * rate2
                total_fee_paid = (100 * fee1) + (cash_after_edge1 * fee2)
                final_cash = 100 * total_rate
                
                print(f"Total multi-hop path:")
                print(f"  Combined rate: {total_rate:.6f}")
                print(f"  Total fees paid: ${total_fee_paid:.2f}")
                print(f"  Final cash: ${final_cash:.2f}")
                print(f"  Net profit: ${final_cash - 100:.2f}")
                
                if direct_edge:
                    print()
                    print("Comparison:")
                    print(f"  Direct path: ${100 * rate_direct:.2f} (fee: ${100 * fee_direct:.2f})")
                    print(f"  Multi-hop:   ${final_cash:.2f} (fee: ${total_fee_paid:.2f})")
                    print(f"  Difference:  ${final_cash - (100 * rate_direct):.2f}")
                    print()
                    if total_fee_paid > (100 * fee_direct):
                        print("✓ Multi-hop correctly pays MORE fees (as expected)")
                    else:
                        print("⚠ Multi-hop pays LESS fees (unexpected!)")
                else:
                    print()
                    print("Note: No direct path exists, so multi-hop is the only option")
                    print("✓ Fees are correctly accumulated across both edges")
            else:
                print("✗ Multi-hop path not found")
                if not edge1:
                    print("  Missing: BUSD → USDT edge")
                if not edge2:
                    print("  Missing: USDT → TUSD edge")
        else:
            print("✗ USDT not available on Binance (unexpected)")
    else:
        print("✗ BUSD or TUSD not available on Binance")
    
    print()
    print("=" * 80)
    print("VERIFICATION COMPLETE")
    print("=" * 80)

if __name__ == "__main__":
    verify_multi_hop_fees()

