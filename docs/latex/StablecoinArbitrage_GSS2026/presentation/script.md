# Presentation Script — GSS 2026
## "Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage"
### Kevin Litvin · Canadian AI 2026 Graduate Student Symposium
### 8 minutes presented + 4 minutes Q&A

---

> **How to use this document**
> - Lines in *italics* are your spoken words — read or memorize them.
> - `[SLIDE: ...]` = advance to or reference the named slide.
> - `[PAUSE]` = stop speaking for 1–2 full seconds. Do not fill it.
> - `[BEAT]` = half-second breath before continuing.
> - `[DIRECTION: ...]` = physical or delivery cue — not spoken.
> - Target pace: ~125 words per minute. Total spoken words: ~940.

---

## Judging Criteria (internalize these — judges score on all six)

| Criterion | Weight |
|-----------|--------|
| Research clarity & significance | 25% |
| Content accuracy & technical depth | 25% |
| Narrative flow & organization | 20% |
| Audience engagement & delivery | 15% |
| Visual aid quality | 10% |
| Q&A preparedness | 5% |

---

---

## SLIDE 1 · Title · **0:00 – 0:35**

`[SLIDE: S1 — Title slide. FullGraph.png full-bleed background at low opacity. Paper title, author name, CdnAI logo.]`

> **Visual:** Dense network graph visible behind the title before you speak — immediate curiosity before a single word.

`[DIRECTION: Walk to centre. Make eye contact with three different people. Two full seconds of silence before you speak.]`

*"Before I start — quick show of hands."*

`[DIRECTION: Raise your own hand as you ask.]`

*"How many of you have ever sent money internationally — Wise, PayPal, a bank transfer, anything?"*

`[PAUSE — scan the room, nod.]`

*"Every one of those transfers was routed through a system trying to find the cheapest path through a global financial network."*

`[BEAT]`

*"What I'm going to show you today is essentially Google Maps... for thirty-three trillion dollars."*

`[DIRECTION: Let that number land. Hold eye contact. Do not continue immediately.]`

---

## SLIDE 2 · The Market · **0:35 – 1:25**

`[SLIDE: S2 — Bar chart: Mastercard $9T / Visa $15T / Stablecoins $33T. Two stat callouts on the right: $300B+ market cap, $33T volume.]`

> **Visual:** The stablecoin bar is clearly the tallest. Let it land before you speak.

*"Stablecoins — USDT, USDC, DAI. Digital dollars pegged one-to-one with fiat. Last year they processed thirty-three trillion dollars in transaction volume."*

`[PAUSE]`

*"More than Visa. More than Mastercard. Combined."*

`[BEAT]`

*"Three hundred billion dollars in market cap. They are the liquidity highways of the entire crypto ecosystem — the bridge every trader crosses when moving capital between exchanges or across borders."*

`[BEAT]`

*"And those highways are fragmented. Twelve independent exchanges, each pricing the same asset differently at the same instant. That fragmentation is both the problem and the opportunity."*

---

## SLIDE 3 · The Problem · **1:25 – 2:30**

`[SLIDE: S3 — Four colour-coded execution barrier cards: Liquidity (blue) / Slippage ★ (red) / Latency (orange) / Reliability (green). Bottom punchline: "Bellman-Ford, 1-hop, 2-hop enumeration — all fail."]`

> **Visual:** Animate each card in on click, synchronized with the four spoken challenges. The bottom punchline appears last.

`[DIRECTION: Step slightly forward. This is where tension builds.]`

*"Imagine you are a quant trader. It is two in the morning. You see USDT cheaper on Kraken than on KuCoin. The gap is real. The math works. Every existing system tells you: take it."*

`[BEAT]`

*"But here is what they do not tell you."*

`[DIRECTION: Count on fingers — slow, deliberate.]`

*"First — the taker fee at each exchange eats your margin. Second — your order is large enough to move the price against you mid-fill. That is slippage — dynamic, live, invisible to static models. Third — the blockchain transfer takes time. The window may close while you wait. Fourth — an exchange might suspend withdrawals overnight. Without warning."*

`[PAUSE]`

*"Liquidity. Slippage. Latency. Reliability."*

`[BEAT]`

