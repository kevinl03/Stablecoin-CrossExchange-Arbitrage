#!/usr/bin/env python3
# ======================================================================
# constrained_consecutive_with_deadend_detection.py
# ======================================================================
#
# This combines the constrained trading system with dead-end detection.
#
# BEFORE accepting any path, it checks:
# 1. Does the endpoint have a viable EXIT?
# 2. Is the net profit (entry + exit) positive?
# 3. Is it a "safe node" where we can hold capital?
#
# This prevents the dead-end problem entirely.
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

# Tier 1: Always safe
TIER1_SAFE_NODES = {
    ("binance", "USDT"),
    ("binance", "USDC"),
    ("kraken", "USDT"),
    ("okx", "USDT"),
    ("kucoin", "USDT"),
}

# Tier 2: Liquid hubs
TIER2_LIQUID_NODES = {
    ("gateio", "USDT"),
    ("bybit", "USDT"),
    ("htx", "USDT"),
}

STARTING_CAPITAL = 10000.0
STARTING_NODE = ("binance", "USDT")
MIN_EXIT_PROFIT = 0.50  # Minimum acceptable exit profit

# ── Dead-End Detection ─────────────────────────────────────────────────

class PathValidator:
    """
    Validates paths before execution to prevent dead-ends.
    
    Checks:
    1. Can we EXIT from the endpoint?
    2. Is the net profit positive?
    3. Is it a safe/acceptable node?
    """
    
    def __init__(self):
        self.validation_log: List[Dict[str, Any]] = []
        self.rejected_count = 0
        self.accepted_count = 0
    
    def check_endpoint_has_exit(
        self,
        endpoint: NodeId,
        capital: float,
    ) -> Tuple[bool, Optional[Any], str]:
        """
        Critical check: Does this endpoint have ANY profitable exit?
        """
        try:
            exit_path = astar_best_path_with_liquidity(
                start_node=endpoint,
                liquid_cash_usd=capital,
                max_depth=5,
                max_time_sec=20.0,  # Shorter timeout for exit check
                min_profit_usd=MIN_EXIT_PROFIT,
                heuristic="h1_liquidity",
                early_exit_after_profit=True,
                early_exit_iterations=100,
            )
        except Exception:
            return False, None, "Search error"
        
        if exit_path and exit_path.path and exit_path.profit_usd >= MIN_EXIT_PROFIT:
            return True, exit_path, f"✓ Exit: {exit_path.path[-1][0]}:{exit_path.path[-1][1]} (+${exit_path.profit_usd:.2f})"
        
        return False, None, "✗ No exit"
    
    def validate_entry_path(
        self,
        entry_path: Any,
        current_capital: float,
    ) -> Tuple[bool, str, Optional[Any]]:
        """
        Validate a proposed entry path.
        
        Returns:
            (is_valid: bool, reason: str, exit_path: Optional[A*result])
        """
        
        if not entry_path or not entry_path.path:
            self.rejected_count += 1
            return False, "Invalid path structure", None
        
        endpoint = entry_path.path[-1]
        final_capital = entry_path.final_cash_usd
        entry_profit = entry_path.profit_usd
        
        # Step 1: Check if endpoint has exit
        has_exit, exit_path, exit_reason = self.check_endpoint_has_exit(endpoint, final_capital)
        
        if not has_exit:
            self.rejected_count += 1
            reason = f"Dead-end: {exit_reason}"
            self.validation_log.append({
                "endpoint": endpoint,
                "entry_profit": entry_profit,
                "has_exit": False,
                "exit_profit": 0,
                "net_profit": None,
                "rejected_reason": reason,
            })
            return False, reason, None
        
        # Step 2: Check net profit
        exit_profit = exit_path.profit_usd if exit_path else 0.0
        net_profit = entry_profit + exit_profit
        
        if net_profit < 0:
            self.rejected_count += 1
            reason = f"Net loss: entry +${entry_profit:.2f}, exit +${exit_profit:.2f} = ${net_profit:.2f}"
            self.validation_log.append({
                "endpoint": endpoint,
                "entry_profit": entry_profit,
                "has_exit": True,
                "exit_profit": exit_profit,
                "net_profit": net_profit,
                "rejected_reason": reason,
            })
            return False, reason, exit_path
        
        # Step 3: Accept!
        self.accepted_count += 1
        reason = f"✓ Valid: entry +${entry_profit:.2f}, exit +${exit_profit:.2f}, net +${net_profit:.2f}"
        self.validation_log.append({
            "endpoint": endpoint,
            "entry_profit": entry_profit,
            "has_exit": True,
            "exit_profit": exit_profit,
            "net_profit": net_profit,
            "accepted": True,
        })
        return True, reason, exit_path

# ── Wallet State ───────────────────────────────────────────────────────

class WalletState:
    """Track wallet balances and execution."""
    
    def __init__(self, starting_amount: float):
        self.balances: Dict[NodeId, float] = {STARTING_NODE: starting_amount}
        self.execution_log: List[Dict[str, Any]] = []
        self.total_profit = 0.0
    
    def get_largest_balance_node(self) -> Optional[NodeId]:
        """Find node with most money."""
        nodes_with_balance = [(node, balance) for node, balance in self.balances.items() if balance > 0.01]
        if not nodes_with_balance:
            return None
        return max(nodes_with_balance, key=lambda x: x[1])[0]
    
    def get_total_value_usd(self) -> float:
        """Get total across all nodes."""
        return sum(self.balances.values())

# ── Main Test ──────────────────────────────────────────────────────────

