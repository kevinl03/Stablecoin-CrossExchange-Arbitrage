"""
Cross-chain DEX arbitrage finder.

Builds an on-chain arbitrage graph from DeFi-Llama prices (Uniswap,
Curve, Jupiter, etc.) and runs Dijkstra + Bellman-Ford to discover
profitable paths across blockchains.

Usage:
    python -m scripts.defi_arbitrage
    python -m scripts.defi_arbitrage --chain arbitrum --token WETH --amount 10000
    python -m scripts.defi_arbitrage --chain solana   --token SOL  --amount 5000 --depth 6
"""

from __future__ import annotations

import argparse
import heapq
import logging
from collections import defaultdict
from dataclasses import dataclass
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.defi_graph import build_graph, Adjacency, NodeId

logger = logging.getLogger(__name__)


@dataclass
class PlanResult:
    path: List[NodeId]
    edges: List[Dict[str, Any]]
    final_cash_usd: float
    profit_usd: float
    profit_pct: float
    nodes_expanded: int = 0
    nodes_generated: int = 0


def _final_cash(initial: float, total_log_cost: float) -> float:
    return initial * exp(-total_log_cost)


# ────────────────────────────────────────────────────────────
# 1.  Dijkstra
# ────────────────────────────────────────────────────────────

def dijkstra_best_path(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 3600.0,
    min_profit_usd: float = 0.0,
    early_exit_iterations: int = 300,
) -> Optional[PlanResult]:
    """
    Best-first search for the most profitable path from *start_node*.
    """
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)

    if start_node not in nodes:
        available = sorted(nodes.keys())[:20]
        raise ValueError(
            f"Start node {start_node} not in graph. "
            f"Available (first 20): {available}"
        )

    counter = 0
    frontier: List[Tuple[float, int, int, float, NodeId, List[NodeId], List[Dict]]] = []
    heapq.heappush(frontier, (0.0, counter, 0, 0.0, start_node, [start_node], []))
    counter += 1

    best_g: Dict[Tuple[NodeId, int], float] = {(start_node, 0): 0.0}
    best: Optional[PlanResult] = None
    found = False
    stale = 0
    expanded = 0
    generated = 1

    while frontier:
        g, _, depth, elapsed, node, pnodes, pedges = heapq.heappop(frontier)
        expanded += 1

        if depth > 0:
            cash = _final_cash(liquid_cash_usd, g)
            profit = cash - liquid_cash_usd
            if cash > liquid_cash_usd and profit >= min_profit_usd:
                if best is None or cash > best.final_cash_usd:
                    best = PlanResult(
                        path=list(pnodes),
                        edges=list(pedges),
                        final_cash_usd=cash,
                        profit_usd=profit,
                        profit_pct=(profit / liquid_cash_usd) * 100.0,
                    )
                    found = True
                    stale = 0
                else:
                    stale += 1
            elif found:
                stale += 1

        if found and stale >= early_exit_iterations:
            break

        if depth >= max_depth or elapsed >= max_time_sec:
            continue

        for edge in adj.get(node, []):
            to_node: NodeId = edge["to"]
            dt = float(edge.get("transfer_time_sec", 0.0))
            new_elapsed = elapsed + dt
            if new_elapsed > max_time_sec:
                continue

            new_g = g + float(edge.get("cost", 0.0))
            new_depth = depth + 1
            key = (to_node, new_depth)

            if key in best_g and new_g >= best_g[key]:
                continue
            best_g[key] = new_g

            heapq.heappush(
                frontier,
                (new_g, counter, new_depth, new_elapsed, to_node,
                 pnodes + [to_node], pedges + [edge]),
            )
            counter += 1
            generated += 1

    if best is not None:
        best.nodes_expanded = expanded
        best.nodes_generated = generated
    return best


# ────────────────────────────────────────────────────────────
# 2.  Bellman-Ford
# ────────────────────────────────────────────────────────────

def _detect_negative_cycles(
    nodes: Dict[NodeId, Dict[str, Any]],
    adj: Adjacency,
) -> List[List[NodeId]]:
    all_nodes = list(nodes.keys())
    n = len(all_nodes)
    dist: Dict[NodeId, float] = {nd: 0.0 for nd in all_nodes}
    pred: Dict[NodeId, Optional[NodeId]] = {nd: None for nd in all_nodes}

    for _ in range(n - 1):
        relaxed = False
        for u in all_nodes:
            for edge in adj.get(u, []):
                v = edge["to"]
                c = float(edge.get("cost", 0.0))
                if dist[u] + c < dist[v]:
                    dist[v] = dist[u] + c
                    pred[v] = u
                    relaxed = True
        if not relaxed:
            break

    cycles: List[List[NodeId]] = []
    seen: set = set()
    for u in all_nodes:
        for edge in adj.get(u, []):
            v = edge["to"]
            c = float(edge.get("cost", 0.0))
            if dist[u] + c < dist[v]:
                cycle = _extract_cycle(v, pred, n)
                if cycle:
                    key = tuple(cycle)
                    if key not in seen:
                        seen.add(key)
                        cycles.append(cycle)
    return cycles


def _extract_cycle(start, pred, max_steps):
    visited, path = {}, []
    current = start
    for _ in range(max_steps):
        if current is None:
            break
        if current in visited:
            return path[visited[current]:] + [current]
        visited[current] = len(path)
        path.append(current)
        current = pred.get(current)
    return None


