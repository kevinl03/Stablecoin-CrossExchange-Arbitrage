"""
A* Arbitrage Path-Finding — Step-by-Step Search Visualization
=============================================================
Demonstrates how A* finds a profitable cross-exchange arbitrage path,
using the same exchange-clustered graph style as the Streamlit UI.

Four panels:
  1. Full graph with Dijkstra expansion (f = g)
  2. Full graph with A* expansion   (f = g + h) — fewer nodes explored
  3. Heuristic breakdown — how h(n) is computed from L2 order books
  4. L2 Order Book depth chart with slippage zone highlighted

Usage:
    python scripts/visualize_astar_demo.py
    python scripts/visualize_astar_demo.py --save
"""

from __future__ import annotations

import sys
import os
import math
import heapq
import argparse
from dataclasses import dataclass, field
from typing import List, Tuple, Dict, Optional, Set
from collections import defaultdict

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, Rectangle
from matplotlib.gridspec import GridSpec
import networkx as nx

# ─── Exchange colour palette (matches scripts/ui.py) ─────────────────────────

EXCHANGE_COLORS = {
    "Binance":  "#F6C344",
    "Kraken":   "#C792D6",
    "Bybit":    "#F2917C",
    "Gate.io":  "#7BA4F4",
    "OKX":      "#A98ED6",
}

# ─── Manufactured L2 order books (realistic depths from statarb data) ─────────

ORDER_BOOKS = {
    ("Binance", "USDC/USDT"): {
        "bids": [(1.00012, 387_318), (1.00011, 1_900_946), (1.00010, 2_391_894),
                 (1.00009, 1_496_781), (1.00008, 624_382), (1.00007, 1_627_266)],
        "asks": [(1.00013, 236_434), (1.00014, 766_831), (1.00015, 2_294_582),
                 (1.00016, 4_990_147), (1.00017, 1_569_348), (1.00018, 2_159_827)],
    },
    ("Kraken", "USDC/USDT"): {
        "bids": [(0.9998, 74_081), (0.9997, 17_715), (0.9996, 11_175),
                 (0.9995, 3_772), (0.9994, 7_069), (0.9993, 4_065)],
        "asks": [(0.9999, 38_136), (1.0000, 24_409), (1.0001, 45_012),
                 (1.0002, 7_125), (1.0003, 11_176), (1.0004, 2_446)],
    },
    ("Bybit", "USDC/USDT"): {
        "bids": [(1.0001, 8_497_869), (1.0000, 5_340_531), (0.9999, 2_378_217),
                 (0.9998, 100_473), (0.9997, 1_067_564), (0.9996, 160_215)],
        "asks": [(1.0002, 5_466_613), (1.0003, 4_225_412), (1.0004, 3_023_116),
                 (1.0005, 1_526_735), (1.0006, 521_941), (1.0007, 635_750)],
    },
    ("Gate.io", "USDC/USDT"): {
        "bids": [(1.0007, 4_925), (1.0006, 4_811), (1.0005, 1_000),
                 (1.0004, 8_085), (1.0003, 1_000), (1.0002, 8_783)],
        "asks": [(1.0008, 6_605), (1.0009, 8_023), (1.0010, 41_181),
                 (1.0011, 7_885), (1.0012, 22_283), (1.0013, 9_227)],
    },
    ("OKX", "USDC/USDT"): {
        "bids": [(1.0000, 2_300_000), (0.9999, 1_500_000), (0.9998, 800_000)],
        "asks": [(1.0001, 1_800_000), (1.0002, 900_000), (1.0003, 400_000)],
    },
}


def compute_slippage_bps(book: dict, size: float, side: str = "buy") -> float:
    """Walk the L2 book and return slippage in bps for *size* units."""
    levels = book["asks"] if side == "buy" else book["bids"]
    if not levels:
        return 50.0
    filled = 0.0
    cost = 0.0
    for price, qty in levels:
        take = min(qty, size - filled)
        cost += take * price
        filled += take
        if filled >= size:
            break
    if filled == 0:
        return 50.0
    avg_price = cost / filled
    ref_price = levels[0][0]
    return abs(avg_price - ref_price) / ref_price * 10_000


# ─── Graph definition ────────────────────────────────────────────────────────

NodeId = Tuple[str, str]  # (exchange, coin)


@dataclass
class Edge:
    src: NodeId
    dst: NodeId
    kind: str          # "trade" | "transfer"
    fee_bps: float     # actual edge cost (g contribution)
    transfer_time_s: float = 0.0
    book_key: Optional[Tuple[str, str]] = None


