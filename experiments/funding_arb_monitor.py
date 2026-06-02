"""
Funding Rate Arbitrage Monitor
==============================

Detects cross-exchange funding rate spreads and computes profit potential.

Strategy: When exchange A has a high positive funding rate and exchange B has
a lower (or negative) rate for the same perp, go short on A (receive funding)
and long on B (pay less or receive funding). The spread is captured every 8h.

Usage:
    python -m experiments.funding_arb_monitor
    python -m experiments.funding_arb_monitor --min-spread 5 --continuous --interval 300
"""

import argparse
import json
import sys
import os
import time
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.data import EXCHANGES, VOLATILE_COINS
from scripts.fees import TRADING_FEES_TAKER

# Perpetual symbols to monitor
PERP_SYMBOLS = [f"{coin}/USDT:USDT" for coin in VOLATILE_COINS]

# Exchanges that support perpetual futures
PERP_EXCHANGES = {
    name: ex for name, ex in EXCHANGES.items()
    if ex.has.get("fetchFundingRate", False)
}


def fetch_all_funding_rates() -> Dict[str, Dict[str, dict]]:
    """
    Fetch funding rates for all perp symbols across all exchanges.
    Returns: {symbol: {exchange: {rate, mark_price, next_rate, ...}}}
    """
    result: Dict[str, Dict[str, dict]] = {}
    ts = datetime.now(timezone.utc).isoformat()

    for sym in PERP_SYMBOLS:
        result[sym] = {}
        for ex_name, ex in PERP_EXCHANGES.items():
            try:
                fr = ex.fetch_funding_rate(sym)
                rate = fr.get("fundingRate")
                if rate is None:
                    continue
                result[sym][ex_name] = {
                    "rate": rate,
                    "rate_bps": rate * 10000,
                    "mark_price": fr.get("markPrice"),
                    "next_rate": fr.get("nextFundingRate"),
                    "funding_datetime": fr.get("fundingDatetime"),
                    "ts": ts,
                }
            except Exception:
                pass  # Symbol may not exist on this exchange

    return result


def find_arb_opportunities(
    funding_data: Dict[str, Dict[str, dict]],
    min_spread_bps: float = 0.0,
) -> List[dict]:
    """
    Find funding rate arb opportunities: pairs where the spread between
    the highest and lowest funding rate exceeds min_spread_bps.
    """
    opportunities = []

    for sym, exchanges in funding_data.items():
        if len(exchanges) < 2:
            continue

        # Sort by funding rate
        sorted_ex = sorted(exchanges.items(), key=lambda x: x[1]["rate"])
        lowest_name, lowest = sorted_ex[0]
        highest_name, highest = sorted_ex[-1]

        spread_bps = (highest["rate"] - lowest["rate"]) * 10000

        if spread_bps < min_spread_bps:
            continue

        # Entry cost: taker fees on both legs (open positions)
        # Exit cost: taker fees on both legs (close positions)
        entry_fee_bps = (
            TRADING_FEES_TAKER.get(highest_name, 0.001) +
            TRADING_FEES_TAKER.get(lowest_name, 0.001)
        ) * 10000
        round_trip_fee_bps = entry_fee_bps * 2  # open + close

        # Funding is paid every 8h = 3x per day
        daily_funding_bps = spread_bps * 3
        annual_funding_bps = daily_funding_bps * 365

        # Break-even: how many 8h periods to recover round-trip fees
        breakeven_periods = round_trip_fee_bps / spread_bps if spread_bps > 0 else float("inf")

        coin = sym.split("/")[0]
        opp = {
            "symbol": sym,
            "coin": coin,
            "short_exchange": highest_name,
            "short_rate_bps": highest["rate_bps"],
            "short_mark_price": highest["mark_price"],
            "long_exchange": lowest_name,
            "long_rate_bps": lowest["rate_bps"],
            "long_mark_price": lowest["mark_price"],
            "spread_bps": spread_bps,
            "daily_bps": daily_funding_bps,
            "annual_pct": annual_funding_bps / 100,
            "round_trip_fee_bps": round_trip_fee_bps,
            "breakeven_8h_periods": breakeven_periods,
            "net_daily_bps_after_1d_hold": daily_funding_bps - round_trip_fee_bps,
            "num_exchanges": len(exchanges),
            "all_rates": {k: v["rate_bps"] for k, v in exchanges.items()},
        }
        opportunities.append(opp)

    # Sort by spread descending
    opportunities.sort(key=lambda x: x["spread_bps"], reverse=True)
    return opportunities


