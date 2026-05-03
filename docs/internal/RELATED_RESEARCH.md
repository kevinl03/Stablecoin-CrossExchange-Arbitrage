# Related Work: Cross-Exchange Cryptocurrency Arbitrage Detection

## Abstract

This section reviews the related work on cross-exchange cryptocurrency arbitrage detection, with particular focus on the methodology and results presented by Oantă and Coroiu (2023). Their work establishes a theoretical framework for detecting arbitrage opportunities using graph theory and classical shortest-path algorithms, specifically the Bellman-Ford algorithm for negative cycle detection. We analyze their approach, compare it with our execution-aware methodology, and discuss how our work addresses limitations identified in their future research directions.

**Key Finding**: The literature on cryptocurrency arbitrage predominantly employs **negative cycle detection algorithms** (Bellman-Ford and variants) for opportunity identification. Our work introduces a novel approach using **A* search with domain-specific heuristics** for execution-aware pathfinding, which addresses a gap in the literature by focusing on execution feasibility rather than mere detection. Additionally, we focus specifically on **stablecoin arbitrage**, which presents unique opportunities due to the price pegging mechanism that creates more predictable arbitrage windows compared to volatile cryptocurrencies.

## 1. Introduction

Cross-exchange cryptocurrency arbitrage has emerged as a low-risk trading strategy that capitalizes on price discrepancies across different cryptocurrency exchanges. According to Shynkevich (2021), arbitrage trading can be divided into multiple sub-strategies, including:

- **Cross-exchange arbitrage**: Exploiting price differences between different exchanges
- **Spatial arbitrage**: Geographic price differences
- **Triangular arbitrage**: Exploiting price differences across three currencies on the same exchange
- **Decentralized arbitrage**: Arbitrage between centralized and decentralized exchanges
- **Statistical arbitrage**: Pattern-based trading strategies

Oantă and Coroiu (2023) focus specifically on cross-exchange arbitrage, presenting a comprehensive approach to detecting such opportunities through a web application called "Crypto Advisor," which implements a theoretical framework based on graph theory and negative cycle detection algorithms.

**Our Focus: Stablecoin Arbitrage**

Our work specifically targets **stablecoin arbitrage**, which presents unique advantages over general cryptocurrency arbitrage:

1. **Price Stability**: Stablecoins are pegged to fiat currencies (USD, EUR, etc.), creating more predictable price ranges and reducing volatility risk during execution windows
2. **Higher Arbitrage Frequency**: The pegging mechanism means that deviations from the peg create arbitrage opportunities that are more frequent and predictable than volatile cryptocurrencies
3. **Lower Execution Risk**: Price movements during execution are typically smaller for stablecoins, reducing the risk of opportunity disappearance before execution completes
4. **Cross-Stablecoin Opportunities**: Different stablecoins (USDT, USDC, DAI, etc.) pegged to the same underlying asset create additional arbitrage paths

This focus on stablecoins distinguishes our work from general cryptocurrency arbitrage approaches and provides a more practical foundation for automated trading systems.

**Algorithmic Approach: A* vs. Negative Cycle Detection**

The literature on arbitrage detection predominantly employs **negative cycle detection algorithms** (Bellman-Ford and variants) for opportunity identification. Recent work includes:

- **DeFiPoser** (Oakland 2021): Frames arbitrage as negative cycle detection using Bellman-Ford-Moore
- **Improved Algorithm for Arbitrage Identification** (2024): Uses modified Moore-Bellman-Ford (MMBF) for arbitrage loops
- **RICH** (VLDB 2025): Real-time identification of negative cycles for arbitrage

Our work introduces a **novel algorithmic approach** using **A* search with domain-specific heuristics** for execution-aware pathfinding. This differs from the canonical negative cycle detection approach by:

- Focusing on **execution feasibility** rather than mere detection
- Using **heuristic-guided search** to efficiently explore the space of executable paths
- Incorporating **real-time constraints** (liquidity, slippage, transfer times) during pathfinding
- Optimizing for **multiple objectives** (profitability, feasibility, safety) simultaneously

This section provides a detailed analysis of existing methodologies, experimental results, and system capabilities, followed by a comparative analysis with our execution-aware approach that addresses real-world constraints and operational risks.

## 2. Related Work: Oantă and Coroiu (2023)

### 2.1 Citation and Overview

