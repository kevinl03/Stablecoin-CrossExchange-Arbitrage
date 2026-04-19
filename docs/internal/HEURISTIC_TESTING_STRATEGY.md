# Heuristic Testing Strategy

## Overview

This document describes the generalized testing strategy for evaluating and comparing different heuristic functions in the A* arbitrage search algorithm. This methodology can be applied to any heuristic (h1_liquidity, h2_slippage, h3_parallel, or future heuristics) to understand their performance characteristics, optimal constant values, and relative effectiveness.

**Purpose**: Provide a systematic approach to:
- Test heuristic constants and parameters
- Compare heuristic performance
- Identify optimal configurations
- Understand factors affecting heuristic effectiveness

---

## Testing Framework

### Core Testing Approach

The testing framework systematically evaluates heuristics by:

1. **Varying Heuristic Constants**: Test different parameter values to understand sensitivity
2. **Controlling Test Conditions**: Use consistent starting conditions for fair comparison
3. **Measuring Multiple Metrics**: Profit, path discovery, execution time, search efficiency
4. **Collecting Comprehensive Data**: Log all results for statistical analysis
5. **Comparing Across Heuristics**: Use same test scenarios for cross-heuristic comparison

### Test Infrastructure

**Test Script**: `scripts/test_h2_constants.py` (generalized for any heuristic)
- Supports batched execution
- Parallel execution capability
- Real-time logging with file persistence
- Configurable test parameters

**Logging System**:
- JSON format for programmatic analysis
- Text format for human readability
- Timestamped results
- Progress tracking

---

## Test Parameters and Factors

### Primary Test Parameters

| Parameter | Typical Values | Impact on Results |
|-----------|----------------|-------------------|
| **Start Node** | `binance:USDT`, `kucoin:USDC`, etc. | Different liquidity conditions, available paths |
| **Initial Capital** | $1K, $10K, $100K, $1M | Order size affects slippage, heuristic sensitivity |
| **Max Depth** | 3, 4, 5, 6, 8, 10 | Search thoroughness vs computation cost |
| **Max Time** | 300s, 600s, 1800s, 3600s | Time window for arbitrage completion |
| **Min Profit** | $0, $10, $50, $100 | Minimum profit threshold |

### Heuristic-Specific Constants

Each heuristic has its own constants that should be tested:

#### h1_liquidity Constants
- `LIQUIDITY_HEURISTIC_WEIGHT` (λ): Controls volume-based penalty strength
- `UNKNOWN_LIQUIDITY_PENALTY`: Penalty when volume data unavailable

#### h2_slippage Constants
- `SLIPPAGE_HEURISTIC_WEIGHT` (w_slip): Controls slippage penalty strength
- `SLIPPAGE_THRESHOLD_BPS`: Acceptable slippage threshold
- `UNKNOWN_SLIPPAGE_PENALTY`: Penalty when order book data unavailable

#### h3_parallel Constants
- `num_starts`: Number of parallel starting points
- Base heuristic selection (h1 or h2)
- Base heuristic constants

---

## Factors Affecting Heuristic Performance

### 1. Search Depth (max_depth)

**Impact on Heuristics**:

| Depth | Heuristic Behavior | Use Case |
|-------|-------------------|----------|
| **Shallow (3-4)** | Fast execution, may miss longer paths | Quick searches, time-sensitive |
| **Medium (5-6)** | Balanced exploration | Default, general purpose |
| **Deep (7-10)** | Thorough exploration, higher computation | Comprehensive searches |

**Testing Strategy**:
- Test multiple depths to find optimal trade-off
- Deeper searches may reveal paths that shallow searches miss
- Heuristic effectiveness may vary with depth

### 2. Order Size (Initial Capital)

**Impact on Heuristics**:

| Order Size | h1_liquidity Impact | h2_slippage Impact | Notes |
|------------|---------------------|-------------------|-------|
| **Small ($1K)** | Low penalty | Low penalty | Both heuristics agree |
| **Medium ($10K)** | Moderate penalty | Moderate penalty | Balanced |
| **Large ($100K+)** | High penalty | **Very high penalty** | h2 becomes more important |

**Testing Strategy**:
- Test across order size spectrum
- Larger orders make execution cost (slippage) more critical
- Smaller orders make liquidity/volume more relevant

### 3. Time Window (max_time_sec)

**Impact on Heuristics**:

| Time Window | h1_liquidity Impact | h2_slippage Impact | Notes |
|-------------|---------------------|-------------------|-------|
| **Short (300s)** | Higher penalty (less volume in window) | No impact | h1 is time-aware |
| **Medium (1800s)** | Balanced | No impact | Default setting |
| **Long (3600s+)** | Lower penalty (more volume in window) | No impact | h1 becomes less restrictive |

**Testing Strategy**:
- h1_liquidity is time-aware, h2_slippage is not
- Test different time windows to see heuristic interaction
- Time constraints affect which heuristic is more appropriate

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

**Testing Strategy**:
- Test with different starting nodes (different market conditions)
- Test during different market states (volatile vs stable)
- Understand when heuristics disagree vs agree

### 5. Aggressive vs Conservative Configurations

**Aggressive Strategy**:
- High heuristic weights
- Strict thresholds
- High penalties for missing data
- **Effect**: More conservative, avoids risky paths
- **Trade-off**: May miss profitable opportunities

**Conservative Strategy**:
- Low heuristic weights
- Lenient thresholds
- Low penalties for missing data
- **Effect**: More exploratory, considers more paths
- **Trade-off**: May explore inefficient paths

**Testing Strategy**:
- Test both extremes and middle values
- Find optimal balance for your use case
- Consider risk tolerance vs profit maximization

---

## Heuristic Functionality Comparison

### h1_liquidity (Volume-Based)

**Core Functionality**:
- Estimates liquidity based on 24h trading volume
- Time-aware (considers remaining arbitrage window)
- Compares order size to typical trading volume

**Strengths**:
- Captures market activity over time
- Accounts for order size relative to typical trading
- Time-aware (important for time-constrained arbitrage)

**Limitations**:
- Volume data may be stale or unavailable
- Doesn't capture order book depth
- Doesn't account for actual execution price impact

**Best For**:
- Markets where volume/liquidity is main concern
- Time-constrained arbitrage
- Small to medium order sizes

### h2_slippage (Order-Book Depth-Based)

**Core Functionality**:
- Estimates slippage by walking the order book
- Real-time order book data
- Computes VWAP vs mid-price

**Strengths**:
- Directly measures execution cost impact
- Real-time data (more current than 24h volume)
- Accounts for actual price levels and depth
- Side-aware (buy vs sell)

**Limitations**:
- Order book data may be unavailable
- More computationally expensive
- Doesn't account for time-to-fill

**Best For**:
- Markets where order book depth is critical
- Large order sizes (where slippage dominates)
- Real-time execution cost estimation

### h3_parallel (Meta-Heuristic)

**Core Functionality**:
- Runs multiple A* searches in parallel from random starting points
- Uses base heuristic (h1 or h2) for each search
- Returns best result across all searches

**Strengths**:
- Explores multiple starting points simultaneously
- Can find paths that single-start search misses
- Parallel execution for efficiency

**Limitations**:
- Higher computational cost (multiple searches)
- Requires base heuristic selection
- May find different paths from different starts

**Best For**:
- Comprehensive path discovery
- When optimal starting point is unknown
- Scenarios with multiple competitive paths

---

## Testing Methodology

### Step 1: Define Test Scenarios

Create a matrix of test scenarios:

| Scenario | Start Node | Capital | Depth | Time | Purpose |
|----------|-----------|---------|-------|------|---------|
| Baseline | binance:USDT | $10K | 6 | 1800s | Standard test |
| Large Order | binance:USDT | $100K | 6 | 1800s | Test slippage sensitivity |
| Small Order | binance:USDT | $1K | 6 | 1800s | Test liquidity sensitivity |
| Shallow | binance:USDT | $10K | 3 | 1800s | Test depth impact |
| Deep | binance:USDT | $10K | 10 | 1800s | Test thoroughness |
| Low Liquidity | kucoin:USDC | $10K | 6 | 1800s | Test different markets |

### Step 2: Define Constant Variations

For each heuristic, test constant ranges:

**Example for h2_slippage**:
- Weight: 0.1, 0.25, 0.5, 1.0, 2.0
- Threshold: 5.0, 10.0, 20.0, 50.0 bps
- Penalty: 10.0, 25.0, 50.0, 100.0

**Example for h1_liquidity**:
- Weight: 0.1, 0.5, 1.0, 2.0
- Penalty: 1.0, 5.0, 10.0, 50.0

### Step 3: Execute Tests

Run tests systematically:
1. Use test script with batched execution
2. Enable parallel execution for efficiency
3. Log all results in real-time
4. Monitor progress and handle failures

### Step 4: Analyze Results

