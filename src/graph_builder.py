"""Graph builder for constructing arbitrage graphs from exchange data."""

from typing import List, Dict, Optional
from .models.graph import ArbitrageGraph
from .connectors.base_connector import BaseExchangeConnector


class GraphBuilder:
    """Builder for constructing arbitrage graphs from exchange connectors."""
    
    def __init__(self):
        """Initialize the graph builder."""
        self.graph = ArbitrageGraph()
        self.connectors: List[BaseExchangeConnector] = []
    
    def add_connector(self, connector: BaseExchangeConnector):
        """Add an exchange connector."""
        self.connectors.append(connector)
    
    def build_graph(
        self,
        default_fee: float = 0.002,
        default_volatility: float = 0.001,
        default_transfer_time: float = 60.0
    ) -> ArbitrageGraph:
        """
        Build the arbitrage graph from all connectors.
        
        Args:
            default_fee: Default transfer fee if not available from connector
            default_volatility: Default volatility cost
            default_transfer_time: Default transfer time in seconds
            
        Returns:
            Constructed ArbitrageGraph
        """
        self.graph = ArbitrageGraph()
        
        # Step 1: Add all nodes (exchange, stablecoin pairs)
        all_stablecoins = set()
        for connector in self.connectors:
            prices = connector.get_all_stablecoin_prices()
            for stablecoin, price in prices.items():
                self.graph.add_node(connector.exchange_name, stablecoin, price)
                all_stablecoins.add(stablecoin)
        
        # Step 2: Add edges between all nodes
        nodes = self.graph.get_all_nodes()
        for source_node in nodes:
            for target_node in nodes:
                if source_node == target_node:
                    continue
                
                # Get connector for source exchange
                source_connector = next(
                    (c for c in self.connectors if c.exchange_name == source_node.exchange),
                    None
                )
                
                if source_connector:
                    fee = source_connector.get_transfer_fee(
                        source_node.stablecoin,
                        target_node.stablecoin
                    )
                    transfer_time = source_connector.get_estimated_transfer_time(
                        source_node.stablecoin,
                        target_node.stablecoin
                    )
                else:
                    fee = default_fee
                    transfer_time = default_transfer_time
                
                # Calculate volatility cost based on price difference
                price_diff = abs(source_node.price - target_node.price)
                volatility_cost = price_diff * default_volatility
                
                self.graph.add_edge(
                    source_node.exchange,
                    source_node.stablecoin,
                    target_node.exchange,
                    target_node.stablecoin,
                    fee,
                    volatility_cost,
                    transfer_time
                )
        
        return self.graph
    
    def update_graph_from_connectors(self) -> ArbitrageGraph:
        """
        Update graph prices from all connectors.
        
        Returns:
            Updated ArbitrageGraph
        """
        price_updates = {}
        
        for connector in self.connectors:
            prices = connector.get_all_stablecoin_prices()
            for stablecoin, price in prices.items():
                key = (connector.exchange_name, stablecoin)
                price_updates[key] = price
        
        self.graph.update_prices(price_updates)
        return self.graph
    
    def get_graph(self) -> ArbitrageGraph:
        """Get the current graph."""
        return self.graph