**Citation:** Oantă, R. and Coroiu, A. (2023). "Crypto Advisor: A Web Application for Spotting Cross-Exchange Cryptocurrency Arbitrage Opportunities." In *Proceedings of the 15th International Conference on Computer Supported Education (CSEDU 2023)*, pages 238-246. DOI: 10.5220/0011850400003470

Oantă and Coroiu (2023) present a theoretical framework for detecting cross-exchange cryptocurrency arbitrage opportunities using graph theory and classical shortest-path algorithms. Their work focuses primarily on **arbitrage detection** rather than execution, providing a mathematical foundation for identifying profitable cycles in cryptocurrency markets. The authors developed a production-ready web application with an underlying API that facilitates this approach, utilizing real data in real-world circumstances.

### 2.2 Methodology

#### 2.2.1 Graph Modeling

The authors model cryptocurrency markets as a **directed weighted graph** where:

- **Nodes** represent currencies (e.g., BTC, ETH, USDT)
- **Edges** represent exchange relationships: a directed edge from currency *i* to currency *j* exists if currency *i* can be exchanged for currency *j*
- **Edge Weights** correspond to exchange rates (*r_{ij}*)

This graph representation captures all available trading pairs across exchanges, enabling systematic analysis of arbitrage opportunities. The graph abstraction allows for the application of classical graph algorithms to detect profitable cycles.

#### 2.2.2 Mathematical Transformation

A critical step in their methodology is the **logarithmic transformation** of exchange rates:

\[
w(e) = -\log(r(e))
\]

This transformation serves two purposes:

1. **Conversion from multiplicative to additive costs**: Exchange rates are multiplicative (the product of rates along a path determines profitability), while graph algorithms typically work with additive costs.

2. **Profitability condition**: Under this transformation, a profitable arbitrage opportunity corresponds to a negative-weight cycle:
   \[
   \prod_{e \in C} r(e) > 1 \quad \Longleftrightarrow \quad \sum_{e \in C} -\log(r(e)) < 0
   \]

This mathematical equivalence enables the use of standard shortest-path algorithms for arbitrage detection.

#### 2.2.3 Negative Cycle Detection Algorithm

The authors employ the **Bellman-Ford algorithm** to detect negative-weight cycles in the transformed graph:

- **Algorithm**: Standard Bellman-Ford with |V|-1 relaxation iterations
- **Negative Cycle Detection**: After |V|-1 iterations, if any edge can still be relaxed, a negative cycle exists
- **Output**: The algorithm identifies cycles where the sum of edge costs is negative (i.e., profitable arbitrage)