def build_demo_graph() -> Tuple[nx.DiGraph, List[Edge]]:
    """Build a manufactured but realistic stablecoin cross-exchange graph."""

    coins = ["USDT", "USDC", "DAI"]
    exchanges = ["Binance", "Kraken", "Bybit", "Gate.io", "OKX"]

    G = nx.DiGraph()
    edges: List[Edge] = []

    for ex in exchanges:
        for coin in coins:
            if ex == "OKX" and coin == "DAI":
                continue
            if ex == "Gate.io" and coin == "DAI":
                continue
            G.add_node((ex, coin), exchange=ex, coin=coin)

    # ── Intra-exchange trades ──
    trade_defs = [
        ("Binance", "USDT", "USDC", 0.8, ("Binance", "USDC/USDT")),
        ("Binance", "USDC", "USDT", 0.8, ("Binance", "USDC/USDT")),
        ("Binance", "USDT", "DAI",  1.5, None),
        ("Binance", "DAI",  "USDT", 1.5, None),
        ("Binance", "USDC", "DAI",  1.6, None),
        ("Binance", "DAI",  "USDC", 1.6, None),
        ("Kraken",  "USDT", "USDC", 2.0, ("Kraken", "USDC/USDT")),
        ("Kraken",  "USDC", "USDT", 2.0, ("Kraken", "USDC/USDT")),
        ("Kraken",  "USDT", "DAI",  2.5, None),
        ("Kraken",  "DAI",  "USDT", 2.5, None),
        ("Bybit",   "USDT", "USDC", 1.0, ("Bybit", "USDC/USDT")),
        ("Bybit",   "USDC", "USDT", 1.0, ("Bybit", "USDC/USDT")),
        ("Bybit",   "USDT", "DAI",  1.8, None),
        ("Bybit",   "DAI",  "USDT", 1.8, None),
        ("Gate.io", "USDT", "USDC", 1.2, ("Gate.io", "USDC/USDT")),
        ("Gate.io", "USDC", "USDT", 1.2, ("Gate.io", "USDC/USDT")),
        ("OKX",     "USDT", "USDC", 0.9, ("OKX", "USDC/USDT")),
        ("OKX",     "USDC", "USDT", 0.9, ("OKX", "USDC/USDT")),
    ]
    for ex, c1, c2, fee, bk in trade_defs:
        e = Edge((ex, c1), (ex, c2), "trade", fee, 0.0, bk)
        edges.append(e)
        G.add_edge((ex, c1), (ex, c2), kind="trade", fee_bps=fee, time_s=0)

    # ── Inter-exchange transfers ──
    xfer_defs = [
        ("Binance", "Kraken",  "USDT", 0.5,  90),
        ("Binance", "Kraken",  "USDC", 0.4, 120),
        ("Kraken",  "Binance", "USDT", 0.7,  70),
        ("Kraken",  "Binance", "USDC", 0.6, 100),
        ("Binance", "Bybit",   "USDT", 0.3,  45),
        ("Bybit",   "Binance", "USDT", 0.4,  50),
        ("Binance", "Bybit",   "USDC", 0.3,  60),
        ("Bybit",   "Binance", "USDC", 0.4,  55),
        ("Bybit",   "Gate.io", "USDT", 0.5, 120),
        ("Gate.io", "Bybit",   "USDT", 0.6, 130),
        ("Gate.io", "Bybit",   "USDC", 0.5, 140),
        ("Bybit",   "Gate.io", "USDC", 0.4, 110),
        ("Kraken",  "OKX",     "USDT", 1.0, 200),
        ("OKX",     "Kraken",  "USDT", 0.9, 180),
        ("OKX",     "Binance", "USDC", 0.5, 150),
        ("Binance", "OKX",     "USDC", 0.4, 160),
        ("Gate.io", "OKX",     "USDT", 0.8, 250),
        ("OKX",     "Gate.io", "USDT", 0.9, 240),
        ("Kraken",  "Gate.io", "USDT", 1.2, 300),
        ("Binance", "Gate.io", "USDT", 0.6, 100),
        ("Gate.io", "Binance", "USDT", 0.7, 110),
        ("Kraken",  "Bybit",   "USDC", 0.8, 180),
        ("Bybit",   "Kraken",  "USDC", 0.7, 170),
    ]
    for ex_f, ex_t, coin, fee, t in xfer_defs:
        if not G.has_node((ex_f, coin)) or not G.has_node((ex_t, coin)):
            continue
        e = Edge((ex_f, coin), (ex_t, coin), "transfer", fee, t, None)
        edges.append(e)
        G.add_edge((ex_f, coin), (ex_t, coin), kind="transfer", fee_bps=fee, time_s=t)

    return G, edges


