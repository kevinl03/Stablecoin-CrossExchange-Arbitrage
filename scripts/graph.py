
from __future__ import annotations

import time
import math
from collections import defaultdict
from typing import Dict, Tuple, List, Any, Optional

# from our own modules
from scripts.data import EXCHANGES, STABLE_COINS, COIN_MARKETS, normalize_price_to_usd
from scripts.fees import (
    WITHDRAWAL_FEES,
    get_taker_fee,
    get_network_gas_fee,
    get_min_portfolio_threshold,
    fetch_live_trading_fees,
    fetch_live_withdrawal_fees,
)
from scripts.transfer_time import get_chain_time_seconds

# Node is (exchange, coin)
NodeId = Tuple[str, str]

Adjacency = Dict[NodeId, List[Dict[str, Any]]]

# Maximum deviation from $1.00 for a coin to be considered a stablecoin
# Coins trading outside this range are excluded (e.g., FRAX can trade at $0.80-$0.90)
STABLECOIN_PRICE_TOLERANCE = 0.05  # 5% tolerance: $0.95 - $1.05

# Graph caching to avoid rebuilding on every search
_CACHED_GRAPH: Optional[Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]] = None
_CACHE_TIMESTAMP: Optional[float] = None
_CACHE_TTL_SEC: float = 60.0  # Cache graph for 60 seconds


# Maximum deviation from $1.00 for a coin to be considered a stablecoin
# Coins trading outside this range are excluded (e.g., FRAX can trade at $0.80-$0.90)
STABLECOIN_PRICE_TOLERANCE = 0.05  # 5% tolerance: $0.95 - $1.05


def fetch_price_snapshot(
    market_data=None,
) -> Tuple[Dict[NodeId, float], float]:
    """
    Fetch a snapshot of USD-normalized prices for all (exchange, coin)
    pairs where we have a configured market in data.py.

    Filters out coins that deviate too far from $1.00 (not true stablecoins).
    Exchanges that fail on the first attempt are skipped for all remaining
    coins to avoid long cumulative timeouts.

    Args:
        market_data: Optional MarketDataStore instance. When provided,
                     prices are read from the store instead of calling CCXT.

    Returns:
        prices:    dict[(exchange, coin)] -> price_usd
        timestamp: unix time when snapshot was taken
    """
    if market_data is not None:
        prices = market_data.get_price_snapshot()
        return prices, time.time()

    prices: Dict[NodeId, float] = {}
    snapshot_ts = time.time()
    failed_exchanges: set = set()

    for coin in STABLE_COINS:
        for ex_name, ex in EXCHANGES.items():
            if ex_name in failed_exchanges:
                continue

            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue

            try:
                ticker = ex.fetch_ticker(market)
            except Exception:
                failed_exchanges.add(ex_name)
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

            if abs(price_usd - 1.0) > STABLECOIN_PRICE_TOLERANCE:
                continue

            prices[(ex_name, coin)] = price_usd

    if failed_exchanges:
        import logging
        logging.warning(
            "Could not reach %d exchange(s): %s",
            len(failed_exchanges),
            ", ".join(sorted(failed_exchanges)),
        )

    return prices, snapshot_ts


