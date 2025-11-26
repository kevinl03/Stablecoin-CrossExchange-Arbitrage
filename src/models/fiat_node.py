"""FiatNode represents a fiat currency on an exchange (e.g., USD on Kraken)."""

from typing import List
from .exchange_node import ExchangeNode


class FiatNode(ExchangeNode):
    """
    A node representing a fiat currency on an exchange.
    
    Fiat currencies (USD, CAD, EUR, etc.) can be converted to/from stablecoins
    on the same exchange, creating additional arbitrage opportunities.
    """
    
    def __init__(self, exchange: str, fiat_currency: str, price: float = 1.0):
        """
        Initialize a FiatNode.
        
        Args:
            exchange: Name of the exchange
            fiat_currency: Fiat currency code (e.g., 'USD', 'CAD', 'EUR')
            price: Price of fiat (typically 1.0 for base currency, or exchange rate)
        """
        # Treat fiat as a special type of "stablecoin" for compatibility
        super().__init__(exchange, fiat_currency, price)
        self.is_fiat = True
        self.fiat_currency = fiat_currency
    
    def __repr__(self):
        """String representation."""
        return f"FiatNode({self.exchange}, {self.fiat_currency}, ${self.price:.4f})"
    
    @staticmethod
    def is_fiat_currency(currency: str) -> bool:
        """
        Check if a currency code represents a fiat currency.
        
        Args:
            currency: Currency code to check
            
        Returns:
            True if currency is a fiat currency
        """
        fiat_currencies = {
            'USD', 'CAD', 'EUR', 'GBP', 'JPY', 'AUD', 'CHF', 'CNY',
            'HKD', 'SGD', 'NZD', 'MXN', 'BRL', 'INR', 'KRW', 'TRY'
        }
        return currency.upper() in fiat_currencies

