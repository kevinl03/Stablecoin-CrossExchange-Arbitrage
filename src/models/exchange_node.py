"""ExchangeNode represents a (exchange, stablecoin) pair in the arbitrage graph."""

from typing import List, Optional


class ExchangeNode:
    """A node in the arbitrage graph representing a stablecoin on a specific exchange."""
    
    def __init__(self, exchange: str, stablecoin: str, price: float):
        """
        Initialize an ExchangeNode.
        
        Args:
            exchange: Name of the exchange (e.g., 'Kraken', 'Coinbase')
            stablecoin: Name of the stablecoin (e.g., 'USDT', 'USDC')
            price: Current price of the stablecoin in reference fiat currency
        """
        self.exchange = exchange
        self.stablecoin = stablecoin
        self.price = price
        self.edges: List['Edge'] = []
    
    def __hash__(self):
        """Hash based on exchange and stablecoin."""
        return hash((self.exchange, self.stablecoin))
    
    def __eq__(self, other):
        """Equality based on exchange and stablecoin."""
        if not isinstance(other, ExchangeNode):
            return False
        return self.exchange == other.exchange and self.stablecoin == other.stablecoin
    
    def __repr__(self):
        """String representation."""
        return f"ExchangeNode({self.exchange}, {self.stablecoin}, ${self.price:.4f})"
    
    def add_edge(self, edge: 'Edge'):
        """Add an outgoing edge from this node."""
        self.edges.append(edge)

