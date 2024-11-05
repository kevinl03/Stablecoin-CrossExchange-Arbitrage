"""Two-level search algorithm comparing all stablecoin pairs across all exchanges."""

from typing import List, Tuple, Dict, Set
from ..models.graph import ArbitrageGraph
from ..models.exchange_node import ExchangeNode
from .dijkstra import dijkstra_arbitrage
from .astar import astar_arbitrage


def two_level_search(
    graph: ArbitrageGraph,
    algorithm: str = 'astar',
    max_depth: int = 10,
    volatility_factor: float = 0.1
) -> List[Tuple[List[ExchangeNode], float, float, str]]:
    """
    Perform two-level search: compare all stablecoin pairs across all exchanges.
    
    This algorithm systematically explores:
    - Level 1: All pairs of exchanges
    - Level 2: All pairs of stablecoins
    
    Args:
        graph: The arbitrage graph
        algorithm: Algorithm to use ('dijkstra' or 'astar')
        max_depth: Maximum path depth
        volatility_factor: Volatility factor for A* heuristic
        
    Returns:
        List of tuples (path, net_profit, total_cost, description) for all opportunities
    """
    all_opportunities: List[Tuple[List[ExchangeNode], float, float, str]] = []
    nodes = graph.get_all_nodes()
    
    # Get unique exchanges and stablecoins
    exchanges = set(node.exchange for node in nodes)
    stablecoins = set(node.stablecoin for node in nodes)
    
    # Two-level search: for each exchange pair, for each stablecoin pair
    for exchange1 in exchanges:
        for exchange2 in exchanges:
            if exchange1 == exchange2:
                continue
            
            for stablecoin1 in stablecoins:
                for stablecoin2 in stablecoins:
                    # Find start node
                    start_node = graph.get_node(exchange1, stablecoin1)
                    if not start_node:
                        continue
                    
                    # Find target node
                    target_node = graph.get_node(exchange2, stablecoin2)
                    if not target_node:
                        continue
                    
                    # Search for arbitrage paths
                    if algorithm == 'astar':
                        opportunities = astar_arbitrage(
                            start_node,
                            max_depth=max_depth,
                            volatility_factor=volatility_factor
                        )
                    else:
                        opportunities = dijkstra_arbitrage(
                            start_node,
                            max_depth=max_depth
                        )
                    
                    # Add description and filter for relevant paths
                    for path, profit, cost in opportunities:
                        # Check if path involves the target exchange/stablecoin
                        if any(
                            node.exchange == exchange2 and node.stablecoin == stablecoin2
                            for node in path
                        ):
                            description = (
                                f"{exchange1}({stablecoin1}) -> "
                                f"{exchange2}({stablecoin2})"
                            )
                            all_opportunities.append((path, profit, cost, description))
    
    # Sort by profit (descending)
    all_opportunities.sort(key=lambda x: x[1], reverse=True)
    return all_opportunities


def compare_all_pairs(
    graph: ArbitrageGraph,
    algorithm: str = 'astar'
) -> Dict[Tuple[str, str, str, str], List[Tuple[List[ExchangeNode], float, float]]]:
    """
    Compare all pairs of (exchange, stablecoin) combinations.
    
    Args:
        graph: The arbitrage graph
        algorithm: Algorithm to use
        
    Returns:
        Dictionary mapping (ex1, coin1, ex2, coin2) to list of opportunities
    """
    results: Dict[Tuple[str, str, str, str], List[Tuple[List[ExchangeNode], float, float]]] = {}
    nodes = graph.get_all_nodes()
    
    for i, node1 in enumerate(nodes):
        for node2 in nodes[i+1:]:
            key = (node1.exchange, node1.stablecoin, node2.exchange, node2.stablecoin)
            
            if algorithm == 'astar':
                opportunities = astar_arbitrage(node1, max_depth=5)
            else:
                opportunities = dijkstra_arbitrage(node1, max_depth=5)
            
            # Filter opportunities that involve node2
            relevant = [
                (path, profit, cost)
                for path, profit, cost in opportunities
                if node2 in path
            ]
            
            if relevant:
                results[key] = relevant
    
    return results

