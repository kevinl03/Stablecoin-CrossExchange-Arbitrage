"""
Cross-exchange cryptocurrency arbitrage finder.

Self-contained runner that:
  1.  Builds the crypto arbitrage graph (live market data).
  2.  Runs Dijkstra's algorithm (shortest-path / best-profit search).
  3.  Runs Bellman-Ford negative-cycle detection.
  4.  Reports all profitable opportunities found.

Usage:
    python -m scripts.crypto_arbitrage                          # defaults
    python -m scripts.crypto_arbitrage --exchange binance --coin USDT --amount 10000
    python -m scripts.crypto_arbitrage --exchange kraken  --coin BTC  --amount 1.5  --depth 6
"""

from __future__ import annotations

import argparse
import heapq
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from math import exp, log
from typing import Any, Dict, List, Optional, Tuple

from scripts.crypto_graph import build_graph, Adjacency, NodeId

logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────────────────
# Result container
# ────────────────────────────────────────────────────────────

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
    """Convert summed log-costs back to dollar value."""
    return initial * exp(-total_log_cost)


# ────────────────────────────────────────────────────────────
# 1.  Dijkstra (A* with h = 0)
# ────────────────────────────────────────────────────────────

def dijkstra_best_path(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 5,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
    early_exit_iterations: int = 200,
) -> Optional[PlanResult]:
    """
    Best-first search for the most profitable path starting from
    *start_node* with *liquid_cash_usd*.

    Identical to the stablecoin A* but with h(n) = 0 (pure Dijkstra).
    Uses cost = -log(rate) and minimises total cost (= maximises product
    of rates = maximises final cash).
    """
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)

    if start_node not in nodes:
        available = sorted(nodes.keys())[:20]
        raise ValueError(
            f"Start node {start_node} not in graph. "
            f"Available (first 20): {available}"
        )

    # (g_score, tiebreaker, depth, elapsed_sec, node, path_nodes, path_edges)
    counter = 0
    frontier: List[Tuple[float, int, int, float, NodeId, List[NodeId], List[Dict]]] = []
    heapq.heappush(frontier, (0.0, counter, 0, 0.0, start_node, [start_node], []))
    counter += 1

    best_g: Dict[Tuple[NodeId, int], float] = {(start_node, 0): 0.0}
    best_result: Optional[PlanResult] = None
    found_profit = False
    iters_since_improvement = 0
    expanded = 0
    generated = 1

    while frontier:
        g, _, depth, elapsed, node, path_nodes, path_edges = heapq.heappop(frontier)
        expanded += 1

        if depth > 0:
            cash = _final_cash(liquid_cash_usd, g)
            profit = cash - liquid_cash_usd
            if cash > liquid_cash_usd and profit >= min_profit_usd:
                if best_result is None or cash > best_result.final_cash_usd:
                    best_result = PlanResult(
                        path=list(path_nodes),
                        edges=list(path_edges),
                        final_cash_usd=cash,
                        profit_usd=profit,
                        profit_pct=(profit / liquid_cash_usd) * 100.0,
                    )
                    found_profit = True
                    iters_since_improvement = 0
                else:
                    iters_since_improvement += 1
            elif found_profit:
                iters_since_improvement += 1

        if found_profit and iters_since_improvement >= early_exit_iterations:
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
                 path_nodes + [to_node], path_edges + [edge]),
            )
            counter += 1
            generated += 1

    if best_result is not None:
        best_result.nodes_expanded = expanded
        best_result.nodes_generated = generated
    return best_result


# ────────────────────────────────────────────────────────────
# 2.  Bellman-Ford — negative cycle detection
# ────────────────────────────────────────────────────────────

def _detect_negative_cycles(
    nodes: Dict[NodeId, Dict[str, Any]],
    adj: Adjacency,
) -> List[List[NodeId]]:
    """Standard Bellman-Ford: |V|-1 relaxations then one extra pass."""
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


def _extract_cycle(
    start: NodeId,
    pred: Dict[NodeId, Optional[NodeId]],
    max_steps: int,
) -> Optional[List[NodeId]]:
    visited: Dict[NodeId, int] = {}
    path: List[NodeId] = []
    current: Optional[NodeId] = start

    for _ in range(max_steps):
        if current is None:
            break
        if current in visited:
            return path[visited[current]:] + [current]
        visited[current] = len(path)
        path.append(current)
        current = pred.get(current)

    return None


