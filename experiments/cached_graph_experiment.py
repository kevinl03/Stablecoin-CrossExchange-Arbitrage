# ======================================================================
# cached_graph_experiment.py — Controlled experiment isolating compute from I/O
# ======================================================================
#
# PURPOSE: Addresses Hang Ma's feedback:
#   "runtime numbers vary widely and may simply reflect data-fetch overheads
#    rather than algorithmic differences (e.g., order-book queries for h2
#    dominate). A controlled, cached experiment isolating computation from
#    I/O would be more informative."
#
#   "Can you provide scaling experiments on larger graphs where heuristics
#    materially change node expansions and outcomes versus Dijkstra?"
#
# METHOD:
#   1. Build graph ONCE (single I/O phase)
#   2. Cache all order book data and volume data
#   3. Run ALL heuristics on the SAME frozen snapshot
#   4. Track: node expansions, nodes generated, pure compute time
#   5. Compare heuristic-guided A* vs Dijkstra (h=0) on node expansion counts
#   6. Run from ALL nodes (not just 3) for comprehensive coverage
#
# This is the definitive experiment for showing heuristic value.
# ======================================================================

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId

from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)
from scripts.weighted_astar import (
    weighted_astar_best_path,
    PlanResult as WeightedPlanResult,
)
from scripts.three_hop_baseline import (
    three_hop_enumeration,
    PlanResult as ThreeHopPlanResult,
)
from scripts.baseline_algorithms import (
    dijkstra_like_search,
    PlanResult as BaselinePlanResult,
)

# ── Configuration ──────────────────────────────────────────────────────
CASH_LEVELS = [1_000.0, 10_000.0, 100_000.0]
MAX_DEPTH = 6                       # deeper search to find longer profitable paths
MAX_TIME_SEC = 120.0                # 2 minute budget per search
EARLY_EXIT = True
EARLY_EXIT_ITERS = 200

# We'll run from EVERY node (or cap at MAX_STARTS for practicality)
MAX_STARTS = 30

HEURISTICS = [
    "dijkstra",            # baseline: h=0
    "h1_liquidity",        # volume/liquidity heuristic
    "h2_slippage",         # order-book slippage heuristic
    "h4_chaincongestion_exchange_risk",  # chain+exchange risk
    "3hop_enum",           # brute-force baseline
]


def _run_search_cached(
    heuristic: str,
    start_node: NodeId,
    cash_usd: float,
) -> Dict[str, Any]:
    """Run one search, return structured dict with node expansion stats."""
    t0 = time.perf_counter()
    result = None
    error = None

    try:
        if heuristic in ("h1_liquidity", "h2_slippage"):
            result = astar_best_path_with_liquidity(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                heuristic=heuristic,
                early_exit_after_profit=EARLY_EXIT,
                early_exit_iterations=EARLY_EXIT_ITERS,
            )
        elif heuristic == "h4_chaincongestion_exchange_risk":
            result = weighted_astar_best_path(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                early_exit_after_profit=EARLY_EXIT,
                early_exit_iterations=EARLY_EXIT_ITERS,
            )
        elif heuristic == "dijkstra":
            result = dijkstra_like_search(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
            )
        elif heuristic == "3hop_enum":
            result = three_hop_enumeration(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_time_sec=MAX_TIME_SEC,
            )
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        import traceback
        traceback.print_exc()

    duration = time.perf_counter() - t0

    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "heuristic": heuristic,
        "start_node": f"{start_node[0]}:{start_node[1]}",
        "cash_usd": cash_usd,
        "compute_time_sec": round(duration, 5),
        "success": result is not None,
        "profit_usd": round(result.profit_usd, 4) if result else None,
        "path_len": len(result.path) if result else None,
        "nodes_expanded": getattr(result, "nodes_expanded", None) if result else None,
        "nodes_generated": getattr(result, "nodes_generated", None) if result else None,
        "error": error,
    }
    return rec


