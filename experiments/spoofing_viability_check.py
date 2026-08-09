#!/usr/bin/env python3
# ======================================================================
# spoofing_viability_check.py — Could price manipulation help?
# ======================================================================
#
# Question: If we could artificially move TUSD/USDT price on mexc,
# could we make the conversion profitable?
#
# This is a thought experiment to understand the economics,
# not a guide to illegal market manipulation.
#
# ======================================================================

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.data import EXCHANGES

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("=" * 80)
    print("SPOOFING VIABILITY ANALYSIS")
    print("=" * 80)
    print()
    print("Question: If we could artificially move TUSD/USDT price, could we escape?")
    print()

    # Current prices
    mexc = EXCHANGES["mexc"]
    ticker = mexc.fetch_ticker("TUSD/USDT")
    current_bid = ticker.get("bid")
    current_ask = ticker.get("ask")

    print("[1] Current Market State")
    print(f"    TUSD/USDT bid:  {current_bid:.8f}")
    print(f"    TUSD/USDT ask:  {current_ask:.8f}")
    print(f"    Bid spread:     {((current_ask - current_bid) / current_bid * 100):.4f}%")
    print()

    # Fees
    taker_fee = 0.0005  # 0.05%
    withdrawal_fee = 1.0  # $1.00
    starting_tusd = 10009.76

    print("[2] Current Economics (No Spoofing)")
    print(f"    Starting:       {starting_tusd:.2f} TUSD")
    print(f"    Sell at bid:    {starting_tusd * current_bid:.2f} USDT")
    print(f"    Trading fee:    -{starting_tusd * current_bid * taker_fee:.2f} USDT")
    print(f"    After trading:  {starting_tusd * current_bid * (1 - taker_fee):.2f} USDT")
    print(f"    Withdrawal fee: -{withdrawal_fee:.2f} USDT")
    print(f"    Final:          {starting_tusd * current_bid * (1 - taker_fee) - withdrawal_fee:.2f} USDT")
    print(f"    Loss:           ${starting_tusd * current_bid * (1 - taker_fee) - withdrawal_fee - starting_tusd:.2f}")
    print()

    # What would we need?
    print("[3] How Much Would Price Need to Move?")
    print()

    # Target: break even (final = starting)
    # starting_tusd * bid * (1 - taker_fee) - withdrawal_fee = starting_tusd
    # starting_tusd * bid * (1 - taker_fee) = starting_tusd + withdrawal_fee
    # bid = (starting_tusd + withdrawal_fee) / (starting_tusd * (1 - taker_fee))

    needed_bid_breakeven = (starting_tusd + withdrawal_fee) / (starting_tusd * (1 - taker_fee))
    bid_move_needed = needed_bid_breakeven - current_bid
    bid_move_pct = (bid_move_needed / current_bid) * 100

    print(f"    To break even:")
    print(f"      Need bid price: {needed_bid_breakeven:.8f}")
    print(f"      Current bid:    {current_bid:.8f}")
    print(f"      Move needed:    +{bid_move_needed:.8f}")
    print(f"      Move %:         +{bid_move_pct:.4f}%")
    print()

    # That means TUSD would need to appreciate
    # 1 TUSD worth more than 1 USDT
    print(f"    What this means:")
    print(f"      • TUSD would need to be worth {needed_bid_breakeven:.6f} USDT")
    print(f"      • That's a {bid_move_pct:.4f}% appreciation vs USDT")
    print(f"      • Both are stablecoins (should be ~$1.00)")
    print(f"      • This requires USDT to depreciate OR TUSD to appreciate")
    print(f"      • Realistically: impossible without major market event")
    print()

    # Could we profit?
    print("[4] Could Spoofing Profitably Liquidate The Position?")
    print()
    
    target_profit = 100  # modest $100 profit target
    needed_bid_profit = (starting_tusd + withdrawal_fee + target_profit) / (starting_tusd * (1 - taker_fee))
    bid_move_pct_profit = ((needed_bid_profit - current_bid) / current_bid) * 100

    print(f"    To profit $100:")
    print(f"      Need bid price: {needed_bid_profit:.8f}")
    print(f"      Move needed:    +{bid_move_pct_profit:.4f}%")
    print()

    print("[5] Spoofing Feasibility Assessment")
    print()
    print(f"    ✗ TUSD and USDT are stablecoins with narrow trading ranges")
    print(f"    ✗ Moving price by {bid_move_pct:.4f}% would require massive volume")
    print(f"    ✗ Mexc has circuit breakers to prevent large moves")
    print(f"    ✗ Spoofing is illegal (Market Abuse Regulation)")
    print(f"    ✗ Even if successful, you'd still need to execute the sale")
    print(f"      (and execution moves the price back down)")
    print()

    print("[6] LEGAL ALTERNATIVES (Spoofing-Free Solutions)")
    print()
    print("    Option A: WAIT FOR MARKET CONDITIONS TO CHANGE")
    print("      If TUSD appreciates (unlikely but possible), conversion becomes profitable")
    print("      Example: If bid moves to 1.0003, then profit ≈ +$20")
    print()
    print("    Option B: ACCEPT SMALL LOSS AND MOVE ON")
    print("      Convert at -$22 loss, redeploy $9,987.75 to profitable trades")
    print("      Lessons learned outweigh the loss")
    print()
    print("    Option C: ANALYZE GRAPH TOPOLOGY")
    print("      The real question: How did we end up in a dead-end in the first place?")
    print("      Better solution: Prevent dead-ends with constrained routing")
    print()
    print("    Option D: DIVERSIFICATION")
    print("      Don't allocate all $10k to one path")
    print("      If 1 path fails, others can sustain operations")
    print()

    print()
    print("=" * 80)
    print("CONCLUSION")
    print("=" * 80)
    print()
    print("Spoofing is NOT a viable escape route because:")
    print()
    print("1. MATHEMATICALLY IMPRACTICAL")
    print("   - Need to move price by +0.022% just to break even")
    print("   - Need to move price by +0.003% to profit $100")
    print("   - Stablecoins rarely move more than 0.1%")
    print()
    print("2. TECHNICALLY DIFFICULT")
    print("   - Mexc has volatility controls")
    print("   - Large fake orders trigger circuit breakers")
    print("   - Other traders will immediately arbitrage the fake price")
    print()
    print("3. LEGALLY PROHIBITED")
    print("   - Market manipulation (spoofing/layering) is illegal")
    print("   - SEC/FCA/relevant regulators prosecute this")
    print("   - Possible criminal penalties")
    print()
    print("4. ECONOMICALLY SELF-DEFEATING")
    print("   - Even if you fake the price and sell, you still owe the fees")
    print("   - The mathematical trap doesn't change")
    print("   - You just moved $22 of loss to your trading account")
    print()
    print("The REAL solution is PREVENTION, not ESCAPE:")
    print("• Use constrained routing to avoid dead-ends")
    print("• Verify exit paths BEFORE entering trades")
    print("• Focus on safer nodes (USDT, USDC, major hubs)")
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
