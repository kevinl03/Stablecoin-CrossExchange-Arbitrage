

"""
Heuristic #2: order-book depth / slippage estimation.

Idea:
  - Volume tells us how much trades, but not the shape of the order book.
  - A market can have high 24h volume but thin order book depth.
  - If we try to market buy/sell a large order, we might move the price
    significantly, eating into our profit.

This module:
  - Fetches order book via CCXT fetch_order_book().
  - Simulates walking the book with a given order size.
  - Computes VWAP vs mid-price to estimate slippage in bps.
  - Exposes h2(n), a non-negative heuristic cost that penalizes
    markets with high expected slippage for our order size.
"""

from __future__ import annotations

import time
from typing import Optional, Tuple

# We reuse the exchange objects and market mappings from data.py
from scripts.data import EXCHANGES, COIN_MARKETS


SLIPPAGE_HEURISTIC_WEIGHT: float = 0.5  # w_slip, can be tuned
SLIPPAGE_THRESHOLD_BPS: float = 10.0    # 0.10% = acceptable slippage
UNKNOWN_SLIPPAGE_PENALTY: float = 50.0  # cost if no order book data

# Cache TTL for order book data (30 seconds - order books change more frequently)
_ORDERBOOK_CACHE_TTL_SEC: float = 30.0
_orderbook_cache: dict[tuple[str, str], tuple[float, Optional[dict]]] = {}  # (exchange, market) -> (timestamp, orderbook)



def fetch_order_book(
    exchange_name: str,
    market: str,
    limit: int = 20,
    market_data=None,
) -> Optional[dict]:
    """
    Fetch the order book for a specific symbol on an exchange.
    
    Uses caching to avoid repeated API calls for the same market within 30 seconds.

    Args:
        exchange_name: "binance", "kraken", "kucoin", "bybit", ...
        market:        CCXT market symbol, e.g. "USDC/USDT", "USDT/USD"
        limit:         Number of price levels to fetch (default: 20)
        market_data:   Optional MarketDataStore; when provided, the order book
                       is read from the store instead of calling CCXT.

    Returns:
        Order book dict with 'bids' and 'asks' lists, or None if error.
        Each bid/ask is [price, amount].
    """
    if market_data is not None:
        for c, ex_map in COIN_MARKETS.items():
            if ex_map.get(exchange_name) == market:
                ob = market_data.get_order_book(exchange_name, c)
                if ob is not None:
                    return ob
                break

    # Check cache first
    cache_key = (exchange_name, market)
    current_time = time.time()
    
    if cache_key in _orderbook_cache:
        cached_time, cached_orderbook = _orderbook_cache[cache_key]
        if (current_time - cached_time) < _ORDERBOOK_CACHE_TTL_SEC:
            return cached_orderbook
    
    # Cache miss or expired - fetch from API
    ex = EXCHANGES.get(exchange_name)
    if ex is None:
        return None

    try:
        orderbook = ex.fetch_order_book(market, limit=limit)
        # Update cache
        _orderbook_cache[cache_key] = (current_time, orderbook)
        return orderbook
    except Exception:
        # Cache the failure (None) to avoid repeated failed calls
        _orderbook_cache[cache_key] = (current_time, None)
        return None


def fetch_order_book_for_coin(
    exchange_name: str,
    coin: str,
    limit: int = 20,
    market_data=None,
) -> Optional[dict]:
    """
    Convenience helper that uses COIN_MARKETS from data.py.

    Args:
        exchange_name: "binance", "kraken", "kucoin", "bybit", ...
        coin:          "USDT", "USDC", "DAI", ...
        limit:         Number of price levels to fetch
        market_data:   Optional MarketDataStore.

    Returns:
        Order book for the configured market of that coin
        on that exchange, or None if no market / order book.
    """
    if market_data is not None:
        ob = market_data.get_order_book(exchange_name, coin)
        if ob is not None:
            return ob

    coin_cfg = COIN_MARKETS.get(coin, {})
    market = coin_cfg.get(exchange_name)
    if not market:
        return None

    return fetch_order_book(exchange_name, market, limit=limit)


def walk_order_book(
    orderbook: dict,
    order_size_base: float,
    side: str,  # "buy" or "sell"
) -> Tuple[float, float]:
    """
    Simulate executing an order by walking the order book.

    Args:
        orderbook:     Order book dict with 'bids' and 'asks' lists.
        order_size_base: Order size in base currency (e.g., USDT amount).
        side:          "buy" (walk asks) or "sell" (walk bids).

    Returns:
        Tuple of (total_cost_quote, vwap_price)
        - total_cost_quote: Total quote currency needed/received.
        - vwap_price: Volume-weighted average price.
    """
    if side == "buy":
        levels = orderbook.get("asks", [])
    else:  # sell
        levels = orderbook.get("bids", [])

    if not levels:
        return (0.0, 0.0)

    remaining = order_size_base
    total_cost_quote = 0.0

    for level in levels:
        if remaining <= 0:
            break

        # Handle both [price, amount] and [price, amount, timestamp] formats
        if len(level) >= 2:
            price = float(level[0])
            amount = float(level[1])
        else:
            continue

        fill_amount = min(remaining, amount)
        cost = fill_amount * price
        total_cost_quote += cost
        remaining -= fill_amount

    if order_size_base > 0:
        vwap = total_cost_quote / order_size_base
    else:
        vwap = 0.0

    return (total_cost_quote, vwap)


