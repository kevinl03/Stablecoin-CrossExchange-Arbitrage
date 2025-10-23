"""ArbitrageGraph represents the complete arbitrage environment as a directed weighted graph."""

from typing import Dict, List, Set, Optional, Tuple
from .exchange_node import ExchangeNode
from .edge import Edge


class ArbitrageGraph:
    """A directed weighted graph modeling the multi-exchange stablecoin arbitrage environment."""
    
    def __init__(self):
        """Initialize an empty arbitrage graph."""
        self.nodes: Dict[Tuple[str, str], ExchangeNode] = {}
        self.edges: List[Edge] = []
    
    def add_node(self, exchange: str, stablecoin: str, price: float) -> ExchangeNode:
        """
        Add a node to the graph.
        
        Args:
            exchange: Name of the exchange
            stablecoin: Name of the stablecoin
            price: Current price in reference fiat currency
            
        Returns:
            The created or existing ExchangeNode
        """
        key = (exchange, stablecoin)
        if key not in self.nodes:
            node = ExchangeNode(exchange, stablecoin, price)
            self.nodes[key] = node
        else:
            # Update price if node exists
            self.nodes[key].price = price
        return self.nodes[key]
    
    def add_edge(
        self,
        source_exchange: str,
        source_stablecoin: str,
        target_exchange: str,
        target_stablecoin: str,
        fee: float,
        volatility_cost: float = 0.0,
        transfer_time: float = 0.0
    ) -> Edge:
        """
        Add an edge to the graph.
        
        Args:
            source_exchange: Source exchange name
            source_stablecoin: Source stablecoin name
            target_exchange: Target exchange name
            target_stablecoin: Target stablecoin name
            fee: Transaction fees
            volatility_cost: Volatility risk cost
            transfer_time: Transfer time in seconds
            
        Returns:
            The created Edge
        """
        source_key = (source_exchange, source_stablecoin)
        target_key = (target_exchange, target_stablecoin)
        
        if source_key not in self.nodes or target_key not in self.nodes:
            raise ValueError(f"Source or target node does not exist")
        
        source_node = self.nodes[source_key]
        target_node = self.nodes[target_key]
        
        edge = Edge(source_node, target_node, fee, volatility_cost, transfer_time)
        source_node.add_edge(edge)
        self.edges.append(edge)
        return edge
    
    def get_node(self, exchange: str, stablecoin: str) -> Optional[ExchangeNode]:
        """Get a node by exchange and stablecoin."""
        return self.nodes.get((exchange, stablecoin))
    
    def get_all_nodes(self) -> List[ExchangeNode]:
        """Get all nodes in the graph."""
        return list(self.nodes.values())
    
    def update_prices(self, price_updates: Dict[Tuple[str, str], float]):
        """
        Update prices for multiple nodes.
        
        Args:
            price_updates: Dictionary mapping (exchange, stablecoin) to new price
        """
        for key, price in price_updates.items():
            if key in self.nodes:
                self.nodes[key].price = price
    
    def __repr__(self):
        """String representation."""
        return f"ArbitrageGraph({len(self.nodes)} nodes, {len(self.edges)} edges)"

