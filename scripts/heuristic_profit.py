# heuristic_profit.py — Profit headroom / economic feasibility heuristic

"""
Heuristic #3: profit headroom (economic feasibility).

Idea:
  - Some arbitrage paths are economically doomed from the start.
  - Even under best-case assumptions (perfect prices, zero slippage),
    they cannot generate enough profit to justify further exploration.
  - Exploring such paths wastes computation and does not improve results.

This heuristic answers:
  “Even if everything goes perfectly from here, can this path still
   achieve the minimum required profit?”

Design constraints (IMPORTANT):
  - Must be admissible (never prune a truly optimal path)
  - Must rely only on information available in the graph
  - Must NOT assume future unseen exchanges, prices, or cash-out to USD
"""

from __future__ import annotations


# --------------------------------------------------------------
# 0. Heuristic tuning parameters
# --------------------------------------------------------------

# Binary pruning penalty:
#   - infeasible → huge penalty
#   - feasible   → 0
#
# Large enough to dominate any realistic g(n)
HUGE_PROFIT_PENALTY: float = 1e6


# --------------------------------------------------------------
# 1. Profit headroom heuristic
# --------------------------------------------------------------

def profit_headroom_heuristic(
    current_cash_usd: float,
    optimistic_remaining_rate: float,
    min_profit_usd: float,
) -> float:
    """
    Heuristic h3(n): penalize economically infeasible paths.

    This computes an optimistic upper bound on the *maximum* profit
    achievable from the current node using only best-case assumptions.

    Args:
        current_cash_usd:
            Current portfolio value at node n (USD-equivalent).
        optimistic_remaining_rate:
            Optimistic upper bound on remaining multiplicative gain.
            This MUST be derived from existing graph edges
            (e.g., best outgoing edge rate).
        min_profit_usd:
            Minimum profit required for a path to be considered viable.

    Returns:
        HUGE_PROFIT_PENALTY if the path cannot possibly reach
        min_profit_usd even under best-case assumptions,
        otherwise 0.0.

    Admissibility:
        - Assumes best possible remaining rate.
        - Ignores future fees already encoded in edge rates.
        - Never underestimates achievable profit.
    """

    # Invalid or bankrupt state → prune
    if current_cash_usd <= 0.0:
        return HUGE_PROFIT_PENALTY

    # Best-case final cash under optimistic assumptions
    max_possible_cash = current_cash_usd * optimistic_remaining_rate

    # Best-case additional profit from this point
    max_possible_profit = max_possible_cash - current_cash_usd

    # If even the optimistic case cannot reach required profit → prune
    if max_possible_profit < min_profit_usd:
        return HUGE_PROFIT_PENALTY

    return 0.0
