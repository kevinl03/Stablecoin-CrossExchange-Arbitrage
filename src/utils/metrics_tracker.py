"""Comprehensive metrics tracking and output system for arbitrage analysis."""

from datetime import datetime
from typing import List, Dict, Optional, Tuple
import pandas as pd
from ..models.exchange_node import ExchangeNode


class MetricsTracker:
    """Tracks arbitrage opportunities and performance metrics."""
    
    def __init__(self, output_file: str = "arbitrage_metrics.csv"):
        """
        Initialize metrics tracker.
        
        Args:
            output_file: Path to CSV output file
        """
        self.output_file = output_file
        self.metrics: List[Dict] = []
        self.algorithm_metrics: List[Dict] = []
        self.market_metrics: List[Dict] = []
    
    def record_opportunity(
        self,
        timestamp: datetime,
        path: List[ExchangeNode],
        predicted_profit: float,
        predicted_cost: float,
        actual_profit: Optional[float] = None,
        execution_time: Optional[float] = None,
        volatility: Optional[float] = None,
        algorithm: str = "astar",
        search_time: Optional[float] = None,
        nodes_explored: Optional[int] = None
    ):
        """
        Record an arbitrage opportunity.
        
        Args:
            timestamp: When the opportunity was detected
            path: List of nodes in the arbitrage path
            predicted_profit: Predicted profit
            predicted_cost: Predicted total cost
            actual_profit: Actual profit if executed (optional)
            execution_time: Time to execute the arbitrage (optional)
            volatility: Market volatility at time of opportunity (optional)
            algorithm: Algorithm used (astar, dijkstra, weighted_astar)
            search_time: Time taken to find opportunity (optional)
            nodes_explored: Number of nodes explored (optional)
        """
        metric = {
            'timestamp': timestamp,
            'path_length': len(path),
            'exchanges': ' -> '.join([node.exchange for node in path]),
            'coins': ' -> '.join([node.stablecoin for node in path]),
            'predicted_profit': predicted_profit,
            'predicted_cost': predicted_cost,
            'actual_profit': actual_profit,
            'execution_time': execution_time,
            'volatility': volatility,
            'roi': predicted_profit / predicted_cost if predicted_cost > 0 else 0,
            'algorithm': algorithm,
            'search_time': search_time,
            'nodes_explored': nodes_explored
        }
        self.metrics.append(metric)
    
    def record_algorithm_performance(
        self,
        timestamp: datetime,
        algorithm: str,
        search_time: float,
        nodes_explored: int,
        opportunities_found: int,
        graph_size: int
    ):
        """
        Record algorithm performance metrics.
        
        Args:
            timestamp: When the search was performed
            algorithm: Algorithm name
            search_time: Time taken for search
            nodes_explored: Number of nodes explored
            opportunities_found: Number of opportunities found
            graph_size: Total number of nodes in graph
        """
        metric = {
            'timestamp': timestamp,
            'algorithm': algorithm,
            'search_time': search_time,
            'nodes_explored': nodes_explored,
            'opportunities_found': opportunities_found,
            'graph_size': graph_size,
            'exploration_rate': nodes_explored / graph_size if graph_size > 0 else 0
        }
        self.algorithm_metrics.append(metric)
    
    def record_market_conditions(
        self,
        timestamp: datetime,
        exchange: str,
        coin: str,
        price: float,
        volatility: float,
        spread: Optional[float] = None
    ):
        """
        Record market conditions.
        
        Args:
            timestamp: When the data was recorded
            exchange: Exchange name
            coin: Stablecoin symbol
            price: Current price
            volatility: Current volatility
            spread: Bid-ask spread (optional)
        """
        metric = {
            'timestamp': timestamp,
            'exchange': exchange,
            'coin': coin,
            'price': price,
            'volatility': volatility,
            'spread': spread
        }
        self.market_metrics.append(metric)
    
    def save_to_csv(self, filename: Optional[str] = None):
        """
        Save all metrics to CSV file.
        
        Args:
            filename: Optional custom filename
        """
        if filename is None:
            filename = self.output_file
        
        if self.metrics:
            df = pd.DataFrame(self.metrics)
            df.to_csv(filename, index=False)
    
    def save_to_excel(self, filename: str = "arbitrage_report.xlsx"):
        """
        Save all metrics to Excel file with multiple sheets.
        
        Args:
            filename: Excel filename
        """
        # Check if we have any data to write
        has_data = bool(self.metrics or self.algorithm_metrics or self.market_metrics)
        
        if not has_data:
            # Create a minimal Excel file with a note
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                note_df = pd.DataFrame([{
                    'Note': 'No metrics recorded yet',
                    'Timestamp': datetime.now().isoformat()
                }])
                note_df.to_excel(writer, sheet_name='Info', index=False)
            return
        
        with pd.ExcelWriter(filename, engine='openpyxl') as writer:
            # Opportunities sheet
            if self.metrics:
                df_opps = pd.DataFrame(self.metrics)
                df_opps.to_excel(writer, sheet_name='Opportunities', index=False)
                
                # Summary statistics
                summary = {
                    'Total Opportunities': len(df_opps),
                    'Total Predicted Profit': df_opps['predicted_profit'].sum(),
                    'Average Predicted Profit': df_opps['predicted_profit'].mean(),
                    'Average ROI': df_opps['roi'].mean(),
                    'Median ROI': df_opps['roi'].median(),
                    'Max ROI': df_opps['roi'].max(),
                    'Min ROI': df_opps['roi'].min()
                }
                
                if 'actual_profit' in df_opps and df_opps['actual_profit'].notna().any():
                    actual_profits = df_opps['actual_profit'].dropna()
                    summary['Total Actual Profit'] = actual_profits.sum()
                    summary['Average Actual Profit'] = actual_profits.mean()
                    summary['Success Rate'] = (actual_profits > 0).sum() / len(actual_profits) if len(actual_profits) > 0 else None
                
                pd.DataFrame([summary]).to_excel(writer, sheet_name='Summary', index=False)
            else:
                # Create empty summary if no opportunities
                empty_summary = pd.DataFrame([{
                    'Note': 'No opportunities recorded',
                    'Timestamp': datetime.now().isoformat()
                }])
                empty_summary.to_excel(writer, sheet_name='Summary', index=False)
            
            # Algorithm performance sheet
            if self.algorithm_metrics:
                df_algo = pd.DataFrame(self.algorithm_metrics)
                df_algo.to_excel(writer, sheet_name='Algorithm Performance', index=False)
            
            # Market conditions sheet
            if self.market_metrics:
                df_market = pd.DataFrame(self.market_metrics)
                df_market.to_excel(writer, sheet_name='Market Conditions', index=False)
    
    def get_summary_statistics(self) -> Dict:
        """
        Get summary statistics.
        
        Returns:
            Dictionary of summary statistics
        """
        if not self.metrics:
            return {}
        
        df = pd.DataFrame(self.metrics)
        summary = {
            'total_opportunities': len(df),
            'total_predicted_profit': float(df['predicted_profit'].sum()),
            'average_predicted_profit': float(df['predicted_profit'].mean()),
            'average_roi': float(df['roi'].mean()),
            'median_roi': float(df['roi'].median())
        }
        
        if 'actual_profit' in df and df['actual_profit'].notna().any():
            actual_profits = df['actual_profit'].dropna()
            summary['total_actual_profit'] = float(actual_profits.sum())
            summary['average_actual_profit'] = float(actual_profits.mean())
            summary['success_rate'] = float((actual_profits > 0).sum() / len(actual_profits))
        
        return summary
    
    def clear_metrics(self):
        """Clear all recorded metrics."""
        self.metrics.clear()
        self.algorithm_metrics.clear()
        self.market_metrics.clear()

