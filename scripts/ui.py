# ==============================================================
# ui.py — Simple Streamlit UI for Stablecoin Arbitrage
# ==============================================================

from __future__ import annotations

import sys
import logging
import io
from pathlib import Path
from typing import Optional, Dict, List, Any, Tuple
from collections import defaultdict

# Add project root (folder that CONTAINS "scripts") to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import json
import streamlit as st           # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import networkx as nx            # type: ignore
import pandas as pd              # type: ignore

from scripts.graph import build_graph, _fetch_actual_trading_pair_rate

# ── DEV FLAG ─────────────────────────────────────────────────────
# TODO: set back to False before pushing / merging to integration
# When True the UI loads a cached JSON snapshot instead of hitting
# live exchange APIs, making reloads instant during development.
USE_CACHED_DATA = True
_SNAPSHOT_PATH = Path(__file__).with_name("graph_snapshot.json")
from scripts.data import EXCHANGES
from scripts.astar_vol import astar_best_path_with_liquidity, PlanResult, NodeId

# Type alias for adjacency list
Adjacency = Dict[NodeId, List[Dict[str, Any]]]
from scripts.weighted_astar import weighted_astar_best_path
from scripts.h1_vol import (
    volume_heuristic_cost,
    UNKNOWN_LIQUIDITY_PENALTY,
)
from scripts.h2_slippage import (
    slippage_heuristic_cost,
    UNKNOWN_SLIPPAGE_PENALTY,
)
from scripts.h4_chaincongestion_exchange_risk import (
    chain_congestion_heuristic_cost,
    exchange_risk_heuristic_cost,
    chain_exchange_risk_heuristic_cost,
    UNKNOWN_CHAIN_PENALTY,
    UNKNOWN_EXCHANGE_PENALTY,
)

# Import all fees as a module so we don't depend on exact dict names
import scripts.fees as fees

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s"
)

# Light, pastel exchange colours.  Adjacent entries within each tier are
# chosen to contrast on the hue wheel so neighbours look distinct.
EXCHANGE_COLORS = {
    "binance":   "#F6C344",   # warm yellow
    "gateio":    "#7BA4F4",   # periwinkle blue
    "kucoin":    "#5EC6A4",   # mint green
    "bybit":     "#F2917C",   # salmon / coral
    "okx":       "#A98ED6",   # soft lavender
    "mexc":      "#7DD4E8",   # sky blue
    "kraken":    "#C792D6",   # orchid purple
    "bitget":    "#88D68A",   # spring green
    "htx":       "#E8A76C",   # warm peach
    "coinbase":  "#6BABF2",   # cornflower blue
    "cryptocom": "#D6A0C4",   # dusty rose
    "phemex":    "#C8E26C",   # lime / chartreuse
}

# Tier-1 (inner ring) vs tier-2 (outer ring).  Within each list the
# ordering alternates warm/cool so ring-neighbours contrast.
MAJOR_EXCHANGES = ["binance", "coinbase", "kraken", "bybit", "okx", "kucoin"]
MINOR_EXCHANGES = ["gateio", "bitget", "mexc", "htx", "cryptocom", "phemex"]


# --------------------------------------------------------------
# Small helper: build a NetworkX graph and matplotlib figure
# --------------------------------------------------------------

def _parse_node_key(s: str) -> NodeId:
    ex, coin = s.split("|", 1)
    return (ex, coin)


def _load_snapshot() -> Tuple[Dict[NodeId, Dict[str, Any]], Dict[NodeId, list]]:
    """Load the offline JSON snapshot produced by dump_graph_snapshot.py."""
    raw = json.loads(_SNAPSHOT_PATH.read_text())
    nodes = {_parse_node_key(k): v for k, v in raw["nodes"].items()}
    adj: Dict[NodeId, list] = {}
    for k, edges in raw["adj"].items():
        parsed_edges = []
        for e in edges:
            for field in ("from", "to"):
                if isinstance(e.get(field), str) and "|" in e[field]:
                    e[field] = _parse_node_key(e[field])
            parsed_edges.append(e)
        adj[_parse_node_key(k)] = parsed_edges
    return nodes, adj


def build_nx_graph(show_all: bool = False):
    """
    Use build_graph() and convert to a NetworkX DiGraph.
    
    Args:
        show_all: If True, build an unfiltered graph with all possible nodes/edges

    Returns:
        (G, error_msg) where error_msg is None on success or a string describing the failure.
    """
    try:
        if USE_CACHED_DATA and _SNAPSHOT_PATH.exists():
            nodes, adj = _load_snapshot()
        elif show_all:
            nodes, adj = build_graph_unfiltered()
        else:
            nodes, adj = build_graph()
    except Exception as exc:
        return nx.DiGraph(), f"Failed to fetch exchange data: {exc}"

    if not nodes:
        return nx.DiGraph(), (
            "No exchange data could be retrieved. "
            "This usually means your network is blocking cryptocurrency exchange APIs "
            "(common on public wifi, campus, and corporate networks). "
            "Try switching to a mobile hotspot or home network."
        )

    G = nx.DiGraph()

    for node_id, meta in nodes.items():
        ex, coin = node_id
        G.add_node(
            node_id,
            exchange=ex,
            coin=coin,
            price_usd=meta["price_usd"],
            snapshot_ts=meta["snapshot_ts"],
        )

    for from_node, edges in adj.items():
        for e in edges:
            kind = e.get("kind", "trade")
            color = "tab:blue" if kind == "trade" else "tab:green"

            G.add_edge(
                e["from"],
                e["to"],
                kind=kind,
                rate=e["rate"],
                cost=e["cost"],
                color=color,
                taker_fee=e.get("taker_fee"),
                withdraw_fee=e.get("withdrawal_fee_units"),
                chain=e.get("chain"),
                transfer_time_sec=e.get("transfer_time_sec", 0.0),
                raw_edge=e,
            )

    return G, None


