#!/usr/bin/env python3
"""
Analyze fee impact on arbitrage profits across different portfolio sizes.

This script demonstrates:
1. How percentage-based trading fees scale
2. How flat withdrawal fees impact different portfolio sizes
3. The break-even point for profitable arbitrage
"""

from typing import Dict, List, Tuple

# Fee structures from fees.py
TRADING_FEES_TAKER = {
    "binance": 0.0010,  # 0.10%
    "kraken":  0.0040,  # 0.40%
    "kucoin":  0.0010,  # 0.10%
    "bybit":   0.0010,  # 0.10%
}

WITHDRAWAL_FEES_EXAMPLE = {
    "USDT": {
        "ETH": 0.75,  # Binance USDT on Ethereum
        "TRX": 0.8,   # Binance USDT on Tron
        "SOL": 0.25,  # Binance USDT on Solana
    },
    "USDC": {
        "ETH": 0.8,   # Binance USDC on Ethereum
        "SOL": 0.2,   # Binance USDC on Solana
    }
}

# Estimated network gas fees (in USD)
NETWORK_GAS_FEES = {
    "ETH": 10.0,      # Ethereum: $10 average
    "ARB": 0.5,       # Arbitrum: $0.50
    "POLYGON": 0.1,   # Polygon: $0.10
    "SOL": 0.00025,   # Solana: $0.00025
    "TRX": 0.0,       # Tron: Free
    "BNB": 0.1,       # BNB Smart Chain: $0.10
}


def calculate_arbitrage_costs(
    portfolio_size_usd: float,
    num_trades: int = 2,
    num_transfers: int = 1,
    exchange: str = "binance",
    coin: str = "USDT",
    chain: str = "ETH",
) -> Dict[str, float]:
    """
    Calculate total costs for an arbitrage path.
    
    Args:
        portfolio_size_usd: Starting portfolio size
        num_trades: Number of trades (typically 2-3)
        num_transfers: Number of cross-exchange transfers (typically 1-2)
        exchange: Exchange name
        coin: Stablecoin being traded
        chain: Blockchain network for transfer
    
    Returns:
        Dictionary with cost breakdown
    """
    # Trading fees (percentage-based)
    taker_fee = TRADING_FEES_TAKER.get(exchange, 0.001)
    total_trading_fee_usd = portfolio_size_usd * taker_fee * num_trades
    
    # Withdrawal fees (flat, in coin units)
    withdrawal_fee_units = WITHDRAWAL_FEES_EXAMPLE.get(coin, {}).get(chain, 0.8)
    withdrawal_fee_usd = withdrawal_fee_units * num_transfers  # Assuming $1 per unit
    
    # Network gas fees (flat, in USD)
    gas_fee_usd = NETWORK_GAS_FEES.get(chain, 0.0) * num_transfers
    
    # Total costs
    total_costs_usd = total_trading_fee_usd + withdrawal_fee_usd + gas_fee_usd
    
    # Percentage impact
    cost_percentage = (total_costs_usd / portfolio_size_usd) * 100
    
    return {
        "portfolio_size_usd": portfolio_size_usd,
        "trading_fees_usd": total_trading_fee_usd,
        "trading_fees_pct": (total_trading_fee_usd / portfolio_size_usd) * 100,
        "withdrawal_fees_usd": withdrawal_fee_usd,
        "withdrawal_fees_pct": (withdrawal_fee_usd / portfolio_size_usd) * 100,
        "gas_fees_usd": gas_fee_usd,
        "gas_fees_pct": (gas_fee_usd / portfolio_size_usd) * 100,
        "total_costs_usd": total_costs_usd,
        "total_costs_pct": cost_percentage,
        "break_even_spread_pct": cost_percentage,  # Minimum spread needed to break even
    }


def print_fee_analysis():
    """Print fee analysis for different portfolio sizes."""
    portfolio_sizes = [100, 500, 1_000, 5_000, 10_000, 50_000, 100_000]
    
    print("=" * 80)
    print("FEE IMPACT ANALYSIS FOR ARBITRAGE")
    print("=" * 80)
    print("\nScenario: 2 trades + 1 transfer (Binance, USDT on Ethereum)")
    print("-" * 80)
    print(f"{'Portfolio':<12} {'Trading':<12} {'Withdrawal':<12} {'Gas':<12} {'Total':<12} {'Break-Even':<12}")
    print(f"{'Size ($)':<12} {'Fees ($)':<12} {'Fees ($)':<12} {'Fees ($)':<12} {'Cost ($)':<12} {'Spread (%)':<12}")
    print("-" * 80)
    
    for size in portfolio_sizes:
        costs = calculate_arbitrage_costs(
            portfolio_size_usd=size,
            num_trades=2,
            num_transfers=1,
            exchange="binance",
            coin="USDT",
            chain="ETH",
        )
        
        print(
            f"${size:>10,}  "
            f"${costs['trading_fees_usd']:>10.2f}  "
            f"${costs['withdrawal_fees_usd']:>10.2f}  "
            f"${costs['gas_fees_usd']:>10.2f}  "
            f"${costs['total_costs_usd']:>10.2f}  "
            f"{costs['break_even_spread_pct']:>10.2f}%"
        )
    
    print("\n" + "=" * 80)
    print("KEY INSIGHTS:")
    print("=" * 80)
    print("1. Trading fees scale linearly (same % regardless of size)")
    print("2. Withdrawal fees are FLAT - they dominate small portfolios")
    print("3. Gas fees are FLAT - Ethereum is expensive, Solana/Tron are cheap")
    print("4. Small portfolios (<$1,000) need very large spreads (>1%) to be profitable")
    print("5. Large portfolios (>$10,000) can profit from smaller spreads (>0.1%)")
    
    print("\n" + "=" * 80)
    print("COMPARISON: Different Chains")
    print("=" * 80)
    print(f"{'Chain':<12} {'Withdrawal':<12} {'Gas Fee':<12} {'Total Flat':<12}")
    print(f"{'':<12} {'Fee (USDT)':<12} {'(USD)':<12} {'Fee (USD)':<12}")
    print("-" * 80)
    
    chains = ["ETH", "ARB", "SOL", "TRX", "BNB"]
    for chain in chains:
        withdrawal = WITHDRAWAL_FEES_EXAMPLE["USDT"].get(chain, 0.8)
        gas = NETWORK_GAS_FEES.get(chain, 0.0)
        total_flat = withdrawal + gas
        print(f"{chain:<12} {withdrawal:<12.2f} ${gas:<11.2f} ${total_flat:<11.2f}")
    
    print("\n" + "=" * 80)
    print("RECOMMENDATION: Use cheap chains (Solana, Tron, BNB) for small portfolios")
    print("=" * 80)


if __name__ == "__main__":
    print_fee_analysis()

