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

## SLIDE 1 · Title · **0:00 – 0:55**

`[SLIDE: Title slide — your name, paper title, GSS 2026 logo, FullGraph.png as full-bleed background image]`

> **Visual:** Use `FullGraph.png` as the slide background at low opacity. The audience sees a dense, beautiful network before you speak. Immediate curiosity — *"what is that?"* — before a single word.

`[DIRECTION: Walk to centre. Make eye contact with three different people. Let two full seconds of silence pass. Do not start talking immediately.]`

*"Before I start — quick show of hands."*

`[DIRECTION: Raise your own hand as you ask.]`

*"How many of you have ever sent money internationally — transferred between banks, used Wise, PayPal, anything like that?"*

`[PAUSE — scan the room, nod.]`

*"Every one of those transfers was routed through a system trying to find the cheapest, fastest path through a global financial network."*

`[BEAT]`

*"What I'm going to show you today is essentially Google Maps... for thirty-three trillion dollars."*

`[DIRECTION: Let that number land. Do not continue immediately. Hold eye contact.]`

---

## SLIDE 2 · The Market · **0:55 – 1:45**

`[SLIDE: Bar chart — Mastercard $8T | Visa $15T | Stablecoins $33T (animated, reveal one bar at a time left to right). USDT and USDC logos beside the stablecoin bar.]`

> **Visual:** The bars should animate in one at a time, left to right, on click. The stablecoin bar should be noticeably taller — the contrast is the whole point. No need for the speaker to describe it; the image does the work.

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

## SLIDE 3 · The Problem · **1:45 – 2:55**

`[SLIDE: Split image — LEFT: a clean A→B profitable cycle (green arrow, simple). RIGHT: the same path with four red warning icons appearing one at a time: a fee tag, a price impact curve, a clock, an exchange suspension warning.]`

> **Visual:** The left half shows what existing systems see — a clean arbitrage cycle. The right half reveals the execution reality. Animate the four icons on click, synchronized with the four spoken challenges.

`[DIRECTION: Step slightly forward. This is where tension builds.]`

*"Imagine you are a quant trader. It is two in the morning. You are watching prices across twelve different exchanges and you see it — USDT is trading fractionally cheaper on Kraken than it is selling for on KuCoin. The gap is real. The math works."*

*"Existing systems would tell you: there is an arbitrage opportunity here. Take it."*

`[BEAT]`

*"But here is what those systems do not tell you."*

`[DIRECTION: Count on fingers — slow, deliberate, one beat after each.]`

*"First — the taker fee at each exchange eats into your margin.*

*Second — your order size is large enough that buying on Kraken moves the price against you before your fill is complete. That is called slippage. Dynamic, live, and invisible to static models.*

*Third — the blockchain transfer between exchanges takes time. The window may close while you are waiting for confirmations.*

*Fourth — an exchange might suspend withdrawals entirely. We have seen this happen overnight, without warning."*

`[PAUSE]`

*"Liquidity. Slippage. Latency. Reliability."*

`[BEAT]`

*"Bellman-Ford finds the cycle. One-hop and two-hop enumeration find the cycle. In our experiments, all three baselines fail entirely — they cannot identify a profitable executable path under these conditions. We needed something different."*

---

## SLIDE 4 · The Graph · **2:55 – 3:40**

`[SLIDE: FullGraph.png — full slide, clean, with one highlighted path glowing through it. Label: "12 exchanges · 41 nodes · 864 edges · Live market data"]`

> **Visual:** Use the actual FullGraph.png image from the paper at full resolution. Overlay a single coloured path through the graph to show what the search is trying to find. The four label terms appear as small annotations. This visual replaces ~150 words of verbal description — point to it, don't recite it.

`[DIRECTION: Gesture toward the slide. Let the image carry the weight here.]`

*"This is our dataset. The actual network we built."*

*"Every dot is a trading pair on one of twelve exchanges. Every line is a possible trade or cross-exchange transfer — and it carries the complete real-world cost of that action: the taker fee, the live slippage estimate from the order book, the gas cost, and the venue's reliability score."*

*"To our knowledge, this is the first execution-aware graph dataset built specifically for stablecoin arbitrage research."*

`[PAUSE]`

*"The question is: which path through this network, starting from any node, ends with more dollars than you started with — and can actually be executed?"*

---

## SLIDE 5 · A* Search · **3:40 – 4:30**

`[SLIDE: Side-by-side animation. LEFT panel labelled "Dijkstra" — nodes light up in a broad expanding wave. RIGHT panel labelled "A* with h₂" — a narrow directed beam reaches the goal with fewer nodes explored. A counter shows node expansion count under each. The right counter stops at ~70% of the left.]`

> **Visual:** This is the single most important visual in the deck. The 29% reduction must be *seen* before it is said. Animate on click: both panels expand simultaneously so the audience sees the contrast live.

*"Our core algorithm is A* search — the same search strategy that powers GPS navigation and game AI. The key insight: instead of exploring every possible path, A* uses an evaluation function, f of n equals g of n plus h of n, to decide which node to expand next."*