def build_graph_unfiltered():
    """
    Build a graph with ALL possible nodes and edges, bypassing filters.
    This includes nodes with prices outside tolerance, edges without actual trading pairs, etc.
    """
    from scripts.data import EXCHANGES, STABLE_COINS, COIN_MARKETS, normalize_price_to_usd
    from scripts.fees import WITHDRAWAL_FEES, get_taker_fee, get_network_gas_fee
    from scripts.transfer_time import get_chain_time_seconds
    import math
    import time
    from collections import defaultdict
    
    # Fetch prices without tolerance filter
    prices: Dict[NodeId, float] = {}
    snapshot_ts = time.time()
    
    for coin in STABLE_COINS:
        for ex_name, ex in EXCHANGES.items():
            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue
            
            try:
                ticker = ex.fetch_ticker(market)
            except Exception:
                continue
            
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            last = ticker.get("last")
            
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                conservative_price = bid
            elif isinstance(last, (int, float)):
                conservative_price = float(last)
            else:
                continue
            
            price_usd = normalize_price_to_usd(coin, market, conservative_price)
            if price_usd is None:
                continue
            
            # NO TOLERANCE FILTER - include all prices
            prices[(ex_name, coin)] = price_usd
    
    # Build nodes
    nodes: Dict[NodeId, Dict[str, Any]] = {
        (ex, coin): {
            "exchange": ex,
            "coin": coin,
            "price_usd": price_usd,
            "snapshot_ts": snapshot_ts,
        }
        for (ex, coin), price_usd in prices.items()
    }
    
    # Build ALL trade edges (even without actual trading pairs)
    adj: Adjacency = defaultdict(list)
    
    for ex_name in EXCHANGES.keys():
        coins_here = [c for c in STABLE_COINS if (ex_name, c) in prices]
        if len(coins_here) < 2:
            continue
        
        taker_fee = get_taker_fee(ex_name) or 0.0
        
        for i in range(len(coins_here)):
            for j in range(len(coins_here)):
                if i == j:
                    continue
                
                c_from = coins_here[i]
                c_to = coins_here[j]
                
                # Try actual trading pair first
                actual_rate = _fetch_actual_trading_pair_rate(ex_name, c_from, c_to)
                
                if actual_rate is not None:
                    raw_rate = actual_rate
                else:
                    # Use normalized price fallback (what was removed before)
                    price_from = prices[(ex_name, c_from)]
                    price_to = prices[(ex_name, c_to)]
                    raw_rate = price_from / price_to
                
                effective_rate = raw_rate * (1.0 - taker_fee)
                if effective_rate <= 0:
                    continue
                
                cost = -math.log(effective_rate)
                
                from_node: NodeId = (ex_name, c_from)
                to_node: NodeId = (ex_name, c_to)
                
                adj[from_node].append({
                    "from": from_node,
                    "to": to_node,
                    "kind": "trade",
                    "exchange": ex_name,
                    "coin_from": c_from,
                    "coin_to": c_to,
                    "rate": effective_rate,
                    "cost": cost,
                    "taker_fee": taker_fee,
                    "withdrawal_fee_units": None,
                    "chain": None,
                    "transfer_time_sec": 0.0,
                })
    
    # Build ALL transfer edges (bypass portfolio size checks)
    coin_exchanges: Dict[str, List[str]] = {
        coin: [ex for (ex, c) in prices.keys() if c == coin]
        for coin in STABLE_COINS
    }
    
    for coin in STABLE_COINS:
        ex_list = coin_exchanges.get(coin, [])
        if len(ex_list) < 2:
            continue
        
        for ex_from in ex_list:
            ex_withdraw_cfg = WITHDRAWAL_FEES.get(ex_from, {}).get(coin)
            if not ex_withdraw_cfg:
                continue
            
            price_from_usd = prices[(ex_from, coin)]
            
            for ex_to in ex_list:
                if ex_to == ex_from:
                    continue
                
                chains_from = ex_withdraw_cfg
                chains_to = WITHDRAWAL_FEES.get(ex_to, {}).get(coin, {})
                
                if chains_to:
                    common_chains = set(chains_from.keys()) & set(chains_to.keys())
                else:
                    common_chains = set(chains_from.keys())
                
                if not common_chains:
                    continue
                
                for chain in common_chains:
                    fee_units = chains_from[chain]
                    gas_fee_usd = get_network_gas_fee(chain)
                    
                    # NO PORTFOLIO SIZE CHECK - include all edges
                    withdrawal_fee_usd = fee_units * price_from_usd
                    total_fee_usd = withdrawal_fee_usd + gas_fee_usd
                    
                    # Use a reference portfolio size for rate calculation
                    ref_portfolio = 10000.0
                    if total_fee_usd >= ref_portfolio:
                        continue
                    
                    rate = 1.0 - (total_fee_usd / ref_portfolio)
                    if rate <= 0:
                        continue
                    
                    cost = -math.log(rate)
                    t_sec = get_chain_time_seconds(chain) or 0.0
                    
                    from_node: NodeId = (ex_from, coin)
                    to_node: NodeId = (ex_to, coin)
                    
                    adj[from_node].append({
                        "from": from_node,
                        "to": to_node,
                        "kind": "transfer",
                        "exchange": ex_from,
                        "target_exchange": ex_to,
                        "coin": coin,
                        "rate": rate,
                        "cost": cost,
                        "taker_fee": None,
                        "withdrawal_fee_units": fee_units,
                        "gas_fee_usd": gas_fee_usd,
                        "total_fee_usd": total_fee_usd,
                        "chain": chain,
                        "transfer_time_sec": t_sec,
                    })
    
    return nodes, adj


