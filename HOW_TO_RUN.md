# How to Run the Stablecoin Arbitrage System

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Basic Example (Synthetic Data)

```bash
python example_usage.py
```

This will:
- Generate a synthetic graph with 4 exchanges and 3 stablecoins
- Find arbitrage opportunities using A*
- Display results

---

## Running Options

### Option 1: Simple Example Script (Recommended for First Time)

```bash
python example_usage.py
```

**What it does:**
- Tests with synthetic data (always works)
- Tests with live API data (requires internet)
- Shows basic usage patterns

---

### Option 2: Using Python Interactively

```python
# Start Python
python3

# Import modules
from src import ArbitrageAgent, GraphBuilder, KrakenConnector, CoinbaseConnector
from src.synthetic_generator import generate_synthetic_graph

# Create synthetic graph
graph = generate_synthetic_graph(num_exchanges=4, num_stablecoins=3, seed=42)

# Create agent
agent = ArbitrageAgent(graph)

# Find opportunities
opportunities = agent.find_all_opportunities(algorithm='astar', max_depth=5)

# Display results
for path, profit, cost, desc in opportunities[:5]:
    print(f"{desc}: Profit=${profit:.4f}, Cost=${cost:.4f}")
```

---

### Option 3: Using Live Exchange Data

```python
from src import ArbitrageAgent, GraphBuilder, KrakenConnector, CoinbaseConnector

# Create connectors
kraken = KrakenConnector()
coinbase = CoinbaseConnector()

# Build graph
builder = GraphBuilder()
builder.add_connector(kraken)
builder.add_connector(coinbase)
graph = builder.build_graph()

# Find opportunities
agent = ArbitrageAgent(graph)
opportunities = agent.find_all_opportunities(algorithm='astar', max_depth=5)

# Display results
print(f"Found {len(opportunities)} opportunities")
for path, profit, cost, desc in opportunities[:5]:
    print(f"{desc}: Profit=${profit:.4f}")
```

---

### Option 4: Using Optimized Features (New!)

#### A. Sparse Graph Builder (Faster for Large Graphs)

```python
from src.graph_builder_sparse import SparseGraphBuilder
from src.connectors.kraken_connector import KrakenConnector
from src.connectors.coinbase_connector import CoinbaseConnector

# Use sparse graph builder
builder = SparseGraphBuilder()
builder.add_connector(KrakenConnector())
builder.add_connector(CoinbaseConnector())

# Build sparse graph (10 edges per node max)
graph = builder.build_graph(max_edges_per_node=10)

# Use with agent
from src import ArbitrageAgent
agent = ArbitrageAgent(graph)
opportunities = agent.find_all_opportunities(algorithm='astar')
```

#### B. Weighted A* (Faster Search)

```python
from src.algorithms.weighted_astar import weighted_astar_arbitrage
from src.synthetic_generator import generate_synthetic_graph

graph = generate_synthetic_graph(num_exchanges=4, num_stablecoins=3)
nodes = graph.get_all_nodes()

if len(nodes) > 0:
    # Use weighted A* directly
    opportunities = weighted_astar_arbitrage(
        nodes[0],
        max_depth=5,
        volatility_factor=0.1,
        weight=1.5  # WA* weight (1.5 = 3x speedup, 5-7% suboptimal)
    )
    
    for path, profit, cost in opportunities:
        print(f"Profit: ${profit:.4f}, Cost: ${cost:.4f}")
```

#### C. With Volatility Tracking

```python
from src.utils.volatility_tracker import VolatilityTracker
from src import ArbitrageAgent, GraphBuilder, KrakenConnector

# Create volatility tracker
tracker = VolatilityTracker(window_size=100)

# Build graph
builder = GraphBuilder()
builder.add_connector(KrakenConnector())
graph = builder.build_graph()

# Update tracker with prices
for node in graph.get_all_nodes():
    tracker.update_price(node.exchange, node.stablecoin, node.price)

# Get adaptive volatility factor
volatility_factor = tracker.get_volatility_factor("Kraken", "USDT", base_factor=0.1)

# Use with agent
agent = ArbitrageAgent(graph)
opportunities = agent.find_all_opportunities(
    algorithm='astar',
    volatility_factor=volatility_factor  # Use adaptive factor
)
```

#### D. With Metrics Tracking

