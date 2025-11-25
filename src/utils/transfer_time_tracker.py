"""Transfer time tracking system for realistic time window estimation."""

from typing import Dict, List, Tuple
import numpy as np
from collections import deque


class TransferTimeTracker:
    """Tracks historical transfer times for realistic time window estimation."""
    
    def __init__(self, window_size: int = 50):
        """
        Initialize transfer time tracker.
        
        Args:
            window_size: Number of transfer records to keep per route
        """
        self.window_size = window_size
        self.transfer_times: Dict[Tuple[str, str, str, str], deque] = {}
    
    def record_transfer(
        self,
        source_exchange: str,
        source_coin: str,
        target_exchange: str,
        target_coin: str,
        actual_time: float
    ):
        """
        Record an actual transfer time.
        
        Args:
            source_exchange: Source exchange name
            source_coin: Source stablecoin symbol
            target_exchange: Target exchange name
            target_coin: Target stablecoin symbol
            actual_time: Actual transfer time in seconds
        """
        key = (source_exchange, source_coin, target_exchange, target_coin)
        if key not in self.transfer_times:
            self.transfer_times[key] = deque(maxlen=self.window_size)
        
        self.transfer_times[key].append(actual_time)
    
    def get_estimated_time(
        self,
        source_exchange: str,
        source_coin: str,
        target_exchange: str,
        target_coin: str,
        percentile: float = 95.0,
        default: float = 60.0
    ) -> float:
        """
        Get estimated transfer time using historical data.
        
        Uses percentile to account for worst-case scenarios.
        
        Args:
            source_exchange: Source exchange name
            source_coin: Source stablecoin symbol
            target_exchange: Target exchange name
            target_coin: Target stablecoin symbol
            percentile: Percentile to use (default: 95th for conservative estimate)
            default: Default time if no history available
            
        Returns:
            Estimated transfer time in seconds
        """
        key = (source_exchange, source_coin, target_exchange, target_coin)
        if key not in self.transfer_times or len(self.transfer_times[key]) == 0:
            return default
        
        times = list(self.transfer_times[key])
        if len(times) == 0:
            return default
        
        # Use percentile to account for worst-case
        estimated = np.percentile(times, percentile)
        return float(estimated)
    
    def get_average_time(
        self,
        source_exchange: str,
        source_coin: str,
        target_exchange: str,
        target_coin: str,
        default: float = 60.0
    ) -> float:
        """
        Get average transfer time.
        
        Args:
            source_exchange: Source exchange name
            source_coin: Source stablecoin symbol
            target_exchange: Target exchange name
            target_coin: Target stablecoin symbol
            default: Default time if no history available
            
        Returns:
            Average transfer time in seconds
        """
        key = (source_exchange, source_coin, target_exchange, target_coin)
        if key not in self.transfer_times or len(self.transfer_times[key]) == 0:
            return default
        
        times = list(self.transfer_times[key])
        return float(np.mean(times))
    
    def clear_history(self):
        """Clear all transfer time history."""
        self.transfer_times.clear()

