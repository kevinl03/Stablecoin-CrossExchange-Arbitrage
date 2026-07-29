"""
A* Arbitrage Search — Animated Step-by-Step Expansion
=====================================================
Produces a GIF + individual PNG frames showing each node expansion:
  - Each frame = one node popped from A*'s priority queue
  - Nodes show exchange:coin with simulated price
  - Edges show fee (bps) for trades and transfers
  - Yellow = currently expanding, orange = frontier, red = profitable cycle

Usage:
    python scripts/animate_astar_search.py              # GIF + frames
    python scripts/animate_astar_search.py --fps 2      # slower GIF
    python scripts/animate_astar_search.py --no-frames  # GIF only
"""

from __future__ import annotations

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
from matplotlib.patches import FancyBboxPatch
from matplotlib.animation import FuncAnimation, PillowWriter
import networkx as nx

# ─── Exchange palette (same as ui.py) ────────────────────────────────────────

EXCHANGE_COLORS = {
    "Binance":  "#F6C344",
    "Kraken":   "#C792D6",
    "Bybit":    "#F2917C",
    "Gate.io":  "#7BA4F4",
    "OKX":      "#A98ED6",
}

# ─── Manufactured L2 order books ─────────────────────────────────────────────

ORDER_BOOKS = {
    ("Binance", "USDC/USDT"): {
        "bids": [(1.00012, 387_318), (1.00011, 1_900_946), (1.00010, 2_391_894),
                 (1.00009, 1_496_781), (1.00008, 624_382), (1.00007, 1_627_266)],
        "asks": [(1.00013, 236_434), (1.00014, 766_831), (1.00015, 2_294_582),
                 (1.00016, 4_990_147), (1.00017, 1_569_348), (1.00018, 2_159_827)],
    },
    ("Kraken", "USDC/USDT"): {
        "bids": [(0.9998, 74_081), (0.9997, 17_715), (0.9996, 11_175)],
        "asks": [(0.9999, 38_136), (1.0000, 24_409), (1.0001, 45_012)],
    },
    ("Bybit", "USDC/USDT"): {
        "bids": [(1.0001, 8_497_869), (1.0000, 5_340_531), (0.9999, 2_378_217)],
        "asks": [(1.0002, 5_466_613), (1.0003, 4_225_412), (1.0004, 3_023_116)],
    },
    ("Gate.io", "USDC/USDT"): {
        "bids": [(1.0007, 4_925), (1.0006, 4_811), (1.0005, 1_000)],
        "asks": [(1.0008, 6_605), (1.0009, 8_023), (1.0010, 41_181)],
    },
    ("OKX", "USDC/USDT"): {
        "bids": [(1.0000, 2_300_000), (0.9999, 1_500_000)],
        "asks": [(1.0001, 1_800_000), (1.0002, 900_000)],
    },
}


def compute_slippage_bps(book: dict, size: float, side: str = "buy") -> float:
    levels = book["asks"] if side == "buy" else book["bids"]
    if not levels:
        return 50.0
    filled, cost = 0.0, 0.0
    for price, qty in levels:
        take = min(qty, size - filled)
        cost += take * price
        filled += take
        if filled >= size:
            break
    if filled == 0:
        return 50.0
    avg_price = cost / filled
    return abs(avg_price - levels[0][0]) / levels[0][0] * 10_000


# ─── Graph ────────────────────────────────────────────────────────────────────

NodeId = Tuple[str, str]


@dataclass
class Edge:
    src: NodeId
    dst: NodeId
    kind: str
    fee_bps: float
    transfer_time_s: float = 0.0
    book_key: Optional[Tuple[str, str]] = None
    rate: float = 1.0  # multiplicative conversion rate


# Simulated prices for display (stablecoins near $1.00)
NODE_PRICES = {
    ("Binance", "USDT"):  1.0001,
    ("Binance", "USDC"):  1.0000,
    ("Binance", "DAI"):   0.9998,
    ("Kraken", "USDT"):   0.9999,
    ("Kraken", "USDC"):   0.9997,
    ("Kraken", "DAI"):    0.9995,
    ("Bybit", "USDT"):    1.0002,
    ("Bybit", "USDC"):    1.0001,
    ("Bybit", "DAI"):     0.9997,
    ("Gate.io", "USDT"):  1.0003,
    ("Gate.io", "USDC"):  1.0001,
    ("OKX", "USDT"):      1.0000,
    ("OKX", "USDC"):      0.9999,
}


