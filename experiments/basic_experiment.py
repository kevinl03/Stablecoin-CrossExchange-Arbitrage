"""Basic experiment script for testing arbitrage algorithms."""

import sys
import os
import time

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import ArbitrageAgent, GraphBuilder, KrakenConnector, CoinbaseConnector
from src.synthetic_generator import generate_synthetic_graph, generate_adversarial_instance


def run_synthetic_experiment():
    """Run experiment with synthetic data."""
    print("=" * 60)
    print("Synthetic Graph Experiment")
    print("=" * 60)
    
    # Generate synthetic graph
    graph = generate_synthetic_graph(
        num_exchanges=4,
        num_stablecoins=3,
        seed=42
    )
    
    print(f"\nGraph created: {graph}")
    print(f"Nodes: {len(graph.get_all_nodes())}")
    print(f"Edges: {len(graph.edges)}")
    
    # Create agent
    agent = ArbitrageAgent(graph)
    
    # Test Dijkstra
    print("\n" + "-" * 60)
    print("Testing Dijkstra Algorithm")
    print("-" * 60)
    start_time = time.time()
    
    start_node = graph.get_all_nodes()[0]
    dijkstra_opportunities = agent.find_arbitrage_paths(
        start_node,
        algorithm='dijkstra',
        max_depth=5
    )
    
    dijkstra_time = time.time() - start_time
    print(f"Found {len(dijkstra_opportunities)} opportunities in {dijkstra_time:.4f}s")
    
    if dijkstra_opportunities:
        print("\nTop 3 opportunities:")
        for i, (path, profit, cost) in enumerate(dijkstra_opportunities[:3], 1):
            print(f"\n{i}. Profit: ${profit:.4f}, Cost: ${cost:.4f}")
            print(f"   Path: {' -> '.join(f'{n.exchange}({n.stablecoin})' for n in path)}")
    
    # Test A*
    print("\n" + "-" * 60)
    print("Testing A* Algorithm")
    print("-" * 60)
    start_time = time.time()
    
    astar_opportunities = agent.find_arbitrage_paths(
        start_node,
        algorithm='astar',
        max_depth=5,
        volatility_factor=0.1
    )
    
    astar_time = time.time() - start_time
    print(f"Found {len(astar_opportunities)} opportunities in {astar_time:.4f}s")
    
    if astar_opportunities:
        print("\nTop 3 opportunities:")
        for i, (path, profit, cost) in enumerate(astar_opportunities[:3], 1):
            print(f"\n{i}. Profit: ${profit:.4f}, Cost: ${cost:.4f}")
            print(f"   Path: {' -> '.join(f'{n.exchange}({n.stablecoin})' for n in path)}")
    
    # Test two-level search
    print("\n" + "-" * 60)
    print("Testing Two-Level Search (A*)")
    print("-" * 60)
    start_time = time.time()
    
    all_opportunities = agent.find_all_opportunities(
        algorithm='astar',
        max_depth=5
    )
    
    two_level_time = time.time() - start_time
    print(f"Found {len(all_opportunities)} total opportunities in {two_level_time:.4f}s")
    
    if all_opportunities:
        print("\nTop 5 opportunities:")
        for i, (path, profit, cost, desc) in enumerate(all_opportunities[:5], 1):
            print(f"\n{i}. {desc}")
            print(f"   Profit: ${profit:.4f}, Cost: ${cost:.4f}")
            print(f"   Path length: {len(path)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print(f"Dijkstra: {len(dijkstra_opportunities)} opportunities, {dijkstra_time:.4f}s")
    print(f"A*:       {len(astar_opportunities)} opportunities, {astar_time:.4f}s")
    print(f"Two-Level: {len(all_opportunities)} opportunities, {two_level_time:.4f}s")


def run_adversarial_experiment():
    """Run experiment with adversarial conditions."""
    print("\n" + "=" * 60)
    print("Adversarial Instance Experiment")
    print("=" * 60)
    
    # Generate adversarial graph
    graph = generate_adversarial_instance(
        num_exchanges=4,
        num_stablecoins=3,
        high_volatility=True,
        asymmetric_fees=True,
        seed=42
    )
    
    print(f"\nGraph created: {graph}")
    
    agent = ArbitrageAgent(graph)
    
    # Test with A*
    print("\nTesting A* on adversarial instance...")
    start_time = time.time()
    
    all_opportunities = agent.find_all_opportunities(
        algorithm='astar',
        max_depth=5,
        volatility_factor=0.2  # Higher volatility factor
    )
    
    elapsed = time.time() - start_time
    print(f"Found {len(all_opportunities)} opportunities in {elapsed:.4f}s")
    
    if all_opportunities:
        print("\nTop 3 opportunities:")
        for i, (path, profit, cost, desc) in enumerate(all_opportunities[:3], 1):
            print(f"\n{i}. {desc}")
            print(f"   Profit: ${profit:.4f}, Cost: ${cost:.4f}")


def run_live_experiment():
    """Run experiment with live API data (if available)."""
    print("\n" + "=" * 60)
    print("Live API Experiment")
    print("=" * 60)
    
    try:
        # Create connectors
        kraken = KrakenConnector()
        coinbase = CoinbaseConnector()
        
        # Build graph
        builder = GraphBuilder()
        builder.add_connector(kraken)
        builder.add_connector(coinbase)
        
        print("Fetching live data from exchanges...")
        graph = builder.build_graph()
        
        print(f"\nGraph created: {graph}")
        print(f"Nodes: {len(graph.get_all_nodes())}")
        
        if len(graph.get_all_nodes()) == 0:
            print("No data available from APIs. Using synthetic data instead.")
            return
        
        # Create agent
        agent = ArbitrageAgent(graph)
        
        # Find opportunities
        print("\nSearching for arbitrage opportunities...")
        start_time = time.time()
        
        all_opportunities = agent.find_all_opportunities(
            algorithm='astar',
            max_depth=5
        )
        
        elapsed = time.time() - start_time
        print(f"Found {len(all_opportunities)} opportunities in {elapsed:.4f}s")
        
        if all_opportunities:
            print("\nTop 5 opportunities:")
            for i, (path, profit, cost, desc) in enumerate(all_opportunities[:5], 1):
                print(f"\n{i}. {desc}")
                print(f"   Profit: ${profit:.4f}, Cost: ${cost:.4f}")
        else:
            print("No profitable opportunities found.")
            
    except Exception as e:
        print(f"Error fetching live data: {e}")
        print("This is expected if APIs are unavailable or rate-limited.")


if __name__ == "__main__":
    # Run experiments
    run_synthetic_experiment()
    run_adversarial_experiment()
    run_live_experiment()

