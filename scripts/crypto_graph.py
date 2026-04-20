"""
Graph construction for cross-exchange cryptocurrency arbitrage.

Builds the same (nodes, adjacency) structure as the stablecoin graph.py
so the existing search algorithms (A*, Bellman-Ford) can consume it
without modification.

Node:  (exchange_name, coin)        e.g.  ("binance", "BTC")
Edge:  dict with at minimum:
         "from", "to", "kind", "rate", "cost"
       where  cost = -log(rate)
       and    rate = effective multiplicative factor on portfolio value.

Edge kinds:
  "trade"     — swap two coins on the *same* exchange (uses bid/ask)
  "transfer"  — move the *same* coin between two exchanges (withdrawal fee)
"""

from __future__ import annotations

import math
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

from scripts.crypto_data import (
    EXCHANGES,
    CRYPTO_COINS,
    ExchangeTickers,
    NodeId,
    derive_usd_prices,
    fetch_all_tickers,
    fetch_exchange_tickers,
)
from scripts.crypto_fees import (
    CRYPTO_WITHDRAWAL_FEES,
    get_taker_fee,
    get_network_gas_fee,
    get_min_portfolio_threshold,
    fetch_live_trading_fees,
)
from scripts.transfer_time import get_chain_time_seconds

Adjacency = Dict[NodeId, List[Dict[str, Any]]]

# ────────────────────────────────────────────────────────────
# Graph cache (same pattern as stablecoin graph.py)
# ────────────────────────────────────────────────────────────
_CACHED_GRAPH: Optional[Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]] = None
_CACHE_TIMESTAMP: Optional[float] = None
_CACHE_TTL_SEC: float = 60.0

REFERENCE_NOTIONAL_USD: float = 10_000.0


# ────────────────────────────────────────────────────────────
# Trade edges
# ────────────────────────────────────────────────────────────

def _build_trade_edges(
    all_tickers: ExchangeTickers,
    prices: Dict[NodeId, float],
    use_live_fees: bool = False,
) -> Adjacency:
    """
    Create trade edges from actual ticker bid/ask data.

    For each relevant pair (e.g. BTC/USDT) on an exchange we create
    TWO directed edges:
      1.  (ex, base) → (ex, quote)   selling base for quote → use BID
      2.  (ex, quote) → (ex, base)   buying  base with quote → use 1/ASK

    **USD-normalized rates**: Unlike stablecoins where all coins ≈ $1,
    crypto prices span orders of magnitude (BTC ~ $95k, DOGE ~ $0.08).
    We normalise every edge rate to a *multiplicative factor on portfolio
    USD value* so that cost = -log(usd_rate) and the search algorithms
    correctly identify profitable paths.

        usd_rate = raw_rate * price_to_usd / price_from_usd
    """
    adj: Adjacency = defaultdict(list)

    for ex_name, tickers in all_tickers.items():
        taker_fee = get_taker_fee(ex_name) or 0.0

        if use_live_fees:
            ex_obj = EXCHANGES.get(ex_name)
            if ex_obj:
                live = fetch_live_trading_fees(ex_name, ex_obj)
                if live and "taker" in live:
                    taker_fee = live["taker"]

        for symbol, ticker in tickers.items():
            parts = symbol.split("/")
            if len(parts) != 2:
                continue
            base, quote = parts

            # Both coins must exist as nodes (with known USD prices)
            price_base = prices.get((ex_name, base))
            price_quote = prices.get((ex_name, quote))
            if not price_base or not price_quote:
                continue
            if price_base <= 0 or price_quote <= 0:
                continue

            bid = ticker.get("bid")
            ask = ticker.get("ask")

            if not (isinstance(bid, (int, float)) and isinstance(ask, (int, float))):
                continue
            if bid <= 0 or ask <= 0:
                continue

            # ── Edge 1: sell base → receive quote ──
            # raw_rate = bid (units of quote per 1 base), after taker fee
            raw_sell = bid * (1.0 - taker_fee)
            usd_sell = raw_sell * price_quote / price_base
            if usd_sell > 0:
                sell_cost = -math.log(usd_sell)
                from_node: NodeId = (ex_name, base)
                to_node: NodeId = (ex_name, quote)
                adj[from_node].append({
                    "from": from_node,
                    "to": to_node,
                    "kind": "trade",
                    "exchange": ex_name,
                    "coin_from": base,
                    "coin_to": quote,
                    "pair": symbol,
                    "rate": usd_sell,
                    "cost": sell_cost,
                    "taker_fee": taker_fee,
                    "raw_rate": raw_sell,
                    "withdrawal_fee_units": None,
                    "reference_amount_units": None,
                    "chain": None,
                    "transfer_time_sec": 0.0,
                })

            # ── Edge 2: buy base with quote ──
            # raw_rate = 1/ask (units of base per 1 quote), after taker fee
            raw_buy = (1.0 / ask) * (1.0 - taker_fee)
            usd_buy = raw_buy * price_base / price_quote
            if usd_buy > 0:
                buy_cost = -math.log(usd_buy)
                from_node2: NodeId = (ex_name, quote)
                to_node2: NodeId = (ex_name, base)
                adj[from_node2].append({
                    "from": from_node2,
                    "to": to_node2,
                    "kind": "trade",
                    "exchange": ex_name,
                    "coin_from": quote,
                    "coin_to": base,
                    "pair": symbol,
                    "rate": usd_buy,
                    "cost": buy_cost,
                    "taker_fee": taker_fee,
                    "raw_rate": raw_buy,
                    "withdrawal_fee_units": None,
                    "reference_amount_units": None,
                    "chain": None,
                    "transfer_time_sec": 0.0,
                })

    return adj