def print_opportunities(opportunities: List[dict]):
    """Pretty-print funding arb opportunities."""
    if not opportunities:
        print("\n  No funding rate arb opportunities found.\n")
        return

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"\n{'='*90}")
    print(f"  FUNDING RATE ARB OPPORTUNITIES — {ts}")
    print(f"{'='*90}")
    print(f"  {'Coin':<6} {'Short@':<10} {'ShortRate':>10} {'Long@':<10} {'LongRate':>10} "
          f"{'Spread':>8} {'Daily':>8} {'Annual%':>8} {'BrkEven':>8}")
    print(f"  {'':<6} {'':>10} {'(bps)':>10} {'':>10} {'(bps)':>10} "
          f"{'(bps)':>8} {'(bps)':>8} {'':>8} {'(8h)':>8}")
    print(f"  {'-'*86}")

    for opp in opportunities:
        be = opp["breakeven_8h_periods"]
        be_str = f"{be:.1f}" if be < 1000 else "inf"
        net_daily = opp["net_daily_bps_after_1d_hold"]
        profit_marker = " ✓" if net_daily > 0 else ""

        print(f"  {opp['coin']:<6} {opp['short_exchange']:<10} "
              f"{opp['short_rate_bps']:>+10.2f} {opp['long_exchange']:<10} "
              f"{opp['long_rate_bps']:>+10.2f} {opp['spread_bps']:>8.2f} "
              f"{opp['daily_bps']:>8.1f} {opp['annual_pct']:>8.1f} "
              f"{be_str:>8}{profit_marker}")

    # Summary
    profitable = [o for o in opportunities if o["net_daily_bps_after_1d_hold"] > 0]
    print(f"\n  Total opportunities: {len(opportunities)}  |  "
          f"Profitable (>1 day hold): {len(profitable)}")
    if profitable:
        best = profitable[0]
        print(f"  Best: {best['coin']} short@{best['short_exchange']} / "
              f"long@{best['long_exchange']} → {best['spread_bps']:.1f} bps/8h "
              f"({best['annual_pct']:.0f}% annualized)")
    print()


def save_results(opportunities: List[dict], output_path: str):
    """Save raw results to JSON."""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w") as f:
        json.dump({
            "ts": datetime.now(timezone.utc).isoformat(),
            "opportunities": opportunities,
        }, f, indent=2, default=str)
    print(f"  Results saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Funding rate arbitrage monitor")
    parser.add_argument("--min-spread", type=float, default=0.0,
                        help="Minimum spread in bps to report (default: 0)")
    parser.add_argument("--continuous", action="store_true",
                        help="Run continuously, rescanning at --interval")
    parser.add_argument("--interval", type=int, default=300,
                        help="Seconds between scans in continuous mode (default: 300)")
    parser.add_argument("--output", type=str, default="data/funding_arb.json",
                        help="Output JSON path (default: data/funding_arb.json)")
    args = parser.parse_args()

    print(f"\n  Funding Rate Arb Monitor")
    print(f"  Perp exchanges: {list(PERP_EXCHANGES.keys())}")
    print(f"  Symbols: {len(PERP_SYMBOLS)} perps")
    print(f"  Min spread filter: {args.min_spread} bps\n")

    while True:
        print("  Fetching funding rates...")
        funding_data = fetch_all_funding_rates()

        # Count how many rates we got
        total_rates = sum(len(v) for v in funding_data.values())
        symbols_with_data = sum(1 for v in funding_data.values() if len(v) >= 2)
        print(f"  Got {total_rates} rates across {symbols_with_data} symbols with ≥2 exchanges")

        opportunities = find_arb_opportunities(funding_data, args.min_spread)
        print_opportunities(opportunities)
        save_results(opportunities, args.output)

        if not args.continuous:
            break

        print(f"  Next scan in {args.interval}s...")
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