def _fetch_actual_trading_pair_rate(
    ex_name: str,
    coin_from: str,
    coin_to: str,
) -> float | None:
    """
    Try to fetch the actual trading pair rate from the exchange using conservative execution prices.
    
    When trading FROM coin_from TO coin_to:
    - We're selling coin_from (receive BID price)
    - We're buying coin_to (pay ASK price)
    
    Uses conservative pricing: bid when selling, ask when buying.
    This gives realistic (pessimistic) profit estimates that account for bid-ask spread.
    
    Returns the rate (units of coin_to per 1 unit of coin_from) or None if not available.
    """
    ex = EXCHANGES.get(ex_name)
    if ex is None:
        return None
    
    # Try both directions
    pairs_to_try = [
        (f"{coin_from}/{coin_to}", False),  # Direct: base=coin_from, quote=coin_to
        (f"{coin_to}/{coin_from}", True),   # Inverted: base=coin_to, quote=coin_from
    ]
    
    for pair, needs_invert in pairs_to_try:
        try:
            ticker = ex.fetch_ticker(pair)
            bid = ticker.get("bid")
            ask = ticker.get("ask")
            
            if not (isinstance(bid, (int, float)) and isinstance(ask, (int, float))):
                continue
            
            # Conservative execution pricing:
            # When trading FROM coin_from TO coin_to:
            # - We sell coin_from: receive BID (lower price, conservative)
            # - We buy coin_to: pay ASK (higher price, conservative)
            #
            # For pair "coin_from/coin_to":
            # - bid = how many coin_to buyers offer for 1 coin_from (we receive this when selling)
            # - ask = how many coin_to sellers want for 1 coin_from (we'd pay this, but we're selling)
            # Since we're selling coin_from, we use BID (what buyers offer)
            #
            # For pair "coin_to/coin_from" (inverted):
            # - bid = how many coin_from buyers offer for 1 coin_to
            # - ask = how many coin_from sellers want for 1 coin_to
            # Since we're buying coin_to, we'd pay ASK, so rate = 1/ask
            
            if needs_invert:
                # Inverted pair: we're buying coin_to, so we pay ASK (higher price)
                # Rate = 1/ask gives us coin_to per coin_from (conservative)
                if ask > 0:
                    return 1.0 / ask
            else:
                # Direct pair: we're selling coin_from, so we receive BID (lower price)
                # Rate = bid gives us coin_to per coin_from (conservative)
                if bid > 0:
                    return bid
        except Exception:
            continue
    
    return None


def _build_trade_edges(
    prices: Dict[NodeId, float],
    use_live_fees: bool = False,
    market_data=None,
) -> Adjacency:
    """
    For each exchange, connect all coins listed there with trade edges.

    Each edge:
        kind = "trade"
        rate = effective multiplicative factor on amount (already includes trading fee)
        cost = -log(rate)
    
    IMPORTANT: 
    - We try to fetch actual trading pair prices first. If not available, we skip
      the edge (the algorithm can still find paths through intermediate pairs).
    - Each edge's rate already includes the trading fee: rate = raw_rate * (1 - taker_fee)
    - When traversing multi-hop paths (e.g., BUSD → USDT → TUSD), fees accumulate
      correctly: you pay the fee on each trade in the sequence.
    """
    adj: Adjacency = defaultdict(list)

    for ex_name in EXCHANGES.keys():
        # collect coins that have a price on this exchange
        coins_here = [c for c in STABLE_COINS if (ex_name, c) in prices]
        if len(coins_here) < 2:
            continue

        # Try to fetch live fees if enabled, otherwise use hardcoded
        taker_fee = get_taker_fee(ex_name) or 0.0
        if use_live_fees:
            ex_obj = EXCHANGES.get(ex_name)
            if ex_obj:
                live_fees = fetch_live_trading_fees(ex_name, ex_obj)
                if live_fees and 'taker' in live_fees:
                    taker_fee = live_fees['taker']

        for i in range(len(coins_here)):
            for j in range(len(coins_here)):
                if i == j:
                    continue

                c_from = coins_here[i]
                c_to = coins_here[j]
                
                # Try to fetch actual trading pair rate first (more accurate)
                actual_rate = _fetch_actual_trading_pair_rate(ex_name, c_from, c_to)
                
                if actual_rate is not None:
                    # Use actual trading pair rate (uses bid/ask correctly)
                    raw_rate = actual_rate
                else:
                    # Skip this edge - no direct trading pair exists
                    # The algorithm can still find paths through intermediate pairs
                    # (e.g., BUSD → USDT → TUSD instead of direct BUSD → TUSD)
                    # This prevents false arbitrage from normalized price fallback
                    continue
                
                effective_rate = raw_rate * (1.0 - taker_fee)

                if effective_rate <= 0:
                    continue

                cost = -math.log(effective_rate)

                from_node: NodeId = (ex_name, c_from)
                to_node: NodeId = (ex_name, c_to)

                adj[from_node].append(
                    {
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
                        "reference_amount_units": None,
                        "chain": None,
                        "transfer_time_sec": 0.0,
                        "uses_actual_pair": actual_rate is not None,  # Flag for debugging
                    }
                )

    return adj



