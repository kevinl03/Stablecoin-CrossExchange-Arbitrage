# ======================================================================
# quote_staleness_test.py — Path survival analysis under quote delays
# ======================================================================
#
# PURPOSE: Addresses Hang Ma's feedback:
#   "No end-to-end executions... no out-of-sample validation or replay
#    analysis is presented to verify that identified paths remain profitable
#    under realistic latencies and order placement."
#   "Given the tiny margins (~0.04%), even small slippage or quote
#    staleness could erase profit."
#
# METHOD:
#   1. Build a fresh graph and find all profitable paths
#   2. Wait DELAY seconds (5, 10, 30, 60, 120, 300)
#   3. Re-fetch prices and re-evaluate each path's edges
#   4. Check if the path is still profitable with NEW prices
#   5. Report "path survival rate" at each delay
#
# This is the closest we can get to paper-trading without executing
# real trades — it measures how quickly arbitrage opportunities decay.
# ======================================================================

from __future__ import annotations

import json
import random
import sys
import time
from datetime import datetime, timezone
from math import exp, log
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.data import EXCHANGES, COIN_MARKETS

from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)
from scripts.three_hop_baseline import (
    three_hop_enumeration,
    PlanResult as ThreeHopPlanResult,
)

# ── Configuration ──────────────────────────────────────────────────────
DELAY_SECONDS = [5, 10, 30, 60, 120, 300]  # Delays to test (seconds)
NUM_ROUNDS: int = 10                         # Number of find-and-check rounds
CASH_USD: float = 10_000.0
NUM_START_NODES: int = 5
MAX_DEPTH: int = 5
MAX_TIME_SEC: float = 60.0
HEURISTICS_TO_TEST = ["h1_liquidity", "3hop_enum"]


# ── Price re-fetching ──────────────────────────────────────────────────

def _refetch_price(exchange_name: str, coin: str) -> Optional[float]:
    """Fetch a fresh price for a single (exchange, coin) pair."""
    market = COIN_MARKETS.get(coin, {}).get(exchange_name)
    if not market:
        return None

    ex = EXCHANGES.get(exchange_name)
    if ex is None:
        return None

    try:
        ticker = ex.fetch_ticker(market)
        bid = ticker.get("bid")
        ask = ticker.get("ask")
        last = ticker.get("last")

        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
            mid = (bid + ask) / 2.0
        elif isinstance(last, (int, float)):
            mid = float(last)
        else:
            return None

        from scripts.data import normalize_price_to_usd
        return normalize_price_to_usd(coin, market, mid)
    except Exception:
        return None


def _reevaluate_path_with_fresh_prices(
    path: List[NodeId],
    edges: List[Dict[str, Any]],
    initial_cash: float,
) -> Dict[str, Any]:
    """
    Re-evaluate a previously found path using freshly fetched prices.

    For each edge in the path:
      - Trade edges: re-fetch the trading pair's bid/ask and recalculate rate
      - Transfer edges: keep the same fees (withdrawal/gas fees don't change with price)

    Returns a dict with the new final_cash, new profit, and whether the path
    is still profitable.
    """
    current_cash = initial_cash
    new_rates = []
    re_eval_errors = []

    for i, edge in enumerate(edges):
        kind = edge.get("kind")

        if kind == "trade":
            exchange = edge.get("exchange", "")
            coin_from = edge.get("coin_from", "")
            coin_to = edge.get("coin_to", "")
            taker_fee = edge.get("taker_fee", 0.0)

            # Re-fetch prices for the trade pair
            price_from = _refetch_price(exchange, coin_from)
            price_to = _refetch_price(exchange, coin_to)

            if price_from is None or price_to is None or price_to == 0:
                re_eval_errors.append(f"edge_{i}: could not refetch {exchange}:{coin_from}->{coin_to}")
                # Use original rate as fallback
                rate = edge.get("rate", 1.0)
            else:
                # Recalculate rate: how many coin_to per coin_from
                raw_rate = price_from / price_to
                rate = raw_rate * (1.0 - taker_fee)

            current_cash *= rate
            new_rates.append(rate)

        elif kind == "transfer":
            # Transfer fees are static (withdrawal + gas), not price-dependent
            rate = edge.get("rate", 1.0)
            current_cash *= rate
            new_rates.append(rate)

    profit = current_cash - initial_cash
    return {
        "new_final_cash": round(current_cash, 4),
        "new_profit": round(profit, 4),
        "still_profitable": profit > 0,
        "profit_decay_pct": None,  # calculated below
        "new_rates": new_rates,
        "errors": re_eval_errors,
    }


# ── Main experiment ───────────────────────────────────────────────────

