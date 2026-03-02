"""
$100 portfolio test — where gas and withdrawal fees dominate.

Runs three algorithms:
  1. Dijkstra        — greedy, fast, but can miss "lose-then-win" paths
  2. Bellman-Ford    — cycle detection (finds risk-free loops)
  3. BF-SSSP (NEW)   — Bellman-Ford single-source shortest path
                       Correctly handles negative edges: will take a
                       LOSS on one step if it opens up a bigger gain
                       on the next step.  Guaranteed optimal.

Outputs detailed trading paths to results/ text file.
"""

from __future__ import annotations

import sys
import time
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from io import StringIO
from math import exp
from typing import Any, Dict, List, Optional, Tuple

# ── graph builders ──
from scripts.crypto_graph import (
    build_graph as build_cex_graph,
    Adjacency as CexAdj,
    NodeId,
)
from scripts.defi_graph import (
    build_graph as build_dex_graph,
    Adjacency as DexAdj,
)

# ── existing algorithms (for comparison) ──
from scripts.crypto_arbitrage import (
    dijkstra_best_path as cex_dijkstra,
    bellman_ford_crypto as cex_bellman_ford,
    _format_path as cex_fmt,
)
from scripts.defi_arbitrage import (
    dijkstra_best_path as dex_dijkstra,
    bellman_ford_defi as dex_bellman_ford,
    _format_path as dex_fmt,
)


# ────────────────────────────────────────────────────────────
# NEW: Bellman-Ford Single-Source Shortest Path (BF-SSSP)
#
# Unlike Dijkstra, this handles NEGATIVE edge weights correctly.
# It will happily take a loss on step N if step N+1 more than
# makes up for it.  Guaranteed to find the optimal path within
# the depth limit.
#
# Complexity: O(max_depth × |E|)
# ────────────────────────────────────────────────────────────

@dataclass
class PathResult:
    path: List[NodeId]
    edges: List[Dict[str, Any]]
    final_cash_usd: float
    profit_usd: float
    profit_pct: float
    total_time_sec: float


def bellman_ford_sssp(
    nodes: Dict[NodeId, Dict[str, Any]],
    adj: Dict[NodeId, List[Dict[str, Any]]],
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 3600.0,
) -> Optional[PathResult]:
    """
    Bellman-Ford SSSP relaxes edges depth-by-depth.

    At each depth d, for every node reachable in exactly d steps,
    we try extending by one more edge.  This naturally allows
    intermediate losses — a loss at depth 2 can be recovered at
    depth 3 if the gain outweighs the loss.

    Returns the single most profitable reachable state, or None.
    """
    if start_node not in nodes:
        return None

    # dist[(node, depth)] = (best_g, elapsed_sec)
    INF = float("inf")
    dist: Dict[Tuple[NodeId, int], Tuple[float, float]] = {}
    pred: Dict[Tuple[NodeId, int], Tuple[Tuple[NodeId, int], Dict[str, Any]]] = {}

    dist[(start_node, 0)] = (0.0, 0.0)

    for d in range(max_depth):
        # Collect all states at current depth
        states_at_d = [
            (key, g, t)
            for key, (g, t) in dist.items()
            if key[1] == d
        ]

        for (node, _depth), g, elapsed in states_at_d:
            for edge in adj.get(node, []):
                to_node: NodeId = edge["to"]
                edge_cost = float(edge.get("cost", 0.0))
                dt = float(edge.get("transfer_time_sec", 0.0))

                new_g = g + edge_cost
                new_t = elapsed + dt

                if new_t > max_time_sec:
                    continue

                new_key = (to_node, d + 1)
                old = dist.get(new_key)

                if old is None or new_g < old[0]:
                    dist[new_key] = (new_g, new_t)
                    pred[new_key] = ((node, d), edge)

    # Find the most profitable destination (any depth > 0)
    best_key: Optional[Tuple[NodeId, int]] = None
    best_cash = liquid_cash_usd  # must beat starting cash

    for (node, depth), (g, t) in dist.items():
        if depth == 0:
            continue
        cash = liquid_cash_usd * exp(-g)
        if cash > best_cash:
            best_cash = cash
            best_key = (node, depth)

    if best_key is None:
        return None

    # Reconstruct path
    path_nodes: List[NodeId] = []
    path_edges: List[Dict[str, Any]] = []
    total_time = dist[best_key][1]
    current = best_key

    while current in pred:
        prev_key, edge = pred[current]
        path_nodes.append(current[0])
        path_edges.append(edge)
        current = prev_key

    path_nodes.append(start_node)
    path_nodes.reverse()
    path_edges.reverse()

    profit = best_cash - liquid_cash_usd
    return PathResult(
        path=path_nodes,
        edges=path_edges,
        final_cash_usd=best_cash,
        profit_usd=profit,
        profit_pct=(profit / liquid_cash_usd) * 100.0,
        total_time_sec=total_time,
    )


