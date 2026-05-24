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
> - Target pace: ~130 words per minute (practiced). Total spoken words: ~1000.
> - Audience: graduate students and researchers in CS / AI. Lean technical without going dry. Skip consumer metaphors until the very end; respect the room.

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

> **Visual:** Dense network graph visible behind the title before you speak. The graph IS the hook — let the audience read it for two seconds.

`[DIRECTION: Walk to centre. Two full seconds of silence. Make eye contact with three different people before you open your mouth.]`

*"At any given moment, the same digital asset can be trading at a dozen different prices simultaneously across independent exchanges."*

`[PAUSE]`

*"This is fragmentation — both the problem and the opportunity. And the stablecoin market, where it happens, moved more than thirty-three trillion dollars last year."*

`[BEAT]`

*"I'm Kevin Litvin from Simon Fraser University. This talk is about a pathfinding algorithm that turns that fragmentation into structured, executable profit — and a heuristic that makes the search itself dramatically more efficient."*

---

## SLIDE 2 · The Market · **0:35 – 1:25**

`[SLIDE: S2 — Stablecoin scale visual. Suggested: stablecoin annual on-chain volume + $300B market cap as primary callouts; stablecoin share of crypto settlement as supporting bar. Source citation as small footer link on the slide — do NOT say verbally.]`

> **Visual:** Lead with the $33T figure and the network graph. The previous Visa/Mastercard comparison was an apples-to-oranges scale framing — replaced with crypto-internal share of volume, which is the relevant comparison.

*"Stablecoins — USDT, USDC, DAI — are blockchain-native dollars pegged one-to-one with fiat. Roughly three hundred billion dollars in circulation. Thirty-three trillion dollars in annual on-chain volume."*

`[PAUSE]`

*"To put that in context: stablecoins are the dominant settlement asset for cross-exchange capital movement in crypto markets. They are how traders rebalance positions, how cross-border settlements clear, how liquidity moves between venues."*

`[BEAT]`

*"And they're listed across more than a dozen independent centralized exchanges — same coin, slightly different price on each, at the exact same instant."*

`[PAUSE]`

*"So the question this research asks:"*

`[BEAT]`

*"Can domain-specific heuristics steer search through that fragmentation faster than general-purpose graph algorithms — without sacrificing profit quality?"*

`[PAUSE — let it land. Advance.]`

---

## SLIDE 3 · The Problem · **1:25 – 2:30**

`[SLIDE: S3 — Four (or five) execution-cost cards: Fees / Slippage ★ / Latency / Operational Risk. Bottom punchline strip: "Bellman-Ford · 1-hop · 2-hop enumeration — none found a profitable executable path."]`

> **Visual:** Reveal each card on click as you name it. The novel one (slippage) gets a star and a different colour. Punchline strip appears last.

`[DIRECTION: Step slightly forward. Speak in clean technical phrases — no theatrics.]`

*"Why does this need new search machinery? Why not just run shortest-path on the price graph?"*

`[BEAT]`

*"Because four real-world costs collapse most candidate paths the moment you try to execute them."*

`[DIRECTION: Count on fingers — one breath between each.]`

*"One — fees. Taker fees compound across every hop."*

*"Two — slippage. As a large order fills, it walks down the L2 order book — the live ladder of bids and asks at each price level — executing at progressively worse prices."*

*"Three — latency. Cross-exchange transfers settle on-chain. Block times and congestion eat the execution window."*

*"Four — operational risk. Withdrawals can be paused, regions geofenced or VPN-blocked. A path that exists on paper can be unreachable in practice."*

`[PAUSE]`

*"We tested three classical baselines — Bellman-Ford negative-cost detection, one-hop, and two-hop enumeration. None of them returned a profitable executable path under live conditions."*

`[BEAT]`

*"We needed search that builds execution cost directly into the heuristic itself."*

---

## SLIDE 4 · The Dataset · **2:30 – 3:05**

`[SLIDE: S4 — FullGraph.png on the left. Stats panel on the right: 12 exchanges / 9 stablecoin symbols / 41 nodes / 864 edges. Below the stats: small list of what each edge carries — fee, L2-derived slippage, gas, reliability.]`

> **Visual:** Let the graph image carry the weight. Gesture to it; do not narrate the colours.

`[DIRECTION: Gesture toward the graph image.]`

*"This is the graph we built."*

