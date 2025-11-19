# System Architecture Documentation

## Overview

This document provides detailed architecture diagrams and explanations for the stablecoin arbitrage system.

## High-Level Architecture

The system follows a modular architecture with clear separation of concerns:

```
┌─────────────┐
│  Exchanges  │  (Kraken, Coinbase APIs)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Connectors   │  (API Integration Layer)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Graph       │  (Graph Builder)
│ Construction│
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ Arbitrage   │  (Main Agent)
│ Agent       │
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ User/CLI    │  (Interface)
└─────────────┘
```

## Graph Model

### Node Structure
Each node represents a (Exchange, Stablecoin) pair:
- **Kraken USDT**: Node with price from Kraken exchange
- **Kraken USDC**: Node with price from Kraken exchange
- **Coinbase USDT**: Node with price from Coinbase exchange
- **Coinbase USDC**: Node with price from Coinbase exchange

### Edge Structure
Directed edges connect nodes, representing transfer possibilities:
- **Source Node**: Where you start
- **Target Node**: Where you transfer to
- **Weight**: Total transfer cost

### Cost Calculation

```
Edge Weight = Fee + Volatility Cost

Where:
  Fee = Transaction Fee + Withdrawal/Deposit Fee
  Volatility Cost = |price_source - price_target| × volatility_factor
```

**Example:**
- Source: Kraken USDT ($1.00)
- Target: Coinbase USDT ($1.01)
- Fee: $0.001 (0.1%)
- Volatility Cost: |1.00 - 1.01| × 0.1 = $0.001
- **Total Cost**: $0.002

## Two-Level Search Algorithm

### Level 1: Exchange Pairs
Systematically compares all pairs of exchanges:
- (Kraken, Coinbase)
- (Kraken, Kraken) - skipped (same exchange)
- (Coinbase, Kraken)
- etc.

### Level 2: Stablecoin Pairs
For each exchange pair, compares all stablecoin combinations:
- Exchange1(USDT) → Exchange2(USDT)
- Exchange1(USDT) → Exchange2(USDC)
- Exchange1(USDT) → Exchange2(DAI)
- Exchange1(USDC) → Exchange2(USDT)
- etc.

### Workflow
1. **Enumerate**: All (exchange, stablecoin) combinations
2. **Build Subgraph**: Create relevant portion of full graph
3. **Search**: Run A* or Dijkstra on subgraph
4. **Evaluate**: Check if opportunities are profitable
5. **Collect**: Add profitable opportunities to results
6. **Repeat**: For next combination

## Agent Workflow

```
1. Initialize Agent with ArbitrageGraph
   ↓
2. Find All Opportunities (Two-Level Search)
   ↓
3. For Each Opportunity:
   - Calculate net profit
   - Evaluate ROI
   - Assess risk
   ↓
4. Sort by Profitability
   ↓
5. Return Ranked List
```

## Algorithm Selection

### When to Use Dijkstra
- Cost minimization is primary concern
- Stable market conditions
- Simple path finding

### When to Use A*
- Volatile markets
- Time-sensitive operations
- Risk-aware decision making
- Large graph sizes

## Data Flow

```
API Data → Connectors → Graph Builder → Arbitrage Graph
                                              ↓
                                    Arbitrage Agent
                                              ↓
                                    Opportunities List
                                              ↓
                                    User/CLI Output
```

## Component Responsibilities

### Connectors
- Fetch live price data from exchanges
- Handle rate limiting
- Normalize data formats
- Provide fee estimates

### Graph Builder
- Construct graph from connector data
- Calculate edge weights
- Update prices dynamically

### Arbitrage Agent
- Execute search algorithms
- Detect opportunities
- Evaluate profitability
- Rank results

## See Also

- [System Architecture Diagram](./system_architecture_diagram.md) - Original diagram description
- [README.md](../README.md) - Main documentation with visual diagrams

