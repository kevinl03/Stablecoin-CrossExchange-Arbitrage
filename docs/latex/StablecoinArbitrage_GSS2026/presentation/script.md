# Presentation Script — GSS 2026
## "Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"
### Kevin Litvin · Canadian AI 2026 Graduate Student Symposium
### 8 minutes (+ 4 min Q&A)

---

> **How to use this document**
> - Lines in *italics* are your spoken words — read or memorize them.
> - `[SLIDE: ...]` = advance or point to the named slide.
> - `[PAUSE]` = stop talking for 1–2 full seconds.
> - `[BEAT]` = half-second breath.
> - `[DIRECTION: ...]` = physical / delivery cue, not spoken.
> - Target pace: ~125 words per minute. Total spoken words: ~950.

---

---

## SLIDE 1 · Title · **0:00 – 1:00**

`[SLIDE: Title — "Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"]`

`[DIRECTION: Walk to centre. Make eye contact with at least three people before you say a word. Breathe. Let the silence build for two full seconds.]`

*"Before I start — quick show of hands."*

`[DIRECTION: Raise your own hand first.]`

*"How many of you have ever sent money internationally — transferred between banks, used Wise, PayPal, Venmo, anything like that?"*

`[PAUSE — look around the room. Nod.]`

*"Every one of those transfers was routed through a system trying to find the cheapest, fastest path through a global financial network."*

`[BEAT]`

*"What I'm going to show you today is essentially Google Maps... for thirty-three trillion dollars."*

`[DIRECTION: Let that number land. Do not rush past it. Look at the audience.]`

---

## SLIDE 2 · The Market · **1:00 – 1:45**

`[SLIDE: "$33 Trillion — Stablecoin Market"]`

*"Stablecoins. You've heard the names: USDT, USDC, DAI. Digital dollars — cryptocurrencies pegged one-to-one with fiat currency, sitting at the intersection of traditional finance and the crypto world."*

*"Last year, stablecoins processed thirty-three trillion dollars in transaction volume."*

`[PAUSE]`

*"More than Visa. More than Mastercard. Combined."*

`[BEAT]`

*"And the total amount of stablecoins in circulation right now — the market cap — exceeds three hundred billion dollars."*

*"They are the liquidity highways of the entire crypto ecosystem. When institutions move capital into DeFi, when traders rebalance between Bitcoin and Ethereum, when cross-border settlements happen outside the traditional banking system — the bridge is almost always a stablecoin."*

*"So here is the interesting question: what happens when those highways are fragmented across twelve independent exchanges, each running at slightly different prices at the same moment in time?"*

`[BEAT]`

*"You get arbitrage opportunities. And that is what this research is about."*

---

## SLIDE 3 · The Problem · **1:45 – 3:15**

`[SLIDE: "The Problem — Four Execution Challenges"]`

`[DIRECTION: Step slightly forward or to the side — signal a shift in energy. This is where the tension builds.]`

*"Let me give you a concrete picture."*

*"Imagine you're at an international airport. There are twelve independent currency exchange desks — all trading the same currencies, but at slightly different rates, updating every few seconds based on supply and demand."*

*"Now imagine a robot that can scan all twelve desks simultaneously and find the optimal sequence of trades to turn ten thousand dollars into ten thousand and ten dollars."*

`[PAUSE]`

*"Sounds straightforward. Right?"*

`[BEAT]`

*"Here is the catch. The robot has to account for four things."*

`[DIRECTION: Count on your fingers — slow and deliberate, one pause after each.]`

*"First — the fee at each desk. Every trade costs money.*

*Second — whether the desk can handle your order size without moving the price against you mid-transaction. That is called slippage.*

*Third — how long the blockchain transfer takes. And whether the profitable window will still be open by the time it settles.*

*Fourth — whether a desk might suspend operations entirely while you are in the middle of your trade."*

`[PAUSE]`

*"Liquidity. Slippage. Latency. Reliability."*

`[BEAT]`

*"Existing arbitrage systems find opportunities on paper. We build something different: a system that finds routes you can actually execute."*

---

## SLIDE 4 · The Dataset · **3:15 – 4:00**

`[SLIDE: "The Graph — 12 Exchanges, 41 Nodes, 864 Edges"]`

*"So what does our system actually look like under the hood?"*

*"We constructed a directed weighted graph. Every node in this graph represents a unique pairing — one exchange, one stablecoin. Every edge represents a trade or a cross-exchange transfer, and it carries the full real-world cost of that action: the taker fee, the slippage estimate from live order-book data, the gas cost, and the exchange reliability score."*

*"Twelve centralized exchanges. Nine stablecoin symbols. Forty-one nodes. Eight hundred and sixty-four edges. All connected to live market data, pulled in real time."*

`[PAUSE]`

*"To our knowledge, this is the first execution-aware dataset of this kind built specifically for stablecoin arbitrage research."*

