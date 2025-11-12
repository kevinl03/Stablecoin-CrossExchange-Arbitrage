"""Performance comparison experiment for different algorithms."""

import sys
import os
import time
from typing import Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src import ArbitrageAgent
from src.synthetic_generator import generate_synthetic_graph


def compare_algorithms(
    num_exchanges: int = 4,
    num_stablecoins: int = 3,
    max_depth: int = 5,
    num_runs: int = 5
) -> Dict:
    """
    Compare performance of different algorithms.
    
    Returns:
        Dictionary with comparison results
    """
    results = {
        'dijkstra': {'opportunities': [], 'times': [], 'profits': []},
        'astar': {'opportunities': [], 'times': [], 'profits': []},
        'two_level_dijkstra': {'opportunities': [], 'times': [], 'profits': []},
        'two_level_astar': {'opportunities': [], 'times': [], 'profits': []}
    }
    
    for run in range(num_runs):
        print(f"\nRun {run + 1}/{num_runs}")
        
        # Generate graph
        graph = generate_synthetic_graph(
            num_exchanges=num_exchanges,
            num_stablecoins=num_stablecoins,
            seed=42 + run
        )
        
        agent = ArbitrageAgent(graph)
        start_node = graph.get_all_nodes()[0]
        
        # Test Dijkstra
        start_time = time.time()
        dijkstra_opps = agent.find_arbitrage_paths(
            start_node,
            algorithm='dijkstra',
            max_depth=max_depth
        )
        dijkstra_time = time.time() - start_time
        dijkstra_profit = sum(profit for _, profit, _ in dijkstra_opps)
        
        results['dijkstra']['opportunities'].append(len(dijkstra_opps))
        results['dijkstra']['times'].append(dijkstra_time)
        results['dijkstra']['profits'].append(dijkstra_profit)
        
        # Test A*
        start_time = time.time()
        astar_opps = agent.find_arbitrage_paths(
            start_node,
            algorithm='astar',
            max_depth=max_depth
        )
        astar_time = time.time() - start_time
        astar_profit = sum(profit for _, profit, _ in astar_opps)
        
        results['astar']['opportunities'].append(len(astar_opps))
        results['astar']['times'].append(astar_time)
        results['astar']['profits'].append(astar_profit)
        
        # Test two-level Dijkstra
        start_time = time.time()
        two_level_dijkstra = agent.find_all_opportunities(
            algorithm='dijkstra',
            max_depth=max_depth
        )
        two_level_dijkstra_time = time.time() - start_time
        two_level_dijkstra_profit = sum(profit for _, profit, _, _ in two_level_dijkstra)
        
        results['two_level_dijkstra']['opportunities'].append(len(two_level_dijkstra))
        results['two_level_dijkstra']['times'].append(two_level_dijkstra_time)
        results['two_level_dijkstra']['profits'].append(two_level_dijkstra_profit)
        
        # Test two-level A*
        start_time = time.time()
        two_level_astar = agent.find_all_opportunities(
            algorithm='astar',
            max_depth=max_depth
        )
        two_level_astar_time = time.time() - start_time
        two_level_astar_profit = sum(profit for _, profit, _, _ in two_level_astar)
        
        results['two_level_astar']['opportunities'].append(len(two_level_astar))
        results['two_level_astar']['times'].append(two_level_astar_time)
        results['two_level_astar']['profits'].append(two_level_astar_profit)
    
    return results


def print_comparison(results: Dict):
    """Print comparison results."""
    print("\n" + "=" * 80)
    print("Algorithm Performance Comparison")
    print("=" * 80)
    
    for algo_name, algo_results in results.items():
        opps = algo_results['opportunities']
        times = algo_results['times']
        profits = algo_results['profits']
        
        avg_opps = sum(opps) / len(opps)
        avg_time = sum(times) / len(times)
        avg_profit = sum(profits) / len(profits)
        
        print(f"\n{algo_name.upper()}:")
        print(f"  Avg Opportunities: {avg_opps:.2f}")
        print(f"  Avg Time: {avg_time:.4f}s")
        print(f"  Avg Total Profit: ${avg_profit:.4f}")


if __name__ == "__main__":
    print("Running performance comparison...")
    results = compare_algorithms(
        num_exchanges=4,
        num_stablecoins=3,
        max_depth=5,
        num_runs=5
    )
    print_comparison(results)