# ─── Search algorithms with step logging ─────────────────────────────────────

@dataclass(order=True)
class SearchState:
    f: float
    g: float = field(compare=False)
    node: NodeId = field(compare=False)
    path: List[NodeId] = field(compare=False, default_factory=list)
    depth: int = field(compare=False, default=0)


def heuristic(edge: Edge, trade_size: float = 50_000) -> float:
    """h(n): slippage from L2 book + time-volatility exposure."""
    h = 0.0
    if edge.book_key and edge.book_key in ORDER_BOOKS:
        h += compute_slippage_bps(ORDER_BOOKS[edge.book_key], trade_size, "buy")
    elif edge.kind == "transfer":
        h += 0.0
    else:
        h += 3.0  # unknown book penalty
    # Time-decay risk: ~1.5 bps/min stablecoin vol exposure
    h += edge.transfer_time_s / 60.0 * 1.5
    return h


def run_search(
    G: nx.DiGraph,
    edges: List[Edge],
    start: NodeId,
    use_heuristic: bool,
    trade_size: float = 50_000,
    max_depth: int = 5,
) -> Tuple[List[NodeId], List[NodeId], List[Tuple[NodeId, NodeId]]]:
    """
    Run Dijkstra (use_heuristic=False) or A* (True).
    Returns: (best_cycle, expansion_order, explored_edge_pairs)
    """
    adj: Dict[NodeId, List[Edge]] = defaultdict(list)
    for e in edges:
        adj[e.src].append(e)

    frontier = [SearchState(0.0, 0.0, start, [start], 0)]
    expansion_order: List[NodeId] = []
    explored_edges: List[Tuple[NodeId, NodeId]] = []
    best_cycle: List[NodeId] = []
    best_cost = float("inf")
    visited: Set[Tuple[NodeId, int]] = set()

    while frontier:
        state = heapq.heappop(frontier)
        key = (state.node, state.depth)
        if key in visited:
            continue
        visited.add(key)
        expansion_order.append(state.node)

        if len(state.path) > 2 and state.node == start:
            if state.g < best_cost:
                best_cost = state.g
                best_cycle = state.path[:]
            continue

        if state.depth >= max_depth:
            continue

        for edge in adj[state.node]:
            new_g = state.g + edge.fee_bps
            h = heuristic(edge, trade_size) if use_heuristic else 0.0
            new_f = new_g + h
            explored_edges.append((edge.src, edge.dst))
            new_path = state.path + [edge.dst]
            heapq.heappush(frontier, SearchState(new_f, new_g, edge.dst, new_path, state.depth + 1))

    return best_cycle, expansion_order, explored_edges


# ─── Layout (ring of exchange clusters) ──────────────────────────────────────

def layout_positions(G: nx.DiGraph) -> Dict[NodeId, Tuple[float, float]]:
    """Place exchanges in a ring; coins clustered inside each exchange."""
    exchanges = list(dict.fromkeys(G.nodes[n]["exchange"] for n in G.nodes()))
    n_ex = len(exchanges)
    ring_r = 5.0
    node_spread = 0.75
    pos = {}
    for i, ex in enumerate(exchanges):
        angle = 2 * math.pi * i / n_ex - math.pi / 2
        cx = ring_r * math.cos(angle)
        cy = ring_r * math.sin(angle)
        ex_nodes = sorted([n for n in G.nodes() if G.nodes[n]["exchange"] == ex],
                          key=lambda n: n[1])
        n_coins = len(ex_nodes)
        for j, node in enumerate(ex_nodes):
            sub_angle = 2 * math.pi * j / max(n_coins, 1) - math.pi / 2
            pos[node] = (cx + node_spread * math.cos(sub_angle),
                         cy + node_spread * math.sin(sub_angle))
    return pos


# ─── Drawing ──────────────────────────────────────────────────────────────────

