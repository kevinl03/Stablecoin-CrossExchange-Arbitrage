"""
Baseline algorithms for arbitrage path search.

These algorithms serve as baselines for comparison against heuristic-guided A* search:
- dijkstra_like: A* with h(n)=0 (no heuristic guidance)
- greedy_best_first: Uses only heuristic, ignores path cost
- breadth_first_search: Explores all paths up to depth limit
- simple_1hop_arbitrage: Direct transfer cycle between two exchanges (same coin)
- simple_2hop_arbitrage: Transfer A→B, trade on B, transfer back to A

Related Research Baseline:
- bellman_ford_arbitrage: Bellman-Ford algorithm for negative cycle detection
  (see scripts/bellman_ford_arbitrage.py and docs/RELATED_RESEARCH.md)
  This implements the methodology from Oantă & Coroiu (2023) for theoretical
  arbitrage detection, serving as a baseline that shows what's theoretically
  possible vs. what's executable with our execution-aware A* approach.
"""

from __future__ import annotations

import heapq
import logging
from collections import deque
from dataclasses import dataclass
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.graph import build_graph
from scripts.h1_vol import volume_heuristic_cost

logger = logging.getLogger(__name__)

NodeId = Tuple[str, str]


@dataclass(frozen=True)
class SearchState:
    node: NodeId
    depth: int
    elapsed_sec: float


@dataclass
class PlanResult:
    path: List[NodeId]
    edges: List[Dict[str, Any]]
    final_cash_usd: float
    profit_usd: float


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


def _final_cash_from_log_cost(initial_cash_usd: float, total_log_cost: float) -> float:
    """Convert log-space cost to final cash amount."""
    return initial_cash_usd * exp(-total_log_cost)


