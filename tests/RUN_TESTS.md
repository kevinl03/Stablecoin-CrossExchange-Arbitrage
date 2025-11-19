# How to Run Tests

## Quick Start

```bash
# Run all tests
python3 -m unittest discover tests -v

# Run specific test suite
python3 -m unittest discover tests/unit -v
python3 -m unittest discover tests/integration -v
python3 -m unittest discover tests/validation -v
python3 -m unittest discover tests/performance -v

# Run specific test file
python3 -m unittest tests.unit.test_models -v

# Run specific test class
python3 -m unittest tests.unit.test_models.TestExchangeNode -v

# Run specific test method
python3 -m unittest tests.unit.test_models.TestExchangeNode.test_node_creation -v
```

## Test Categories

### 1. Unit Tests (Sanity Checks)
**Location**: `tests/unit/`
**Purpose**: Verify basic component functionality

```bash
python3 -m unittest discover tests/unit -v
```

**Tests**:
- `test_models.py`: ExchangeNode, Edge, Graph creation and operations
- `test_cost_calculation.py`: Cost function calculations

### 2. Integration Tests
**Location**: `tests/integration/`
**Purpose**: Verify component interactions

```bash
python3 -m unittest discover tests/integration -v
```

**Tests**:
- `test_graph_builder.py`: Graph construction from connectors
- `test_end_to_end.py`: Complete workflow testing

### 3. Validation Tests
**Location**: `tests/validation/`
**Purpose**: Ensure correctness of arbitrage detection

```bash
python3 -m unittest discover tests/validation -v
```

**Tests**:
- `test_arbitrage_detection.py`: Opportunity detection logic
- `test_two_level_search.py`: Two-level search coverage
- `test_astar_heuristic.py`: A* heuristic correctness

### 4. Performance Tests
**Location**: `tests/performance/`
**Purpose**: Measure efficiency and scalability

```bash
python3 -m unittest discover tests/performance -v
```

**Tests**:
- `test_algorithm_performance.py`: Execution time benchmarks
- `test_memory_usage.py`: Memory efficiency

### 5. Backtesting (Framework Ready)
**Location**: `tests/backtesting/`
**Purpose**: Historical validation

```bash
python3 -m unittest discover tests/backtesting -v
```

**Note**: Requires historical price data to be meaningful

### 6. Monte Carlo (Framework Ready)
**Location**: `tests/monte_carlo/`
**Purpose**: Robustness testing under uncertainty

```bash
python3 -m unittest discover tests/monte_carlo -v
```

## Expected Results

### Unit Tests
- ✅ All model creation tests pass
- ✅ Cost calculations are accurate
- ✅ Graph operations work correctly

### Integration Tests
- ✅ GraphBuilder creates valid graphs
- ✅ End-to-end workflow functions
- ✅ Agent can find opportunities

### Validation Tests
- ✅ Arbitrage conditions correctly evaluated
- ✅ Profit calculations are accurate
- ✅ Paths are valid and traversable

### Performance Tests
- ✅ Small graphs: < 1 second
- ✅ Medium graphs: < 10 seconds
- ✅ Algorithms scale reasonably

## Troubleshooting

### Import Errors
If you get import errors, make sure you're in the project root:
```bash
cd /Users/user/Desktop/CMPT417/Stablecoin-CrossExchange-Arbitrage
python3 -m unittest discover tests -v
```

### Missing Dependencies
Install required packages:
```bash
pip install -r requirements.txt
```

### Test Failures
- Check that synthetic data generators are working
- Verify graph structure is correct
- Ensure algorithms are finding paths correctly