*"g of n is the cost of the path so far. h of n is our heuristic — a domain-specific estimate of the execution risk ahead. Together they steer the search toward paths that are not just short, but feasible."*

*"Think of it like Google Maps during rush hour. It does not just find the shortest route. It weights the toll, the traffic density, the road reliability. It steers you toward the path you can actually take — not just the one that looks best on a map."*

*"That is exactly what we are doing. Except the map is a live financial network, and the traffic is real-time order-book data."*

---

## SLIDE 6 · Three Heuristics · **4:30 – 5:25**

`[SLIDE: Three vertical panels, each with an icon and one-line label. Reveal one panel at a time on click.]`
`[Panel 1 — h₁: water depth gauge icon. Label: "Liquidity — Is there enough market depth?"]`
`[Panel 2 — h₂: price impact curve icon. Label: "Slippage ★ — Does my order move the price?"]`
`[Panel 3 — h₃: chain link + clock icon. Label: "Chain + Venue — Will it settle in time?"]`

> **Visual:** Keep each panel clean: one icon, one line, the heuristic formula in small text below for the technical audience. Mark h₂ with a star — it is the novel contribution and the one that works.

*"We designed three guidance heuristics. Each one estimates a different dimension of execution risk, and each adds that estimate to the priority function — steering A* away from paths that look profitable but cannot be executed."*

`[DIRECTION: Reveal each panel as you name it. One breath between each. Do not rush through them.]`

*"Heuristic one: Liquidity. Is there enough market depth in this venue to support our order size right now, without exhausting the book?*

*Heuristic two: Slippage. This is our novel contribution. Using live order-book data, we compute the volume-weighted average price of filling our order — and penalize paths where that price diverges too far from the mid-price. It is dynamic. It updates with the market.*

*Heuristic three: Chain congestion and exchange reliability. How long will the blockchain transfer take? And how operationally reliable is this particular venue?"*

`[BEAT]`

*"One of these three will prove decisive."*

---

## SLIDE 7 · The Result · **5:25 – 6:20**

`[SLIDE: Two-part layout. TOP: fig01_node_expansion_bar.png — the bar chart (Dijkstra vs h₁ vs h₂ vs h₃), with h₂ bar highlighted in SFU red. "−29%" annotation visible. BOTTOM: CameraReadySuccesfulPathProfit.png — an actual found profitable path, labelled with the profit amount ($9.91 on $10k).]`

> **Visual:** The bar chart is the evidence. The found path image is the proof of life — it makes the abstract concrete. The profit label should be large and readable from the back of the room.

`[DIRECTION: Slow down. Every sentence here gets its own breath. This is the payoff.]`

*"Here is what we found."*

`[PAUSE]`

*"Our slippage-aware heuristic — h-two — achieved the same profit quality as the Dijkstra baseline. Within one percent."*

`[PAUSE]`

*"But it did so using twenty-nine percent fewer node expansions."*

`[BEAT]`

*"Same destination. Same profit. Twenty-nine percent less work."*

`[PAUSE]`

*"And this — "*

`[DIRECTION: Gesture to the bottom image on the slide.]`

*" — is a real path our system found. Kraken to KuCoin, USDT to TUSD. Nine dollars and ninety-one cents profit on a ten-thousand dollar order. Found in under ten milliseconds of search time."*

*"We ran this across an eight-hour overnight campaign — seven thousand two hundred search instances, live market data, continuous operation. Every A* run in that campaign found a profitable path. When we re-evaluated those paths two minutes later, accounting for quotes that had gone stale — ninety-nine point six percent were still profitable."*

*"That is not a simulation artifact. That is a system working under real market conditions."*

---

## SLIDE 8 · Why It Matters · **6:20 – 7:25**

`[SLIDE: Left half — a world map with cryptocurrency exchange logos at major financial centres. Right half — a price divergence chart showing the same stablecoin at two different prices across two exchanges during a period of market stress. Small annotation: "February 2022 — crypto markets during geopolitical shock."]`

> **Visual:** The price divergence chart makes the abstract tangible. Show an actual divergence event — not hypothetical. If you have one from your overnight data, use it. The geographic map gives spatial intuition for why twelve independent exchanges exist.

`[DIRECTION: Energy rises here. This is the vision. Speak with conviction.]`

*"Now you might be thinking — this is a niche trading problem. Why does it belong at an AI conference?"*

`[BEAT]`

*"Consider what happens to stablecoin markets during moments of geopolitical shock. A war breaks out. A government announces an exchange freeze. A major venue halts withdrawals overnight. These are the moments when price discrepancies across independent exchanges spike — not by fractions of a percent, but by meaningful margins, in real time."*

*"A system that can navigate those disruptions — twenty-nine percent more efficiently than the baseline — is not just a trading tool. It is a lens for understanding how fragmented financial markets behave under stress. That is a research question with implications well beyond cryptocurrency."*

