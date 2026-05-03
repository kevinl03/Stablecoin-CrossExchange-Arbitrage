# Response Plan for Hang Ma's Feedback

This document outlines how to address each point raised in Hang Ma's review.

## 1. A* Admissibility and Consistency Issues

### Current State
- Paper acknowledges heuristics are "guidance penalties" not admissible lower bounds
- Section 3.3 states: "We therefore design our heuristics h₁–h₄ as **guidance penalties** rather than admissible lower bounds"
- Weighted A* is mentioned but not fully formalized

### Issues to Address
1. **Admissibility Claim**: Paper mentions admissibility "under path node cost remains constant" - this is unrealistic
2. **Weighted A* Formulation**: Need explicit formula: f(n) = g(n) + w·h(n) with w values
3. **Suboptimality Bounds**: Need to clarify what guarantees exist (or don't exist)

### Action Items
- [ ] **Clarify in Section 3.3**: Explicitly state that heuristics are NOT admissible and explain why this is acceptable for execution-aware search
- [ ] **Formalize Weighted A***: Add explicit formula for H4:
  ```
  f(n) = g(n) + w(n) · h₄(n)
  where w(n) = w_min + (w_max - w_min) · ρ(n)
  w_min = 1.0, w_max = 3.0
  ```
- [ ] **Add Suboptimality Discussion**: Explain that we trade optimality guarantees for execution feasibility
- [ ] **Reference Risk-Averse A* Literature**: Cite work on CVaR/FSD frameworks as suggested

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/3_problem_formulation.tex`
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/4_Novel_Heuristics.tex`

---

## 2. Goal Condition Ambiguity

### Current State
- Section 3.3 defines goal set as: "all nodes where C_k > C_0"
- Paper states this is an "open-path formulation" (not requiring return to start)
- Justification: stablecoins are USD-pegged, so any terminal node holds USD value

### Issues to Address
1. **Clarity**: Need to make goal condition crystal clear
2. **Economic Justification**: Strengthen argument for open-path vs closed-cycle
3. **Marked-to-Market**: Clarify how profit is "realized" in USD

### Action Items
- [ ] **Strengthen Goal Definition**: Add explicit formalization:
  ```
  Goal Set: G = {v_k ∈ V | C_k = C_0 · ∏_{e∈P} r(e) > C_0}
  where profit is marked-to-market in USD at terminal node
  ```
- [ ] **Add Economic Rationale Section**: Explain why open-path is valid:
  - All stablecoins are USD-pegged (within ±2% tolerance)
  - Terminal position value = C_k USD (by construction)
  - No conversion step needed to realize profit
- [ ] **Clarify vs. Standard Arbitrage**: Acknowledge difference from cycle-based literature but justify it

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/3_problem_formulation.tex` (Section 3.3)

---

## 3. H3 as Meta-Heuristic vs Node-Level

### Current State
- H3 is described as "multi-start parallel search"
- It's grouped with node-level heuristics H1, H2, H4

### Issues to Address
1. **Classification**: H3 is a meta-heuristic, not a node-level heuristic
2. **Multi-Agent Confusion**: Title mentions "multi-agent" but H3 is just parallel single-agent search
3. **Separation**: Should be separated from A* optimality discussions

### Action Items
- [ ] **Reorganize Section 4**: 
  - Subsection 4.1-4.3: Node-level heuristics (H1, H2, H4)
  - Subsection 4.4: Meta-heuristic (H3 - multi-start)
- [ ] **Clarify Multi-Agent**: Either:
  - Remove "multi-agent" from title if not modeling multiple agents
  - OR explain if there's a multi-agent interpretation (e.g., parallel searches as "agents")
- [ ] **Update Discussion**: Remove H3 from A* optimality discussions (it's a search strategy, not a heuristic)

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/4_Novel_Heuristics.tex`
- `docs/latex/StablecoinArbitrage_CanadianAI2026/main.tex` (title if needed)

---

## 4. Slippage Double-Counting

### Current State
- Slippage is included in edge effective rates (g(n))
- H2 also penalizes slippage (h₂(n))
- Unclear if this double-counts

### Issues to Address
1. **Clarification Needed**: Is H2 only guidance, or does it modify the objective?
2. **Double-Counting Risk**: If slippage is in both g(n) and h₂(n), it's counted twice

### Action Items
- [ ] **Clarify Edge Construction**: Document exactly what's in effective rates:
  - Trading fees: YES
  - Withdrawal fees: YES
  - Bid-ask spread: YES
  - Slippage: PARTIAL (estimated from order book depth)
- [ ] **Clarify H2 Role**: State explicitly:
  - H2 is **guidance only** (not added to g(n))
  - H2 penalizes **additional slippage risk** beyond what's already in edge costs
  - H2 uses **real-time order book walk** (more accurate than static estimate in g(n))
- [ ] **Add Section**: Explain the distinction between:
  - Static slippage estimate (in g(n)): based on historical/estimated depth
  - Dynamic slippage penalty (in h₂(n)): based on real-time order book

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/3_problem_formulation.tex` (edge construction)
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/4_Novel_Heuristics.tex` (H2 section)

---

## 5. Narrow Evaluation Scope (PARTIALLY ADDRESSED)

### Current State
- Original: 19 nodes, 3 start nodes, single snapshot
- **ADDRESSED**: Overnight testing with 96 snapshots, 5 start nodes per snapshot

### Remaining Issues
1. **Graph Size**: Still relatively small (50-100 nodes)
2. **Heuristic Differentiation**: Need to show cases where heuristics meaningfully differ

### Action Items
- [ ] **Cite Overnight Results**: Reference Figure 10 and 11 showing:
  - 96 snapshots over 8 hours
  - 7,200+ individual searches
  - Temporal variation in heuristic performance
- [ ] **Graph Scaling Experiments**: Reference Figure 6-8 showing scaling to 12 exchanges
- [ ] **Identify Differentiation Cases**: Analyze overnight data to find snapshots where heuristics find different paths/profits
- [ ] **Acknowledge Limitations**: Still paper trading, not live execution

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/5.5_Results.tex`
- Add new subsection on temporal robustness

---

## 6. Missing Parameter Specifications

### Current State
- Parameters mentioned but values not always specified
- λ weights, thresholds, scoring scales, exchange reliability priors

### Issues to Address
1. **Complete Parameter Table**: Need all values documented
2. **Justification**: Why these specific values?

### Action Items
- [ ] **Create Parameter Table**: Document all heuristic parameters:
  ```
  H1 (Liquidity):
    - λ_liq = 1.0 (default, sensitivity tested)
    - Liquidity ratio threshold: log-based scoring
  
  H2 (Slippage):
    - λ_slip = 0.5 (default)
    - Threshold θ = 10.0 bps
    - Unknown slippage penalty = 50.0
  
  H4 (Chain/Exchange Risk):
    - λ_chain = 1.0
    - λ_exchange = 1.0
    - w_min = 1.0, w_max = 3.0
    - Exchange reliability scores: [source needed]
  ```
- [ ] **Add Sensitivity Analysis**: Reference Figures 12-15 showing sensitivity to:
  - H1 λ values
  - H2 λ and threshold
  - Order size
  - Max depth
- [ ] **Document Data Sources**: Where do exchange reliability scores come from?

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/4_Novel_Heuristics.tex`
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/5.4_Evaluation_Methodoloy.tex`
- Add appendix with complete parameter table

---

## 7. Missing Sensitivity Analyses (PARTIALLY ADDRESSED)

### Current State
- **ADDRESSED**: Sensitivity experiments exist (Figures 12-15)
  - H1 λ sensitivity
  - H2 λ and threshold sensitivity
  - Order size sensitivity
  - Max depth sensitivity

### Remaining Issues
1. **Integration**: Need to discuss sensitivity results in main paper
2. **Robustness Claims**: What can we say about parameter robustness?

### Action Items
- [ ] **Add Sensitivity Section**: New subsection in Results:
  - H1: λ=1.0 is robust default (Figure 12)
  - H2: Moderate threshold (10 bps) works well (Figure 13)
  - Order size: Profits scale but % returns vary (Figure 14)
  - Max depth: Diminishing returns beyond 4-5 hops (Figure 15)
- [ ] **Quantify Robustness**: Report parameter ranges where performance is stable

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/5.5_Results.tex`
- Add sensitivity analysis subsection

---

## 8. No End-to-End Execution Validation

### Current State
- All experiments are paper trading
- No actual order placement or execution tracking

### Issues to Address
1. **Realistic Execution**: Quote staleness, latency, actual slippage
2. **Path Survival**: Do identified paths remain profitable after delays?

### Action Items
- [ ] **Cite Quote Staleness Experiment**: Reference Figure 9 showing:
  - Path survival rates under various delay scenarios
  - Fraction of paths that remain profitable after 1s, 5s, 30s delays
- [ ] **Acknowledge Limitation**: Explicitly state:
  - "We validate path feasibility through quote staleness analysis, but do not perform live execution"
  - "Future work should include paper trading with realistic latency simulation"
- [ ] **Add Realistic Scenarios**: Discuss what fraction of identified paths would survive:
  - Typical API latency (100-500ms)
  - Order placement delay (1-5 seconds)
  - Blockchain confirmation time (varies by chain)

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/5.5_Results.tex`
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/6_Conclusion.tex` (future work)

---

## 9. Multi-Agent Path Finding Clarification

### Current State
- Title/abstract may mention "multi-agent"
- H3 is just parallel single-agent search

### Issues to Address
1. **Terminology**: Is this actually multi-agent path finding?
2. **Clarification**: Need to define what "multi-agent" means (if anything)

### Action Items
- [ ] **Review Title/Abstract**: Check if "multi-agent" appears
- [ ] **Clarify or Remove**: Either:
  - Remove "multi-agent" terminology if not applicable
  - OR define: "We use parallel multi-start search (H3) which can be viewed as multiple independent agents exploring the search space"
- [ ] **Separate from H3 Discussion**: Make clear H3 is a search strategy, not a path-finding algorithm for multiple agents

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/0_abstract.tex`
- `docs/latex/StablecoinArbitrage_CanadianAI2026/main.tex` (title)
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/4_Novel_Heuristics.tex` (H3 section)

---

## 10. Ethical Considerations

### Current State
- Section 5.6 exists but may need strengthening

### Issues to Address
1. **Market Manipulation**: Risks of automated arbitrage
2. **Centralization**: Concentration of arbitrage among low-latency actors
3. **MEV Extraction**: Relationship to maximal extractable value
4. **User Risk**: Impact on retail traders

### Action Items
- [ ] **Strengthen Section 5.6**: Add discussion of:
  - **Market Efficiency**: Automated arbitrage improves price discovery
  - **Centralization Risk**: Low-latency infrastructure advantages
  - **MEV Concerns**: Distinguish from front-running/MEV extraction
  - **Regulatory Compliance**: Note that arbitrage is legal market-making
  - **User Impact**: Generally beneficial (reduces spreads) but may disadvantage retail
- [ ] **Add Limitations**: Acknowledge that:
  - System requires significant capital and infrastructure
  - May contribute to market centralization
  - Should be used responsibly

### Files to Modify
- `docs/latex/StablecoinArbitrage_CanadianAI2026/sec/5.6_Ethics.tex`

---

## 11. Additional Questions from Hang Ma

### Q1: What is the exact goal condition?
**Answer**: Open-path formulation where goal = {v_k | C_k > C_0}. Terminal node holds USD-pegged stablecoin, so profit is realized value. See Action Item #2.

### Q2: How do you ensure heuristic admissibility/consistency?
**Answer**: We don't. Heuristics are guidance penalties, not admissible. We trade optimality for execution feasibility. See Action Item #1.

### Q3: How are exchange reliability scores estimated?
**Answer**: [NEED TO DOCUMENT] Currently using static priors? Rolling measurements? Third-party data? See Action Item #6.

### Q4: Did you attempt paper-trading or historical replay?
**Answer**: Quote staleness analysis (Figure 9) simulates delays. No full historical replay. See Action Item #8.

### Q5: Why is "multi-agent path finding" in the title?
**Answer**: [NEED TO CLARIFY] Either remove or define as parallel multi-start search. See Action Item #9.

### Q6: Can you provide scaling experiments?
**Answer**: YES - Figures 6-8 show scaling to 12 exchanges. Overnight testing shows temporal scaling. See Action Item #5.

### Q7: What are the λ weights and thresholds?
**Answer**: Documented in sensitivity experiments (Figures 12-15). Need to add to main paper. See Action Item #6.

### Q8: Compare against 3-hop enumeration baseline?
**Answer**: YES - 3-hop enumeration is included in all experiments and finds same paths when they exist. See Results section.

### Q9: How do you avoid double-counting slippage?
**Answer**: H2 is guidance only (not added to g(n)). H2 uses real-time order book, g(n) uses static estimate. See Action Item #4.

---

## Priority Order

1. **HIGH PRIORITY** (Core Technical Issues):
   - #1: A* Admissibility/Consistency
   - #2: Goal Condition
   - #4: Slippage Double-Counting
   - #9: Multi-Agent Clarification

2. **MEDIUM PRIORITY** (Experimental Validation):
   - #5: Evaluation Scope (cite overnight results)
   - #6: Parameter Specifications
   - #7: Sensitivity Analyses (integrate into paper)
   - #8: End-to-End Execution (cite quote staleness)

3. **LOW PRIORITY** (Clarifications):
   - #3: H3 Classification
   - #10: Ethics (strengthen existing section)

---

## Implementation Checklist

- [ ] Review and update Section 3 (Problem Formulation)
- [ ] Review and update Section 4 (Heuristics)
- [ ] Add sensitivity analysis to Section 5.5 (Results)
- [ ] Strengthen Section 5.6 (Ethics)
- [ ] Create parameter table (Appendix or Section 4)
- [ ] Update abstract/title if needed
- [ ] Add citations to risk-averse A* literature
- [ ] Document exchange reliability score sources
- [ ] Review all figures for consistency with text

