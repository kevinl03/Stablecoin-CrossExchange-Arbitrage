# ======================================================================
# slippage_vwap_test.py — Order-book VWAP slippage verification
# ======================================================================
#
# PURPOSE: Addresses Hang Ma's feedback:
#   "Given the tiny margins (~0.04%), even small slippage or quote
#    staleness could erase profit."
#   "Theoretical models of liquidity and slippage... suggest more faithful
#    slippage proxies than 24h-volume-based ratios."
#
# METHOD:
#   For each profitable path found:
#     1. Fetch the FULL order book for each trade edge
#     2. Compute VWAP (Volume-Weighted Average Price) at the actual trade size
#     3. Compare: mid-price profit vs VWAP-adjusted profit
#     4. Report what fraction of paths remain profitable under VWAP
#
# This proves that our fee-inclusive edge rates already approximate
# real execution prices, or quantifies how far off they are.
# ======================================================================

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from math import log
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.data import EXCHANGES, COIN_MARKETS
from scripts.fees import TRADING_FEES_TAKER

from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)
from scripts.three_hop_baseline import (
    three_hop_enumeration,
    PlanResult as ThreeHopPlanResult,
)

# ── Configuration ──────────────────────────────────────────────────────
CASH_LEVELS = [1_000.0, 10_000.0, 50_000.0, 100_000.0]
NUM_START_NODES = 8
MAX_DEPTH = 5
MAX_TIME_SEC = 60.0
ORDER_BOOK_DEPTH = 50  # levels to fetch


def _fetch_order_book(exchange_name: str, market: str, limit: int = ORDER_BOOK_DEPTH) -> Optional[Dict]:
    """Fetch order book for a given market."""
    ex = EXCHANGES.get(exchange_name)
    if ex is None:
        return None
    try:
        ob = ex.fetch_order_book(market, limit=limit)
        return ob
    except Exception:
        return None


def _compute_vwap(
    levels: List[List[float]],
    target_amount_base: float,
) -> Optional[float]:
    """
    Compute VWAP for a given order size from order book levels.
    
    levels: [[price, size], [price, size], ...]
    target_amount_base: amount in base currency to fill
    
    Returns: VWAP price, or None if not enough liquidity
    """
    if not levels:
        return None

    total_cost = 0.0
    total_filled = 0.0

    for price, size in levels:
        if total_filled >= target_amount_base:
            break

        fill = min(size, target_amount_base - total_filled)
        total_cost += fill * price
        total_filled += fill

    if total_filled < target_amount_base * 0.95:
        # Not enough liquidity to fill the order
        return None

    return total_cost / total_filled if total_filled > 0 else None