Compare results across:
- **Profit**: Which configurations find best paths?
- **Execution Time**: Which configurations are most efficient?
- **Path Discovery**: Do different constants find different paths?
- **Consistency**: Do constants affect optimality or just efficiency?

### Step 5: Cross-Heuristic Comparison

Compare heuristics using same test scenarios:
- Which heuristic finds best profit?
- Which heuristic is fastest?
- Which heuristic is most consistent?
- When does each heuristic perform best?

---

## Metrics and Analysis

### Key Metrics to Collect

1. **Profit Metrics**:
   - Final cash amount
   - Profit in USD
   - Profit percentage
   - Comparison to baseline

2. **Path Metrics**:
   - Optimal path discovered
   - Path length
   - Path uniqueness (same vs different paths)

3. **Efficiency Metrics**:
   - Execution time
   - Nodes explored (if available)
   - Search convergence speed

4. **Consistency Metrics**:
   - Result variance across runs
   - Success rate
   - Path stability

### Analysis Questions

1. **Do different constants find different paths?**
   - If yes: Constants significantly affect path selection
   - If no: Optimal path is dominant regardless of constants

2. **Do different constants find different profits?**
   - If yes: Some constants guide to better paths
   - If no: All constants converge to same optimal solution

3. **Do execution times vary?**
   - Faster: Heuristic guides search more efficiently
   - Slower: Heuristic causes more exploration

4. **Which constant values perform best?**
   - Compare profits across configurations
   - Consider execution time trade-offs
   - Evaluate robustness across scenarios

5. **How do heuristics compare?**
   - Which finds best profit?
   - Which is fastest?
   - Which is most consistent?
   - When does each excel?

---

## Best Practices

### Test Design

1. **Start with Baseline**: Establish baseline performance first
2. **Systematic Variation**: Test one constant at a time initially
3. **Comprehensive Coverage**: Test full range of values, not just extremes
4. **Multiple Scenarios**: Test across different market conditions
5. **Statistical Validity**: Run multiple times to account for variability

### Data Collection

1. **Real-time Logging**: Log results immediately to prevent data loss
2. **Dual Format**: Use both JSON (analysis) and text (readability)
3. **Progress Tracking**: Monitor completion status
4. **Error Handling**: Capture and log failures
5. **Resume Capability**: Support resuming interrupted tests

### Analysis

1. **Compare Like-to-Like**: Use same test scenarios for fair comparison
2. **Statistical Analysis**: Calculate means, variances, correlations
3. **Visualization**: Use charts and tables for clarity
4. **Context Matters**: Consider market conditions and test parameters
5. **Document Findings**: Record patterns, anomalies, and insights

---

## Example Test Plans

### Plan 1: Constant Sensitivity Analysis

**Goal**: Understand how constants affect heuristic performance

**Approach**:
1. Fix all parameters except one constant
2. Vary that constant across full range
3. Measure profit and execution time
4. Repeat for each constant

**Example**: Test h2_slippage with weight=[0.1, 0.5, 1.0, 2.0], threshold=10.0, penalty=50.0

### Plan 2: Cross-Heuristic Comparison

**Goal**: Compare h1, h2, h3 on same scenarios

**Approach**:
1. Define standard test scenarios
2. Run each heuristic with optimal constants
3. Compare profits, paths, execution times
4. Identify when each heuristic excels

**Example**: Compare h1_liquidity, h2_slippage, h3_parallel on 5 different starting nodes

### Plan 3: Scenario-Specific Optimization

**Goal**: Find best heuristic/constants for specific use case

**Approach**:
1. Define your specific scenario (order size, time window, etc.)
2. Test all heuristics and constant combinations
3. Select best configuration for your needs
4. Validate across similar scenarios

**Example**: Optimize for $100K orders with 10-minute window

---

## Future Extensions

### Additional Heuristics

When testing new heuristics:
1. Identify heuristic-specific constants
2. Define reasonable test ranges
3. Use same test scenarios for comparison
4. Document heuristic-specific behavior

### Advanced Analysis

- **Machine Learning**: Learn optimal constants from historical data
- **Adaptive Constants**: Adjust constants based on market conditions
- **Multi-Objective Optimization**: Balance profit, speed, and risk
- **Statistical Validation**: Multiple runs to account for variability

---

## Reference Documents

- **h2_slippage Results**: `docs/H2_CONSTANT_TEST_RESULTS.md`
- **Heuristic Comparison**: `docs/HEURISTIC_COMPARISON.md`
- **Test Script**: `scripts/test_h2_constants.py`

---

*This document provides the testing framework for evaluating and comparing all heuristics in the arbitrage system.*