*"Forty-one nodes — each a stablecoin on one of twelve centralized exchanges. Eight hundred sixty-four directed edges. Each edge encodes the live execution cost of that hop: taker fee, slippage from the venue's L2 order book, on-chain settlement cost, and a venue-reliability discount."*

`[PAUSE]`

*"To our knowledge, this is the first academically integrated centralized-exchange stablecoin dataset assembled for arbitrage-style search."*

`[BEAT]`

*"Goal: find a path that ends with more dollars than it started — with every execution cost accounted for."*

---

## SLIDE 5 · Method: A* · **3:05 – 3:50**

`[SLIDE: S5 — f(n) = g(n) + h(n) displayed large. Below it: pipeline diagram: Live L2 Order Books → Execution-Aware Graph → A* + h(n) → Profitable Path.]`

> **Visual:** Formula front and centre. Pipeline below shows what comes in and what comes out. Audience is CS — they don't need GPS metaphors, they need the precise statement.

*"Our search backbone is A* — best-first graph search with a goal-directed heuristic."*

`[BEAT]`

*"Quick refresher: A* is Dijkstra's algorithm plus a heuristic. True accumulated cost g of n, plus an estimate h of n of the cost remaining. f equals g plus h decides which node we expand next."*

`[PAUSE]`

*"In our setup, g of n carries the accumulated execution cost — fees, slippage, gas, reliability. h of n is where our contribution lives: a domain-specific estimate of the execution risk still ahead."*

`[BEAT]`

*"One important note for later: A* with h equal to zero is just Dijkstra — exhaustive best-first by cost. So Dijkstra on the same execution-aware graph is our profit-quality reference. The heuristic is what saves the work."*

---

## SLIDE 6 · Three Heuristics · **3:50 – 4:45**

`[SLIDE: S6 — Three panels: h₁ Liquidity (blue) / h₂ ★ Slippage (red) / h₃ Chain+Venue (green). Each panel: short name, one-line definition, and the formula. Right side: slippage curve illustrating VWAP divergence as order size grows.]`

> **Visual:** Reveal each panel as you name it. Star h₂. The slippage curve on the right gives technical depth without needing extra words.

*"We designed three execution-aware heuristics. Each adds a domain-specific penalty to h of n — steering A* away from paths that look profitable on paper but are too risky to execute under live costs."*

`[DIRECTION: Reveal each panel as you name it. One breath between each.]`

*"h-one — Liquidity. Queries the live L2 order book from each venue and penalises hops where the available depth is too thin to absorb our order size."*

*"h-two — Slippage. From the same L2 book, computes a volume-weighted execution price and penalises paths where the VWAP diverges from the mid-quote. Updates in real time as the book moves."*

*"h-three — Chain and venue risk. Penalty proportional to on-chain settlement time, plus a discount for venue reliability."*

`[BEAT]`

*"In our experiments, one of these three consistently outperforms the others."*

---

## SLIDE 7 · The Result · **4:45 – 5:25**

`[SLIDE: S7 — fig01_node_expansion_bar.png full-screen. h₂ bar highlighted in SFU red. "−29%" annotation large. Header: "h₂ — 29% fewer node expansions · profit within 1% of Dijkstra".]`

> **Visual:** The bar chart is the entire message. The 29% gap must be readable from the back of the room. Slow down here.

`[DIRECTION: Slow down. Let each sentence land before the next.]`

*"Here is the headline."*

`[PAUSE]`

*"The slippage heuristic — h-two — matched Dijkstra's profit quality within one percent across the test set."*

`[BEAT]`

*"While expanding twenty-nine percent fewer nodes."*

`[PAUSE]`

*"That is a measurable efficiency gain from domain-specialized guidance, with no meaningful loss in solution quality."*

`[BEAT]`

*"And it holds at scale — seven thousand two hundred independent searches across eight consecutive hours of live market data."*

---

## SLIDE 8 · Real-World Proof · **5:25 – 6:05**

`[SLIDE: S8 — TOP half: fig10_overnight_timeseries.png. BOTTOM half: fig09_quote_staleness.png. Right callouts: "7,200 searches · 8 continuous hours" and "99.6% still profitable at +2 min".]`

> **Visual:** Two stacked plots. Top shows results held continuously through the overnight campaign; bottom shows the path stays valid for a meaningful window after discovery.

`[DIRECTION: Brief pause after advancing to this slide.]`

