"""Coinbase exchange API connector."""

import requests
import time
from typing import Dict, Optional
from .base_connector import BaseExchangeConnector


class CoinbaseConnector(BaseExchangeConnector):
    """Connector for Coinbase exchange API."""
    
    BASE_URL = "https://api.coinbase.com/v2"
    
    # Common stablecoin pairs on Coinbase
    STABLECOIN_PAIRS = {
        'USDT': 'USDT-USD',
        'USDC': 'USDC-USD',
        'DAI': 'DAI-USD',
    }
    
    def __init__(self):
        """Initialize Coinbase connector."""
        super().__init__("Coinbase")
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Rate limiting
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str) -> Optional[Dict]:
        """
        Make an API request with error handling.
        
        Args:
            endpoint: API endpoint
            
        Returns:
            JSON response or None if error
        """
        self._rate_limit()
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'errors' in data:
                print(f"Coinbase API error: {data['errors']}")
                return None
            
            return data.get('data')
        except requests.exceptions.RequestException as e:
            print(f"Coinbase API request failed: {e}")
            return None
    
    def get_stablecoin_price(self, stablecoin: str) -> Optional[float]:
        """
        Get the current price of a stablecoin from Coinbase.
        
        Args:
            stablecoin: Symbol of the stablecoin
            
        Returns:
            Price in USD, or None if unavailable
        """
        pair = self.STABLECOIN_PAIRS.get(stablecoin.upper())
        if not pair:
            return None
        
        result = self._make_request(f'exchange-rates?currency={stablecoin.upper()}')
        if not result:
            # Fallback: try spot price endpoint
            result = self._make_request(f'prices/{pair}/spot')
            if not result:
                return None
        
        # Coinbase returns different structures depending on endpoint
        if 'rates' in result:
            # Exchange rates endpoint
            usd_rate = result['rates'].get('USD')
            if usd_rate:
                try:
                    return float(usd_rate)
                except (ValueError, TypeError):
                    return None
        elif 'amount' in result:
            # Spot price endpoint
            try:
                return float(result['amount'])
            except (ValueError, TypeError):
                return None
        
        return None
    
    def get_all_stablecoin_prices(self) -> Dict[str, float]:
        """
        Get prices for all available stablecoins on Coinbase.
        
        Returns:
            Dictionary mapping stablecoin symbols to prices
        """
        prices = {}
        for stablecoin in self.STABLECOIN_PAIRS.keys():
            price = self.get_stablecoin_price(stablecoin)
            if price is not None:
                prices[stablecoin] = price
        return prices
    
    def get_transfer_fee(
        self,
        source_stablecoin: str,
        target_stablecoin: str,
        amount: float = 1.0
    ) -> float:
        """
        Get the transfer fee between two stablecoins.
        
        Note: This is a simplified implementation. In practice, you would
        query Coinbase's fee structure or use their API.
        
        Args:
            source_stablecoin: Source stablecoin symbol
            target_stablecoin: Target stablecoin symbol
            amount: Transfer amount
            
        Returns:
            Estimated transfer fee in USD
        """
        # Coinbase fee structure
        # Trading fees: 0.4% - 0.6% for retail
        # Withdrawal fees: Network fees (variable)
        
        base_withdrawal_fee = 0.0  # Network fees vary
        trading_fee_rate = 0.005  # 0.5% average for retail
        
        if source_stablecoin == target_stablecoin:
            # Same coin, just withdrawal/deposit
            return base_withdrawal_fee
        else:
            # Different coins, need trading + withdrawal
            trading_fee = amount * trading_fee_rate
            return base_withdrawal_fee + trading_fee
    
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
        # Coinbase typically faster for same-exchange operations
        if source_stablecoin == target_stablecoin:
            # Same coin transfer: 1-3 minutes
            return 120.0  # 2 minutes average
        else:
            # Cross-coin: trading + transfer
            return 45.0  # 45 seconds for trading + some buffer