def make_paper_ready_figure(
    G: nx.DiGraph,
    highlight_cycle: Optional[List[NodeId]] = None,
    show_cycle_label: bool = True,
) -> plt.Figure:
    """
    Create a conference-ready figure with structured block layout.
    
    Design principles:
    - Structured 2x2 grid layout for exchanges
    - White background, clean styling
    - Nodes: white fill, colored borders, asset names only
    - Intra-exchange edges: thin, low opacity, exchange color
    - Inter-exchange edges: thick, dark green, full opacity
    - Optional highlighted arbitrage cycle in red
    
    Args:
        G: NetworkX directed graph
        highlight_cycle: Optional list of nodes forming a cycle to highlight
        show_cycle_label: If True, add "Cycle P" label to highlighted cycle
    """
    import math
    from matplotlib.patches import Rectangle, FancyBboxPatch
    from matplotlib.patches import FancyArrowPatch
    import matplotlib.patches as mpatches
    
    exchange_colors = EXCHANGE_COLORS
    
    # Group nodes by exchange (use EXCHANGE_COLORS order for ring spacing)
    exchange_names = list(EXCHANGE_COLORS.keys())
    node_groups = {ex: [] for ex in exchange_names}
    
    for node in G.nodes():
        ex = G.nodes[node]["exchange"]
        node_groups[ex].append(node)
    
    # Filter to only exchanges that have nodes
    active_exchanges = [ex for ex in exchange_names if node_groups[ex]]
    if not active_exchanges:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No nodes to display", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return fig
    
    # Create figure with white background
    fig, ax = plt.subplots(figsize=(10, 10), facecolor="white")
    ax.set_facecolor("white")
    
    # Structured 2x2 grid layout
    # Calculate grid dimensions (try to make it as square as possible)
    num_exchanges = len(active_exchanges)
    if num_exchanges <= 2:
        cols = num_exchanges
        rows = 1
    elif num_exchanges <= 4:
        cols = 2
        rows = 2
    else:
        cols = 3
        rows = (num_exchanges + 2) // 3
    
    # Block dimensions
    block_width = 3.0
    block_height = 3.0
    block_spacing = 4.0
    
    # Calculate positions for each exchange block
    exchange_positions = {}
    exchange_blocks = {}  # Store block boundaries for drawing
    
    for idx, ex in enumerate(active_exchanges):
        row = idx // cols
        col = idx % cols
        
        # Center the grid
        total_width = cols * block_width + (cols - 1) * block_spacing
        total_height = rows * block_height + (rows - 1) * block_spacing
        start_x = -total_width / 2
        start_y = total_height / 2
        
        block_center_x = start_x + col * (block_width + block_spacing) + block_width / 2
        block_center_y = start_y - row * (block_height + block_spacing) - block_height / 2
        
        exchange_positions[ex] = (block_center_x, block_center_y)
        exchange_blocks[ex] = {
            "center": (block_center_x, block_center_y),
            "width": block_width,
            "height": block_height,
        }
    
    # Position nodes within each block
    pos = {}
    node_size = 300
    
    for ex in active_exchanges:
        nodes_in_exchange = sorted(node_groups[ex], key=lambda n: G.nodes[n]["coin"])
        num_nodes = len(nodes_in_exchange)
        block_center_x, block_center_y = exchange_positions[ex]
        
        # Arrange nodes in a grid or circle within the block
        if num_nodes == 1:
            pos[nodes_in_exchange[0]] = (block_center_x, block_center_y)
        elif num_nodes <= 4:
            # 2x2 grid
            grid_size = 2
            node_spacing = 0.8
            for i, node in enumerate(nodes_in_exchange):
                row = i // grid_size
                col = i % grid_size
                x = block_center_x - node_spacing / 2 + col * node_spacing
                y = block_center_y + node_spacing / 2 - row * node_spacing
                pos[node] = (x, y)
        else:
            # Circular arrangement
            radius = min(block_width, block_height) * 0.35
            for i, node in enumerate(nodes_in_exchange):
                angle = 2 * math.pi * i / num_nodes
                x = block_center_x + radius * math.cos(angle)
                y = block_center_y + radius * math.sin(angle)
                pos[node] = (x, y)
    
    # Draw exchange block boundaries (subtle)
    for ex, block_info in exchange_blocks.items():
        center_x, center_y = block_info["center"]
        width = block_info["width"]
        height = block_info["height"]
        color = exchange_colors.get(ex, "#808080")
        
        # Draw subtle rectangle border
        rect = Rectangle(
            (center_x - width/2, center_y - height/2),
            width,
            height,
            linewidth=2,
            edgecolor=color,
            facecolor="none",
            alpha=0.3,
            linestyle="--",
        )
        ax.add_patch(rect)
        
        # Add exchange name label above block
        ax.text(
            center_x,
            center_y + height/2 + 0.3,
            ex.capitalize(),
            ha="center",
            va="bottom",
            fontsize=12,
            fontweight="bold",
            color=color,
        )
        
        # Add node count (optional, subtle)
        num_nodes = len(node_groups[ex])
        ax.text(
            center_x,
            center_y + height/2 + 0.1,
            f"|V| = {num_nodes}",
            ha="center",
            va="bottom",
            fontsize=9,
            color="gray",
            style="italic",
        )
    
    # Separate edges into intra-exchange and inter-exchange
    intra_edges = []
    inter_edges = []
    highlight_edges = set()
    
    if highlight_cycle and len(highlight_cycle) > 1:
        # Create set of edges in the cycle
        cycle_edges = set()
        for i in range(len(highlight_cycle)):
            u = highlight_cycle[i]
            v = highlight_cycle[(i + 1) % len(highlight_cycle)]
            cycle_edges.add((u, v))
        highlight_edges = cycle_edges
    
    for u, v in G.edges():
        u_ex = G.nodes[u]["exchange"]
        v_ex = G.nodes[v]["exchange"]
        edge_kind = G.edges[(u, v)].get("kind", "trade")
        
        if (u, v) in highlight_edges:
            # Will be drawn separately
            continue
        elif u_ex == v_ex:
            intra_edges.append((u, v))
        else:
            inter_edges.append((u, v))
    
    # Draw intra-exchange edges (thin, low opacity, exchange color)
    for u, v in intra_edges:
        u_ex = G.nodes[u]["exchange"]
        edge_color = exchange_colors.get(u_ex, "#808080")
        
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=[(u, v)],
            edge_color=edge_color,
            width=0.5,
            alpha=0.3,
            arrows=True,
            arrowsize=8,
            arrowstyle="->",
            ax=ax,
        )
    
    # Draw inter-exchange edges (thick, dark green, full opacity)
    if inter_edges:
        nx.draw_networkx_edges(
            G,
            pos,
            edgelist=inter_edges,
            edge_color="#2E7D32",  # Dark green
            width=2.0,
            alpha=1.0,
            arrows=True,
            arrowsize=12,
            arrowstyle="->",
            ax=ax,
        )
    
    # Draw highlighted cycle edges (bold red)
    if highlight_cycle and len(highlight_cycle) > 1:
        cycle_edge_list = []
        for i in range(len(highlight_cycle)):
            u = highlight_cycle[i]
            v = highlight_cycle[(i + 1) % len(highlight_cycle)]
            if G.has_edge(u, v):
                cycle_edge_list.append((u, v))
        
        if cycle_edge_list:
            nx.draw_networkx_edges(
                G,
                pos,
                edgelist=cycle_edge_list,
                edge_color="#D32F2F",  # Bright red
                width=3.5,
                alpha=1.0,
                arrows=True,
                arrowsize=15,
                arrowstyle="->",
                ax=ax,
            )
            
            # Add "Cycle P" label if requested
            if show_cycle_label and cycle_edge_list:
                # Find midpoint of first edge for label
                u, v = cycle_edge_list[0]
                x1, y1 = pos[u]
                x2, y2 = pos[v]
                label_x = (x1 + x2) / 2
                label_y = (y1 + y2) / 2 + 0.3
                ax.text(
                    label_x,
                    label_y,
                    "Cycle P",
                    ha="center",
                    va="bottom",
                    fontsize=10,
                    fontweight="bold",
                    color="#D32F2F",
                    bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#D32F2F", linewidth=1.5),
                )
    
    # Draw nodes (white fill, colored border, asset name only)
    for ex in active_exchanges:
        nodes_in_exchange = node_groups[ex]
        node_color = exchange_colors.get(ex, "#808080")
        
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=nodes_in_exchange,
            node_size=node_size,
            node_color="white",
            edgecolors=node_color,
            linewidths=2.5,
            ax=ax,
        )
        
        # Add labels (asset names only, no prices)
        labels = {node: G.nodes[node]["coin"] for node in nodes_in_exchange}
        nx.draw_networkx_labels(
            G,
            pos,
            labels=labels,
            font_size=9,
            font_weight="bold",
            ax=ax,
        )
    
    # Set axis limits with padding
    all_x = [p[0] for p in pos.values()]
    all_y = [p[1] for p in pos.values()]
    x_margin = 1.0
    y_margin = 1.0
    ax.set_xlim(min(all_x) - x_margin, max(all_x) + x_margin)
    ax.set_ylim(min(all_y) - y_margin, max(all_y) + y_margin)
    
    ax.axis("off")
    ax.set_aspect("equal")
    fig.tight_layout()
    
    return fig


def make_path_only_figure(
    G: nx.DiGraph,
    highlight_path: List[NodeId],
    highlight_edges: Optional[List[Dict[str, Any]]] = None,
) -> plt.Figure:
    """
    Create a simplified graph showing ONLY the successful path.
    Removes all other nodes and edges for clarity.
    """
    import math
    
    if not highlight_path or len(highlight_path) < 2:
        fig, ax = plt.subplots(figsize=(8, 6))
        ax.text(0.5, 0.5, "No path to display", ha="center", va="center", transform=ax.transAxes)
        ax.axis("off")
        return fig
    
    # Create subgraph with only path nodes
    path_nodes = set(highlight_path)
    path_edges = []
    
    # Build edge list from path
    for i in range(len(highlight_path) - 1):
        u, v = highlight_path[i], highlight_path[i + 1]
        if G.has_edge(u, v):
            path_edges.append((u, v))
    
    # Create subgraph
    subgraph = G.subgraph(path_nodes).copy()
    
    exchange_colors = EXCHANGE_COLORS
    
    # Create layout - use a curved 2D path for better visualization
    pos = {}
    is_cycle = len(highlight_path) > 2 and highlight_path[0] == highlight_path[-1]
    num_nodes = len(highlight_path) - 1 if is_cycle else len(highlight_path)
    
    if num_nodes <= 2:
        # Simple two-node layout with some vertical offset
        pos[highlight_path[0]] = (0, 0)
        if len(highlight_path) > 1:
            pos[highlight_path[1]] = (3, 0.5)
    elif is_cycle:
        # Circular layout for cycles
        radius = 3.0
        for i, node in enumerate(highlight_path[:-1]):  # Exclude duplicate last node
            angle = 2 * math.pi * i / (len(highlight_path) - 1) - math.pi / 2  # Start at top
            pos[node] = (radius * math.cos(angle), radius * math.sin(angle))
    else:
            # Curved path layout (S-curve or arc) for better 2D visualization
            # Use a smooth curve that goes up and down
            for i, node in enumerate(highlight_path):
                x = i * 3.0
                # Create a wave/curve pattern
                y = 1.5 * math.sin(i * math.pi / (num_nodes - 1) if num_nodes > 1 else 0)
                pos[node] = (x, y)
    
    # Adjust figure size based on path length
    if num_nodes <= 3:
        fig, ax = plt.subplots(figsize=(10, 6))
    elif num_nodes <= 5:
        fig, ax = plt.subplots(figsize=(14, 8))
    else:
        fig, ax = plt.subplots(figsize=(16, 10))
    
    # Draw nodes
    node_colors = []
    node_labels = {}
    for node in highlight_path:
        ex = subgraph.nodes[node]["exchange"]
        coin = subgraph.nodes[node]["coin"]
        price = subgraph.nodes[node]["price_usd"]
        
        node_colors.append(exchange_colors.get(ex, "#808080"))
        node_labels[node] = f"{ex}:{coin}\n${price:.4f}"
    
    nx.draw_networkx_nodes(
        subgraph,
        pos,
        node_size=1500,
        node_color=node_colors,
        edgecolors="black",
        linewidths=3.0,
        ax=ax,
    )
    
    # Draw edges (all are part of the path, so make them bold)
    nx.draw_networkx_edges(
        subgraph,
        pos,
        edgelist=path_edges,
        edge_color="#D32F2F",  # Bold red
        arrows=True,
        arrowsize=25,
        width=4.0,
        alpha=1.0,
        arrowstyle="->",
        ax=ax,
    )
    
    # Add edge labels with rates/prices
    if highlight_edges and len(highlight_edges) == len(path_edges):
        edge_labels = {}
        for i, (u, v) in enumerate(path_edges):
            if i < len(highlight_edges):
                edge_data = highlight_edges[i]
                rate = edge_data.get("rate", 0.0)
                kind = edge_data.get("kind", "trade")
                
                if kind == "trade":
                    label = f"{rate:.4f}"
                else:
                    total_fee = edge_data.get("total_fee_usd", 0.0)
                    label = f"${total_fee:.2f}" if total_fee > 0 else f"{rate:.4f}"
                
                edge_labels[(u, v)] = label
        
        if edge_labels:
            nx.draw_networkx_edge_labels(
                subgraph,
                pos,
                edge_labels=edge_labels,
                font_size=10,
                font_weight="bold",
                bbox=dict(boxstyle="round,pad=0.5", facecolor="white", edgecolor="#D32F2F", linewidth=2),
                ax=ax,
            )
    
    # Draw node labels
    nx.draw_networkx_labels(
        subgraph,
        pos,
        labels=node_labels,
        font_size=10,
        font_weight="bold",
        ax=ax,
    )
    
    # Add step numbers with better positioning
    for i, node in enumerate(highlight_path):
        if node in pos:
            x, y = pos[node]
            # Position step number below node, adjusting for layout
            offset_y = -0.8 if not is_cycle else -0.6
            ax.text(x, y + offset_y, f"Step {i+1}", ha="center", va="top", 
                   fontsize=9, style="italic", color="gray", fontweight="bold")
    
    ax.set_title("Arbitrage Path (Simplified View)\nShowing only the successful path", 
                 fontsize=14, fontweight="bold")
    ax.axis("off")
    ax.set_aspect("equal")
    fig.tight_layout()
    
    return fig


