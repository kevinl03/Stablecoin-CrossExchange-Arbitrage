"""Edge represents a transfer possibility between two ExchangeNodes."""

from typing import Optional
from .exchange_node import ExchangeNode


class Edge:
    """A directed edge in the arbitrage graph representing a transfer possibility."""
    
    def __init__(
        self,
        source: ExchangeNode,
        target: ExchangeNode,
        fee: float,
        volatility_cost: float = 0.0,
        transfer_time: float = 0.0
    ):
        """
        Initialize an Edge.
        
        Args:
            source: Source ExchangeNode
            target: Target ExchangeNode
            fee: Transaction and withdrawal/deposit fees
            volatility_cost: Slippage and volatility risk cost
            transfer_time: Estimated transfer time in seconds
        """
        self.source = source
        self.target = target
        self.fee = fee
        self.volatility_cost = volatility_cost
        self.transfer_time = transfer_time
        self.weight = fee + volatility_cost  # Total transfer cost
    
    def __repr__(self):
        """String representation."""
        return f"Edge({self.source} -> {self.target}, cost=${self.weight:.4f})"
    
    def update_volatility_cost(self, new_cost: float):
        """Update the volatility cost and recalculate weight."""
        self.volatility_cost = new_cost
        self.weight = self.fee + self.volatility_cost

