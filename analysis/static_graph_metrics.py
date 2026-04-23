"""
Offline graph size metrics from static config only (no exchange API calls).

Model (for reporting / upper bounds):
  * Nodes: every (exchange, coin) with a non-None market in ``COIN_MARKETS``,
    using prices present in ``prices`` (synthetic 1.0 USD for each such node so
    all configured venues are included even if live fetches would fail).
  * Intra-exchange (trade) edges: full directed clique—each coin at an
    exchange has a trade edge to every *other* coin on that same exchange
    (n * (n-1) per exchange). This is stronger than ``_build_trade_edges``,
    which only adds edges when a real CCXT direct pair exists.
  * Inter-exchange (transfer) edges: only between nodes sharing the *same*
    coin symbol, using ``_build_transfer_edges`` (common chains in
    ``WITHDRAWAL_FEES``, portfolio threshold, etc.)—see ``scripts/graph.py``.

Run: ``python -m analysis.static_graph_metrics`` from the repo root.
"""
from __future__ import annotations

from collections import defaultdict

from scripts.data import EXCHANGES, STABLE_COINS, COIN_MARKETS
from scripts.graph import (
    NodeId,
    REFERENCE_NOTIONAL_USD,
    _build_transfer_edges,
)


def static_price_map() -> dict[NodeId, float]:
    """One synthetic USD price per configured (exchange, coin)."""
    prices: dict[NodeId, float] = {}
    for coin in STABLE_COINS:
        for ex in EXCHANGES:
            if COIN_MARKETS.get(coin, {}).get(ex):
                prices[(ex, coin)] = 1.0
    return prices


def directed_intra_exchange_trade_count(prices: dict[NodeId, float]) -> int:
    """
    Full directed clique: for each exchange, all ordered coin pairs
    (c_from, c_to) with c_from != c_to among coins that have a node.
    """
    ex_to_coins: dict[str, set[str]] = defaultdict(set)
    for (ex, coin) in prices:
        ex_to_coins[ex].add(coin)
    total = 0
    for coins in ex_to_coins.values():
        n = len(coins)
        total += n * (n - 1)
    return total


def main() -> None:
    prices = static_price_map()
    n_nodes = len(prices)
    n_trade = directed_intra_exchange_trade_count(prices)

    t_adj = _build_transfer_edges(
        prices,
        portfolio_size_usd=REFERENCE_NOTIONAL_USD,
        use_live_fees=False,
    )
    n_transfer = sum(len(edges) for edges in t_adj.values())

    # Sanity: only same-coin transfers (enforced in _build_transfer_edges)
    for u, edges in t_adj.items():
        for e in edges:
            assert e.get("kind") == "transfer"
            c = e.get("coin")
            assert c == u[1] == e["to"][1], (u, e)

    n_total = n_trade + n_transfer

    print("Static graph (offline, synthetic prices for all configured markets)")
    print("  Unique coin symbols (STABLE_COINS):", len(STABLE_COINS))
    print("  Nodes (exchange, coin) from COIN_MARKETS:", n_nodes)
    print("  Directed trade edges (full clique, intra-exchange only):", n_trade)
    print("  Directed transfer edges (same coin, fee config + common chains):", n_transfer)
    print("  Directed edge total (trade + transfer):", n_total)
    print()
    print("  Reference notion (transfer fee logic):", REFERENCE_NOTIONAL_USD, "USD")


if __name__ == "__main__":
    main()