def make_graph_figure(
    G: nx.DiGraph,
    highlight_path: Optional[List[NodeId]] = None,
    highlight_edges: Optional[List[Dict[str, Any]]] = None,
):
    """
    Create a matplotlib Figure with exchange clusters and proper edge coloring.
    
    Args:
        G: NetworkX directed graph
        highlight_path: Optional list of nodes in the path to highlight
        highlight_edges: Optional list of edge dicts from the path to highlight
    """
    import math
    
    exchange_colors = EXCHANGE_COLORS
    
    exchange_names = list(EXCHANGE_COLORS.keys())
    node_colors = []
    node_labels = {}
    node_groups = {ex: [] for ex in exchange_names}
    
    # Create set of highlighted nodes for faster lookup
    highlight_nodes_set = set(highlight_path) if highlight_path else set()
    
    # Create set of highlighted edges (u, v) tuples
    highlight_edges_set = set()
    if highlight_path and len(highlight_path) > 1:
        for i in range(len(highlight_path) - 1):
            u, v = highlight_path[i], highlight_path[i + 1]
            # Only add edge if both nodes exist in graph and edge exists
            if u in G.nodes() and v in G.nodes() and G.has_edge(u, v):
                highlight_edges_set.add((u, v))
        # If it's a cycle, also add the closing edge
        if len(highlight_path) > 2 and highlight_path[0] == highlight_path[-1]:
            u, v = highlight_path[-1], highlight_path[0]
            if u in G.nodes() and v in G.nodes() and G.has_edge(u, v):
                highlight_edges_set.add((u, v))

    # Group nodes by exchange
    for node in G.nodes():
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        price = G.nodes[node]["price_usd"]
        
        node_labels[node] = f"{ex}:{coin}\n${price:.4f}"
        
        if node in highlight_nodes_set:
            node_colors.append("#FF6B6B")
        else:
            node_colors.append(exchange_colors.get(ex, "#808080"))
        
        node_groups[ex].append(node)

    intra_edges = []
    transfer_edges = []
    highlighted_edges = []
    edge_color_map = {}
    edge_width_map = {}
    
    for u, v in G.edges():
        u_ex = G.nodes[u]["exchange"]
        v_ex = G.nodes[v]["exchange"]
        edge_kind = G.edges[(u, v)].get("kind", "trade")
        
        if (u, v) in highlight_edges_set:
            highlighted_edges.append((u, v))
            edge_color_map[(u, v)] = "#D32F2F"
            edge_width_map[(u, v)] = 4.0
        elif u_ex != v_ex or edge_kind == "transfer":
            transfer_edges.append((u, v))
            edge_color_map[(u, v)] = "#BDBDBD"
            edge_width_map[(u, v)] = 0.8
        else:
            intra_edges.append((u, v))
            edge_color_map[(u, v)] = exchange_colors.get(u_ex, "#808080")
            edge_width_map[(u, v)] = 2.0

    pos = {}
    active_exchanges = [ex for ex in exchange_names if node_groups[ex]]
    num_exchanges = len(active_exchanges)

    if num_exchanges == 0:
        pos = nx.spring_layout(G, seed=42, k=2.0)
    else:
        min_node_gap = 1.4

        cluster_radii = {}
        for ex in active_exchanges:
            n = len(node_groups[ex])
            if n <= 1:
                cluster_radii[ex] = 0.0
            else:
                cluster_radii[ex] = min_node_gap / (2 * math.sin(math.pi / n))

        inner_tier = [ex for ex in MAJOR_EXCHANGES if ex in active_exchanges]
        outer_tier = [ex for ex in MINOR_EXCHANGES if ex in active_exchanges]
        leftover = [ex for ex in active_exchanges
                     if ex not in inner_tier and ex not in outer_tier]
        outer_tier.extend(leftover)

        if not inner_tier:
            inner_tier, outer_tier = outer_tier, []

        max_cr = max(cluster_radii.values()) if cluster_radii else 0.0
        pad = 0.5

        n_inner = len(inner_tier)
        if n_inner >= 2:
            ring_inner = (max_cr + pad) / math.sin(math.pi / n_inner)
        elif n_inner == 1:
            ring_inner = 0.0
        else:
            ring_inner = 0.0

        n_outer = len(outer_tier)
        ring_outer = ring_inner + 2 * max_cr + 2.2 if n_outer else 0.0

        def _place_ring(tier, ring_r, angle_offset=0.0):
            n = len(tier)
            for i, ex in enumerate(tier):
                angle = 2 * math.pi * i / n + angle_offset
                cx = ring_r * math.cos(angle)
                cy = ring_r * math.sin(angle)
                r = cluster_radii[ex]
                nodes_sorted = sorted(
                    node_groups[ex],
                    key=lambda nd: (G.nodes[nd]["coin"], G.nodes[nd]["price_usd"]),
                )
                for ni, node in enumerate(nodes_sorted):
                    if len(nodes_sorted) == 1:
                        pos[node] = (cx, cy)
                    else:
                        a = 2 * math.pi * ni / len(nodes_sorted)
                        pos[node] = (cx + r * math.cos(a), cy + r * math.sin(a))

        _place_ring(inner_tier, ring_inner)
        offset = math.pi / n_inner if n_inner else 0.0
        _place_ring(outer_tier, ring_outer, angle_offset=offset)

    fig, ax = plt.subplots(figsize=(18, 14))
    
    # Layer 1: inter-exchange transfers — light gray, thin, dotted, faint
    if transfer_edges:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=transfer_edges,
            edge_color=[edge_color_map[(u, v)] for u, v in transfer_edges],
            arrows=True, arrowsize=8,
            width=[edge_width_map[(u, v)] for u, v in transfer_edges],
            alpha=0.25,
            style="dotted",
            arrowstyle="->",
            ax=ax,
        )

    # Layer 2: intra-exchange trades — solid, exchange-coloured
    if intra_edges:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=intra_edges,
            edge_color=[edge_color_map[(u, v)] for u, v in intra_edges],
            arrows=True, arrowsize=16,
            width=[edge_width_map[(u, v)] for u, v in intra_edges],
            alpha=0.7,
            arrowstyle="->",
            ax=ax,
        )

    # Layer 3: highlighted path — bold red, on top
    if highlighted_edges:
        nx.draw_networkx_edges(
            G, pos,
            edgelist=highlighted_edges,
            edge_color=[edge_color_map[(u, v)] for u, v in highlighted_edges],
            arrows=True, arrowsize=22,
            width=[edge_width_map[(u, v)] for u, v in highlighted_edges],
            alpha=1.0,
            arrowstyle="->",
            ax=ax,
        )
    
    # Draw nodes with exchange brand colors (highlighted nodes get special treatment)
    regular_nodes = [n for n in G.nodes() if n not in highlight_nodes_set]
    highlighted_nodes = [n for n in G.nodes() if n in highlight_nodes_set]
    
    if regular_nodes:
        regular_node_colors = [node_colors[list(G.nodes()).index(n)] for n in regular_nodes]
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=regular_nodes,
            node_size=2800,
            node_color=regular_node_colors,
            edgecolors="white",
            linewidths=1.5,
            ax=ax,
        )
    
    if highlighted_nodes:
        nx.draw_networkx_nodes(
            G,
            pos,
            nodelist=highlighted_nodes,
            node_size=3400,
            node_color="#FFE0E0",
            edgecolors="#D32F2F",
            linewidths=3.0,
            ax=ax,
        )
    
    nx.draw_networkx_labels(
        G,
        pos,
        labels=node_labels,
        font_size=6.5,
        font_weight="bold",
        font_color="#222222",
        ax=ax,
    )
    
    # Add edge labels for highlighted path (showing rates/prices)
    if highlighted_edges and highlight_edges:
        edge_labels = {}
        for i, (u, v) in enumerate(highlighted_edges):
            if i < len(highlight_edges):
                edge_data = highlight_edges[i]
                rate = edge_data.get("rate", 0.0)
                cost = edge_data.get("cost", 0.0)
                kind = edge_data.get("kind", "trade")
                
                # Format label based on edge type
                if kind == "trade":
                    # Show rate (multiplicative factor)
                    label = f"{rate:.4f}"
                else:
                    # Transfer: show cost or fee info
                    total_fee = edge_data.get("total_fee_usd", 0.0)
                    if total_fee > 0:
                        label = f"${total_fee:.2f}"
                    else:
                        label = f"{cost:.4f}"
                
                edge_labels[(u, v)] = label
        
        if edge_labels:
            # Draw edge labels for highlighted path
            nx.draw_networkx_edge_labels(
                G,
                pos,
                edge_labels=edge_labels,
                font_size=7,
                font_weight="bold",
                bbox=dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#D32F2F", linewidth=1.5),
                ax=ax,
            )

    import matplotlib.lines as mlines
    legend_handles = [
        mlines.Line2D([], [], color="#888888", linewidth=2.0,
                       label="Intra-exchange trade"),
        mlines.Line2D([], [], color="#BDBDBD", linewidth=1.0, linestyle="dotted",
                       label="Cross-exchange transfer"),
        mlines.Line2D([], [], color="#D32F2F", linewidth=3.5,
                       label="Profitable path"),
    ]
    ax.legend(
        handles=legend_handles,
        loc="center",
        frameon=True,
        fancybox=True,
        shadow=False,
        fontsize=10,
        framealpha=0.85,
        edgecolor="#CCCCCC",
        facecolor="white",
    )

    title = "Stablecoin Arbitrage Graph"
    if highlight_path:
        title += "  (profitable path in red)"
    ax.set_title(title, fontsize=13, fontweight="bold")
    ax.axis("off")
    fig.tight_layout()

    return fig


