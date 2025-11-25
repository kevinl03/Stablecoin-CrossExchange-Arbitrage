#!/usr/bin/env python3
"""Main script to run the stablecoin arbitrage system."""

import sys
import argparse
from datetime import datetime
from src.graph_builder_sparse import SparseGraphBuilder
from src.graph_builder import GraphBuilder
from src.connectors.kraken_connector import KrakenConnector
from src.connectors.coinbase_connector import CoinbaseConnector
from src.algorithms.weighted_astar import weighted_astar_arbitrage
from src.utils.volatility_tracker import VolatilityTracker
from src.utils.metrics_tracker import MetricsTracker
from src import ArbitrageAgent
from src.synthetic_generator import generate_synthetic_graph


def run_synthetic(num_exchanges=4, num_stablecoins=3, algorithm='astar', max_depth=5):
    """Run with synthetic data."""
    print("="*60)
    print("Running with Synthetic Data")
    print("="*60)
    
    graph = generate_synthetic_graph(
        num_exchanges=num_exchanges,
        num_stablecoins=num_stablecoins,
        seed=42
    )
    
    agent = ArbitrageAgent(graph)
    opportunities = agent.find_all_opportunities(
        algorithm=algorithm,
        max_depth=max_depth
    )
    
    print(f"\n✓ Graph: {len(graph.get_all_nodes())} nodes, {len(graph.edges)} edges")
    print(f"✓ Found {len(opportunities)} opportunities")
    
    if opportunities:
        print("\nTop Opportunities:")
        for i, (path, profit, cost, desc) in enumerate(opportunities[:5], 1):
            print(f"\n  {i}. {desc}")
            print(f"     Profit: ${profit:.4f}, Cost: ${cost:.4f}")
            print(f"     ROI: {(profit/cost*100) if cost > 0 else 0:.2f}%")
    
    return opportunities


def run_live(use_sparse=True, algorithm='astar', max_depth=5, save_metrics=True):
    """Run with live exchange data."""
    print("="*60)
    print("Running with Live Exchange Data")
    print("="*60)
    
    try:
        # Create connectors
        print("\n1. Connecting to exchanges...")
        kraken = KrakenConnector()
        coinbase = CoinbaseConnector()
        
        # Build graph
        print("2. Building graph...")
        if use_sparse:
            builder = SparseGraphBuilder()
            print("   Using sparse graph builder (optimized)")
        else:
            builder = GraphBuilder()
            print("   Using dense graph builder")
        
        builder.add_connector(kraken)
        builder.add_connector(coinbase)
        graph = builder.build_graph()
        
        nodes = graph.get_all_nodes()
        if len(nodes) == 0:
            print("   ⚠ No data available. Falling back to synthetic data.")
            return run_synthetic()
        
        print(f"   ✓ Graph: {len(nodes)} nodes, {len(graph.edges)} edges")
        
        # Track volatility
        print("3. Tracking volatility...")
        tracker = VolatilityTracker()
        for node in nodes:
            tracker.update_price(node.exchange, node.stablecoin, node.price)
        
        # Create agent
        print("4. Creating arbitrage agent...")
        agent = ArbitrageAgent(graph)
        
        # Find opportunities
        print(f"5. Searching for opportunities ({algorithm.upper()})...")
        opportunities = agent.find_all_opportunities(
            algorithm=algorithm,
            max_depth=max_depth
        )
        
        print(f"   ✓ Found {len(opportunities)} opportunities")
        
        # Save metrics
        if save_metrics:
            print("6. Saving metrics...")
            metrics = MetricsTracker()
            for path, profit, cost, desc in opportunities:
                metrics.record_opportunity(
                    timestamp=datetime.now(),
                    path=path,
                    predicted_profit=profit,
                    predicted_cost=cost,
                    algorithm=algorithm
                )
            
            metrics.save_to_csv("arbitrage_results.csv")
            try:
                metrics.save_to_excel("arbitrage_results.xlsx")
                print("   ✓ Saved: arbitrage_results.csv, arbitrage_results.xlsx")
            except Exception as e:
                print(f"   ⚠ Excel export: {e}")
        
        # Display results
        if opportunities:
            print("\nTop Opportunities:")
            for i, (path, profit, cost, desc) in enumerate(opportunities[:5], 1):
                print(f"\n  {i}. {desc}")
                print(f"     Profit: ${profit:.4f}, Cost: ${cost:.4f}")
                print(f"     ROI: {(profit/cost*100) if cost > 0 else 0:.2f}%")
        else:
            print("\nNo profitable opportunities found at this time.")
        
        return opportunities
        
    except Exception as e:
        print(f"\n⚠ Error: {e}")
        print("Falling back to synthetic data...")
        return run_synthetic()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Stablecoin Arbitrage Detection System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run with synthetic data
  python run_arbitrage.py --synthetic
  
  # Run with live data
  python run_arbitrage.py --live
  
  # Run with optimizations
  python run_arbitrage.py --live --sparse --algorithm weighted_astar
  
  # Custom parameters
  python run_arbitrage.py --synthetic --exchanges 6 --coins 5 --depth 7
        """
    )
    
    parser.add_argument(
        '--synthetic',
        action='store_true',
        help='Use synthetic data (default: try live, fallback to synthetic)'
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='Use live exchange data'
    )
    parser.add_argument(
        '--sparse',
        action='store_true',
        help='Use sparse graph builder (faster for large graphs)'
    )
    parser.add_argument(
        '--algorithm',
        choices=['dijkstra', 'astar', 'weighted_astar'],
        default='astar',
        help='Search algorithm to use (default: astar)'
    )
    parser.add_argument(
        '--depth',
        type=int,
        default=5,
        help='Maximum search depth (default: 5)'
    )
    parser.add_argument(
        '--exchanges',
        type=int,
        default=4,
        help='Number of exchanges for synthetic data (default: 4)'
    )
    parser.add_argument(
        '--coins',
        type=int,
        default=3,
        help='Number of stablecoins for synthetic data (default: 3)'
    )
    parser.add_argument(
        '--no-metrics',
        action='store_true',
        help='Skip saving metrics to file'
    )
    
    args = parser.parse_args()
    
    # Determine mode
    if args.synthetic:
        run_synthetic(
            num_exchanges=args.exchanges,
            num_stablecoins=args.coins,
            algorithm=args.algorithm,
            max_depth=args.depth
        )
    elif args.live:
        run_live(
            use_sparse=args.sparse,
            algorithm=args.algorithm,
            max_depth=args.depth,
            save_metrics=not args.no_metrics
        )
    else:
        # Default: try live, fallback to synthetic
        print("No mode specified. Trying live data first...")
        try:
            run_live(
                use_sparse=args.sparse,
                algorithm=args.algorithm,
                max_depth=args.depth,
                save_metrics=not args.no_metrics
            )
        except:
            print("\nFalling back to synthetic data...")
            run_synthetic(
                num_exchanges=args.exchanges,
                num_stablecoins=args.coins,
                algorithm=args.algorithm,
                max_depth=args.depth
            )


if __name__ == "__main__":
    main()

