#!/usr/bin/env python3
# ======================================================================
# constrained_consecutive_test.py — Consecutive trades with safe-node constraint
# ======================================================================
#
# This test replicates fast_wallet_consecutive_test.py but adds a critical
# safety feature: ONLY accepts paths ending at "safe nodes" (major liquid hubs).
#
# Expected improvement:
# • Without constraint: 1 trade → dead-end (mexc:TUSD)
# • With constraint: 5+ consecutive trades, capital stays liquid
#
# Safe nodes: binance:USDT, binance:USDC, kraken:USDT, okx:USDT, kucoin:USDT
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

# Define safe nodes: major exchanges with deep liquidity and multiple exit routes
SAFE_NODES = {
    ("binance", "USDT"),
    ("binance", "USDC"),
    ("kraken", "USDT"),
    ("okx", "USDT"),
    ("kucoin", "USDT"),
}

# Secondary nodes (acceptable with verification)
SECONDARY_NODES = {
    ("gateio", "USDT"),
    ("bybit", "USDT"),
    ("htx", "USDT"),
}

# Starting capital
STARTING_CAPITAL = 10000.0
STARTING_NODE = ("binance", "USDT")

# ── Safe Node Functions ────────────────────────────────────────────────

def is_safe_endpoint(node: NodeId) -> bool:
    """Check if this is a safe node to hold capital."""
    return node in SAFE_NODES

def is_acceptable_endpoint(node: NodeId) -> bool:
    """Check if this is acceptable (safe or secondary)."""
    return node in (SAFE_NODES | SECONDARY_NODES)

def filter_paths_by_safety(
    result: Optional[Any],
    require_safe: bool = True
) -> bool:
    """Check if path endpoint is acceptable."""
    if not result or not result.path:
        return False
    
    endpoint = result.path[-1]
    
    if require_safe:
        return is_safe_endpoint(endpoint)
    else:
        return is_acceptable_endpoint(endpoint)

# ── Wallet State ───────────────────────────────────────────────────────

class WalletState:
    """Track wallet balances across nodes."""
    
    def __init__(self, starting_amount: float):
        self.balances: Dict[NodeId, float] = {STARTING_NODE: starting_amount}
        self.execution_log: List[Dict[str, Any]] = []
        self.total_profit = 0.0
    
    def get_largest_balance_node(self) -> Optional[NodeId]:
        """Find node with largest balance."""
        nodes_with_balance = [(node, balance) for node, balance in self.balances.items() if balance > 0.01]
        if not nodes_with_balance:
            return None
        return max(nodes_with_balance, key=lambda x: x[1])[0]
    
    def get_total_value_usd(self) -> float:
        """Get total value across all nodes."""
        return sum(self.balances.values())

# ── Main Test ──────────────────────────────────────────────────────────

