# ==========================================================
# weighted_astar.py — Weighted A* using chain + exchange risk (h4+h5)
# ==========================================================

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.graph import build_graph
from scripts.h4_chaincongestion_exchange_risk import (
    estimate_chain_kickback_risk_score,
    chain_exchange_risk_heuristic_cost,
)

logger = logging.getLogger(__name__)

# Node is ("binance", "USDT")
NodeId = Tuple[str, str]


@dataclass(frozen=True)
class SearchState:
    node: NodeId
    depth: int
    elapsed_sec: float  # total time spent along this path so far


@dataclass
class PlanResult:
    path: List[NodeId]              # sequence of nodes
    edges: List[Dict[str, Any]]     # sequence of edge dicts
    final_cash_usd: float
    profit_usd: float


# ------------------------------------------------------
# Helper: log-cost → final cash
# ------------------------------------------------------

def _final_cash_from_log_cost(
    initial_cash_usd: float,
    total_log_cost: float,
) -> float:
    return initial_cash_usd * exp(-total_log_cost)


# ------------------------------------------------------
# Weighted A* parameters for chain component
# ------------------------------------------------------

# These control how strongly we scale the chain-related heuristic
# based on "how fast" a chain is.
#
# Design:
#   - Fast chains (short transfer time, high kickback risk) ⇒ HIGHER weight
#   - Slow chains (longer transfer time) ⇒ LOWER weight
MIN_CHAIN_WEIGHT: float = 1.0
MAX_CHAIN_WEIGHT: float = 3.0


def _compute_chain_weight_from_risk(risk: float) -> float:
    """
    Map risk in [0,1] → W_chain in [MIN_CHAIN_WEIGHT, MAX_CHAIN_WEIGHT].

    Higher risk (fast chain) ⇒ higher W_chain.
    """
    if risk < 0.0:
        risk = 0.0
    elif risk > 1.0:
        risk = 1.0

    w = MIN_CHAIN_WEIGHT + (MAX_CHAIN_WEIGHT - MIN_CHAIN_WEIGHT) * risk
    return max(MIN_CHAIN_WEIGHT, min(MAX_CHAIN_WEIGHT, w))


# ------------------------------------------------------
# Weighted A* using chain + exchange risk heuristic
# ------------------------------------------------------