**Rationale for Bellman-Ford:**
- Can handle negative edge weights (unlike Dijkstra's algorithm)
- Explicitly detects negative cycles
- O(V·E) time complexity, suitable for graph sizes in cryptocurrency markets

#### 2.2.4 Arbitrage Amplification

Once a negative cycle is detected, the authors introduce the concept of **arbitrage amplification**:

If a cycle has return factor *R* = ∏ r(e) > 1, then after *k* repetitions:

\[
C_k = C_0 \cdot R^k
\]

The paper analyzes:
- Growth behavior as *k* increases
- Sensitivity to exchange rate fluctuations
- How small inefficiencies can compound into large gains

This amplification analysis assumes the cycle can be repeated indefinitely with the same profitability, which represents a theoretical idealization.

#### 2.2.5 Methodological Assumptions

The Oantă and Coroiu methodology relies on several strong assumptions:

1. **Perfect Liquidity**: Trades of any size execute at the quoted exchange rate
2. **Instant Execution**: No latency or transfer delays between exchanges
3. **Static Prices**: Prices remain constant during cycle execution
4. **No Operational Risk**: No exchange downtime, failed withdrawals, or chain congestion

These assumptions are acceptable for **theoretical detection** but limit real-world applicability, as they do not account for execution feasibility or operational constraints.

### 2.3 System Implementation and Capabilities

#### 2.3.1 Architecture

The authors developed **Crypto Advisor**, a web application with the following technical architecture:

- **Backend**: FastAPI framework (Python), leveraging asyncio for high-performance async operations
- **Frontend**: Vue.js single-page application (SPA)
- **Data Collection**: CCXT library for real-time price and order book data from exchange APIs
- **Communication**: WebSocket for real-time opportunity streaming
- **Database**: PostgreSQL with SQLAlchemy ORM

#### 2.3.2 System Capabilities

The implemented system provides:

- **Supported Exchanges**: 10 centralized exchanges
- **Supported Currencies**: 1,000 cryptocurrencies
- **API Performance**: Described as delivering "precise data with low latency" (specific quantitative metrics not provided in the paper)
- **Features**:
  - Real-time arbitrage opportunity detection
  - Public REST API with opportunities endpoint
  - WebSocket for 24/7 streaming of opportunities
  - History endpoint for past opportunities and backtesting data
  - User authentication and email notifications

#### 2.3.3 Comparison with Existing Solutions

The paper includes a comprehensive comparison (Table 1) of Crypto Advisor with other arbitrage tools, including ArbiTool, ArbiSmart, Cryptohopper, Coygo, and Hummingbot. Key differentiators for Crypto Advisor include:

**Unique Features:**
- History table for past arbitrage opportunities (not available in most competitors)
- Public API with opportunities endpoint
- Opportunities WebSocket for 24/7 streaming
- History endpoint for backtesting data
- Free subscription model

**Limitations:**
- Fewer supported exchanges (10) compared to some competitors (up to 35)
- No DEX (decentralized exchange) support
- No automated trading system (spotter only, not executor)

#### 2.3.4 Performance Characteristics

- **API Design**: Built on FastAPI framework, leveraging asyncio for high-performance async operations
- **Data Collection**: Uses CCXT library for real-time price and order book data from exchange APIs
- **WebSocket Performance**: The authors note that "additional optimizations are required as the number of external clients connecting to our websocket affects its performance"

### 2.4 Results and Findings

The authors report successful development of a robust API that delivers precise data with low latency. Their API solution is described as "highly specialized in cross-exchange arbitrage for centralized exchanges, making it rather distinctive in terms of its capabilities." The authors state that they were "unable to discover one [API] that incorporates every aspect required to perform an arbitrage trade, as our API does."

However, the paper does not provide quantitative experimental results such as:
- Detection accuracy or false positive rates
- Latency measurements
- Throughput metrics
- Comparison of detected opportunities vs. actual executable trades
- Profitability analysis of detected cycles

### 2.5 Conclusion and Future Work

The authors conclude that they successfully:
- Assessed the efficacy of the cross-exchange arbitrage strategy
- Built a robust API delivering precise data with low latency
- Created a specialized solution for cross-exchange arbitrage on centralized exchanges

**Future Work** (directly relevant to our research):
- Incorporate additional exchanges, especially decentralized ones
- **"Make the system more efficient by utilizing graph networks and cost-based pathfinding algorithms, such as Dijkstra's algorithm"**
- Develop solutions for additional arbitrage strategies beyond cross-exchange

This future work direction explicitly identifies the need for graph-based pathfinding algorithms, which aligns closely with our approach of using A* search with domain-specific heuristics for arbitrage detection and execution planning.

## 3. Comparative Analysis: Oantă & Coroiu (2023) vs. Our Work

### 3.1 Key Differences

| Aspect | Oantă & Coroiu (2023) | Our Work |
|--------|----------------------|----------|
| **Primary Research Question** | "Does arbitrage exist?" | "Can it be executed, safely and profitably?" |
| **Algorithm** | Bellman-Ford (negative cycle detection) | A* with domain-specific heuristics (H1-H4) |
| **Graph Model** | Currency-centric (nodes = currencies) | Exchange-coin pairs (nodes = (exchange, coin)) |
| **Execution Model** | Theoretical (no execution constraints) | Execution-aware (time, fees, risk) |
| **Constraints Modeled** | None | Time budgets, transfer delays, liquidity, slippage |
| **Risk Modeling** | None | Chain congestion, exchange reliability, timing risk |
| **Search Strategy** | Exhaustive cycle search | Heuristic-guided search |
| **Output** | Any profitable cycle | Executable path from specific start node |
| **Practical Deployment** | Spotter only (detection) | Execution planning with feasibility analysis |

### 3.2 Algorithm Comparison

#### 3.2.1 Bellman-Ford Approach (Oantă & Coroiu)

**Advantages:**
- Finds **any** negative cycle in the graph (comprehensive detection)
- O(V·E) time complexity
- No start node required (global search)
- Provides theoretical upper bound on arbitrage opportunities

**Limitations:**
- Assumes perfect execution (no constraints)
- Does not consider execution feasibility
- No path optimization for real-world deployment
- Theoretical baseline rather than practical strategy

#### 3.2.2 A* with Heuristics Approach (Our Work)

**Advantages:**
- Finds **executable path** from specific start node
- Guided search using domain-specific heuristics (H1-H4)
- Considers execution constraints (time, fees, risk)
- Practical for real-world automated trading systems
- Optimizes for both profitability and safety

**Limitations:**
- Requires start node specification
- Heuristic quality affects solution optimality
- More complex implementation

### 3.3 Why Both Approaches Matter

1. **Bellman-Ford** provides a **theoretical upper bound** on arbitrage opportunities
   - Shows what's theoretically possible under ideal conditions
   - Useful for validating that our execution-aware approach doesn't miss obvious opportunities
   - Serves as a baseline for comparison

2. **A* with Heuristics** provides **executable strategies**
   - Considers real-world constraints and operational risks
   - Optimizes for both safety and profitability
   - Suitable for automated trading system deployment
   - Addresses the gap identified in Oantă and Coroiu's future work

### 3.4 Integration in Our Experimental Framework

We implement Bellman-Ford as a **related research baseline** in our experimental framework:

- **Purpose**: Compare theoretical detection vs. execution-aware pathfinding
- **Use Case**: Validate that our heuristics find opportunities that Bellman-Ford also detects
- **Limitation**: Bellman-Ford results represent theoretical maximums, not executable strategies
- **Value**: Demonstrates the gap between theoretical detection and practical execution

## 4. Discussion

### 4.1 Addressing Identified Gaps

Oantă and Coroiu (2023) explicitly identify in their future work the need to "utilize graph networks and cost-based pathfinding algorithms, such as Dijkstra's algorithm." Our work directly addresses this gap by:

1. **Implementing graph-based pathfinding**: We use A* search, which extends Dijkstra's algorithm with heuristic guidance
2. **Cost-based optimization**: Our approach considers execution costs (fees, transfer times, slippage) in the pathfinding process
3. **Domain-specific heuristics**: We introduce four heuristics (H1-H4) that guide search toward profitable and executable paths
4. **Execution feasibility**: Unlike theoretical detection, our approach evaluates whether detected opportunities can actually be executed

### 4.2 Methodological Contributions

Our work extends the foundation established by Oantă and Coroiu (2023) by:

- **Modeling execution constraints**: Time budgets, transfer delays, liquidity constraints, slippage
- **Incorporating risk factors**: Chain congestion, exchange reliability, timing risk
- **Using heuristic-guided search**: Domain-specific heuristics for efficient pathfinding
- **Optimizing for real-world deployment**: Practical strategies suitable for automated trading systems

### 4.3 Limitations of Theoretical Approaches

The theoretical approach presented by Oantă and Coroiu, while mathematically sound, has limitations in practice:

1. **No execution simulation**: Detected cycles may not be executable due to liquidity, timing, or operational constraints
2. **Perfect market assumptions**: Real markets have slippage, fees, and transfer delays that affect profitability
3. **No risk assessment**: Theoretical detection does not account for exchange downtime, failed withdrawals, or chain congestion
4. **Static price assumption**: Prices change during execution, affecting cycle profitability

Our execution-aware approach addresses these limitations by explicitly modeling constraints and risks.

## 5. Conclusion

Oantă and Coroiu (2023) establish an important mathematical foundation for arbitrage detection using graph theory and negative cycle detection. Their work successfully answers the question: **"Does arbitrage exist?"** by providing a theoretical framework and practical implementation for detecting profitable cycles.

Our work extends this foundation to answer: **"Can it be executed, safely and profitably?"** by:
- Modeling execution constraints (time, fees, transfers)
- Incorporating risk factors (chain congestion, exchange reliability)
- Using heuristic-guided search for efficient pathfinding
- Optimizing for real-world deployment

Both approaches are valuable and complementary: Bellman-Ford provides theoretical bounds and comprehensive detection, while our execution-aware A* provides practical trading strategies suitable for automated systems.

**Notably**, the authors' future work explicitly mentions using "graph networks and cost-based pathfinding algorithms, such as Dijkstra's algorithm" - which is exactly what we have implemented with our A* search approach, demonstrating that our work addresses a recognized gap in their methodology and advances the state of the art in practical arbitrage execution planning.

## 6. Related Arbitrage Strategies and Our Unique Contribution

### 6.1 Taxonomy of Arbitrage Strategies

Shynkevich (2021) provides a comprehensive taxonomy of cryptocurrency arbitrage strategies. While the literature covers various approaches, most focus on **detection** rather than **execution planning**. The strategies identified include:

1. **Cross-Exchange Arbitrage** (Oantă & Coroiu, 2023; our work)
   - Exploits price differences between different exchanges
   - Requires cross-exchange transfers
   - Most relevant to our work

2. **Triangular Arbitrage**
   - Exploits price differences across three currencies on the same exchange
   - No cross-exchange transfers required
   - Faster execution but typically smaller profit margins

3. **Spatial Arbitrage**
   - Geographic price differences
   - Less relevant for digital assets

4. **Decentralized Arbitrage**
   - Between centralized and decentralized exchanges
   - Involves different execution models (order books vs. liquidity pools)

5. **Statistical Arbitrage**
   - Pattern-based strategies
   - Requires historical analysis and prediction

### 6.2 Algorithmic Approaches in Literature

**Detection-Focused Approaches (Canonical in Literature):**
- **Bellman-Ford and Variants** (Oantă & Coroiu, 2023; DeFiPoser, 2021; MMBF, 2024; RICH, 2025): Negative cycle detection for arbitrage identification
  - **DeFiPoser** (Oakland 2021): "On the Just-In-Time Discovery of Profit-Generating Transactions in DeFi" - explicitly frames arbitrage as negative cycle detection using Bellman-Ford-Moore
  - **Improved Algorithm** (2024): Uses modified Moore-Bellman-Ford (MMBF) for arbitrage loops
  - **RICH** (VLDB 2025): Real-time identification of negative cycles for high-frequency arbitrage
- **Graph-based methods**: Various shortest-path algorithms for cycle detection
- **Statistical methods**: Pattern recognition and prediction-based approaches

**Execution-Focused Approaches:**
- **Reinforcement Learning** (ICML 2006, 2024): Optimal trade execution using RL
- **Market Making / Microstructure Models**: Jane Street / Citadel-style execution strategies (proprietary, not published)
- **Simple heuristics**: Rule-based execution strategies
- **Optimization algorithms**: Linear programming, integer programming for optimal execution
- **Our approach**: **A* with domain-specific heuristics** for execution-aware pathfinding (novel contribution)

**Key Observation**: The literature shows that **A* is not a canonical arbitrage algorithm**. Most arbitrage detection problems map to either:
- **Negative cycle detection** (graph arb) → Bellman-Ford family (most common)
- **Best conversion path / routing** (DEX routing) → Dijkstra / dynamic programming

Our use of **A* with heuristics** is a novel contribution that addresses execution feasibility, which is not the focus of canonical negative cycle detection approaches.

### 6.3 What Makes Our Approach Unique

Our work introduces several novel contributions that distinguish it from existing approaches in the literature:

#### 6.3.1 Execution-Aware Pathfinding

**Unique Aspect**: While most prior work (including Oantă & Coroiu, 2023) focuses on **detection** ("Does arbitrage exist?"), our approach focuses on **execution planning** ("Can it be executed safely and profitably?").

**Key Innovation**: We model execution constraints explicitly:
- Time budgets and transfer delays
- Liquidity constraints and slippage
- Chain congestion and exchange reliability
- Risk factors affecting execution feasibility

#### 6.3.2 Domain-Specific Heuristic Functions

**Unique Aspect**: We introduce **four domain-specific heuristics** (H1-H4) that guide search toward profitable and executable paths, rather than using generic graph algorithms.

**Heuristics:**
- **H1 (Liquidity)**: Volume-based, time-aware heuristic for conservative strategies
- **H2 (Slippage)**: Order-book depth-based heuristic for large capital deployments
- **H3 (Parallel)**: Meta-heuristic using parallel A* searches for diverse exploration
- **H4 (Chain Congestion + Exchange Risk)**: Combined risk-aware heuristic for safety-critical applications

**Novelty**: Unlike Bellman-Ford which performs exhaustive search, our heuristics **guide** search toward paths that are both profitable and executable, significantly improving efficiency for real-world deployment.

#### 6.3.3 Multi-Objective Optimization

**Unique Aspect**: Our approach optimizes for **multiple objectives simultaneously**:
- Profitability (maximize final cash)
- Execution feasibility (time, liquidity, risk)
- Safety (chain congestion, exchange reliability)

This differs from theoretical approaches that optimize only for profit under perfect execution assumptions.

#### 6.3.4 Graph Model Innovation

**Unique Aspect**: Our graph model uses **exchange-coin pairs** as nodes (e.g., (Binance, USDT)) rather than just currencies, enabling:
- Explicit modeling of cross-exchange transfers
- Exchange-specific constraints (fees, reliability)
- Coin-specific transfer times and costs

This contrasts with currency-centric models (Oantă & Coroiu) that abstract away exchange-specific details.

### 6.4 Comparison with Other Execution Approaches

While some literature discusses execution strategies, our approach is unique in combining:

1. **Heuristic-guided search** (A*) rather than exhaustive search or simple rules
2. **Domain-specific heuristics** tailored to cryptocurrency arbitrage constraints
3. **Multi-heuristic framework** allowing selection based on risk profile and capital size
4. **Real-time constraint evaluation** (liquidity, slippage, risk) during pathfinding
5. **Execution feasibility analysis** before path selection

### 6.5 Addressing Identified Gaps

Oantă and Coroiu (2023) explicitly identify in their future work the need to "utilize graph networks and cost-based pathfinding algorithms, such as Dijkstra's algorithm." Our work directly addresses this gap by:

1. **Implementing graph-based pathfinding**: A* search (which extends Dijkstra's algorithm)
2. **Cost-based optimization**: Execution costs (fees, transfer times, slippage) in pathfinding
3. **Domain-specific guidance**: Heuristics that encode domain knowledge
4. **Execution feasibility**: Evaluation of whether opportunities can actually be executed

**Conclusion**: Our approach is unique in the literature for combining execution-aware pathfinding, domain-specific heuristics, and multi-objective optimization specifically tailored for cross-exchange cryptocurrency arbitrage execution planning. While the canonical approach in the literature is negative cycle detection (Bellman-Ford family), our A* heuristic-guided approach addresses the execution feasibility gap that negative cycle detection does not. Additionally, our focus on stablecoin arbitrage provides a more practical and lower-risk foundation compared to general cryptocurrency arbitrage.

## References

Fang, F., Ventre, C., Basios, M., Kanthan, L., Martinez-Rego, D., Wu, F., and Li, L. (2022). Cryptocurrency trading: a comprehensive survey. *Financial Innovation*, 8(1):1-59.

Jothi, K. and Oswalt Manoj, S. (2022). A comprehensive survey on blockchain and cryptocurrency technologies: Approaches, challenges, and opportunities. *Blockchain, Artificial Intelligence, and the Internet of Things: Possibilities and Opportunities*, pages 1-22.

Oantă, R. and Coroiu, A. (2023). Crypto Advisor: A Web Application for Spotting Cross-Exchange Cryptocurrency Arbitrage Opportunities. In *Proceedings of the 15th International Conference on Computer Supported Education (CSEDU 2023)* - Volume 1, pages 238-246. ISBN: 978-989-758-641-5; ISSN: 2184-5026. DOI: 10.5220/0011850400003470

Shynkevich, A. (2021). Bitcoin arbitrage. *Finance Research Letters*, 40:101698.

### Additional Related Work: Graph-Based Arbitrage Detection

**Negative Cycle Detection Approaches:**

DeFiPoser (2021). On the Just-In-Time Discovery of Profit-Generating Transactions in DeFi. *IEEE Symposium on Security and Privacy (Oakland)*. Uses Bellman-Ford-Moore for negative cycle detection in DeFi arbitrage.

Improved Algorithm (2024). An Improved Algorithm to Identify More Arbitrage Opportunities. *arXiv:2406.16573*. Uses modified Moore-Bellman-Ford (MMBF) approach for arbitrage loop detection.

RICH (2025). Real-Time Identification of Negative Cycles for High-Efficiency Arbitrage. *VLDB*, 18:4081-4094. Real-time identification of negative cycles for arbitrage in production systems.

**Execution and Market Making:**

Kearns, M. and Nevmyvaka, Y. (2006). Reinforcement Learning for Optimized Trade Execution. *ICML*. Classic paper on RL-based optimal execution using real limit order book data.

Optimal Execution with RL (2024). Optimal Execution with Reinforcement Learning. *arXiv:2411.06389*. Framing execution as reinforcement learning decision-making.

Reinforcement Learning for Quantitative Trading (2023). Reinforcement Learning for Quantitative Trading: A Survey. *ACM Computing Surveys*. Broad overview of RL applications in trading, execution, and market making.

**Note on Proprietary Strategies**: Major quantitative trading firms (Jane Street, Citadel) do not publish their proprietary execution strategies. The academic literature focuses on the mathematical problem classes (market making, optimal execution, arbitrage detection) rather than specific firm implementations.
