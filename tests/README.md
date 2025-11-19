# Test Suite Documentation

## Overview

This test suite provides comprehensive testing for the stablecoin arbitrage system, covering sanity checks, integration tests, validation, and performance benchmarks.

## Test Structure

```
tests/
├── unit/              # Unit tests for individual components
│   ├── test_models.py
│   └── test_cost_calculation.py
├── integration/       # Integration tests for component interactions
│   ├── test_graph_builder.py
│   └── test_end_to_end.py
├── validation/       # Validation tests for correctness
│   ├── test_arbitrage_detection.py
│   ├── test_two_level_search.py
│   └── test_astar_heuristic.py
├── performance/      # Performance and scalability tests
│   ├── test_algorithm_performance.py
│   └── test_memory_usage.py
└── test_runner.py    # Main test runner
```

## Running Tests

### Run All Tests
```bash
python -m pytest tests/ -v
# or
python tests/test_runner.py
```

### Run Specific Test Suite
```bash
# Unit tests only
python -m pytest tests/unit/ -v

# Integration tests only
python -m pytest tests/integration/ -v

# Validation tests only
python -m pytest tests/validation/ -v

# Performance tests only
python -m pytest tests/performance/ -v
```

### Run Specific Test File
```bash
python -m pytest tests/unit/test_models.py -v
```

### Run with Coverage
```bash
python -m pytest tests/ --cov=src --cov-report=html
```

## Test Categories

### 1. Unit Tests (Sanity Checks)
- **Purpose**: Verify basic functionality of individual components
- **Coverage**:
  - Data model creation and operations
  - Cost calculations
  - Edge weight computations
  - Graph structure integrity

### 2. Integration Tests
- **Purpose**: Verify components work together
- **Coverage**:
  - GraphBuilder with connectors
  - End-to-end workflow (Graph → Agent → Opportunities)
  - API connector structure
  - Price update mechanisms

### 3. Validation Tests
- **Purpose**: Ensure correctness of arbitrage detection
- **Coverage**:
  - Arbitrage condition evaluation
  - Cycle detection
  - Profit calculation accuracy
  - Path validity
  - Two-level search coverage

### 4. Performance Tests
- **Purpose**: Measure efficiency and scalability
- **Coverage**:
  - Algorithm execution time
  - Memory usage
  - Scalability with graph size
  - Algorithm comparison (Dijkstra vs A*)

## Test Data

Tests use:
- **Synthetic graphs**: Generated test instances (no API calls)
- **Known scenarios**: Predefined graphs with expected outcomes
- **Adversarial cases**: Edge cases and failure scenarios

## Future Testing (Not Yet Implemented)

### Backtesting
- Historical price data replay
- Opportunity detection validation
- Profit accuracy measurement

### Monte Carlo Simulation
- Random market condition generation
- Statistical performance analysis
- Risk metric calculation

## Continuous Integration

To set up CI/CD:
```yaml
# Example GitHub Actions
- name: Run tests
  run: python -m pytest tests/ -v
  
- name: Generate coverage
  run: python -m pytest tests/ --cov=src --cov-report=xml
```

## Test Maintenance

- Add new tests when adding features
- Update tests when changing interfaces
- Keep tests fast (< 1 minute total)
- Use synthetic data to avoid API rate limits