def dijkstra_like_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 4,  # Reduced from 6 to 4 for faster execution
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    A* search with h(n)=0 (Dijkstra-like, no heuristic guidance).
    
    This baseline uses only the actual path cost (g-score) without any
    heuristic guidance, exploring paths in order of accumulated cost.
    """
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    
    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")
    
    start_state = SearchState(node=start_node, depth=0, elapsed_sec=0.0)
    start_g = 0.0
    start_h = 0.0  # No heuristic
    start_f = start_g + start_h
    
    logger.info("Dijkstra-like search starting (h(n)=0)")
    logger.info(f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}")
    
    frontier: List[Tuple[float, float, int, SearchState, List[NodeId], List[Dict[str, Any]]]] = []
    counter = 0
    heapq.heappush(frontier, (start_f, start_g, counter, start_state, [start_node], []))
    counter += 1
    
    best_g_seen: Dict[Tuple[NodeId, int], float] = {(start_node, 0): start_g}
    best_result: Optional[PlanResult] = None
    
    while frontier:
        f_score, g_score, _, state, path_nodes, path_edges = heapq.heappop(frontier)
        current_node = state.node
        current_cash = _final_cash_from_log_cost(liquid_cash_usd, g_score)
        
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
        
        if state.depth >= max_depth or state.elapsed_sec >= max_time_sec:
            continue
        
        for edge in adj.get(current_node, []):
            to_node: NodeId = edge["to"]
            dt = float(edge.get("transfer_time_sec", 0.0))
            new_elapsed = state.elapsed_sec + dt
            if new_elapsed > max_time_sec:
                continue
            
            edge_cost = float(edge.get("cost", 0.0))
            new_g = g_score + edge_cost
            new_depth = state.depth + 1
            new_state = SearchState(node=to_node, depth=new_depth, elapsed_sec=new_elapsed)
            
            key = (to_node, new_depth)
            if key in best_g_seen and new_g >= best_g_seen[key]:
                continue
            best_g_seen[key] = new_g
            
            # h(n) = 0 for Dijkstra-like
            h = 0.0
            f = new_g + h
            
            new_path_nodes = path_nodes + [to_node]
            new_path_edges = path_edges + [edge]
            
            heapq.heappush(
                frontier,
                (f, new_g, counter, new_state, new_path_nodes, new_path_edges),
            )
            counter += 1
    
    if best_result is None:
        logger.info("Dijkstra-like search: No profitable path found")
        return None
    
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
        f"Dijkstra-like search completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}{cost_info}"
    )
    return best_result


def greedy_best_first_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 4,  # Reduced from 6 to 4 for faster execution
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
    heuristic: str = "h1_liquidity",
) -> Optional[PlanResult]:
    """
    Greedy Best-First Search: uses only heuristic, ignores path cost.
    
    This baseline prioritizes nodes with the lowest heuristic value,
    completely ignoring the actual path cost (g-score).
    """
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    
    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")
    
    start_state = SearchState(node=start_node, depth=0, elapsed_sec=0.0)
    
    logger.info(f"Greedy Best-First search starting with heuristic: {heuristic}")
    logger.info(f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}")
    
    # Compute initial heuristic
    if heuristic == "h1_liquidity":
        start_h = volume_heuristic_cost(
            exchange_name=start_node[0],
            coin=start_node[1],
            order_notional_usd=liquid_cash_usd,
            remaining_time_sec=max_time_sec,
        )
    else:
        raise ValueError(f"Unknown heuristic: {heuristic}")
    
    # Use only heuristic (h) for priority, ignore g
    frontier: List[Tuple[float, float, int, SearchState, List[NodeId], List[Dict[str, Any]]]] = []
    counter = 0
    heapq.heappush(frontier, (start_h, 0.0, counter, start_state, [start_node], []))
    counter += 1
    
    visited: Dict[Tuple[NodeId, int], float] = {(start_node, 0): 0.0}
    best_result: Optional[PlanResult] = None
    
    while frontier:
        h_score, g_score, _, state, path_nodes, path_edges = heapq.heappop(frontier)
        current_node = state.node
        current_cash = _final_cash_from_log_cost(liquid_cash_usd, g_score)
        
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
        
        if state.depth >= max_depth or state.elapsed_sec >= max_time_sec:
            continue
        
        for edge in adj.get(current_node, []):
            to_node: NodeId = edge["to"]
            dt = float(edge.get("transfer_time_sec", 0.0))
            new_elapsed = state.elapsed_sec + dt
            if new_elapsed > max_time_sec:
                continue
            
            edge_cost = float(edge.get("cost", 0.0))
            new_g = g_score + edge_cost
            new_depth = state.depth + 1
            new_state = SearchState(node=to_node, depth=new_depth, elapsed_sec=new_elapsed)
            
            key = (to_node, new_depth)
            if key in visited:
                continue  # Greedy: don't revisit
            visited[key] = new_g
            
            # Compute heuristic at neighbor
            remaining_time = max_time_sec - new_elapsed
            new_cash = _final_cash_from_log_cost(liquid_cash_usd, new_g)
            
            if heuristic == "h1_liquidity":
                h = volume_heuristic_cost(
                    exchange_name=to_node[0],
                    coin=to_node[1],
                    order_notional_usd=new_cash,
                    remaining_time_sec=remaining_time,
                )
            else:
                raise ValueError(f"Unknown heuristic: {heuristic}")
            
            # Use only h for priority (greedy)
            new_path_nodes = path_nodes + [to_node]
            new_path_edges = path_edges + [edge]
            
            heapq.heappush(
                frontier,
                (h, new_g, counter, new_state, new_path_nodes, new_path_edges),
            )
            counter += 1
    
    if best_result is None:
        logger.info("Greedy Best-First search: No profitable path found")
        return None
    
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
        f"Greedy Best-First search completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}{cost_info}"
    )
    return best_result


def breadth_first_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 4,  # Reduced from 6 to 4 for faster execution
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    Breadth-First Search: explores all paths up to depth limit.
    
    This baseline explores nodes level by level, finding the first
    profitable path at the shallowest depth.
    """
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    
    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")
    
    logger.info("Breadth-First search starting")
    logger.info(f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}")
    
    start_state = SearchState(node=start_node, depth=0, elapsed_sec=0.0)
    queue: deque = deque([(0.0, start_state, [start_node], [])])
    visited: Dict[Tuple[NodeId, int], float] = {(start_node, 0): 0.0}
    best_result: Optional[PlanResult] = None
    
    while queue:
        g_score, state, path_nodes, path_edges = queue.popleft()
        current_node = state.node
        current_cash = _final_cash_from_log_cost(liquid_cash_usd, g_score)
        
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
        
        if state.depth >= max_depth or state.elapsed_sec >= max_time_sec:
            continue
        
        for edge in adj.get(current_node, []):
            to_node: NodeId = edge["to"]
            dt = float(edge.get("transfer_time_sec", 0.0))
            new_elapsed = state.elapsed_sec + dt
            if new_elapsed > max_time_sec:
                continue
            
            edge_cost = float(edge.get("cost", 0.0))
            new_g = g_score + edge_cost
            new_depth = state.depth + 1
            new_state = SearchState(node=to_node, depth=new_depth, elapsed_sec=new_elapsed)
            
            key = (to_node, new_depth)
            if key in visited:
                continue
            visited[key] = new_g
            
            new_path_nodes = path_nodes + [to_node]
            new_path_edges = path_edges + [edge]
            
            queue.append((new_g, new_state, new_path_nodes, new_path_edges))
    
    if best_result is None:
        logger.info("Breadth-First search: No profitable path found")
        return None
    
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
        f"Breadth-First search completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}{cost_info}"
    )
    return best_result


