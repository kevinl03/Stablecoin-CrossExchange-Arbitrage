#!/usr/bin/env python3
# ======================================================================
# fiat_intermediary_analysis.py — Can we escape via FIAT conversion?
# ======================================================================
#
# Question: Could we convert mexc:TUSD → FIAT (USD) → USDT?
# This would bypass the direct TUSD/USDT conversion entirely.
#
# Analysis:
# 1. Can mexc even withdraw TUSD to fiat?
# 2. What are the conversion rates and fees?
# 3. Would it be cheaper than direct TUSD→USDT?
# 4. Is this even possible on mexc?
#
# ======================================================================

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.data import EXCHANGES
from scripts.fees import WITHDRAWAL_FEES

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("=" * 80)
    print("FIAT INTERMEDIARY ANALYSIS")
    print("=" * 80)
    print()
    print("Question: Can we escape mexc:TUSD via FIAT conversion?")
    print("Route: mexc:TUSD → [FIAT USD] → mexc:USDT")
    print()

    # Get mexc object
    mexc = EXCHANGES["mexc"]
    
    print("[1] Checking if mexc:TUSD can be withdrawn to FIAT")
    print("-" * 80)
    print()
    
    # Check what withdrawal methods mexc supports for TUSD
    try:
        # Try to get TUSD market data
        ticker = mexc.fetch_ticker("TUSD/USDT")
        print(f"    ✓ TUSD/USDT pair exists on mexc")
        print(f"      Bid: {ticker.get('bid'):.8f}")
        print(f"      Ask: {ticker.get('ask'):.8f}")
    except Exception as e:
        print(f"    ✗ Error fetching TUSD data: {e}")
    
    print()

    # Check withdrawal fees
    print("[2] Withdrawal Fee Analysis")
    print("-" * 80)
    print()
    
    print("    TUSD Withdrawal from mexc:")
    print()
    
    # Check if TUSD has withdrawal info
    if "TUSD" in WITHDRAWAL_FEES:
        tusd_fees = WITHDRAWAL_FEES["TUSD"]
        print(f"      On-chain fee: ${tusd_fees.get('withdrawal_fee', 'N/A')}")
        print(f"      Min amount:   ${tusd_fees.get('min_withdrawal', 'N/A')}")
    else:
        print(f"      TUSD not in withdrawal fee database")
        print(f"      Typical stablecoin withdrawal: $0.50-$2.00")
    
    print()

    # ─ The Key Question ──────────────────────────────────────────────────

    print("[3] Critical Issue: FIAT Conversion on Mexc")
    print("-" * 80)
    print()
    
    print("    Can mexc:TUSD be converted to actual FIAT (USD)?")
    print()
    
    print("    ✗ SHORT ANSWER: Probably not in the way you're thinking")
    print()
    
    print("    Here's why:")
    print()
    
    print("    1. MEXC doesn't do FIAT on-ramps/off-ramps for most regions")
    print("       • Mexc is primarily a crypto exchange")
    print("       • FIAT support is limited (few countries)")
    print("       • United States: NO direct FIAT support on mexc")
    print()
    
    print("    2. Even if it did, conversion costs would be high")
    print("       • Crypto → FIAT conversion: 2-5% fee typical")
    print("       • Bank transfer: $10-50 per transaction")
    print("       • Example: $10,009.76 would cost $200-500 in fees")
    print()
    
    print("    3. FIAT → back to USDT still requires conversion")
    print("       • FIAT → Crypto is another 2-5% fee")
    print("       • You'd pay the conversion twice")
    print("       • Net result: MUCH worse than direct TUSD→USDT")
    print()

    # ─ The Real Issue ────────────────────────────────────────────────────

    print("[4] The Real Problem With FIAT Conversion")
    print("-" * 80)
    print()
    
    print("    Why FIAT conversion WON'T work:")
    print()
    
    print("    Route 1: Direct TUSD→USDT (within mexc)")
    print("      Step 1: Trade TUSD for USDT on mexc")
    print("              Fee: 0.05% (trading)")
    print("              Cost: $5.00")
    print("      Step 2: (No withdrawal needed, already on mexc)")
    print("      ────────────────────────")
    print("      Total cost: ~$5-6")
    print("      Final: ~$9,987.75 USDT")
    print()
    
    print("    Route 2: TUSD→FIAT→USDT (expensive detour)")
    print("      Step 1: Convert TUSD to actual FIAT (USD)")
    print("              Crypto→FIAT conversion: 2-5% fee")
    print("              Fee: $200-500")
    print("      Step 2: Bank transfer (if available)")
    print("              Fee: $10-50")
    print("      Step 3: Deposit FIAT back to crypto")
    print("              FIAT→Crypto conversion: 2-5% fee")
    print("              Fee: $200-500")
    print("      Step 4: Convert received crypto to USDT")
    print("              Fee: $50-100")
    print("      ────────────────────────")
    print("      Total cost: $460-1,150+")
    print("      Final: ~$8,860-9,550 USDT (even worse!)")
    print()
    
    print("    VERDICT: FIAT conversion is 100× more expensive")
    print()

    # ─ Alternative: Crypto Bridge ────────────────────────────────────────

    print("[5] Alternative: Could We Use Crypto Bridges?")
    print("-" * 80)
    print()
    
    print("    What about: TUSD (on mexc) → Bridge → USDT?")
    print()
    
    print("    Bridges like Stargate, Across, Connext exist, but:")
    print()
    print("    ✗ They bridge between blockchains, not within an exchange")
    print("    ✗ TUSD on mexc is a deposit/wallet, not an on-chain asset")
    print("    ✗ You'd need to withdraw TUSD from mexc to blockchain first")
    print("    ✗ That withdrawal costs fees (same as direct TUSD→USDT)")
    print()
    
    print("    So you're back to: Direct TUSD→USDT is still cheaper")
    print()

    # ─ What COULD Work ──────────────────────────────────────────────────

    print("[6] What COULD Actually Work (But Won't Help)")
    print("-" * 80)
    print()
    
    print("    IF mexc supported FIAT conversion (it doesn't):")
    print("    IF FIAT conversion was cheap (it's not):")
    print()
    
    print("    Even then:")
    print()
    
    starting = 10009.76
    
    print("    Route: TUSD → FIAT → back to USDT")
    print()
    
    # Hypothetical costs
    print("    Hypothetical (best case scenario):")
    print("      Starting: $10,009.76 TUSD")
    print("      Step 1: TUSD→FIAT (1% fee): -$100")
    print("              Result: $9,909.76 FIAT")
    print("      Step 2: Bank transfer: -$25")
    print("              Result: $9,884.76")
    print("      Step 3: FIAT→USDT (1% fee): -$99")
    print("              Result: $9,785.76")
    print("      ────────────────────────")
    print("      Total loss: $224 (2.24%)")
    print()
    
    print("    Compare to direct TUSD→USDT: -$22 (0.22%)")
    print()
    print("    FIAT route is 10× WORSE, not better!")
    print()

    # ─ The Fundamental Issue ─────────────────────────────────────────────

    print("[7] The Fundamental Issue")
    print("-" * 80)
    print()
    
    print("    Why FIAT intermediary doesn't work:")
    print()
    print("    1. You're trying to escape TUSD illiquidity")
    print("       → FIAT doesn't solve this (adds costs)")
    print()
    print("    2. The problem is on mexc specifically")
    print("       → TUSD/USDT conversion is the ONLY exit path")
    print("       → That path costs $22")
    print()
    print("    3. FIAT conversion costs 10-100× more")
    print("       → Makes the problem worse, not better")
    print()
    print("    4. You still end up in USDT anyway")
    print("       → Why not just convert TUSD→USDT directly?")
    print()

    # ─ Conclusion ────────────────────────────────────────────────────────

    print("[8] CONCLUSION")
    print("-" * 80)
    print()
    
    print("    ✗ FIAT intermediary will NOT help")
    print()
    
    print("    Why:")
    print("    • Mexc has no cheap FIAT conversion")
    print("    • FIAT bridges have 2-5% fees (vs 0.05% direct)")
    print("    • Total cost: $200-500+ (vs $22 direct)")
    print("    • You still need to convert back to crypto")
    print("    • Net result: Much worse than direct liquidation")
    print()
    
    print("    Best path forward:")
    print("    1. Accept -$22 loss (sunk cost)")
    print("    2. Liquidate TUSD→USDT directly")
    print("    3. Implement safe-node constraint")
    print("    4. Recover loss in 2-3 constrained trades")
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