*"To stress-test this, we ran what we call our overnight campaign — eight hours of continuous A* search against twelve live exchange feeds. Two findings stand out."*

`[BEAT]`

*"First — across all seven thousand two hundred searches, the algorithm consistently surfaced profitable executable paths. Reproducible at high volume, not a one-off."*

`[PAUSE]`

*"Second — staleness. There is always a gap between finding a path and being able to act on it: operator review, transfer confirmation. So we measured how long an opportunity actually persists. Ninety-nine point six percent of paths were still profitable two minutes after discovery. After that, the market converges."*

`[BEAT]`

*"Practical execution window: about one hundred and twenty seconds."*

---

## SLIDE 9 · Why It Matters + Close · **6:05 – 8:00**

`[SLIDE: S9 — FullGraph.png full-bleed dark. LEFT: three lines large — "Less Exploration. / More Execution. / Same Profit." RIGHT: fig18_radar_summary.png — method comparison radar across all metrics.]`

> **Visual:** Callback to the title-slide graph — now meaningful. The radar on the right summarizes the full method comparison so judges can read the holistic story.

`[DIRECTION: Energy rises first for the "why it matters" section, then pace drops for the close.]`

*"Why does this matter beyond stablecoin trading?"*

`[BEAT]`

*"Picture two people running the same search on the same graph. One uses general-purpose graph search. The other uses our domain-specialized heuristic. Both find the same profitable path — ours gets there with twenty-nine percent less compute and twenty-nine percent less latency."*

`[BEAT]`

*"In a market with a hundred-and-twenty-second execution window, that's a structural edge."*

`[BEAT]`

*"More broadly, this is a template for execution-aware search in any fragmented marketplace — decentralized exchanges, AMMs, on-chain liquidity. That's the natural next frontier."*

`[PAUSE]`

`[DIRECTION: Return to centre. Slow your pace.]`

*"We asked: can heuristic guidance steer search through a fragmented market faster than general-purpose algorithms — without sacrificing profit?"*

`[PAUSE]`

*"The short answer is yes."*

`[BEAT]`

*"Less exploration. More execution. Same profit."*

`[PAUSE — two full seconds. Make eye contact.]`

*"Or, if you prefer the consumer analogy: Google Maps, for thirty-three trillion dollars in stablecoin volume."*

`[BEAT]`

*"Thank you."*

`[DIRECTION: Hold the silence. Do not add "...any questions?" — let the room respond.]`

---

---

# Slide Visual Guide

| Slide | Title | Key visual | Source |
|-------|-------|-----------|--------|
| 1 | Title | FullGraph.png full-bleed dark background | `figures/FullGraph.png` |
| 2 | The Market | Stablecoin volume + market cap callouts + share-of-crypto-volume supporting bar (citation as slide footer link) | Generated |
| 3 | The Problem | Four execution-cost cards (Fees / Slippage★ / Latency / Operational Risk) + "all baselines fail" punchline | Generated |
| 4 | The Dataset | FullGraph.png + stats (12 exch / 9 coins / 41 nodes / 864 edges) + edge-payload list | `figures/FullGraph.png` |
| 5 | A* Method | f(n) formula + L2→graph→A*→path pipeline diagram | Generated |
| 6 | Three Heuristics | Three panels (h₁/h₂★/h₃) + slippage / VWAP-divergence curve | Generated |
| 7 | The Result | fig01_node_expansion_bar.png full-screen hero, h₂ in red, −29% large | `figures/fig01_node_expansion_bar.png` |
| 8 | Real-World Proof | TOP: fig10 overnight timeseries · BOTTOM: fig09 quote staleness | `figures/fig10_overnight_timeseries.png` + `fig09` |
| 9 | Close | FullGraph.png dark + three-line summary + fig18 radar | `figures/FullGraph.png` + `figures/fig18_radar_summary.png` |

---

---

# Q&A Rebuttal Preparation

> Lead with the **one-line opener** every time. Elaborate only if the questioner follows up.
> Aim for 30–45 seconds per answer. Do not over-explain.

---

### Q1 — "Why A\* and not Bellman-Ford or negative cycle detection?"

**One-line opener:** *"Bellman-Ford with negative-cycle detection solves a different problem — closed cycles on a static graph, with no execution costs modeled."*

