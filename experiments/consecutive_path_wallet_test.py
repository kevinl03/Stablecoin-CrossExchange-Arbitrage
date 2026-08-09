#!/usr/bin/env python3
# ======================================================================
# consecutive_path_wallet_test.py — Real wallet fragmentation simulation
# ======================================================================
#
# PURPOSE: Follow execution paths over time to see actual accumulated profit
# with real wallet state changes. Mimics real-time trading behavior where:
#   1. Start with $10,000 in one exchange
#   2. Execute a profitable path (ending in a different coin/exchange)
#   3. Continue trading from the EXIT NODE until profit is found
#   4. Track wallet fragmentation across exchanges/coins
#   5. Accumulate net profit over multiple consecutive trades
#
# Key differences from snapshot tests:
#   - Maintains persistent wallet state (balances at each node)
#   - Executes paths sequentially, not independently
#   - Tracks how much value is "stuck" waiting for profitable paths
#   - Identifies dead-ends where profit takes time to materialize
#
# Output: JSON log of each execution + final wallet summary
# ======================================================================

from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Project imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.astar_vol import astar_best_path_with_liquidity

# ── Configuration ──────────────────────────────────────────────────────

INITIAL_CASH = 10_000.0  # Start with $10k in one exchange
INITIAL_NODE = ("binance", "USDT")  # Start node
MAX_DEPTH = 5
MAX_TIME_SEC = 60.0
MIN_PROFIT_TO_EXECUTE = 1.00  # Only execute if profit > $1.00
CONSECUTIVE_PATHS = 10  # How many consecutive paths to execute

# ── Wallet State ───────────────────────────────────────────────────────

