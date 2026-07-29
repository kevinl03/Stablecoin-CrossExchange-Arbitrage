"""
A* Arbitrage Search — Animated Step-by-Step Expansion
=====================================================
Produces a GIF that shows each node expansion as it happens:
  - Frame N: the Nth node gets popped from the priority queue
  - Frontier edges light up, expanded nodes fill in
  - Final frame highlights the discovered profitable cycle

Usage:
    python scripts/animate_astar_search.py          # saves GIF
    python scripts/animate_astar_search.py --fps 2  # slower
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
            G.add_node((ex, coin), exchange=ex, coin=coin)

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
    """Render a single frame of the search animation."""
    ax.clear()
    ax.set_title(
        f"A* Search: f(n) = g(n) + h(n)    —    Step {step_idx + 1}/{total_steps}",
        fontsize=12, fontweight="bold", pad=10,
    )
    ax.axis("off")
    ax.set_aspect("equal")
    ax.set_xlim(-7, 7)
    ax.set_ylim(-7, 7)

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
            (cx - w/2, cy - h/2), w, h,
            boxstyle="round,pad=0.15",
            linewidth=2.0, edgecolor=color, facecolor=color + "18",
            linestyle="--", zorder=0,
        )
        ax.add_patch(rect)
        ax.text(cx, cy + h/2 + 0.15, ex, ha="center", va="bottom",
                fontsize=9, fontweight="bold", color=color)

    # State sets
    expanded_set = set(step.expanded_so_far)
    frontier_edge_set = set(step.frontier_edges)
    cycle_set = set(step.best_cycle) if step.best_cycle else set()
    cycle_edge_set: Set[Tuple[NodeId, NodeId]] = set()
    if step.best_cycle and len(step.best_cycle) > 1:
        for i in range(len(step.best_cycle) - 1):
            cycle_edge_set.add((step.best_cycle[i], step.best_cycle[i+1]))

    # ── Edges ──
    for u, v, data in G.edges(data=True):
        kind = data.get("kind", "trade")
        if (u, v) in cycle_edge_set:
            color, alpha, lw = "#D32F2F", 1.0, 3.5
        elif (u, v) in frontier_edge_set:
            color, alpha, lw = "#FF9800", 0.9, 2.0  # frontier = orange glow
        elif u in expanded_set and v in expanded_set:
            color = "#2E7D32" if kind == "transfer" else "#555"
            alpha, lw = 0.5, 1.0
        else:
            color, alpha, lw = "#CCCCCC", 0.15, 0.4

        style = "-" if kind == "trade" else (0, (4, 3))
        nx.draw_networkx_edges(
            G, pos, edgelist=[(u, v)],
            edge_color=color, width=lw, alpha=alpha,
            arrows=True, arrowsize=9, arrowstyle="->",
            style=style, ax=ax, connectionstyle="arc3,rad=0.08",
        )

    # ── Nodes ──
    for node in G.nodes():
        x, y = pos[node]
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        base_color = EXCHANGE_COLORS.get(ex, "#808080")

        if node == step.current_node:
            # Currently being expanded — big highlight
            fc, ec, tc, lw = "#FFEB3B", "#F57F17", "#333", 3.0
        elif node in cycle_set:
            fc, ec, tc, lw = "#D32F2F", "#B71C1C", "white", 2.5
        elif node in expanded_set:
            fc, ec, tc, lw = "white", base_color, "#222", 2.2
        else:
            fc, ec, tc, lw = "#F5F5F5", "#CCCCCC", "#AAA", 1.2

        circle = plt.Circle((x, y), 0.38, facecolor=fc, edgecolor=ec,
                            linewidth=lw, zorder=4)
        ax.add_patch(circle)
        ax.text(x, y, coin, ha="center", va="center",
                fontsize=7.5, fontweight="bold", color=tc, zorder=5)

    # ── Info box (current step details) ──
    info_lines = [
        f"Expanding: {step.current_node[0]} / {step.current_node[1]}",
        f"g(n) = {step.g_value:.2f} bps   h(n) = {step.h_value:.2f} bps",
        f"f(n) = {step.f_value:.2f} bps",
        f"Nodes expanded: {len(step.expanded_so_far)}/{G.number_of_nodes()}",
    ]
    if step.best_cycle:
        cycle_str = " → ".join(f"{n[0][:3]}:{n[1]}" for n in step.best_cycle)
        info_lines.append(f"Cycle found: {cycle_str}")

    info_text = "\n".join(info_lines)
    ax.text(0.02, 0.02, info_text, transform=ax.transAxes, fontsize=8,
            va="bottom", ha="left", family="monospace",
            bbox=dict(boxstyle="round,pad=0.4", facecolor="#263238",
                      edgecolor="#455A64", linewidth=1, alpha=0.92),
            color="#E0E0E0")

    # ── Legend ──
    legend = [
        mpatches.Patch(facecolor="#FFEB3B", edgecolor="#F57F17", linewidth=2, label="Currently expanding"),
        mpatches.Patch(facecolor="white", edgecolor="#888", linewidth=1.5, label="Already expanded"),
        mpatches.Patch(facecolor="#F5F5F5", edgecolor="#CCC", linewidth=1, label="Not yet reached"),
        mpatches.Patch(facecolor="#FF9800", edgecolor="#E65100", linewidth=1.5, label="Frontier edges"),
        mpatches.Patch(facecolor="#D32F2F", edgecolor="#B71C1C", linewidth=2, label="Best cycle"),
    ]
    ax.legend(handles=legend, loc="upper right", fontsize=7, framealpha=0.92,
              edgecolor="#555")


def main():
    parser = argparse.ArgumentParser(description="Animated A* search visualization")
    parser.add_argument("--fps", type=int, default=1, help="Frames per second (default: 1)")
    parser.add_argument("--trade-size", type=float, default=50_000)
    parser.add_argument("--output", type=str, default="docs/figures/astar_search_animated.gif")
    args = parser.parse_args()

    G, edges = build_graph()
    start: NodeId = ("Binance", "USDT")
    pos = layout_positions(G)

    print("Running A* with step recording...")
    steps = run_astar_with_steps(G, edges, start, trade_size=args.trade_size)
    print(f"  {len(steps)} expansion steps recorded.")

    # Create animation
    fig, ax = plt.subplots(figsize=(10, 10), facecolor="white")
    fig.subplots_adjust(left=0.02, right=0.98, top=0.95, bottom=0.02)

    def animate(frame_idx):
        render_frame(ax, G, pos, steps[frame_idx], frame_idx, len(steps))

    anim = FuncAnimation(fig, animate, frames=len(steps), interval=1000 // args.fps, repeat=True)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    print(f"Saving {len(steps)}-frame GIF @ {args.fps} fps → {args.output}")
    anim.save(args.output, writer=PillowWriter(fps=args.fps))
    print("Done.")
    plt.close(fig)


if __name__ == "__main__":
    main()
