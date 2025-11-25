"""Wallet balance and volume optimization system for arbitrage execution."""

from typing import Dict, List, Tuple, Optional, Callable
from ..models.exchange_node import ExchangeNode


class WalletManager:
    """
    Manages wallet balances and optimizes trade volumes based on fee tiers.
    
    This system addresses two critical issues:
    1. Insufficient funds: Checks if opportunities can actually be executed
    2. Suboptimal volume: Optimizes trade size based on volume-dependent fees
    """
    
    def __init__(self):
        """Initialize the wallet manager."""
        # (exchange, coin) -> balance in USD
        self.balances: Dict[Tuple[str, str], float] = {}
        
        # exchange -> fee function (volume -> fee_rate)
        self.fee_schedules: Dict[str, Callable[[float], float]] = {}
        
        # Default fee schedule (can be overridden per exchange)
        self._default_fee_schedule = self._create_default_fee_schedule()
    
    def _create_default_fee_schedule(self) -> Callable[[float], float]:
        """
        Create default volume-based fee schedule.
        
        Tiers:
        - < $1,000: 0.1% (0.001)
        - $1,000 - $10,000: 0.05% (0.0005)
        - $10,000 - $100,000: 0.02% (0.0002)
        - > $100,000: 0.01% (0.0001)
        """
        def fee_func(volume: float) -> float:
            if volume < 1000:
                return 0.001  # 0.1%
            elif volume < 10000:
                return 0.0005  # 0.05%
            elif volume < 100000:
                return 0.0002  # 0.02%
            else:
                return 0.0001  # 0.01%
        
        return fee_func
    
    def set_balance(self, exchange: str, coin: str, balance: float) -> None:
        """
        Set the balance for a specific exchange and coin.
        
        Args:
            exchange: Exchange name
            coin: Coin/stablecoin name
            balance: Balance in USD
        """
        key = (exchange, coin)
        self.balances[key] = balance
    
    def get_balance(self, exchange: str, coin: str) -> float:
        """
        Get the balance for a specific exchange and coin.
        
        Args:
            exchange: Exchange name
            coin: Coin/stablecoin name
            
        Returns:
            Balance in USD, or 0.0 if not set
        """
        key = (exchange, coin)
        return self.balances.get(key, 0.0)
    
    def set_fee_schedule(self, exchange: str, fee_func: Callable[[float], float]) -> None:
        """
        Set a custom fee schedule for an exchange.
        
        Args:
            exchange: Exchange name
            fee_func: Function that takes volume (float) and returns fee rate (float)
        """
        self.fee_schedules[exchange] = fee_func
    
    def get_effective_fee(self, exchange: str, volume: float) -> float:
        """
        Get the effective fee rate for a given volume on an exchange.
        
        Args:
            exchange: Exchange name
            volume: Trade volume in USD
            
        Returns:
            Fee rate (e.g., 0.001 for 0.1%)
        """
        fee_func = self.fee_schedules.get(exchange, self._default_fee_schedule)
        return fee_func(volume)
    
    def can_execute(
        self,
        path: List[ExchangeNode],
        required_amount: float
    ) -> bool:
        """
        Check if sufficient funds are available to execute an arbitrage path.
        
        Args:
            path: List of ExchangeNodes representing the arbitrage path
            required_amount: Required amount in USD
            
        Returns:
            True if all nodes in path have sufficient balance
        """
        for node in path:
            balance = self.get_balance(node.exchange, node.stablecoin)
            if balance < required_amount:
                return False
        return True
    
    def get_max_executable_amount(
        self,
        path: List[ExchangeNode]
    ) -> float:
        """
        Get the maximum amount that can be executed for a given path.
        
        Args:
            path: List of ExchangeNodes representing the arbitrage path
            
        Returns:
            Maximum executable amount in USD (minimum balance across path)
        """
        if not path:
            return 0.0
        
        min_balance = float('inf')
        for node in path:
            balance = self.get_balance(node.exchange, node.stablecoin)
            min_balance = min(min_balance, balance)
        
        return min_balance if min_balance != float('inf') else 0.0
    
    def optimize_volume(
        self,
        path: List[ExchangeNode],
        base_profit_rate: float,
        base_cost_rate: float,
        available_funds: float
    ) -> Tuple[float, float]:
        """
        Find optimal volume to maximize profit considering fee tiers.
        
        Uses binary search to find the volume that maximizes net profit
        after accounting for volume-dependent fees.
        
        Args:
            path: List of ExchangeNodes representing the arbitrage path
            base_profit_rate: Profit per unit (e.g., 0.001 for 0.1%)
            base_cost_rate: Base cost per unit (before volume optimization)
            available_funds: Maximum funds available
            
        Returns:
            Tuple of (optimal_volume, net_profit)
        """
        if not path or available_funds <= 0:
            return (0.0, 0.0)
        
        # Test volumes at key points (tier boundaries and midpoints)
        test_volumes = [
            0.0,
            min(1000, available_funds),
            min(10000, available_funds),
            min(100000, available_funds),
            available_funds
        ]
        
        # Remove duplicates and sort
        test_volumes = sorted(set(test_volumes))
        
        best_volume = 0.0
        best_net_profit = 0.0
        
        for volume in test_volumes:
            if volume <= 0:
                continue
            
            # Calculate total fees for this volume across the path
            total_fee_rate = 0.0
            for node in path:
                fee_rate = self.get_effective_fee(node.exchange, volume)
                total_fee_rate += fee_rate
            
            # Net profit = (profit_rate - cost_rate - total_fee_rate) * volume
            net_profit_rate = base_profit_rate - base_cost_rate - total_fee_rate
            net_profit = net_profit_rate * volume
            
            if net_profit > best_net_profit:
                best_net_profit = net_profit
                best_volume = volume
        
        return (best_volume, best_net_profit)
    
    def evaluate_opportunity(
        self,
        path: List[ExchangeNode],
        predicted_profit_rate: float,
        predicted_cost_rate: float,
        min_amount: float = 100.0
    ) -> Dict[str, any]:
        """
        Evaluate an arbitrage opportunity considering wallet constraints.
        
        Args:
            path: List of ExchangeNodes representing the arbitrage path
            predicted_profit_rate: Predicted profit per unit
            predicted_cost_rate: Predicted cost per unit
            min_amount: Minimum trade amount to consider
            
        Returns:
            Dictionary with:
            - executable: bool
            - max_amount: float
            - optimal_volume: float
            - optimal_profit: float
            - can_execute: bool
        """
        max_amount = self.get_max_executable_amount(path)
        can_execute = max_amount >= min_amount
        
        if not can_execute:
            return {
                'executable': False,
                'max_amount': max_amount,
                'optimal_volume': 0.0,
                'optimal_profit': 0.0,
                'can_execute': False,
                'reason': 'Insufficient funds'
            }
        
        # Optimize volume
        optimal_volume, optimal_profit = self.optimize_volume(
            path,
            predicted_profit_rate,
            predicted_cost_rate,
            max_amount
        )
        
        return {
            'executable': optimal_profit > 0,
            'max_amount': max_amount,
            'optimal_volume': optimal_volume,
            'optimal_profit': optimal_profit,
            'can_execute': True,
            'reason': 'Sufficient funds available'
        }
    
    def get_summary(self) -> Dict[str, any]:
        """
        Get a summary of all wallet balances.
        
        Returns:
            Dictionary with total balances and per-exchange breakdown
        """
        total_balance = sum(self.balances.values())
        exchange_totals: Dict[str, float] = {}
        
        for (exchange, coin), balance in self.balances.items():
            if exchange not in exchange_totals:
                exchange_totals[exchange] = 0.0
            exchange_totals[exchange] += balance
        
        return {
            'total_balance': total_balance,
            'num_positions': len(self.balances),
            'exchange_totals': exchange_totals,
            'balances': dict(self.balances)
        }

