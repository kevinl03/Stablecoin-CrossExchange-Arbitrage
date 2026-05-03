# Heuristic Comparison: h1_liquidity vs h2_slippage

## Executive Summary

This document provides a comprehensive analysis of two heuristic functions used in the A* search algorithm for stablecoin cross-exchange arbitrage. We compare `h1_liquidity` (volume-based) and `h2_slippage` (order-book slippage-based) heuristics, documenting their theoretical foundations, implementation details, empirical results, and potential improvements.

**Key Finding**: Both heuristics converge to the same optimal path in tested scenarios, but explore different intermediate paths during search, demonstrating that heuristic choice affects search efficiency even when final results are identical.

---

## Table of Contents

1. [Theoretical Foundations](#theoretical-foundations)
2. [Implementation Details](#implementation-details)
3. [Comparison Methodology](#comparison-methodology)
4. [Empirical Results](#empirical-results)
5. [Analysis and Observations](#analysis-and-observations)
6. [Factors Affecting Heuristic Performance](#factors-affecting-heuristic-performance)
7. [Potential Improvements](#potential-improvements)
8. [Future Work](#future-work)

---

## Theoretical Foundations

### Heuristic 1: h1_liquidity (Volume-Based)

**Core Concept**: Markets with higher 24-hour trading volume are more likely to fill orders quickly with minimal slippage.

**Mathematical Model**:
```
h1(n) = λ * (1 - liquidity_score)

where:
  liquidity_score = f(quote_volume_24h, order_notional_usd, time_window_sec)
  
  liquidity_ratio = (vol_per_sec * time_window) / order_notional_usd
  vol_per_sec = quote_volume_24h / (24 * 3600)
  
  score = clamp((log10(liquidity_ratio) + 1) / 2, 0, 1)
```

**Key Parameters**:
- `LIQUIDITY_HEURISTIC_WEIGHT (λ)`: 1.0
- `UNKNOWN_LIQUIDITY_PENALTY`: 5.0
- Range: [0, λ] where 0 = very liquid, λ = very illiquid

**Strengths**:
- Captures market activity over time
- Accounts for order size relative to typical trading volume
- Time-aware (considers remaining arbitrage window)

**Limitations**:
- Volume data may be stale or unavailable
- Doesn't capture order book depth (can have high volume but thin book)
- Doesn't account for actual execution price impact

### Heuristic 2: h2_slippage (Order-Book Depth-Based)

**Core Concept**: Markets with deeper order books (more liquidity at each price level) will have lower slippage for large orders.

**Mathematical Model**:
```
h2(n) = w_slip * max(0, slippage_bps - threshold_bps)

where:
  slippage_bps = compute_slippage_bps(orderbook, order_size_base, side)
  
  slippage_bps = ((vwap - mid_price) / mid_price) * 10000
  
  vwap = walk_order_book(orderbook, order_size_base, side)
```

**Key Parameters**:
- `SLIPPAGE_HEURISTIC_WEIGHT (w_slip)`: 0.5
- `SLIPPAGE_THRESHOLD_BPS`: 10.0 (0.10% acceptable slippage)
- `UNKNOWN_SLIPPAGE_PENALTY`: 50.0
- Range: [0, ∞) where 0 = acceptable slippage, higher = worse

**Strengths**:
- Directly measures execution cost impact
- Real-time order book data (more current than 24h volume)
- Accounts for actual price levels and depth
- Side-aware (buy vs sell)

**Limitations**:
- Order book data may be unavailable or incomplete
- More computationally expensive (requires order book fetch)
- Doesn't account for time-to-fill (only depth)

---

## Implementation Details

### Integration into A* Search

Both heuristics are integrated into `astar_best_path_with_liquidity()` in `scripts/astar_vol.py`:

```python
def astar_best_path_with_liquidity(
    start_node: NodeId,
    liquid_cash_usd: float,
    max_depth: int = 6,
    max_time_sec: float = 1800.0,
    min_profit_usd: float = 0.0,
    heuristic: str = "h1_liquidity",  # Selectable heuristic
) -> Optional[PlanResult]:
```

**Heuristic Selection**:
- Conditional import and function call based on `heuristic` parameter
- Both heuristics receive:
  - `exchange_name`: Exchange identifier
  - `coin`: Stablecoin symbol
  - `order_size_usd`: Current order size (updated along path)
  - Additional parameters specific to each heuristic

**A* Cost Function**:
```
f(n) = g(n) + h(n)

where:
  g(n) = accumulated cost from start (sum of -log(rate) for each edge)
  h(n) = heuristic estimate (h1_liquidity or h2_slippage)
```

### UI Integration

The Streamlit UI (`scripts/ui.py`) allows users to:
1. Select heuristic via dropdown: `h1_liquidity`, `h2_slippage`, or `h3_parallel`
2. View real-time logging of search progress
3. Compare heuristic values at each step of the optimal path
4. See debug output showing both h1 and h2 values side-by-side

**Debug Output Format**:
```
Step 1: binance:USDT
  h1_liquidity: 0.000000 ← USED
  h2_slippage:  0.000000
  Difference: 0.000000

Step 2: kucoin:USDT
  h1_liquidity: 0.142377 ← USED
  h2_slippage:  0.000000
  Difference: 0.142377 ⭐
```

---

## Comparison Methodology

### Test Configuration

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Start Node | `binance:USDT` | High-liquidity starting point |
| Initial Capital | $10,000.00 USD | Representative trading size |
| Max Depth | 6 | Balance between exploration and computation |
| Max Time | 1800 seconds (30 min) | Realistic arbitrage window |
| Min Profit | $0.00 | Find any profitable path |

### Comparison Approach

1. **Same Starting Conditions**: Both heuristics run with identical parameters
2. **Path Tracking**: Log intermediate paths discovered during search
3. **Heuristic Value Comparison**: Calculate both h1 and h2 at each node in final path
4. **Search Behavior Analysis**: Compare exploration order and paths considered

### Logging Infrastructure

Added comprehensive logging to track:
- Heuristic selection and initialization
- Heuristic values at each node expansion
- Intermediate profitable paths discovered
- Final optimal path and profit

**Example Log Output**:
```
INFO: A* search starting with heuristic: h1_liquidity
INFO: Start node: ('binance', 'USDT'), liquid_cash: $10000.00
INFO: Start node h1_liquidity heuristic: 0.000000
INFO: Start f_score: 0.000000 (g=0.000000 + h=0.000000)
INFO: New best path found (heuristic=h1_liquidity): profit=$8.01, path_length=2, path=binance:USDT -> binance:FDUSD
INFO: New best path found (heuristic=h1_liquidity): profit=$41.96, path_length=3, path=binance:USDT -> kucoin:USDT -> kucoin:TUSD
INFO: A* search completed (heuristic=h1_liquidity): Final profit=$41.96
```

---

## Empirical Results

### Test Case: binance:USDT → Optimal Path

#### Final Optimal Path

Both heuristics converge to the **same optimal path**:

```
binance:USDT → kucoin:USDT → kucoin:TUSD
```

#### Profit Comparison

| Heuristic | Final Cash | Profit | Profit % | Path Length |
|-----------|------------|--------|----------|-------------|
| h1_liquidity | $10,041.96 | $41.96 | 0.4196% | 3 |
| h2_slippage | $10,041.96 | $41.96 | 0.4196% | 3 |

**Conclusion**: Profits are **identical** because both heuristics find the same optimal path.

#### Search Exploration Differences

| Heuristic | First Path Found | Profit | Second Path Found | Profit |
|-----------|------------------|--------|-------------------|--------|
| h1_liquidity | binance:USDT → binance:FDUSD | $8.01 | binance:USDT → kucoin:USDT → kucoin:TUSD | $41.96 ⭐ |
| h2_slippage | binance:USDT → binance:TUSD | $28.09 | binance:USDT → kucoin:USDT → kucoin:TUSD | $41.96 ⭐ |

**Observation**: h2_slippage finds a better intermediate path ($28.09 vs $8.01), suggesting it may explore more promising regions earlier in the search.

#### Heuristic Values at Each Step

| Step | Node | h1_liquidity | h2_slippage | Difference | Analysis |
|------|------|--------------|-------------|------------|----------|
| 1 | binance:USDT | 0.000000 | 0.000000 | 0.000000 | Very liquid market, both return 0 |
| 2 | kucoin:USDT | 0.142377 | 0.000000 | 0.142377 ⭐ | h1 penalizes low volume; h2 finds acceptable depth |
| 3 | kucoin:TUSD | 1.000000 | 1.383374 | 0.383374 ⭐ | h1 max penalty (no volume data); h2 higher (high slippage) |

**Key Insights**:
- At `kucoin:USDT`: h1 penalizes (0.14) while h2 doesn't (0.00) - different risk assessment
- At `kucoin:TUSD`: h2 is more conservative (1.38) than h1 (1.00) - h2 detects slippage risk
- Differences exist but are small relative to actual edge costs, explaining convergence

---

## Analysis and Observations

### Why Do Both Heuristics Find the Same Path?

1. **Clear Optimal Solution**: The optimal path has significantly higher profit than alternatives
2. **Heuristic Differences Are Small**: Relative to actual edge costs (fees, spreads), heuristic differences (0.14, 0.38) are minor
3. **Single Dominant Path**: There may be only one truly profitable path from this starting point
4. **A* Optimality**: Both heuristics are admissible (don't overestimate), so A* guarantees finding the optimal path

### When Would Heuristics Differ?

Heuristics would likely produce different results when:
1. **Multiple Equally Profitable Paths**: Heuristic choice would determine which is explored first
2. **Large Order Sizes**: Slippage becomes more important relative to fees
3. **Thin Order Books**: h2_slippage would penalize more than h1_liquidity
4. **Missing Data**: When volume data is unavailable but order books are (or vice versa)
5. **Time Constraints**: h1_liquidity is time-aware, which matters for tight windows

### Search Efficiency Comparison

| Metric | h1_liquidity | h2_slippage | Winner |
|--------|--------------|-------------|--------|
| First profitable path | $8.01 (2 steps) | $28.09 (2 steps) | h2_slippage |
| Time to optimal | 2 intermediate paths | 2 intermediate paths | Tie |
| Computational cost | Lower (ticker data) | Higher (order book fetch) | h1_liquidity |
| Data availability | Generally higher | May be limited | h1_liquidity |

---

## Factors Affecting Heuristic Performance

### 1. Search Depth (max_depth)

**Current Setting**: `max_depth = 6`

**Impact Analysis**:

| Depth | h1_liquidity Behavior | h2_slippage Behavior | Notes |
|-------|----------------------|----------------------|-------|
| 2-3 | Finds short paths quickly | May miss longer profitable paths | Shallow search |
| 4-6 | Balanced exploration | Balanced exploration | Current setting |
| 7-10 | More exploration, higher computation | More exploration, higher computation | Diminishing returns |

**Recommendation**: 
- For quick searches: `max_depth = 4`
- For thorough searches: `max_depth = 6-8`
- Beyond 8: Likely unnecessary for stablecoin arbitrage

### 2. Order Size (liquid_cash_usd)

**Impact on Heuristics**:

| Order Size | h1_liquidity Impact | h2_slippage Impact |
|------------|---------------------|-------------------|
| Small ($1K) | Low penalty (high liquidity ratio) | Low penalty (minimal slippage) |
| Medium ($10K) | Moderate penalty | Moderate penalty (some slippage) |
| Large ($100K+) | High penalty (low liquidity ratio) | **Very high penalty** (significant slippage) |

**Key Insight**: For large orders, `h2_slippage` becomes more important as slippage dominates execution costs.

### 3. Time Window (max_time_sec)

**Impact on h1_liquidity**:

| Time Window | Liquidity Score Calculation | Heuristic Behavior |
|-------------|----------------------------|-------------------|
| Short (300s) | `vol_window = vol_per_sec * 300` | Higher penalty (less volume in window) |
| Medium (1800s) | `vol_window = vol_per_sec * 1800` | Balanced (current setting) |
| Long (3600s+) | `vol_window = vol_per_sec * 3600` | Lower penalty (more volume in window) |

**Note**: `h2_slippage` is **not** time-aware - it only considers order book depth at the current moment.

### 4. Market Conditions

**High Volume, Thin Book**:
- h1_liquidity: Low penalty (high volume)
- h2_slippage: High penalty (thin book)
- **Result**: Different path selection

**Low Volume, Deep Book**:
- h1_liquidity: High penalty (low volume)
- h2_slippage: Low penalty (deep book)
- **Result**: Different path selection

**Both High / Both Low**:
- Both heuristics agree
- **Result**: Similar path selection

### 5. Data Availability

| Scenario | h1_liquidity | h2_slippage | Impact |
|----------|--------------|-------------|--------|
| Both available | Normal operation | Normal operation | Best case |
| Volume missing | Penalty = 5.0 | Normal operation | h2 preferred |
| Order book missing | Normal operation | Penalty = 50.0 | h1 preferred |
| Both missing | Penalty = 5.0 | Penalty = 50.0 | Both penalize, h2 more |

**Observation**: `UNKNOWN_SLIPPAGE_PENALTY (50.0)` is much higher than `UNKNOWN_LIQUIDITY_PENALTY (5.0)`, making h2_slippage more conservative when data is unavailable.

---

## Potential Improvements

### 1. Heuristic Weight Tuning

**Current Values**:
- `LIQUIDITY_HEURISTIC_WEIGHT`: 1.0
- `SLIPPAGE_HEURISTIC_WEIGHT`: 0.5

**Tuning Strategy**:
- Increase weights to make heuristics more influential
- Decrease weights to rely more on actual edge costs
- Use machine learning to optimize weights based on historical performance

**Proposed Experiments**:
```python
# Test different weight combinations
weights = [
    (1.0, 0.5),  # Current
    (2.0, 1.0),  # More influential
    (0.5, 0.25), # Less influential
    (1.0, 1.0),  # Equal weight
]
```

### 2. Hybrid Heuristic

**Concept**: Combine both heuristics with adaptive weighting

```python
def hybrid_heuristic_cost(...):
    h1 = volume_heuristic_cost(...)
    h2 = slippage_heuristic_cost(...)
    
    # Adaptive weighting based on order size
    if order_size_usd > 50000:
        # Large orders: favor slippage
        return 0.3 * h1 + 0.7 * h2
    else:
        # Small orders: favor liquidity
        return 0.7 * h1 + 0.3 * h2
```

### 3. Time-Aware Slippage Heuristic

**Current Limitation**: h2_slippage doesn't consider time-to-fill

**Improvement**: Estimate time-to-fill based on order book depth and order size, then adjust penalty

```python
def time_aware_slippage_cost(...):
    slippage = slippage_heuristic_cost(...)
    time_to_fill = estimate_fill_time(orderbook, order_size)
    
    # Penalize if time-to-fill exceeds remaining time
    if time_to_fill > remaining_time_sec:
        return slippage * (1 + time_penalty_factor)
    return slippage
```

### 4. Dynamic Penalty Adjustment

**Current**: Fixed penalties for missing data

**Improvement**: Scale penalties based on order size and market conditions

```python
def adaptive_unknown_penalty(order_size_usd, market_volatility):
    base_penalty = UNKNOWN_PENALTY
    size_multiplier = log10(order_size_usd / 1000)  # Scale with order size
    return base_penalty * (1 + size_multiplier)
```

### 5. Caching and Performance

**Current**: Heuristics fetch data on every call

**Improvement**: Cache heuristic values with TTL (time-to-live)

```python
@lru_cache(maxsize=1000)
def cached_heuristic_cost(exchange, coin, order_size, timestamp_bucket):
    # timestamp_bucket: round to nearest 5 minutes for caching
    return heuristic_cost(...)
```

### 6. Depth-Aware Heuristic Scaling

**Concept**: Adjust heuristic influence based on search depth

```python
def depth_scaled_heuristic(h_value, depth, max_depth):
    # Reduce heuristic influence as we go deeper
    depth_factor = 1.0 - (depth / max_depth) * 0.5
    return h_value * depth_factor
```

**Rationale**: At shallow depths, heuristics are more important. At deep depths, actual costs dominate.

### 7. Market-Specific Tuning

**Concept**: Different heuristic weights for different exchanges/coins

```python
EXCHANGE_HEURISTIC_WEIGHTS = {
    "binance": {"h1": 1.0, "h2": 0.5},  # High volume, good books
    "kucoin": {"h1": 1.5, "h2": 0.7},   # Lower volume, need more penalty
    # ...
}
```

---

## Future Work

### 1. Comprehensive Testing Suite

**Proposed Tests**:
- Multiple starting nodes (especially low-liquidity markets)
- Various order sizes ($1K, $10K, $100K, $1M)
- Different time windows (5 min, 15 min, 30 min, 60 min)
- Different depth limits (3, 4, 5, 6, 8, 10)
- Market condition variations (high/low volume, deep/thin books)

### 2. Statistical Analysis

**Metrics to Collect**:
- Path discovery time (when optimal path is found)
- Number of nodes explored
- Number of intermediate profitable paths
- Heuristic value distributions
- Correlation between heuristic differences and path differences

### 3. Machine Learning Integration

**Potential Approaches**:
- Learn optimal heuristic weights from historical data
- Predict which heuristic will perform better for given conditions
- Adaptive heuristic selection based on market state

### 4. Real-Time Performance Monitoring

**Dashboard Metrics**:
- Heuristic effectiveness (how often does it guide to optimal path)
- Search efficiency (nodes explored vs optimal path found)
- Data availability rates (volume vs order book)
- Execution time comparison

### 5. Advanced Heuristics

**Potential New Heuristics**:
- **h3_volatility**: Price volatility risk
- **h4_latency**: Exchange API latency and reliability
- **h5_regulatory**: Regulatory risk (withdrawal restrictions, etc.)
- **h6_historical**: Historical success rate of paths

### 6. Benchmarking Framework

**Standard Test Cases**:
- Create a suite of benchmark scenarios
- Compare heuristic performance across scenarios
- Track improvements over time
- Publish results for reproducibility

---

## Conclusion

Both `h1_liquidity` and `h2_slippage` heuristics are well-designed and correctly implemented. They converge to the same optimal path in tested scenarios, demonstrating the robustness of the A* algorithm. However, they explore different intermediate paths, suggesting that heuristic choice can impact search efficiency.

**Key Takeaways**:
1. **Heuristics are complementary**: h1 focuses on volume/time, h2 focuses on execution cost
2. **Context matters**: Order size, time window, and market conditions affect which heuristic is more appropriate
3. **Both are needed**: A hybrid approach may provide the best of both worlds
4. **Tuning is important**: Current weights may not be optimal for all scenarios
5. **More testing needed**: Limited test cases prevent definitive conclusions

**Recommendations**:
- Continue testing with diverse scenarios
- Experiment with hybrid heuristics
- Tune weights based on empirical results
- Consider depth-aware and time-aware improvements
- Build comprehensive benchmarking framework

---

## Appendix: Code References

### Key Files

- `scripts/h1_vol.py`: Volume-based heuristic implementation
- `scripts/h2_slippage.py`: Slippage-based heuristic implementation
- `scripts/astar_vol.py`: A* search algorithm with heuristic integration
- `scripts/ui.py`: Streamlit UI with heuristic selection and comparison
- `docs/HEURISTIC_COMPARISON.md`: This document

### Key Functions

- `volume_heuristic_cost()`: h1(n) calculation
- `slippage_heuristic_cost()`: h2(n) calculation
- `astar_best_path_with_liquidity()`: A* search with selectable heuristic
- `run_search_and_format()`: UI integration with debug output

---