# --------------------------------------------------------------
# Helper: run search and format result text (with risk info)
# --------------------------------------------------------------

def run_search_and_format(
    start_wallet: str,
    liquid_cash: float,
    heuristic_name: str,
    status_container=None,  # Streamlit container for real-time log updates
) -> tuple[str, Optional[PlanResult]]:
    """
    Run A* / Weighted A* from the selected start node and return a human-readable report.

    Uses the selected heuristic in the search.
    """
    try:
        ex, coin = start_wallet.split(":")
    except ValueError:
        return "Invalid start wallet selection (expected 'exchange:coin').", None

    start_node: NodeId = (ex, coin)

    # Set up real-time logging to Streamlit if status_container provided
    class StreamlitLogHandler(logging.Handler):
        def __init__(self, container):
            super().__init__()
            self.container = container
            self.log_lines = []

        def emit(self, record):
            try:
                msg = self.format(record)
                self.log_lines.append(msg)
                # Update the container with latest logs (keep last 10 lines)
                if self.container:
                    display_lines = self.log_lines[-10:]  # Show last 10 lines
                    self.container.code("\n".join(display_lines), language=None)
            except Exception:
                pass

    # Capture logging output for file / Streamlit
    log_capture = io.StringIO()
    handler = logging.StreamHandler(log_capture)
    handler.setLevel(logging.INFO)
    formatter = logging.Formatter("%(message)s")  # Simplified format
    handler.setFormatter(formatter)

    # Get loggers for search modules
    astar_logger = logging.getLogger("scripts.astar_vol")
    h3_parallel_logger = logging.getLogger("scripts.h3_parallel")
    weighted_logger = logging.getLogger("scripts.weighted_astar")

    for lg in (astar_logger, h3_parallel_logger, weighted_logger):
        lg.addHandler(handler)
        lg.setLevel(logging.INFO)

    # Add Streamlit handler if container provided
    streamlit_handler = None
    if status_container:
        streamlit_handler = StreamlitLogHandler(status_container)
        streamlit_handler.setLevel(logging.INFO)
        streamlit_handler.setFormatter(logging.Formatter("%(message)s"))
        for lg in (astar_logger, h3_parallel_logger, weighted_logger):
            lg.addHandler(streamlit_handler)

    try:
        # Verify heuristic parameter is being passed correctly
        if heuristic_name not in [
            "h1_liquidity",
            "h2_slippage",
            "h3_parallel",
            "h4_chain_congestion",
        ]:
            if streamlit_handler:
                for lg in (astar_logger, h3_parallel_logger, weighted_logger):
                    lg.removeHandler(streamlit_handler)
            for lg in (astar_logger, h3_parallel_logger, weighted_logger):
                lg.removeHandler(handler)
            return (
                f"Invalid heuristic: {heuristic_name}. "
                "Must be 'h1_liquidity', 'h2_slippage', "
                "'h3_parallel', or 'h4_chain_congestion'."
            )

        # Handle parallel search heuristic
        if heuristic_name == "h3_parallel":
            from scripts.h3_parallel import parallel_search_from_random_starts

            if streamlit_handler:
                streamlit_handler.container.text(
                    "Running parallel search from 3 random starting points..."
                )

            # For parallel search, choose a base heuristic
            base_heuristic = "h1_liquidity"

            result: Optional[PlanResult] = parallel_search_from_random_starts(
                liquid_cash_usd=liquid_cash,
                max_depth=4,  # Reduced from 6 to 4 for faster execution
                max_time_sec=1800.0,
                min_profit_usd=0.0,
                heuristic=base_heuristic,  # Base heuristic for each parallel search
                num_starts=3,
            )

        elif heuristic_name == "h4_chain_congestion":
            # Weighted A* with chain + exchange risk heuristic
            result = weighted_astar_best_path(
            start_node=start_node,
            liquid_cash_usd=liquid_cash,
                max_depth=4,  # Reduced from 6 to 4 for faster execution
            max_time_sec=1800.0,
            min_profit_usd=0.0,
        )

        else:
            # Standard single-start search for h1 / h2
            result = astar_best_path_with_liquidity(
                start_node=start_node,
                liquid_cash_usd=liquid_cash,
                max_depth=4,  # Reduced from 6 to 4 for faster execution
                max_time_sec=1800.0,
                min_profit_usd=0.0,
                heuristic=heuristic_name,  # Pass selected heuristic to A*
            )

        # Clean up handlers
        if streamlit_handler:
            for lg in (astar_logger, h3_parallel_logger, weighted_logger):
                lg.removeHandler(streamlit_handler)
        for lg in (astar_logger, h3_parallel_logger, weighted_logger):
            lg.removeHandler(handler)

    except Exception as e:
        if streamlit_handler:
            for lg in (astar_logger, h3_parallel_logger, weighted_logger):
                lg.removeHandler(streamlit_handler)
        for lg in (astar_logger, h3_parallel_logger, weighted_logger):
            lg.removeHandler(handler)
        return f"Error while running search: {e}", None

    if result is None:
        if heuristic_name == "h3_parallel":
            return (
                "No profitable path found from any of the 3 random starting points "
                f"with {liquid_cash:.2f} USD using parallel search.",
                None
            )
        else:
            return (
                f"No profitable path found from {start_wallet} with "
                f"{liquid_cash:.2f} USD using heuristic {heuristic_name}.",
                None
            )

    profit_pct = (
        (result.profit_usd / liquid_cash) * 100.0 if liquid_cash > 0 else 0.0
    )
    route_str = " -> ".join(f"{ex}:{c}" for (ex, c) in result.path)

    lines: list[str] = []
    if heuristic_name == "h3_parallel":
        lines.append(
            "Max profitable current trade (Parallel search from 3 random starts):"
        )
        lines.append("Note: Searched from 3 random starting points in parallel")
    elif heuristic_name == "h4_chain_congestion":
        lines.append(
            "Max profitable current trade (Weighted A* with chain + exchange risk):"
        )
        lines.append(f"Start node: {start_wallet}")
    else:
        lines.append(f"Max profitable current trade (A* with {heuristic_name}):")
        lines.append(f"Start node: {start_wallet}")

    lines.append(f"Start cash: {liquid_cash:.2f} USD")
    lines.append(f"Final cash: {result.final_cash_usd:.2f} USD")
    lines.append(f"Profit: {result.profit_usd:.2f} USD ({profit_pct:.4f}%)")
    lines.append("")

    lines.append("Route:")
    lines.append(f"  {route_str}")
    lines.append("")

    # Add heuristic debug section
    lines.append("Heuristic Values (Debug):")
    lines.append("-" * 60)

    current_cash = liquid_cash
    remaining_time = 1800.0  # max_time_sec from search call

    if heuristic_name == "h3_parallel":
        lines.append(
            "Per-node heuristic values are omitted for parallel search "
            "(multiple A* runs with a base heuristic)."
        )
    else:
        for i, node in enumerate(result.path):
            exchange, coin = node
            lines.append(f"  Step {i+1}: {exchange}:{coin}")

            if heuristic_name == "h1_liquidity":
                h1_val = volume_heuristic_cost(
                    exchange_name=exchange,
                    coin=coin,
                    order_notional_usd=current_cash,
                    remaining_time_sec=remaining_time,
                )

                if h1_val == UNKNOWN_LIQUIDITY_PENALTY:
                    label = "RISKY (no volume data)"
                elif h1_val < 0.1:
                    label = "OK (very liquid)"
                elif h1_val < 1.0:
                    label = "Moderate liquidity risk"
                else:
                    label = "RISKY (low liquidity)"

                lines.append(
                    f"    Liquidity: {label} [penalty={h1_val:.4f}]"
                )

            elif heuristic_name == "h2_slippage":
                h2_val = slippage_heuristic_cost(
                    exchange_name=exchange,
                    coin=coin,
                    order_size_usd=current_cash,
                    side="buy",  # Default side
                )

                if h2_val == UNKNOWN_SLIPPAGE_PENALTY:
                    label = "RISKY (no order book data)"
                elif h2_val < 5.0:
                    label = "OK (low slippage)"
                elif h2_val < 20.0:
                    label = "Moderate slippage risk"
                else:
                    label = "RISKY (high slippage)"

                lines.append(
                    f"    Slippage: {label} [penalty={h2_val:.4f}]"
                )

            elif heuristic_name == "h4_chain_congestion":
                # Chain kickback risk
                h_chain = chain_congestion_heuristic_cost(
                    exchange_name=exchange,
                    coin=coin,
                    remaining_time_sec=remaining_time,
                )

                if h_chain == UNKNOWN_CHAIN_PENALTY:
                    label_chain = "RISKY (no chain timing info / invalid)"
                elif h_chain < 0.1:
                    label_chain = "Low kickback risk (slow / conservative chain)"
                elif h_chain < 1.0:
                    label_chain = "Moderate kickback risk (faster chain)"
                else:
                    label_chain = "HIGH kickback risk (very fast chain)"

                # Exchange freeze risk
                h_exch = exchange_risk_heuristic_cost(exchange)

                if h_exch == UNKNOWN_EXCHANGE_PENALTY:
                    label_exch = "RISKY (unknown exchange)"
                elif h_exch < 0.1:
                    label_exch = "OK (reliable exchange)"
                elif h_exch < 1.0:
                    label_exch = "Moderate freeze risk"
                else:
                    label_exch = "HIGH freeze / shutdown risk"

                # Combined penalty (what Weighted A* uses in h)
                h_total = chain_exchange_risk_heuristic_cost(
                    exchange_name=exchange,
                    coin=coin,
                    remaining_time_sec=remaining_time,
                )

                lines.append(
                    f"    Chain risk: {label_chain} [penalty={h_chain:.4f}]"
                )
                lines.append(
                    f"    Exchange risk: {label_exch} [penalty={h_exch:.4f}]"
                )
                lines.append(
                    f"    Combined (h_chain + h_exchange) = {h_total:.4f}"
                )

            lines.append("")

    lines.append("Steps:")

    # One line per edge, showing chain for transfers
    for i, edge in enumerate(result.edges, start=1):
        kind = edge.get("kind", "trade")

        if kind == "trade":
            ex = edge.get("exchange")
            c_from = edge.get("coin_from")
            c_to = edge.get("coin_to")
            taker_fee = edge.get("taker_fee")
            if isinstance(taker_fee, (int, float)):
                fee_str = f", taker fee ≈ {taker_fee * 100:.3f}%"
            else:
                fee_str = ""
            lines.append(f"{i}. Trade on {ex}: {c_from} → {c_to}{fee_str}")
        else:
            ex_from = edge.get("exchange")
            ex_to = edge.get("target_exchange")
            coin = edge.get("coin")
            chain = edge.get("chain") or "unknown chain"
            fee_units = edge.get("withdrawal_fee_units")
            t_sec = edge.get("transfer_time_sec")

            details: list[str] = []
            if isinstance(fee_units, (int, float)):
                details.append(f"fee {fee_units:g} {coin}")
            if isinstance(t_sec, (int, float)) and t_sec > 0:
                details.append(f"~{t_sec:.0f}s est. transfer time")
            detail_str = f" ({', '.join(details)})" if details else ""

            lines.append(
                f"{i}. Transfer {coin}: {ex_from} → {ex_to} via {chain}{detail_str}"
            )

    return "\n".join(lines), result