*"We tried every standard algorithm — Bellman-Ford, one-hop, two-hop enumeration. Under live market conditions, all of them fail. Zero profitable paths found. We needed something built for this problem."*

---

## SLIDE 4 · The Dataset · **2:30 – 3:05**

`[SLIDE: S4 — FullGraph.png on the left. Four stats on the right: 12 exchanges / 9 stablecoin symbols / 41 nodes / 864 edges.]`

> **Visual:** Let the graph image carry the weight. Point to it, don't describe it.

`[DIRECTION: Gesture toward the graph image.]`

*"This is our dataset. The actual network we built."*

*"Every node is a trading pair on one of twelve exchanges. Every edge carries the full execution cost of that hop — the taker fee, a live slippage estimate from the order book, gas cost, and venue reliability. To our knowledge, this is the first execution-aware graph dataset built specifically for stablecoin arbitrage."*

`[PAUSE]`

*"The question: which path through here ends with more dollars than you started — and can actually be executed?"*

---

## SLIDE 5 · Method: A* · **3:05 – 3:50**

`[SLIDE: S5 — f(n) = g(n) + h(n) displayed large. Below it: pipeline diagram: Live Order Books → Graph → A* + h₂ → Profitable Path.]`

> **Visual:** Formula front and centre. The pipeline below shows the full system — what goes in, what comes out.

*"Our algorithm is A* search — the same strategy behind GPS navigation and game AI. The evaluation function: f of n equals g of n plus h of n."*

*"g of n is the accumulated execution cost so far — fees, slippage, gas, all of it. h of n is our domain-specific estimate of the execution risk still ahead. Together they steer the search toward paths that are not just profitable, but feasible."*

*"Think of it as Google Maps during rush hour. Not just the shortest route — the one that accounts for tolls, congestion, and road reliability. Except the map is a live financial network and the traffic is real-time order-book data."*

---

## SLIDE 6 · Three Heuristics · **3:50 – 4:45**

`[SLIDE: S6 — Three panels: h₁ Liquidity (blue) / h₂ ★ Slippage (red) / h₃ Chain+Venue (green). Each with formula. Right side: slippage curve for h₂.]`

> **Visual:** Reveal each panel as you name it. Star h₂ — it is the novel contribution. The slippage curve on the right gives technical depth without needing words.

*"We designed three guidance heuristics. Each adds a domain-specific penalty to h of n, steering A* away from paths that look profitable but cannot be executed."*

`[DIRECTION: Reveal each panel as you name it. One breath between each.]`

*"Heuristic one: Liquidity. Is there enough market depth for our order size, right now?"*

*"Heuristic two: Slippage — our novel contribution. Using live order-book data, we compute the volume-weighted average execution price and penalise paths where that price diverges too far from the mid. It updates in real time as the market moves."*

*"Heuristic three: Chain congestion and venue reliability. How long will the transfer take, and how stable is this exchange?"*

`[BEAT]`

*"One of these three will prove decisive."*

---

## SLIDE 7 · The Result · **4:45 – 5:25**

`[SLIDE: S7 — fig01_node_expansion_bar.png full-screen. h₂ bar highlighted in SFU red. "−29%" annotation large. Header: "h₂ — 29% fewer node expansions. Same profit."]`

> **Visual:** The bar chart IS the message. 29% gap must be unmissable from the back of the room. Slow down and let the numbers breathe.

`[DIRECTION: Slow down completely. Every sentence gets its own breath.]`

*"Here is what we found."*

`[PAUSE]`

*"Our slippage-aware heuristic — h-two — matched Dijkstra's profit quality within one percent."*

`[PAUSE]`

*"But it did so using twenty-nine percent fewer node expansions."*

`[PAUSE]`

*"Same destination. Same profit. Twenty-nine percent less work."*

`[BEAT]`

*"And this result held across seven thousand two hundred live searches, eight hours of continuous operation, on real market data — not a simulation."*

---

## SLIDE 8 · Real-World Proof · **5:25 – 6:05**

`[SLIDE: S8 — TOP half: fig10_overnight_timeseries.png. BOTTOM half: fig09_quote_staleness.png. Right callout: "100% success rate · 99.6% still profitable at +2 min".]`

> **Visual:** The overnight time series running continuously is the credibility. The staleness curve shows the path doesn't expire instantly. Let both images register before speaking.

