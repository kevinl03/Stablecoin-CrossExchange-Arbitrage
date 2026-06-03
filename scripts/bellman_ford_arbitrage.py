"""
Bellman-Ford algorithm for detecting negative-weight cycles (arbitrage opportunities).

This implementation follows the methodology from:
Oantă, R. and Coroiu, A. (2023). "Crypto Advisor: A Web Application for Spotting 
Cross-Exchange Cryptocurrency Arbitrage Opportunities." CSEDU 2023.

The algorithm detects negative cycles in the log-transformed graph, where:
- Edge weights are already in log-space: cost = -log(rate)
- A negative cycle (sum of costs < 0) corresponds to profitable arbitrage
- Unlike A* which finds paths from a start node, Bellman-Ford finds any negative cycle
"""

from __future__ import annotations

import logging
from collections import defaultdict
from dataclasses import dataclass
from math import exp
from typing import Any, Dict, List, Optional, Tuple

from scripts.graph import build_graph, Adjacency, NodeId

logger = logging.getLogger(__name__)


@dataclass
class PlanResult:
    path: List[NodeId]
    edges: List[Dict[str, Any]]
    final_cash_usd: float
    profit_usd: float


def _final_cash_from_log_cost(initial_cash_usd: float, total_log_cost: float) -> float:
    """Convert log-space cost to final cash amount."""
    return initial_cash_usd * exp(-total_log_cost)


def detect_negative_cycles(
    nodes: Dict[NodeId, Dict[str, Any]],
    adj: Adjacency,
) -> List[List[NodeId]]:
    """
    Detect negative-weight cycles in the graph using Bellman-Ford algorithm.
    
    The graph edges already have costs in log-space (cost = -log(rate)).
    A negative cycle means sum of costs < 0, which corresponds to profitable arbitrage.
    
    Args:
        nodes: Dictionary of node metadata
        adj: Adjacency list mapping node -> list of edge dicts
        
    Returns:
        List of cycles, where each cycle is a list of nodes forming a negative cycle.
        Returns empty list if no negative cycles are found.
    """
    if not nodes:
        return []
    
    # Initialize distance and predecessor arrays
    # Use a dummy source node that connects to all nodes with 0 cost
    all_nodes = list(nodes.keys())
    n = len(all_nodes)
    
    # Distance from source (we'll use 0 for all nodes initially)
    dist: Dict[NodeId, float] = {node: 0.0 for node in all_nodes}
    pred: Dict[NodeId, Optional[NodeId]] = {node: None for node in all_nodes}
    
    # Relax edges |V| - 1 times
    for _ in range(n - 1):
        relaxed = False
        for u in all_nodes:
            if u not in adj:
                continue
            for edge in adj[u]:
                v = edge["to"]
                cost = float(edge.get("cost", 0.0))
                
                # Relax edge if we can improve distance
                if dist[u] + cost < dist[v]:
                    dist[v] = dist[u] + cost
                    pred[v] = u
                    relaxed = True
        
        # Early termination if no relaxation occurred
        if not relaxed:
            break
    
    # Check for negative cycles
    # If we can still relax an edge after |V|-1 iterations, there's a negative cycle
    negative_cycles: List[List[NodeId]] = []
    visited_cycles: set = set()
    
    for u in all_nodes:
        if u not in adj:
            continue
        for edge in adj[u]:
            v = edge["to"]
            cost = float(edge.get("cost", 0.0))
            
            # If we can still relax, there's a negative cycle
            if dist[u] + cost < dist[v]:
                # Trace back to find the cycle
                # Use 2*n steps: predecessor chains in cycles can revisit nodes,
                # and n steps is insufficient for Hamiltonian cycles (cycle len == n)
                cycle = _extract_cycle(v, pred, 2 * n)
                if cycle and tuple(cycle) not in visited_cycles:
                    visited_cycles.add(tuple(cycle))
                    negative_cycles.append(cycle)
    
    return negative_cycles


def _extract_cycle(
    start_node: NodeId,
    pred: Dict[NodeId, Optional[NodeId]],
    max_steps: int,
) -> Optional[List[NodeId]]:
    """
    Extract a cycle starting from start_node by following predecessors.
    
    Args:
        start_node: Node to start tracing from
        pred: Predecessor dictionary
        max_steps: Maximum steps to trace (to avoid infinite loops)
        
    Returns:
        List of nodes forming a cycle, or None if no cycle found
    """
    visited: Dict[NodeId, int] = {}
    path: List[NodeId] = []
    current = start_node
    
    for step in range(max_steps):
        if current is None:
            break
        
        if current in visited:
            # Found a cycle - extract it
            cycle_start_idx = visited[current]
            cycle = path[cycle_start_idx:] + [current]
            return cycle
        
        visited[current] = len(path)
        path.append(current)
        current = pred.get(current)
    
    return None


