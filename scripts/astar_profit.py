from __future__ import annotations

import heapq
import math
from typing import Dict, Tuple, Optional, List

from graph import NodeId, Adjacency
from profit_headroom_heuristic import profit_headroom_heuristic

# --------------------------------------------------------------
# Types
# --------------------------------------------------------------

State = Tuple[NodeId, float]  # ((exchange, coin), cash_usd)


# --------------------------------------------------------------
# A* profit search (graph-aware, admissible)
# --------------------------------------------------------------

def astar_profit_search(
    start_node: NodeId,
    start_cash_usd: float,
    min_profit_usd: float,
    adj: Adjacency,
    max_depth: int = 6,
) -> Optional[Tuple[List[NodeId], float]]:
    """
    A* search that maximizes profit using a graph-grounded
    profit headroom (economic feasibility) heuristic.

    Assumptions:
      - adj is built ONCE via graph.build_graph()
      - edge["rate"] already includes all fees
      - heuristic is admissible (optimistic upper bound)
    """

    # Priority queue entries:
    # (f, g, depth, node, cash, path)
    pq: list = []

    # Initial costs
    g0 = 0.0
    f0 = 0.0

    heapq.heappush(
        pq,
        (f0, g0, 0, start_node, start_cash_usd, [start_node])
    )

    # Dominance pruning:
    # best_cash[(node, depth)] = best cash seen
    best_cash: Dict[Tuple[NodeId, int], float] = {
        (start_node, 0): start_cash_usd
    }

    while pq:
        f, g, depth, node, cash, path = heapq.heappop(pq)

        # --------------------------------------------------
        # Goal condition:
        # Profit reached AND no further improvement possible
        # --------------------------------------------------
        if cash - start_cash_usd >= min_profit_usd:
            return path, cash

        if depth >= max_depth:
            continue

        # --------------------------------------------------
        # Expand neighbors
        # --------------------------------------------------
        outgoing_edges = adj.get(node, [])
        if not outgoing_edges:
            continue

        for edge in outgoing_edges:
            rate = edge.get("rate", 0.0)
            if rate <= 0:
                continue

            next_node = edge["to"]
            new_cash = cash * rate

            state_key = (next_node, depth + 1)

            # Dominance pruning (cash + depth)
            if new_cash <= best_cash.get(state_key, 0.0):
                continue

            # ------------------------------
            # g(n): realized loss so far
            # ------------------------------
            new_g = -math.log(new_cash / start_cash_usd)

            # ------------------------------
            # h(n): profit headroom heuristic
            # ------------------------------
            # Optimistic remaining rate:
            # take the BEST outgoing rate from next_node
            best_future_rate = 1.0
            for e2 in adj.get(next_node, []):
                r2 = e2.get("rate", 0.0)
                if r2 > best_future_rate:
                    best_future_rate = r2

            h = profit_headroom_heuristic(
                current_cash_usd=new_cash,
                optimistic_remaining_rate=best_future_rate,
                min_remaining_fees_usd=0.0,  # fees already encoded in edges
                min_profit_usd=min_profit_usd,
            )

            # f(n) = g(n) + h(n)
            new_f = new_g + h

            best_cash[state_key] = new_cash

            heapq.heappush(
                pq,
                (
                    new_f,
                    new_g,
                    depth + 1,
                    next_node,
                    new_cash,
                    path + [next_node],
                )
            )

    return None
