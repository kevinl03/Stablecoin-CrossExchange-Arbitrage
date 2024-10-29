"""Kraken exchange API connector."""

import requests
import time
from typing import Dict, Optional
from .base_connector import BaseExchangeConnector


class KrakenConnector(BaseExchangeConnector):
    """Connector for Kraken exchange API."""
    
    BASE_URL = "https://api.kraken.com/0/public"
    
    # Common stablecoin pairs on Kraken
    STABLECOIN_PAIRS = {
        'USDT': 'USDTUSD',
        'USDC': 'USDCUSD',
        'DAI': 'DAIUSD',
        'BUSD': 'BUSDUSD',
    }
    
    def __init__(self):
        """Initialize Kraken connector."""
        super().__init__("Kraken")
        self.session = requests.Session()
        self.last_request_time = 0
        self.min_request_interval = 1.0  # Rate limiting: 1 request per second
    
    def _rate_limit(self):
        """Enforce rate limiting."""
        current_time = time.time()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.min_request_interval:
            time.sleep(self.min_request_interval - time_since_last)
        self.last_request_time = time.time()
    
    def _make_request(self, endpoint: str, params: Dict = None) -> Optional[Dict]:
        """
        Make an API request with error handling.
        
        Args:
            endpoint: API endpoint
            params: Request parameters
            
        Returns:
            JSON response or None if error
        """
        self._rate_limit()
        try:
            url = f"{self.BASE_URL}/{endpoint}"
            response = self.session.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            if 'error' in data and data['error']:
                print(f"Kraken API error: {data['error']}")
                return None
            
            return data.get('result')
        except requests.exceptions.RequestException as e:
            print(f"Kraken API request failed: {e}")
            return None
    
    def get_stablecoin_price(self, stablecoin: str) -> Optional[float]:
        """
        Get the current price of a stablecoin from Kraken.
        
        Args:
            stablecoin: Symbol of the stablecoin
            
        Returns:
            Price in USD, or None if unavailable
        """
        pair = self.STABLECOIN_PAIRS.get(stablecoin.upper())
        if not pair:
            return None
        
        result = self._make_request('Ticker', {'pair': pair})
        if not result:
            return None
        
        # Kraken returns nested dict with pair as key
        ticker_data = result.get(pair) or result.get(list(result.keys())[0])
        if not ticker_data:
            return None
        
        # Get the last trade price (index 0 in 'c' array)
        price_str = ticker_data.get('c', [None])[0]
        if price_str:
            try:
                return float(price_str)
            except (ValueError, TypeError):
                return None
        
        return None
    
    def get_all_stablecoin_prices(self) -> Dict[str, float]:
        """
        Get prices for all available stablecoins on Kraken.
        
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
        query Kraken's fee structure or use their API.
        
        Args:
            source_stablecoin: Source stablecoin symbol
            target_stablecoin: Target stablecoin symbol
            amount: Transfer amount
            
        Returns:
            Estimated transfer fee in USD
        """
        # Default fee structure (can be customized)
        # Typical withdrawal fees: 0-5 USD depending on coin
        # Trading fees: 0.16% - 0.26% maker/taker
        
        base_withdrawal_fee = 0.0  # Varies by coin
        trading_fee_rate = 0.002  # 0.2% average
        
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
        # Typical blockchain confirmation times
        # USDT (ERC-20): ~15 seconds (Ethereum)
        # USDC (ERC-20): ~15 seconds (Ethereum)
        # DAI (ERC-20): ~15 seconds (Ethereum)
        
        if source_stablecoin == target_stablecoin:
            # Same coin transfer: 1-5 minutes
            return 180.0  # 3 minutes average
        else:
            # Cross-coin: trading + transfer
            return 60.0  # 1 minute for trading + some buffer