`[DIRECTION: Brief pause after advancing to this slide.]`

*"Here is the evidence. Seven thousand two hundred searches over eight consecutive hours of live market data. Every single one found a profitable path."*

`[BEAT]`

*"And those paths stayed good. Ninety-nine point six percent were still profitable two minutes after discovery. After that, the market starts closing the gap."*

*"So the practical takeaway: find the path, act within one hundred and twenty seconds."*

---

## SLIDE 9 · Why It Matters + Close · **6:05 – 8:00**

`[SLIDE: S9 — FullGraph.png full-bleed dark. LEFT: three lines large: "Less Exploration. / More Execution. / Same Profit." RIGHT: fig18_radar_summary.png — method comparison radar across all metrics.]`

> **Visual:** Visual callback — the audience saw this graph before you spoke a word. Now it has meaning. The radar on the right gives technical judges a holistic view of all heuristics without needing a separate slide.

`[DIRECTION: Energy rises first for the "why it matters" section, then pace drops for the close.]`

*"Now — you might be thinking: this is a niche trading problem. Why does it belong at an AI conference?"*

`[BEAT]`

*"Consider what happens to these markets during geopolitical shocks. An exchange freeze. A government ban. A liquidity crisis. These are the moments when price discrepancies spike across fragmented venues — not by fractions of a percent, but by meaningful margins, in real time. A system that can navigate those disruptions twenty-nine percent more efficiently is not just a trading tool. It is a lens for understanding how fragmented markets behave under stress."*

*"And this framework scales. Decentralised exchanges, automated market makers, on-chain liquidity — that is the natural next frontier, and it demands exactly this kind of execution-aware pathfinding."*

`[PAUSE]`

`[DIRECTION: Return to centre. Slow your pace below your normal speaking speed.]`

*"We started with a question: how do you find the most profitable, actually executable path through a thirty-three trillion dollar market?"*

`[PAUSE]`

*"Less exploration. More execution. Same profit."*

`[PAUSE — two full seconds. Make eye contact. Do not add anything.]`

*"Thank you."*

`[DIRECTION: Hold the silence. Do not add "...any questions?" — let the room respond.]`

---

---

# Slide Visual Guide

| Slide | Title | Key visual | Source |
|-------|-------|-----------|--------|
| 1 | Title | FullGraph.png full-bleed dark background | `figures/FullGraph.png` |
| 2 | The Market | Bar chart: MC $9T / Visa $15T / Stablecoins $33T + stat callouts | Generated |
| 3 | The Problem | Four colour-coded barrier cards + "all baselines fail" punchline | Generated |
| 4 | The Dataset | FullGraph.png + 4 stats (12 exch / 9 coins / 41 nodes / 864 edges) | `figures/FullGraph.png` |
| 5 | A* Method | f(n) formula + pipeline diagram | Generated |
| 6 | Three Heuristics | Three panels (h₁/h₂★/h₃) + slippage curve | Generated |
| 7 | The Result | fig01_node_expansion_bar.png full-screen hero, h₂ in red, −29% large | `figures/fig01_node_expansion_bar.png` |
| 8 | Real-World Proof | TOP: fig10 overnight timeseries · BOTTOM: fig09 quote staleness | `figures/fig10_overnight_timeseries.png` + `fig09` |
| 9 | Close | FullGraph.png dark + three-word summary + fig18 radar | `figures/FullGraph.png` + `figures/fig18_radar_summary.png` |

---

---

# Q&A Rebuttal Preparation

> Lead with the **one-line opener** every time. Elaborate only if the questioner follows up.
> Aim for 30–45 seconds per answer. Do not over-explain.

---

### Q1 — "Why A\* and not Bellman-Ford or negative cycle detection?"

**One-line opener:** *"Bellman-Ford solves a different problem — it finds closed cycles that look profitable on paper, but does not model whether you can execute them."*

**Full answer:** Traditional arbitrage systems use negative cycle detection — closed loops where the product of exchange rates exceeds one. That framing has two problems here. First, it ignores all execution costs: fees, slippage, delays, reliability. Second, it requires returning to your starting asset — unnecessary when all assets are dollar-pegged stablecoins. Our open-path formulation is different: we look for any path ending with more USD than we started, accounting for all real costs. A* with goal-directed early termination is the right tool. Bellman-Ford, one-hop, and two-hop enumeration all fail under live market conditions.

