"""Synthetic instance generator for testing arbitrage algorithms."""

import random
from typing import List, Tuple, Optional
from .models.graph import ArbitrageGraph


def generate_synthetic_graph(
    num_exchanges: int = 4,
    num_stablecoins: int = 3,
    base_price: float = 1.0,
    price_variance: float = 0.01,
    fee_range: Tuple[float, float] = (0.001, 0.005),
    volatility_range: Tuple[float, float] = (0.0001, 0.001),
    seed: Optional[int] = None
) -> ArbitrageGraph:
    """
    Generate a synthetic arbitrage graph for testing.
    
    Args:
        num_exchanges: Number of exchanges
        num_stablecoins: Number of stablecoins
        base_price: Base price for stablecoins
        price_variance: Maximum variance from base price
        fee_range: Range for transfer fees (min, max)
        volatility_range: Range for volatility costs (min, max)
        seed: Random seed for reproducibility
        
    Returns:
        Generated ArbitrageGraph
    """
    if seed is not None:
        random.seed(seed)
    
    graph = ArbitrageGraph()
    exchanges = [f"Exchange{i+1}" for i in range(num_exchanges)]
    stablecoins = [f"USDT", "USDC", "DAI"][:num_stablecoins]
    
    # Add nodes with slightly varying prices
    for exchange in exchanges:
        for stablecoin in stablecoins:
            # Price varies slightly from base
            price = base_price + random.uniform(-price_variance, price_variance)
            graph.add_node(exchange, stablecoin, price)
    
    # Add edges with random costs
    nodes = graph.get_all_nodes()
    for source_node in nodes:
        for target_node in nodes:
            if source_node == target_node:
                continue
            
            fee = random.uniform(fee_range[0], fee_range[1])
            volatility = random.uniform(volatility_range[0], volatility_range[1])
            transfer_time = random.uniform(30.0, 300.0)  # 30s to 5min
            
            graph.add_edge(
                source_node.exchange,
                source_node.stablecoin,
                target_node.exchange,
                target_node.stablecoin,
                fee,
                volatility,
                transfer_time
            )
    
    return graph


def generate_adversarial_instance(
    num_exchanges: int = 4,
    num_stablecoins: int = 3,
    high_volatility: bool = True,
    asymmetric_fees: bool = True,
    illiquid_markets: bool = False,
    seed: Optional[int] = None
) -> ArbitrageGraph:
    """
    Generate an adversarial test instance with challenging conditions.
    
    Args:
        num_exchanges: Number of exchanges
        num_stablecoins: Number of stablecoins
        high_volatility: Whether to use high volatility costs
        asymmetric_fees: Whether to use asymmetric fee structures
        illiquid_markets: Whether to simulate illiquid markets (high costs)
        seed: Random seed
        
    Returns:
        Generated ArbitrageGraph with adversarial conditions
    """
    if seed is not None:
        random.seed(seed)
    
    graph = ArbitrageGraph()
    exchanges = [f"Exchange{i+1}" for i in range(num_exchanges)]
    stablecoins = [f"USDT", "USDC", "DAI"][:num_stablecoins]
    
    # Add nodes
    for exchange in exchanges:
        for stablecoin in stablecoins:
            # Prices can vary more in adversarial scenarios
            if high_volatility:
                price = 1.0 + random.uniform(-0.05, 0.05)  # ±5%
            else:
                price = 1.0 + random.uniform(-0.01, 0.01)  # ±1%
            graph.add_node(exchange, stablecoin, price)
    
    # Add edges with challenging costs
    nodes = graph.get_all_nodes()
    for source_node in nodes:
        for target_node in nodes:
            if source_node == target_node:
                continue
            
            if asymmetric_fees:
                # Asymmetric: some paths very expensive
                if random.random() < 0.3:  # 30% chance of high fee
                    fee = random.uniform(0.01, 0.05)  # 1-5%
                else:
                    fee = random.uniform(0.001, 0.003)  # 0.1-0.3%
            else:
                fee = random.uniform(0.001, 0.005)
            
            if high_volatility:
                volatility = random.uniform(0.001, 0.01)  # High volatility
            else:
                volatility = random.uniform(0.0001, 0.001)
            
            if illiquid_markets:
                # Illiquid markets have very high costs
                fee *= 2
                volatility *= 2
            
            transfer_time = random.uniform(60.0, 600.0)  # 1-10 minutes
            
            graph.add_edge(
                source_node.exchange,
                source_node.stablecoin,
                target_node.exchange,
                target_node.stablecoin,
                fee,
                volatility,
                transfer_time
            )
    
    return graph

