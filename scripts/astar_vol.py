
from __future__ import annotations # lets the file use flexible type hints without worrying about import order.

import heapq
import logging
from dataclasses import dataclass #used so we dont use _init_ and _repr_
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.graph import build_graph            
from scripts.h1_vol import volume_heuristic_cost
# h2_slippage imported conditionally when needed

# Set up logging
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
    edges: List[Dict[str, Any]]     # sequence of edge dicts, used for edge costs and extracted from fees.py
    final_cash_usd: float
    profit_usd: float
    nodes_expanded: int = 0         # number of nodes popped from frontier
    nodes_generated: int = 0        # number of nodes pushed to frontier


def _calculate_cost_breakdown(
    edges: List[Dict[str, Any]],
    initial_cash_usd: float,
) -> Dict[str, Any]:
    """
    Calculate detailed cost breakdown from path edges.
    
    Returns:
        Dictionary with cost breakdown information.
    """
    num_trades = 0
    num_transfers = 0
    total_trading_fees = 0.0
    total_withdrawal_fees = 0.0
    total_gas_fees = 0.0
    current_cash = initial_cash_usd
    
    for edge in edges:
        edge_kind = edge.get("kind")
        
        if edge_kind == "trade":
            num_trades += 1
            taker_fee = edge.get("taker_fee", 0.0)
            if taker_fee:
                trading_fee = current_cash * taker_fee
                total_trading_fees += trading_fee
                rate = edge.get("rate", 1.0)
                current_cash = current_cash * rate
        
        elif edge_kind == "transfer":
            num_transfers += 1
            total_fee_usd = edge.get("total_fee_usd")
            withdrawal_fee_units = edge.get("withdrawal_fee_units")
            gas_fee_usd = edge.get("gas_fee_usd", 0.0)
            
            if total_fee_usd is not None:
                if withdrawal_fee_units is not None and gas_fee_usd > 0:
                    withdrawal_fee_usd = withdrawal_fee_units * 1.0
                    total_withdrawal_fees += withdrawal_fee_usd
                    total_gas_fees += gas_fee_usd
                elif gas_fee_usd > 0:
                    total_gas_fees += gas_fee_usd
                    total_withdrawal_fees += (total_fee_usd - gas_fee_usd)
                elif withdrawal_fee_units is not None:
                    withdrawal_fee_usd = withdrawal_fee_units * 1.0
                    total_withdrawal_fees += withdrawal_fee_usd
                else:
                    total_withdrawal_fees += total_fee_usd
                
                rate = edge.get("rate", 1.0)
                current_cash = current_cash * rate
            else:
                if withdrawal_fee_units is not None:
                    withdrawal_fee_usd = withdrawal_fee_units * 1.0
                    total_withdrawal_fees += withdrawal_fee_usd
                    current_cash -= withdrawal_fee_usd
                if gas_fee_usd:
                    total_gas_fees += gas_fee_usd
                    current_cash -= gas_fee_usd
    
    total_costs = total_trading_fees + total_withdrawal_fees + total_gas_fees
    
    return {
        "num_trades": num_trades,
        "num_transfers": num_transfers,
        "total_trading_fees": total_trading_fees,
        "total_withdrawal_fees": total_withdrawal_fees,
        "total_gas_fees": total_gas_fees,
        "total_costs": total_costs,
    }


def _final_cash_from_log_cost(
    initial_cash_usd: float,
    total_log_cost: float,
) -> float:
    """
    Our graph edges store:

        cost = -log(rate)

    where 'rate' is the multiplicative factor on *portfolio value*
    after that step (including fees & withdrawal loss).

    If we sum all costs:

        total_log_cost = sum_i -log(rate_i) = -log(prod_i rate_i)

    then:

        prod_i rate_i = exp(-total_log_cost)
        final_cash    = initial_cash * prod_i rate_i
                       = initial_cash * exp(-total_log_cost)
    """
    return initial_cash_usd * exp(-total_log_cost)


