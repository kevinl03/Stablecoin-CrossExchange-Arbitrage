"""Weighted A* (WA*) search algorithm for faster arbitrage path finding."""

import heapq
from typing import List, Optional, Tuple, Set
from ..models.exchange_node import ExchangeNode
from ..models.edge import Edge
from .astar import volatility_heuristic


def weighted_astar_arbitrage(
    start_node: ExchangeNode,
    max_depth: int = 10,
    volatility_factor: float = 0.1,
    weight: float = 1.5
) -> List[Tuple[List[ExchangeNode], float, float]]:
    """
    Find arbitrage opportunities using Weighted A* search.
    
    Weighted A* uses f(n) = g(n) + w × h(n) where w > 1.
    This trades slight suboptimality for significant speedup.
    
    Args:
        start_node: Starting node for the search
        max_depth: Maximum path length to explore
        volatility_factor: Factor for volatility risk in heuristic
        weight: Weight factor for heuristic (w > 1 for WA*, w=1 for standard A*)
        
    Returns:
        List of tuples (path, net_profit, total_cost) for profitable arbitrage cycles
    """
    # Priority queue: (f_cost, total_cost, current_node, path, depth)
    # f_cost = total_cost + weight * heuristic
    frontier = [(0, 0, start_node, [start_node], 0)]
    visited: Set[Tuple[ExchangeNode, int]] = set()
    opportunities: List[Tuple[List[ExchangeNode], float, float]] = []
    
    while frontier:
        f_cost, total_cost, current, path, depth = heapq.heappop(frontier)
        
        # Skip if we've visited this node at this depth
        state = (current, depth)
        if state in visited:
            continue
        
        visited.add(state)
        
        # Check if we've found a cycle back to start
        if len(path) > 1 and current == start_node:
            # Calculate net profit
            initial_price = start_node.price
            net_profit = initial_price - (initial_price * (1 + total_cost))
            
            if net_profit > 0:
                opportunities.append((path.copy(), net_profit, total_cost))
            continue
        
        # Limit depth
        if depth >= max_depth:
            continue
        
        # Explore neighbors
        for edge in current.edges:
            neighbor = edge.target
            new_cost = total_cost + edge.weight
            new_path = path + [neighbor]
            new_depth = depth + 1
            
            # Calculate heuristic
            heuristic = volatility_heuristic(current, neighbor, edge, volatility_factor)
            # Weighted A*: multiply heuristic by weight
            f_new = new_cost + weight * heuristic
            
            # Check for arbitrage opportunity
            price_diff = current.price - neighbor.price
            if price_diff > edge.weight:
                heapq.heappush(
                    frontier,
                    (f_new, new_cost, neighbor, new_path, new_depth)
                )
    
    # Sort by net profit (descending)
    opportunities.sort(key=lambda x: x[1], reverse=True)
    return opportunities


def find_optimal_path_weighted_astar(
    start_node: ExchangeNode,
    target_node: ExchangeNode,
    max_depth: int = 10,
    volatility_factor: float = 0.1,
    weight: float = 1.5
) -> Optional[Tuple[List[ExchangeNode], float]]:
    """
    Find optimal path from start to target using Weighted A*.
    
    Args:
        start_node: Starting node
        target_node: Target node
        max_depth: Maximum path length
        volatility_factor: Volatility risk factor
        weight: Weight factor for heuristic
        
    Returns:
        Tuple of (path, total_cost) or None if no path exists
    """
    frontier = [(0, 0, start_node, [start_node], 0)]
    visited: Set[Tuple[ExchangeNode, int]] = set()
    
    while frontier:
        f_cost, total_cost, current, path, depth = heapq.heappop(frontier)
        
        if current == target_node and len(path) > 1:
            return (path, total_cost)
        
        state = (current, depth)
        if state in visited:
            continue
        
        visited.add(state)
        
        if depth >= max_depth:
            continue
        
        for edge in current.edges:
            neighbor = edge.target
            new_cost = total_cost + edge.weight
            new_path = path + [neighbor]
            new_depth = depth + 1
            
            # Heuristic: estimate cost to target
            heuristic = volatility_heuristic(current, target_node, edge, volatility_factor)
            f_new = new_cost + weight * heuristic
            
            heapq.heappush(
                frontier,
                (f_new, new_cost, neighbor, new_path, new_depth)
            )
    
    return None

