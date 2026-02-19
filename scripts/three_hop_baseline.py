"""
3-hop enumeration baseline: brute-force search over transfer→trade→transfer cycles.

The professor's feedback suggests comparing against a domain-strong baseline
that enumerates all 3-hop cycles of the form:

  (exchange_A, coin) --transfer--> (exchange_B, coin) --trade--> (exchange_B, coin')
       --transfer--> (exchange_C, coin')

Since observed optimal paths in our experiments are typically 3 hops, this
baseline shows where A* search adds value (or doesn't) versus exhaustive
enumeration on small graphs.

The algorithm:
  1. For every node in the graph, enumerate all outgoing transfer edges.
  2. From the destination, enumerate all trade edges.
  3. From the trade destination, enumerate all transfer edges.
  4. Evaluate final cash and keep the most profitable 3-hop path.

Complexity: O(|V| * max_out_degree^3), which is feasible for graphs with
~50-100 nodes but becomes expensive for larger graphs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.graph import build_graph, NodeId

logger = logging.getLogger(__name__)


@dataclass
class PlanResult:
    path: List[NodeId]
    edges: List[Dict[str, Any]]
    final_cash_usd: float
    profit_usd: float
    nodes_expanded: int = 0
    nodes_generated: int = 0


def _final_cash_from_log_cost(
    initial_cash_usd: float,
    total_log_cost: float,
) -> float:
    """Convert log-space cost to final cash amount."""
    return initial_cash_usd * exp(-total_log_cost)


def three_hop_enumeration(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    Brute-force 3-hop enumeration baseline.

    Enumerates all paths of exactly 3 edges starting from start_node:
      hop 1: transfer (same coin, different exchange)
      hop 2: trade    (same exchange, different coin)
      hop 3: transfer (same coin, different exchange)

    Also enumerates the reverse pattern:
      hop 1: trade    (same exchange, different coin)
      hop 2: transfer (same coin, different exchange)
      hop 3: trade    (same exchange, different coin)

    Returns the most profitable 3-hop path, or None if no profitable path exists.
    """
    t0 = time.perf_counter()

    # Build graph with portfolio-appropriate fees
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)

    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")

    best_result: Optional[PlanResult] = None
    paths_evaluated = 0

    # --- Pattern 1: transfer → trade → transfer ---
    for edge1 in adj.get(start_node, []):
        if edge1.get("kind") != "transfer":
            continue

        node1 = edge1["to"]
        cost1 = float(edge1.get("cost", 0.0))
        time1 = float(edge1.get("transfer_time_sec", 0.0))

        for edge2 in adj.get(node1, []):
            if edge2.get("kind") != "trade":
                continue

            node2 = edge2["to"]
            cost2 = cost1 + float(edge2.get("cost", 0.0))
            time2 = time1 + float(edge2.get("transfer_time_sec", 0.0))

            if time2 > max_time_sec:
                continue

            for edge3 in adj.get(node2, []):
                if edge3.get("kind") != "transfer":
                    continue

                node3 = edge3["to"]
                total_cost = cost2 + float(edge3.get("cost", 0.0))
                total_time = time2 + float(edge3.get("transfer_time_sec", 0.0))

                if total_time > max_time_sec:
                    continue

                paths_evaluated += 1
                final_cash = _final_cash_from_log_cost(liquid_cash_usd, total_cost)
                profit = final_cash - liquid_cash_usd

                if final_cash > liquid_cash_usd and profit >= min_profit_usd:
                    if best_result is None or final_cash > best_result.final_cash_usd:
                        best_result = PlanResult(
                            path=[start_node, node1, node2, node3],
                            edges=[edge1, edge2, edge3],
                            final_cash_usd=final_cash,
                            profit_usd=profit,
                        )

    # --- Pattern 2: trade → transfer → trade ---
    for edge1 in adj.get(start_node, []):
        if edge1.get("kind") != "trade":
            continue

        node1 = edge1["to"]
        cost1 = float(edge1.get("cost", 0.0))
        time1 = float(edge1.get("transfer_time_sec", 0.0))

        for edge2 in adj.get(node1, []):
            if edge2.get("kind") != "transfer":
                continue

            node2 = edge2["to"]
            cost2 = cost1 + float(edge2.get("cost", 0.0))
            time2 = time1 + float(edge2.get("transfer_time_sec", 0.0))

            if time2 > max_time_sec:
                continue

            for edge3 in adj.get(node2, []):
                if edge3.get("kind") != "trade":
                    continue

                node3 = edge3["to"]
                total_cost = cost2 + float(edge3.get("cost", 0.0))
                total_time = time2 + float(edge3.get("transfer_time_sec", 0.0))

                if total_time > max_time_sec:
                    continue

                paths_evaluated += 1
                final_cash = _final_cash_from_log_cost(liquid_cash_usd, total_cost)
                profit = final_cash - liquid_cash_usd

                if final_cash > liquid_cash_usd and profit >= min_profit_usd:
                    if best_result is None or final_cash > best_result.final_cash_usd:
                        best_result = PlanResult(
                            path=[start_node, node1, node2, node3],
                            edges=[edge1, edge2, edge3],
                            final_cash_usd=final_cash,
                            profit_usd=profit,
                        )

    elapsed = time.perf_counter() - t0

    if best_result is not None:
        best_result.nodes_expanded = paths_evaluated
        best_result.nodes_generated = paths_evaluated

    if best_result is None:
        logger.info(
            f"3-hop enumeration: No profitable path found "
            f"({paths_evaluated} paths evaluated in {elapsed:.5f}s)"
        )
        return None

    logger.info(
        f"3-hop enumeration completed: profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}, "
        f"{paths_evaluated} paths evaluated in {elapsed:.5f}s, "
        f"path={' -> '.join(f'{ex}:{c}' for ex, c in best_result.path)}"
    )
    return best_result