```python
from src.utils.metrics_tracker import MetricsTracker
from datetime import datetime
from src import ArbitrageAgent
from src.synthetic_generator import generate_synthetic_graph

# Create metrics tracker
metrics = MetricsTracker(output_file="my_results.csv")

# Generate graph and find opportunities
graph = generate_synthetic_graph(num_exchanges=4, num_stablecoins=3)
agent = ArbitrageAgent(graph)
opportunities = agent.find_all_opportunities(algorithm='weighted_astar', max_depth=5)

# Record opportunities
for path, profit, cost, desc in opportunities:
    metrics.record_opportunity(
        timestamp=datetime.now(),
        path=path,
        predicted_profit=profit,
        predicted_cost=cost,
        algorithm="weighted_astar"
    )

# Save to CSV
metrics.save_to_csv("my_results.csv")

# Save to Excel (with summary)
metrics.save_to_excel("my_results.xlsx")

# Get summary
summary = metrics.get_summary_statistics()
print(f"Total opportunities: {summary['total_opportunities']}")
print(f"Average ROI: {summary['average_roi']:.2f}%")
```

---

### Option 5: Run Experiments

#### Basic Experiment
```bash
python experiments/basic_experiment.py
```

#### Performance Comparison
```bash
python experiments/performance_comparison.py
```

---

### Option 6: Complete Example with All Optimizations

```python
#!/usr/bin/env python3
"""Complete example using all optimizations."""

from datetime import datetime
from src.graph_builder_sparse import SparseGraphBuilder
from src.connectors.kraken_connector import KrakenConnector
from src.connectors.coinbase_connector import CoinbaseConnector
from src.algorithms.weighted_astar import weighted_astar_arbitrage
from src.utils.volatility_tracker import VolatilityTracker
from src.utils.metrics_tracker import MetricsTracker
from src import ArbitrageAgent

def main():
    print("="*60)
    print("Stablecoin Arbitrage System - Optimized Version")
    print("="*60)
    
    # 1. Create connectors
    print("\n1. Connecting to exchanges...")
    kraken = KrakenConnector()
    coinbase = CoinbaseConnector()
    
    # 2. Build sparse graph (faster)
    print("2. Building graph (sparse, optimized)...")
    builder = SparseGraphBuilder()
    builder.add_connector(kraken)
    builder.add_connector(coinbase)
    graph = builder.build_graph(max_edges_per_node=10)
    
    nodes = graph.get_all_nodes()
    print(f"   ✓ Graph: {len(nodes)} nodes, {len(graph.edges)} edges")
    
    if len(nodes) == 0:
        print("   ⚠ No nodes found. Using synthetic data...")
        from src.synthetic_generator import generate_synthetic_graph
        graph = generate_synthetic_graph(num_exchanges=4, num_stablecoins=3, seed=42)
        nodes = graph.get_all_nodes()
    
    # 3. Track volatility
    print("3. Tracking volatility...")
    tracker = VolatilityTracker()
    for node in nodes:
        tracker.update_price(node.exchange, node.stablecoin, node.price)
    
    # 4. Create agent
    print("4. Creating arbitrage agent...")
    agent = ArbitrageAgent(graph)
    
    # 5. Find opportunities with weighted A*
    print("5. Searching for opportunities (Weighted A*)...")
    opportunities = agent.find_all_opportunities(
        algorithm='astar',  # Will use standard A* through agent
        max_depth=5
    )
    
    # Or use weighted A* directly:
    if len(nodes) > 0:
        wa_opportunities = weighted_astar_arbitrage(
            nodes[0],
            max_depth=5,
            volatility_factor=0.1,
            weight=1.5
        )
        print(f"   ✓ Found {len(wa_opportunities)} opportunities (Weighted A*)")
    
    print(f"   ✓ Found {len(opportunities)} opportunities (Standard)")
    
    # 6. Track metrics
    print("6. Recording metrics...")
    metrics = MetricsTracker()
    for path, profit, cost, desc in opportunities[:10]:
        metrics.record_opportunity(
            timestamp=datetime.now(),
            path=path,
            predicted_profit=profit,
            predicted_cost=cost,
            algorithm="astar"
        )
    
    # 7. Save results
    print("7. Saving results...")
    metrics.save_to_csv("results.csv")
    metrics.save_to_excel("results.xlsx")
    print("   ✓ Saved: results.csv, results.xlsx")
    
    # 8. Display summary
    print("\n" + "="*60)
    print("RESULTS SUMMARY")
    print("="*60)
    summary = metrics.get_summary_statistics()
    for key, value in summary.items():
        print(f"  {key}: {value}")
    
    # Display top opportunities
    if opportunities:
        print("\nTop 3 Opportunities:")
        for i, (path, profit, cost, desc) in enumerate(opportunities[:3], 1):
            print(f"\n  {i}. {desc}")
            print(f"     Profit: ${profit:.4f}")
            print(f"     Cost: ${cost:.4f}")
            print(f"     ROI: {(profit/cost*100) if cost > 0 else 0:.2f}%")
    
    print("\n" + "="*60)
    print("Done!")
    print("="*60)

if __name__ == "__main__":
    main()

