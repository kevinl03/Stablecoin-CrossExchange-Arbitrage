# ======================================================================
# graph_scaling_test.py — Graph scaling experiments (4/6/8/10/12 exchanges)
# ======================================================================
#
# PURPOSE: Addresses Hang Ma's feedback:
#   "Can you provide scaling experiments on larger graphs (more exchanges/
#    assets, deeper paths) where heuristics materially change node
#    expansions and outcomes versus Dijkstra? How does performance scale
#    with graph size and number of start nodes?"
#
# METHOD:
#   We artificially restrict the graph to subsets of exchanges:
#     4 exchanges  → ~15 nodes
#     6 exchanges  → ~22 nodes
#     8 exchanges  → ~30 nodes
#     10 exchanges → ~35 nodes
#     12 exchanges → ~41 nodes (full graph)
#
#   For each graph size we run Dijkstra vs H1 vs H4 from all start nodes
#   and compare:
#     - Node expansions
#     - Nodes generated
#     - Runtime (pure compute)
#     - Success rate / profit
# ======================================================================

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import scripts.data as data_module
import scripts.graph as graph_module
from scripts.graph import build_graph, NodeId

from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)
from scripts.weighted_astar import (
    weighted_astar_best_path,
    PlanResult as WeightedPlanResult,
)
from scripts.baseline_algorithms import (
    dijkstra_like_search,
    PlanResult as BaselinePlanResult,
)
from scripts.three_hop_baseline import (
    three_hop_enumeration,
    PlanResult as ThreeHopPlanResult,
)

# ── Configuration ──────────────────────────────────────────────────────
CASH_USD = 10_000.0
MAX_DEPTH = 6
MAX_TIME_SEC = 120.0
EARLY_EXIT = True
EARLY_EXIT_ITERS = 200
MAX_STARTS = 10  # per graph size

EXCHANGE_TIERS = [
    # Tier 1: 4 major exchanges
    ["binance", "kraken", "kucoin", "bybit"],
    # Tier 2: 6 exchanges
    ["binance", "kraken", "kucoin", "bybit", "okx", "gateio"],
    # Tier 3: 8 exchanges
    ["binance", "kraken", "kucoin", "bybit", "okx", "gateio", "bitget", "mexc"],
    # Tier 4: 10 exchanges
    ["binance", "kraken", "kucoin", "bybit", "okx", "gateio", "bitget", "mexc", "htx", "coinbase"],
    # Tier 5: All 12 exchanges
    ["binance", "kraken", "kucoin", "bybit", "okx", "gateio", "bitget", "mexc", "htx", "coinbase", "cryptocom", "phemex"],
]

HEURISTICS = ["dijkstra", "h1_liquidity", "h4_chaincongestion_exchange_risk", "3hop_enum"]


def _build_restricted_graph(exchange_subset: List[str]) -> Tuple[Dict, Dict]:
    """
    Build the graph but only include nodes from the given exchange subset.
    
    We do this by temporarily replacing the EXCHANGES dict in data.py,
    building the graph, then restoring it.
    """
    import scripts.graph as graph_module
    
    # Save originals
    original_exchanges = data_module.EXCHANGES.copy()
    
    # Restrict to subset
    restricted = {k: v for k, v in original_exchanges.items() if k in exchange_subset}
    data_module.EXCHANGES.clear()
    data_module.EXCHANGES.update(restricted)
    
    # Invalidate cache
    graph_module._CACHED_GRAPH = None
    graph_module._CACHE_TIMESTAMP = None
    
    try:
        nodes, adj = build_graph(force_refresh=True, portfolio_size_usd=CASH_USD)
    finally:
        # Restore original exchanges
        data_module.EXCHANGES.clear()
        data_module.EXCHANGES.update(original_exchanges)
        # Invalidate cache again
        graph_module._CACHED_GRAPH = None
        graph_module._CACHE_TIMESTAMP = None
    
    return nodes, adj


def _run_search(
    heuristic: str,
    start_node: NodeId,
    cash_usd: float,
) -> Dict[str, Any]:
    """Run one search and return structured result."""
    t0 = time.perf_counter()
    result = None
    error = None

    try:
        if heuristic == "h1_liquidity":
            result = astar_best_path_with_liquidity(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                heuristic="h1_liquidity",
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
        error = str(e)

    duration = time.perf_counter() - t0

    rec = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "heuristic": heuristic,
        "start_node": f"{start_node[0]}:{start_node[1]}",
        "cash_usd": cash_usd,
        "compute_sec": round(duration, 5),
        "success": result is not None,
        "profit": round(result.profit_usd, 4) if result else None,
        "path_len": len(result.path) if result else None,
        "nodes_expanded": getattr(result, "nodes_expanded", None) if result else None,
        "nodes_generated": getattr(result, "nodes_generated", None) if result else None,
        "error": error,
    }
    return rec