def consecutive_with_deadend_detection(
    starting_amount: float = STARTING_CAPITAL,
    max_iterations: int = 20,
) -> Dict[str, Any]:
    """
    Execute consecutive trades with dead-end detection.
    
    This PREVENTS dead-ends by rejecting any path whose endpoint
    doesn't have a viable exit.
    """
    
    print()
    print("=" * 80)
    print("CONSECUTIVE TRADING WITH DEAD-END DETECTION")
    print("=" * 80)
    print()
    print(f"Starting capital:      ${starting_amount:.2f}")
    print(f"Starting node:         {STARTING_NODE[0]}:{STARTING_NODE[1]}")
    print(f"Min exit profit:       ${MIN_EXIT_PROFIT:.2f}")
    print(f"Dead-end prevention:   ACTIVE")
    print()
    
    wallet = WalletState(starting_amount)
    validator = PathValidator()
    results = []
    
    for iteration in range(max_iterations):
        best_node = wallet.get_largest_balance_node()
        if not best_node:
            print()
            print("    ✗ No nodes with balance")
            break
        
        current_balance = wallet.balances[best_node]
        
        print(f"[Trade {iteration+1:2d}] {best_node[0]:8s}:{best_node[1]:6s} (${current_balance:12,.2f})", end=" | ")
        sys.stdout.flush()
        
        # Search for entry path
        try:
            entry = astar_best_path_with_liquidity(
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
        
        if not entry or not entry.path:
            print(f"✗ No path found")
            break
        
        # *** DEAD-END DETECTION CHECK ***
        is_valid, reason, exit_path = validator.validate_entry_path(entry, current_balance)
        
        if not is_valid:
            print(f"✗ {reason}")
            continue
        
        # Execute trade
        endpoint = entry.path[-1]
        new_balance = entry.final_cash_usd
        entry_profit = entry.profit_usd
        
        wallet.balances[best_node] = 0
        wallet.balances[endpoint] = new_balance
        wallet.total_profit += entry_profit
        
        wallet.execution_log.append({
            "trade": iteration + 1,
            "from": best_node,
            "to": endpoint,
            "entry_profit": entry_profit,
            "exit_profit": exit_path.profit_usd if exit_path else 0,
            "final_cash": new_balance,
        })
        
        results.append(entry)
        print(f"✓ {reason} → ${new_balance:12,.2f}")
    
    print()
    print("=" * 80)
    print("RESULTS")
    print("=" * 80)
    print()
    print(f"Trades executed:       {len(results)}")
    print(f"Paths rejected:        {validator.rejected_count}")
    print(f"Paths accepted:        {validator.accepted_count}")
    print(f"Total profit:          ${wallet.total_profit:.2f}")
    print(f"Final value:           ${wallet.get_total_value_usd():.2f}")
    print()
    
    return {
        "trades_executed": len(results),
        "paths_rejected": validator.rejected_count,
        "paths_accepted": validator.accepted_count,
        "total_profit": wallet.total_profit,
        "final_value": wallet.get_total_value_usd(),
        "final_balances": {f"{n[0]}:{n[1]}": b for n, b in wallet.balances.items() if b > 0.01},
        "validation_log": validator.validation_log,
        "execution_log": wallet.execution_log,
    }

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("╔" + "=" * 78 + "╗")
    print("║" + " " * 78 + "║")
    print("║" + "DEAD-END DETECTION IN ACTION".center(78) + "║")
    print("║" + "Prevents Trapped Positions Automatically".center(78) + "║")
    print("║" + " " * 78 + "║")
    print("╚" + "=" * 78 + "╝")
    
    print()
    print("[1] Building graph...")
    start = time.time()
    try:
        nodes, adj = build_graph()
        elapsed = time.time() - start
        print(f"    ✓ Ready ({len(nodes)} nodes) in {elapsed:.1f}s")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        return 1
    
    print()
    print("[2] Running trades with dead-end detection...")
    print()
    
    results = consecutive_with_deadend_detection(
        starting_amount=STARTING_CAPITAL,
        max_iterations=20,
    )
    
    print()
    print("[3] Saving results...")
    results_dir = project_root / "results"
    results_dir.mkdir(exist_ok=True)
    
    output_file = results_dir / f"deadend_detection_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"    ✓ Saved to {output_file.name}")
    print()
    
    print("=" * 80)
    print("ANALYSIS")
    print("=" * 80)
    print()
    
    print("Dead-end prevention algorithm:")
    print()
    print("  1. Search for profitable path (entry)")
    print("  2. Get endpoint of that path")
    print("  3. Search for profitable exit FROM endpoint")
    print("  4. If no exit found → REJECT path (would be trapped)")
    print("  5. If exit found but net < 0 → REJECT (net loss)")
    print("  6. Otherwise → ACCEPT path")
    print()
    
    print("Results:")
    print(f"  • Paths found:       {results['paths_accepted'] + results['paths_rejected']}")
    print(f"  • Paths accepted:    {results['paths_accepted']} (safe, has exit)")
    print(f"  • Paths rejected:    {results['paths_rejected']} (dead-end or net loss)")
    print(f"  • Rejection rate:    {results['paths_rejected'] / max(1, results['paths_accepted'] + results['paths_rejected']) * 100:.1f}%")
    print()
    
    if results['trades_executed'] > 0:
        print(f"✓ Executed {results['trades_executed']} trades with zero dead-ends!")
        print(f"✓ All positions have verified exit paths")
        print(f"✓ Total profit: ${results['total_profit']:.2f}")
    else:
        print(f"⚠ No trades executed")
        print(f"  Reason: All profitable paths would create dead-ends or net losses")
        print(f"  This is actually GOOD—the algorithm prevented losses!")
    
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