# ────────────────────────────────────────────────────────────
# Transfer edges
# ────────────────────────────────────────────────────────────

def _build_transfer_edges(
    prices: Dict[NodeId, float],
    portfolio_size_usd: float = REFERENCE_NOTIONAL_USD,
    use_live_fees: bool = False,
) -> Adjacency:
    """
    For each coin present on >= 2 exchanges, create transfer edges via
    common blockchain networks.

    **USD-normalized rate** includes both the fee impact AND any
    cross-exchange price difference for the same coin:

        fee_rate   = 1 - total_fee_usd / portfolio_size_usd
        price_gain = price_to / price_from
        usd_rate   = fee_rate * price_gain

    A positive price_gain (destination exchange prices the coin higher)
    is the core of cross-exchange arbitrage.
    """
    adj: Adjacency = defaultdict(list)

    coin_exchanges: Dict[str, List[str]] = defaultdict(list)
    for (ex, coin) in prices:
        coin_exchanges[coin].append(ex)

    for coin, ex_list in coin_exchanges.items():
        if len(ex_list) < 2:
            continue

        for ex_from in ex_list:
            ex_withdraw_cfg = CRYPTO_WITHDRAWAL_FEES.get(ex_from, {}).get(coin)
            if not ex_withdraw_cfg:
                continue

            price_from = prices.get((ex_from, coin))
            if not price_from or price_from <= 0:
                continue

            amount_units = portfolio_size_usd / price_from

            for ex_to in ex_list:
                if ex_to == ex_from:
                    continue

                price_to = prices.get((ex_to, coin))
                if not price_to or price_to <= 0:
                    continue

                chains_to_cfg = CRYPTO_WITHDRAWAL_FEES.get(ex_to, {}).get(coin, {})
                if chains_to_cfg:
                    common_chains = set(ex_withdraw_cfg) & set(chains_to_cfg)
                else:
                    common_chains = set(ex_withdraw_cfg)

                if not common_chains:
                    continue

                for chain in common_chains:
                    fee_units = ex_withdraw_cfg[chain]
                    gas_fee_usd = get_network_gas_fee(chain)

                    min_threshold = get_min_portfolio_threshold(chain)
                    if portfolio_size_usd < min_threshold:
                        continue

                    withdrawal_fee_usd = fee_units * price_from
                    total_fee_usd = withdrawal_fee_usd + gas_fee_usd

                    if total_fee_usd >= portfolio_size_usd:
                        continue

                    fee_rate = 1.0 - (total_fee_usd / portfolio_size_usd)
                    if fee_rate <= 0:
                        continue

                    # Cross-exchange price ratio: >1 if destination is more expensive
                    price_ratio = price_to / price_from
                    usd_rate = fee_rate * price_ratio

                    if usd_rate <= 0:
                        continue

                    cost = -math.log(usd_rate)
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
                        "rate": usd_rate,
                        "cost": cost,
                        "taker_fee": None,
                        "withdrawal_fee_units": fee_units,
                        "gas_fee_usd": gas_fee_usd,
                        "total_fee_usd": total_fee_usd,
                        "price_from_usd": price_from,
                        "price_to_usd": price_to,
                        "price_ratio": price_ratio,
                        "reference_amount_units": amount_units,
                        "chain": chain,
                        "transfer_time_sec": t_sec,
                    })

    return adj


