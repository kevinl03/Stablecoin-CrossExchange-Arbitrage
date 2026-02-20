#!/usr/bin/env python3
# ======================================================================
# escape_deadend_analysis.py — How to escape unprofitable wallet positions
# ======================================================================
#
# Problem: Wallet is stuck in mexc:TUSD with no profitable path back
# 
# Solution: Analyze alternative escape strategies:
# 1. Accept small loss to reach liquid position
# 2. Wait for market conditions to change
# 3. Diversify across multiple coins/exchanges
# 4. Use risk-adjusted routing
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
TARGET_NODES = [
    ("binance", "USDT"),
    ("binance", "USDC"),
    ("kraken", "USDT"),
    ("kucoin", "USDT"),
    ("okx", "USDT"),
]

# ── Escape Strategy Analysis ───────────────────────────────────────────

def find_escape_routes(
    stuck_node: NodeId,
    stuck_balance: float,
    target_nodes: List[NodeId],
) -> Dict[str, Any]:
    """
    Find all possible ways to escape from stuck position, including:
    1. Profitable paths (no loss)
    2. Break-even paths (minimal loss)
    3. Acceptable loss paths (< 5% loss)
    4. Emergency exit (any exit, accept loss)
    """
    
    results = {
        "stuck_node": f"{stuck_node[0]}:{stuck_node[1]}",
        "stuck_balance": stuck_balance,
        "escape_strategies": [],
        "best_strategy": None,
        "worst_case": None,
    }

    print(f"\n" + "=" * 70)
    print(f"ESCAPE ANALYSIS: {stuck_node[0]}:{stuck_node[1]} (${stuck_balance:.2f})")
    print("=" * 70)
    print()
    print("Testing escape routes to liquid positions...\n")

    profitable_paths = []
    breakeven_paths = []
    acceptable_loss_paths = []
    emergency_paths = []

    # Test paths to each target node with different search depths
    for target_node in target_nodes:
        print(f"Target: {target_node[0]}:{target_node[1]}", end="")

        for max_depth in [2, 3, 4, 5, 6]:
            try:
                result = astar_best_path_with_liquidity(
                    start_node=stuck_node,
                    liquid_cash_usd=stuck_balance,
                    max_depth=max_depth,
                    max_time_sec=30.0,
                    min_profit_usd=-stuck_balance,  # Allow any path (even big losses)
                    heuristic="h1_liquidity",
                    early_exit_after_profit=False,  # Don't stop early, explore all
                    early_exit_iterations=500,
                )

                if result and result.path:
                    profit = result.profit_usd
                    final_cash = result.final_cash_usd
                    loss_pct = (profit / stuck_balance * 100) if profit < 0 else 0

                    path_info = {
                        "target": f"{target_node[0]}:{target_node[1]}",
                        "path_length": len(result.path),
                        "profit": profit,
                        "final_cash": final_cash,
                        "loss_pct": loss_pct if profit < 0 else 0,
                        "nodes_expanded": result.nodes_expanded,
                    }

                    # Categorize
                    if profit > 0:
                        profitable_paths.append(path_info)
                        print(".", end="", flush=True)
                    elif profit >= -10:
                        breakeven_paths.append(path_info)
                        print("•", end="", flush=True)
                    elif loss_pct <= 5:
                        acceptable_loss_paths.append(path_info)
                        print("◦", end="", flush=True)
                    else:
                        emergency_paths.append(path_info)
                        print("×", end="", flush=True)
                    break  # Found a path, stop testing deeper

            except Exception as e:
                print("?", end="", flush=True)
                continue

        print()

    # Sort by profit
    profitable_paths.sort(key=lambda x: x["profit"], reverse=True)
    breakeven_paths.sort(key=lambda x: x["profit"], reverse=True)
    acceptable_loss_paths.sort(key=lambda x: x["loss_pct"])
    emergency_paths.sort(key=lambda x: x["loss_pct"])

    # Compile results
    results["escape_strategies"] = {
        "profitable": profitable_paths,
        "breakeven": breakeven_paths,
        "acceptable_loss": acceptable_loss_paths,
        "emergency": emergency_paths,
    }

    # Determine best strategy
    if profitable_paths:
        results["best_strategy"] = {
            "type": "PROFITABLE",
            "path": profitable_paths[0],
            "recommendation": f"Execute immediately! Profit ${profitable_paths[0]['profit']:.2f}",
        }
    elif breakeven_paths:
        results["best_strategy"] = {
            "type": "BREAK-EVEN",
            "path": breakeven_paths[0],
            "recommendation": f"Execute to reach liquid position. Loss: ${abs(breakeven_paths[0]['profit']):.2f}",
        }
    elif acceptable_loss_paths:
        best = acceptable_loss_paths[0]
        results["best_strategy"] = {
            "type": "ACCEPTABLE_LOSS",
            "path": best,
            "recommendation": f"Accept {best['loss_pct']:.2f}% loss (${abs(best['profit']):.2f}) to escape",
        }
    elif emergency_paths:
        worst = emergency_paths[0]
        results["worst_case"] = {
            "type": "EMERGENCY",
            "path": worst,
            "recommendation": f"Last resort: {worst['loss_pct']:.2f}% loss to exit trapped position",
        }
    else:
        results["best_strategy"] = {
            "type": "NO_ESCAPE",
            "path": None,
            "recommendation": "NO VIABLE ESCAPE ROUTE FOUND. Funds are truly stuck.",
        }

    return results

# ── Escape Prevention ──────────────────────────────────────────────────

