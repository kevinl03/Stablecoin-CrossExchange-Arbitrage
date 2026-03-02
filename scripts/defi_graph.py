"""
Graph construction for cross-chain DEX arbitrage.

Builds the same (nodes, adjacency) structure as graph.py / crypto_graph.py
so all search algorithms work unchanged.

Node:  (chain, token_symbol)   e.g. ("arbitrum", "WETH")

Edge kinds:
  "swap"    — DEX trade, same chain, different tokens.
              Cost = DEX fee + gas.  Rate is USD-normalised.
  "bridge"  — Cross-chain transfer, same token, different chains.
              Cost = bridge % fee + flat fee + gas.
              Rate captures the cross-chain price differential.
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from scripts.defi_data import (
    CHAINS,
    TOKEN_REGISTRY,
    TOKEN_SYMBOLS,
    NodeId,
    fetch_defi_prices,
)
from scripts.defi_fees import (
    get_bridge_cost,
    get_dex_swap_fee,
    get_gas_per_swap,
    get_min_bridge_portfolio,
)

Adjacency = Dict[NodeId, List[Dict[str, Any]]]

# Graph cache
_CACHED_GRAPH: Optional[Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]] = None
_CACHE_TS: Optional[float] = None
_CACHE_TTL: float = 60.0

REFERENCE_NOTIONAL_USD: float = 10_000.0


# ────────────────────────────────────────────────────────────
# Swap edges (same chain, different tokens)
# ────────────────────────────────────────────────────────────

def _build_swap_edges(
    prices: Dict[NodeId, float],
    portfolio_size_usd: float,
) -> Adjacency:
    """
    For each chain, create directed swap edges between every pair of
    tokens that have a known price on that chain.

    USD-normalised rate:
        raw_rate = price_from / price_to  (units of to per from)
        usd_rate = raw_rate * price_to / price_from = 1.0  (before fees)
        After fees:  usd_rate = (1 - dex_fee) - gas / portfolio

    Since DeFi-Llama gives one aggregated price per chain, same-chain
    swaps are ≈ neutral in USD (only fees/gas drag).  The real arb
    comes from cross-chain price differences in the bridge edges.
    """
    adj: Adjacency = defaultdict(list)

    # Group tokens by chain
    chain_tokens: Dict[str, List[str]] = defaultdict(list)
    for (chain, symbol) in prices:
        chain_tokens[chain].append(symbol)

    for chain, symbols in chain_tokens.items():
        if len(symbols) < 2:
            continue

        gas_usd = get_gas_per_swap(chain)

        for sym_from in symbols:
            price_from = prices[(chain, sym_from)]
            for sym_to in symbols:
                if sym_from == sym_to:
                    continue
                price_to = prices[(chain, sym_to)]

                dex_fee = get_dex_swap_fee(chain, sym_from, sym_to)

                # USD rate: after percentage fee and flat gas cost
                # (1 - dex_fee) is the % retained
                # then subtract gas as fraction of portfolio
                usd_rate = (1.0 - dex_fee) - (gas_usd / portfolio_size_usd)
                if usd_rate <= 0:
                    continue

                cost = -math.log(usd_rate)

                from_node: NodeId = (chain, sym_from)
                to_node: NodeId = (chain, sym_to)

                adj[from_node].append({
                    "from": from_node,
                    "to": to_node,
                    "kind": "swap",
                    "chain": chain,
                    "token_from": sym_from,
                    "token_to": sym_to,
                    "rate": usd_rate,
                    "cost": cost,
                    "dex_fee": dex_fee,
                    "gas_usd": gas_usd,
                    "transfer_time_sec": 0.0,  # same-chain = instant
                })

    return adj


# ────────────────────────────────────────────────────────────
# Bridge edges (same token, different chains)
# ────────────────────────────────────────────────────────────

def _build_bridge_edges(
    prices: Dict[NodeId, float],
    portfolio_size_usd: float,
) -> Adjacency:
    """
    For each token present on >= 2 chains, create directed bridge
    edges via fast cross-chain bridges.

    USD-normalised rate includes:
      - bridge percentage fee
      - bridge flat fee (as fraction of portfolio)
      - **cross-chain price ratio** (price_to / price_from)
        This is where the arbitrage profit comes from.
    """
    adj: Adjacency = defaultdict(list)

    # Group chains by token
    token_chains: Dict[str, List[str]] = defaultdict(list)
    for (chain, symbol) in prices:
        token_chains[symbol].append(chain)

    for symbol, chains_list in token_chains.items():
        if len(chains_list) < 2:
            continue

        for chain_from in chains_list:
            price_from = prices[(chain_from, symbol)]
            for chain_to in chains_list:
                if chain_to == chain_from:
                    continue
                price_to = prices[(chain_to, symbol)]

                # Check minimum portfolio thresholds
                min_from = get_min_bridge_portfolio(chain_from)
                min_to = get_min_bridge_portfolio(chain_to)
                if portfolio_size_usd < max(min_from, min_to):
                    continue

                pct_fee, flat_fee_usd, bridge_time = get_bridge_cost(
                    chain_from, chain_to,
                )

                total_flat = flat_fee_usd
                if total_flat >= portfolio_size_usd:
                    continue

                # USD rate:
                #   (1 - pct_fee)           percentage retained
                #   - flat/portfolio        flat cost as fraction
                #   × (price_to/price_from) cross-chain price gain
                fee_rate = (1.0 - pct_fee) - (total_flat / portfolio_size_usd)
                if fee_rate <= 0:
                    continue

                price_ratio = price_to / price_from
                usd_rate = fee_rate * price_ratio
                if usd_rate <= 0:
                    continue

                cost = -math.log(usd_rate)

                from_node: NodeId = (chain_from, symbol)
                to_node: NodeId = (chain_to, symbol)

                adj[from_node].append({
                    "from": from_node,
                    "to": to_node,
                    "kind": "bridge",
                    "chain_from": chain_from,
                    "chain_to": chain_to,
                    "token": symbol,
                    "rate": usd_rate,
                    "cost": cost,
                    "bridge_pct_fee": pct_fee,
                    "bridge_flat_fee_usd": flat_fee_usd,
                    "price_from_usd": price_from,
                    "price_to_usd": price_to,
                    "price_ratio": price_ratio,
                    "transfer_time_sec": bridge_time,
                })

    return adj


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def build_graph(
    force_refresh: bool = False,
    portfolio_size_usd: float = REFERENCE_NOTIONAL_USD,
) -> Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]:
    """
    Build the cross-chain DEX arbitrage graph.

    Returns (nodes, adj) in the same format as graph.py / crypto_graph.py.
    """
    global _CACHED_GRAPH, _CACHE_TS

    now = time.time()
    if (
        not force_refresh
        and _CACHED_GRAPH is not None
        and _CACHE_TS is not None
        and (now - _CACHE_TS) < _CACHE_TTL
    ):
        return _CACHED_GRAPH

    print("\n[defi_graph] Fetching on-chain prices from DeFi-Llama …")
    prices, snapshot_ts = fetch_defi_prices()

    nodes: Dict[NodeId, Dict[str, Any]] = {
        (chain, symbol): {
            "chain": chain,
            "token": symbol,
            "price_usd": price_usd,
            "snapshot_ts": snapshot_ts,
        }
        for (chain, symbol), price_usd in prices.items()
    }

    adj: Adjacency = defaultdict(list)

    swap_adj = _build_swap_edges(prices, portfolio_size_usd)
    bridge_adj = _build_bridge_edges(prices, portfolio_size_usd)

    for node, edges in swap_adj.items():
        adj[node].extend(edges)
    for node, edges in bridge_adj.items():
        adj[node].extend(edges)

    _CACHED_GRAPH = (nodes, adj)
    _CACHE_TS = now

    swap_count = sum(len(e) for e in swap_adj.values())
    bridge_count = sum(len(e) for e in bridge_adj.values())
    print(f"[defi_graph] Nodes:  {len(nodes)}")
    print(f"[defi_graph] Swap edges:   {swap_count}")
    print(f"[defi_graph] Bridge edges: {bridge_count}")
    print(f"[defi_graph] Total edges:  {swap_count + bridge_count}")

    return nodes, adj


if __name__ == "__main__":
    nodes, adj = build_graph(force_refresh=True)

    print(f"\n{'─'*60}")
    print("Sample edges:")
    count = 0
    for node, edges in adj.items():
        for e in edges:
            kind = e["kind"]
            fr = e["from"]
            to = e["to"]
            rate = e["rate"]
            if kind == "swap":
                print(
                    f"  SWAP   {fr[0]:10s}  {fr[1]:5s} → {to[1]:5s}  "
                    f"rate={rate:.8f}  fee={e['dex_fee']*100:.2f}%  "
                    f"gas=${e['gas_usd']:.2f}"
                )
            else:
                pr = e.get("price_ratio", 0)
                print(
                    f"  BRIDGE {fr[0]:10s} → {to[0]:10s}  [{fr[1]:5s}]  "
                    f"rate={rate:.8f}  price_ratio={pr:.6f}  "
                    f"fee={e['bridge_pct_fee']*100:.3f}%+${e['bridge_flat_fee_usd']:.2f}  "
                    f"time={e['transfer_time_sec']:.0f}s"
                )
            count += 1
            if count >= 25:
                break
        if count >= 25:
            break
