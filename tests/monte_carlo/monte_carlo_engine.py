"""Monte Carlo simulation engine for robustness testing."""

import random
from typing import List, Dict, Tuple
from src import ArbitrageAgent
from src.models import ArbitrageGraph


class MonteCarloEngine:
    """Engine for Monte Carlo simulation of arbitrage scenarios."""
    
    def __init__(self, num_simulations: int = 100, seed: int = None):
        """
        Initialize Monte Carlo engine.
        
        Args:
            num_simulations: Number of simulations to run
            seed: Random seed for reproducibility
        """
        self.num_simulations = num_simulations
        if seed is not None:
            random.seed(seed)
        self.results: List[Dict] = []
    
    def run_simulation(
        self,
        num_exchanges: int = 3,
        num_stablecoins: int = 2,
        price_volatility: float = 0.01,
        fee_range: Tuple[float, float] = (0.001, 0.005),
        algorithm: str = 'astar',
        max_depth: int = 5
    ) -> List[Dict]:
        """
        Run Monte Carlo simulation.
        
        Args:
            num_exchanges: Number of exchanges
            num_stablecoins: Number of stablecoins
            price_volatility: Price volatility factor
            fee_range: Range for random fees (min, max)
            algorithm: Algorithm to use
            max_depth: Maximum path depth
            
        Returns:
            List of simulation results
        """
        results = []
        
        for sim in range(self.num_simulations):
            # Generate random market conditions
            graph = self._generate_random_graph(
                num_exchanges,
                num_stablecoins,
                price_volatility,
                fee_range
            )
            
            # Run arbitrage detection
            agent = ArbitrageAgent(graph)
            opportunities = agent.find_all_opportunities(
                algorithm=algorithm,
                max_depth=max_depth
            )
            
            # Calculate metrics
            total_profit = sum(profit for _, profit, _, _ in opportunities)
            num_opps = len(opportunities)
            
            result = {
                'simulation': sim,
                'num_opportunities': num_opps,
                'total_profit': total_profit,
                'avg_profit': total_profit / num_opps if num_opps > 0 else 0,
                'graph_size': len(graph.get_all_nodes()),
                'has_opportunities': num_opps > 0
            }
            results.append(result)
        
        self.results = results
        return results
    
    def _generate_random_graph(
        self,
        num_exchanges: int,
        num_stablecoins: int,
        price_volatility: float,
        fee_range: Tuple[float, float]
    ) -> ArbitrageGraph:
        """Generate random graph with market conditions."""
        from src.models import ArbitrageGraph
        
        exchanges = [f"Exchange{i+1}" for i in range(num_exchanges)]
        stablecoins = ['USDT', 'USDC', 'DAI'][:num_stablecoins]
        base_price = 1.0
        
        graph = ArbitrageGraph()
        
        # Add nodes with random prices
        for exchange in exchanges:
            for stablecoin in stablecoins:
                price = base_price + random.uniform(-price_volatility, price_volatility)
                graph.add_node(exchange, stablecoin, price)
        
        # Add edges with random fees
        nodes = graph.get_all_nodes()
        for source_node in nodes:
            for target_node in nodes:
                if source_node == target_node:
                    continue
                
                fee = random.uniform(fee_range[0], fee_range[1])
                price_diff = abs(source_node.price - target_node.price)
                volatility_cost = price_diff * random.uniform(0.0001, 0.001)
                transfer_time = random.uniform(30.0, 300.0)
                
                graph.add_edge(
                    source_node.exchange,
                    source_node.stablecoin,
                    target_node.exchange,
                    target_node.stablecoin,
                    fee,
                    volatility_cost,
                    transfer_time
                )
        
        return graph
    
    def calculate_statistics(self) -> Dict:
        """
        Calculate statistical metrics from simulations.
        
        Returns:
            Dictionary with statistical results
        """
        if not self.results:
            return {}
        
        profits = [r['total_profit'] for r in self.results]
        num_opps = [r['num_opportunities'] for r in self.results]
        has_opps = [r['has_opportunities'] for r in self.results]
        
        # Basic statistics
        success_rate = sum(has_opps) / len(has_opps) if has_opps else 0
        avg_profit = sum(profits) / len(profits) if profits else 0
        avg_opportunities = sum(num_opps) / len(num_opps) if num_opps else 0
        
        # Risk metrics
        if profits:
            sorted_profits = sorted(profits)
            # Value at Risk (VaR) - 5th percentile
            var_5 = sorted_profits[int(len(sorted_profits) * 0.05)] if len(sorted_profits) > 20 else 0
            # Expected shortfall (average of worst 5%)
            worst_5_percent = sorted_profits[:int(len(sorted_profits) * 0.05)]
            expected_shortfall = sum(worst_5_percent) / len(worst_5_percent) if worst_5_percent else 0
        else:
            var_5 = 0
            expected_shortfall = 0
        
        return {
            'num_simulations': len(self.results),
            'success_rate': success_rate,
            'avg_profit': avg_profit,
            'avg_opportunities_per_simulation': avg_opportunities,
            'total_profit': sum(profits),
            'max_profit': max(profits) if profits else 0,
            'min_profit': min(profits) if profits else 0,
            'var_5_percentile': var_5,
            'expected_shortfall': expected_shortfall
        }


def run_stress_test_scenario(
    num_simulations: int = 50,
    high_volatility: bool = True,
    asymmetric_fees: bool = True
) -> Dict:
    """
    Run stress test scenario with adverse conditions.
    
    Args:
        num_simulations: Number of simulations
        high_volatility: Use high price volatility
        asymmetric_fees: Use asymmetric fee structures
        
    Returns:
        Statistical results
    """
    engine = MonteCarloEngine(num_simulations=num_simulations, seed=42)
    
    price_volatility = 0.05 if high_volatility else 0.01
    fee_range = (0.001, 0.01) if asymmetric_fees else (0.001, 0.005)
    
    results = engine.run_simulation(
        num_exchanges=4,
        num_stablecoins=3,
        price_volatility=price_volatility,
        fee_range=fee_range
    )
    
    return engine.calculate_statistics()