def simple_1hop_arbitrage(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    Simple 1-hop baseline: Direct transfer cycle between two exchanges for the same coin.
    
    This represents the naive strategy of finding the best direct price difference
    between two exchanges by transferring from exchange A to exchange B and back.
    
    Algorithm:
    1. For each exchange pair that supports the same coin as start_node
    2. Find transfer edge A→B (same coin)
    3. Find transfer edge B→A (same coin)
    4. Calculate total cost and return most profitable cycle
    """
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    
    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")
    
    start_exchange, start_coin = start_node
    
    logger.info("Simple 1-hop arbitrage starting")
    logger.info(f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}")
    
    best_result: Optional[PlanResult] = None
    
    # Find all exchanges that support the same coin
    exchanges_with_coin = [
        (ex, coin) for (ex, coin) in nodes.keys()
        if coin == start_coin and ex != start_exchange
    ]
    
    # Try each exchange pair
    for target_exchange, _ in exchanges_with_coin:
        target_node: NodeId = (target_exchange, start_coin)
        
        # Find transfer edge from start to target
        transfer_out_edge = None
        for edge in adj.get(start_node, []):
            if (edge.get("kind") == "transfer" and 
                edge["to"] == target_node and
                edge.get("coin") == start_coin):
                transfer_out_edge = edge
                break
        
        if transfer_out_edge is None:
            continue
        
        # Find transfer edge from target back to start
        transfer_back_edge = None
        for edge in adj.get(target_node, []):
            if (edge.get("kind") == "transfer" and
                edge["to"] == start_node and
                edge.get("coin") == start_coin):
                transfer_back_edge = edge
                break
        
        if transfer_back_edge is None:
            continue
        
        # Calculate total cost
        total_cost = transfer_out_edge["cost"] + transfer_back_edge["cost"]
        total_time = (transfer_out_edge.get("transfer_time_sec", 0.0) + 
                     transfer_back_edge.get("transfer_time_sec", 0.0))
        
        if total_time > max_time_sec:
            continue
        
        final_cash = _final_cash_from_log_cost(liquid_cash_usd, total_cost)
        profit = final_cash - liquid_cash_usd
        
        if final_cash > liquid_cash_usd and profit >= min_profit_usd:
            if best_result is None or final_cash > best_result.final_cash_usd:
                best_result = PlanResult(
                    path=[start_node, target_node, start_node],
                    edges=[transfer_out_edge, transfer_back_edge],
                    final_cash_usd=final_cash,
                    profit_usd=profit,
                )
    
    if best_result is None:
        logger.info("Simple 1-hop arbitrage: No profitable path found")
        return None
    
    logger.info(
        f"Simple 1-hop arbitrage completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}"
    )
    return best_result


def simple_2hop_arbitrage(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    Simple 2-hop baseline: Transfer A→B, trade on B, transfer back to A.
    
    This represents a naive 2-exchange arbitrage strategy:
    1. Transfer from exchange A to exchange B (same coin)
    2. Trade to a different coin on exchange B
    3. Transfer back to exchange A (with the new coin, if supported)
    
    If exchange A doesn't support the new coin, we trade back to original coin
    on exchange B before transferring (making it effectively 3 hops, but still
    a simple strategy).
    """
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    
    if start_node not in nodes:
        raise ValueError(f"Start node {start_node} not present in graph.")
    
    start_exchange, start_coin = start_node
    
    logger.info("Simple 2-hop arbitrage starting")
    logger.info(f"Start node: {start_node}, liquid_cash: ${liquid_cash_usd:.2f}")
    
    best_result: Optional[PlanResult] = None
    
    # Find all exchanges that support the same coin
    exchanges_with_coin = [
        (ex, coin) for (ex, coin) in nodes.keys()
        if coin == start_coin and ex != start_exchange
    ]
    
    # Try each target exchange
    for target_exchange, _ in exchanges_with_coin:
        target_node: NodeId = (target_exchange, start_coin)
        
        # Find transfer edge from start to target
        transfer_out_edge = None
        for edge in adj.get(start_node, []):
            if (edge.get("kind") == "transfer" and 
                edge["to"] == target_node and
                edge.get("coin") == start_coin):
                transfer_out_edge = edge
                break
        
        if transfer_out_edge is None:
            continue
        
        # Find all coins available on target exchange
        coins_on_target = [
            coin for (ex, coin) in nodes.keys()
            if ex == target_exchange and coin != start_coin
        ]
        
        # Try each coin on target exchange
        for target_coin in coins_on_target:
            target_coin_node: NodeId = (target_exchange, target_coin)
            
            # Find trade edge on target exchange (start_coin -> target_coin)
            trade_edge = None
            for edge in adj.get(target_node, []):
                if (edge.get("kind") == "trade" and
                    edge["to"] == target_coin_node and
                    edge.get("exchange") == target_exchange):
                    trade_edge = edge
                    break
            
            if trade_edge is None:
                continue
            
            # Calculate cost so far
            cost_so_far = transfer_out_edge["cost"] + trade_edge["cost"]
            time_so_far = (transfer_out_edge.get("transfer_time_sec", 0.0) +
                          trade_edge.get("transfer_time_sec", 0.0))
            
            # Try to transfer back to start exchange with target_coin
            final_node_with_new_coin: NodeId = (start_exchange, target_coin)
            transfer_back_edge = None
            
            if final_node_with_new_coin in nodes:
                # Start exchange supports the new coin - direct transfer back
                for edge in adj.get(target_coin_node, []):
                    if (edge.get("kind") == "transfer" and
                        edge["to"] == final_node_with_new_coin and
                        edge.get("coin") == target_coin):
                        transfer_back_edge = edge
                        break
                
                if transfer_back_edge:
                    total_cost = cost_so_far + transfer_back_edge["cost"]
                    total_time = time_so_far + transfer_back_edge.get("transfer_time_sec", 0.0)
                    
                    if total_time <= max_time_sec:
                        final_cash = _final_cash_from_log_cost(liquid_cash_usd, total_cost)
                        profit = final_cash - liquid_cash_usd
                        
                        if final_cash > liquid_cash_usd and profit >= min_profit_usd:
                            if best_result is None or final_cash > best_result.final_cash_usd:
                                best_result = PlanResult(
                                    path=[start_node, target_node, target_coin_node, final_node_with_new_coin],
                                    edges=[transfer_out_edge, trade_edge, transfer_back_edge],
                                    final_cash_usd=final_cash,
                                    profit_usd=profit,
                                )
            
            # If direct transfer back not possible, trade back to start_coin then transfer
            if transfer_back_edge is None:
                # Find trade edge back to start_coin on target exchange
                trade_back_edge = None
                for edge in adj.get(target_coin_node, []):
                    if (edge.get("kind") == "trade" and
                        edge["to"] == target_node and
                        edge.get("exchange") == target_exchange):
                        trade_back_edge = edge
                        break
                
                if trade_back_edge is None:
                    continue
                
                # Find transfer back to start with original coin
                transfer_back_original = None
                for edge in adj.get(target_node, []):
                    if (edge.get("kind") == "transfer" and
                        edge["to"] == start_node and
                        edge.get("coin") == start_coin):
                        transfer_back_original = edge
                        break
                
                if transfer_back_original is None:
                    continue
                
                total_cost = cost_so_far + trade_back_edge["cost"] + transfer_back_original["cost"]
                total_time = (time_so_far + 
                            trade_back_edge.get("transfer_time_sec", 0.0) +
                            transfer_back_original.get("transfer_time_sec", 0.0))
                
                if total_time <= max_time_sec:
                    final_cash = _final_cash_from_log_cost(liquid_cash_usd, total_cost)
                    profit = final_cash - liquid_cash_usd
                    
                    if final_cash > liquid_cash_usd and profit >= min_profit_usd:
                        if best_result is None or final_cash > best_result.final_cash_usd:
                            best_result = PlanResult(
                                path=[start_node, target_node, target_coin_node, target_node, start_node],
                                edges=[transfer_out_edge, trade_edge, trade_back_edge, transfer_back_original],
                                final_cash_usd=final_cash,
                                profit_usd=profit,
                            )
    
    if best_result is None:
        logger.info("Simple 2-hop arbitrage: No profitable path found")
        return None
    
    logger.info(
        f"Simple 2-hop arbitrage completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}"
    )
    return best_result


def two_hop_max_depth_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    2-hop max depth baseline: A* with h(n)=0 and max_depth=2.
    
    This represents a restricted search that:
    1. Starts at a node (exchange, coin)
    2. Can jump to any other node within the same exchange (trade edge)
    3. From there can jump to any exchange with the same coin (transfer edge)
    4. That's it (max depth = 2)
    
    This is essentially Dijkstra's algorithm (h=0) with a strict 2-hop limit.
    """
    return dijkstra_like_search(
        start_node=start_node,
        liquid_cash_usd=liquid_cash_usd,
        max_depth=2,  # Strict 2-hop limit
        max_time_sec=max_time_sec,
        min_profit_usd=min_profit_usd,
    )