class WalletState:
    """Track balances across all nodes (exchange:coin pairs)."""

    def __init__(self, initial_node: NodeId, initial_cash: float):
        self.balances: Dict[NodeId, float] = {}
        self.balances[initial_node] = initial_cash
        self.total_profit = 0.0
        self.execution_log: List[Dict[str, Any]] = []

    def get_balance(self, node: NodeId) -> float:
        """Get balance at a node (0 if not held)."""
        return self.balances.get(node, 0.0)

    def set_balance(self, node: NodeId, amount: float) -> None:
        """Set balance at a node."""
        self.balances[node] = max(0.0, amount)

    def total_value(self) -> float:
        """Total USD value across all nodes."""
        return sum(self.balances.values())

    def summary(self) -> Dict[str, Any]:
        """Get wallet summary."""
        non_zero = {str(k): v for k, v in self.balances.items() if v > 0.01}
        return {
            "total_value": self.total_value(),
            "total_profit": self.total_profit,
            "num_nodes_held": len(non_zero),
            "balances": non_zero,
            "num_trades": len(self.execution_log),
        }

    def log_execution(self, execution_data: Dict[str, Any]) -> None:
        """Log a path execution."""
        self.execution_log.append(execution_data)

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    """Run consecutive path execution simulation."""

    print("=" * 70)
    print("CONSECUTIVE PATH WALLET EXECUTION TEST")
    print("=" * 70)
    print(f"Initial capital: ${INITIAL_CASH:,.2f}")
    print(f"Starting node: {INITIAL_NODE}")
    print(f"Max consecutive paths: {CONSECUTIVE_PATHS}")
    print(f"Min profit to execute: ${MIN_PROFIT_TO_EXECUTE:,.2f}")
    print()

    # Build graph once
    print("[1] Building graph...")
    try:
        nodes, adjacency = build_graph()
        print(f"    ✓ Graph has {len(nodes)} nodes")
    except Exception as e:
        print(f"    ✗ Failed to build graph: {e}")
        import traceback
        traceback.print_exc()
        return 1

    # Initialize wallet
    wallet = WalletState(INITIAL_NODE, INITIAL_CASH)
    execution_count = 0

    print(f"\n[2] Starting consecutive path execution...")
    print(f"    Time: {datetime.now(timezone.utc).isoformat()}\n")

    # Execute consecutive paths
    while execution_count < CONSECUTIVE_PATHS:
        # Find node with largest balance to trade from
        if not wallet.balances:
            print("\n❌ Wallet is empty!")
            break

        max_node = max(wallet.balances.items(), key=lambda x: x[1])[0]
        max_balance = wallet.balances[max_node]

        if max_balance < MIN_PROFIT_TO_EXECUTE:
            print(
                f"\n[EXECUTION {execution_count + 1}] "
                f"Max balance ${max_balance:.2f} at {max_node} < min threshold"
            )
            print("    ✗ Cannot execute (insufficient balance)")
            break

        # Find profitable path using h1_liquidity heuristic
        print(
            f"\n[EXECUTION {execution_count + 1}] "
            f"Searching from {max_node} (balance=${max_balance:.2f})..."
        )

        try:
            result = astar_best_path_with_liquidity(
                start_node=max_node,
                liquid_cash_usd=max_balance,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                min_profit_usd=MIN_PROFIT_TO_EXECUTE,
                heuristic="h1_liquidity",
                early_exit_after_profit=True,
                early_exit_iterations=100,
            )

            if result is None or not result.path:
                print(f"    ⚠️  No profitable path found")
                break

            # Extract end node from path
            end_node = result.path[-1] if result.path else max_node
            net_profit = result.profit_usd
            final_cash = result.final_cash_usd

            # Update wallet
            wallet.set_balance(max_node, 0.0)  # Empty starting node
            wallet.set_balance(end_node, final_cash)
            wallet.total_profit += net_profit

            # Log execution
            path_str = " → ".join([f"{n[0]}:{n[1]}" for n in result.path[:5]])
            if len(result.path) > 5:
                path_str += f" ... ({len(result.path)} nodes)"

            execution_log = {
                "execution_num": execution_count + 1,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_node": f"{max_node[0]}:{max_node[1]}",
                "to_node": f"{end_node[0]}:{end_node[1]}",
                "path_length": len(result.path),
                "starting_cash": max_balance,
                "final_cash": final_cash,
                "net_profit": net_profit,
                "path": path_str,
                "nodes_expanded": result.nodes_expanded,
            }
            wallet.log_execution(execution_log)

            print(f"    ✅ Success! Executed {len(result.path)}-step path")
            print(f"       {path_str}")
            print(f"       Profit: ${net_profit:+.2f} → Final: ${final_cash:.2f}")
            print(f"       Wallet total: ${wallet.total_value():.2f} (cumulative profit: ${wallet.total_profit:+.2f})")

            execution_count += 1

        except Exception as e:
            print(f"    ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            break

    # Summary
    print("\n" + "=" * 70)
    print("EXECUTION SUMMARY")
    print("=" * 70)

    summary = wallet.summary()
    print(f"Total executions: {summary['num_trades']}")
    print(f"Total profit: ${summary['total_profit']:+.2f}")
    print(f"Final wallet value: ${summary['total_value']:.2f}")
    print(f"Nodes with balance: {summary['num_nodes_held']}")
    print()

    if summary["num_nodes_held"] > 1:
        print("⚠️  WALLET FRAGMENTATION:")
        for node_str, balance in summary["balances"].items():
            print(f"   {node_str}: ${balance:.2f}")
    print()

    # Write results file
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    output_file = Path(__file__).parent.parent / "results" / f"consecutive_wallet_{timestamp}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    results = {
        "test": "consecutive_path_wallet_execution",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "config": {
            "initial_cash": INITIAL_CASH,
            "initial_node": str(INITIAL_NODE),
            "max_paths": CONSECUTIVE_PATHS,
            "min_profit_to_execute": MIN_PROFIT_TO_EXECUTE,
        },
        "summary": summary,
        "execution_log": wallet.execution_log,
    }

    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"✓ Results saved to: {output_file}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