def weighted_astar_best_path(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 4,  # Reduced from 6 to 4 for faster execution
    max_time_sec: float = 1800.0,   # 30 minutes by default
    min_profit_usd: float = 0.0,
    early_exit_after_profit: bool = True,  # Exit early when profitable path found
    early_exit_iterations: int = 100,  # Continue searching for better paths for N iterations after finding profit
) -> Optional[PlanResult]:
    """
    Weighted A* search over the arbitrage graph that:

      * Starts at `start_node` with `liquid_cash_usd` (USD value).
      * Uses edge["rate"] / edge["cost"] from graph.py
        (these already encode spreads + taker/withdrawal fees).
      * Uses edge["transfer_time_sec"] for timing.
      * Uses a combined heuristic h(n) = h_chain(n) + h_exchange(n):
          - h_chain: penalizes FAST chains (kickback / timing risk)
          - h_exchange: penalizes risky exchanges (freeze / halt risk)
      * Applies a node-specific weight W_chain that depends only on
        chain kickback risk (fast chain ⇒ higher W_chain).
      * Treats ANY reachable node as a potential destination.
      * Picks the path with the highest final USD value.
    """

    # Build graph (nodes: metadata; adj: adjacency list)
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)

    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")

    # Priority queue entries:
    #   (f_score, g_score, counter, SearchState, path_nodes, path_edges)
    start_state = SearchState(node=start_node, depth=0, elapsed_sec=0.0)
    start_g = 0.0

    logger.info("Weighted A* search starting with chain+exchange risk heuristic (h4+h5)")
    logger.info(
        f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}, "
        f"max_time_sec={max_time_sec}"
    )

    # Initial heuristic (remaining time is the full budget at start)
    start_remaining_time = max_time_sec

    # Chain risk used for weighting
    start_chain_risk = estimate_chain_kickback_risk_score(
        exchange_name=start_node[0],
        coin=start_node[1],
        remaining_time_sec=start_remaining_time,
    )

    # Combined heuristic: chain + exchange risk
    start_h = chain_exchange_risk_heuristic_cost(
        exchange_name=start_node[0],
        coin=start_node[1],
        remaining_time_sec=start_remaining_time,
    )

    start_W = _compute_chain_weight_from_risk(start_chain_risk)
    start_f = start_g + start_W * start_h

    logger.info(
        f"Start node: chain_risk={start_chain_risk:.6f}, "
        f"h_combined={start_h:.6f}, W_chain={start_W:.3f}, f={start_f:.6f}"
    )

    frontier: List[
        Tuple[float, float, int, SearchState, List[NodeId], List[Dict[str, Any]]]
    ] = []

    counter = 0
    heapq.heappush(frontier, (start_f, start_g, counter, start_state, [start_node], []))
    counter += 1

    # For pruning: best (lowest) g_score we've seen for (node, depth)
    best_g_seen: Dict[Tuple[NodeId, int], float] = {(start_node, 0): start_g}

    best_result: Optional[PlanResult] = None
    iterations_since_profit = 0
    found_profit = False

    while frontier:
        f_score, g_score, _, state, path_nodes, path_edges = heapq.heappop(frontier)
        current_node = state.node

        # Recompute current cash in USD from g_score
        current_cash = _final_cash_from_log_cost(liquid_cash_usd, g_score)

        # Record this as a candidate destination (unless it's the trivial start state)
        if state.depth > 0:
            final_cash = current_cash
            profit = final_cash - liquid_cash_usd

            if final_cash > liquid_cash_usd and profit >= min_profit_usd:
                if best_result is None or final_cash > best_result.final_cash_usd:
                    best_result = PlanResult(
                        path=path_nodes.copy(),
                        edges=path_edges.copy(),
                        final_cash_usd=final_cash,
                        profit_usd=profit,
                    )
                    found_profit = True
                    iterations_since_profit = 0  # Reset counter when we find a better path
                    logger.info(
                        "New best path found (Weighted A* h4+h5): "
                        f"profit=${profit:.2f}, path_length={len(path_nodes)}, "
                        f"path={' -> '.join(f'{ex}:{c}' for (ex, c) in path_nodes)}"
                    )
                else:
                    # Found a profit but not better than current best
                    if found_profit:
                        iterations_since_profit += 1
            else:
                # No profit found, increment counter if we previously found profit
                if found_profit:
                    iterations_since_profit += 1
        
        # Early exit: if we found a profitable path and searched enough iterations without improvement
        if early_exit_after_profit and found_profit and iterations_since_profit >= early_exit_iterations:
            logger.info(
                f"Early exit: Found profitable path and searched {iterations_since_profit} iterations "
                f"without improvement. Returning best result."
            )
            break

        # Stop expanding if depth/time limits reached
        if state.depth >= max_depth or state.elapsed_sec >= max_time_sec:
            continue

        # Expand neighbors
        for edge in adj.get(current_node, []):
            to_node: NodeId = edge["to"]

            # Time update
            dt = float(edge.get("transfer_time_sec", 0.0))
            new_elapsed = state.elapsed_sec + dt
            if new_elapsed > max_time_sec:
                continue

            # Cost update (graph.py gives us cost = -log(rate))
            edge_cost = float(edge.get("cost", 0.0))
            new_g = g_score + edge_cost
            new_depth = state.depth + 1
            new_state = SearchState(node=to_node, depth=new_depth, elapsed_sec=new_elapsed)

            key = (to_node, new_depth)

            if key in best_g_seen and new_g >= best_g_seen[key]:
                continue
            best_g_seen[key] = new_g

            # Remaining time budget
            remaining_time = max_time_sec - new_elapsed

            # Chain risk (fast = higher risk) — used for the weight
            chain_risk = estimate_chain_kickback_risk_score(
                exchange_name=to_node[0],
                coin=to_node[1],
                remaining_time_sec=remaining_time,
            )

            # Combined heuristic: chain + exchange risk
            h = chain_exchange_risk_heuristic_cost(
                exchange_name=to_node[0],
                coin=to_node[1],
                remaining_time_sec=remaining_time,
            )

            # Node-specific chain weight from chain risk
            W_chain = _compute_chain_weight_from_risk(chain_risk)

            f = new_g + W_chain * h

            logger.debug(
                f"  Neighbor {to_node[0]}:{to_node[1]}: "
                f"g={new_g:.6f}, chain_risk={chain_risk:.6f}, "
                f"h_combined={h:.6f}, W_chain={W_chain:.3f}, "
                f"f={f:.6f}, remaining_time={remaining_time:.1f}s"
            )

            new_path_nodes = path_nodes + [to_node]
            new_path_edges = path_edges + [edge]

            heapq.heappush(
                frontier,
                (f, new_g, counter, new_state, new_path_nodes, new_path_edges),
            )
            counter += 1

    if best_result is None:
        logger.info("Weighted A* (h4+h5) completed: No profitable path found")
        return None

    logger.info(
        "Weighted A* (h4+h5) completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}, "
        f"path={' -> '.join(f'{ex}:{c}' for ex, c in best_result.path)}"
    )
    return best_result


if __name__ == "__main__":
    # Optional quick smoke test or just leave empty
    pass
