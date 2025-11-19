# Stablecoin Arbitrage System Architecture Diagram

## Original Diagram Description

This document preserves the original diagram description for reference.

### 1. High-Level Architecture

```
Exchanges → Connectors → Graph Construction → Arbitrage Agent → User/CLI/Script
```

**Components:**
- **Exchanges**: Kraken API, Coinbase API
- **Connectors**: Base Exchange Connector, Connector Connector
- **Graph Construction**: Graph Builder
- **Arbitrage Agent**: Main agent for opportunity detection
- **User/CLI/Script**: Interface layer

### 2. Graph and Cost Model

**ArbitrageGraph Structure:**
- Nodes: (Exchange, Stablecoin) pairs
  - Kraken USDT
  - Kraken USDC
  - Coinbase USDT
  - Coinbase USDC
- Edges: Directed, weighted connections between nodes

**Edge Cost Calculation:**
```
Total Cost = Fee + Volatility Cost
where:
  Volatility Cost = price_diff × volatility_factor
```

### 3. Two-Level Search Workflow

1. Enumerate all exchange pairs (e₁, e₂)
2. For each exchange pair, enumerate all stablecoin pairs
3. Build/select relevant subgraph of ArbitrageGraph
4. Run A* or Dijkstra algorithm
5. Check arbitrage opportunity (path, profit, ROI, risk)
6. If profitable, add to list
7. Try next combination

### 4. Agent Workflow

- Start two-level search
- Enumerate exchange pairs and stablecoin pairs
- Use A* or Dijkstra
- Check arbitrage opportunities
- Evaluate profitability
- Return list of profitable opportunities

