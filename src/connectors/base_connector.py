"""Base class for exchange connectors."""

from abc import ABC, abstractmethod
from typing import Dict, Optional


class BaseExchangeConnector(ABC):
    """Abstract base class for exchange API connectors."""
    
    def __init__(self, exchange_name: str):
        """
        Initialize the connector.
        
        Args:
            exchange_name: Name of the exchange
        """
        self.exchange_name = exchange_name
    
    @abstractmethod
    def get_stablecoin_price(self, stablecoin: str) -> Optional[float]:
        """
        Get the current price of a stablecoin.
        
        Args:
            stablecoin: Symbol of the stablecoin (e.g., 'USDT', 'USDC')
            
        Returns:
            Price in reference fiat currency, or None if unavailable
        """
        pass
    
    @abstractmethod
    def get_all_stablecoin_prices(self) -> Dict[str, float]:
        """
        Get prices for all available stablecoins.
        
        Returns:
            Dictionary mapping stablecoin symbols to prices
        """
        pass
    
    @abstractmethod
    def get_transfer_fee(
        self,
        source_stablecoin: str,
        target_stablecoin: str,
        amount: float = 1.0
    ) -> float:
        """
        Get the transfer fee between two stablecoins.
        
        Args:
            source_stablecoin: Source stablecoin symbol
            target_stablecoin: Target stablecoin symbol
            amount: Transfer amount (default: 1.0)
            
        Returns:
            Transfer fee in reference fiat currency
        """
        pass
    
    @abstractmethod
    def get_estimated_transfer_time(
        self,
        source_stablecoin: str,
        target_stablecoin: str
    ) -> float:
        """
        Get estimated transfer time in seconds.
        
        Args:
            source_stablecoin: Source stablecoin symbol
            target_stablecoin: Target stablecoin symbol
            
        Returns:
            Estimated transfer time in seconds
        """
        pass