---

### Q2 — "Is a 29% reduction practically significant in live trading?"

**One-line opener:** *"The significance is not just speed — it is that the heuristic steers search intelligently toward paths the market can actually support."*

**Full answer:** A 29% reduction while matching profit within 1% tells us h₂'s slippage estimate is genuinely informative — it guides A* toward the same high-quality routes as Dijkstra but with fewer dead ends. In deployment this means lower compute cost at scale — thousands of searches per day — and faster termination in time-sensitive windows. More importantly for the research: it validates that domain-specific guidance can improve efficiency without sacrificing solution quality.

---

### Q3 — "Are your heuristics admissible? Do they guarantee optimal paths?"

**One-line opener:** *"No — they are guidance penalties, not admissible lower bounds. We trade optimality guarantees for execution-aware steering, and we are explicit about that in the paper."*

**Full answer:** Admissibility requires the heuristic to never overestimate the true remaining cost. Ours are domain-specific calibrations tuned to execution risk, so they can overestimate — meaning A* may not return the globally optimal path. We accept that deliberately. In real-time arbitrage, a good executable path found quickly beats proving optimality. The fact that h₂ matches Dijkstra's profit within 1% across 7,200 instances suggests the practical cost of inadmissibility is negligible.

---

### Q4 — "What are the main limitations?"

**One-line opener:** *"Three honest ones: centralised exchanges only, planning not live execution, and heuristic weights need domain tuning."*

**Full answer:** First, CEX-only — DEX extension is future work. Second, we plan paths but do not place live orders; bridging the planning-execution gap — partial fills, rejections, race conditions — is open. Third, the lambda parameters in our heuristics were tuned on our dataset; applying to a different exchange set or asset class requires retuning. All three are in the conclusion.

---

### Q5 — "How do you handle stale market quotes?"

**One-line opener:** *"We ran a dedicated experiment: 99.6% of found paths remain profitable after two minutes — that defines the execution window."*

**Full answer:** After finding a path, we re-evaluated it at delays of 5, 30, 60, 120, and 300 seconds. Up to 120 seconds, 99.6% remained profitable. Beyond that, the rate degrades — telling us how long discrepancies actually persist. The practical answer: act within two minutes of path discovery.

---

### Q6 — "Your paper shows 56.7% success on the cached graph. But you said every run found a path?"

**One-line opener:** *"Those are two different experiments — good catch."*

**Full answer:** The 56.7% is from the cached-graph study: 30 fixed starting nodes, 17 of which had a reachable profitable path. Not every starting node has an arbitrage opportunity — the market may not support one from node X at that moment. The overnight campaign is different: 7,200 searches with varied starting conditions across 8 hours of live data. Every instance found a profitable path because we were not restricted to a fixed set of potentially unprofitable starting nodes.

---

### Q7 — "Could this be used for market manipulation?"

**One-line opener:** *"Arbitrage is market-stabilising — it pushes prices toward equilibrium, not away from it."*

**Full answer:** Our system finds naturally occurring discrepancies between independent exchanges. It does not coordinate orders to move prices, and the capital scale we test — $1,000 to $100,000 — is orders of magnitude below what would move a $300B market. Arbitrage is broadly considered stabilising: buying cheap and selling dear drives convergence. This is a planning and analysis framework, not a deployment-ready trading system.

---

---

# Timing Reference

| Slide | Section | Target end | Running total |
|-------|---------|-----------|---------------|
| 1 | Hook — Title | 0:35 | 0:35 |
| 2 | The Market | 1:25 | 1:25 |
| 3 | The Problem | 2:30 | 2:30 |
| 4 | The Dataset | 3:05 | 3:05 |
| 5 | A* Method | 3:50 | 3:50 |
| 6 | Three Heuristics | 4:45 | 4:45 |
| 7 | The Result | 5:25 | 5:25 |
| 8 | Real-World Proof | 6:05 | 6:05 |
| 9 | Why It Matters + Close | 8:00 | 8:00 |

**Practice tip:** Record yourself once with a timer. Target 7:45–8:10. S7 (The Result) is the emotional centrepiece — do not rush it. S9 (Close) has the most words; the first half is conviction, the second half is quiet.