*"And the framework we built here is a foundation. Decentralized exchanges — Uniswap, Curve — are the natural next frontier. Continuous pricing invariants, automated market makers, on-chain liquidity: a richer search space that demands exactly this kind of execution-aware pathfinding."*

*"The market is expanding. The navigation tools need to scale with it."*

---

## SLIDE 9 · Close · **7:25 – 8:00**

`[SLIDE: FullGraph.png again — full bleed, same opening image — but now a single glowing path runs through it end to end. Text overlay, centred, large: "Less Exploration. More Execution. Same Profit."]`

> **Visual:** This is the visual callback. The audience saw this graph at the start, before you spoke. Now it has meaning. The single glowing path is the answer to the question you opened with.

`[DIRECTION: Return to centre. Slow your pace to below your normal speaking speed. This is the callback.]`

*"We started with a question: how do you find the most profitable, actually executable path through a thirty-three trillion dollar market?"*

*"The answer: model the ecosystem as a graph. Encode every real-world cost as an edge weight. Apply A* search, guided by a slippage-aware heuristic that steers search toward paths the market can actually support."*

`[PAUSE]`

*"Less exploration. More execution. Same profit."*

`[PAUSE — two full seconds. Make eye contact. Do not add anything.]`

*"Thank you."*

`[DIRECTION: Hold the silence after "Thank you." Do not add "...any questions?" Let the room respond.]`

---

---

# Slide Visual Guide — Quick Reference

| Slide | Key visual | Source |
|-------|-----------|--------|
| 1 — Title | FullGraph.png at low opacity as background | `docs/latex/.../figures/FullGraph.png` |
| 2 — Market | Animated bar chart: MC $8T / Visa $15T / Stablecoins $33T | Create in PowerPoint |
| 3 — Problem | Split: clean cycle LEFT / four red warning icons RIGHT (animated) | Create in PowerPoint |
| 4 — The Graph | FullGraph.png full slide with one highlighted path | `figures/FullGraph.png` |
| 5 — A* Method | Side-by-side animated expansion: Dijkstra wave vs. A* beam | Create in PowerPoint |
| 6 — Heuristics | Three panels with icons, revealed one at a time | Create in PowerPoint |
| 7 — Result | TOP: fig01 bar chart (h₂ highlighted) + BOTTOM: profitable path image | `figures/fig01_node_expansion_bar.png` + `figures/CameraReadySuccesfulPathProfit.png` |
| 8 — Impact | World map + price divergence chart | Create / find real data |
| 9 — Close | FullGraph.png again + glowing path + three-word text overlay | `figures/FullGraph.png` |

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

# Timing Reference

| Section | Slide | Target end | Running total |
|---------|-------|-----------|---------------|
| Hook | Title | 0:55 | 0:55 |
| The Market | $33T Bar Chart | 1:45 | 1:45 |
| The Problem | Split Warning Icons | 2:55 | 2:55 |
| The Graph | FullGraph | 3:40 | 3:40 |
| A* Method | Side-by-Side Animation | 4:30 | 4:30 |
| Heuristics | Three Panels | 5:25 | 5:25 |
| Result | Bar Chart + Path | 6:20 | 6:20 |
| Impact | World Map + Divergence | 7:25 | 7:25 |
| Close | FullGraph + Glowing Path | 8:00 | 8:00 |

**Practice tip:** Record yourself once with a timer. Target 7:45–8:10. The `[PAUSE]` and `[DIRECTION]` markers consume approximately 50 seconds of the 8 minutes — do not skip them, they are not dead time.

---

# What Changed in This Revision (v2)

| Issue | Fix |
|-------|-----|
| Research question never stated | Added explicitly in Slide 2: "Can we build a system smart enough to find and execute a profitable path through that fragmentation?" |
| "Every A* run found a profitable path" conflated two experiments | Clarified: overnight campaign (7,200 instances) vs. cached graph (56.7%). Added Q6 to handle the likely challenge |
| `h(n)` described as "adding to search cost" (wrong framing) | Slide 5 now correctly describes f(n) = g(n) + h(n) with g(n) and h(n) defined separately |
| Airport analogy conflated slippage and liquidity | Split: Slide 3 mentions slippage correctly; h₁/h₂ distinction preserved in Slide 6 |
| Bellman-Ford / baseline failure never mentioned | Added to Slide 3: "all three baselines fail entirely" |
| No personal/human moment | Added: "Imagine you are a quant trader. It is two in the morning..." in Slide 3 |
| No tension before result reveal | Added: "One of these three will prove decisive." at end of Slide 6 |
| Slide 8 ended on a limitation ("only built the foundation") | Reframed as forward momentum: "The framework we built here is a foundation" |
| Q1 Bellman-Ford answer contained error | Fixed: now correctly distinguishes closed-cycle vs. open-path problem structure |
| No slides actually designed | Added full Slide Visual Guide with figure sources and slide-by-slide design specs |
| Visual spec missing from script | Every slide now has a `> Visual:` block with exact content and source |