def _compute_vwap_slippage_for_trade(
    exchange_name: str,
    coin_from: str,
    coin_to: str,
    amount_usd: float,
) -> Dict[str, Any]:
    """
    Compute VWAP-based execution price for a trade on an exchange.
    
    Returns dict with mid_price, vwap_price, slippage_bps, etc.
    """
    # Find the market symbol for this pair
    market_from = COIN_MARKETS.get(coin_from, {}).get(exchange_name)
    market_to = COIN_MARKETS.get(coin_to, {}).get(exchange_name)

    # Try to find a direct trading pair
    # Common patterns: COIN_FROM/COIN_TO or COIN_TO/COIN_FROM
    direct_market = None
    side = None

    # Check if there's a direct pair like "COIN_FROM/COIN_TO"
    possible_markets = [
        f"{coin_from}/{coin_to}",
        f"{coin_to}/{coin_from}",
    ]

    ex = EXCHANGES.get(exchange_name)
    if ex is None:
        return {"error": "exchange_not_found"}

    try:
        ex.load_markets()
    except Exception:
        pass

    for pm in possible_markets:
        if pm in ex.markets:
            direct_market = pm
            base, quote = pm.split("/")
            if base == coin_from:
                side = "sell"  # selling coin_from for coin_to
            else:
                side = "buy"   # buying coin_from with coin_to
            break

    if direct_market is None:
        return {"error": f"no_direct_market_{coin_from}_{coin_to}"}

    # Fetch order book
    ob = _fetch_order_book(exchange_name, direct_market)
    if ob is None:
        return {"error": "orderbook_fetch_failed"}

    bids = ob.get("bids", [])
    asks = ob.get("asks", [])

    if not bids or not asks:
        return {"error": "empty_orderbook"}

    # Mid price
    best_bid = bids[0][0]
    best_ask = asks[0][0]
    mid_price = (best_bid + best_ask) / 2.0

    # Calculate how much base currency we need
    base_currency, quote_currency = direct_market.split("/")
    if side == "sell":
        # Selling base → we have `amount_usd` worth of base to sell
        amount_base = amount_usd / mid_price if mid_price > 0 else 0
        vwap = _compute_vwap(bids, amount_base)
    else:
        # Buying base → we spend `amount_usd` of quote
        amount_base = amount_usd / mid_price if mid_price > 0 else 0
        vwap = _compute_vwap(asks, amount_base)

    if vwap is None:
        return {
            "market": direct_market,
            "side": side,
            "mid_price": mid_price,
            "vwap": None,
            "slippage_bps": None,
            "error": "insufficient_liquidity",
            "best_bid": best_bid,
            "best_ask": best_ask,
            "book_depth_bids": len(bids),
            "book_depth_asks": len(asks),
        }

    # Slippage in basis points
    slippage_bps = abs(vwap - mid_price) / mid_price * 10_000

    return {
        "market": direct_market,
        "side": side,
        "mid_price": mid_price,
        "vwap": vwap,
        "slippage_bps": round(slippage_bps, 2),
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread_bps": round((best_ask - best_bid) / mid_price * 10_000, 2),
        "book_depth_bids": len(bids),
        "book_depth_asks": len(asks),
        "amount_usd": amount_usd,
    }


def _evaluate_path_with_vwap(
    path: List[NodeId],
    edges: List[Dict[str, Any]],
    initial_cash: float,
) -> Dict[str, Any]:
    """
    Re-evaluate a path using VWAP prices instead of mid prices.
    """
    current_cash_mid = initial_cash
    current_cash_vwap = initial_cash
    trade_slippages = []

    for edge in edges:
        kind = edge.get("kind")

        if kind == "trade":
            exchange = edge.get("exchange", "")
            coin_from = edge.get("coin_from", "")
            coin_to = edge.get("coin_to", "")
            rate = edge.get("rate", 1.0)
            taker_fee = edge.get("taker_fee", 0.0)

            # Mid-price path
            current_cash_mid *= rate

            # VWAP path
            vwap_result = _compute_vwap_slippage_for_trade(
                exchange, coin_from, coin_to, current_cash_vwap
            )
            trade_slippages.append(vwap_result)

            if vwap_result.get("vwap") is not None and vwap_result.get("mid_price"):
                # Adjust the rate by the VWAP/mid ratio
                vwap_ratio = vwap_result["vwap"] / vwap_result["mid_price"]

                if vwap_result["side"] == "sell":
                    # Selling: VWAP < mid means we get less
                    vwap_adjusted_rate = rate * vwap_ratio
                else:
                    # Buying: VWAP > mid means we pay more (but the rate should decrease)
                    vwap_adjusted_rate = rate / vwap_ratio

                current_cash_vwap *= vwap_adjusted_rate
            else:
                # Fallback to mid-price rate if VWAP unavailable
                current_cash_vwap *= rate

        elif kind == "transfer":
            rate = edge.get("rate", 1.0)
            current_cash_mid *= rate
            current_cash_vwap *= rate

    mid_profit = current_cash_mid - initial_cash
    vwap_profit = current_cash_vwap - initial_cash

    avg_slippage = None
    valid_slippages = [s.get("slippage_bps") for s in trade_slippages if s.get("slippage_bps") is not None]
    if valid_slippages:
        avg_slippage = sum(valid_slippages) / len(valid_slippages)

    return {
        "mid_final_cash": round(current_cash_mid, 4),
        "vwap_final_cash": round(current_cash_vwap, 4),
        "mid_profit": round(mid_profit, 4),
        "vwap_profit": round(vwap_profit, 4),
        "still_profitable_vwap": vwap_profit > 0,
        "profit_erosion_pct": round(
            ((mid_profit - vwap_profit) / mid_profit * 100) if mid_profit > 0 else 0, 2
        ),
        "avg_slippage_bps": round(avg_slippage, 2) if avg_slippage is not None else None,
        "trade_details": trade_slippages,
    }