def bellman_ford_defi(
    liquid_cash_usd: float,
    max_time_sec: float = 3600.0,
    min_profit_usd: float = 0.0,
) -> List[PlanResult]:
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    if not nodes:
        return []

    cycles = _detect_negative_cycles(nodes, adj)
    if not cycles:
        return []

    results: List[PlanResult] = []
    for cycle in cycles:
        if len(cycle) < 2:
            continue

        pnodes, pedges = [], []
        total_cost, total_time = 0.0, 0.0
        valid = True

        for i in range(len(cycle) - 1):
            u, v = cycle[i], cycle[i + 1]
            pnodes.append(u)
            found = False
            for edge in adj.get(u, []):
                if edge["to"] == v:
                    pedges.append(edge)
                    total_cost += float(edge.get("cost", 0.0))
                    total_time += float(edge.get("transfer_time_sec", 0.0))
                    found = True
                    break
            if not found:
                valid = False
                break

        if not valid or total_time > max_time_sec:
            continue

        cash = _final_cash(liquid_cash_usd, total_cost)
        profit = cash - liquid_cash_usd
        if profit >= min_profit_usd:
            results.append(PlanResult(
                path=pnodes,
                edges=pedges,
                final_cash_usd=cash,
                profit_usd=profit,
                profit_pct=(profit / liquid_cash_usd) * 100.0,
            ))

    results.sort(key=lambda r: -r.profit_usd)
    return results


# ────────────────────────────────────────────────────────────
# 3.  Formatting
# ────────────────────────────────────────────────────────────

def _format_path(result: PlanResult) -> str:
    lines = [
        f"  Profit: ${result.profit_usd:,.2f}  "
        f"({result.profit_pct:+.4f}%)  "
        f"Final value: ${result.final_cash_usd:,.2f}",
        f"  Path length: {len(result.path)} nodes",
    ]

    for i, edge in enumerate(result.edges):
        fr = edge["from"]
        to = edge["to"]
        kind = edge["kind"]
        rate = edge.get("rate", 0)

        if kind == "swap":
            fee = edge.get("dex_fee", 0) * 100
            gas = edge.get("gas_usd", 0)
            lines.append(
                f"    {i+1}. SWAP    {fr[0]:10s}  {fr[1]:5s} → {to[1]:5s}  "
                f"rate={rate:.8f}  dex_fee={fee:.2f}%  gas=${gas:.2f}"
            )
        else:  # bridge
            pr = edge.get("price_ratio", 0)
            pf = edge.get("bridge_pct_fee", 0) * 100
            ff = edge.get("bridge_flat_fee_usd", 0)
            t = edge.get("transfer_time_sec", 0)
            p_from = edge.get("price_from_usd", 0)
            p_to = edge.get("price_to_usd", 0)
            lines.append(
                f"    {i+1}. BRIDGE  {fr[0]:10s} → {to[0]:10s}  [{fr[1]:5s}]  "
                f"rate={rate:.8f}  price ${p_from:,.2f}→${p_to:,.2f}  "
                f"ratio={pr:.6f}  fee={pf:.3f}%+${ff:.2f}  time={t:.0f}s"
            )

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# 4.  CLI
# ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-chain DEX arbitrage finder (DeFi-Llama + Hyperliquid)"
    )
    parser.add_argument("--chain", default="ethereum",
                        help="Starting chain (default: ethereum)")
    parser.add_argument("--token", default="WETH",
                        help="Starting token (default: WETH)")
    parser.add_argument("--amount", type=float, default=10_000.0,
                        help="Starting portfolio in USD (default: 10000)")
    parser.add_argument("--depth", type=int, default=6,
                        help="Max search depth (default: 6)")
    parser.add_argument("--time", type=float, default=3600.0,
                        help="Max seconds for arb cycle (default: 3600)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    start_node: NodeId = (args.chain, args.token)
    cash = args.amount

    print("=" * 70)
    print("  CROSS-CHAIN DEX ARBITRAGE FINDER")
    print(f"  Start: {start_node}  |  Portfolio: ${cash:,.2f}")
    print(f"  Data source: DeFi-Llama (Uniswap, Curve, Jupiter, …)")
    print("=" * 70)

    # ── Dijkstra ──
    print("\n── Dijkstra (best-profit path search) ──")
    try:
        dijk = dijkstra_best_path(
            start_node=start_node,
            liquid_cash_usd=cash,
            max_depth=args.depth,
            max_time_sec=args.time,
        )
        if dijk:
            print(f"\n  *** PROFITABLE PATH FOUND ***")
            print(_format_path(dijk))
            print(
                f"\n  Search stats: expanded={dijk.nodes_expanded}, "
                f"generated={dijk.nodes_generated}"
            )
        else:
            print("  No profitable path found.")
    except ValueError as e:
        print(f"  Error: {e}")

    # ── Bellman-Ford ──
    print("\n── Bellman-Ford (negative-cycle detection) ──")
    bf = bellman_ford_defi(
        liquid_cash_usd=cash,
        max_time_sec=args.time,
    )
    if bf:
        print(f"\n  *** {len(bf)} ARBITRAGE CYCLE(S) FOUND ***\n")
        for idx, res in enumerate(bf[:10], 1):
            print(f"  ─── Cycle {idx} ───")
            print(_format_path(res))
            print()
    else:
        print("  No negative cycles detected.")

    print("=" * 70)
    print("  Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