---

## SLIDE 5 · A* Search · **4:00 – 4:50**

`[SLIDE: "Method — A* as Google Maps for Money"]`

*"How do you find the best path through this network?"*

*"Our core algorithm is A* search — the same algorithm that powers GPS navigation, robot pathfinding, and game AI. A* is efficient because it does not blindly explore every possible route. It uses an evaluation function to prioritize the most promising paths, exploring the best-looking options first."*

*"We are doing exactly that — except instead of roads, we have trade corridors. Instead of traffic jams, we have order-book depth. Instead of road closures, we have exchange API downtime and blockchain congestion."*

*"The goal: find the path from any starting node to any node where your final USD value exceeds your starting capital. Not a round trip. An open path. Because all assets are dollar-pegged, we do not need to close the loop."*

---

## SLIDE 6 · Three Heuristics · **4:50 – 5:40**

`[SLIDE: "Three Novel Guidance Heuristics"]`

*"Here is where our core contribution lives."*

*"We designed three domain-specific heuristics — smart penalties that steer A* toward paths that are not just profitable, but executable under real market conditions."*

`[DIRECTION: One breath between each. These are the rule of three — give each one equal weight.]`

*"Heuristic one: Liquidity. Is there enough market depth to support this trade size, right now? Think of it as checking whether the highway can handle your truck without causing a jam.*

*Heuristic two: Slippage. Will this large order move the price against us before we can fill it? This is the toll road — and it is dynamic, computed from live order-book data in real time.*

*Heuristic three: Chain congestion and exchange reliability. How long will the blockchain transfer take, and how trustworthy is this particular venue? Road conditions and bridge reliability — before you commit to the route."*

`[BEAT]`

*"Each heuristic adds a penalty to the search cost. A* steers away from expensive estimates and toward cleaner, more executable paths."*

---

## SLIDE 7 · The Result · **5:40 – 6:30**

`[SLIDE: "Key Result — 29% Fewer Node Expansions"]`

`[DIRECTION: Slow down. This is the payoff. Every sentence gets its own breath.]`

*"Here is what we found."*

`[PAUSE]`

*"Our slippage-aware heuristic — h-two — achieved exactly the same profit as the Dijkstra baseline."*

`[PAUSE]`

*"But it did so using twenty-nine percent fewer computational steps."*

`[BEAT]`

*"Same destination. Same profit. Twenty-nine percent less work."*

`[PAUSE]`

*"We validated this across seven thousand two hundred search instances — an eight-hour overnight campaign, running continuously against live market data. Every single A* run found a profitable path."*

*"And when we re-evaluated those paths two minutes later, to account for quotes that may have gone stale? Ninety-nine point six percent were still profitable."*

*"That is a system working under real market conditions, not a simulation artifact."*

---

## SLIDE 8 · Why It Matters · **6:30 – 7:30**

`[SLIDE: "Impact — Markets Under Stress"]`

`[DIRECTION: Energy shift upward. You are now speaking about the bigger picture. Own the space.]`

*"Now you might be thinking — this is a niche trading problem. Why does it belong at an AI conference?"*

`[BEAT]`

*"Consider what happens to stablecoin markets during moments of geopolitical shock. A war breaks out. A government announces a crypto ban. A major exchange halts withdrawals overnight. These are exactly the moments when price discrepancies across independent exchanges spike — sometimes dramatically, in real time."*

*"A system that can navigate those disruptions, twenty-nine percent more efficiently than the baseline, is not just a trading tool. It is a lens for understanding how fragmented financial markets behave under stress — the kind of stress that is increasingly relevant as digital assets become part of global financial infrastructure."*

*"And we have only built the foundation. The framework extends naturally to decentralized exchanges — Uniswap, Curve — where continuous pricing invariants and automated market makers create an even richer search space."*

*"The market is expanding. The navigation tools need to scale with it."*

---

## SLIDE 9 · Close · **7:30 – 8:00**

`[SLIDE: Conclusion — "Less Exploration. More Execution."]`

`[DIRECTION: Return to centre. Calm. Measured. This is the callback to the opening. Slower pace than anywhere else in the talk.]`

*"We started with a question: how do you find the most profitable, actually executable path through a thirty-three trillion dollar market?"*

*"The answer: model the entire ecosystem as a graph. Encode every real-world cost — fees, slippage, gas, latency, reliability — as edge weights. Apply A* search, guided by domain-specific heuristics that reflect how markets actually behave."*

*"And let the algorithm find the way."*

`[PAUSE]`

*"Less exploration. More execution. Same profit."*

`[PAUSE — hold for two seconds. Make eye contact.]`

*"Thank you."*

`[DIRECTION: Do not add anything after "Thank you." Hold the silence. Let applause begin naturally.]`

---

---

# Q&A Rebuttal Preparation

