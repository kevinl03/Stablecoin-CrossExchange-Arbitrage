# Experimental Work Summary

**Branch:** `feature/experiments-and-results`  
**Date:** February 2026  
**Purpose:** Consolidated findings from deadend detection, consecutive trading, and escape strategy experiments

---

## 🎯 Key Problem Identified

**Dead-End Wallet Positions**: Paths that appear profitable on entry but trap capital in illiquid positions with no profitable exit routes.

### Example Scenario
- **Entry**: USDT → TUSD shows +$9.76 profit
- **Exit**: TUSD → USDT costs -$22.01 loss
- **Net Result**: -$12.25 loss (capital trapped)

---

## 🔍 Core Findings

### 1. Deadend Detection Algorithm

**File**: `experiments/deadend_detection_algorithm.py`

**Key Insight**: The loss happens on ENTRY, not on exit. A position is a "dead-end" if:
- You can ENTER with profit (e.g., USDT → TUSD, +$9.76)
- But CANNOT EXIT with profit (TUSD → ???, all paths negative)

**Solution**: Check exit viability BEFORE executing entry trade.

**Algorithm**:
```python
class DeadEndDetector:
    def has_viable_exit(node, liquid_cash_usd) -> bool:
        # Search for ANY profitable exit from this node
        # If no exit found with min_profit, reject the entry path
```

**Prevention Strategies**:
1. **Constrained Search**: Only select paths that can reach a liquid hub (binance:USDT, kraken:USDT)
2. **Two-Phase Execution**: Verify exit path exists BEFORE executing entry trade
3. **Portfolio Diversification**: Split capital across multiple paths
4. **Mandatory Liquidity Score**: Require minimum liquidity score for endpoint nodes

---

### 2. Escape Strategy Analysis

**Files**: 
- `experiments/escape_deadend_analysis.py`
- `experiments/escape_deadend_detailed.py`

**Purpose**: When already stuck in a dead-end position, find the best escape route.

**Escape Route Categories**:
1. **Profitable Escapes**: Exit with profit (ideal)
2. **Break-Even Escapes**: Minimal loss (< $50)
3. **Acceptable Loss**: < 5% loss (< $500)
4. **Emergency Exit**: Any exit, accept larger loss

**Key Finding**: Some positions (e.g., `mexc:TUSD`) may have NO viable escape routes at certain times, making capital truly stuck.

**Results Location**: `results/escape_analysis_*.json`, `results/escape_detailed_*.json`

---

### 3. Consecutive Wallet Trading Tests

**Files**:
- `experiments/consecutive_path_wallet_test.py`
- `experiments/fast_wallet_consecutive_test.py`
- `experiments/simple_wallet_consecutive_test.py`

**Purpose**: Simulate real wallet state over multiple consecutive trades to track:
- Wallet fragmentation across exchanges/coins
- Accumulated profit over time
- Dead-end occurrences
- Capital stuck waiting for profitable paths

**Key Metrics Tracked**:
- `total_profit`: Cumulative profit across all trades
- `num_nodes_held`: Wallet fragmentation (how many different exchange:coin positions)
- `balances`: Distribution of capital across nodes
- `execution_log`: Full history of each trade

**Findings**:
- Wallet fragmentation is a real problem (capital splits across multiple exchanges/coins)
- Some test runs found 0 profitable paths (market conditions dependent)
- Need to track wallet state persistently, not just snapshot profits

**Results Location**: `results/consecutive_wallet_*.json`

---

### 4. Constrained Consecutive Testing

**Files**:
- `experiments/constrained_consecutive_test.py`
- `experiments/constrained_consecutive_test_v2.py`
- `experiments/constrained_with_deadend_detection.py`

**Purpose**: Test consecutive trading WITH deadend prevention constraints.

**Constraint**: Only execute paths that end in "safe nodes" (liquid hubs with guaranteed exit routes).

**Safe Nodes** (typically):
- `binance:USDT`
- `kraken:USDT`
- `okx:USDT`
- `kucoin:USDT`
- `binance:USDC`

**Key Finding**: Constrained search may find fewer profitable paths, but prevents capital from getting trapped.

**Results Location**: `results/constrained_consecutive_*.json`

---

### 5. Supporting Analysis Scripts

**Diagnostic Tools**:
- `experiments/diagnose_tusd_isolation.py`: Analyze why TUSD positions become isolated
- `experiments/analyze_tusd_to_usdt.py`: Specific analysis of TUSD→USDT paths
- `experiments/fiat_intermediary_analysis.py`: Explore fiat currency as intermediary
- `experiments/wait_for_recovery_analysis.py`: Analyze waiting vs. liquidating
- `experiments/spoofing_viability_check.py`: Check if spoofing detection affects paths

**Utility Scripts**:
- `experiments/smoke_test.py`: Fast validation that all experiment scripts work
- `profit_withdrawal_executor.py`: Execute profit withdrawal strategies

---

## 📊 Results Summary

### Deadend Detection Results
- **Location**: `results/deadend_detection_*.json`
- **Finding**: Successfully identifies dead-end positions before execution
- **Status**: Algorithm works, but needs integration into main pathfinding