def bellman_ford_arbitrage(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
) -> Optional[PlanResult]:
    """
    Find arbitrage opportunities using Bellman-Ford negative cycle detection.
    
    This follows the methodology from Oantă & Coroiu (2023), which detects
    negative cycles in the log-transformed graph. Unlike A* which finds paths
    from a start node, this finds any profitable cycle in the graph.
    
    Note: This is a theoretical baseline that assumes:
    - Perfect liquidity (any trade size executes at quoted rate)
    - Instant execution (no transfer delays)
    - Static prices during execution
    
    Args:
        start_node: Starting node (used for consistency with other algorithms,
                   but Bellman-Ford finds cycles regardless of start)
        liquid_cash_usd: Initial cash amount
        max_time_sec: Maximum time budget (not used in Bellman-Ford, but kept
                     for interface consistency)
        min_profit_usd: Minimum profit threshold
        
    Returns:
        PlanResult with the most profitable cycle found, or None if no profitable
        cycles exist.
    """
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    
    if not nodes:
        logger.warning("Bellman-Ford: No nodes in graph")
        return None
    
    logger.info("Bellman-Ford arbitrage detection starting")
    logger.info(f"Graph has {len(nodes)} nodes")
    
    # Detect all negative cycles
    cycles = detect_negative_cycles(nodes, adj)
    
    if not cycles:
        logger.info("Bellman-Ford: No negative cycles (arbitrage opportunities) found")
        return None
    
    logger.info(f"Bellman-Ford: Found {len(cycles)} negative cycle(s)")
    
    # Find the most profitable cycle
    best_result: Optional[PlanResult] = None
    
    for cycle in cycles:
        # Close the cycle (add first node at end)
        if len(cycle) < 2:
            continue
        
        closed_cycle = cycle + [cycle[0]]
        
        # Build path and calculate total cost
        path_nodes: List[NodeId] = []
        path_edges: List[Dict[str, Any]] = []
        total_cost = 0.0
        total_time = 0.0
        
        for i in range(len(closed_cycle) - 1):
            u = closed_cycle[i]
            v = closed_cycle[i + 1]
            
            path_nodes.append(u)
            
            # Find edge from u to v
            edge_found = False
            if u in adj:
                for edge in adj[u]:
                    if edge["to"] == v:
                        path_edges.append(edge)
                        total_cost += float(edge.get("cost", 0.0))
                        total_time += float(edge.get("transfer_time_sec", 0.0))
                        edge_found = True
                        break
            
            if not edge_found:
                logger.warning(f"Bellman-Ford: Could not find edge from {u} to {v}")
                break
        
        if len(path_edges) != len(closed_cycle) - 1:
            continue
        
        # Check time constraint
        if total_time > max_time_sec:
            continue
        
        # Calculate profit
        final_cash = _final_cash_from_log_cost(liquid_cash_usd, total_cost)
        profit = final_cash - liquid_cash_usd
        
        if profit >= min_profit_usd:
            if best_result is None or profit > best_result.profit_usd:
                best_result = PlanResult(
                    path=path_nodes,
                    edges=path_edges,
                    final_cash_usd=final_cash,
                    profit_usd=profit,
                )
    
    if best_result is None:
        logger.info("Bellman-Ford: No profitable cycles found (after time/profit filtering)")
        return None
    
    logger.info(
        f"Bellman-Ford completed: "
        f"Final profit=${best_result.profit_usd:.2f}, "
        f"path_length={len(best_result.path)}"
    )
    return best_result


if __name__ == "__main__":
    # Test the implementation
    import sys
    
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) < 3:
        print("Usage: python bellman_ford_arbitrage.py <exchange> <coin>")
        print("Example: python bellman_ford_arbitrage.py binance USDT")
        sys.exit(1)
    
    exchange = sys.argv[1]
    coin = sys.argv[2]
    start_node: NodeId = (exchange, coin)
    
    result = bellman_ford_arbitrage(
        start_node=start_node,
        liquid_cash_usd=10000.0,
        max_time_sec=1800.0,
        min_profit_usd=0.0,
    )
    
    if result:
        print(f"\nFound arbitrage opportunity:")
        print(f"  Profit: ${result.profit_usd:.2f}")
        print(f"  Final cash: ${result.final_cash_usd:.2f}")
        print(f"  Path length: {len(result.path)}")
        print(f"  Path: {' -> '.join([f'{n[0]}:{n[1]}' for n in result.path])}")
    else:
        print("\nNo arbitrage opportunity found")