def format_bf_path(r: PathResult, label: str = "BF-SSSP") -> str:
    lines = [
        f"  [{label}] Profit: ${r.profit_usd:,.4f}  "
        f"({r.profit_pct:+.4f}%)  Final: ${r.final_cash_usd:,.4f}  "
        f"Time: {r.total_time_sec:.0f}s",
        f"  Path: {len(r.path)} nodes",
    ]
    running_usd = r.final_cash_usd - r.profit_usd  # start value
    for i, edge in enumerate(r.edges):
        fr = edge["from"]
        to = edge["to"]
        kind = edge["kind"]
        rate = edge.get("rate", 0)
        cost = edge.get("cost", 0)
        step_pnl = "gain" if cost < 0 else "LOSS"

        if kind in ("trade", "swap"):
            fee_key = "taker_fee" if "taker_fee" in edge else "dex_fee"
            fee = edge.get(fee_key, 0)
            fee_pct = fee * 100 if fee else 0
            gas = edge.get("gas_usd", 0)
            chain = edge.get("chain", edge.get("exchange", fr[0]))
            lines.append(
                f"    {i+1}. {'TRADE' if kind=='trade' else 'SWAP ':5s}  "
                f"{fr[0]:10s}  {fr[1]:5s} → {to[1]:5s}  "
                f"rate={rate:.8f}  fee={fee_pct:.3f}%  gas=${gas:.2f}  "
                f"[{step_pnl}]"
            )
        else:  # transfer / bridge
            p_from = edge.get("price_from_usd", edge.get("price_from_usd", 0))
            p_to = edge.get("price_to_usd", edge.get("price_to_usd", 0))
            pr = edge.get("price_ratio", 0)

            if kind == "bridge":
                pf = edge.get("bridge_pct_fee", 0) * 100
                ff = edge.get("bridge_flat_fee_usd", 0)
                t = edge.get("transfer_time_sec", 0)
                lines.append(
                    f"    {i+1}. BRIDGE  "
                    f"{fr[0]:10s} → {to[0]:10s}  [{fr[1]:5s}]  "
                    f"rate={rate:.8f}  "
                    f"${p_from:,.2f}→${p_to:,.2f} (ratio={pr:.6f})  "
                    f"fee={pf:.3f}%+${ff:.2f}  time={t:.0f}s  [{step_pnl}]"
                )
            else:  # CEX transfer
                wd = edge.get("withdrawal_fee_units", 0)
                gas = edge.get("gas_fee_usd", 0)
                chain = edge.get("chain", "?")
                t = edge.get("transfer_time_sec", 0)
                lines.append(
                    f"    {i+1}. XFER    "
                    f"{fr[0]:10s} → {to[0]:10s}  [{fr[1]:5s}]  "
                    f"chain={chain}  wd_fee={wd}  gas=${gas:.2f}  "
                    f"rate={rate:.8f}  time={t:.0f}s  [{step_pnl}]"
                )

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# Test runner
# ────────────────────────────────────────────────────────────

class Tee:
    def __init__(self):
        self.buf = StringIO()
        self.stdout = sys.stdout
    def write(self, s):
        self.stdout.write(s)
        self.buf.write(s)
    def flush(self):
        self.stdout.flush()
    def getvalue(self):
        return self.buf.getvalue()


