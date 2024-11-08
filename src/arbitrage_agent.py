"""ArbitrageAgent: Main agent class for detecting and evaluating arbitrage opportunities."""

from typing import List, Tuple, Optional, Dict
from .models.graph import ArbitrageGraph
from .models.exchange_node import ExchangeNode
from .algorithms.dijkstra import dijkstra_arbitrage
from .algorithms.astar import astar_arbitrage
from .algorithms.two_level_search import two_level_search


class ArbitrageAgent:
    """Main agent for detecting and evaluating stablecoin arbitrage opportunities."""
    
    def __init__(self, graph: ArbitrageGraph):
        """
        Initialize the arbitrage agent.
        
        Args:
            graph: The arbitrage graph to work with
        """
        self.graph = graph
    
    def find_arbitrage_paths(
        self,
        start_node: ExchangeNode,
        algorithm: str = 'astar',
        max_depth: int = 10,
        volatility_factor: float = 0.1
    ) -> List[Tuple[List[ExchangeNode], float, float]]:
        """
        Find arbitrage paths from a starting node.
        
        Args:
            start_node: Starting node
            algorithm: Algorithm to use ('dijkstra' or 'astar')
            max_depth: Maximum path depth
            volatility_factor: Volatility factor for A* heuristic
            
        Returns:
            List of tuples (path, net_profit, total_cost)
        """
        if algorithm == 'astar':
            return astar_arbitrage(
                start_node,
                max_depth=max_depth,
                volatility_factor=volatility_factor
            )
        else:
            return dijkstra_arbitrage(start_node, max_depth=max_depth)
    
    def find_all_opportunities(
        self,
        algorithm: str = 'astar',
        max_depth: int = 10,
        volatility_factor: float = 0.1
    ) -> List[Tuple[List[ExchangeNode], float, float, str]]:
        """
        Find all arbitrage opportunities using two-level search.
        
        Args:
            algorithm: Algorithm to use ('dijkstra' or 'astar')
            max_depth: Maximum path depth
            volatility_factor: Volatility factor for A* heuristic
            
        Returns:
            List of tuples (path, net_profit, total_cost, description)
        """
        return two_level_search(
            self.graph,
            algorithm=algorithm,
            max_depth=max_depth,
            volatility_factor=volatility_factor
        )
    
    def record_opportunity(
        self,
        path: List[ExchangeNode],
        net_profit: float,
        total_cost: float
    ) -> Dict:
        """
        Record an arbitrage opportunity with detailed information.
        
        Args:
            path: Path through the graph
            net_profit: Net profit from the opportunity
            total_cost: Total cost of the path
            
        Returns:
            Dictionary with opportunity details
        """
        if not path:
            return {}
        
        opportunity = {
            'path': path,
            'net_profit': net_profit,
            'total_cost': total_cost,
            'start': f"{path[0].exchange}({path[0].stablecoin})",
            'end': f"{path[-1].exchange}({path[-1].stablecoin})",
            'path_length': len(path),
            'profit_margin': net_profit / path[0].price if path[0].price > 0 else 0
        }
        
        return opportunity
    
    def evaluate_opportunity(
        self,
        path: List[ExchangeNode],
        amount: float = 1.0
    ) -> Dict:
        """
        Evaluate an arbitrage opportunity with a specific amount.
        
        Args:
            path: Path through the graph
            amount: Amount to trade
            
        Returns:
            Dictionary with evaluation details
        """
        if len(path) < 2:
            return {'error': 'Path too short'}
        
        start_price = path[0].price
        end_price = path[-1].price
        
        # Calculate total cost along the path
        total_cost = 0.0
        for i in range(len(path) - 1):
            current = path[i]
            next_node = path[i + 1]
            
            # Find edge between current and next
            for edge in current.edges:
                if edge.target == next_node:
                    total_cost += edge.weight * amount
                    break
        
        # Calculate profit
        price_diff = (start_price - end_price) * amount
        net_profit = price_diff - total_cost
        
        return {
            'amount': amount,
            'start_price': start_price,
            'end_price': end_price,
            'price_difference': price_diff,
            'total_cost': total_cost,
            'net_profit': net_profit,
            'roi': (net_profit / (start_price * amount)) * 100 if start_price * amount > 0 else 0,
            'profitable': net_profit > 0
        }
    
    def update_graph_prices(self, price_updates: Dict[Tuple[str, str], float]):
        """
        Update prices in the graph.
        
        Args:
            price_updates: Dictionary mapping (exchange, stablecoin) to new price
        """
        self.graph.update_prices(price_updates)
    
    def get_statistics(self) -> Dict:
        """
        Get statistics about the current graph state.
        
        Returns:
            Dictionary with graph statistics
        """
        nodes = self.graph.get_all_nodes()
        edges = self.graph.edges
        
        exchanges = set(node.exchange for node in nodes)
        stablecoins = set(node.stablecoin for node in nodes)
        
        return {
            'num_nodes': len(nodes),
            'num_edges': len(edges),
            'num_exchanges': len(exchanges),
            'num_stablecoins': len(stablecoins),
            'exchanges': list(exchanges),
            'stablecoins': list(stablecoins),
            'avg_price': sum(node.price for node in nodes) / len(nodes) if nodes else 0
        }