### Escape Analysis Results
- **Location**: `results/escape_analysis_*.json`, `results/escape_detailed_*.json`
- **Finding**: Some positions (mexc:TUSD) have NO viable escape routes
- **Recommendation**: Prevention is better than escape

### Consecutive Trading Results
- **Location**: `results/consecutive_wallet_*.json`
- **Finding**: Market conditions vary; some runs find 0 profitable paths
- **Observation**: Wallet fragmentation occurs naturally over multiple trades

### Constrained Trading Results
- **Location**: `results/constrained_consecutive_*.json`
- **Finding**: Constrained search prevents dead-ends but may reduce opportunities
- **Trade-off**: Safety vs. profit maximization

---

## 🚀 Next Steps / Future Work

### High Priority
1. **Integrate Deadend Detection**: Add `DeadEndDetector` check into main A* pathfinding
2. **Wallet State Management**: Implement persistent wallet state tracking in main system
3. **Constrained Search Option**: Make safe-node constraint optional/configurable
4. **Escape Route Monitoring**: If stuck, continuously monitor for escape opportunities

### Medium Priority
1. **Fiat Intermediary**: Explore using fiat currencies as escape routes
2. **Recovery Waiting**: Implement logic to wait for market recovery vs. immediate liquidation
3. **Portfolio Diversification**: Split capital across multiple paths to reduce dead-end risk

### Low Priority
1. **Spoofing Analysis**: Understand if exchange spoofing detection affects path viability
2. **Historical Analysis**: Replay historical data to identify dead-end patterns

---

## 📁 File Organization

### Experiment Scripts (`experiments/`)
- **Deadend Detection**: `deadend_detection_algorithm.py`
- **Escape Strategies**: `escape_deadend_analysis.py`, `escape_deadend_detailed.py`
- **Consecutive Trading**: `consecutive_path_wallet_test.py`, `fast_wallet_consecutive_test.py`, `simple_wallet_consecutive_test.py`
- **Constrained Trading**: `constrained_consecutive_test.py`, `constrained_consecutive_test_v2.py`, `constrained_with_deadend_detection.py`
- **Diagnostics**: `diagnose_tusd_isolation.py`, `analyze_tusd_to_usdt.py`, `fiat_intermediary_analysis.py`, `wait_for_recovery_analysis.py`, `spoofing_viability_check.py`
- **Utilities**: `smoke_test.py`

### Results (`results/`)
- **Deadend**: `deadend_detection_*.json`
- **Escape**: `escape_analysis_*.json`, `escape_detailed_*.json`
- **Consecutive**: `consecutive_wallet_*.json`, `wallet_consecutive_*.json`
- **Constrained**: `constrained_consecutive_*.json`, `constrained_consecutive_v2_*.json`

### Executors
- `profit_withdrawal_executor.py`: Execute profit withdrawal strategies

---

## 🔑 Key Algorithms

### Deadend Detection
```python
# Before executing a path, check if endpoint has viable exit
def is_deadend(entry_path, capital):
    endpoint = entry_path.path[-1]
    exit_path = search_for_exit(endpoint, capital)
    return exit_path is None or exit_path.profit < min_profit
```

### Escape Route Finding
```python
# When stuck, find best escape route
def find_escape_routes(stuck_node, stuck_balance, target_nodes):
    # Test paths to liquid hubs
    # Categorize: profitable, breakeven, acceptable_loss, emergency
    # Return best strategy
```

### Constrained Search
```python
# Only accept paths ending in safe nodes
def constrained_search(start_node, safe_nodes):
    path = astar_search(start_node)
    if path.endpoint in safe_nodes:
        return path
    else:
        reject_path()
```

---

## ⚠️ Important Notes

1. **Market Conditions**: Results are time-sensitive. Dead-ends may appear/disappear as market conditions change.

2. **TUSD Isolation**: TUSD (TrueUSD) appears particularly prone to dead-end positions, especially on MEXC exchange.

3. **Liquid Hubs**: Major exchanges with USDT/USDC are typically safe endpoints (binance, kraken, okx, kucoin).

4. **Prevention > Escape**: It's better to prevent dead-ends than to escape them. Some positions have no viable escape routes.

5. **Wallet Fragmentation**: Consecutive trading naturally fragments capital across exchanges/coins. This is expected but needs management.

---

## 📝 Quick Reference

**To resume work on this branch:**
1. Review this summary document
2. Check `results/` for latest experimental data
3. Run `experiments/smoke_test.py` to validate all scripts
4. Review specific experiment scripts for detailed implementation
5. Integrate findings into main arbitrage system

**Key files to review:**
- `experiments/deadend_detection_algorithm.py` - Core prevention logic
- `experiments/escape_deadend_analysis.py` - Escape strategy finder
- `experiments/constrained_consecutive_test.py` - Safe-node constrained trading
- `results/` - All experimental results

---

*This document consolidates findings from multiple experimental MD files that were removed to keep the branch clean. All key information has been preserved here.*

