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
> - Target pace: ~125 words per minute. Total spoken words: ~950.

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

## SLIDE 1 · Title · **0:00 – 0:50**

`[SLIDE: S1 — Title slide. FullGraph.png full-bleed background at low opacity. Paper title + author name + CdnAI logo.]`

> **Visual:** The audience sees a dense, beautiful network graph before you speak. Immediate curiosity — *"what is that?"* — before a single word.

`[DIRECTION: Walk to centre. Make eye contact with three different people. Let two full seconds of silence pass. Do not start talking immediately.]`

*"Before I start — quick show of hands."*

`[DIRECTION: Raise your own hand as you ask.]`

*"How many of you have ever sent money internationally — transferred between banks, used Wise, PayPal, anything like that?"*

`[PAUSE — scan the room, nod.]`

*"Every one of those transfers was routed through a system trying to find the cheapest, fastest path through a global financial network."*

`[BEAT]`

*"What I'm going to show you today is essentially Google Maps... for thirty-three trillion dollars."*

`[DIRECTION: Let that number land. Hold eye contact. Do not continue immediately.]`

---

## SLIDE 2 · The Market · **0:50 – 1:35**

`[SLIDE: S2 — Bar chart: Mastercard $9T / Visa $15T / Stablecoins $33T. Two stat callouts on the right: $300B+ market cap, $33T volume.]`

> **Visual:** The stablecoin bar is noticeably taller. The contrast IS the point. Let the image land before speaking.

*"Stablecoins — USDT, USDC, DAI. Digital dollars. Cryptocurrencies pegged one-to-one with fiat, sitting at the intersection of traditional finance and the crypto world."*

*"Last year, stablecoins processed thirty-three trillion dollars in transaction volume."*

`[PAUSE]`

*"More than Visa. More than Mastercard. Combined."*

`[BEAT]`

*"Three hundred billion dollars in market capitalization. They are the liquidity highways of the entire crypto ecosystem — the bridge every trader crosses when moving capital between assets, exchanges, or borders."*

*"So here is the question this research asks: those highways are fragmented across twelve independent exchanges, each pricing the same assets slightly differently at the same instant. Can we build a system smart enough to find and execute a profitable path through that fragmentation — accounting for every real-world cost?"*

`[BEAT]`

*"That is what we set out to answer."*

---

## SLIDE 3 · Price Fragmentation · **1:35 – 2:00**

`[SLIDE: S3 — USDT mid-price listed across all 12 exchanges as a horizontal bar chart. Spread annotation: "Spread = $0.0031 ← arbitrage window".]`

> **Visual:** This is a data table that speaks for itself. USDT should theoretically trade at exactly $1.0000 everywhere — the visual shows it doesn't. Let the audience read the spread for a moment before explaining it.

`[DIRECTION: Gesture toward the slide. Pause briefly before speaking.]`

*"Let me show you what that fragmentation looks like in practice."*

`[PAUSE]`

*"This is USDT — one of the world's most liquid assets — priced simultaneously across twelve independent exchanges. Look at the spread. The same dollar, at the same moment, with different prices on every platform. That gap — that is the arbitrage window."*

`[BEAT]`

*"And capturing it requires finding a path through this network before anyone else does, and before the gap closes."*

---

## SLIDE 4 · Execution Barriers · **2:00 – 2:50**

`[SLIDE: S4 — Four colour-coded challenge cards: Liquidity (blue) / Slippage ★ (red) / Latency (orange) / Reliability (green). Bottom punchline: "Bellman-Ford, 1-hop, and 2-hop enumeration all fail."]`

> **Visual:** Animate each card in on click, synchronized with the four spoken challenges.

`[DIRECTION: Step slightly forward. This is where tension builds.]`

*"Imagine you are a quant trader. It is two in the morning. You see USDT cheaper on Kraken than on KuCoin. The gap is real. The math works. Existing systems say: take it."*

`[BEAT]`

*"But here is what they do not tell you."*

`[DIRECTION: Count on fingers — slow, deliberate, one beat after each.]`

*"First — the taker fee at each exchange eats into your margin."*

*"Second — your order size is large enough that buying on Kraken moves the price against you mid-fill. That is slippage. Dynamic, live, invisible to static models."*

*"Third — the blockchain transfer between exchanges takes time. The window may close while you wait for confirmations."*

*"Fourth — an exchange might suspend withdrawals entirely. We have seen this happen overnight, without warning."*

`[PAUSE]`

*"Liquidity. Slippage. Latency. Reliability."*

---

