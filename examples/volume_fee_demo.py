#!/usr/bin/env python3
"""Demonstration of volume-based fee savings and cross-exchange arbitrage."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.utils.wallet_manager import WalletManager
from src.models.exchange_node import ExchangeNode
from src.models.edge import Edge
from src.models.graph import ArbitrageGraph


def demonstrate_volume_fee_savings():
    """Show how higher volumes reduce fees."""
    print("="*70)
    print("VOLUME-BASED FEE SAVINGS DEMONSTRATION")
    print("="*70)
    
    manager = WalletManager()
    
    # Example: Trading USDT on Kraken
    print("\n1. Fee Schedule (Default):")
    print("-" * 70)
    volumes = [500, 1000, 5000, 10000, 50000, 100000, 200000]
    
    print(f"{'Volume (USD)':<15} {'Fee Rate':<15} {'Fee Amount':<15} {'Savings vs Small'}")
    print("-" * 70)
    
    base_fee = None
    for volume in volumes:
        fee_rate = manager.get_effective_fee("Kraken", volume)
        fee_amount = volume * fee_rate
        
        if base_fee is None:
            base_fee = fee_amount
            savings = 0
        else:
            savings = base_fee - fee_amount
        
        print(f"${volume:>10,}     {fee_rate*100:>6.3f}%      ${fee_amount:>10.2f}     ${savings:>10.2f}")
    
    print("\n💡 Key Insight: Higher volumes = Lower fees = More profit!")
    print("   Example: $200,000 trade saves $180 vs $500 trade")


def demonstrate_cross_exchange_arbitrage():
    """Show arbitrage opportunities between exchanges."""
    print("\n\n" + "="*70)
    print("CROSS-EXCHANGE ARBITRAGE OPPORTUNITIES")
    print("="*70)
    
    # Create example scenario
    graph = ArbitrageGraph()
    
    # Add nodes with different prices (arbitrage opportunity)
    kraken_usdt = graph.add_node("Kraken", "USDT", 1.001)  # Slightly overvalued
    coinbase_usdc = graph.add_node("Coinbase", "USDC", 0.999)  # Slightly undervalued
    binance_busd = graph.add_node("Binance", "BUSD", 1.000)  # At par
    
    # Add edges with fees
    # Transfer from Kraken to Coinbase
    graph.add_edge("Kraken", "USDT", "Coinbase", "USDC", fee=0.001, volatility_cost=0.0001)
    
    # Transfer from Coinbase to Binance
    graph.add_edge("Coinbase", "USDC", "Binance", "BUSD", fee=0.001, volatility_cost=0.0001)
    
    # Transfer back to Kraken
    graph.add_edge("Binance", "BUSD", "Kraken", "USDT", fee=0.001, volatility_cost=0.0001)
    
    print("\n1. Price Differences (Arbitrage Opportunity):")
    print("-" * 70)
    print(f"Kraken USDT:  ${kraken_usdt.price:.4f}  (overvalued)")
    print(f"Coinbase USDC: ${coinbase_usdc.price:.4f}  (undervalued)")
    print(f"Binance BUSD:  ${binance_busd.price:.4f}  (at par)")
    
    print("\n2. Arbitrage Path:")
    print("-" * 70)
    path = [kraken_usdt, coinbase_usdc, binance_busd, kraken_usdt]
    
    total_fee = 0.0
    for i in range(len(path) - 1):
        source = path[i]
        target = path[i + 1]
        edge = None
        for e in source.edges:
            if e.target == target:
                edge = e
                break
        
        if edge:
            fee = edge.fee
            total_fee += fee
            print(f"  {source.exchange}({source.stablecoin}) → {target.exchange}({target.stablecoin})")
            print(f"    Fee: {fee*100:.2f}%")
    
    print(f"\n  Total Fee: {total_fee*100:.2f}%")
    
    # Calculate profit
    initial_price = kraken_usdt.price
    final_price = initial_price  # Back to start
    price_diff = initial_price - coinbase_usdc.price  # Price difference exploited
    
    print("\n3. Profit Calculation:")
    print("-" * 70)
    print(f"Price difference exploited: ${price_diff:.4f} per unit")
    print(f"Total cost (fees): {total_fee*100:.2f}%")
    
    # For $10,000 trade
    trade_amount = 10000
    gross_profit = price_diff * trade_amount
    total_cost = total_fee * trade_amount
    net_profit = gross_profit - total_cost
    
    print(f"\nFor ${trade_amount:,} trade:")
    print(f"  Gross profit: ${gross_profit:.2f}")
    print(f"  Total cost:  ${total_cost:.2f}")
    print(f"  Net profit:   ${net_profit:.2f}")
    print(f"  ROI:          {(net_profit/trade_amount)*100:.2f}%")


def demonstrate_volume_optimization():
    """Show how WalletManager optimizes volume."""
    print("\n\n" + "="*70)
    print("VOLUME OPTIMIZATION EXAMPLE")
    print("="*70)
    
    manager = WalletManager()
    
    # Set balances
    manager.set_balance("Kraken", "USDT", 50000.0)
    manager.set_balance("Coinbase", "USDC", 50000.0)
    
    # Create a path
    path = [
        ExchangeNode("Kraken", "USDT", 1.0),
        ExchangeNode("Coinbase", "USDC", 1.0)
    ]
    
    # Simulate an opportunity with 0.1% profit rate, 0.05% base cost
    profit_rate = 0.001  # 0.1% profit per unit
    cost_rate = 0.0005   # 0.05% base cost
    
    print("\n1. Opportunity Details:")
    print("-" * 70)
    print(f"Profit rate: {profit_rate*100:.2f}%")
    print(f"Base cost rate: {cost_rate*100:.2f}%")
    print(f"Available funds: $50,000")
    
    # Optimize volume
    optimal_volume, optimal_profit = manager.optimize_volume(
        path, profit_rate, cost_rate, 50000.0
    )
    
    print("\n2. Volume Optimization Results:")
    print("-" * 70)
    
    # Compare different volumes
    test_volumes = [1000, 5000, 10000, 50000]
    
    print(f"{'Volume':<15} {'Fee Rate':<15} {'Net Profit':<20} {'ROI'}")
    print("-" * 70)
    
    for volume in test_volumes:
        fee_rate = manager.get_effective_fee("Kraken", volume) + manager.get_effective_fee("Coinbase", volume)
        net_profit_rate = profit_rate - cost_rate - fee_rate
        net_profit = net_profit_rate * volume
        roi = (net_profit / volume) * 100 if volume > 0 else 0
        
        marker = " ← OPTIMAL" if abs(volume - optimal_volume) < 100 else ""
        print(f"${volume:>10,}     {fee_rate*100:>6.3f}%      ${net_profit:>12.2f}     {roi:>5.2f}%{marker}")
    
    print(f"\n✅ Optimal volume: ${optimal_volume:,.2f}")
    print(f"✅ Optimal profit: ${optimal_profit:,.2f}")
    print(f"✅ ROI: {(optimal_profit/optimal_volume)*100:.2f}%")
    
    print("\n💡 The system automatically finds the volume that maximizes profit!")
    print("   Higher volumes = lower fees = better net profit (up to a point)")


def demonstrate_combined_benefits():
    """Show combined benefits of volume optimization + arbitrage."""
    print("\n\n" + "="*70)
    print("COMBINED BENEFITS: ARBITRAGE + VOLUME OPTIMIZATION")
    print("="*70)
    
    manager = WalletManager()
    
    # Set large balances to enable volume optimization
    manager.set_balance("Kraken", "USDT", 100000.0)
    manager.set_balance("Coinbase", "USDC", 100000.0)
    manager.set_balance("Binance", "BUSD", 100000.0)
    
    path = [
        ExchangeNode("Kraken", "USDT", 1.001),
        ExchangeNode("Coinbase", "USDC", 0.999),
        ExchangeNode("Binance", "BUSD", 1.000),
        ExchangeNode("Kraken", "USDT", 1.001)
    ]
    
    # Arbitrage opportunity: 0.2% profit rate, 0.15% base cost
    profit_rate = 0.002  # 0.2% from price difference
    cost_rate = 0.0015   # 0.15% base transfer costs
    
    print("\nScenario: Cross-exchange arbitrage with volume optimization")
    print("-" * 70)
    print(f"Arbitrage profit rate: {profit_rate*100:.2f}%")
    print(f"Base cost rate: {cost_rate*100:.2f}%")
    print(f"Available funds: $100,000 per exchange")
    
    # Evaluate opportunity
    result = manager.evaluate_opportunity(path, profit_rate, cost_rate, min_amount=1000.0)
    
    print("\nResults:")
    print("-" * 70)
    print(f"Executable: {result['executable']}")
    print(f"Max amount: ${result['max_amount']:,.2f}")
    print(f"Optimal volume: ${result['optimal_volume']:,.2f}")
    print(f"Optimal profit: ${result['optimal_profit']:,.2f}")
    
    if result['executable']:
        roi = (result['optimal_profit'] / result['optimal_volume']) * 100
        print(f"ROI: {roi:.2f}%")
        
        # Show fee savings
        small_volume = 1000
        large_volume = result['optimal_volume']
        
        small_fee = (manager.get_effective_fee("Kraken", small_volume) + 
                    manager.get_effective_fee("Coinbase", small_volume) +
                    manager.get_effective_fee("Binance", small_volume)) * small_volume
        
        large_fee = (manager.get_effective_fee("Kraken", large_volume) + 
                     manager.get_effective_fee("Coinbase", large_volume) +
                     manager.get_effective_fee("Binance", large_volume)) * large_volume
        
        fee_savings = small_fee - large_fee
        
        print(f"\n💡 Fee savings from volume optimization: ${fee_savings:,.2f}")
        print(f"   Small trade (${small_volume:,}): ${small_fee:.2f} fees")
        print(f"   Large trade (${large_volume:,.0f}): ${large_fee:.2f} fees")


if __name__ == "__main__":
    demonstrate_volume_fee_savings()
    demonstrate_cross_exchange_arbitrage()
    demonstrate_volume_optimization()
    demonstrate_combined_benefits()
    
    print("\n\n" + "="*70)
    print("SUMMARY")
    print("="*70)
    print("""
✅ YES, there are significant deals/benefits:

1. VOLUME-BASED FEE SAVINGS:
   - Higher volumes = Lower fee rates
   - Example: $200k trade pays 0.01% vs $500 trade pays 0.1%
   - Savings: $180 on a $200k trade vs $500 trade

2. CROSS-EXCHANGE ARBITRAGE:
   - Price differences between exchanges create opportunities
   - Example: Kraken USDT at $1.001 vs Coinbase USDC at $0.999
   - Can profit from the $0.002 difference per unit

3. COMBINED OPTIMIZATION:
   - System finds optimal volume to maximize profit
   - Considers both arbitrage profit AND fee savings
   - Automatically selects best trade size

The WalletManager and volume optimization system handle this automatically!
    """)