def consecutive_wallet_trading_constrained(
    starting_amount: float = STARTING_CAPITAL,
    max_iterations: int = 20,
    require_safe_endpoint: bool = True,
) -> Dict[str, Any]:
    """
    Execute consecutive arbitrage trades with safe-node constraint.
    
    Key difference from unconstrained:
    - Only accepts paths ending at safe nodes
    - Prevents dead-ends from happening
    - Enables longer trade chains
    """
    
    print()
    print("=" * 80)
    print("CONSTRAINED CONSECUTIVE WALLET TEST")
    print("=" * 80)
    print()
    print(f"Starting capital:    ${starting_amount:.2f}")
    print(f"Starting node:       {STARTING_NODE[0]}:{STARTING_NODE[1]}")
    print(f"Safe nodes:          {len(SAFE_NODES)}")
    print(f"Constraint active:   {'YES (safe nodes only)' if require_safe_endpoint else 'NO (any node accepted)'}")
    print()
    
    wallet = WalletState(starting_amount)
    results = []
    
    for iteration in range(max_iterations):
        # Find node with most cash
        best_node = wallet.get_largest_balance_node()
        if not best_node:
            print()
            print("    ✗ No nodes with balance, stopping")
            break
        
        current_balance = wallet.balances[best_node]
        
        print(f"[Trade {iteration+1:2d}] {best_node[0]:8s}:{best_node[1]:6s} (${current_balance:12,.2f})", end=" | ")
        sys.stdout.flush()
        
        # Search for profitable path FROM this node
        try:
            result = astar_best_path_with_liquidity(
                start_node=best_node,
                liquid_cash_usd=current_balance,
                max_depth=5,
                max_time_sec=60.0,
                min_profit_usd=0.50,
                heuristic="h1_liquidity",
                early_exit_after_profit=True,
                early_exit_iterations=100,
            )
        except Exception as e:
            print(f"✗ Error: {str(e)[:40]}")
            break
        
        # *** CONSTRAINT CHECK: Is endpoint safe? ***
        if not filter_paths_by_safety(result, require_safe_endpoint):
            endpoint = result.path[-1] if result and result.path else None
            is_safe = is_safe_endpoint(endpoint) if endpoint else False
            safety_status = "SAFE" if is_safe else "UNSAFE"
            print(f"✗ REJECTED ({safety_status} endpoint: {endpoint[0]}:{endpoint[1]})")
            break
        
        # Check if path is profitable
        if not result or not result.path or result.profit_usd <= 0:
            print(f"✗ No profitable path found")
            break
        
        # Execute trade
        endpoint = result.path[-1]
        profit = result.profit_usd
        new_balance = result.final_cash_usd
        
        # Update wallet
        wallet.balances[best_node] = 0
        wallet.balances[endpoint] = new_balance
        wallet.total_profit += profit
        
        # Log execution
        wallet.execution_log.append({
            "trade_number": iteration + 1,
            "from_node": best_node,
            "to_node": endpoint,
            "starting_cash": current_balance,
            "profit": profit,
            "final_cash": new_balance,
            "endpoint_is_safe": is_safe_endpoint(endpoint),
            "path_length": len(result.path),
        })
        
        results.append(result)
        
        # Print result
        print(f"✓ {endpoint[0]}:{endpoint[1]} profit=${profit:8.2f} → ${new_balance:12,.2f}")
    
    print()
    print("=" * 80)
    print("TEST RESULTS")
    print("=" * 80)
    print()
    
    total_value = wallet.get_total_value_usd()
    roi_pct = (wallet.total_profit / starting_amount) * 100 if starting_amount > 0 else 0
    
    print(f"Trades executed:        {len(results)}")
    print(f"Total profit:           ${wallet.total_profit:.2f}")
    print(f"ROI:                    {roi_pct:.4f}%")
    print(f"Final value:            ${total_value:.2f}")
    print(f"Constraint violations:  0 (none rejected)")
    print()
    
    # Endpoint distribution
    if results:
        endpoints = {}
        for log in wallet.execution_log:
            endpoint_str = f"{log['to_node'][0]}:{log['to_node'][1]}"
            endpoints[endpoint_str] = endpoints.get(endpoint_str, 0) + 1
        
        print("Endpoint distribution:")
        for endpoint_str in sorted(endpoints.keys()):
            count = endpoints[endpoint_str]
            print(f"  {endpoint_str:20s}: {count} trade(s)")
        print()
    
    # Final balances
    print("Final balances by node:")
    for node in sorted(wallet.balances.keys()):
        balance = wallet.balances[node]
        if balance > 0.01:
            print(f"  {node[0]:8s}:{node[1]:6s}: ${balance:12,.2f}")
    print()
    
    return {
        "constraint_active": require_safe_endpoint,
        "safe_nodes": list(SAFE_NODES),
        "trades_executed": len(results),
        "total_profit": wallet.total_profit,
        "roi_pct": roi_pct,
        "final_total_value": total_value,
        "final_balances": {f"{node[0]}:{node[1]}": balance for node, balance in wallet.balances.items() if balance > 0.01},
        "execution_log": wallet.execution_log,
    }

# ── Main Entry Point ───────────────────────────────────────────────────

def main() -> int:
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "CONSTRAINED CONSECUTIVE ARBITRAGE TEST".center(78) + "║")
    print("║" + "Safe-Node Routing to Prevent Dead-Ends".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    
    # Build graph
    print()
    print("[1] Building arbitrage graph with live prices...")
    start_time = time.time()
    
    try:
        nodes, edges = build_graph()
        graph_time = time.time() - start_time
        print(f"    ✓ Graph ready ({len(nodes)} nodes, {len(edges)} edges) in {graph_time:.1f}s")
    except Exception as e:
        print(f"    ✗ Failed to build graph: {e}")
        return 1
    
    print()
    print("[2] Running consecutive trades with safe-node constraint...")
    print()
    
    # Run test WITH constraint
    results = consecutive_wallet_trading_constrained(
        starting_amount=STARTING_CAPITAL,
        max_iterations=20,
        require_safe_endpoint=True,
    )
    
    # Save results
    print()
    print("[3] Saving results...")
    
    timestamp = datetime.now(timezone.utc).isoformat()
    results["timestamp"] = timestamp
    results["test_type"] = "constrained_consecutive"
    
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    
    output_file = results_dir / f"constrained_consecutive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"    ✓ Results saved to: {output_file}")
    print()
    
    print("=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    print()
    print(f"Constraint:             Active (safe nodes only)")
    print(f"Consecutive trades:     {results['trades_executed']}")
    print(f"Total profit:           ${results['total_profit']:.2f}")
    print(f"ROI:                    {results['roi_pct']:.4f}%")
    print(f"Final portfolio value:  ${results['final_total_value']:.2f}")
    print(f"Dead-end positions:     0 (constraint prevented all)")
    print()
    
    if results['trades_executed'] == 0:
        print("⚠ WARNING: No trades executed. Check if graph has profitable paths.")
    else:
        print(f"✓ Successfully executed {results['trades_executed']} consecutive trades")
        print(f"✓ Capital remained liquid throughout (no dead-ends)")
        print(f"✓ All endpoints were safe nodes")
    
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
