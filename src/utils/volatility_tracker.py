"""Dynamic volatility tracking system for adaptive risk estimation."""

from typing import Dict, List, Tuple
import numpy as np
from collections import deque


class VolatilityTracker:
    """Tracks historical price volatility for adaptive risk estimation."""
    
    def __init__(self, window_size: int = 100):
        """
        Initialize volatility tracker.
        
        Args:
            window_size: Number of price updates to keep in history
        """
        self.window_size = window_size
        self.price_history: Dict[Tuple[str, str], deque] = {}
    
    def update_price(self, exchange: str, coin: str, price: float):
        """
        Update price history for a specific (exchange, coin) pair.
        
        Args:
            exchange: Exchange name
            coin: Stablecoin symbol
            price: Current price
        """
        key = (exchange, coin)
        if key not in self.price_history:
            self.price_history[key] = deque(maxlen=self.window_size)
        
        self.price_history[key].append(price)
    
    def get_volatility(self, exchange: str, coin: str) -> float:
        """
        Get current volatility estimate for (exchange, coin) pair.
        
        Args:
            exchange: Exchange name
            coin: Stablecoin symbol
            
        Returns:
            Volatility estimate (standard deviation of returns), or 0.1 default
        """
        key = (exchange, coin)
        if key not in self.price_history or len(self.price_history[key]) < 2:
            return 0.1  # Default volatility
        
        prices = list(self.price_history[key])
        if len(prices) < 2:
            return 0.1
        
        # Calculate returns
        returns = []
        for i in range(1, len(prices)):
            if prices[i-1] > 0:
                ret = (prices[i] / prices[i-1]) - 1
                returns.append(ret)
        
        if len(returns) < 2:
            return 0.1
        
        # Calculate standard deviation of returns
        volatility = np.std(returns)
        return max(volatility, 0.001)  # Minimum 0.1% volatility
    
    def get_volatility_factor(self, exchange: str, coin: str, base_factor: float = 0.1) -> float:
        """
        Get adaptive volatility factor based on historical volatility.
        
        Args:
            exchange: Exchange name
            coin: Stablecoin symbol
            base_factor: Base volatility factor (default: 0.1)
            
        Returns:
            Adjusted volatility factor
        """
        volatility = self.get_volatility(exchange, coin)
        # Scale factor based on volatility: higher volatility = higher factor
        # Normalize: if volatility is 0.01 (1%), use base_factor
        # If volatility is 0.05 (5%), use 5x base_factor
        normalized_vol = volatility / 0.01  # Normalize to 1% baseline
        return base_factor * max(normalized_vol, 0.5)  # At least 0.5x, up to 5x
    
    def get_all_volatilities(self) -> Dict[Tuple[str, str], float]:
        """
        Get volatility estimates for all tracked pairs.
        
        Returns:
            Dictionary mapping (exchange, coin) to volatility
        """
        return {
            key: self.get_volatility(key[0], key[1])
            for key in self.price_history.keys()
        }
    
    def clear_history(self):
        """Clear all price history."""
        self.price_history.clear()

