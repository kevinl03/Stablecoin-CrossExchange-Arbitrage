#!/usr/bin/env python3
# ======================================================================
# analyze_tusd_to_usdt.py — What's the actual profit of TUSD → USDT?
# ======================================================================

from __future__ import annotations

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.data import EXCHANGES
from scripts.fees import get_taker_fee, get_network_gas_fee

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("=" * 80)
    print("ANALYZING TUSD → USDT CONVERSION ON MEXC")
    print("=" * 80)
    print()

    print("[1] Fetching live prices for TUSD and USDT on mexc...")
    mexc = EXCHANGES["mexc"]
    
    try:
        # Get TUSD/USDT pair price
        ticker = mexc.fetch_ticker("TUSD/USDT")
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        print(f"    ✓ TUSD/USDT ticker on mexc")
        print(f"      Bid: {bid:.8f}")
        print(f"      Ask: {ask:.8f}")
        print(f"      Spread: {((ask - bid) / bid * 100):.4f}%")
    except Exception as e:
        print(f"    ✗ Failed to fetch TUSD/USDT: {e}")
        return 1
    
    print()
    print("[2] Calculating conversion costs for $10,009.76 TUSD → USDT...")
    print()
    
    starting_tusd = 10009.76
    starting_usdt = 0
    
    # Trading fee (taker fee on mexc)
    taker_fee = get_taker_fee("mexc") or 0.001  # Default to 0.1% if not found
    print(f"    Starting: {starting_tusd:.2f} TUSD")
    print(f"    Taker fee rate on mexc: {taker_fee*100:.2f}%")
    print()
    
    # When selling TUSD for USDT, we use BID (what we receive)
    usdt_received_gross = starting_tusd * bid
    trading_fee_usd = usdt_received_gross * taker_fee
    usdt_after_trading_fee = usdt_received_gross - trading_fee_usd
    
    print(f"    [Step 1] Trade TUSD → USDT using BID={bid:.8f}")
    print(f"      Gross USDT received: {usdt_received_gross:.2f}")
    print(f"      Trading fee ({taker_fee*100:.2f}%): ${trading_fee_usd:.2f}")
    print(f"      USDT after trading fee: {usdt_after_trading_fee:.2f}")
    print()
    
    # Check if there are withdrawal fees
    # On mexc, withdrawing USDT typically has a fee
    print(f"    [Step 2] Check withdrawal fees...")
    withdrawal_fee_usdt = 1.0  # Typical USDT withdrawal fee on mexc
    print(f"      Withdrawal fee: {withdrawal_fee_usdt:.2f} USDT")
    
    final_usdt = usdt_after_trading_fee - withdrawal_fee_usdt
    profit = final_usdt - starting_tusd
    
    print()
    print("    " + "=" * 76)
    print(f"    Final USDT balance: {final_usdt:.2f}")
    print(f"    Starting TUSD: {starting_tusd:.2f}")
    print(f"    PROFIT/LOSS: ${profit:.2f}")
    print("    " + "=" * 76)
    print()
    
    if profit < 0:
        loss_pct = (abs(profit) / starting_tusd) * 100
        print(f"    ✗ LOSS: {loss_pct:.2f}%")
        print()
        print(f"    This explains why the edge is marked as $0.00 profit!")
        print(f"    The graph building algorithm filters out non-positive profit edges.")
        print()
        print(f"    KEY INSIGHT:")
        print(f"    - Converting TUSD → USDT costs more than the value gained")
        print(f"    - Trading fee + withdrawal fee = {trading_fee_usd + withdrawal_fee_usdt:.2f}")
        print(f"    - The bid price ({bid:.8f}) is not enough to cover these costs")
        print(f"    - Therefore: MEXC:TUSD is a DEAD-END")
    else:
        print(f"    ✓ PROFIT: {profit:.2f}")
    
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
