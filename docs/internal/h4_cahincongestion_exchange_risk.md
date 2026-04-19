## Heuristic h5: Exchange Reliability / Freeze Risk

### Motivation

In cross-exchange arbitrage, profitability alone does **not** guarantee successful execution.  
Even if prices and fees suggest a profitable route, the arbitrage can fail if funds become
**stuck on an exchange**.

Common failure scenarios include:

- Temporary or prolonged withdrawal halts
- Wallet maintenance or network upgrades
- Regulatory restrictions or compliance actions
- Infrastructure instability or outages

Different exchanges have **different operational risk profiles**.  
Large, regulated exchanges tend to be more reliable, while smaller or offshore exchanges
may present higher freeze risk.

This heuristic explicitly models **exchange-level reliability risk**, which is not captured
by price spreads, fees, or blockchain transfer times.

### Core Idea

Heuristic **h5** penalizes search states that involve **less reliable exchanges**.

> If an exchange has a higher probability of withdrawal issues or operational failure,
> routes passing through that exchange should be deprioritized — even if they appear profitable.

### Definitions

Let the current search node be:
n = (exchange, coin)

Let:

- `exchange_reliability_score(exchange)` ∈ [0, 1]  
  represent the normalized reliability of the exchange

Where:

- **1.0** = very reliable (low freeze risk)
- **0.0** = extremely risky or unknown exchange

These scores are defined **exogenously** using historical behavior, reputation,
and operational characteristics.

### Exchange Reliability Model

The heuristic uses a predefined reliability table:

| Exchange | Reliability Score |
|--------|-------------------|
| Binance | 0.9 |
| Kraken  | 0.9 |
| KuCoin  | 0.6 |
| Bybit   | 0.4 |

Unknown exchanges are treated as **high risk**.

### Exchange Reliability Score

Formally, the exchange reliability score is:

\[
\text{score}(n) = \text{exchange\_reliability\_score}(\text{exchange})
\]

#### Interpretation

- **score ≈ 1**  
  → very reliable exchange  
  → low probability of frozen funds  

- **score ≈ 0**  
  → high operational or regulatory risk  
  → strong chance of execution failure  

### Heuristic Cost Function

The heuristic cost is defined as:

\[
h_5(n) = \lambda \cdot (1 - \text{score}(n))
\]

Where:

- `λ` is a tunable weight (`EXCHANGE_HEURISTIC_WEIGHT`)
- `h_5(n) ≥ 0`

If the exchange score is unknown or zero, a large constant penalty is applied:

\[
h_5(n) = \text{UNKNOWN\_EXCHANGE\_PENALTY}
\]

### How h5 Works in Practice

| Situation | Effect of h5 |
|---------|-------------|
| Highly reliable exchange (Binance, Kraken) | Very small penalty |
| Moderately reliable exchange (KuCoin) | Moderate penalty |
| High-risk exchange (Bybit) | Large penalty |
| Unknown exchange | Strongly discouraged |

This encourages the search to **prefer safer exchanges**, especially when capital size
or execution reliability is critical.

### Integration with Weighted A\*

The planner integrates **h5** into a composite **Weighted A\*** objective:

\[
f(n) = g(n) + w \cdot (h_4(n) + h_5(n))
\]

Where:

- `g(n)` = accumulated log-cost from fees and slippage  
- `h_4(n)` = chain congestion heuristic  
- `h_5(n)` = exchange reliability heuristic  
- `w > 1` biases the search toward safer, more reliable routes  

### Why h5 Is Necessary

Fee-based optimization alone can produce routes that are **theoretically optimal**
but **practically dangerous**.

h5 addresses risks that arise **after the trade decision** but **before funds are usable**,
which is one of the most common real-world arbitrage failure modes.

### When Should a User Enable h5?

#### Strongly Recommended When

- Capital size is large and losses are unacceptable
- Arbitrage spans multiple exchanges
- Some candidate routes involve smaller or less regulated exchanges
- User prioritizes **capital safety** over marginal profit

#### Less Useful When

- Trading occurs on a single trusted exchange
- Arbitrage window is extremely short and intra-exchange only
- Exchange reliability is guaranteed (e.g., sandbox or simulation)