def compute_slippage_bps(
    orderbook: dict,
    order_size_base: float,
    side: str,
) -> Optional[float]:
    """
    Compute slippage in basis points (bps) for a given order.

    Args:
        orderbook:     Order book dict with 'bids' and 'asks' lists.
        order_size_base: Order size in base currency.
        side:          "buy" or "sell".

    Returns:
        Slippage in basis points (bps), or None if cannot compute.
        Positive = worse (higher slippage), 0 = perfect execution.
    """
    if not orderbook or order_size_base <= 0:
        return None

    # Get mid-price
    bids = orderbook.get("bids", [])
    asks = orderbook.get("asks", [])

    if not bids or not asks:
        return None

    # Handle both [price, amount] and [price, amount, timestamp] formats
    best_bid = float(bids[0][0]) if bids and len(bids[0]) >= 1 else 0.0
    best_ask = float(asks[0][0]) if asks and len(asks[0]) >= 1 else 0.0

    if best_bid <= 0 or best_ask <= 0:
        return None

    mid_price = (best_bid + best_ask) / 2.0

    # Walk the book
    _, vwap = walk_order_book(orderbook, order_size_base, side)

    if vwap <= 0:
        return None

    # Compute slippage
    if side == "buy":
        # Buying: we pay more than mid-price
        slippage_pct = ((vwap - mid_price) / mid_price) * 100.0
    else:  # sell
        # Selling: we receive less than mid-price
        slippage_pct = ((mid_price - vwap) / mid_price) * 100.0

    # Convert to basis points (1% = 100 bps)
    slippage_bps = slippage_pct * 100.0

    return slippage_bps


def estimate_slippage_for_coin(
    exchange_name: str,
    coin: str,
    order_size_usd: float,
    side: str = "buy",
    market_data=None,
) -> Optional[float]:
    """
    High-level helper to estimate slippage for a coin on an exchange.

    Args:
        exchange_name: Exchange identifier, e.g. "binance", "kraken".
        coin:          Stablecoin symbol, e.g. "USDT", "USDC".
        order_size_usd: Order size in USD.
        side:          "buy" or "sell" (default: "buy").
        market_data:   Optional MarketDataStore.

    Returns:
        Slippage in basis points (bps), or None if cannot compute.
    """
    orderbook = fetch_order_book_for_coin(exchange_name, coin, market_data=market_data)
    if orderbook is None:
        return None

    order_size_base = order_size_usd

    return compute_slippage_bps(orderbook, order_size_base, side)


def slippage_heuristic_cost(
    exchange_name: str,
    coin: str,
    order_size_usd: float,
    side: str = "buy",
    market_data=None,
) -> float:
    """
    Heuristic h2(n) for node n = (exchange_name, coin).

    This returns a non-negative cost that penalizes markets with
    high expected slippage for the given order size.

    Args:
        exchange_name:
            Exchange identifier, e.g. "binance", "kraken".
        coin:
            Stablecoin symbol at this node, e.g. "USDT", "USDC".
        order_size_usd:
            Order size in USD.
        side:
            "buy" or "sell" (default: "buy").

    Returns:
        h2(n) = w_slip * max(0, slippage_bps - threshold_bps)
        or UNKNOWN_SLIPPAGE_PENALTY if order book data is unavailable.

    Usage in A*:
        g(n) = accumulated fee / loss so far.
        h1(n) = volume_heuristic_cost(...)  (from h1_vol.py)
        h2(n) = slippage_heuristic_cost(...)
        f(n) = g(n) + h1(n) + h2(n)
    """
    slippage_bps = estimate_slippage_for_coin(
        exchange_name=exchange_name,
        coin=coin,
        order_size_usd=order_size_usd,
        side=side,
        market_data=market_data,
    )

    # If no order book info, treat as very risky.
    if slippage_bps is None:
        return UNKNOWN_SLIPPAGE_PENALTY

    # Only penalize slippage above threshold
    excess_slippage = max(0.0, slippage_bps - SLIPPAGE_THRESHOLD_BPS)

    # Convert to cost: w_slip * excess_slippage
    penalty = SLIPPAGE_HEURISTIC_WEIGHT * excess_slippage

    return penalty