## SLIDE 5 · Baselines Fail · **2:50 – 3:10**

`[SLIDE: S5 — Bar chart: Bellman-Ford = $0 profit / 1-Hop = $0 / 2-Hop = $0 / A*+h₂ = $9.91. "FAIL" labels on first three bars.]`

> **Visual:** The contrast is stark and immediate. Three grey bars at zero, one red bar at $9.91. The slide does the work — keep your words short and fast here.

*"The natural instinct is to use existing graph algorithms. We tried. Bellman-Ford finds closed cycles — it cannot model open-path stablecoin arbitrage. One-hop and two-hop enumeration are too shallow to find the multi-leg paths that matter."*

`[PAUSE]`

*"Under our live market conditions — none of them find a profitable executable path."*

`[BEAT]`

*"We needed a fundamentally different approach."*

---

## SLIDE 6 · The Dataset · **3:10 – 3:40**

`[SLIDE: S6 — FullGraph.png on the left. Four stats on the right: 12 exchanges / 9 stablecoin symbols / 41 nodes / 864 edges.]`

> **Visual:** Let the graph image carry the weight. The four stats anchor the scale. Point to the graph, not the stats.

`[DIRECTION: Gesture toward the graph image.]`

*"This is our dataset. The actual network we built."*

*"Every node is a trading pair on one of twelve exchanges. Every edge carries the complete execution cost of that hop: the taker fee, a live slippage estimate derived from the order book, the gas cost, and the venue's reliability score."*

*"To our knowledge, this is the first execution-aware graph dataset built specifically for stablecoin arbitrage research."*

`[PAUSE]`

*"The question is: which path through here ends with more dollars than you started with — and can actually be executed?"*

---

## SLIDE 7 · Method: A* Search · **3:40 – 4:20**

`[SLIDE: S7 — f(n) = g(n) + h(n) displayed large. Below it: pipeline diagram: Live Order Books → Execution-Aware Graph → A* + h₂ → Profitable Path.]`

> **Visual:** The formula is front and centre. The pipeline diagram shows the full system in one image — what comes in, what the search does, what comes out. Technical audience will read it immediately.

*"Our core algorithm is A* search — the same search strategy that powers GPS navigation and game AI. The evaluation function: f of n equals g of n plus h of n."*

*"g of n is the accumulated execution cost so far. h of n is our domain-specific estimate of the execution risk still ahead. Together, they prioritize nodes that are not just close to the goal — but reachable."*

*"Think of it as Google Maps during rush hour. Not the shortest route. The one you can actually drive — accounting for tolls, congestion, and road reliability. Except the map is a live financial network, and the traffic is real-time order-book data."*

---

## SLIDE 8 · Three Heuristics · **4:20 – 5:10**

`[SLIDE: S8 — Three coloured panels: h₁ Liquidity (blue) / h₂ ★ Slippage (red) / h₃ Chain+Venue (green), each with formula. Right side: slippage curve showing price impact vs order size.]`

> **Visual:** Reveal each panel as you name it. Mark h₂ with a star — it is the novel contribution and the one that wins. The slippage curve on the right gives technical context for h₂ without requiring a verbal explanation.

*"We designed three guidance heuristics. Each adds a domain-specific penalty to h of n, steering A* away from paths that look profitable but cannot be executed."*

`[DIRECTION: Reveal each panel as you name it. One breath between each. Do not rush.]`

*"Heuristic one: Liquidity. Is there enough market depth in this venue for our order size right now?"*

*"Heuristic two: Slippage. Our novel contribution. Using live order-book data, we compute the volume-weighted average execution price and penalize paths where the slippage diverges too far from the mid-price. It updates in real time as the market moves."*

*"Heuristic three: Chain congestion and exchange reliability. How long will the blockchain transfer take, and how operationally stable is this venue?"*

`[BEAT]`

*"One of these three will prove decisive."*

---

## SLIDE 9 · Key Result · **5:10 – 5:40**

`[SLIDE: S9 — fig01_node_expansion_bar.png full-screen hero. h₂ bar highlighted in SFU red. "−29%" annotation large and visible. Header: "h₂ (Slippage Heuristic) — 29% fewer node expansions. Same profit."]`

> **Visual:** The bar chart IS the message. The 29% gap must be unmissable. No text needed — slow down and let the numbers breathe.

`[DIRECTION: Slow down. Every sentence here gets its own breath. This is the payoff.]`

*"Here is what we found."*

`[PAUSE]`

*"Our slippage-aware heuristic — h-two — achieved the same profit quality as the Dijkstra baseline. Within one percent."*

