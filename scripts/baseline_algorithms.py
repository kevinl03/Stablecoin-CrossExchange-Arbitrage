"""
Baseline algorithms for arbitrage path search.

These algorithms serve as baselines for comparison against heuristic-guided A* search:
- dijkstra_like: A* with h(n)=0 (no heuristic guidance)
- greedy_best_first: Uses only heuristic, ignores path cost
- breadth_first_search: Explores all paths up to depth limit
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


def _final_cash_from_log_cost(initial_cash_usd: float, total_log_cost: float) -> float:
    """Convert log-space cost to final cash amount."""
    return initial_cash_usd * exp(-total_log_cost)


def dijkstra_like_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    A* search with h(n)=0 (Dijkstra-like, no heuristic guidance).
    
    This baseline uses only the actual path cost (g-score) without any
    heuristic guidance, exploring paths in order of accumulated cost.
    """
    nodes, adj = build_graph()
    
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
    
    logger.info(
        f"Dijkstra-like search completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}"
    )
    return best_result


def greedy_best_first_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
    heuristic: str = "h1_liquidity",
) -> Optional[PlanResult]:
    """
    Greedy Best-First Search: uses only heuristic, ignores path cost.
    
    This baseline prioritizes nodes with the lowest heuristic value,
    completely ignoring the actual path cost (g-score).
    """
    nodes, adj = build_graph()
    
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
    
    logger.info(
        f"Greedy Best-First search completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}"
    )
    return best_result


def breadth_first_search(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    Breadth-First Search: explores all paths up to depth limit.
    
    This baseline explores nodes level by level, finding the first
    profitable path at the shallowest depth.
    """
    nodes, adj = build_graph()
    
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
    
    logger.info(
        f"Breadth-First search completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}"
    )
    return best_result