def bellman_ford_crypto(
    liquid_cash_usd: float,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> List[PlanResult]:
    """
    Find **all** profitable arbitrage cycles via Bellman-Ford.

    Returns a list of PlanResult sorted by profit (descending).
    """
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

        path_nodes: List[NodeId] = []
        path_edges: List[Dict[str, Any]] = []
        total_cost = 0.0
        total_time = 0.0
        valid = True

        for i in range(len(cycle) - 1):
            u, v = cycle[i], cycle[i + 1]
            path_nodes.append(u)

            found = False
            for edge in adj.get(u, []):
                if edge["to"] == v:
                    path_edges.append(edge)
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
                path=path_nodes,
                edges=path_edges,
                final_cash_usd=cash,
                profit_usd=profit,
                profit_pct=(profit / liquid_cash_usd) * 100.0,
            ))

    results.sort(key=lambda r: -r.profit_usd)
    return results


# ────────────────────────────────────────────────────────────
# 3.  Pretty printing helpers
# ────────────────────────────────────────────────────────────

def _format_path(result: PlanResult) -> str:
    lines: List[str] = []
    lines.append(
        f"  Profit: ${result.profit_usd:,.2f}  "
        f"({result.profit_pct:+.4f}%)  "
        f"Final value: ${result.final_cash_usd:,.2f}"
    )
    lines.append(f"  Path length: {len(result.path)} nodes")

    for i, edge in enumerate(result.edges):
        fr = edge["from"]
        to = edge["to"]
        kind = edge["kind"]
        rate = edge.get("rate", 0)
        if kind == "trade":
            pair = edge.get("pair", f"{fr[1]}/{to[1]}")
            fee = edge.get("taker_fee", 0) * 100
            lines.append(
                f"    {i+1}. TRADE   {fr[0]:10s}  {fr[1]:5s} → {to[1]:5s}  "
                f"pair={pair}  rate={rate:.8f}  fee={fee:.3f}%"
            )
        else:
            chain = edge.get("chain", "?")
            wd = edge.get("withdrawal_fee_units", 0)
            gas = edge.get("gas_fee_usd", 0)
            t = edge.get("transfer_time_sec", 0)
            lines.append(
                f"    {i+1}. XFER    {fr[0]:10s} → {to[0]:10s}  [{fr[1]}]  "
                f"chain={chain}  wd_fee={wd}  gas=${gas:.2f}  "
                f"time={t:.0f}s  rate={rate:.8f}"
            )

    return "\n".join(lines)


# ────────────────────────────────────────────────────────────
# 4.  CLI entry-point
# ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Cross-exchange crypto arbitrage finder"
    )
    parser.add_argument(
        "--exchange", default="binance",
        help="Starting exchange (default: binance)",
    )
    parser.add_argument(
        "--coin", default="USDT",
        help="Starting coin (default: USDT)",
    )
    parser.add_argument(
        "--amount", type=float, default=10_000.0,
        help="Starting portfolio in USD (default: 10000)",
    )
    parser.add_argument(
        "--depth", type=int, default=5,
        help="Max search depth for Dijkstra (default: 5)",
    )
    parser.add_argument(
        "--time", type=float, default=1800.0,
        help="Max wall-clock seconds for arbitrage cycle (default: 1800)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-7s  %(message)s",
    )

    start_node: NodeId = (args.exchange, args.coin)
    cash = args.amount

    print("=" * 70)
    print("  CRYPTO ARBITRAGE FINDER")
    print(f"  Start: {start_node}  |  Portfolio: ${cash:,.2f}")
    print("=" * 70)

    # ── Dijkstra ──
    print("\n── Dijkstra (best-profit path search) ──")
    try:
        dijk_result = dijkstra_best_path(
            start_node=start_node,
            liquid_cash_usd=cash,
            max_depth=args.depth,
            max_time_sec=args.time,
        )
        if dijk_result:
            print(f"\n  *** PROFITABLE PATH FOUND ***")
            print(_format_path(dijk_result))
            print(
                f"\n  Search stats: expanded={dijk_result.nodes_expanded}, "
                f"generated={dijk_result.nodes_generated}"
            )
        else:
            print("  No profitable path found via Dijkstra.")
    except ValueError as e:
        print(f"  Error: {e}")

    # ── Bellman-Ford ──
    print("\n── Bellman-Ford (negative-cycle detection) ──")
    bf_results = bellman_ford_crypto(
        liquid_cash_usd=cash,
        max_time_sec=args.time,
    )
    if bf_results:
        print(f"\n  *** {len(bf_results)} ARBITRAGE CYCLE(S) FOUND ***\n")
        for idx, res in enumerate(bf_results[:10], 1):
            print(f"  ─── Cycle {idx} ───")
            print(_format_path(res))
            print()
    else:
        print("  No negative cycles (arbitrage) detected by Bellman-Ford.")

    print("=" * 70)
    print("  Done.")
    print("=" * 70)


if __name__ == "__main__":
    main()