**Full answer:** Traditional stablecoin arbitrage work formulates the problem as negative-cycle detection on the price graph — a closed loop where the product of exchange rates exceeds one. That framing has two issues for us. First, it ignores all execution costs: fees, slippage, on-chain delays, operational risk. Second, it requires returning to the starting asset, which is an unnecessary constraint when all assets are dollar-pegged stablecoins. Our formulation is an open-path one: find any path ending with more USD than we started, with execution costs fully accounted for. A* with goal-directed termination is the right tool, and the three classical baselines we tested — Bellman-Ford, one-hop, and two-hop enumeration — all failed to produce a profitable executable path under live conditions.

---

### Q2 — "Is a 29% reduction in node expansions practically significant?"

**One-line opener:** *"The significance is not just compute — it's that the heuristic is genuinely informative about execution risk, which is what we wanted to prove."*

**Full answer:** A 29% reduction in node expansions while matching profit quality within 1% tells us h₂'s slippage estimate is doing real work — A* is being guided toward the same high-quality routes Dijkstra finds, but with fewer wasted expansions on paths that would have failed under execution costs. In deployment, that's lower compute at scale and faster termination inside time-sensitive windows. For the research contribution, it validates that domain-specific guidance can improve efficiency without trading away solution quality.

---

### Q3 — "Are your heuristics admissible? Do you guarantee optimal paths?"

**One-line opener:** *"No — they are guidance penalties, not admissible lower bounds. We trade optimality guarantees for execution-aware steering, and we're explicit about that in the paper."*

**Full answer:** Admissibility requires the heuristic to never overestimate the true remaining cost. Ours are domain-specific risk penalties tuned to execution conditions, so they can overestimate — meaning A* may not return the globally optimal path. We accept that deliberately. In real-time arbitrage-like search, a good executable path found quickly beats proving optimality. And empirically, h₂ matches Dijkstra's profit within 1% across 7,200 instances, which suggests the practical cost of inadmissibility is negligible in this regime.

---

### Q4 — "What are the main limitations?"

**One-line opener:** *"Three honest ones: centralised exchanges only, planning rather than live execution, and heuristic weights that need domain tuning."*

**Full answer:** First, CEX-only — extending to DEXs is future work. Second, we plan paths but do not place live orders; bridging the planning-to-execution gap (partial fills, rejections, race conditions, MEV) is an open problem. Third, the lambda parameters in our heuristics were tuned on this dataset; applying to a different exchange set or asset class would require retuning. All three are discussed in the conclusion.

---

### Q5 — "How do you handle stale market quotes?"

**One-line opener:** *"We measured it directly: 99.6% of found paths remain profitable two minutes after discovery — and that defines the execution window."*

**Full answer:** After A* surfaces a path, we re-evaluated it under fresh order books at delays of 5, 30, 60, 120, and 300 seconds. Up through 120 seconds the success rate stays at 99.6%. Past that, the rate degrades as the market converges. That gives us a concrete practical answer: act within two minutes of path discovery.

---

### Q6 — "Your paper shows 56.7% success on the cached graph. But you said every overnight run found a path?"

**One-line opener:** *"They're two different experiments — good catch."*

**Full answer:** The 56.7% figure is from the cached-graph study: 30 fixed starting nodes, 17 of which had a reachable profitable path. Not every starting node has an arbitrage opportunity — the market may not support one from node X at that moment. The overnight campaign is a different setup: 7,200 searches with varied starting conditions across 8 hours of live data. Across that campaign the algorithm consistently surfaced profitable executable paths, because we weren't restricted to a fixed set of potentially unprofitable starting nodes.

---

### Q7 — "Could this be used for market manipulation?"

**One-line opener:** *"Arbitrage-style trading is broadly price-stabilising — it pushes prices toward equilibrium, not away from it."*

**Full answer:** Our system finds naturally occurring discrepancies between independent exchanges. It does not coordinate orders to move prices, and the capital scale we test — $1,000 to $100,000 — is orders of magnitude below what would move a $300B market. Arbitrage of this form is considered stabilising in market microstructure: buying cheap and selling dear drives convergence. This is a planning and analysis framework, not a deployment-ready trading system.

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

**Practice tip:** Record yourself once with a timer. Target 7:45–8:10. S7 is the structural climax — slow down and breathe through the 29%. S9 is your widest range: open with energy on "two people running the same search," drop to slow and quiet for "Less exploration. More execution. Same profit." The Google Maps line at the end is a deliberate wink — earned by everything before it, never offered as the opener.