### Summary

Heuristic **h5**:

- Models **exchange-level operational and freeze risk**
- Penalizes unreliable or unknown exchanges
- Complements fee, liquidity, and chain-time heuristics
- Improves **real-world executability** of arbitrage paths


------------------------------------------------------------------------

## Heuristic h4: Chain Congestion / Reliability

### Motivation

In cross-exchange stablecoin arbitrage, **low fees alone do not guarantee success**.  
Even if a route looks profitable on paper, the arbitrage may fail if:

- Transfers take too long
- The arbitrage window closes while funds are in transit
- Prices move unfavorably before funds arrive
- Withdrawals or deposits are delayed on congested networks

Different blockchains have **very different latency characteristics**:

- **Fast, reliable:** Solana, Tron  
- **Moderate:** Polygon, BNB Smart Chain  
- **Slow / congested:** Ethereum mainnet, some L2s during peak load  

This heuristic explicitly models **time-based risk**, which is not captured by fee-based costs alone.

### Core Idea

Heuristic **h4** penalizes states that rely on **slow blockchain transfers** relative to the **remaining arbitrage time window**.

> If the fastest available transfer is slow compared to the remaining time,  
> the route is risky and should be deprioritized.

### Definitions

Let the current search node be:

n = (exchange, coin)

Let:

- `T_remain` = remaining allowed time for the arbitrage  
- `t_i` = transfer time (in seconds) of each outgoing **transfer** edge from node `n`

Only **transfer edges** are considered, since trade edges are assumed instantaneous
relative to blockchain transfers.

### Chain Reliability Score

We define the **chain reliability score** as a normalized value in **[0, 1]**:

\[
\text{score}(n) = 1 - \frac{\min(t_i)}{T_{\text{remain}}}
\]

#### Interpretation

- **score ≈ 1**  
  → very fast transfer relative to remaining time  
  → low congestion risk  

- **score ≈ 0**  
  → transfer consumes almost the entire remaining window  
  → extremely risky  

#### Special Cases

- If there are **no outgoing transfer edges**, the node poses no congestion risk:

\[
\text{score}(n) = 1
\]

- If the remaining time is exhausted:

\[
\text{score}(n) = 0
\]

### Heuristic Cost Function

The heuristic cost is defined as:

\[
h_4(n) = \lambda \cdot (1 - \text{score}(n))
\]

Where:

- `λ` is a tunable weight (`CHAIN_HEURISTIC_WEIGHT`)
- `h_4(n) ≥ 0`

If the score collapses to zero or becomes invalid, a large constant penalty is applied:

\[
h_4(n) = \text{UNKNOWN\_CHAIN\_PENALTY}
\]

### How h4 Works in Practice

| Situation | Effect of h4 |
|---------|-------------|
| Fast chain + large remaining time | Very small penalty |
| Slow chain + tight time window | Large penalty |
| Ethereum mainnet with ~10-minute delay | Strongly discouraged |
| Solana / Tron transfers | Preferred early in search |
| No transfers needed | No penalty |

This causes the search to **naturally prefer faster networks when time is scarce**.

### Integration with Weighted A\*

The planner uses **Weighted A\*** with a composite heuristic:

\[
f(n) = g(n) + w \cdot (h_4(n) + h_5(n))
\]

Where:

- `g(n)` = accumulated log-cost from fees and slippage  
- `h_4(n)` = chain congestion heuristic  
- `h_5(n)` = exchange risk heuristic  
- `w > 1` biases the search toward safer paths  

### Why Weighted A\*?

- Faster convergence than standard A\*
- Accepts slight sub-optimality in exchange for **much better real-world reliability**
- Ideal when **time-sensitive arbitrage** matters more than theoretical optimality

### When Should a User Enable h4?

#### Strongly Recommended When

- Arbitrage window is short (minutes, not hours)
- Transfers involve Ethereum or congested networks
- Capital size is large (failure risk is costly)
- User prioritizes **execution reliability** over raw profit

#### Less Useful When

- Arbitrage window is very large
- Only intra-exchange trades are considered
- Transfers are guaranteed fast (e.g., Solana-only routes)
