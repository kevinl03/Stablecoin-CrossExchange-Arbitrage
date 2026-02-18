# Paper-Ready Graph Visualization

## Overview

A new conference-ready visualization has been implemented based on feedback for CAIAC/CVPR-style papers. This visualization emphasizes **clarity, structure, and interpretability** over decorative elements.

## Design Principles

✅ **Structured Layout**: 2×2 grid of exchange blocks (modular block model)  
✅ **Clean Styling**: White background, minimal clutter  
✅ **Clear Encoding**: 
   - Nodes: White fill, colored borders, asset names only (no prices)
   - Intra-exchange edges: Thin, low opacity (0.3), exchange color
   - Inter-exchange edges: Thick (2.0), dark green, full opacity
   - Highlighted cycle: Bold red (3.5 width) with "Cycle P" label

✅ **Exchange Partitioning**: Each exchange shown as a distinct block with:
   - Exchange name as title
   - Node count (|V| = N) for graph-theoretic clarity
   - Subtle dashed border in exchange color

## How to Use

### In Streamlit UI

1. Open the Streamlit UI: `streamlit run scripts/ui.py`
2. In the "Arbitrage Graph" section, check the **"Paper-ready visualization"** checkbox
3. The graph will automatically:
   - Arrange exchanges in a structured 2×2 grid
   - Highlight a profitable cycle if one exists (optional)
   - Apply clean, conference-appropriate styling

### Programmatically

```python
from scripts.ui import make_paper_ready_figure
import networkx as nx

# Build your graph
G = build_nx_graph()

# Option 1: Without highlighted cycle
fig = make_paper_ready_figure(G)

# Option 2: With highlighted cycle
highlight_cycle = [(ex1, coin1), (ex2, coin2), ...]  # List of nodes
fig = make_paper_ready_figure(
    G, 
    highlight_cycle=highlight_cycle,
    show_cycle_label=True
)

# Save for paper
fig.savefig("arbitrage_graph.pdf", dpi=300, bbox_inches="tight")
fig.savefig("arbitrage_graph.png", dpi=300, bbox_inches="tight")
```

## Figure Caption (Suggested)

> **Figure X:** Structured cross-exchange arbitrage graph. Each block represents an exchange containing fully connected stablecoin trading pairs. Thin edges denote intra-exchange trades, while thick green edges represent inter-exchange asset transfers. A highlighted cycle (red) illustrates a profitable arbitrage opportunity identified by the search algorithm.

## Key Differences from Debug Visualization

| Debug Version | Paper-Ready Version |
|--------------|---------------------|
| Circular cluster layout | Structured 2×2 grid |
| Grey background | White background |
| Prices on nodes | Asset names only |
| All edges same weight | Hierarchical edge weights |
| Exchange:Coin labels | Exchange as block title |
| No cycle highlighting | Optional cycle highlight |

## Technical Details

- **Layout Algorithm**: Grid-based positioning with automatic spacing
- **Node Arrangement**: 
  - 1 node: Centered
  - 2-4 nodes: 2×2 grid
  - 5+ nodes: Circular arrangement
- **Edge Filtering**: Automatically separates intra-exchange (trade) and inter-exchange (transfer) edges
- **Cycle Detection**: Optionally finds and highlights profitable paths using A* search

## Export Settings for Papers

For best quality in papers:

```python
fig.savefig(
    "arbitrage_graph.pdf",
    dpi=300,
    bbox_inches="tight",
    facecolor="white",
    edgecolor="none"
)
```

Recommended figure width for 2-column papers: `0.8\linewidth` in LaTeX.

## Color Scheme

- **Binance**: `#FFD700` (Gold)
- **Kraken**: `#9C27B0` (Purple)
- **KuCoin**: `#00BCD4` (Cyan)
- **Bybit**: `#E91E63` (Pink/Magenta)
- **Coinbase**: `#2196F3` (Blue)
- **Inter-exchange edges**: `#2E7D32` (Dark Green)
- **Highlighted cycle**: `#D32F2F` (Red)

All colors are chosen for maximum visual distinction and accessibility.



