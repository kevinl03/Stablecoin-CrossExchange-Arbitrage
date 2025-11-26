"""Graph builder with fiat currency support for expanded arbitrage opportunities."""

from typing import List, Dict, Optional, Set, Tuple
from .models.graph import ArbitrageGraph
from .models.fiat_node import FiatNode
from .connectors.base_connector import BaseExchangeConnector


class FiatEnabledGraphBuilder:
    """
    Graph builder that includes fiat currencies as nodes.
    
    This enables arbitrage paths like:
    - USDT (Kraken) -> USD (Kraken) -> USD (Coinbase) -> USDC (Coinbase)
    - USDT (Kraken) -> USD (Kraken) -> USDC (Coinbase) -> USDT (Kraken)
    
    Fiat currencies act as intermediate nodes that can be converted to/from
    stablecoins on the same exchange, and transferred between exchanges.
    """
    
    def __init__(self):
        """Initialize the fiat-enabled graph builder."""
        self.graph = ArbitrageGraph()
        self.connectors: List[BaseExchangeConnector] = []
        self.supported_fiats: Dict[str, Set[str]] = {}  # exchange -> set of fiat currencies
    
    def add_connector(self, connector: BaseExchangeConnector, supported_fiats: Optional[List[str]] = None):
        """
        Add an exchange connector with supported fiat currencies.
        
        Args:
            connector: Exchange connector
            supported_fiats: List of fiat currencies supported by this exchange
                           (e.g., ['USD', 'CAD']). If None, defaults to ['USD']
        """
        self.connectors.append(connector)
        if supported_fiats is None:
            supported_fiats = ['USD']  # Default to USD
        self.supported_fiats[connector.exchange_name] = set(supported_fiats)
    
    def build_graph(
        self,
        default_fee: float = 0.002,
        default_volatility: float = 0.001,
        default_transfer_time: float = 60.0,
        fiat_conversion_fee: float = 0.001,  # Fee for stablecoin <-> fiat conversion
        fiat_transfer_fee: float = 0.0015,   # Fee for fiat transfer between exchanges
        include_fiat_to_fiat: bool = True    # Include edges between fiat on different exchanges
    ) -> ArbitrageGraph:
        """
        Build the arbitrage graph including fiat currency nodes.
        
        Args:
            default_fee: Default transfer fee for stablecoin transfers
            default_volatility: Default volatility cost
            default_transfer_time: Default transfer time in seconds
            fiat_conversion_fee: Fee for converting stablecoin <-> fiat on same exchange
            fiat_transfer_fee: Fee for transferring fiat between exchanges
            include_fiat_to_fiat: Whether to create edges between fiat on different exchanges
            
        Returns:
            Constructed ArbitrageGraph with fiat nodes
        """
        self.graph = ArbitrageGraph()
        
        # Step 1: Add stablecoin nodes
        all_stablecoins = set()
        for connector in self.connectors:
            prices = connector.get_all_stablecoin_prices()
            for stablecoin, price in prices.items():
                self.graph.add_node(connector.exchange_name, stablecoin, price)
                all_stablecoins.add(stablecoin)
        
        # Step 2: Add fiat currency nodes
        for connector in self.connectors:
            exchange = connector.exchange_name
            fiats = self.supported_fiats.get(exchange, {'USD'})
            
            for fiat in fiats:
                # Fiat price is typically 1.0 (or could be fetched from exchange)
                # For now, we'll use 1.0 as the base price
                fiat_price = 1.0
                self.graph.add_node(exchange, fiat, fiat_price)
        
        # Step 3: Add edges between stablecoins (existing functionality)
        nodes = self.graph.get_all_nodes()
        for source_node in nodes:
            for target_node in nodes:
                if source_node == target_node:
                    continue
                
                # Skip if both are fiat (handled separately)
                if (FiatNode.is_fiat_currency(source_node.stablecoin) and 
                    FiatNode.is_fiat_currency(target_node.stablecoin)):
                    continue
                
                # Standard stablecoin transfer
                if not FiatNode.is_fiat_currency(source_node.stablecoin) and \
                   not FiatNode.is_fiat_currency(target_node.stablecoin):
                    self.graph.add_edge(
                        source_node.exchange, source_node.stablecoin,
                        target_node.exchange, target_node.stablecoin,
                        fee=default_fee,
                        volatility_cost=default_volatility,
                        transfer_time=default_transfer_time
                    )
        
        # Step 4: Add stablecoin <-> fiat conversion edges (same exchange)
        for connector in self.connectors:
            exchange = connector.exchange_name
            fiats = self.supported_fiats.get(exchange, {'USD'})
            
            # Get stablecoins on this exchange
            exchange_stablecoins = [
                node for node in nodes 
                if node.exchange == exchange and 
                not FiatNode.is_fiat_currency(node.stablecoin)
            ]
            
            for stablecoin_node in exchange_stablecoins:
                for fiat in fiats:
                    fiat_node = self.graph.get_node(exchange, fiat)
                    if fiat_node:
                        # Stablecoin -> Fiat conversion
                        self.graph.add_edge(
                            exchange, stablecoin_node.stablecoin,
                            exchange, fiat,
                            fee=fiat_conversion_fee,
                            volatility_cost=0.0001,  # Lower volatility for same-exchange conversion
                            transfer_time=0.0  # Instant conversion
                        )
                        
                        # Fiat -> Stablecoin conversion
                        self.graph.add_edge(
                            exchange, fiat,
                            exchange, stablecoin_node.stablecoin,
                            fee=fiat_conversion_fee,
                            volatility_cost=0.0001,
                            transfer_time=0.0
                        )
        
        # Step 5: Add fiat -> fiat edges (between exchanges)
        if include_fiat_to_fiat:
            fiat_nodes = [
                node for node in nodes 
                if FiatNode.is_fiat_currency(node.stablecoin)
            ]
            
            for source_fiat in fiat_nodes:
                for target_fiat in fiat_nodes:
                    if source_fiat == target_fiat:
                        continue
                    
                    # Only connect same fiat currency between different exchanges
                    if (source_fiat.stablecoin == target_fiat.stablecoin and
                        source_fiat.exchange != target_fiat.exchange):
                        self.graph.add_edge(
                            source_fiat.exchange, source_fiat.stablecoin,
                            target_fiat.exchange, target_fiat.stablecoin,
                            fee=fiat_transfer_fee,
                            volatility_cost=0.0001,  # Lower volatility for fiat
                            transfer_time=default_transfer_time
                        )
        
        return self.graph
    
    def get_fiat_arbitrage_paths(
        self,
        start_stablecoin: str,
        target_stablecoin: str,
        fiat_currency: str = 'USD'
    ) -> List[List[Tuple[str, str]]]:
        """
        Get potential arbitrage paths using fiat as intermediate step.
        
        Args:
            start_stablecoin: Starting stablecoin
            target_stablecoin: Target stablecoin
            fiat_currency: Fiat currency to use as intermediate
            
        Returns:
            List of paths, where each path is a list of (exchange, currency) tuples
        """
        paths = []
        nodes = self.graph.get_all_nodes()
        
        # Find all nodes for start and target stablecoins
        start_nodes = [n for n in nodes if n.stablecoin == start_stablecoin]
        target_nodes = [n for n in nodes if n.stablecoin == target_stablecoin]
        fiat_nodes = [n for n in nodes if n.stablecoin == fiat_currency]
        
        # Path: Start -> Fiat (same exchange) -> Fiat (different exchange) -> Target
        for start in start_nodes:
            for fiat1 in fiat_nodes:
                if fiat1.exchange == start.exchange:
                    for fiat2 in fiat_nodes:
                        if fiat2.exchange != fiat1.exchange:
                            for target in target_nodes:
                                if target.exchange == fiat2.exchange:
                                    paths.append([
                                        (start.exchange, start.stablecoin),
                                        (fiat1.exchange, fiat1.stablecoin),
                                        (fiat2.exchange, fiat2.stablecoin),
                                        (target.exchange, target.stablecoin)
                                    ])
        
        return paths

