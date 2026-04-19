# Problem Formulation and Related Work

## 1. Introduction

### 1.1 Research Questions and Problem Statement

**Primary Research Question**: How can we identify and execute profitable cross-exchange stablecoin arbitrage opportunities in real-time, accounting for execution constraints, market dynamics, and operational risks?

**Sub-Questions**:
1. How do we model stablecoin arbitrage as a pathfinding problem with real-world constraints?
2. What heuristics effectively guide search toward profitable and executable arbitrage paths?
3. How do execution constraints (slippage, liquidity, transfer delays) affect arbitrage profitability?
4. How does stablecoin pegging create arbitrage opportunities distinct from volatile cryptocurrencies?

### 1.2 Why This Problem Matters

Cross-exchange cryptocurrency arbitrage represents a low-risk trading strategy that capitalizes on market inefficiencies. However, **stablecoin arbitrage** presents unique characteristics and opportunities:

1. **Implied Volatility from Pegging**: Stablecoins are pegged to fiat currencies (primarily USD), but imperfect pegging across exchanges creates price discrepancies. The **multi-level pegging mechanism** (stablecoin → USD → exchange rates) introduces **implied volatility** that manifests as arbitrage opportunities more frequently than in volatile cryptocurrencies.

2. **Execution Feasibility Gap**: Existing literature focuses on **arbitrage detection** ("Does an opportunity exist?") but not **execution planning** ("Can it be executed profitably given real-world constraints?"). The gap between theoretical detection and practical execution is significant due to:
   - **Slippage**: Large orders move prices, reducing profitability
   - **Liquidity constraints**: Order book depth limits executable quantities
   - **Transfer delays**: Blockchain confirmation times create execution windows
   - **Operational risks**: Exchange downtime, failed withdrawals, chain congestion

3. **Real-Time Constraints**: Arbitrage opportunities are ephemeral. Price movements during execution can eliminate profitability, making real-time constraint evaluation critical.

### 1.3 Our Approach: Summary

This paper addresses the execution feasibility gap by:

1. **Modeling arbitrage as execution-aware pathfinding**: We represent the problem as a graph where nodes are (exchange, stablecoin) pairs and edges encode trades/transfers with real execution costs (fees, slippage, time).

2. **Heuristic-guided search with domain knowledge**: We use **A* search** with four domain-specific heuristics (H1-H4) that incorporate:
   - **Internal metrics**: Real-time order book depth, 24h trading volume, transfer times
   - **Predictive heuristics**: Estimates of slippage, liquidity availability, execution risk
   - **Multi-objective optimization**: Balancing profitability, feasibility, and safety

3. **Real-time constraint evaluation**: Unlike theoretical detection algorithms, our approach evaluates execution constraints (slippage, liquidity, transfer delays) **during pathfinding**, not after detection.

4. **Stablecoin-specific optimization**: We leverage the predictable price ranges and frequent peg deviations that characterize stablecoin markets.

## 2. Related Work

### 2.1 Arbitrage Problem Formulation in Literature

The arbitrage problem has been studied across multiple domains. **Shynkevich (2021)** provides a taxonomy of cryptocurrency arbitrage strategies:

- **Cross-exchange arbitrage**: Price differences between exchanges (our focus)
- **Triangular arbitrage**: Price differences across three currencies on the same exchange
- **Spatial arbitrage**: Geographic price differences
- **Decentralized arbitrage**: Between centralized and decentralized exchanges
- **Statistical arbitrage**: Pattern-based strategies

**Common Solution Approaches**:

1. **Negative Cycle Detection (Most Common)**: The problem is formulated as finding negative-weight cycles in a graph where:
   - Nodes represent currencies
   - Edges represent exchange rates (transformed via log: w(e) = -log(r(e)))
   - Algorithms: Bellman-Ford, Moore-Bellman-Ford, variants
   - **Examples**: 
     - **DeFiPoser (2021)**: "On the Just-In-Time Discovery of Profit-Generating Transactions in DeFi" - uses Bellman-Ford-Moore for DeFi arbitrage
     - **MMBF (2024)**: Modified Moore-Bellman-Ford for arbitrage loop detection
     - **RICH (2025)**: Real-time negative cycle identification for high-frequency arbitrage
     - **Oantă & Coroiu (2023)**: Bellman-Ford for cross-exchange arbitrage detection

2. **Shortest Path / Routing**: For DEX routing and conversion path optimization:
   - Dijkstra's algorithm
   - Dynamic programming
   - Specialized solvers