# ────────────────────────────────────────────────────────────
# Public API
# ────────────────────────────────────────────────────────────

def build_graph(
    force_refresh: bool = False,
    portfolio_size_usd: float = REFERENCE_NOTIONAL_USD,
    use_live_fees: bool = False,
) -> Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]:
    """
    Build the crypto arbitrage graph.

    Returns the **same** (nodes, adj) tuple format as ``graph.build_graph``
    so all existing algorithms work unchanged.

    Args:
        force_refresh:      bypass 60-second cache
        portfolio_size_usd: used for fee-impact calculations
        use_live_fees:      try CCXT live fee endpoints first

    Returns:
        nodes  — dict[(exchange, coin)] -> metadata dict
        adj    — adjacency list: node -> list[edge_dict]
    """
    global _CACHED_GRAPH, _CACHE_TIMESTAMP

    now = time.time()
    if (
        not force_refresh
        and _CACHED_GRAPH is not None
        and _CACHE_TIMESTAMP is not None
        and (now - _CACHE_TIMESTAMP) < _CACHE_TTL_SEC
    ):
        return _CACHED_GRAPH

    print("\n[crypto_graph] Fetching live market data …")
    all_tickers = fetch_all_tickers()
    prices, snapshot_ts = derive_usd_prices(all_tickers)

    # Build node metadata
    nodes: Dict[NodeId, Dict[str, Any]] = {
        (ex, coin): {
            "exchange": ex,
            "coin": coin,
            "price_usd": price_usd,
            "snapshot_ts": snapshot_ts,
        }
        for (ex, coin), price_usd in prices.items()
    }

    # Build edges
    adj: Adjacency = defaultdict(list)

    trade_adj = _build_trade_edges(all_tickers, prices, use_live_fees=use_live_fees)
    transfer_adj = _build_transfer_edges(
        prices,
        portfolio_size_usd=portfolio_size_usd,
        use_live_fees=use_live_fees,
    )

    for node, edges in trade_adj.items():
        adj[node].extend(edges)
    for node, edges in transfer_adj.items():
        adj[node].extend(edges)

    _CACHED_GRAPH = (nodes, adj)
    _CACHE_TIMESTAMP = now

    # Summary
    trade_count = sum(len(e) for e in trade_adj.values())
    transfer_count = sum(len(e) for e in transfer_adj.values())
    print(f"[crypto_graph] Nodes: {len(nodes)}")
    print(f"[crypto_graph] Trade edges: {trade_count}")
    print(f"[crypto_graph] Transfer edges: {transfer_count}")
    print(f"[crypto_graph] Total edges: {trade_count + transfer_count}")

    return nodes, adj


if __name__ == "__main__":
    nodes, adj = build_graph(force_refresh=True)

    print(f"\n{'─'*60}")
    print(f"Graph built successfully.")
    print(f"  Nodes: {len(nodes)}")
    print(f"  Edges: {sum(len(v) for v in adj.values())}")

    # Show a few sample edges
    sample_count = 0
    for node, edges in adj.items():
        for e in edges:
            kind = e["kind"]
            fr = e["from"]
            to = e["to"]
            rate = e["rate"]
            cost = e["cost"]
            if kind == "trade":
                print(
                    f"  TRADE  {fr[0]:10s} {fr[1]:5s} → {to[1]:5s}  "
                    f"rate={rate:.8f}  cost={cost:.6f}"
                )
            else:
                chain = e.get("chain", "?")
                print(
                    f"  XFER   {fr[0]:10s} → {to[0]:10s} [{fr[1]}]  "
                    f"chain={chain}  rate={rate:.8f}  cost={cost:.6f}"
                )
            sample_count += 1
            if sample_count >= 20:
                break
        if sample_count >= 20:
            break