def astar_best_path_with_liquidity(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 4,  # Reduced from 6 to 4 for faster execution
    max_time_sec: float = 1800.0,   # 30 minutes by default
    min_profit_usd: float = 0.0,
    heuristic: str = "h1_liquidity",  # "h1_liquidity" or "h2_slippage"
    early_exit_after_profit: bool = True,  # Exit early when profitable path found
    early_exit_iterations: int = 100,  # Continue searching for better paths for N iterations after finding profit
) -> Optional[PlanResult]:
    """
    A* search over the arbitrage graph that:

      * Starts at `start_node` with `liquid_cash_usd` (USD value).
      * Uses edge["rate"] / edge["cost"] from graph.py
        (these already encode spreads + taker/withdrawal fees).
      * Uses edge["transfer_time_sec"] for timing.
      * Uses selected heuristic (h1_liquidity or h2_slippage) to guide search.
      * Treats ANY reachable node as a potential destination where
        the trader does their last buy, then conceptually sells to USD.
      * Picks the path with the highest final USD value.

    We do **not** require returning to the original node.

    Returns
    -------
    PlanResult or None if no profitable path within constraints.
    """
    # Build graph (nodes: metadata; adj: adjacency list)
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)

    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")

    start_state = SearchState(node=start_node, depth=0, elapsed_sec=0.0)
    start_g = 0.0

    # Initial heuristic: selected heuristic at the start node
    logger.info(f"A* search starting with heuristic: {heuristic}")
    logger.info(f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}")
    
    if heuristic == "h2_slippage":
        from scripts.h2_slippage import slippage_heuristic_cost
        start_h = slippage_heuristic_cost(
            exchange_name=start_node[0],
            coin=start_node[1],
            order_size_usd=liquid_cash_usd,
            side="buy",  # Assume buying at start
        )
        logger.info(f"Start node h2_slippage heuristic: {start_h:.6f}")
    elif heuristic == "h1_liquidity":
        start_h = volume_heuristic_cost(
            exchange_name=start_node[0],
            coin=start_node[1],
            order_notional_usd=liquid_cash_usd,
            remaining_time_sec=max_time_sec,
        )
        logger.info(f"Start node h1_liquidity heuristic: {start_h:.6f}")
    else:
        raise ValueError(f"Unknown heuristic: {heuristic}. Must be 'h1_liquidity' or 'h2_slippage'")
    start_f = start_g + start_h
    logger.info(f"Start f_score: {start_f:.6f} (g={start_g:.6f} + h={start_h:.6f})")

    frontier: List[
        Tuple[float, float, int, SearchState, List[NodeId], List[Dict[str, Any]]]
    ] = []

    counter = 0  # unique tie-breaker based on position 
    heapq.heappush(frontier, (start_f, start_g, counter, start_state, [start_node], []))
    counter += 1

    # For pruning: best (lowest) g_score we've seen for (node, depth)
    best_g_seen: Dict[Tuple[NodeId, int], float] = {(start_node, 0): start_g}

    best_result: Optional[PlanResult] = None
    iterations_since_profit = 0
    found_profit = False
    nodes_expanded = 0
    nodes_generated = 1  # start node

    while frontier:
        f_score, g_score, _, state, path_nodes, path_edges = heapq.heappop(frontier)
        current_node = state.node
        nodes_expanded += 1

        # Recompute current cash in USD from g_score
        current_cash = _final_cash_from_log_cost(liquid_cash_usd, g_score)

        # Record this as a candidate destination (unless it's the trivial start state)
        if state.depth > 0:
            final_cash = current_cash
            profit = final_cash - liquid_cash_usd

            # NOTE: final_cash already has fees deducted (they're baked into edge rates)
            # So profit is already NET profit - no need to compare to fees

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
                    
                    # Calculate cost breakdown
                    cost_breakdown = _calculate_cost_breakdown(path_edges, liquid_cash_usd)
                    cost_info = (
                        f" | fees: trade=${cost_breakdown['total_trading_fees']:.2f} "
                        f"({cost_breakdown['num_trades']}x), "
                        f"wd=${cost_breakdown['total_withdrawal_fees']:.2f} "
                        f"({cost_breakdown['num_transfers']}x), "
                        f"gas=${cost_breakdown['total_gas_fees']:.2f}, "
                        f"total=${cost_breakdown['total_costs']:.2f}"
                    )
                    
                    logger.info(
                        f"New best path found (heuristic={heuristic}): "
                        f"profit=${profit:.2f}, path_length={len(path_nodes)}{cost_info}, "
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

            # Cost update (graph.py already gives us cost = -log(rate))
            edge_cost = float(edge.get("cost", 0.0))
            new_g = g_score + edge_cost
            new_depth = state.depth + 1
            new_state = SearchState(node=to_node, depth=new_depth, elapsed_sec=new_elapsed)

            key = (to_node, new_depth)

            # If we've already reached (node, depth) with a strictly better g (lower),
            # we don't need to expand this worse version.
            if key in best_g_seen and new_g >= best_g_seen[key]:
                continue
            best_g_seen[key] = new_g

            # Heuristic: selected heuristic cost at the neighbor
            remaining_time = max_time_sec - new_elapsed
            # Current notional after taking this edge:
            new_cash = _final_cash_from_log_cost(liquid_cash_usd, new_g)

            if heuristic == "h2_slippage":
                from scripts.h2_slippage import slippage_heuristic_cost
                # Determine side based on edge type (trade vs transfer)
                edge_kind = edge.get("kind", "trade")
                side = "buy" if edge_kind == "trade" else "buy"  # Default to buy
                h = slippage_heuristic_cost(
                    exchange_name=to_node[0],
                    coin=to_node[1],
                    order_size_usd=new_cash,
                    side=side,
                )
                logger.debug(
                    f"  h2_slippage at {to_node[0]}:{to_node[1]}: h={h:.6f} "
                    f"(order_size=${new_cash:.2f})"
                )
            elif heuristic == "h1_liquidity":
                h = volume_heuristic_cost(
                    exchange_name=to_node[0],
                    coin=to_node[1],
                    order_notional_usd=new_cash,
                    remaining_time_sec=remaining_time,
                )
                logger.debug(
                    f"  h1_liquidity at {to_node[0]}:{to_node[1]}: h={h:.6f} "
                    f"(order_size=${new_cash:.2f}, remaining_time={remaining_time:.1f}s)"
                )
            else:
                raise ValueError(f"Unknown heuristic: {heuristic}. Must be 'h1_liquidity' or 'h2_slippage'")

            f = new_g + h

            # Extend paths
            new_path_nodes = path_nodes + [to_node]
            new_path_edges = path_edges + [edge]

            # Push with a fresh unique counter so heapq never compares SearchState
            heapq.heappush(
                frontier,
                (f, new_g, counter, new_state, new_path_nodes, new_path_edges),
            )
            counter += 1
            nodes_generated += 1

    if best_result is None:
        logger.info(
            f"A* search completed (heuristic={heuristic}): No profitable path found "
            f"(expanded={nodes_expanded}, generated={nodes_generated})"
        )
        return None

    # Store search stats on result
    best_result.nodes_expanded = nodes_expanded
    best_result.nodes_generated = nodes_generated

    # Calculate final cost breakdown
    cost_breakdown = _calculate_cost_breakdown(best_result.edges, liquid_cash_usd)
    cost_info = (
        f" | fees: trade=${cost_breakdown['total_trading_fees']:.2f} "
        f"({cost_breakdown['num_trades']}x), "
        f"wd=${cost_breakdown['total_withdrawal_fees']:.2f} "
        f"({cost_breakdown['num_transfers']}x), "
        f"gas=${cost_breakdown['total_gas_fees']:.2f}, "
        f"total=${cost_breakdown['total_costs']:.2f}"
    )
    
    logger.info(
        f"A* search completed (heuristic={heuristic}): "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}{cost_info}, "
        f"expanded={nodes_expanded}, generated={nodes_generated}, "
        f"path={' -> '.join(f'{ex}:{c}' for (ex, c) in best_result.path)}"
    )
    return best_result