# Default reference notional for backward compatibility
REFERENCE_NOTIONAL_USD: float = 10_000.0  # deprecated: use portfolio_size_usd parameter


def _build_transfer_edges(
    prices: Dict[NodeId, float],
    portfolio_size_usd: float = REFERENCE_NOTIONAL_USD,
    use_live_fees: bool = False,
) -> Adjacency:
    """
    For each coin and pair of exchanges, create transfer edges based on
    WITHDRAWAL_FEES, network gas fees, and chain transfer times.

    Uses actual portfolio size to calculate withdrawal fee impact (not a fixed reference).
    This ensures accurate cost calculations for small portfolios where flat fees dominate.

    Args:
        prices: Dict of (exchange, coin) -> price_usd
        portfolio_size_usd: Actual portfolio size in USD (default: 10,000 for backward compat)
        use_live_fees: If True, attempt to fetch live fees from CCXT (falls back to hardcoded)

    Each edge includes:
        kind  = "transfer"
        rate  = amount multiplier after withdrawal fee and gas fee
        cost  = -log(rate)
        chain = network used for transfer
        withdrawal_fee_units = flat withdrawal fee in coin units
        gas_fee_usd = network gas fee in USD
    """
    adj: Adjacency = defaultdict(list)

    # Precompute which exchanges have each coin priced
    coin_exchanges: Dict[str, List[str]] = {
        coin: [ex for (ex, c) in prices.keys() if c == coin]
        for coin in STABLE_COINS
    }

    for coin in STABLE_COINS:
        ex_list = coin_exchanges.get(coin, [])
        if len(ex_list) < 2:
            continue

        for ex_from in ex_list:
            # withdrawal options for this coin on ex_from
            ex_withdraw_cfg = WITHDRAWAL_FEES.get(ex_from, {}).get(coin)
            if not ex_withdraw_cfg:
                continue

            price_from_usd = prices[(ex_from, coin)]
            # Use actual portfolio size instead of fixed reference
            amount_start_units = portfolio_size_usd / price_from_usd

            for ex_to in ex_list:
                if ex_to == ex_from:
                    continue

                # Optional: require common chains between from/to;
                # for now we intersect chain names if both have entries.
                chains_from = ex_withdraw_cfg
                chains_to = WITHDRAWAL_FEES.get(ex_to, {}).get(coin, {})

                if chains_to:
                    common_chains = set(chains_from.keys()) & set(chains_to.keys())
                else:
                    # if we don't know deposit networks for ex_to, just
                    # assume all chains_from are usable (approximation)
                    common_chains = set(chains_from.keys())

                if not common_chains:
                    continue

                for chain in common_chains:
                    # Get withdrawal fee (try live first if enabled, then fallback to hardcoded)
                    fee_units = chains_from[chain]
                    if use_live_fees:
                        ex_obj = EXCHANGES.get(ex_from)
                        if ex_obj:
                            live_fees = fetch_live_withdrawal_fees(ex_from, ex_obj, coin)
                            if live_fees and chain.upper() in live_fees:
                                fee_units = live_fees[chain.upper()]
                    
                    # Get network gas fee
                    gas_fee_usd = get_network_gas_fee(chain)
                    
                    # Check if portfolio meets minimum threshold for this chain
                    min_threshold = get_min_portfolio_threshold(chain)
                    if portfolio_size_usd < min_threshold:
                        # Skip this chain if portfolio is too small (flat fees would dominate)
                        continue
                    
                    # Calculate total cost: withdrawal fee + gas fee
                    # Withdrawal fee impact (as percentage of portfolio)
                    withdrawal_fee_usd = fee_units * price_from_usd  # Convert coin units to USD
                    total_fee_usd = withdrawal_fee_usd + gas_fee_usd
                    
                    # If total fees exceed portfolio, skip
                    if total_fee_usd >= portfolio_size_usd:
                        continue
                    
                    # Calculate rate after both fees
                    # rate = (portfolio - total_fees) / portfolio = 1 - (total_fees / portfolio)
                    rate = 1.0 - (total_fee_usd / portfolio_size_usd)
                    if rate <= 0:
                        continue

                    cost = -math.log(rate)
                    t_sec = get_chain_time_seconds(chain) or 0.0

                    from_node: NodeId = (ex_from, coin)
                    to_node: NodeId = (ex_to, coin)

                    adj[from_node].append(
                        {
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
                            "reference_amount_units": amount_start_units,
                            "chain": chain,
                            "transfer_time_sec": t_sec,
                        }
                    )

    return adj