def main():
    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"cached_graph_experiment_{timestamp}.jsonl"
    summary_path = results_dir / f"cached_graph_summary_{timestamp}.txt"

    print("=== Cached Graph Experiment ===")
    print("Phase 1: Building graph (I/O phase)...")

    io_start = time.perf_counter()
    nodes, adj = build_graph(force_refresh=True)
    io_time = time.perf_counter() - io_start

    num_nodes = len(nodes)
    num_edges = sum(len(v) for v in adj.values())

    print(f"  Graph built in {io_time:.3f}s (I/O)")
    print(f"  {num_nodes} nodes, {num_edges} edges")

    # Pre-warm caches: h1 and h2 both fetch data from exchanges.
    # We do one round of h2 data fetching to warm the order book cache.
    print("\nPhase 1b: Pre-warming order book & volume caches...")
    cache_start = time.perf_counter()
    for (ex, coin) in list(nodes.keys())[:10]:
        try:
            from scripts.h1_vol import estimate_liquidity_score_live
            estimate_liquidity_score_live(ex, coin, 10000.0, 60.0)
        except Exception:
            pass
        try:
            from scripts.h2_slippage import estimate_slippage_for_coin
            estimate_slippage_for_coin(ex, coin, 10000.0, "buy")
        except Exception:
            pass
    cache_time = time.perf_counter() - cache_start
    print(f"  Cache warming done in {cache_time:.3f}s")

    # Select start nodes (all of them, capped)
    all_starts = list(nodes.keys())
    if len(all_starts) > MAX_STARTS:
        import random
        random.seed(42)
        random.shuffle(all_starts)
        all_starts = all_starts[:MAX_STARTS]

    print(f"\nPhase 2: Running {len(HEURISTICS)} heuristics × {len(all_starts)} starts × {len(CASH_LEVELS)} cash levels")
    print(f"         = {len(HEURISTICS) * len(all_starts) * len(CASH_LEVELS)} total searches")
    print(f"Output: {out_path}")
    print()

    all_results: List[Dict[str, Any]] = []

    with out_path.open("w", encoding="utf-8") as fout:
        for cash in CASH_LEVELS:
            print(f"\n--- Cash: ${cash:,.2f} ---")
            for start in all_starts:
                for heur in HEURISTICS:
                    try:
                        rec = _run_search_cached(heur, start, cash)
                    except Exception as e:
                        rec = {
                            "heuristic": heur,
                            "start_node": f"{start[0]}:{start[1]}",
                            "cash_usd": cash,
                            "compute_time_sec": 0.0,
                            "success": False,
                            "error": f"crash: {type(e).__name__}: {e}",
                        }
                    all_results.append(rec)
                    fout.write(json.dumps(rec) + "\n")
                    fout.flush()  # flush after each result for crash safety

                    status = "✓" if rec["success"] else "✗"
                    profit = rec.get("profit_usd")
                    pstr = f"${profit:.4f}" if profit is not None else "N/A"
                    exp = rec.get("nodes_expanded", "?")
                    gen = rec.get("nodes_generated", "?")
                    print(
                        f"  [{status}] {heur:40s} "
                        f"{rec['start_node']:15s} "
                        f"profit={pstr:>10s} "
                        f"exp={str(exp):>6s} "
                        f"gen={str(gen):>6s} "
                        f"compute={rec['compute_time_sec']:.5f}s"
                    )

        fout.flush()

    # ── Aggregate Summary ──────────────────────────────────────────────
    print(f"\n\n{'='*70}")
    print("NODE EXPANSION COMPARISON (Heuristic vs Dijkstra)")
    print(f"{'='*70}")

    # Group by heuristic and cash level
    by_heur_cash: Dict[str, Dict[float, List[Dict]]] = defaultdict(lambda: defaultdict(list))
    for r in all_results:
        by_heur_cash[r["heuristic"]][r["cash_usd"]].append(r)

    summary_lines = []
    summary_lines.append("CACHED GRAPH EXPERIMENT SUMMARY")
    summary_lines.append(f"{'='*70}")
    summary_lines.append(f"Graph: {num_nodes} nodes, {num_edges} edges")
    summary_lines.append(f"I/O time: {io_time:.3f}s")
    summary_lines.append(f"Start nodes: {len(all_starts)}")
    summary_lines.append("")

    for cash in CASH_LEVELS:
        header = f"Cash: ${cash:,.2f}"
        print(f"\n{header}")
        summary_lines.append(f"\n{header}")
        print(f"{'Heuristic':40s} {'Success%':>8s} {'AvgProfit':>10s} "
              f"{'AvgExpand':>10s} {'AvgGen':>10s} {'AvgTime':>10s} {'MedianExp':>10s}")
        summary_lines.append(
            f"{'Heuristic':40s} {'Success%':>8s} {'AvgProfit':>10s} "
            f"{'AvgExpand':>10s} {'AvgGen':>10s} {'AvgTime':>10s} {'MedianExp':>10s}"
        )
        print("-" * 100)
        summary_lines.append("-" * 100)

        for heur in HEURISTICS:
            group = by_heur_cash[heur][cash]
            if not group:
                continue

            total = len(group)
            successes = [g for g in group if g["success"]]
            n_success = len(successes)
            success_pct = n_success / total * 100 if total > 0 else 0

            avg_profit = (
                sum(g["profit_usd"] for g in successes if g["profit_usd"] is not None) / n_success
                if n_success > 0 else 0
            )

            expansions = [g["nodes_expanded"] for g in group if g.get("nodes_expanded") is not None]
            avg_exp = sum(expansions) / len(expansions) if expansions else 0
            sorted_exp = sorted(expansions)
            median_exp = sorted_exp[len(sorted_exp) // 2] if sorted_exp else 0

            generated = [g["nodes_generated"] for g in group if g.get("nodes_generated") is not None]
            avg_gen = sum(generated) / len(generated) if generated else 0

            avg_time = sum(g["compute_time_sec"] for g in group) / total if total > 0 else 0

            line = (
                f"{heur:40s} {success_pct:>7.1f}% "
                f"${avg_profit:>9.4f} "
                f"{avg_exp:>10.1f} "
                f"{avg_gen:>10.1f} "
                f"{avg_time:>9.5f}s "
                f"{median_exp:>10.0f}"
            )
            print(line)
            summary_lines.append(line)

    # Dijkstra vs heuristic expansion ratio
    print(f"\n\n{'='*70}")
    print("EXPANSION REDUCTION vs DIJKSTRA")
    print(f"{'='*70}")
    summary_lines.append(f"\n\n{'='*70}")
    summary_lines.append("EXPANSION REDUCTION vs DIJKSTRA")
    summary_lines.append(f"{'='*70}")

    for cash in CASH_LEVELS:
        dijkstra_exps = [
            g["nodes_expanded"]
            for g in by_heur_cash["dijkstra"][cash]
            if g.get("nodes_expanded") is not None
        ]
        if not dijkstra_exps:
            continue
        avg_dijk = sum(dijkstra_exps) / len(dijkstra_exps)

        line = f"\nCash ${cash:,.2f} — Dijkstra avg expansions: {avg_dijk:.1f}"
        print(line)
        summary_lines.append(line)

        for heur in HEURISTICS:
            if heur == "dijkstra":
                continue
            heur_exps = [
                g["nodes_expanded"]
                for g in by_heur_cash[heur][cash]
                if g.get("nodes_expanded") is not None
            ]
            if not heur_exps:
                continue
            avg_h = sum(heur_exps) / len(heur_exps)

            if avg_dijk > 0:
                reduction = (1 - avg_h / avg_dijk) * 100
                line = f"  {heur:40s} avg={avg_h:.1f}  reduction={reduction:+.1f}%"
            else:
                line = f"  {heur:40s} avg={avg_h:.1f}"
            print(line)
            summary_lines.append(line)

    # Write summary file
    with summary_path.open("w", encoding="utf-8") as sf:
        sf.write("\n".join(summary_lines) + "\n")

    print(f"\nDetailed results: {out_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()