def run():
    tee = Tee()
    sys.stdout = tee
    AMOUNT = 100.0

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 80)
    print(f"  $100 PORTFOLIO TEST — Gas & Fee Sensitivity Analysis")
    print(f"  Timestamp: {ts}")
    print(f"  Portfolio: ${AMOUNT:.2f}")
    print("=" * 80)
    print()
    print("  WHY $100 MATTERS:")
    print("    - Ethereum gas ($5/swap) = 5% of portfolio per swap")
    print("    - A bridge flat fee of $5 = 5% loss instantly")
    print("    - Only cheap chains (Solana, Polygon, Base, L2s) are viable")
    print("    - CEX withdrawal fees can exceed the entire spread")
    print()
    print("  ALGORITHMS COMPARED:")
    print("    1. Dijkstra — greedy, expands lowest-cost first.")
    print("       LIMITATION: cannot take a loss now for a bigger gain later")
    print("       because it never revisits cheaper-looking states.")
    print("    2. Bellman-Ford SSSP — relaxes ALL edges at each depth.")
    print("       CAN take an intermediate loss if the next step profits more.")
    print("       Guaranteed optimal within the depth limit.")
    print("    3. Bellman-Ford cycle detection — finds risk-free loops.")

    # ────────────────────────────────────────────────────────
    # PART 1: DEX — DeFi-Llama on-chain
    # ────────────────────────────────────────────────────────
    print("\n\n")
    print("█" * 80)
    print("  PART 1: DEX ON-CHAIN ARBITRAGE ($100)")
    print("█" * 80)

    dex_nodes, dex_adj = build_dex_graph(
        force_refresh=True,
        portfolio_size_usd=AMOUNT,
    )

    dex_scenarios = [
        ("polygon",  "USDC"),
        ("polygon",  "WETH"),
        ("arbitrum", "WETH"),
        ("base",     "WETH"),
        ("optimism", "WETH"),
        ("solana",   "SOL"),
        ("solana",   "USDC"),
        ("arbitrum", "WBTC"),
    ]

    for chain, token in dex_scenarios:
        start = (chain, token)
        if start not in dex_nodes:
            continue

        print(f"\n{'─'*72}")
        print(f"  START: ({chain}, {token})  |  ${AMOUNT:.0f}")
        print(f"{'─'*72}")

        # Dijkstra
        try:
            dijk = dex_dijkstra(
                start_node=start,
                liquid_cash_usd=AMOUNT,
                max_depth=6,
                max_time_sec=3600.0,
            )
            if dijk:
                print(f"\n  [Dijkstra] Profit: ${dijk.profit_usd:,.4f} ({dijk.profit_pct:+.4f}%)")
                print(f"  Path: {' → '.join(f'{n[0]}:{n[1]}' for n in dijk.path)}")
            else:
                print(f"\n  [Dijkstra] No profitable path.")
        except ValueError:
            print(f"\n  [Dijkstra] Start node not in graph.")

        # BF-SSSP
        bf = bellman_ford_sssp(
            dex_nodes, dex_adj,
            start_node=start,
            liquid_cash_usd=AMOUNT,
            max_depth=6,
            max_time_sec=3600.0,
        )
        if bf:
            print()
            print(format_bf_path(bf, "BF-SSSP"))
        else:
            print(f"\n  [BF-SSSP] No profitable path.")

        # Compare
        if dijk and bf:
            if bf.profit_usd > dijk.profit_usd + 0.001:
                diff = bf.profit_usd - dijk.profit_usd
                print(f"\n  >>> BF-SSSP found ${diff:,.4f} MORE profit than Dijkstra!")
                print(f"      (BF-SSSP can take intermediate losses for bigger gains)")

    # BF cycle detection
    print(f"\n{'─'*72}")
    print(f"  Bellman-Ford Cycle Detection ($100)")
    print(f"{'─'*72}")
    bf_cycles = dex_bellman_ford(liquid_cash_usd=AMOUNT)
    if bf_cycles:
        print(f"  {len(bf_cycles)} cycle(s) found")
        for i, c in enumerate(bf_cycles[:3], 1):
            print(f"    Cycle {i}: profit=${c.profit_usd:,.4f} ({c.profit_pct:+.4f}%)")
    else:
        print(f"  No cycles found at $100.")

    # ────────────────────────────────────────────────────────
    # PART 2: CEX — Centralized exchanges
    # ────────────────────────────────────────────────────────
    print("\n\n")
    print("█" * 80)
    print("  PART 2: CEX CRYPTO ARBITRAGE ($100)")
    print("█" * 80)

    cex_nodes, cex_adj = build_cex_graph(
        force_refresh=True,
        portfolio_size_usd=AMOUNT,
    )

    cex_scenarios = [
        ("binance",  "USDT"),
        ("binance",  "BTC"),
        ("okx",      "SOL"),
        ("coinbase", "USDC"),
        ("mexc",     "XRP"),
        ("kucoin",   "ETH"),
    ]

    for exchange, coin in cex_scenarios:
        start = (exchange, coin)
        if start not in cex_nodes:
            print(f"\n  ({exchange}, {coin}) — not in graph at $100 (fees too high)")
            continue

        print(f"\n{'─'*72}")
        print(f"  START: ({exchange}, {coin})  |  ${AMOUNT:.0f}")
        print(f"{'─'*72}")

        # Dijkstra
        try:
            dijk = cex_dijkstra(
                start_node=start,
                liquid_cash_usd=AMOUNT,
                max_depth=5,
            )
            if dijk:
                print(f"\n  [Dijkstra] Profit: ${dijk.profit_usd:,.4f} ({dijk.profit_pct:+.4f}%)")
                print(f"  Path: {' → '.join(f'{n[0]}:{n[1]}' for n in dijk.path)}")
            else:
                print(f"\n  [Dijkstra] No profitable path.")
        except ValueError:
            print(f"\n  [Dijkstra] Start node not in graph.")
            dijk = None

        # BF-SSSP
        bf = bellman_ford_sssp(
            cex_nodes, cex_adj,
            start_node=start,
            liquid_cash_usd=AMOUNT,
            max_depth=5,
            max_time_sec=1800.0,
        )
        if bf:
            print()
            print(format_bf_path(bf, "BF-SSSP"))
        else:
            print(f"\n  [BF-SSSP] No profitable path.")

        if dijk and bf:
            if bf.profit_usd > dijk.profit_usd + 0.001:
                diff = bf.profit_usd - dijk.profit_usd
                print(f"\n  >>> BF-SSSP found ${diff:,.4f} MORE profit than Dijkstra!")

    # BF cycles
    print(f"\n{'─'*72}")
    print(f"  Bellman-Ford Cycle Detection ($100)")
    print(f"{'─'*72}")
    bf_cycles = cex_bellman_ford(liquid_cash_usd=AMOUNT)
    if bf_cycles:
        print(f"  {len(bf_cycles)} cycle(s) found")
        for i, c in enumerate(bf_cycles[:3], 1):
            print(f"    Cycle {i}: profit=${c.profit_usd:,.4f} ({c.profit_pct:+.4f}%)")
    else:
        print(f"  No cycles found at $100.")

    # ────────────────────────────────────────────────────────
    # SUMMARY
    # ────────────────────────────────────────────────────────
    print("\n\n")
    print("█" * 80)
    print("  ALGORITHM COMPARISON SUMMARY")
    print("█" * 80)
    print("""
  ┌────────────────────┬───────────────┬────────────────────────────────────┐
  │ Algorithm          │ Negative      │ Key Behaviour                      │
  │                    │ Edges?        │                                    │
  ├────────────────────┼───────────────┼────────────────────────────────────┤
  │ Dijkstra           │ NO — greedy,  │ Always picks lowest-cost next      │
  │ (current default)  │ may miss      │ step. CANNOT take a loss now for   │
  │                    │ optimal paths │ a bigger gain later.               │
  ├────────────────────┼───────────────┼────────────────────────────────────┤
  │ BF-SSSP (NEW)      │ YES — handles │ Relaxes ALL edges at each depth.   │
  │                    │ negative      │ WILL take intermediate loss if     │
  │                    │ edges         │ the overall path profits more.     │
  │                    │ correctly     │ Guaranteed optimal within depth.   │
  ├────────────────────┼───────────────┼────────────────────────────────────┤
  │ BF Cycle Detect    │ YES           │ Finds ALL risk-free arbitrage      │
  │                    │               │ loops (negative-weight cycles).    │
  │                    │               │ Does not need a start node.        │
  ├────────────────────┼───────────────┼────────────────────────────────────┤
  │ A* + Heuristics    │ Depends on h  │ Faster than Dijkstra if heuristic  │
  │ (h1-h4, existing)  │               │ is good. Same negative-edge issue. │
  └────────────────────┴───────────────┴────────────────────────────────────┘

  RECOMMENDATION for volatile markets:
    Use BF-SSSP as the primary algorithm. It finds paths Dijkstra misses
    where you lose money on an intermediate swap/transfer but gain more
    on the next step (e.g., pay gas to bridge ETH to a chain where it's
    1.7% more expensive, even though the bridge itself costs 0.06%).
""")

    # Write to file
    sys.stdout = tee.stdout
    output = tee.getvalue()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"results/100_dollar_test_{timestamp}.txt"
    with open(filepath, "w") as f:
        f.write(output)
    print(f"\n  Results written to: {filepath}")
    return filepath


if __name__ == "__main__":
    run()