3. **Reinforcement Learning**: For optimal execution and market making:
   - **Kearns & Nevmyvaka (2006)**: RL for optimized trade execution
   - **Optimal Execution with RL (2024)**: Execution as RL decision-making

**Key Observation**: **A* search is not a canonical arbitrage algorithm** in the literature. Most work uses negative cycle detection (Bellman-Ford family) for detection, or RL/optimization for execution. Our use of A* with heuristics bridges this gap.

### 2.2 Stablecoin Arbitrage: Unique Characteristics

While general cryptocurrency arbitrage is well-studied, **stablecoin arbitrage** presents distinct characteristics:

1. **Pegging Mechanism Creates Implied Volatility**: 
   - Stablecoins are pegged to fiat (e.g., USDT, USDC, DAI → USD)
   - Imperfect pegging across exchanges creates price discrepancies
   - **Multi-level pegging** (stablecoin → USD → exchange rates) introduces more arbitrage opportunities than volatile cryptocurrencies
   - Price deviations are smaller but more frequent and predictable

2. **Lower Execution Risk**:
   - Smaller price movements during execution windows
   - More predictable price ranges
   - Reduced risk of opportunity disappearance before execution

3. **Cross-Stablecoin Opportunities**:
   - Multiple stablecoins (USDT, USDC, DAI, BUSD, etc.) pegged to the same underlying asset
   - Creates additional arbitrage paths beyond simple cross-exchange pairs

### 2.3 Infrastructure and Systems Work

**Oantă & Coroiu (2023)** developed "Crypto Advisor," a web application for spotting cross-exchange arbitrage opportunities. Their work provides:

- **System Architecture**: FastAPI backend, Vue.js frontend, WebSocket streaming
- **Data Collection**: CCXT library for real-time exchange data
- **API Design**: Public REST API with opportunities endpoint
- **Supported Scale**: 10 exchanges, 1,000 cryptocurrencies

**Our Infrastructure**: We build upon similar foundations:
- **CCXT Library**: Real-time price and order book data (same as Oantă & Coroiu)
- **Exchange APIs**: Direct integration with multiple centralized exchanges
- **Real-Time Data**: Live prices, order books, 24h volume
- **Focus**: Stablecoins across 5+ major exchanges (Binance, Kraken, KuCoin, Bybit, Coinbase)

**Key Difference**: While Oantă & Coroiu focus on **detection and delivery** (spotting opportunities via API), we focus on **execution planning** (finding executable paths with constraint evaluation).

### 2.4 Execution Constraints: The Gap in Literature