def build_graph(
    force_refresh: bool = False,
    portfolio_size_usd: float = REFERENCE_NOTIONAL_USD,
    use_live_fees: bool = False,
    market_data=None,
) -> Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]:
    """
    Build the arbitrage graph.
    
    Uses caching to avoid rebuilding the graph on every call. The cache is valid
    for CACHE_TTL_SEC seconds. Set force_refresh=True to bypass the cache.
    
    Args:
        force_refresh: If True, bypass cache and rebuild graph from scratch.
        portfolio_size_usd: Actual portfolio size in USD. Used for accurate fee calculations.
                           Defaults to REFERENCE_NOTIONAL_USD for backward compatibility.
        use_live_fees: If True, attempt to fetch live fees from CCXT exchanges.
                      Falls back to hardcoded fees if unavailable.
        market_data: Optional MarketDataStore instance. When provided, prices
                     are read from the store instead of calling CCXT, and the
                     graph cache is bypassed (the store IS the cache).
    
    Returns:
        nodes:
            dict[(exchange, coin)] -> {
                "exchange": ...,
                "coin": ...,
                "price_usd": ...,
                "snapshot_ts": ...,
            }

        adj:
            adjacency list mapping node -> list of edge dicts.
    """
    global _CACHED_GRAPH, _CACHE_TIMESTAMP

    # When using the live market data store, always build fresh
    # (the store already caches data from background workers).
    if market_data is None:
        current_time = time.time()
        if (
            not force_refresh
            and _CACHED_GRAPH is not None
            and _CACHE_TIMESTAMP is not None
            and (current_time - _CACHE_TIMESTAMP) < _CACHE_TTL_SEC
        ):
            return _CACHED_GRAPH
    
    # Build fresh graph
    prices, snapshot_ts = fetch_price_snapshot(market_data=market_data)

    # Nodes with metadata (price + snapshot time)
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

    trade_adj = _build_trade_edges(
        prices, use_live_fees=use_live_fees, market_data=market_data,
    )
    transfer_adj = _build_transfer_edges(
        prices,
        portfolio_size_usd=portfolio_size_usd,
        use_live_fees=use_live_fees,
    )

    # merge adjacency lists
    for node, edges in trade_adj.items():
        adj[node].extend(edges)
    for node, edges in transfer_adj.items():
        adj[node].extend(edges)

    # Update cache (only when not using market_data)
    if market_data is None:
        _CACHED_GRAPH = (nodes, adj)
        _CACHE_TIMESTAMP = time.time()

    return nodes, adj


if __name__ == "__main__":
    # Small sanity check: build graph and print basic stats
    nodes, adj = build_graph()
    print(f"Nodes: {len(nodes)}")
    edge_count = sum(len(v) for v in adj.values())
    print(f"Edges: {edge_count}")