def main():
    random.seed(42)

    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"graph_scaling_{timestamp}.jsonl"
    summary_path = results_dir / f"graph_scaling_summary_{timestamp}.txt"

    print("=== Graph Scaling Experiment ===")
    print(f"Exchange tiers: {[len(t) for t in EXCHANGE_TIERS]}")
    print(f"Heuristics: {HEURISTICS}")
    print(f"Cash: ${CASH_USD:,.2f}")
    print(f"Output: {out_path}")
    print()

    all_results: List[Dict[str, Any]] = []
    scaling_data: List[Dict[str, Any]] = []

    with out_path.open("w", encoding="utf-8") as fout:
        for tier_idx, exchange_list in enumerate(EXCHANGE_TIERS):
            n_exchanges = len(exchange_list)
            print(f"\n{'='*60}")
            print(f"Tier {tier_idx+1}: {n_exchanges} exchanges — {exchange_list}")
            print(f"{'='*60}")

            # Build restricted graph
            try:
                nodes, adj = _build_restricted_graph(exchange_list)
            except Exception as e:
                print(f"  [ERROR] Could not build graph: {e}")
                continue

            n_nodes = len(nodes)
            n_edges = sum(len(v) for v in adj.values())
            print(f"  Graph: {n_nodes} nodes, {n_edges} edges")

            # Select start nodes
            starts = list(nodes.keys())
            random.shuffle(starts)
            starts = starts[:MAX_STARTS]

            tier_summary: Dict[str, Dict[str, Any]] = {}

            for heur in HEURISTICS:
                heur_results = []
                for start in starts:
                    rec = _run_search(heur, start, CASH_USD)
                    rec["n_exchanges"] = n_exchanges
                    rec["n_nodes"] = n_nodes
                    rec["n_edges"] = n_edges
                    heur_results.append(rec)
                    all_results.append(rec)
                    fout.write(json.dumps(rec) + "\n")

                # Aggregate
                successes = [r for r in heur_results if r["success"]]
                n_success = len(successes)
                avg_profit = sum(r["profit"] for r in successes) / n_success if n_success else 0
                exps = [r["nodes_expanded"] for r in heur_results if r.get("nodes_expanded") is not None]
                avg_exp = sum(exps) / len(exps) if exps else 0
                avg_time = sum(r["compute_sec"] for r in heur_results) / len(heur_results) if heur_results else 0

                tier_summary[heur] = {
                    "success_rate": n_success / len(heur_results) * 100 if heur_results else 0,
                    "avg_profit": avg_profit,
                    "avg_exp": avg_exp,
                    "avg_time": avg_time,
                }

                print(
                    f"  {heur:40s} "
                    f"success={n_success}/{len(heur_results)} "
                    f"avg_profit=${avg_profit:.4f} "
                    f"avg_exp={avg_exp:.0f} "
                    f"avg_time={avg_time:.5f}s"
                )

            scaling_data.append({
                "n_exchanges": n_exchanges,
                "n_nodes": n_nodes,
                "n_edges": n_edges,
                "summary": tier_summary,
            })

        fout.flush()

    # ── Print scaling table ────────────────────────────────────────────
    print(f"\n\n{'='*80}")
    print("SCALING TABLE: Node Expansions by Graph Size")
    print(f"{'='*80}")

    header = f"{'Exchanges':>10s} {'Nodes':>6s} {'Edges':>6s}"
    for h in HEURISTICS:
        header += f"  {h[:15]:>15s}"
    print(header)
    print("-" * len(header))

    summary_lines = [
        "GRAPH SCALING EXPERIMENT SUMMARY",
        "=" * 80,
        header,
        "-" * len(header),
    ]

    for sd in scaling_data:
        line = f"{sd['n_exchanges']:>10d} {sd['n_nodes']:>6d} {sd['n_edges']:>6d}"
        for h in HEURISTICS:
            if h in sd["summary"]:
                exp = sd["summary"][h]["avg_exp"]
                line += f"  {exp:>15.0f}"
            else:
                line += f"  {'N/A':>15s}"
        print(line)
        summary_lines.append(line)

    # Expansion reduction vs Dijkstra
    print(f"\n{'='*80}")
    print("EXPANSION REDUCTION vs DIJKSTRA by Graph Size")
    print(f"{'='*80}")
    summary_lines.append(f"\n{'='*80}")
    summary_lines.append("EXPANSION REDUCTION vs DIJKSTRA by Graph Size")
    summary_lines.append(f"{'='*80}")

    for sd in scaling_data:
        dijk_exp = sd["summary"].get("dijkstra", {}).get("avg_exp", 0)
        print(f"\n{sd['n_exchanges']} exchanges ({sd['n_nodes']} nodes, {sd['n_edges']} edges) — Dijkstra: {dijk_exp:.0f} expansions")
        summary_lines.append(f"\n{sd['n_exchanges']} exchanges ({sd['n_nodes']} nodes, {sd['n_edges']} edges) — Dijkstra: {dijk_exp:.0f} expansions")

        for h in HEURISTICS:
            if h == "dijkstra":
                continue
            h_exp = sd["summary"].get(h, {}).get("avg_exp", 0)
            if dijk_exp > 0:
                reduction = (1 - h_exp / dijk_exp) * 100
                line = f"  {h:40s} {h_exp:>6.0f} expansions  reduction={reduction:>+6.1f}%"
            else:
                line = f"  {h:40s} {h_exp:>6.0f} expansions"
            print(line)
            summary_lines.append(line)

    with summary_path.open("w", encoding="utf-8") as sf:
        sf.write("\n".join(summary_lines) + "\n")

    print(f"\nDetailed results: {out_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()