def main():
    random.seed(42)

    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"slippage_vwap_{timestamp}.jsonl"

    print("=== VWAP Slippage Verification Experiment ===")
    print(f"Cash levels: {CASH_LEVELS}")
    print(f"Order book depth: {ORDER_BOOK_DEPTH} levels")
    print(f"Output: {out_path}")
    print()

    # Build graph
    print("Building graph...")
    nodes, adj = build_graph(force_refresh=True)
    print(f"  {len(nodes)} nodes")

    # Start nodes
    starts = list(nodes.keys())
    random.shuffle(starts)
    starts = starts[:NUM_START_NODES]

    # Accumulate results
    total_paths = 0
    survived_vwap = 0
    all_erosions = []
    all_slippages = []

    with out_path.open("w", encoding="utf-8") as fout:
        for cash in CASH_LEVELS:
            print(f"\n{'='*60}")
            print(f"Cash: ${cash:,.2f}")
            print(f"{'='*60}")

            for start in starts:
                # Find paths with H1
                result = None
                try:
                    result = astar_best_path_with_liquidity(
                        start_node=start,
                        liquid_cash_usd=cash,
                        max_depth=MAX_DEPTH,
                        max_time_sec=MAX_TIME_SEC,
                        heuristic="h1_liquidity",
                    )
                except Exception:
                    pass

                if result is None or result.profit_usd <= 0:
                    continue

                total_paths += 1

                # Evaluate with VWAP
                vwap_eval = _evaluate_path_with_vwap(
                    result.path, result.edges, cash
                )

                if vwap_eval["still_profitable_vwap"]:
                    survived_vwap += 1

                erosion = vwap_eval["profit_erosion_pct"]
                all_erosions.append(erosion)

                if vwap_eval["avg_slippage_bps"] is not None:
                    all_slippages.append(vwap_eval["avg_slippage_bps"])

                status = "✓ SURVIVED" if vwap_eval["still_profitable_vwap"] else "✗ ERASED"
                print(
                    f"  [{status}] {start[0]}:{start[1]:>6s} "
                    f"mid=${vwap_eval['mid_profit']:.4f} → "
                    f"vwap=${vwap_eval['vwap_profit']:.4f} "
                    f"(erosion={erosion:+.1f}%, "
                    f"avg_slip={vwap_eval['avg_slippage_bps'] or '?'}bps)"
                )

                # Write record
                record = {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "cash_usd": cash,
                    "start": f"{start[0]}:{start[1]}",
                    "path": [f"{e}:{c}" for e, c in result.path],
                    "mid_profit": vwap_eval["mid_profit"],
                    "vwap_profit": vwap_eval["vwap_profit"],
                    "still_profitable_vwap": vwap_eval["still_profitable_vwap"],
                    "profit_erosion_pct": erosion,
                    "avg_slippage_bps": vwap_eval["avg_slippage_bps"],
                }
                fout.write(json.dumps(record) + "\n")
                fout.flush()

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("VWAP SLIPPAGE SUMMARY")
    print(f"{'='*60}")

    if total_paths > 0:
        survival_rate = survived_vwap / total_paths * 100
        print(f"Total profitable paths found:  {total_paths}")
        print(f"Survived VWAP adjustment:      {survived_vwap} ({survival_rate:.1f}%)")

        if all_erosions:
            avg_erosion = sum(all_erosions) / len(all_erosions)
            max_erosion = max(all_erosions)
            print(f"Avg profit erosion:            {avg_erosion:.2f}%")
            print(f"Max profit erosion:            {max_erosion:.2f}%")

        if all_slippages:
            avg_slip = sum(all_slippages) / len(all_slippages)
            max_slip = max(all_slippages)
            print(f"Avg slippage:                  {avg_slip:.2f} bps")
            print(f"Max slippage:                  {max_slip:.2f} bps")
    else:
        print("No profitable paths found to evaluate.")

    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()