# --------------------------------------------------------------
# Streamlit app
# --------------------------------------------------------------

def main():
    st.set_page_config(
        page_title="Stablecoin Arbitrage UI",
        layout="wide",
    )

    st.title("Stablecoin Cross-Exchange Arbitrage")
    st.caption("Live graph + heuristic selection + price updates")

    # Session state: store the current NetworkX graph and search result text
    if "graph" not in st.session_state:
        with st.spinner("Fetching live data from exchanges (this may take up to a minute)..."):
            G, err = build_nx_graph(show_all=True)
        st.session_state["graph"] = G
        if err:
            st.session_state["network_error"] = err
    if "best_trade_text" not in st.session_state:
        st.session_state["best_trade_text"] = "Click **Run search** to compute a path."
    if "show_all" not in st.session_state:
        st.session_state["show_all"] = True
    if "last_search_result" not in st.session_state:
        st.session_state["last_search_result"] = None

    if st.session_state.get("network_error"):
        st.error(st.session_state["network_error"])
        st.info(
            "**Troubleshooting:**\n"
            "- Switch to a mobile hotspot or home wifi\n"
            "- Use a VPN that allows exchange traffic\n"
            "- Click **Update price** below once you're on a working network"
        )

    G: nx.DiGraph = st.session_state["graph"]

    # Prepare list of starting wallets (exchange:coin)
    start_wallet_options = sorted(f"{ex}:{coin}" for (ex, coin) in G.nodes())
    default_start = "binance:BUSD"
    if default_start not in start_wallet_options and start_wallet_options:
        default_start = start_wallet_options[0]

    # ---------------- Tabs at the top ----------------
    tab_graph, tab_prices, tab_fees, tab_help = st.tabs(
        ["Arbitrage Graph", "Live Prices", "Fees", "How to Use"]
    )

    # ---------------- Tab 1: Graph + controls ----------------
    with tab_graph:
        # Top layout: graph + controls
        col_graph, col_controls = st.columns([3, 1])

        with col_controls:
            st.subheader("Controls")

            # Toggle for showing all nodes/edges (unfiltered)
            show_all = st.checkbox(
                "Show all nodes & edges (unfiltered)",
                value=st.session_state.get("show_all", True),
                help="If enabled, shows all nodes and edges including those filtered out by price tolerance, portfolio size checks, etc."
            )
            
            # Rebuild graph if checkbox state changed
            if show_all != st.session_state.get("show_all", False):
                st.session_state["show_all"] = show_all
                G, err = build_nx_graph(show_all=show_all)
                st.session_state["graph"] = G
                st.session_state["network_error"] = err
                if err:
                    st.error(err)
                start_wallet_options[:] = sorted(
                    f"{ex}:{coin}" for (ex, coin) in G.nodes()
                )

            # Update prices -> rebuild the graph
            if st.button("Update price"):
                with st.spinner("Fetching live data from exchanges..."):
                    G, err = build_nx_graph(show_all=show_all)
                st.session_state["graph"] = G
                st.session_state["network_error"] = err
                if err:
                    st.error(err)
                else:
                    st.success("Prices updated and graph rebuilt.")

                start_wallet_options[:] = sorted(
                    f"{ex}:{coin}" for (ex, coin) in G.nodes()
                )

            # Liquid cash input
            liquid_cash = st.number_input(
                "Liquid cash (USD)",
                min_value=0.0,
                value=1000.0,
                step=100.0,
                help="Total capital available to allocate to a trade.",
            )

            # Heuristic dropdown
            heuristic = st.selectbox(
                "Heuristic",
                [
                    "h1_liquidity",        # volume-based heuristic
                    "h2_slippage",         # order-book slippage heuristic
                    "h3_parallel",         # parallel search from random starts
                    "h4_chain_congestion", # Weighted A* using chain + exchange risk
                ],
                help="Select which heuristic h(n) to use in the search.",
            )

            # Start wallet selection (only hidden for parallel search)
            if heuristic != "h3_parallel":
                start_wallet = st.selectbox(
                    "Starting wallet (exchange:coin)",
                    options=start_wallet_options,
                    index=start_wallet_options.index(default_start)
                    if default_start in start_wallet_options
                    else 0,
                    help="Node where your funds currently live.",
                )
            else:
                # For parallel search, we don't need a specific starting wallet
                start_wallet = (
                    start_wallet_options[0] if start_wallet_options else "binance:USDT"
                )
                st.info("Parallel search will use 3 random starting points")

        st.markdown("---")
        st.subheader("Max profitable current trade")

        # ---- Run button: only run search when clicked ----
        if st.button("Run search"):
            # Create a status container for real-time logging
            with st.status("Running search...", expanded=True) as status:
                    # Create a code block for real-time log display
                    log_display = st.empty()

                    # Run search with real-time logging
                    result_text, search_result = run_search_and_format(
                        start_wallet, liquid_cash, heuristic, status_container=log_display
                    )

                    # Update status when done
                    status.update(label="Search completed!", state="complete")
                    st.session_state["best_trade_text"] = result_text
                    # Store the result object for graph highlighting
                    st.session_state["last_search_result"] = search_result

        # Display the last result (or the initial message)
        st.text(st.session_state["best_trade_text"])

    with col_graph:
        st.subheader("Arbitrage Graph")
        
        # Toggle for paper-ready visualization
        paper_mode = st.checkbox(
            "Paper-ready visualization",
            value=False,
            help="Structured block layout suitable for conference papers (CAIAC/CVPR style)"
        )
        
        # Get the last search result for highlighting
        last_result = st.session_state.get("last_search_result")
        highlight_path = None
        highlight_edges = None
        if last_result:
            # Filter path to only include nodes that exist in current graph
            # (in case graph was rebuilt after search)
            highlight_path = [node for node in last_result.path if node in G.nodes()]
            highlight_edges = last_result.edges
            
            # Debug: show if path was filtered
            if len(highlight_path) != len(last_result.path):
                st.caption(f"⚠️ Path filtered: {len(last_result.path)} → {len(highlight_path)} nodes (graph may have been rebuilt)")
            elif highlight_path:
                st.caption(f"✓ Highlighting path with {len(highlight_path)} nodes")
        
        # Toggle for simplified path-only view
        show_path_only = st.checkbox(
            "Show path only (simplified)",
            value=False,
            help="Show only the successful path, hiding all other nodes and edges"
        )
        
        # For paper mode, use the search result if available
        highlight_cycle = highlight_path if paper_mode else None
        
        if show_path_only and highlight_path:
            # Show simplified path-only graph
            fig = make_path_only_figure(G, highlight_path=highlight_path, highlight_edges=highlight_edges)
        elif paper_mode:
            fig = make_paper_ready_figure(G, highlight_cycle=highlight_cycle, show_cycle_label=True)
        else:
            fig = make_graph_figure(G, highlight_path=highlight_path, highlight_edges=highlight_edges)
        st.pyplot(fig, use_container_width=True)

        st.markdown(
            """
            **Edge legend**

            • **Solid (exchange colour)** — Intra-exchange trade (swap), cost includes taker fee.  
            • **Dotted gray** — Cross-exchange transfer, cost includes withdrawal fee.  
            • **Bold red** — Profitable arbitrage path found by the search.
            """
        )

    # ---------------- Tab 2: Live Prices ----------------
    with tab_prices:
        st.subheader("Live Prices (from current graph)")
        st.write(
            "These are the latest prices used to build the arbitrage graph. "
            "They ultimately come from ccxt/exchange APIs and configuration in `data.py`."
        )

        # Optional: allow refresh here as well
        if st.button("Refresh prices", key="refresh_prices_tab"):
            with st.spinner("Fetching live data from exchanges..."):
                G, err = build_nx_graph(show_all=st.session_state.get("show_all", False))
            st.session_state["graph"] = G
            st.session_state["network_error"] = err
            if err:
                st.error(err)
            else:
                st.success("Prices refreshed.")

        price_rows = []
        for node in G.nodes():
            meta = G.nodes[node]
            price_rows.append(
                {
                    "exchange": meta["exchange"],
                    "coin": meta["coin"],
                    "price_usd": meta["price_usd"],
                    "snapshot_ts": meta["snapshot_ts"],
                }
            )

        if price_rows:
            df_prices = pd.DataFrame(price_rows).sort_values(
                by=["exchange", "coin"]
            )
            st.dataframe(df_prices, use_container_width=True)
        else:
            st.info("No nodes found in the current graph.")

    # ---------------- Tab 3: Fees ----------------
    with tab_fees:
        st.subheader("Fees from fees.py")

        st.write(
            "All upper-case fee dictionaries in `fees.py` are shown below. "
            "Trading fees are typically percentages; withdrawal fees are per-coin "
            "and per-chain amounts."
        )

        # Collect all dict-like globals from the fees module
        fee_dicts = []
        for name in dir(fees):
            if not name.isupper():
                continue
            obj = getattr(fees, name)
            if isinstance(obj, dict):
                fee_dicts.append((name, obj))

        if not fee_dicts:
            st.warning("No fee dictionaries found in fees.py.")
        else:
            for name, mapping in fee_dicts:
                nice_name = name.replace("_", " ").title()
                st.markdown(f"### {nice_name}")

                rows = []

                # Special handling for withdrawal-fee dicts: they are typically
                # nested as exchange -> coin -> chain -> fee_units
                if name.startswith("WITHDRAWAL"):
                    for exchange, per_coin in mapping.items():
                        # per_coin might be dict(coin -> chain_map or fee)
                        if isinstance(per_coin, dict):
                            for coin, chain_map in per_coin.items():
                                # chain_map can be dict(chain -> fee) or a direct fee
                                if isinstance(chain_map, dict):
                                    for chain, fee_val in chain_map.items():
                                        rows.append(
                                            {
                                                "exchange": exchange,
                                                "coin": coin,
                                                "chain": chain,
                                                "fee_units": fee_val,
                                            }
                                        )
                                else:
                                    rows.append(
                                        {
                                            "exchange": exchange,
                                            "coin": coin,
                                            "chain": "N/A",
                                            "fee_units": chain_map,
                                        }
                                    )
                        else:
                            rows.append(
                                {
                                    "exchange": exchange,
                                    "coin": "N/A",
                                    "chain": "N/A",
                                    "fee_units": per_coin,
                                }
                            )
                else:
                    # Default behavior for simple flat dicts, e.g. trading fees
                    for k, v in mapping.items():
                        if isinstance(v, dict):
                            row = {"key": k}
                            for sub_k, sub_v in v.items():
                                row[sub_k] = sub_v
                            rows.append(row)
                        else:
                            rows.append({"key": k, "value": v})

                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)
                else:
                    st.info(f"No data in {name}.")

    # ---------------- Tab 4: How to Use ----------------
    with tab_help:
        st.subheader("How to Use This UI")

        st.markdown(
            """
### Overview

This interface helps you **visualize** the stablecoin arbitrage graph,  
inspect **live prices** and **fees**, and run different **A\\*-based searches**  
to find the most profitable current trade route.

The UI is organized into four tabs:

1. **Arbitrage Graph** – main view (graph + controls + search results)  
2. **Live Prices** – table of the prices currently used in the graph  
3. **Fees** – trading + withdrawal fees used in the model  
4. **How to Use** – this help page  

---

### 1. Arbitrage Graph Tab

**Left side: Graph**

- Each **node** is a wallet: `exchange:COIN` (e.g. `binance:USDT`).  
- Node label shows the coin’s **USD price** on that exchange.  
- **Blue edges** = *trades* on a single exchange (swapping one stablecoin for another).  
- **Green edges** = *transfers* between exchanges (withdrawal on a specific chain).

This is the graph over which the A\\* / Weighted A\\* search runs.

**Right side: Controls**

1. **Update price**  
   - Rebuilds the graph using the latest data from the exchanges.  
   - Use this whenever you want a fresh snapshot of the market.

2. **Liquid cash (USD)**  
   - How much capital you pretend to have in the starting wallet.  
   - The algorithm uses this to estimate fees, slippage, and profit.

3. **Heuristic**  
   - `h1_liquidity` – prefers routes with high trading volume / good liquidity.  
   - `h2_slippage` – penalizes routes where large orders would move the price a lot.  
   - `h3_parallel` – runs several A\\* searches in parallel from random starting nodes.  
   - `h4_chain_congestion` – Weighted A\\* that also penalizes fast / risky chains and less reliable exchanges.

4. **Starting wallet (exchange:coin)**  
   - Where your funds are assumed to live **before** you start the route.  
   - For `h3_parallel` this is hidden; the algorithm chooses random starts instead.

5. **Run search**  
   - Launches the selected search algorithm.  
   - While it’s running, a status box shows streaming log messages from the search.  
   - When finished, the “Max profitable current trade” section is updated.

**Search Results Section**

After you click **Run search**, you’ll see:

- **Start cash / Final cash / Profit**  
  - Shows how much your capital would grow along the best route found.  

- **Route**  
  - A list like `binance:USDT -> kucoin:USDT -> ...`  
  - Each step is a node in the path returned by the search.

- **Heuristic Values (Debug)**  
  - For each node on the path, you see labels such as:  
    - “OK (very liquid)” / “Moderate liquidity risk” / “RISKY (low liquidity)”  
    - “OK (low slippage)” / “RISKY (high slippage)”  
    - “Low kickback risk” / “HIGH freeze / shutdown risk”, etc.  
  - This helps you understand **why** each heuristic preferred or avoided certain routes.

- **Steps**  
  - Detailed step-by-step explanation of the route:  
    - For trades: which coin you trade into on which exchange and the taker fee.  
    - For transfers: from which exchange to which exchange, on which chain,
      approximate transfer time, and the withdrawal fee in coin units.

---

### 2. Live Prices Tab

- Shows a table with one row per node in the graph:
  - `exchange`  
  - `coin`  
  - `price_usd`  
  - `snapshot_ts` (timestamp when that price was fetched)  

- Use **Refresh prices** in this tab if you want to update the table and graph
  without switching back to the main tab first.

This is useful for quickly checking whether prices look reasonable before you
trust any arbitrage route.

---

### 3. Fees Tab

- Shows all fee dictionaries defined in `fees.py`.

**Trading fees**

- Displayed as simple key–value tables:
  - `key` = exchange name  
  - `value` = maker/taker fee expressed as a decimal (e.g. `0.001` = 0.1%)

**Withdrawal fees**

- Shown in a flattened table with columns:
  - `exchange` – which exchange the withdrawal is from  
  - `coin` – which asset you are withdrawing (e.g. `USDT`)  
  - `chain` – blockchain / network used (e.g. `ETH`, `TRX`)  
  - `fee_units` – fee charged in **coin units** on that chain  

These are exactly the fees that are baked into the **green transfer edges** on the graph.

---

### 4. Tips for Interpreting Results

- A route with very high profit but lots of “RISKY” labels probably relies on:
  - low-liquidity markets  
  - chains or exchanges with higher operational risk  

- Comparing heuristics:
  - Try running the same starting wallet and cash with different heuristics
    to see how the route changes.  
  - `h1_liquidity` is usually the safest baseline;  
    `h4_chain_congestion` is more conservative about infrastructure risk.

- Remember: this UI is **simulation only**.  
  It does not place real orders or transfers funds.
            """
        )


if __name__ == "__main__":
    main()