> These are prepared answers for the six most likely questions. Practice saying each one out loud — aim for 30–45 seconds per answer. You do not need to give the full answer every time; lead with the one-line opener, then elaborate only if the questioner follows up.

---

### Q1 — "Why A\* and not Bellman-Ford or negative cycle detection?"

**One-line opener:** *"Bellman-Ford finds cycles that look profitable on paper. It does not tell you whether you can actually execute them."*

**Full answer:** Traditional arbitrage framing looks for negative-weight cycles — closed loops where the product of exchange rates exceeds one. But that framing ignores execution costs entirely: fees, slippage, transfer delays, and reliability are not in those models. Our open-path formulation encodes all of those costs as edge weights. A* with a domain-specific heuristic is then the natural fit: it can terminate early the moment it finds a path worth executing, without needing to explore the entire graph. Bellman-Ford has no equivalent early-termination mechanism.

---

### Q2 — "Is a 29% reduction in node expansions practically significant in live trading?"

**One-line opener:** *"In a market where opportunities can close in under a second, 29% fewer steps can mean the difference between executing and missing the window entirely."*

**Full answer:** In our overnight campaign, price quotes remained valid for an average of more than two minutes — so wall-clock speed is less critical at this scale than it would be in high-frequency equity trading. The significance of the result is two-fold: first, computational efficiency directly translates to lower operational cost at scale across thousands of daily searches; second, it validates that slippage-aware guidance genuinely steers search toward the same high-quality routes as Dijkstra, rather than getting distracted by suboptimal detours. That has implications for how we design heuristics for any real-time market-search problem.

---

### Q3 — "Are your heuristics admissible? Do they guarantee optimal paths?"

**One-line opener:** *"No — they are guidance penalties, not admissible lower bounds, and we make that explicit in the paper."*

**Full answer:** Admissibility would require that our heuristics never overestimate the true remaining cost. Because our penalties are domain-specific calibrations — not worst-case bounds — they can overestimate, which means A* may not return the globally optimal path. We accept that trade-off deliberately. In real-time arbitrage, finding a good executable path quickly is more valuable than proving it is the best possible path. h2 matching Dijkstra's profit within 1% across 7,200 instances suggests the practical cost of inadmissibility is negligible in this domain.

---

### Q4 — "What are the main limitations of this work?"

**One-line opener:** *"Three main ones: we operate on centralized exchanges only, this is a planning system not a live executor, and the heuristic weights require domain tuning."*

**Full answer:** First, we only use centralized exchange (CEX) data — the extension to DEX and AMM markets is future work. Second, our system finds paths in simulation; it does not place orders. Bridging the planning-execution gap — handling partial fills, order rejections, and race conditions — is a significant open problem. Third, the lambda parameters in our heuristics were tuned empirically on our dataset; transferring them to a new exchange set or asset class would require retuning. These are honest limitations we acknowledge in the conclusion.

---

### Q5 — "How do you handle the problem of stale market quotes?"

**One-line opener:** *"We tested this directly — 99.6% of paths remain profitable after two minutes, which gives a practical execution window."*

**Full answer:** We ran a dedicated quote-staleness experiment: after finding a profitable path, we re-evaluated it at delays of 5, 30, 60, 120, and 300 seconds using fresh market data. Up to 120 seconds, 99.6% of paths remained profitable. Beyond that, the success rate begins to degrade — which tells us something real about market dynamics. This gives practitioners a concrete execution window: a path found today should be acted on within two minutes for near-certain profitability.

---

### Q6 — "Could a system like this be used for market manipulation?"

**One-line opener:** *"The system exploits naturally occurring price discrepancies between independent exchanges — it does not create or amplify them."*

**Full answer:** Arbitrage is generally considered market-stabilizing: by buying where prices are low and selling where they are high, traders push prices toward equilibrium across venues. Our system finds these discrepancies; it does not create them. It does not place orders that move prices, and the scale of capital we test — ten thousand to one hundred thousand dollars — is orders of magnitude below what would be required to meaningfully influence a market with three hundred billion dollars in capitalization. The research is intended as a framework for studying execution feasibility, not a trading system designed for deployment without human oversight.

---

---

# Timing Reference

| Section | Slide | Target end |
|---------|-------|-----------|
| Hook | Title | 1:00 |
| The Market | $33T | 1:45 |
| The Problem | 4 Challenges | 3:15 |
| The Dataset | Graph | 4:00 |
| A* Method | GPS | 4:50 |
| Heuristics | h1/h2/h3 | 5:40 |
| Result | 29% | 6:30 |
| Impact | Markets Under Stress | 7:30 |
| Close | Conclusion | 8:00 |

**Practice tip:** Record yourself once with a timer. If you land between 7:45 and 8:10, you are in the right zone. The pauses and directions will consume about 45–60 seconds of the 8 minutes — do not rush through them.
