## Heuristic h3: Profit Headroom / Economic Feasibility

### Motivation

In arbitrage search, **not every path is worth exploring**.

Some paths are *economically doomed from the start*:  
even under **best-case assumptions** (perfect prices, zero slippage, instant execution),
they cannot generate enough profit to meet the user’s minimum profit requirement.

Exploring such paths:

- Wastes computation
- Increases search time
- Does not improve solution quality

This heuristic answers the question:

> **“Even if everything goes perfectly from here, can this path still achieve the required profit?”**

If the answer is **no**, the path should be pruned immediately.

### Design Constraints

This heuristic is designed with the following strict constraints:

- **Admissible**: never prunes a truly optimal path  
- **Graph-grounded**: relies only on information already present in the graph  
- **Optimistic**: assumes best-case future gains  
- **No lookahead assumptions**:  
  - no unseen exchanges  
  - no future prices  
  - no forced cash-out to USD  

### Core Idea

Heuristic **h3** computes an **optimistic upper bound** on the *maximum profit*
that could still be achieved from the current state.

If even this optimistic bound is **below the required minimum profit**,  
the path is **economically infeasible** and can be safely pruned.

### Definitions

Let the current search state be:

n = (node, current_cash_usd)


Let:

- `current_cash_usd` = current portfolio value at node `n`
- `min_profit_usd` = minimum profit required by the user
- `optimistic_remaining_rate` = optimistic upper bound on future multiplicative gain  
  (derived from existing graph edges)

### Optimistic Profit Upper Bound

We compute the **best-case final cash** as:

\[
\text{max\_possible\_cash} = \text{current\_cash\_usd} \times \text{optimistic\_remaining\_rate}
\]

The **maximum possible remaining profit** is:

\[
\text{max\_possible\_profit} =
\text{max\_possible\_cash} - \text{current\_cash\_usd}
\]

This assumes:

- The best available outgoing rate is achieved
- No additional losses beyond those already encoded in the graph
- Perfect execution from this point onward

### Heuristic Cost Function

The profit headroom heuristic is defined as:

\[
h_3(n) =
\begin{cases}
\text{HUGE\_PROFIT\_PENALTY}, & \text{if } \text{max\_possible\_profit} < \text{min\_profit\_usd} \\
0, & \text{otherwise}
\end{cases}
\]

Where:

- `HUGE_PROFIT_PENALTY` is a very large constant (e.g., `1e6`)
- The heuristic is **binary**:
  - feasible → `0`
  - infeasible → prune

### Why h3 Is Admissible

This heuristic is **admissible** because it:

- Uses an **optimistic upper bound** on future gains
- Assumes the **best possible remaining rate**
- Never underestimates achievable profit
- Only prunes paths that **cannot possibly** meet the profit constraint

Therefore, **no valid optimal path is ever removed**.

### How h3 Works in Practice

| Situation | Effect of h3 |
|---------|-------------|
| Large remaining upside | No penalty |
| Marginal profit potential | Allowed to continue |
| Guaranteed loss or insufficient upside | Immediate pruning |
| Bankrupt state | Pruned |
| Path cannot meet minimum profit | Strongly discouraged |

This results in **aggressive but safe pruning** of hopeless branches.

### Integration with A\* Search

The planner uses a profit-maximizing A\* formulation:

\[
f(n) = g(n) + h_3(n)
\]

Where:

- `g(n)` = realized loss so far (−log of cumulative rate)
- `h_3(n)` = profit headroom heuristic

Because `h_3(n)` is either `0` or a huge penalty, it acts as a **hard feasibility filter**
inside the A\* search.

### Why h3 Is Necessary

Without h3, the search may:

- Explore long chains with no chance of profitability
- Waste time expanding states that cannot satisfy user constraints
- Scale poorly as graph size increases

h3 ensures that **only economically viable paths** are explored.

### When Should a User Enable h3?

#### Strongly Recommended When

- A minimum profit threshold is required
- Search space is large
- Computational efficiency matters
- User wants fast rejection of infeasible trades

#### Less Useful When

- User wants to explore *all* possible paths
- Minimum profit is set to zero
- Graph is very small

### Summary

Heuristic **h3**:

- Enforces **economic feasibility**
- Uses a strict but admissible upper bound
- Safely prunes hopeless paths
- Improves search efficiency without sacrificing optimality
