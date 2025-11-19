"""Backtesting engine for historical arbitrage validation."""

from typing import List, Dict, Tuple
from datetime import datetime, timedelta
from src import ArbitrageAgent
from src.models import ArbitrageGraph


class BacktestEngine:
    """Engine for backtesting arbitrage strategies on historical data."""
    
    def __init__(self, historical_data: Dict[datetime, Dict[Tuple[str, str], float]]):
        """
        Initialize backtesting engine.
        
        Args:
            historical_data: Dictionary mapping timestamps to price data
                           Format: {timestamp: {(exchange, stablecoin): price}}
        """
        self.historical_data = historical_data
        self.results: List[Dict] = []
    
    def run_backtest(
        self,
        algorithm: str = 'astar',
        max_depth: int = 5,
        volatility_factor: float = 0.1
    ) -> List[Dict]:
        """
        Run backtest on historical data.
        
        Args:
            algorithm: Algorithm to use ('dijkstra' or 'astar')
            max_depth: Maximum path depth
            volatility_factor: Volatility factor for A*
            
        Returns:
            List of backtest results
        """
        results = []
        
        for timestamp, prices in sorted(self.historical_data.items()):
            # Build graph for this timestamp
            graph = self._build_graph_from_prices(prices)
            agent = ArbitrageAgent(graph)
            
            # Find opportunities
            opportunities = agent.find_all_opportunities(
                algorithm=algorithm,
                max_depth=max_depth,
                volatility_factor=volatility_factor
            )
            
            # Record results
            result = {
                'timestamp': timestamp,
                'num_opportunities': len(opportunities),
                'opportunities': opportunities,
                'graph_stats': agent.get_statistics()
            }
            results.append(result)
        
        self.results = results
        return results
    
    def _build_graph_from_prices(
        self,
        prices: Dict[Tuple[str, str], float],
        default_fee: float = 0.002,
        default_volatility: float = 0.001
    ) -> ArbitrageGraph:
        """Build graph from price data."""
        from src.models import ArbitrageGraph
        
        graph = ArbitrageGraph()
        
        # Add nodes
        for (exchange, stablecoin), price in prices.items():
            graph.add_node(exchange, stablecoin, price)
        
        # Add edges between all nodes
        nodes = graph.get_all_nodes()
        for source_node in nodes:
            for target_node in nodes:
                if source_node == target_node:
                    continue
                
                price_diff = abs(source_node.price - target_node.price)
                volatility_cost = price_diff * default_volatility
                
                graph.add_edge(
                    source_node.exchange,
                    source_node.stablecoin,
                    target_node.exchange,
                    target_node.stablecoin,
                    default_fee,
                    volatility_cost,
                    60.0  # Default transfer time
                )
        
        return graph
    
    def calculate_metrics(self) -> Dict:
        """
        Calculate backtesting metrics.
        
        Returns:
            Dictionary with performance metrics
        """
        if not self.results:
            return {}
        
        total_opportunities = sum(r['num_opportunities'] for r in self.results)
        timestamps_with_opps = sum(1 for r in self.results if r['num_opportunities'] > 0)
        
        # Calculate total potential profit
        total_profit = 0.0
        for result in self.results:
            for path, profit, cost, desc in result['opportunities']:
                total_profit += profit
        
        return {
            'total_timestamps': len(self.results),
            'timestamps_with_opportunities': timestamps_with_opps,
            'total_opportunities': total_opportunities,
            'avg_opportunities_per_timestamp': total_opportunities / len(self.results) if self.results else 0,
            'total_potential_profit': total_profit,
            'avg_profit_per_opportunity': total_profit / total_opportunities if total_opportunities > 0 else 0
        }


def generate_synthetic_historical_data(
    num_days: int = 30,
    exchanges: List[str] = None,
    stablecoins: List[str] = None,
    base_price: float = 1.0,
    volatility: float = 0.01,
    seed: int = None
) -> Dict[datetime, Dict[Tuple[str, str], float]]:
    """
    Generate synthetic historical price data for backtesting.
    
    Args:
        num_days: Number of days of data
        exchanges: List of exchange names
        stablecoins: List of stablecoin symbols
        base_price: Base price for stablecoins
        volatility: Price volatility factor
        seed: Random seed for reproducibility
        
    Returns:
        Dictionary of historical price data
    """
    import random
    from datetime import datetime, timedelta
    
    if seed is not None:
        random.seed(seed)
    
    if exchanges is None:
        exchanges = ['Kraken', 'Coinbase']
    if stablecoins is None:
        stablecoins = ['USDT', 'USDC', 'DAI']
    
    historical_data = {}
    start_date = datetime.now() - timedelta(days=num_days)
    
    # Generate hourly data
    for day in range(num_days):
        for hour in range(24):
            timestamp = start_date + timedelta(days=day, hours=hour)
            prices = {}
            
            for exchange in exchanges:
                for stablecoin in stablecoins:
                    # Generate price with small random variation
                    price = base_price + random.uniform(-volatility, volatility)
                    prices[(exchange, stablecoin)] = price
            
            historical_data[timestamp] = prices
    
    return historical_data

