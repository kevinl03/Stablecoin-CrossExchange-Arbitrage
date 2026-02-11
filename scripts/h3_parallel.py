
"""
Heuristic #3: Parallel search from multiple random starting points.

Idea:
  - Instead of using a single heuristic value, run A* from multiple
    random starting points in parallel
  - This explores the search space more broadly
  - Returns the best result across all parallel searches

This module:
  - Selects 3 random starting nodes from the graph
  - Runs A* search from each in parallel using threads
  - Compares results and returns the best path found
"""

from __future__ import annotations

import random
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional, List, Tuple

from scripts.graph import NodeId, build_graph
from scripts.astar_vol import astar_best_path_with_liquidity, PlanResult

import logging
logger = logging.getLogger(__name__)


def parallel_search_from_random_starts(
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
    heuristic: str = "h1_liquidity",  # Base heuristic to use for each search
    num_starts: int = 3,  # Number of random starting points
) -> Optional[PlanResult]:
    """
    Run A* search from multiple random starting points in parallel.
    
    Args:
        liquid_cash_usd: Initial capital in USD
        max_depth: Maximum path depth
        max_time_sec: Maximum time constraint
        min_profit_usd: Minimum profit threshold
        heuristic: Base heuristic to use (h1_liquidity or h2_slippage)
        num_starts: Number of random starting points to try
    
    Returns:
        Best PlanResult found across all parallel searches, or None
    """
    # Build graph to get available nodes
    # Pass portfolio size for accurate fee calculations
    nodes, adj = build_graph(portfolio_size_usd=liquid_cash_usd)
    if not nodes:
        return None
    
    # Get list of available nodes
    available_nodes = list(nodes.keys())
    if len(available_nodes) < num_starts:
        num_starts = len(available_nodes)
    
    # Select random starting points
    random_starts = random.sample(available_nodes, num_starts)
    
    # Log which starting points were selected
    logger.info(f"Parallel search: Selected {num_starts} random starting points:")
    for i, start in enumerate(random_starts, 1):
        logger.info(f"  {i}. {start[0]}:{start[1]}")
    
    # Thread-safe result storage
    results_lock = threading.Lock()
    best_result: Optional[PlanResult] = None
    best_start: Optional[NodeId] = None
    
    def run_search_from_start(start_node: NodeId) -> Optional[PlanResult]:
        """Run A* search from a single starting point."""
        try:
            result = astar_best_path_with_liquidity(
                start_node=start_node,
                liquid_cash_usd=liquid_cash_usd,
                max_depth=max_depth,
                max_time_sec=max_time_sec,
                min_profit_usd=min_profit_usd,
                heuristic=heuristic,
            )
            return result
        except Exception:
            return None
    
    # Run searches in parallel
    with ThreadPoolExecutor(max_workers=num_starts) as executor:
        # Submit all searches
        future_to_start = {
            executor.submit(run_search_from_start, start): start
            for start in random_starts
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_start):
            start_node = future_to_start[future]
            try:
                result = future.result()
                if result:
                    with results_lock:
                        # Keep the result with highest final cash
                        if best_result is None or result.final_cash_usd > best_result.final_cash_usd:
                            best_result = result
                            best_start = start_node
                            logger.info(
                                f"New best from {start_node[0]}:{start_node[1]}: "
                                f"profit=${result.final_cash_usd - liquid_cash_usd:.2f}"
                            )
            except Exception:
                continue
    
    if best_result:
        logger.info(
            f"Parallel search completed: Best result from {best_start[0]}:{best_start[1]}, "
            f"profit=${best_result.final_cash_usd - liquid_cash_usd:.2f}"
        )
    
    return best_result


def parallel_search_heuristic_cost(
    exchange_name: str,
    coin: str,
    order_notional_usd: float,
    remaining_time_sec: float,
) -> float:
    """
    Heuristic cost function for parallel search.
    
    This is a placeholder - parallel search doesn't use a traditional
    heuristic value. Instead, it runs multiple searches in parallel.
    
    Returns 0.0 as it's not used in the traditional sense.
    """
    return 0.0

