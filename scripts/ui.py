# ==============================================================
# ui.py — Simple Streamlit UI for Stablecoin Arbitrage
# ==============================================================

from __future__ import annotations

import sys
import logging
import io
from pathlib import Path
from typing import Optional, Dict, List, Any
from collections import defaultdict

# Add project root (folder that CONTAINS "scripts") to path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import streamlit as st           # type: ignore
import matplotlib.pyplot as plt  # type: ignore
import networkx as nx            # type: ignore
import pandas as pd              # type: ignore

from scripts.graph import build_graph, _fetch_actual_trading_pair_rate
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


# --------------------------------------------------------------
# Small helper: build a NetworkX graph and matplotlib figure
# --------------------------------------------------------------

def build_nx_graph(show_all: bool = False):
    """
    Use build_graph() and convert to a NetworkX DiGraph.
    
    Args:
        show_all: If True, build an unfiltered graph with all possible nodes/edges
    """
    if show_all:
        nodes, adj = build_graph_unfiltered()
    else:
        nodes, adj = build_graph()

    G = nx.DiGraph()

    # Add nodes
    for node_id, meta in nodes.items():
        ex, coin = node_id
        G.add_node(
            node_id,
            exchange=ex,
            coin=coin,
            price_usd=meta["price_usd"],
            snapshot_ts=meta["snapshot_ts"],
        )

    # Add edges
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
                raw_edge=e,  # keep original dict if we ever need it
            )

    return G


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