`[PAUSE]`

*"But it did so using twenty-nine percent fewer node expansions."*

`[PAUSE]`

*"Same destination. Same profit. Twenty-nine percent less work."*

---

## SLIDE 10 · Profit Quality & Speed · **5:40 – 6:00**

`[SLIDE: S10 — LEFT: fig03_profit_boxplot.png (profit distribution by algorithm). RIGHT: fig02_compute_time_bar.png (compute time comparison). Bottom banner: "h₂ matches Dijkstra profit within 1% · all algorithms run <10 ms · no speed-quality trade-off".]`

> **Visual:** Let the two charts tell the story side by side. The profit distributions should look nearly identical — that's the point. Brief spoken words, then move on.

`[DIRECTION: Gesture left, then right.]`

*"And this is the profit distribution across all runs — h-two's quality matches Dijkstra almost exactly."*

`[BEAT]`

*"Same speed. Same profit. Fewer expansions. There is no trade-off."*

---

## SLIDE 11 · Overnight Campaign · **6:00 – 6:22**

`[SLIDE: S11 — TOP: fig10_overnight_timeseries.png (profit over 8-hour run). BOTTOM: fig11_overnight_heuristic_comparison.png (heuristic comparison across run). Right callout: "7 200 searches · 100% found a path · 8 hours · live data".]`

> **Visual:** The time series shows a real system running continuously. The flatness of the overnight line — no crashes, no gaps — is itself the message. The bottom comparison shows h₂ holding up throughout.

*"This is not a snapshot. We ran seven thousand two hundred live searches across eight consecutive hours of real market data."*

`[PAUSE]`

*"Every single A* run found a profitable path. Not in simulation — on live order books."*

---

## SLIDE 12 · Execution Window · **6:22 – 6:38**

`[SLIDE: S12 — fig09_quote_staleness.png (success rate vs time delay). Right callout: "99.6% still profitable at +2 min". Bottom: "Act within 120 seconds."]`

> **Visual:** The staleness curve tells the story instantly — the line stays high until 120 seconds, then degrades. Point to the inflection point. The "99.6%" number should be large enough to read from the back.

*"And those paths stayed profitable. Ninety-nine point six percent were still valid two minutes after discovery."*

`[BEAT]`

*"That is a concrete execution window: act within one hundred and twenty seconds."*

---

## SLIDE 13 · Why It Matters + Close · **6:38 – 8:00**

`[SLIDE: S13 — FullGraph.png full-bleed dark. LEFT: three-line summary: "Less Exploration. / More Execution. / Same Profit." RIGHT: fig18_radar_summary.png (method comparison radar chart across all metrics).]`

> **Visual:** This is the visual callback AND the impact statement. The radar chart on the right gives technical judges a holistic view of all heuristics across all dimensions. The FullGraph background closes the loop — the audience saw this image before you spoke a word.

`[DIRECTION: Return to centre. Energy rises first — this is the vision — then slows for the callback. Two distinct beats within this slide.]`

*"Now you might be thinking — this is a niche trading problem. Why does it belong at an AI conference?"*

`[BEAT]`

*"Consider what happens to stablecoin markets during geopolitical shocks. A war breaks out. A government announces an exchange freeze. These are the moments when price discrepancies spike across independent exchanges — not by fractions of a percent, but by meaningful margins, in real time."*

*"A system that can navigate those disruptions — twenty-nine percent more efficiently than the baseline — is not just a trading tool. It is a lens for understanding how fragmented financial markets behave under stress. That is a research question with implications well beyond cryptocurrency."*

*"Decentralized exchanges, automated market makers, on-chain liquidity — these are the next frontier. The framework we built here scales directly to that space."*

`[PAUSE]`

`[DIRECTION: Slow your pace below your normal speaking speed for the next three lines. This is the callback.]`

*"We started with a question: how do you find the most profitable, actually executable path through a thirty-three trillion dollar market?"*

`[PAUSE]`

*"Less exploration. More execution. Same profit."*

`[PAUSE — two full seconds. Make eye contact. Do not add anything.]`

*"Thank you."*

`[DIRECTION: Hold the silence after "Thank you." Do not add "...any questions?" Let the room respond.]`

---

---

# Slide Visual Guide — Quick Reference (v2 — 13 slides)