def build_graph() -> Tuple[nx.DiGraph, List[Edge]]:
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
            price = NODE_PRICES.get((ex, coin), 1.0000)
            G.add_node((ex, coin), exchange=ex, coin=coin, price_usd=price)

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
        rate = 1.0 - fee / 10_000  # fee_bps → multiplicative rate
        e = Edge((ex, c1), (ex, c2), "trade", fee, 0.0, bk, rate)
        edges.append(e)
        G.add_edge((ex, c1), (ex, c2), kind="trade", fee_bps=fee, time_s=0, rate=rate)

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
        rate = 1.0 - fee / 10_000
        e = Edge((ex_f, coin), (ex_t, coin), "transfer", fee, t, None, rate)
        edges.append(e)
        G.add_edge((ex_f, coin), (ex_t, coin), kind="transfer", fee_bps=fee, time_s=t, rate=rate)

    return G, edges


# ─── A* with full step recording ─────────────────────────────────────────────

@dataclass
class StepSnapshot:
    """State of the search at one expansion step."""
    expanded_so_far: List[NodeId]         # nodes already expanded (in order)
    current_node: NodeId                  # node being expanded this step
    frontier_edges: List[Tuple[NodeId, NodeId]]  # edges just added to frontier
    best_cycle: Optional[List[NodeId]]    # cycle found so far (or None)
    f_value: float
    g_value: float
    h_value: float


@dataclass(order=True)
class SearchState:
    f: float
    g: float = field(compare=False)
    node: NodeId = field(compare=False)
    path: List[NodeId] = field(compare=False, default_factory=list)
    depth: int = field(compare=False, default=0)
    h_at_entry: float = field(compare=False, default=0.0)


def heuristic(edge: Edge, trade_size: float = 50_000) -> float:
    h = 0.0
    if edge.book_key and edge.book_key in ORDER_BOOKS:
        h += compute_slippage_bps(ORDER_BOOKS[edge.book_key], trade_size, "buy")
    elif edge.kind == "transfer":
        h += 0.0
    else:
        h += 3.0
    h += edge.transfer_time_s / 60.0 * 1.5
    return h


def run_astar_with_steps(
    G: nx.DiGraph,
    edges: List[Edge],
    start: NodeId,
    trade_size: float = 50_000,
    max_depth: int = 5,
) -> List[StepSnapshot]:
    """Run A* and record a snapshot at every node expansion."""
    adj: Dict[NodeId, List[Edge]] = defaultdict(list)
    for e in edges:
        adj[e.src].append(e)

    frontier = [SearchState(0.0, 0.0, start, [start], 0, 0.0)]
    visited: Set[Tuple[NodeId, int]] = set()
    steps: List[StepSnapshot] = []
    expanded_so_far: List[NodeId] = []
    best_cycle: Optional[List[NodeId]] = None
    best_cost = float("inf")

    while frontier:
        state = heapq.heappop(frontier)
        key = (state.node, state.depth)
        if key in visited:
            continue
        visited.add(key)

        expanded_so_far.append(state.node)

        # Check cycle
        if len(state.path) > 2 and state.node == start:
            if state.g < best_cost:
                best_cost = state.g
                best_cycle = state.path[:]
            steps.append(StepSnapshot(
                expanded_so_far=expanded_so_far[:],
                current_node=state.node,
                frontier_edges=[],
                best_cycle=best_cycle[:] if best_cycle else None,
                f_value=state.f,
                g_value=state.g,
                h_value=state.h_at_entry,
            ))
            continue

        if state.depth >= max_depth:
            expanded_so_far.pop()  # don't count depth-limited
            continue

        # Expand neighbors
        new_frontier_edges = []
        for edge in adj[state.node]:
            new_g = state.g + edge.fee_bps
            h = heuristic(edge, trade_size)
            new_f = new_g + h
            new_frontier_edges.append((edge.src, edge.dst))
            new_path = state.path + [edge.dst]
            heapq.heappush(frontier, SearchState(new_f, new_g, edge.dst, new_path, state.depth + 1, h))

        steps.append(StepSnapshot(
            expanded_so_far=expanded_so_far[:],
            current_node=state.node,
            frontier_edges=new_frontier_edges,
            best_cycle=best_cycle[:] if best_cycle else None,
            f_value=state.f,
            g_value=state.g,
            h_value=state.h_at_entry,
        ))

    return steps


# ─── Layout ──────────────────────────────────────────────────────────────────

