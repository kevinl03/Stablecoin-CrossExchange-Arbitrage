"""Dijkstra's algorithm for finding least-cost arbitrage paths."""

import heapq
from typing import Dict, List, Optional, Tuple, Set
from ..models.exchange_node import ExchangeNode
from ..models.edge import Edge


def dijkstra_arbitrage(
    start_node: ExchangeNode,
    max_depth: int = 10
) -> List[Tuple[List[ExchangeNode], float, float]]:
    """
    Find arbitrage opportunities using Dijkstra's algorithm.
    
    Args:
        start_node: Starting node for the search
        max_depth: Maximum path length to explore
        
    Returns:
        List of tuples (path, net_profit, total_cost) for profitable arbitrage cycles
    """
    # Priority queue: (total_cost, current_node, path, depth)
    frontier = [(0, start_node, [start_node], 0)]
    visited: Set[Tuple[ExchangeNode, int]] = set()
    opportunities: List[Tuple[List[ExchangeNode], float, float]] = []
    
    while frontier:
        total_cost, current, path, depth = heapq.heappop(frontier)
        
        # Skip if we've visited this node at this depth
        state = (current, depth)
        if state in visited:
            continue
        
        visited.add(state)
        
        # Check if we've found a cycle back to start
        if len(path) > 1 and current == start_node:
            # Calculate net profit
            initial_price = start_node.price
            final_price = path[-1].price if path else start_node.price
            
            # For a cycle, we need to account for all edge costs
            # Net profit = price difference - total transfer costs
            net_profit = initial_price - (initial_price * (1 + total_cost))
            
            if net_profit > 0:
                opportunities.append((path.copy(), net_profit, total_cost))
            continue
        
        # Limit depth to prevent infinite loops
        if depth >= max_depth:
            continue
        
        # Explore neighbors
        for edge in current.edges:
            neighbor = edge.target
            new_cost = total_cost + edge.weight
            new_path = path + [neighbor]
            new_depth = depth + 1
            
            # Check for arbitrage opportunity
            price_diff = current.price - neighbor.price
            if price_diff > edge.weight:
                # Potential opportunity - continue exploring
                heapq.heappush(
                    frontier,
                    (new_cost, neighbor, new_path, new_depth)
                )
    
    # Sort by net profit (descending)
    opportunities.sort(key=lambda x: x[1], reverse=True)
    return opportunities


def find_shortest_paths(
    start_node: ExchangeNode,
    target_node: ExchangeNode,
    max_depth: int = 10
) -> Optional[Tuple[List[ExchangeNode], float]]:
    """
    Find the shortest path from start to target using Dijkstra's algorithm.
    
    Args:
        start_node: Starting node
        target_node: Target node
        max_depth: Maximum path length
        
    Returns:
        Tuple of (path, total_cost) or None if no path exists
    """
    frontier = [(0, start_node, [start_node], 0)]
    visited: Set[Tuple[ExchangeNode, int]] = set()
    
    while frontier:
        total_cost, current, path, depth = heapq.heappop(frontier)
        
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
            
            heapq.heappush(
                frontier,
                (new_cost, neighbor, new_path, new_depth)
            )
    
    return None