def draw_graph_panel(
    ax: plt.Axes,
    G: nx.DiGraph,
    pos: Dict[NodeId, Tuple[float, float]],
    expansion_order: List[NodeId],
    best_cycle: List[NodeId],
    explored_edges: List[Tuple[NodeId, NodeId]],
    title: str,
):
    """Draw exchange-clustered graph with search exploration overlaid."""
    ax.set_title(title, fontsize=11, fontweight="bold", pad=12)
    ax.axis("off")
    ax.set_aspect("equal")

    # ── Exchange cluster boxes ──
    exchanges = list(dict.fromkeys(G.nodes[n]["exchange"] for n in G.nodes()))
    for ex in exchanges:
        ex_nodes = [n for n in G.nodes() if G.nodes[n]["exchange"] == ex]
        xs = [pos[n][0] for n in ex_nodes]
        ys = [pos[n][1] for n in ex_nodes]
        cx, cy = np.mean(xs), np.mean(ys)
        pad = 1.2
        w = max(max(xs) - min(xs) + pad, 2.0)
        h = max(max(ys) - min(ys) + pad, 2.0)
        color = EXCHANGE_COLORS.get(ex, "#808080")

        rect = FancyBboxPatch(
            (cx - w / 2, cy - h / 2), w, h,
            boxstyle="round,pad=0.15",
            linewidth=2.0,
            edgecolor=color,
            facecolor=color + "18",
            linestyle="--",
            zorder=0,
        )
        ax.add_patch(rect)
        ax.text(cx, cy + h / 2 + 0.15, ex, ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=color)

    # ── Edges ──
    explored_set = set(explored_edges)
    cycle_edge_set: Set[Tuple[NodeId, NodeId]] = set()
    if best_cycle and len(best_cycle) > 1:
        for i in range(len(best_cycle) - 1):
            cycle_edge_set.add((best_cycle[i], best_cycle[i + 1]))

    for u, v, data in G.edges(data=True):
        kind = data.get("kind", "trade")
        if (u, v) in cycle_edge_set:
            color, alpha, lw = "#D32F2F", 1.0, 3.0
        elif (u, v) in explored_set:
            color = "#2E7D32" if kind == "transfer" else "#555555"
            alpha, lw = 0.55, 1.0
        else:
            color = "#CCCCCC"
            alpha, lw = 0.18, 0.5

        style = "-" if kind == "trade" else (0, (4, 3))
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)],
            edge_color=color, width=lw, alpha=alpha,
            arrows=True, arrowsize=10, arrowstyle="->",
            style=style, ax=ax,
            connectionstyle="arc3,rad=0.1",
        )

    # ── Nodes ──
    expanded_set = set(expansion_order)
    cycle_set = set(best_cycle) if best_cycle else set()

    for node in G.nodes():
        x, y = pos[node]
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        base_color = EXCHANGE_COLORS.get(ex, "#808080")

        if node in cycle_set:
            fc, ec, tc = "#D32F2F", "#B71C1C", "white"
        elif node in expanded_set:
            fc, ec, tc = "white", base_color, "#222222"
        else:
            fc, ec, tc = "#F5F5F5", "#CCCCCC", "#AAAAAA"

        circle = plt.Circle((x, y), 0.38, facecolor=fc,
                            edgecolor=ec, linewidth=2.2, zorder=4)
        ax.add_patch(circle)
        ax.text(x, y, coin, ha="center", va="center",
                fontsize=7.5, fontweight="bold", color=tc, zorder=5)

        # Expansion badge
        if node in expanded_set:
            idx = expansion_order.index(node)
            ax.text(x + 0.30, y + 0.30, str(idx + 1),
                    ha="center", va="center", fontsize=5.5, fontweight="bold",
                    color="#D32F2F",
                    bbox=dict(boxstyle="round,pad=0.08", facecolor="white",
                              edgecolor="#D32F2F", linewidth=0.6),
                    zorder=6)

    # ── Stats ──
    n_exp = len(set(expansion_order))
    n_edg = len(explored_edges)
    ax.text(0.02, 0.02, f"Nodes expanded: {n_exp}\nEdges explored: {n_edg}",
            transform=ax.transAxes, fontsize=7.5, va="bottom", ha="left",
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF9C4",
                      edgecolor="#F9A825", linewidth=0.8))

    # ── Legend ──
    legend = [
        mpatches.Patch(facecolor="white", edgecolor="#555", linewidth=1, label="Trade (intra-exch)"),
        mpatches.Patch(facecolor="white", edgecolor="#2E7D32", linewidth=1, label="Transfer (cross-exch)"),
        mpatches.Patch(facecolor="#D32F2F", edgecolor="#B71C1C", linewidth=1, label="Optimal cycle found"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=6.5, framealpha=0.92,
              edgecolor="#CCC")


def draw_heuristic_panel(ax: plt.Axes, edges: List[Edge], trade_size: float):
    """Bar chart showing h(n) decomposition for sample edges."""
    ax.set_title(r"Heuristic $h(n)$: Slippage + Time-Decay Risk",
                 fontsize=11, fontweight="bold", pad=10)

    # Select diverse edges
    samples: List[Edge] = []
    seen = set()
    for e in edges:
        key = (e.src[0], e.kind)
        if key not in seen and len(samples) < 6:
            seen.add(key)
            samples.append(e)

    labels, slip_vals, time_vals = [], [], []
    for e in samples:
        labels.append(f"{e.src[0][:3]}→{e.dst[0][:3]}\n{e.src[1]}→{e.dst[1]}\n({e.kind})")
        if e.book_key and e.book_key in ORDER_BOOKS:
            slip = compute_slippage_bps(ORDER_BOOKS[e.book_key], trade_size, "buy")
        elif e.kind == "transfer":
            slip = 0.0
        else:
            slip = 3.0
        slip_vals.append(slip)
        time_vals.append(e.transfer_time_s / 60.0 * 1.5)

    x = np.arange(len(labels))
    w = 0.5
    ax.bar(x, slip_vals, w, label="Slippage from L2 book",
           color="#FF7043", alpha=0.85, edgecolor="#BF360C", linewidth=0.5)
    ax.bar(x, time_vals, w, bottom=slip_vals,
           label=r"Time-decay risk ($\sigma \cdot \sqrt{\Delta t}$)",
           color="#42A5F5", alpha=0.85, edgecolor="#1565C0", linewidth=0.5)

    for i, (s, t) in enumerate(zip(slip_vals, time_vals)):
        ax.text(i, s + t + 0.08, f"h={s+t:.2f}", ha="center", va="bottom",
                fontsize=7, fontweight="bold", color="#333")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=6.5)
    ax.set_ylabel("Heuristic cost (bps)", fontsize=9)
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(axis="y", alpha=0.2)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    formula = (r"$f(n) = g(n) + h(n)$"
               r"$\quad$where$\quad$"
               r"$h = \mathrm{slippage}_{L2}(n) + \sigma\cdot\sqrt{\Delta t}$")
    ax.text(0.5, 0.93, formula, transform=ax.transAxes, ha="center", va="top",
            fontsize=10, color="#1A237E",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#E8EAF6",
                      edgecolor="#3F51B5", linewidth=1))