**The Problem**: Most arbitrage literature assumes:
- Perfect liquidity (any size executes at quoted rate)
- Instant execution (no transfer delays)
- Static prices (prices don't change during execution)
- No operational risk (exchanges always available)

**Reality**: Execution constraints significantly affect profitability:
- **Slippage**: Large orders move prices; order book depth limits executable quantities
- **Transfer Delays**: Blockchain confirmation times (seconds to minutes) create execution windows
- **Liquidity Constraints**: Thin order books prevent large trades at quoted prices
- **Operational Risks**: Exchange downtime, failed withdrawals, chain congestion

**Our Contribution**: We explicitly model these constraints during pathfinding, using:
- **Real-time order book analysis**: Estimate slippage by walking the order book
- **Volume-based heuristics**: Assess liquidity using 24h trading volume
- **Transfer time modeling**: Account for blockchain confirmation times
- **Risk heuristics**: Evaluate chain congestion and exchange reliability

### 2.5 Algorithmic Approach: A* vs. Negative Cycle Detection

**Canonical Approach (Literature)**: Negative cycle detection using Bellman-Ford:
- **Strengths**: Finds all profitable cycles, comprehensive detection
- **Limitations**: Assumes perfect execution, no constraint evaluation, theoretical baseline

**Our Approach**: A* search with domain-specific heuristics:
- **Strengths**: Execution-aware, constraint evaluation during search, practical for deployment
- **Novelty**: Not canonical in arbitrage literature; addresses execution feasibility gap

**Why A* is Appropriate**:
1. **Large State Space**: Multi-exchange, multi-stablecoin, multi-hop paths create exponential search space
2. **Heuristic Guidance**: Domain knowledge (liquidity, slippage, risk) can guide search efficiently
3. **Constraint Evaluation**: Real-time evaluation of execution constraints during pathfinding
4. **Multi-Objective**: Optimize for profitability, feasibility, and safety simultaneously

**Our Heuristics (H1-H4)**:
- **H1 (Liquidity)**: Volume-based, time-aware heuristic for conservative strategies
- **H2 (Slippage)**: Order-book depth-based heuristic for large capital deployments
- **H3 (Parallel)**: Meta-heuristic using parallel A* searches for diverse exploration
- **H4 (Chain Congestion + Exchange Risk)**: Combined risk-aware heuristic for safety-critical applications

These heuristics use **internal metrics** (order book depth, trading volume, transfer times) to **predict execution outcomes** (slippage, liquidity availability, execution risk) before committing to a path.

### 2.6 How Our Work Builds on Existing Research

**Building on Oantă & Coroiu (2023)**:
- **Infrastructure**: Similar use of CCXT library and exchange APIs
- **Graph Model**: Extend their currency-centric model to (exchange, coin) pairs for execution modeling
- **Algorithm**: Move from Bellman-Ford (detection) to A* (execution planning)

**Addressing Identified Gaps**:
- Oantă & Coroiu's future work: "utilize graph networks and cost-based pathfinding algorithms, such as Dijkstra's algorithm"
- **Our contribution**: Implement A* (extends Dijkstra) with domain-specific heuristics for execution-aware pathfinding

**Novel Contributions**:
1. **Execution-aware pathfinding** (not just detection)
2. **Domain-specific heuristics** incorporating real-time constraints
3. **Stablecoin-specific optimization** leveraging pegging characteristics
4. **Multi-objective optimization** (profitability, feasibility, safety)

## 3. Problem Formulation

### 3.1 Graph Model

We model stablecoin arbitrage as a **directed weighted graph**:

- **Nodes**: (exchange, stablecoin) pairs, e.g., (Binance, USDT), (Kraken, USDC)
- **Edges**: Two types:
  - **Trade edges**: Intra-exchange swaps (e.g., USDT → USDC on Binance)
  - **Transfer edges**: Cross-exchange transfers (e.g., USDT from Binance → Kraken)

- **Edge Weights**: Execution costs in log-space:
  - Trading fees, withdrawal fees, slippage → multiplicative factors
  - Transformation: `cost = -log(rate)` where `rate` accounts for fees and slippage
  - Transfer time: `transfer_time_sec` for time-budget constraints

**Key Difference from Literature**: 
- **Literature**: Nodes = currencies (abstracts away exchanges)
- **Our Model**: Nodes = (exchange, coin) pairs (enables execution modeling)

### 3.2 Execution Constraints

Unlike theoretical detection, we model:

1. **Slippage**: Estimated by walking the order book to compute VWAP vs. mid-price
2. **Liquidity**: Assessed via 24h trading volume relative to order size
3. **Transfer Delays**: Blockchain confirmation times (chain-dependent)
4. **Time Budgets**: Maximum execution window (e.g., 30 minutes)
5. **Operational Risk**: Chain congestion scores, exchange reliability

### 3.3 Objective Function

We optimize for **multiple objectives**:

- **Primary**: Maximize final cash (profitability)
- **Secondary**: Minimize execution risk (feasibility)
- **Tertiary**: Minimize time to execution (opportunity window)

**Heuristics encode these objectives**:
- H1: Prioritize high-liquidity paths (feasibility)
- H2: Minimize slippage (profitability preservation)
- H3: Explore diverse paths (opportunity discovery)
- H4: Minimize risk (safety)

### 3.4 Problem Complexity

- **State Space**: Exponential in path length (number of hops)
- **Constraints**: Real-time evaluation of order books, volumes, transfer times
- **Heuristic Quality**: Affects solution optimality vs. search efficiency trade-off

**Our Solution**: A* with domain-specific heuristics provides:
- **Guided search**: Heuristics prune infeasible paths early
- **Real-time evaluation**: Constraints evaluated during search, not after
- **Practical deployment**: Finds executable paths efficiently

## 4. Summary

**Problem**: Cross-exchange stablecoin arbitrage with execution constraints.

**Why Important**: Stablecoin pegging creates frequent arbitrage opportunities, but execution feasibility is the bottleneck, not detection.

**Our Approach**: A* search with domain-specific heuristics that use internal metrics (order books, volumes, transfer times) to predict execution outcomes (slippage, liquidity, risk) during pathfinding.

**Novelty**: 
- Execution-aware pathfinding (not just detection)
- A* with heuristics (not canonical in arbitrage literature)
- Stablecoin-specific optimization
- Real-time constraint evaluation

**Building on**: Oantă & Coroiu (infrastructure), negative cycle detection literature (problem formulation), execution constraint modeling (our contribution).