def main():
    random.seed(int(time.time()))

    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"quote_staleness_{timestamp}.jsonl"

    print("=== Quote Staleness Experiment ===")
    print(f"Delays to test: {DELAY_SECONDS} seconds")
    print(f"Rounds: {NUM_ROUNDS}")
    print(f"Cash: ${CASH_USD:,.2f}")
    print(f"Heuristics: {HEURISTICS_TO_TEST}")
    print(f"Output: {out_path}")
    print()

    # Accumulate survival stats
    # survival_stats[delay][heuristic] = {"survived": int, "total": int}
    survival_stats: Dict[int, Dict[str, Dict[str, int]]] = {
        d: {h: {"survived": 0, "total": 0} for h in HEURISTICS_TO_TEST}
        for d in DELAY_SECONDS
    }

    with out_path.open("w", encoding="utf-8") as fout:
        for round_idx in range(1, NUM_ROUNDS + 1):
            print(f"\n{'='*60}")
            print(f"Round {round_idx}/{NUM_ROUNDS} — {datetime.now(timezone.utc).isoformat()}")
            print(f"{'='*60}")

            # 1. Build fresh graph
            try:
                nodes, adj = build_graph(force_refresh=True)
            except Exception as e:
                print(f"  [ERROR] Graph build failed: {e}")
                continue

            # 2. Pick start nodes
            starts = list(nodes.keys())
            random.shuffle(starts)
            starts = starts[:NUM_START_NODES]

            # 3. Find profitable paths with each heuristic
            found_paths: List[Dict[str, Any]] = []

            for heur in HEURISTICS_TO_TEST:
                for start in starts:
                    result = None
                    try:
                        if heur == "h1_liquidity":
                            result = astar_best_path_with_liquidity(
                                start_node=start,
                                liquid_cash_usd=CASH_USD,
                                max_depth=MAX_DEPTH,
                                max_time_sec=MAX_TIME_SEC,
                                heuristic="h1_liquidity",
                            )
                        elif heur == "3hop_enum":
                            result = three_hop_enumeration(
                                start_node=start,
                                liquid_cash_usd=CASH_USD,
                                max_time_sec=MAX_TIME_SEC,
                            )
                    except Exception:
                        pass

                    if result is not None and result.profit_usd > 0:
                        found_paths.append({
                            "heuristic": heur,
                            "start": f"{start[0]}:{start[1]}",
                            "path": result.path,
                            "edges": result.edges,
                            "original_profit": result.profit_usd,
                            "original_final_cash": result.final_cash_usd,
                        })
                        print(
                            f"  Found: {heur} from {start[0]}:{start[1]} — "
                            f"profit=${result.profit_usd:.4f}"
                        )

            if not found_paths:
                print("  No profitable paths found in this round. Skipping delays.")
                continue

            print(f"\n  Found {len(found_paths)} profitable paths. Testing staleness...")

            # 4. For each delay, wait then re-check all paths
            for delay in DELAY_SECONDS:
                print(f"\n  Delay: {delay}s — waiting...")
                time.sleep(delay)

                for fp in found_paths:
                    heur = fp["heuristic"]
                    reeval = _reevaluate_path_with_fresh_prices(
                        path=fp["path"],
                        edges=fp["edges"],
                        initial_cash=CASH_USD,
                    )

                    original_profit = fp["original_profit"]
                    new_profit = reeval["new_profit"]

                    # Decay %
                    if original_profit > 0:
                        decay_pct = ((original_profit - new_profit) / original_profit) * 100
                    else:
                        decay_pct = 0.0
                    reeval["profit_decay_pct"] = round(decay_pct, 2)

                    survived = reeval["still_profitable"]
                    survival_stats[delay][heur]["total"] += 1
                    if survived:
                        survival_stats[delay][heur]["survived"] += 1

                    status = "✓ SURVIVED" if survived else "✗ DECAYED"
                    print(
                        f"    [{status}] {heur:20s} {fp['start']:15s} "
                        f"orig=${original_profit:.4f} → new=${new_profit:.4f} "
                        f"(decay={decay_pct:+.1f}%)"
                    )

                    # Write record
                    record = {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "round": round_idx,
                        "delay_sec": delay,
                        "heuristic": heur,
                        "start": fp["start"],
                        "original_profit": round(original_profit, 4),
                        "new_profit": new_profit,
                        "still_profitable": survived,
                        "profit_decay_pct": reeval["profit_decay_pct"],
                        "path": [f"{e}:{c}" for e, c in fp["path"]],
                    }
                    fout.write(json.dumps(record) + "\n")
                    fout.flush()

    # ── Summary ────────────────────────────────────────────────────────
    print(f"\n\n{'='*60}")
    print("SURVIVAL RATE SUMMARY")
    print(f"{'='*60}")
    print(f"{'Delay (s)':>10s}", end="")
    for h in HEURISTICS_TO_TEST:
        print(f"  {h:>25s}", end="")
    print()

    for delay in DELAY_SECONDS:
        print(f"{delay:>10d}", end="")
        for h in HEURISTICS_TO_TEST:
            s = survival_stats[delay][h]
            if s["total"] > 0:
                rate = s["survived"] / s["total"] * 100
                print(f"  {rate:>20.1f}% ({s['survived']}/{s['total']})", end="")
            else:
                print(f"  {'N/A':>25s}", end="")
        print()

    print(f"\nResults saved to: {out_path}")


if __name__ == "__main__":
    main()