| Slide | Title | Key visual | Source |
|-------|-------|-----------|--------|
| 1 | Title | FullGraph.png full-bleed background at low opacity | `figures/FullGraph.png` |
| 2 | Market | Bar chart: MC $9T / Visa $15T / Stablecoins $33T + stat callouts | `v2_market.png` (generated) |
| 3 | Price Fragmentation | Horizontal bar: USDT mid-price across 12 exchanges, spread annotated | `v2_price_table.png` (generated) |
| 4 | Execution Barriers | Four colour-coded challenge cards | Generated in fill_slides_v2.py |
| 5 | Baselines Fail | Bar chart: Bellman-Ford/1-hop/2-hop = $0, A*+h₂ = $9.91 | `v2_baselines.png` (generated) |
| 6 | Dataset | FullGraph.png + 4 stats (12 exch / 9 coins / 41 nodes / 864 edges) | `figures/FullGraph.png` |
| 7 | A* Method | f(n) formula + pipeline diagram (Data → Graph → A*+h₂ → Path) | `v2_pipeline.png` (generated) |
| 8 | Heuristics | Three panels (h₁/h₂★/h₃) + slippage curve for h₂ | `v2_slippage.png` (generated) |
| 9 | Key Result | fig01_node_expansion_bar.png full-screen, h₂ highlighted, −29% large | `figures/fig01_node_expansion_bar.png` |
| 10 | Profit Quality | fig03 profit boxplot (LEFT) + fig02 compute time (RIGHT) | `figures/fig03_profit_boxplot.png` + `fig02` |
| 11 | Overnight | fig10 overnight time series (TOP) + fig11 heuristic comparison (BOTTOM) | `figures/fig10_overnight_timeseries.png` + `fig11` |
| 12 | Execution Window | fig09 quote staleness curve + "99.6%" callout | `figures/fig09_quote_staleness.png` |
| 13 | Close | FullGraph.png dark + three-word summary + fig18 radar | `figures/FullGraph.png` + `figures/fig18_radar_summary.png` |

---

---

# Q&A Rebuttal Preparation

> Lead with the **one-line opener** every time. Elaborate only if the questioner follows up.
> Aim for 30–45 seconds per answer. Do not over-explain.

---

### Q1 — "Why A\* and not Bellman-Ford or negative cycle detection?"

**One-line opener:** *"Bellman-Ford solves a different problem. It finds closed cycles that look profitable on paper — it does not model whether you can execute them."*

**Full answer:** Traditional arbitrage systems use negative cycle detection — they look for closed loops where the product of exchange rates exceeds one. But that framing has two problems for our setting. First, it ignores execution costs entirely: fees, slippage, transfer delays, and exchange reliability are not in that model. Second, it requires a closed loop — returning to your starting asset — which is unnecessary when all assets are dollar-pegged stablecoins. Our open-path formulation is fundamentally different: we are looking for any path that ends with more USD value than we started with, accounting for all real costs. A* with goal-directed early termination is the right tool for that problem. Bellman-Ford, one-hop, and two-hop enumeration all fail in our experiments — they cannot identify a profitable executable path under live market conditions.

---

### Q2 — "Is a 29% reduction in node expansions practically significant in live trading?"

**One-line opener:** *"The significance is not just speed — it is that the heuristic is steering search more intelligently, toward paths the market can actually support."*

**Full answer:** A 29% reduction while matching profit within 1% tells us something important: h₂'s slippage estimate is genuinely informative. It is guiding A* toward the same high-quality routes as Dijkstra, but exploring fewer dead ends along the way. In a real deployment, this translates to lower computational cost at scale — thousands of searches per day — and faster termination in time-sensitive windows. But more importantly for the research: it validates that domain-specific guidance can improve search efficiency without sacrificing solution quality, which has implications beyond this specific application.

---

### Q3 — "Are your heuristics admissible? Do they guarantee optimal paths?"

**One-line opener:** *"No — they are guidance penalties, not admissible lower bounds. We trade optimality guarantees for execution-aware steering, and we are explicit about that in the paper."*

**Full answer:** Admissibility would require our heuristics to never overestimate the true remaining cost. Because they are domain-specific calibrations tuned to execution risk — not worst-case bounds — they can overestimate, meaning A* may not return the globally optimal path. We accept that trade-off deliberately. In real-time arbitrage, finding a good executable path quickly is more valuable than proving it is optimal. The fact that h₂ matches Dijkstra's profit within 1% across 7,200 instances suggests the practical cost of inadmissibility is negligible in this domain.

---

### Q4 — "What are the main limitations of this work?"

**One-line opener:** *"Three honest ones: centralized exchanges only, planning not live execution, and heuristic weights require domain tuning."*