def make_graph_figure(G: nx.DiGraph):
    """Create a matplotlib Figure with exchange clusters and proper edge coloring."""
    import math
    
    # Define distinct brand colors for each exchange
    exchange_colors = {
        "binance": "#F0B90B",      # Binance yellow
        "kraken": "#5842A3",       # Kraken purple
        "kucoin": "#26C6F9",       # KuCoin cyan
        "bybit": "#F7A600",        # Bybit orange
        "coinbase": "#0052FF",     # Coinbase blue
    }
    
    exchange_names = list(EXCHANGES.keys())
    node_colors = []
    node_labels = {}
    node_groups = {ex: [] for ex in exchange_names}

    # Group nodes by exchange
    for node in G.nodes():
        ex = G.nodes[node]["exchange"]
        coin = G.nodes[node]["coin"]
        price = G.nodes[node]["price_usd"]
        
        node_labels[node] = f"{ex}:{coin}\n${price:.4f}"
        node_colors.append(exchange_colors.get(ex, "#808080"))  # Gray for unknown exchanges
        node_groups[ex].append(node)

    # Color edges: same color for intra-exchange, different for inter-exchange
    edge_colors_list = []
    for u, v in G.edges():
        u_ex = G.nodes[u]["exchange"]
        v_ex = G.nodes[v]["exchange"]
        edge_kind = G.edges[(u, v)].get("kind", "trade")
        
        if u_ex == v_ex:
            # Intra-exchange edge (trade): use exchange color with transparency
            edge_color = exchange_colors.get(u_ex, "#808080")
            edge_colors_list.append(edge_color)
        else:
            # Inter-exchange edge (transfer): use green for transfers
            if edge_kind == "transfer":
                edge_colors_list.append("#2E7D32")  # Dark green for transfers
            else:
                edge_colors_list.append("#1976D2")  # Blue for trades (shouldn't happen but safety)

    # Create circular clusters for each exchange
    pos = {}
    num_exchanges = len([ex for ex in exchange_names if node_groups[ex]])
    
    if num_exchanges == 0:
        # Fallback if no nodes
        pos = nx.spring_layout(G, seed=42, k=2.0)
    else:
        # Arrange exchange clusters in a circle
        cluster_radius = 3.0  # Distance from center to cluster centers
        node_cluster_radius = 1.2  # Radius within each cluster for nodes
        
        for idx, ex in enumerate(exchange_names):
            if not node_groups[ex]:
                continue
            
            # Calculate cluster center position (arranged in a circle)
            angle = 2 * math.pi * idx / num_exchanges
            cluster_center_x = cluster_radius * math.cos(angle)
            cluster_center_y = cluster_radius * math.sin(angle)
            
            # Position nodes in a circle within this cluster
            nodes_in_exchange = sorted(node_groups[ex], key=lambda n: (G.nodes[n]["coin"], G.nodes[n]["price_usd"]))
            num_nodes = len(nodes_in_exchange)
            
            for node_idx, node in enumerate(nodes_in_exchange):
                if num_nodes == 1:
                    # Single node at cluster center
                    pos[node] = (cluster_center_x, cluster_center_y)
                else:
                    # Arrange nodes in a circle within the cluster
                    node_angle = 2 * math.pi * node_idx / num_nodes
                    node_x = cluster_center_x + node_cluster_radius * math.cos(node_angle)
                    node_y = cluster_center_y + node_cluster_radius * math.sin(node_angle)
                    pos[node] = (node_x, node_y)

    fig, ax = plt.subplots(figsize=(14, 10))
    
    # Draw nodes with exchange brand colors
    nx.draw_networkx_nodes(
        G,
        pos,
        node_size=800,
        node_color=node_colors,
        edgecolors="black",
        linewidths=2.0,
        ax=ax,
    )
    
    # Draw edges with proper coloring
    nx.draw_networkx_edges(
        G,
        pos,
        edge_color=edge_colors_list,
        arrows=True,
        arrowsize=18,
        width=2.5,
        alpha=0.8,
        arrowstyle="->",
        ax=ax,
    )
    
    # Draw labels
    nx.draw_networkx_labels(
        G,
        pos,
        labels=node_labels,
        font_size=8,
        font_weight="bold",
        ax=ax,
    )

    ax.set_title("Stablecoin Arbitrage Graph\nNodes clustered by exchange (colored by exchange) | Intra-exchange edges = exchange color, Inter-exchange edges = green", 
                 fontsize=12, fontweight="bold")
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
) -> str:
    """
    Run A* / Weighted A* from the selected start node and return a human-readable report.

    Uses the selected heuristic in the search.
    """
    try:
        ex, coin = start_wallet.split(":")
    except ValueError:
        return "Invalid start wallet selection (expected 'exchange:coin')."

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
        return f"Error while running search: {e}"

    if result is None:
        if heuristic_name == "h3_parallel":
            return (
                "No profitable path found from any of the 3 random starting points "
                f"with {liquid_cash:.2f} USD using parallel search."
            )
        else:
            return (
                f"No profitable path found from {start_wallet} with "
                f"{liquid_cash:.2f} USD using heuristic {heuristic_name}."
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

    return "\n".join(lines)


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
        st.session_state["graph"] = build_nx_graph(show_all=False)
    if "best_trade_text" not in st.session_state:
        st.session_state["best_trade_text"] = "Click **Run search** to compute a path."
    if "show_all" not in st.session_state:
        st.session_state["show_all"] = False

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
                value=st.session_state.get("show_all", False),
                help="If enabled, shows all nodes and edges including those filtered out by price tolerance, portfolio size checks, etc."
            )
            
            # Rebuild graph if checkbox state changed
            if show_all != st.session_state.get("show_all", False):
                st.session_state["show_all"] = show_all
                st.session_state["graph"] = build_nx_graph(show_all=show_all)
                G = st.session_state["graph"]
                # Refresh start wallet options in case node set changed
                start_wallet_options[:] = sorted(
                    f"{ex}:{coin}" for (ex, coin) in G.nodes()
                )

            # Update prices -> rebuild the graph
            if st.button("Update price"):
                st.session_state["graph"] = build_nx_graph(show_all=show_all)
                G = st.session_state["graph"]
                st.success("Prices updated and graph rebuilt.")

                # Refresh start wallet options in case node set changed
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
                    result_text = run_search_and_format(
                        start_wallet, liquid_cash, heuristic, status_container=log_display
                    )

                    # Update status when done
                    status.update(label="Search completed!", state="complete")
                    st.session_state["best_trade_text"] = result_text

        # Display the last result (or the initial message)
        st.text(st.session_state["best_trade_text"])

    with col_graph:
        st.subheader("Arbitrage Graph")
        fig = make_graph_figure(G)
        st.pyplot(fig, use_container_width=True)

        st.markdown(
            """
            **Edge colours**

            • Blue — Trade edge (intra-exchange swap), cost includes taker fee.  
            • Green — Transfer edge (cross-exchange), cost includes withdrawal fee on the chosen chain.  

                Edge costs (negative log of effective rate) are still used internally by A*,
                but are hidden here to keep the visualization readable.
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
            st.session_state["graph"] = build_nx_graph(show_all=st.session_state.get("show_all", False))
            G = st.session_state["graph"]
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
