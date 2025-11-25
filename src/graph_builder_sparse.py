"""Sparse graph builder that only creates feasible edges."""

from typing import List, Dict, Optional, Set
from .models.graph import ArbitrageGraph
from .connectors.base_connector import BaseExchangeConnector


class SparseGraphBuilder:
    """Builder for constructing sparse arbitrage graphs with only feasible edges."""
    
    def __init__(self):
        """Initialize the sparse graph builder."""
        self.graph = ArbitrageGraph()
        self.connectors: List[BaseExchangeConnector] = []
    
    def add_connector(self, connector: BaseExchangeConnector):
        """Add an exchange connector."""
        self.connectors.append(connector)
    
    def is_feasible_transfer(
        self,
        source_node,
        target_node,
        source_connector: Optional[BaseExchangeConnector],
        cached_prices: Optional[Dict[str, Dict[str, float]]] = None
    ) -> bool:
        """
        Check if a transfer from source to target is feasible.
        
        Args:
            source_node: Source ExchangeNode
            target_node: Target ExchangeNode
            source_connector: Connector for source exchange
            cached_prices: Cached prices dict to avoid repeated API calls
            
        Returns:
            True if transfer is feasible, False otherwise
        """
        # Same exchange, different coin: always feasible
        if source_node.exchange == target_node.exchange:
            return True
        
        # Different exchanges: check if target exchange supports target coin
        target_connector = next(
            (c for c in self.connectors if c.exchange_name == target_node.exchange),
            None
        )
        
        if target_connector is None:
            # Don't have connector for target, assume feasible but use defaults
            return True
        
        # Use cached prices if available to avoid repeated API calls
        if cached_prices is not None:
            exchange_prices = cached_prices.get(target_node.exchange, {})
            if target_node.stablecoin not in exchange_prices:
                return False
        else:
            # Fallback: check if target exchange supports the target coin
            # This is expensive, so we should use cached_prices when possible
            try:
                target_prices = target_connector.get_all_stablecoin_prices()
                if target_node.stablecoin not in target_prices:
                    return False
            except Exception:
                # If API call fails, assume not feasible to be safe
                return False
        
        # If we have source connector, could add more checks here
        # For now, if target supports the coin, assume feasible
        return True
    
    def build_graph(
        self,
        default_fee: float = 0.002,
        default_volatility: float = 0.001,
        default_transfer_time: float = 60.0,
        max_edges_per_node: int = 10
    ) -> ArbitrageGraph:
        """
        Build sparse arbitrage graph with only feasible edges.
        
        Args:
            default_fee: Default transfer fee if not available
            default_volatility: Default volatility cost
            default_transfer_time: Default transfer time in seconds
            max_edges_per_node: Maximum edges to create per node (for further sparsification)
            
        Returns:
            Constructed sparse ArbitrageGraph
        """
        self.graph = ArbitrageGraph()
        
        # Step 1: Add all nodes and cache prices to avoid repeated API calls
        all_stablecoins = set()
        cached_prices: Dict[str, Dict[str, float]] = {}
        
        for connector in self.connectors:
            try:
                prices = connector.get_all_stablecoin_prices()
                cached_prices[connector.exchange_name] = prices
                for stablecoin, price in prices.items():
                    self.graph.add_node(connector.exchange_name, stablecoin, price)
                    all_stablecoins.add(stablecoin)
            except Exception as e:
                # If API call fails, log but continue
                print(f"Warning: Failed to get prices from {connector.exchange_name}: {e}")
                cached_prices[connector.exchange_name] = {}
        
        # Step 2: Add edges only for feasible transfers
        nodes = self.graph.get_all_nodes()
        
        for source_node in nodes:
            edges_created = 0
            
            # Get connector for source exchange
            source_connector = next(
                (c for c in self.connectors if c.exchange_name == source_node.exchange),
                None
            )
            
            # Create edges, prioritizing same-exchange transfers
            # First pass: same-exchange transfers (always feasible, faster)
            for target_node in nodes:
                if edges_created >= max_edges_per_node:
                    break
                
                if source_node == target_node:
                    continue
                
                # Prioritize same-exchange transfers
                if source_node.exchange == target_node.exchange:
                    # Same exchange, different coin: always feasible
                    # Get fee and transfer time
                    if source_connector:
                        try:
                            fee = source_connector.get_transfer_fee(
                                source_node.stablecoin,
                                target_node.stablecoin
                            )
                            transfer_time = source_connector.get_estimated_transfer_time(
                                source_node.stablecoin,
                                target_node.stablecoin
                            )
                        except Exception:
                            fee = default_fee
                            transfer_time = default_transfer_time
                    else:
                        fee = default_fee
                        transfer_time = default_transfer_time
                    
                    # Calculate volatility cost
                    price_diff = abs(source_node.price - target_node.price)
                    volatility_cost = price_diff * default_volatility
                    
                    # Add edge
                    self.graph.add_edge(
                        source_node.exchange,
                        source_node.stablecoin,
                        target_node.exchange,
                        target_node.stablecoin,
                        fee,
                        volatility_cost,
                        transfer_time
                    )
                    edges_created += 1
            
            # Second pass: cross-exchange transfers (if we haven't hit the limit)
            if edges_created < max_edges_per_node:
                for target_node in nodes:
                    if edges_created >= max_edges_per_node:
                        break
                    
                    if source_node == target_node:
                        continue
                    
                    # Skip same-exchange (already added)
                    if source_node.exchange == target_node.exchange:
                        continue
                    
                    # Check if transfer is feasible (use cached prices for efficiency)
                    if not self.is_feasible_transfer(source_node, target_node, source_connector, cached_prices):
                        continue
                    
                    # Get fee and transfer time
                    if source_connector:
                        try:
                            fee = source_connector.get_transfer_fee(
                                source_node.stablecoin,
                                target_node.stablecoin
                            )
                            transfer_time = source_connector.get_estimated_transfer_time(
                                source_node.stablecoin,
                                target_node.stablecoin
                            )
                        except Exception:
                            fee = default_fee
                            transfer_time = default_transfer_time
                    else:
                        fee = default_fee
                        transfer_time = default_transfer_time
                    
                    # Calculate volatility cost
                    price_diff = abs(source_node.price - target_node.price)
                    volatility_cost = price_diff * default_volatility
                    
                    # Add edge
                    self.graph.add_edge(
                        source_node.exchange,
                        source_node.stablecoin,
                        target_node.exchange,
                        target_node.stablecoin,
                        fee,
                        volatility_cost,
                        transfer_time
                    )
                    edges_created += 1
        
        return self.graph
    
    def update_graph_from_connectors(self) -> ArbitrageGraph:
        """Update graph prices from all connectors."""
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