**Full answer:** First, this is a CEX-only study — the extension to decentralized exchanges and AMMs is future work. Second, our system is a path planner: it finds routes in simulation but does not place live orders. Bridging the planning-execution gap — handling partial fills, order rejections, and race conditions — is a significant open problem. Third, the lambda parameters in our heuristics were tuned empirically on our dataset; transferring them to a different exchange set or asset class would require retuning. We acknowledge all three in the conclusion.

---

### Q5 — "How do you handle the problem of stale market quotes?"

**One-line opener:** *"We ran a dedicated experiment: 99.6% of found paths remain profitable after two minutes, which defines a practical execution window."*

**Full answer:** After finding a profitable path, we re-evaluated it using fresh market data at delays of 5, 30, 60, 120, and 300 seconds. Up to 120 seconds, 99.6% of paths remained profitable. Beyond 120 seconds the success rate begins to degrade — which tells us something real about how long these discrepancies persist. For a practitioner, this gives a concrete answer: act within two minutes of path discovery for near-certain profitability.

---

### Q6 — "Your paper shows 56.7% success on the cached graph. But you said every run found a profitable path?"

**One-line opener:** *"Those are two different experiments — good catch."*

**Full answer:** The 56.7% figure is from the cached-graph study: we tested thirty fixed starting nodes, and 17 of them had a profitable path reachable from that specific starting point. Not every starting node in the network has an arbitrage opportunity — the market may simply not be in a state where a profitable path exists from node X. The overnight campaign is different: we ran 7,200 searches with varied starting conditions across eight hours of live market data, and in each of those 7,200 instances, A* found a profitable path. The success rate in that setting is 100% because we were not restricted to a fixed set of potentially unprofitable starting nodes.

---

### Q7 — "Could a system like this be used for market manipulation?"

**One-line opener:** *"Arbitrage is generally market-stabilizing — it pushes prices toward equilibrium across venues, not away from it."*

**Full answer:** Our system finds naturally occurring price discrepancies between independent exchanges. It does not place orders that move prices in a coordinated way, and the capital scale we test — $1,000 to $100,000 — is orders of magnitude below what would be required to meaningfully influence a market with $300 billion in capitalization. Arbitrage is broadly considered a stabilizing force: buying cheap and selling dear drives prices toward convergence. The research is intended as a planning and analysis framework, not a deployment-ready trading system.

---

---

# Timing Reference (v2 — 13 slides)

| Slide | Section | Target end | Running total |
|-------|---------|-----------|---------------|
| 1 | Hook — Title | 0:50 | 0:50 |
| 2 | The Market | 1:35 | 1:35 |
| 3 | Price Fragmentation | 2:00 | 2:00 |
| 4 | Execution Barriers | 2:50 | 2:50 |
| 5 | Baselines Fail | 3:10 | 3:10 |
| 6 | The Dataset | 3:40 | 3:40 |
| 7 | A* Method | 4:20 | 4:20 |
| 8 | Three Heuristics | 5:10 | 5:10 |
| 9 | Key Result (−29%) | 5:40 | 5:40 |
| 10 | Profit Quality | 6:00 | 6:00 |
| 11 | Overnight Campaign | 6:22 | 6:22 |
| 12 | Execution Window | 6:38 | 6:38 |
| 13 | Why It Matters + Close | 8:00 | 8:00 |

**Practice tip:** Record yourself once with a timer. Target 7:45–8:10. Slides 9–12 are intentionally short — let the paper figures carry them. Slides 4 and 13 carry the most weight; do not rush them.

---

# What Changed Script → v3 (alignment with slides_v2.pptx)

| Change | Reason |
|--------|--------|
| Added S3 dialogue (Price Fragmentation) | New slide in v2 had no script words |
| Added S5 dialogue (Baselines Fail) | New slide in v2 had no script words |
| Split old Slide 7 Result → S9 + S10 + S11 + S12 | Old slide had 4 distinct data points crammed into one |
| Removed standalone Impact slide | Content folded into S13 Close (Impact + callback combined) |
| Added S10 dialogue (Profit Quality, 20s) | fig03/fig02 added in v2 but unscripted |
| Added S11 dialogue (Overnight, 22s) | fig10/fig11 added in v2 but unscripted |
| Added S12 dialogue (Staleness, 16s) | fig09 added in v2 but unscripted |
| Expanded S13 to include Impact framing | Replaced standalone Slide 8 from old script |
| Updated all timing markers | 9→13 slides, same 8-minute target |
| Updated Visual Guide table | Now 13-row table matching v2 slide names |