def analyze_prevention_strategy() -> Dict[str, Any]:
    """
    What could have been done to avoid the dead-end?
    """
    
    print("\n" + "=" * 70)
    print("DEAD-END PREVENTION STRATEGY")
    print("=" * 70)
    print()

    prevention = {
        "problem": "Executed path ending in mexc:TUSD with no profitable exit",
        "root_cause": "Path endpoint selection did not consider exit viability",
        "prevention_strategies": [
            {
                "name": "Constrained Search",
                "description": "Only select paths that can reach a liquid hub (binance:USDT, kraken:USDT)",
                "implementation": "Add constraint: final node must have profitable path back within 2-3 hops",
                "cost": "May miss some profitable opportunities",
                "benefit": "Guarantees capital remains liquid",
            },
            {
                "name": "Two-Phase Execution",
                "description": "Verify exit path exists BEFORE executing entry trade",
                "implementation": "1) Search for exit path from destination, 2) Only execute if exit found",
                "cost": "2x search time, may be slower",
                "benefit": "Never gets trapped",
            },
            {
                "name": "Portfolio Diversification",
                "description": "Split capital across multiple paths, not all-in on one route",
                "implementation": "Instead of $10k → mexc:TUSD, do $5k → mexc:TUSD + $5k → other routes",
                "cost": "More complex, more fees",
                "benefit": "If one path dead-ends, others may be profitable",
            },
            {
                "name": "Mandatory Liquidity Score",
                "description": "Rate each node by 'how easy to exit profitably'",
                "implementation": "Rank nodes by: # profitable exit paths, avg exit profit, exit time",
                "cost": "Requires network analysis",
                "benefit": "Avoid dead-ends entirely",
            },
            {
                "name": "Dynamic Rebalancing",
                "description": "Continuously move funds away from low-liquidity nodes",
                "implementation": "Every N minutes, check if current node has exit. If not, market-sell at loss",
                "cost": "Loses the stuck profit, but avoids complete trap",
                "benefit": "Better for live trading",
            },
        ],
    }

    for i, strategy in enumerate(prevention["prevention_strategies"], 1):
        print(f"{i}. {strategy['name'].upper()}")
        print(f"   Idea: {strategy['description']}")
        print(f"   How: {strategy['implementation']}")
        print(f"   ✓ Benefit: {strategy['benefit']}")
        print(f"   ✗ Cost: {strategy['cost']}")
        print()

    return prevention

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 70)
    print("HOW TO ESCAPE DEAD-END WALLET POSITIONS")
    print("=" * 70)
    print()
    print("Scenario: Wallet has $10,009.76 in mexc:TUSD")
    print("Problem: No profitable path found back to liquid positions")
    print("Question: What are our options?")
    print()

    # Build graph
    print("[1] Building graph with live prices...")
    try:
        nodes, adjacency = build_graph()
        print(f"    ✓ Graph ready ({len(nodes)} nodes)\n")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return 1

    # Analyze escape routes
    print("[2] Analyzing escape routes...")
    escape_results = find_escape_routes(STUCK_NODE, STUCK_BALANCE, TARGET_NODES)

    # Display results
    print("\n" + "=" * 70)
    print("ESCAPE ROUTE ANALYSIS RESULTS")
    print("=" * 70)
    print()

    strategies = escape_results["escape_strategies"]
    
    if strategies["profitable"]:
        print(f"✅ PROFITABLE ESCAPES: {len(strategies['profitable'])}")
        best = strategies["profitable"][0]
        print(f"   Best: {best['target']} → +${best['profit']:.2f} ({best['path_length']} hops)")
        print()

    if strategies["breakeven"]:
        print(f"⚪ BREAK-EVEN ESCAPES: {len(strategies['breakeven'])}")
        best = strategies["breakeven"][0]
        print(f"   Best: {best['target']} → -${abs(best['profit']):.2f} loss ({best['path_length']} hops)")
        print()

    if strategies["acceptable_loss"]:
        print(f"🟡 ACCEPTABLE LOSS: {len(strategies['acceptable_loss'])}")
        best = strategies["acceptable_loss"][0]
        print(f"   Best: {best['target']} → {best['loss_pct']:.2f}% loss, -${abs(best['profit']):.2f} ({best['path_length']} hops)")
        print()

    if strategies["emergency"]:
        print(f"🔴 EMERGENCY ROUTES: {len(strategies['emergency'])}")
        worst = strategies["emergency"][0]
        print(f"   Only option: {worst['target']} → {worst['loss_pct']:.2f}% loss, -${abs(worst['profit']):.2f}")
        print()

    # Best strategy recommendation
    print("=" * 70)
    print("RECOMMENDATION")
    print("=" * 70)
    print()
    best = escape_results["best_strategy"]
    print(f"Strategy: {best['type']}")
    print(f"Action: {best['recommendation']}")
    if best['path']:
        print(f"Target: {best['path']['target']}")
        print(f"Result: Final balance ${best['path']['final_cash']:.2f}")
    print()

    # Prevention analysis
    analyze_prevention_strategy()

    # Save results
    output_file = Path(__file__).parent.parent / "results" / f"escape_analysis_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    output_data = {
        "analysis": "How to escape dead-end wallet position",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "stuck_position": {
            "node": escape_results["stuck_node"],
            "balance": escape_results["stuck_balance"],
        },
        "escape_routes": escape_results["escape_strategies"],
        "recommendation": escape_results["best_strategy"],
    }

    with open(output_file, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Analysis saved to: {output_file.name}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