def layout_positions(G: nx.DiGraph) -> Dict[NodeId, Tuple[float, float]]:
    exchanges = list(dict.fromkeys(G.nodes[n]["exchange"] for n in G.nodes()))
    n_ex = len(exchanges)
    ring_r = 4.5
    spread = 0.7
    pos = {}
    for i, ex in enumerate(exchanges):
        angle = 2 * math.pi * i / n_ex - math.pi / 2
        cx = ring_r * math.cos(angle)
        cy = ring_r * math.sin(angle)
        ex_nodes = sorted([n for n in G.nodes() if G.nodes[n]["exchange"] == ex], key=lambda n: n[1])
        for j, node in enumerate(ex_nodes):
            sub_angle = 2 * math.pi * j / max(len(ex_nodes), 1) - math.pi / 2
            pos[node] = (cx + spread * math.cos(sub_angle), cy + spread * math.sin(sub_angle))
    return pos


# ─── Animation ────────────────────────────────────────────────────────────────

def render_frame(
    ax: plt.Axes,
    G: nx.DiGraph,
    pos: Dict[NodeId, Tuple[float, float]],
    step: StepSnapshot,
    step_idx: int,
    total_steps: int,
):
    """
    Render one frame of the A* search using the same visual style as
    scripts/ui.py: exchange-colored nodes, dotted transfers, rate labels.
    """
    ax.clear()
    ax.axis("off")
    ax.set_aspect("equal")
    ax.set_xlim(-7.5, 7.5)
    ax.set_ylim(-7.5, 7.5)

    # Title
    ax.set_title(
        f"A* Search   f(n) = g(n) + h(n)          Step {step_idx + 1} / {total_steps}",
        fontsize=13, fontweight="bold", pad=14, loc="left",
    )

    # State sets
    expanded_set = set(step.expanded_so_far)
    frontier_edge_set = set(step.frontier_edges)
    cycle_set = set(step.best_cycle) if step.best_cycle else set()
    cycle_edge_set: Set[Tuple[NodeId, NodeId]] = set()
    if step.best_cycle and len(step.best_cycle) > 1:
        for i in range(len(step.best_cycle) - 1):
            cycle_edge_set.add((step.best_cycle[i], step.best_cycle[i + 1]))

    # ── Exchange cluster boxes (dashed rectangle, exchange color) ──
    exchanges = list(dict.fromkeys(G.nodes[n]["exchange"] for n in G.nodes()))
    for ex in exchanges:
        ex_nodes = [n for n in G.nodes() if G.nodes[n]["exchange"] == ex]
        xs = [pos[n][0] for n in ex_nodes]
        ys = [pos[n][1] for n in ex_nodes]
        cx, cy = np.mean(xs), np.mean(ys)
        pad_box = 1.35
        w = max(max(xs) - min(xs) + pad_box, 2.2)
        h = max(max(ys) - min(ys) + pad_box, 2.2)
        color = EXCHANGE_COLORS.get(ex, "#808080")

        from matplotlib.patches import Rectangle as Rect
        rect = Rect(
            (cx - w / 2, cy - h / 2), w, h,
            linewidth=2.0, edgecolor=color, facecolor="none",
            linestyle="--", alpha=0.35, zorder=0,
        )
        ax.add_patch(rect)
        # Exchange label above box
        n_coins = len(ex_nodes)
        ax.text(cx, cy + h / 2 + 0.15, f"{ex}",
                ha="center", va="bottom", fontsize=10, fontweight="bold", color=color)
        ax.text(cx, cy + h / 2 + 0.0, f"|V| = {n_coins}",
                ha="center", va="top", fontsize=7, color="#999", style="italic")

    # ── Layer 1: background edges (not yet explored) ──
    for u, v, data in G.edges(data=True):
        kind = data.get("kind", "trade")
        if (u, v) in cycle_edge_set or (u, v) in frontier_edge_set:
            continue
        if u in expanded_set or v in expanded_set:
            continue
        style = "dotted" if kind == "transfer" else "-"
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)],
            edge_color="#CCCCCC", width=0.4, alpha=0.12,
            arrows=True, arrowsize=6, arrowstyle="->",
            style=style, ax=ax, connectionstyle="arc3,rad=0.08",
        )

    # ── Layer 2: explored edges (expanded nodes connected) ──
    for u, v, data in G.edges(data=True):
        kind = data.get("kind", "trade")
        if (u, v) in cycle_edge_set or (u, v) in frontier_edge_set:
            continue
        if not (u in expanded_set and v in expanded_set):
            continue

        u_ex = G.nodes[u]["exchange"]
        if kind == "transfer":
            ec, alpha, lw, style = "#BDBDBD", 0.3, 0.8, "dotted"
        else:
            ec = EXCHANGE_COLORS.get(u_ex, "#808080")
            alpha, lw, style = 0.55, 1.5, "-"

        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)],
            edge_color=ec, width=lw, alpha=alpha,
            arrows=True, arrowsize=10, arrowstyle="->",
            style=style, ax=ax, connectionstyle="arc3,rad=0.08",
        )

    # ── Layer 3: frontier edges (orange, just pushed to queue) ──
    frontier_list = [e for e in step.frontier_edges if e not in cycle_edge_set]
    if frontier_list:
        nx.draw_networkx_edges(
            G, pos, edgelist=frontier_list,
            edge_color="#FF9800", width=2.2, alpha=0.85,
            arrows=True, arrowsize=14, arrowstyle="->",
            ax=ax, connectionstyle="arc3,rad=0.08",
        )
        # Fee labels on frontier edges
        for u, v in frontier_list:
            fee = G.edges[(u, v)].get("fee_bps", 0)
            mx = (pos[u][0] + pos[v][0]) / 2
            my = (pos[u][1] + pos[v][1]) / 2
            ax.text(mx, my, f"{fee:.1f}bp", ha="center", va="center",
                    fontsize=5.5, color="#E65100", fontweight="bold",
                    bbox=dict(boxstyle="round,pad=0.15", facecolor="white",
                              edgecolor="#FF9800", linewidth=0.6, alpha=0.9),
                    zorder=8)

    # ── Layer 4: cycle edges (bold red) ──
    if cycle_edge_set:
        cycle_list = list(cycle_edge_set)
        nx.draw_networkx_edges(
            G, pos, edgelist=cycle_list,
            edge_color="#D32F2F", width=3.5, alpha=1.0,
            arrows=True, arrowsize=18, arrowstyle="->",
            ax=ax, connectionstyle="arc3,rad=0.08",
        )
        # Rate labels on cycle edges
        for u, v in cycle_list:
            rate = G.edges[(u, v)].get("rate", 1.0)
            fee = G.edges[(u, v)].get("fee_bps", 0)
            mx = (pos[u][0] + pos[v][0]) / 2
            my = (pos[u][1] + pos[v][1]) / 2
            ax.text(mx, my, f"{rate:.4f}\n({fee:.1f}bp)",
                    ha="center", va="center", fontsize=6, fontweight="bold",
                    color="#B71C1C",
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="white",
                              edgecolor="#D32F2F", linewidth=1.2),
                    zorder=9)

    # ── Nodes (ui.py style: exchange-colored fill, white edge, label inside) ──
    for node in G.nodes():
        x, y = pos[node]
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        price = G.nodes[node].get("price_usd", 1.0)
        base_color = EXCHANGE_COLORS.get(ex, "#808080")

        if node == step.current_node:
            # Currently being expanded: bright yellow with thick border
            fc, ec, tc, lw, r = "#FFEB3B", "#F57F17", "#333333", 3.5, 0.48
        elif node in cycle_set:
            # Part of a profitable cycle: red highlight
            fc, ec, tc, lw, r = "#FFE0E0", "#D32F2F", "#222222", 3.0, 0.48
        elif node in expanded_set:
            # Already expanded: exchange-colored fill, white border
            fc, ec, tc, lw, r = base_color, "white", "#222222", 1.8, 0.42
        else:
            # Not yet reached: gray
            fc, ec, tc, lw, r = "#E0E0E0", "white", "#999999", 1.0, 0.38

        circle = plt.Circle((x, y), r, facecolor=fc, edgecolor=ec,
                            linewidth=lw, zorder=4)
        ax.add_patch(circle)

        # Label: exchange:coin + price
        label = f"{ex[:3]}:{coin}\n${price:.4f}"
        ax.text(x, y, label, ha="center", va="center",
                fontsize=5.5, fontweight="bold", color=tc, zorder=5,
                linespacing=1.3)

    # ── Info box (dark terminal-style panel) ──
    info_lines = [
        f"EXPANDING  {step.current_node[0]}:{step.current_node[1]}",
        f"",
        f"  g(n) = {step.g_value:6.2f} bps  (actual fees so far)",
        f"  h(n) = {step.h_value:6.2f} bps  (estimated slippage)",
        f"  f(n) = {step.f_value:6.2f} bps  (total priority)",
        f"",
        f"  Expanded: {len(step.expanded_so_far)}/{G.number_of_nodes()} nodes",
    ]
    if step.best_cycle:
        cycle_str = " → ".join(f"{n[0][:3]}:{n[1]}" for n in step.best_cycle)
        info_lines.append(f"")
        info_lines.append(f"  CYCLE FOUND: {cycle_str}")
        total_fee = sum(
            G.edges[(step.best_cycle[i], step.best_cycle[i+1])].get("fee_bps", 0)
            for i in range(len(step.best_cycle) - 1)
            if G.has_edge(step.best_cycle[i], step.best_cycle[i+1])
        )
        info_lines.append(f"  Total cycle cost: {total_fee:.2f} bps")

    info_text = "\n".join(info_lines)
    ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=7.5,
            va="bottom", ha="left", family="monospace",
            bbox=dict(boxstyle="round,pad=0.5", facecolor="#1B2631",
                      edgecolor="#2C3E50", linewidth=1.2, alpha=0.93),
            color="#E8E8E8")

    # ── Legend (matches ui.py style) ──
    import matplotlib.lines as mlines
    legend = [
        mlines.Line2D([], [], marker="o", color="w", markerfacecolor="#FFEB3B",
                       markeredgecolor="#F57F17", markersize=10, label="Currently expanding"),
        mlines.Line2D([], [], marker="o", color="w", markerfacecolor="#F6C344",
                       markeredgecolor="white", markersize=8, label="Already expanded"),
        mlines.Line2D([], [], marker="o", color="w", markerfacecolor="#E0E0E0",
                       markeredgecolor="white", markersize=8, label="Not yet reached"),
        mlines.Line2D([], [], color="#FF9800", linewidth=2.5, label="Frontier (just queued)"),
        mlines.Line2D([], [], color="#888", linewidth=1.5, label="Intra-exchange trade"),
        mlines.Line2D([], [], color="#BDBDBD", linewidth=1, linestyle="dotted",
                       label="Cross-exchange transfer"),
        mlines.Line2D([], [], color="#D32F2F", linewidth=3.5, label="Profitable cycle"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=7, framealpha=0.92,
              edgecolor="#777", fancybox=True)


def main():
    parser = argparse.ArgumentParser(description="Animated A* search visualization")
    parser.add_argument("--fps", type=int, default=2, help="Frames per second (default: 2)")
    parser.add_argument("--trade-size", type=float, default=50_000)
    parser.add_argument("--output", type=str, default="docs/figures/astar_search_animated.gif")
    parser.add_argument("--no-frames", action="store_true",
                        help="Skip saving individual PNG frames")
    args = parser.parse_args()

    G, edges = build_graph()
    start: NodeId = ("Binance", "USDT")
    pos = layout_positions(G)

    print("Running A* with step recording...")
    steps = run_astar_with_steps(G, edges, start, trade_size=args.trade_size)
    print(f"  {len(steps)} expansion steps recorded.")

    # ── Save individual PNG frames for presentations ──
    if not args.no_frames:
        frames_dir = "docs/figures/astar_frames"
        os.makedirs(frames_dir, exist_ok=True)

        # Pick key frames: first, a few mid-steps, first cycle found, last
        key_indices = [0]
        # Add every 5th step
        key_indices += list(range(4, len(steps), 5))
        # Add cycle-found steps
        for i, s in enumerate(steps):
            if s.best_cycle:
                key_indices.append(i)
                break
        key_indices.append(len(steps) - 1)
        key_indices = sorted(set(i for i in key_indices if 0 <= i < len(steps)))

        print(f"  Saving {len(key_indices)} key frames to {frames_dir}/")
        for frame_num, si in enumerate(key_indices):
            fig_f, ax_f = plt.subplots(figsize=(14, 14), facecolor="white")
            fig_f.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.01)
            render_frame(ax_f, G, pos, steps[si], si, len(steps))
            out = os.path.join(frames_dir, f"frame_{frame_num:02d}_step{si+1:02d}.png")
            fig_f.savefig(out, dpi=150, bbox_inches="tight", facecolor="white")
            plt.close(fig_f)
        print(f"  Frames saved.")

    # ── Save animated GIF ──
    fig, ax = plt.subplots(figsize=(14, 14), facecolor="white")
    fig.subplots_adjust(left=0.01, right=0.99, top=0.96, bottom=0.01)

    def animate(frame_idx):
        render_frame(ax, G, pos, steps[frame_idx], frame_idx, len(steps))

    anim = FuncAnimation(fig, animate, frames=len(steps),
                         interval=1000 // args.fps, repeat=True)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    print(f"  Saving {len(steps)}-frame GIF @ {args.fps} fps → {args.output}")
    anim.save(args.output, writer=PillowWriter(fps=args.fps))
    print("Done.")
    plt.close(fig)


if __name__ == "__main__":
    main()
