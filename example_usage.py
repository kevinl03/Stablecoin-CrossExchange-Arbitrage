"""Example usage of the stablecoin arbitrage system."""

from src import (
    ArbitrageAgent,
    GraphBuilder,
    KrakenConnector,
    CoinbaseConnector
)
from src.synthetic_generator import generate_synthetic_graph


def example_synthetic():
    """Example using synthetic data."""
    print("Example 1: Synthetic Graph")
    print("-" * 60)
    
    # Generate a synthetic graph
    graph = generate_synthetic_graph(
        num_exchanges=4,
        num_stablecoins=3,
        seed=42
    )
    
    print(f"Created graph with {len(graph.get_all_nodes())} nodes")
    
    # Create arbitrage agent
    agent = ArbitrageAgent(graph)
    
    # Find opportunities using A*
    print("\nSearching for arbitrage opportunities...")
    opportunities = agent.find_all_opportunities(
        algorithm='astar',
        max_depth=5
    )
    
    print(f"\nFound {len(opportunities)} opportunities")
    
    # Display top opportunities
    if opportunities:
        print("\nTop 3 opportunities:")
        for i, (path, profit, cost, desc) in enumerate(opportunities[:3], 1):
            print(f"\n{i}. {desc}")
            print(f"   Net Profit: ${profit:.4f}")
            print(f"   Total Cost: ${cost:.4f}")
            print(f"   Path: {' -> '.join(f'{n.exchange}({n.stablecoin})' for n in path[:5])}...")
            
            # Evaluate with specific amount
            evaluation = agent.evaluate_opportunity(path, amount=100.0)
            if evaluation.get('profitable'):
                print(f"   ROI: {evaluation['roi']:.2f}%")
    
    # Get statistics
    stats = agent.get_statistics()
    print(f"\nGraph Statistics:")
    print(f"  Exchanges: {', '.join(stats['exchanges'])}")
    print(f"  Stablecoins: {', '.join(stats['stablecoins'])}")
    print(f"  Average Price: ${stats['avg_price']:.4f}")


def example_live_api():
    """Example using live API data."""
    print("\n\nExample 2: Live API Data")
    print("-" * 60)
    
    try:
        # Create exchange connectors
        kraken = KrakenConnector()
        coinbase = CoinbaseConnector()
        
        # Build graph from live data
        builder = GraphBuilder()
        builder.add_connector(kraken)
        builder.add_connector(coinbase)
        
        print("Fetching live data from exchanges...")
        graph = builder.build_graph()
        
        if len(graph.get_all_nodes()) == 0:
            print("No data available. Check API connectivity.")
            return
        
        print(f"Created graph with {len(graph.get_all_nodes())} nodes")
        
        # Create agent
        agent = ArbitrageAgent(graph)
        
        # Find opportunities
        print("\nSearching for arbitrage opportunities...")
        opportunities = agent.find_all_opportunities(
            algorithm='astar',
            max_depth=5
        )
        
        print(f"\nFound {len(opportunities)} opportunities")
        
        if opportunities:
            print("\nTop opportunities:")
            for i, (path, profit, cost, desc) in enumerate(opportunities[:3], 1):
                print(f"\n{i}. {desc}")
                print(f"   Net Profit: ${profit:.4f}")
                print(f"   Total Cost: ${cost:.4f}")
        else:
            print("No profitable opportunities found at this time.")
            
    except Exception as e:
        print(f"Error: {e}")
        print("This is expected if APIs are unavailable.")


if __name__ == "__main__":
    # Run examples
    example_synthetic()
    example_live_api()