def draw_orderbook_panel(ax: plt.Axes, exchange: str, pair: str, trade_size: float):
    """L2 depth chart with slippage zone."""
    ax.set_title(f"L2 Order Book — {exchange} {pair}", fontsize=11,
                 fontweight="bold", pad=10)

    book = ORDER_BOOKS.get((exchange, pair))
    if not book:
        ax.text(0.5, 0.5, "No book data", ha="center", va="center",
                transform=ax.transAxes)
        return

    bids, asks = book["bids"], book["asks"]
    bid_prices = [b[0] for b in bids]
    bid_cum = np.cumsum([b[1] for b in bids]) / 1e6
    ask_prices = [a[0] for a in asks]
    ask_cum = np.cumsum([a[1] for a in asks]) / 1e6

    ax.fill_between(bid_prices, 0, bid_cum, alpha=0.25, color="#4CAF50", step="post")
    ax.step(bid_prices, bid_cum, where="post", color="#2E7D32", linewidth=1.8, label="Bids")
    ax.fill_between(ask_prices, 0, ask_cum, alpha=0.25, color="#F44336", step="post")
    ax.step(ask_prices, ask_cum, where="post", color="#C62828", linewidth=1.8, label="Asks")

    # Trade size marker
    ax.axhline(y=trade_size / 1e6, color="#FF9800", linestyle="--", linewidth=1.5,
               alpha=0.8, label=f"Trade size ({trade_size/1000:.0f}K)")

    # Slippage zone
    slippage = compute_slippage_bps(book, trade_size, "buy")
    filled, fill_price = 0.0, asks[0][0]
    for price, qty in asks:
        filled += qty
        if filled >= trade_size:
            fill_price = price
            break
    if fill_price > asks[0][0]:
        ax.axvspan(asks[0][0], fill_price, alpha=0.12, color="#FF9800",
                   label=f"Slippage zone ({slippage:.3f} bps)")

    # Mid price
    mid = (bids[0][0] + asks[0][0]) / 2
    ax.axvline(x=mid, color="#9E9E9E", linestyle=":", linewidth=1, alpha=0.7)

    spread_bps = (asks[0][0] - bids[0][0]) / mid * 10_000
    ax.text(0.03, 0.95,
            f"Spread: {spread_bps:.2f} bps\nSlippage @{trade_size/1000:.0f}K: {slippage:.3f} bps",
            transform=ax.transAxes, ha="left", va="top", fontsize=8,
            bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF3E0",
                      edgecolor="#E65100", linewidth=0.8))

    ax.set_xlabel("Price", fontsize=9)
    ax.set_ylabel("Cumulative Depth (M units)", fontsize=9)
    ax.legend(fontsize=7, loc="upper right")
    ax.grid(alpha=0.15)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.ticklabel_format(useOffset=False, style="plain", axis="x")
    ax.tick_params(axis="x", labelsize=7)


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="A* Arbitrage Visualization Demo")
    parser.add_argument("--save", action="store_true", help="Save to docs/figures/")
    parser.add_argument("--trade-size", type=float, default=50_000)
    args = parser.parse_args()

    G, edges = build_demo_graph()
    start: NodeId = ("Binance", "USDT")

    # Run both searches
    dij_cycle, dij_order, dij_edges = run_search(G, edges, start, use_heuristic=False, trade_size=args.trade_size)
    ast_cycle, ast_order, ast_edges = run_search(G, edges, start, use_heuristic=True, trade_size=args.trade_size)

    print("=" * 65)
    print("  A* ARBITRAGE PATH-FINDING — SEARCH VISUALIZATION")
    print("=" * 65)
    print(f"  Start: {start}")
    print(f"  Trade size: {args.trade_size:,.0f} units")
    print(f"\n  Dijkstra  f(n) = g(n):")
    print(f"    Nodes expanded : {len(set(dij_order))}")
    print(f"    Edges explored : {len(dij_edges)}")
    print(f"    Best cycle     : {' -> '.join(f'{n[0][:3]}:{n[1]}' for n in dij_cycle) if dij_cycle else 'none'}")
    print(f"\n  A*  f(n) = g(n) + h(n):")
    print(f"    Nodes expanded : {len(set(ast_order))}")
    print(f"    Edges explored : {len(ast_edges)}")
    print(f"    Best cycle     : {' -> '.join(f'{n[0][:3]}:{n[1]}' for n in ast_cycle) if ast_cycle else 'none'}")
    reduction = (1 - len(set(ast_order)) / max(len(set(dij_order)), 1)) * 100
    print(f"\n  Node expansion reduction: {reduction:.1f}%")
    print("=" * 65)

    # ── Build figure ──
    pos = layout_positions(G)

    fig = plt.figure(figsize=(16, 14), facecolor="white")
    fig.suptitle("A* Search for Cross-Exchange Stablecoin Arbitrage\n",
                 fontsize=14, fontweight="bold", y=0.99)

    gs = GridSpec(2, 2, figure=fig, hspace=0.32, wspace=0.25,
                  left=0.04, right=0.97, top=0.94, bottom=0.04)

    # Panel 1: Dijkstra
    ax1 = fig.add_subplot(gs[0, 0])
    draw_graph_panel(ax1, G, pos, dij_order, dij_cycle, dij_edges,
                     "Dijkstra: f(n) = g(n) only\n(blind — explores uniformly)")

    # Panel 2: A*
    ax2 = fig.add_subplot(gs[0, 1])
    draw_graph_panel(ax2, G, pos, ast_order, ast_cycle, ast_edges,
                     "A*: f(n) = g(n) + h(n)\n(guided by slippage heuristic)")

    # Panel 3: Heuristic breakdown
    ax3 = fig.add_subplot(gs[1, 0])
    draw_heuristic_panel(ax3, edges, args.trade_size)

    # Panel 4: L2 Order Book
    ax4 = fig.add_subplot(gs[1, 1])
    draw_orderbook_panel(ax4, "Binance", "USDC/USDT", args.trade_size)

    if args.save:
        os.makedirs("docs/figures", exist_ok=True)
        out_path = "docs/figures/astar_arbitrage_demo.png"
        fig.savefig(out_path, dpi=200, bbox_inches="tight", facecolor="white")
        print(f"\n  Saved -> {out_path}")
    else:
        plt.show()


if __name__ == "__main__":
    main()

