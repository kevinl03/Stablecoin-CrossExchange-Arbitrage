#!/usr/bin/env python3
# ======================================================================
# escape_deadend_detailed.py — Check if lower-fee intermediate nodes exist
# ======================================================================
#
# Problem: Current escape analysis only looked for paths to major hubs
# Question: Are there intermediate exchange nodes with lower fees?
#
# Example: mexc:TUSD → gate_io:USDT (lower fees?) → kraken:USDT
#
# ======================================================================

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.astar_vol import astar_best_path_with_liquidity

# ── Configuration ──────────────────────────────────────────────────────

STUCK_NODE = ("mexc", "TUSD")  # Where we got stuck
STUCK_BALANCE = 10_009.76

# ── Enhanced Escape Analysis ───────────────────────────────────────────

def find_all_escape_routes(
    stuck_node: NodeId,
    stuck_balance: float,
) -> Dict[str, Any]:
    """
    Find paths to ANY reachable node, not just major hubs.
    This tests if intermediate nodes with lower fees could bridge the gap.
    """
    
    results = {
        "stuck_node": f"{stuck_node[0]}:{stuck_node[1]}",
        "stuck_balance": stuck_balance,
        "total_paths_tested": 0,
        "paths_found": [],
    }

    print(f"\n{'=' * 80}")
    print(f"DETAILED ESCAPE ANALYSIS: {stuck_node[0]}:{stuck_node[1]} (${stuck_balance:.2f})")
    print("=" * 80)
    print()
    print("[1] Building graph with live prices...")
    
    try:
        graph_start = time.time()
        nodes, edges = build_graph()
        graph_time = time.time() - graph_start
        print(f"    ✓ Graph ready ({len(nodes)} nodes, {len(edges)} edges) in {graph_time:.1f}s")
    except Exception as e:
        print(f"    ✗ Failed to build graph: {e}")
        return results

    print()
    print("[2] Analyzing escape routes to ALL reachable nodes...")
    print()

    # Get all nodes that are NOT the stuck node
    target_nodes = [node for node in nodes if node != stuck_node]
    print(f"    Testing {len(target_nodes)} target nodes...")
    print()

    profitable_paths = []
    breakeven_paths = []  # loss < $50
    acceptable_loss_paths = []  # loss < $500 (5%)
    catastrophic_paths = []  # loss >= $500

    # Test each target node with increasing search depths
    for i, target_node in enumerate(target_nodes):
        target_str = f"{target_node[0]}:{target_node[1]}"
        
        # Show progress
        if (i + 1) % 5 == 0:
            print(f"    [{i+1}/{len(target_nodes)}] Testing intermediate nodes...", flush=True)

        for max_depth in [2, 3, 4, 5]:
            try:
                result = astar_best_path_with_liquidity(
                    start_node=stuck_node,
                    liquid_cash_usd=stuck_balance,
                    max_depth=max_depth,
                    max_time_sec=20.0,
                    min_profit_usd=-stuck_balance,  # Allow any path (allow losses)
                    heuristic="h1_liquidity",
                    early_exit_after_profit=False,
                    early_exit_iterations=300,
                )

                if result and result.path and result.path[-1] == target_node:
                    profit = result.profit_usd
                    final_cash = result.final_cash_usd
                    path_length = len(result.path)
                    
                    path_info = {
                        "target": target_str,
                        "path": " → ".join([f"{ex}:{coin}" for ex, coin in result.path]),
                        "path_length": path_length,
                        "profit": profit,
                        "final_cash": final_cash,
                        "loss_pct": (profit / stuck_balance * 100) if profit < 0 else 0,
                        "nodes_expanded": result.nodes_expanded,
                    }

                    # Categorize
                    if profit > 0:
                        profitable_paths.append(path_info)
                    elif profit >= -50:  # Less than $50 loss
                        breakeven_paths.append(path_info)
                    elif profit >= -500:  # Less than 5% loss
                        acceptable_loss_paths.append(path_info)
                    else:
                        catastrophic_paths.append(path_info)

                    results["total_paths_tested"] += 1
                    break  # Found path to this node, move to next target

            except Exception as e:
                continue

    # Sort by profit
    profitable_paths.sort(key=lambda x: x["profit"], reverse=True)
    breakeven_paths.sort(key=lambda x: x["profit"], reverse=True)
    acceptable_loss_paths.sort(key=lambda x: x["profit"], reverse=True)
    catastrophic_paths.sort(key=lambda x: x["profit"], reverse=True)

    # ── Report Results ──────────────────────────────────────────────────────

    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()

    if profitable_paths:
        print("✓ PROFITABLE PATHS FOUND!")
        print()
        for i, path in enumerate(profitable_paths[:3], 1):
            print(f"  {i}. {path['target']} via {path['path_length']}-hop path")
            print(f"     Path: {path['path']}")
            print(f"     Profit: ${path['profit']:.2f}")
            print()
        results["recommendation"] = f"EXECUTE IMMEDIATELY! Found {len(profitable_paths)} profitable paths"
        results["paths_found"] = profitable_paths

    elif breakeven_paths:
        print("◦ BREAK-EVEN PATHS FOUND (minimal loss < $50)")
        print()
        for i, path in enumerate(breakeven_paths[:3], 1):
            print(f"  {i}. {path['target']} via {path['path_length']}-hop path")
            print(f"     Path: {path['path']}")
            print(f"     Loss: ${abs(path['profit']):.2f}")
            print()
        results["recommendation"] = f"Found {len(breakeven_paths)} break-even paths - acceptable exit"
        results["paths_found"] = breakeven_paths

    elif acceptable_loss_paths:
        print("◦ ACCEPTABLE LOSS PATHS FOUND (loss < 5%)")
        print()
        for i, path in enumerate(acceptable_loss_paths[:5], 1):
            loss_pct = path['loss_pct']
            print(f"  {i}. {path['target']} via {path['path_length']}-hop path")
            print(f"     Path: {path['path']}")
            print(f"     Loss: ${abs(path['profit']):.2f} ({loss_pct:.2f}%)")
            print()
        results["recommendation"] = f"Found {len(acceptable_loss_paths)} acceptable-loss paths"
        results["paths_found"] = acceptable_loss_paths

    else:
        print("✗ NO ESCAPE ROUTES FOUND at any loss threshold")
        print()
        print("   This confirms: wallet is TRULY trapped in mexc:TUSD")
        print()
        if catastrophic_paths:
            print(f"   Even catastrophic loss paths don't work ({len(catastrophic_paths)} tested)")
            print("   This suggests: TUSD → other coins has no viable path at all")
        results["recommendation"] = "NO ESCAPE - funds are irretrievably stuck"
        results["paths_found"] = []

    print()
    print("=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    print()
    print(f"  Total paths tested: {results['total_paths_tested']}")
    print(f"  Profitable paths:   {len(profitable_paths)}")
    print(f"  Break-even paths:   {len(breakeven_paths)}")
    print(f"  Acceptable loss:    {len(acceptable_loss_paths)}")
    print(f"  Catastrophic loss:  {len(catastrophic_paths)}")
    print()
    print(f"  Recommendation: {results['recommendation']}")
    print()

    # Save results
    results["paths_by_category"] = {
        "profitable": profitable_paths,
        "breakeven": breakeven_paths,
        "acceptable_loss": acceptable_loss_paths,
        "catastrophic": catastrophic_paths,
    }

    return results

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("=" * 80)
    print("ENHANCED ESCAPE ANALYSIS: Looking for lower-fee intermediate nodes")
    print("=" * 80)
    print()
    print("Question: Can we escape via intermediate exchange with lower fees?")
    print("Example: mexc:TUSD → gate_io:USDT → kraken:USDT")
    print()

    start_time = time.time()
    results = find_all_escape_routes(STUCK_NODE, STUCK_BALANCE)
    elapsed = time.time() - start_time

    # Save to file
    timestamp = datetime.now(timezone.utc).isoformat()
    results["timestamp"] = timestamp
    results["elapsed_seconds"] = elapsed

    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    
    output_file = results_dir / f"escape_detailed_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"✓ Detailed analysis saved to: {output_file}")
    print(f"  Elapsed time: {elapsed:.1f}s")
    print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
