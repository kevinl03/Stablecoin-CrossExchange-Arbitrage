# Execution-Aware A* Search for Cross-Exchange Stablecoin Arbitrage

**Kevin Litvin** -- Simon Fraser University

[![Paper](https://img.shields.io/badge/Paper-PDF-red.svg)](docs/latex/StablecoinArbitrage_GSS2026/Execution_Aware_A_Star_Search_for_Cross_Exchange_Stablecoin_Arbitrage_GSS2026.pdf)
[![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

> **[Read the Paper (PDF)](docs/latex/StablecoinArbitrage_GSS2026/Execution_Aware_A_Star_Search_for_Cross_Exchange_Stablecoin_Arbitrage_GSS2026.pdf)**
>
> Published at the Canadian AI 2026 Graduate Student Symposium (GSS).

---

## Abstract

Cross-exchange cryptocurrency arbitrage enables low-risk profit from price discrepancies across exchanges, yet existing approaches employ negative cycle detection that targets opportunity identification rather than execution feasibility. We introduce an **execution-aware pathfinding framework** using **A\* search** with domain-specific guidance heuristics, applied to stablecoins -- a unique asset class exceeding $300 billion in market capitalization. The problem is modelled as a weighted directed graph where nodes represent (exchange, stablecoin) pairs across 12 centralized exchanges and edges encode real-world costs including fees, slippage, gas, transfer delays, and exchange reliability. Three guidance heuristics and a multi-start strategy are evaluated over 7,200 search instances. Our slippage-aware heuristic h2 reduces node expansions by 29% relative to Dijkstra while matching its profit, demonstrating that domain-specific heuristics can meaningfully improve execution feasibility in real-time arbitrage planning.

## Demo

[![Stablecoin Arbitrage Demo](https://img.youtube.com/vi/Fuu5OI83uMY/0.jpg)](https://www.youtube.com/watch?v=Fuu5OI83uMY)

**Watch on YouTube**: https://www.youtube.com/watch?v=Fuu5OI83uMY

---

## Repository Structure

```
.
├── README.md
├── requirements.txt
├── scripts/              # Core implementation
│   ├── ui.py             #   Streamlit interactive UI
│   ├── astar_vol.py      #   A* search with volatility
│   ├── graph.py           #   Graph construction from live data
│   ├── data.py            #   Exchange data fetching (CCXT)
│   ├── fees.py            #   Fee models
│   ├── h1_vol.py          #   h1: volume/liquidity heuristic
│   ├── h2_slippage.py     #   h2: order-book slippage heuristic
│   ├── h3_parallel.py     #   h3: multi-start parallel A*
│   ├── h4_chaincongestion_exchange_risk.py  # h4: risk-weighted A*
│   ├── run_ui.sh          #   Launch Streamlit (background)
│   └── stop_ui.sh         #   Stop Streamlit
├── experiments/          # Reproducible experiment scripts
│   ├── monte_carlo_simulation.py
│   ├── compare_heuristics_live.py
│   ├── sensitivity_sweep.py
│   └── ...
├── results/              # Raw experiment outputs and logs
├── analysis/             # Figure generation for the paper
├── testing/              # Verification and debugging utilities
└── docs/
    ├── latex/            # LaTeX source for the papers
    │   ├── StablecoinArbitrage_GSS2026/   # GSS paper (primary)
    │   └── StablecoinArbitrage_CAIAC2026/           # Full-length paper
    ├── img/              # README images
    ├── videos/           # Demo recordings
    └── internal/         # Development notes and analysis docs
```

## Getting Started

### Prerequisites

- Python 3.12+
- pip

### Installation

```bash
git clone https://github.com/kevinl03/Stablecoin-CrossExchange-Arbitrage.git
cd Stablecoin-CrossExchange-Arbitrage

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt
```

### Run the Interactive UI

```bash
streamlit run scripts/ui.py
```

Opens at http://localhost:8501. Initial load takes ~1 minute while fetching live market data from all exchanges.

### Run Experiments

```bash
# Monte Carlo simulation (10 trials per heuristic)
python experiments/monte_carlo_simulation.py

# Live heuristic comparison
python experiments/compare_heuristics_live.py

# Sensitivity analysis
python experiments/sensitivity_sweep.py
```

---

## Heuristics Overview

| Heuristic | Strategy | Strength |
|-----------|----------|----------|
| **h1** (volume) | Prefers high-liquidity routes using 24h trading volume | Reliable execution, 100% success rate |
| **h2** (slippage) | Walks the order book to estimate actual price impact | Best for large orders; 29% fewer expansions than Dijkstra |
| **h3** (parallel) | Multi-start A\* from random entry points | Discovers diverse opportunities |
| **h4** (risk-weighted) | Penalises congested chains and unreliable exchanges | 10--20x faster; production-oriented |

See the paper for full experimental comparison across 7,200 search instances.

---

## Citation

If you use this code or build on this work, please cite:

```bibtex
@inproceedings{litvin2026execution,
  title     = {Execution-Aware {A*} Search for Cross-Exchange Stablecoin Arbitrage},
  author    = {Litvin, Kevin},
  booktitle = {Proceedings of the 39th Canadian Conference on Artificial Intelligence,
               Graduate Student Symposium (Canadian AI GSS)},
  year      = {2026}
}
```

## License

This project is released under the [MIT License](LICENSE).
