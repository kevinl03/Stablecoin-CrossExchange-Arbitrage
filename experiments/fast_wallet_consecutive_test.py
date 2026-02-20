#!/usr/bin/env python3
# ======================================================================
# fast_wallet_consecutive_test.py — Wallet test with timeout handling
# ======================================================================
#
# Same as simple_wallet_consecutive_test.py but with:
# - API timeout of 120 seconds max
# - Better error handling for slow/down exchanges
# - Progress indicators
#
# ======================================================================

from __future__ import annotations

import json
import sys
import time
import signal
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId
from scripts.astar_vol import astar_best_path_with_liquidity

# ── Configuration ──────────────────────────────────────────────────────

INITIAL_CASH = 10_000.0
INITIAL_NODE = ("binance", "USDT")
MAX_DEPTH = 5
MAX_TIME_SEC = 60.0
MIN_PROFIT_TO_EXECUTE = 0.50
MAX_CONSECUTIVE_PATHS = 15
GRAPH_BUILD_TIMEOUT = 180  # 3 minutes max

# ── Wallet State ───────────────────────────────────────────────────────

class WalletState:
    def __init__(self, initial_node: NodeId, initial_cash: float):
        self.balances: Dict[NodeId, float] = {initial_node: initial_cash}
        self.total_profit = 0.0
        self.execution_log: List[Dict[str, Any]] = []

    def get_largest_balance(self) -> tuple[NodeId, float]:
        """Return (node, balance) with largest balance."""
        if not self.balances:
            return None, 0.0
        return max(self.balances.items(), key=lambda x: x[1])

    def total_value(self) -> float:
        return sum(self.balances.values())

    def execute_trade(
        self, from_node: NodeId, to_node: NodeId, amount: float, profit: float
    ) -> None:
        """Execute a trade: move funds from from_node to to_node."""
        self.balances[from_node] = max(0.0, self.balances.get(from_node, 0.0) - amount)
        self.balances[to_node] = self.balances.get(to_node, 0.0) + amount + profit
        self.total_profit += profit

        self.execution_log.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_node": f"{from_node[0]}:{from_node[1]}",
            "to_node": f"{to_node[0]}:{to_node[1]}",
            "starting_cash": amount,
            "profit": profit,
            "final_cash": amount + profit,
        })

# ── Timeout Handler ────────────────────────────────────────────────────

class TimeoutException(Exception):
    pass

def timeout_handler(signum, frame):
    raise TimeoutException("Graph building timed out")

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print("=" * 70)
    print("FAST CONSECUTIVE PATH WALLET TEST")
    print("=" * 70)
    print(f"Initial: ${INITIAL_CASH:,.2f} in {INITIAL_NODE}")
    print(f"Max consecutive executions: {MAX_CONSECUTIVE_PATHS}")
    print()

    # Build graph with timeout
    print("[1] Fetching LIVE price data from exchanges (timeout: 3 min)...")
    print("    (This fetches from: binance, kraken, kucoin, okx, mexc, gateio, bybit, etc.)")
    print()

    # Set alarm signal for timeout
    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(GRAPH_BUILD_TIMEOUT)

    try:
        start_time = time.time()
        nodes, adjacency = build_graph()
        signal.alarm(0)  # Cancel alarm
        elapsed = time.time() - start_time
        print(f"    ✓ Graph ready in {elapsed:.1f}s: {len(nodes)} nodes\n")
    except TimeoutException:
        print(f"    ✗ Timed out after {GRAPH_BUILD_TIMEOUT}s")
        print("    (Exchanges may be slow or unreachable)")
        return 1
    except KeyboardInterrupt:
        signal.alarm(0)
        print("\n    ✗ Interrupted by user")
        return 1
    except Exception as e:
        signal.alarm(0)
        print(f"    ✗ Failed: {e}")
        return 1

    # Initialize wallet
    wallet = WalletState(INITIAL_NODE, INITIAL_CASH)
    execution_num = 0

    print("[2] Executing consecutive paths...\n")

    # Execute consecutive paths
    while execution_num < MAX_CONSECUTIVE_PATHS:
        execution_num += 1

        # Get node with largest balance
        current_node, current_balance = wallet.get_largest_balance()

        if current_balance < MIN_PROFIT_TO_EXECUTE:
            print(f"[{execution_num}] Balance ${current_balance:.2f} < threshold. Stopping.")
            break

        print(
            f"[{execution_num}] Searching from {current_node[0]}:{current_node[1]} "
            f"(${current_balance:.2f})...",
            end=" ",
            flush=True,
        )

        # Find profitable path
        try:
            result = astar_best_path_with_liquidity(
                start_node=current_node,
                liquid_cash_usd=current_balance,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                min_profit_usd=MIN_PROFIT_TO_EXECUTE,
                heuristic="h1_liquidity",
                early_exit_after_profit=True,
                early_exit_iterations=100,
            )

            if not result or not result.path:
                print("⚠️  No profitable path. Stopping.")
                break

            # Get end node
            end_node = result.path[-1]
            profit = result.profit_usd
            final_cash = result.final_cash_usd

            # Execute the trade
            wallet.execute_trade(current_node, end_node, current_balance, profit)

            # Display result
            path_str = " → ".join([f"{n[0]}:{n[1]}" for n in result.path[:3]])
            if len(result.path) > 3:
                path_str += f"..."

            print(f"✅")
            print(f"   Path: {path_str}")
            print(f"   Profit: ${profit:+.2f} → Final: ${final_cash:.2f}")
            print(f"   Wallet: ${wallet.total_value():.2f} | Total profit: ${wallet.total_profit:+.2f}\n")

        except KeyboardInterrupt:
            print("\n\n   Interrupted by user.")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            break

    # Summary
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Executions: {len(wallet.execution_log)}")
    print(f"Total profit: ${wallet.total_profit:+.2f}")
    print(f"Final value: ${wallet.total_value():.2f}")
    print(f"ROI: {(wallet.total_profit / INITIAL_CASH * 100):.2f}%")
    print()

    # Show final wallet state
    non_zero = {f"{k[0]}:{k[1]}": v for k, v in wallet.balances.items() if v > 0.01}
    if len(non_zero) > 1:
        print("Final wallet distribution:")
        for node, balance in sorted(non_zero.items(), key=lambda x: x[1], reverse=True):
            print(f"  {node}: ${balance:.2f}")
    else:
        node_str = list(non_zero.keys())[0] if non_zero else "EMPTY"
        print(f"Final wallet: {node_str}")
    print()

    # Save results
    output_file = Path(__file__).parent.parent / "results" / f"wallet_consecutive_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, "w") as f:
        json.dump({
            "test": "consecutive_wallet_execution",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "initial_cash": INITIAL_CASH,
                "initial_node": str(INITIAL_NODE),
            },
            "results": {
                "executions": len(wallet.execution_log),
                "total_profit": wallet.total_profit,
                "final_value": wallet.total_value(),
                "roi_pct": wallet.total_profit / INITIAL_CASH * 100,
            },
            "execution_log": wallet.execution_log,
        }, f, indent=2)

    print(f"✓ Results saved to: {output_file.name}\n")
    return 0

if __name__ == "__main__":
    sys.exit(main())
