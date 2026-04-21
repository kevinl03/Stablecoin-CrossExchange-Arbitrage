
"""
Heuristic #1: volume / liquidity on a given exchange.

Idea:
  - If we only have (say) a 10 minute window to complete an arbitrage
    cycle, we don't want to rely on a market that barely trades anything.
  - We approximate "volatility" here as *how much the pair is traded*
    (24h volume) on that specific exchange.
  - Higher volume ⇒ orders are more likely to be filled quickly and
    with less slippage.

This module:
  - Fetches 24h volume via CCXT ticker data.
  - Estimates how much volume typically trades in a given time window.
  - Compares that to the user's order notional and produces a score
    in [0, 1] where higher = safer liquidity.
  - Exposes h1(n), a non-negative heuristic cost that penalizes
    illiquid nodes (exchange, coin) given the remaining time window.
"""

from __future__ import annotations # lets the file use flexible type hints without worrying about import order.

from functools import lru_cache
from math import log10
from typing import Optional

# We reuse the exchange objects and market mappings from data.py
from scripts.data import EXCHANGES, COIN_MARKETS



LIQUIDITY_HEURISTIC_WEIGHT: float = 1.0   # λ, can be tuned in experiments
UNKNOWN_LIQUIDITY_PENALTY: float = 5.0    # cost if no volume data is available

# Cache TTL for volume data (60 seconds)
_VOLUME_CACHE_TTL_SEC: float = 60.0
_volume_cache: dict[tuple[str, str], tuple[float, Optional[float]]] = {}  # (exchange, market) -> (timestamp, volume)


def get_24h_quote_volume(
    exchange_name: str,
    market: str,
    market_data=None,
) -> Optional[float]:
    """
    Fetch the 24h quote volume for a specific symbol on an exchange.
    
    Uses caching to avoid repeated API calls for the same market within 60 seconds.

    Args:
        exchange_name: "binance", "kraken", "kucoin", "bybit", ...
        market:        CCXT market symbol, e.g. "USDC/USDT", "USDT/USD"
        market_data:   Optional MarketDataStore; when provided, volume is
                       read from the store instead of calling CCXT.

    Returns:
        float | None:
            - 24h quote volume if available (usually in quote currency).
            - Falls back to baseVolume if quoteVolume is missing.
            - None if we cannot fetch a ticker or volume is missing.
    """
    import time

    if market_data is not None:
        for c, ex_map in COIN_MARKETS.items():
            if ex_map.get(exchange_name) == market:
                vol = market_data.get_volume(exchange_name, c)
                if vol is not None:
                    return vol
                break

    # Check cache first
    cache_key = (exchange_name, market)
    current_time = time.time()
    
    if cache_key in _volume_cache:
        cached_time, cached_volume = _volume_cache[cache_key]
        if (current_time - cached_time) < _VOLUME_CACHE_TTL_SEC:
            return cached_volume
    
    # Cache miss or expired - fetch from API
    ex = EXCHANGES.get(exchange_name)
    if ex is None:
        return None

    try:
        ticker = ex.fetch_ticker(market)
    except Exception:
        # Cache the failure (None) to avoid repeated failed calls
        _volume_cache[cache_key] = (current_time, None)
        return None

    qv = ticker.get("quoteVolume")
    bv = ticker.get("baseVolume")

    volume = None
    if isinstance(qv, (int, float)) and qv > 0: # try quote volume first then fallback to base volume
        volume = float(qv)
    elif isinstance(bv, (int, float)) and bv > 0:
        volume = float(bv)

    # Update cache
    _volume_cache[cache_key] = (current_time, volume)
    return volume


def get_24h_quote_volume_for_coin(
    exchange_name: str,
    coin: str,
    market_data=None,
) -> Optional[float]:
    """
    Convenience helper that uses COIN_MARKETS from data.py.

    Args:
        exchange_name: "binance", "kraken", "kucoin", "bybit", ...
        coin:          "USDT", "USDC", "DAI", ...
        market_data:   Optional MarketDataStore.

    Returns:
        24h quote volume for the configured market of that coin
        on that exchange, or None if no market / volume.
    """
    if market_data is not None:
        vol = market_data.get_volume(exchange_name, coin)
        if vol is not None:
            return vol

    coin_cfg = COIN_MARKETS.get(coin, {})
    market = coin_cfg.get(exchange_name)
    if not market:
        return None

    return get_24h_quote_volume(exchange_name, market)


# Liquidity score based on 24h volume, order size, and window
def estimate_liquidity_score(
    quote_volume_24h: float,
    order_notional_usd: float, # the size of the users order
    time_window_sec: float,
) -> float:
    """
    Turn 24h volume into a 0–1 score based on how big our order is
    relative to typical trading in the time window.

    Intuition:
      - Approximate per-second flow:
            flow_per_sec ≈ quote_volume_24h / (24 * 3600)
      - Expected traded volume in the window:
            vol_window ≈ flow_per_sec * time_window_sec
      - Compare vol_window to our order_notional_usd.

    We define:
        liquidity_ratio = vol_window / order_notional_usd

      - If liquidity_ratio >> 1  ⇒ our order is tiny relative to flow
                                  ⇒ we should fill easily.
      - If liquidity_ratio ~ 1   ⇒ our order is comparable to typical
                                  flow in that window.
      - If liquidity_ratio << 1  ⇒ our order is huge ⇒ risky.

    We then squash log10(liquidity_ratio) into [0, 1] so we get a
    smooth score:

        log10_ratio in [-1, 1] maps to score in [0, 1].
        (< 0.1x typical flow ⇒ score ≈ 0,
         10x typical flow     ⇒ score ≈ 1)

    Args:
        quote_volume_24h: 24h quote volume (in USD-ish units).
        order_notional_usd: our order size (how much value we want to trade).
        time_window_sec:    time window we care about, e.g. 600 for 10 minutes.

    Returns:
        score in [0, 1], where 1 = very liquid, 0 = very illiquid.
    """
    if quote_volume_24h <= 0 or order_notional_usd <= 0 or time_window_sec <= 0:
        return 0.0

    vol_per_sec = quote_volume_24h / (24.0 * 3600.0) # representing volume in seconds based on what was traded that day
    vol_window = vol_per_sec * time_window_sec # time window here is how much volume gets traded within the time window you are working with 

    liquidity_ratio = vol_window / order_notional_usd # comparing window volume with the size of your order

    if liquidity_ratio <= 0:
        return 0.0

    log10_ratio = log10(liquidity_ratio)
    score = (log10_ratio + 1.0) / 2.0 # mathematical trick to get our ratios from [0,1] instead of [-1,1]

    # dealing with edge cases
    if score < 0.0:
        score = 0.0
    elif score > 1.0:
        score = 1.0

    return score

# puts the above functions together 
def estimate_liquidity_score_live(
    exchange_name: str,
    coin: str,
    order_notional_usd: float,
    time_window_sec: float,
    market_data=None,
) -> Optional[float]:
    """
    High-level helper:
      - Uses COIN_MARKETS + CCXT to fetch the 24h volume for `coin`
        on `exchange_name`.
      - Computes the liquidity score for the given order size and window.

    This is what you'll likely call from your path / heuristic code.

    Args:
        market_data: Optional MarketDataStore.

    Example:
        # want to trade 5,000 USDT within a 10-minute window on Binance
        score = estimate_liquidity_score_live(
            "binance", "USDT",
            order_notional_usd=5000,
            time_window_sec=600,
        )

        # score close to 1  => very liquid, safe
        # score close to 0  => illiquid, avoid this route
    """
    vol_24h = get_24h_quote_volume_for_coin(exchange_name, coin, market_data=market_data)
    if vol_24h is None:
        return None

    return estimate_liquidity_score(vol_24h, order_notional_usd, time_window_sec)


def volume_heuristic_cost(
    exchange_name: str,
    coin: str,
    order_notional_usd: float,
    remaining_time_sec: float,
    market_data=None,
) -> float:
    """
    Heuristic h1(n) for node n = (exchange_name, coin).

    This returns a non-negative cost that penalizes being on an
    illiquid market given how much time remains in the arbitrage window.

    Args:
        exchange_name:
            Exchange identifier, e.g. "binance", "kraken".
        coin:
            Stablecoin symbol at this node, e.g. "USDT", "USDC".
        order_notional_usd:
            Current notional size of the trade expressed in USD.
        remaining_time_sec:
            Remaining time (in seconds) within the user's arbitrage
            window from this node until the cycle must be completed.

    Returns:
        h1(n) = λ * (1 - liquidity_score)  in [0, λ],
        or UNKNOWN_LIQUIDITY_PENALTY if volume data is unavailable.

    Usage in A*:
        g(n) = accumulated fee / loss so far.
        h1(n) = volume_heuristic_cost(...)
        f(n) = g(n) + h1(n)
    """
    if remaining_time_sec <= 0:
        # No time left ⇒ effectively impossible, very high penalty.
        return UNKNOWN_LIQUIDITY_PENALTY

    score = estimate_liquidity_score_live(
        exchange_name=exchange_name,
        coin=coin,
        order_notional_usd=order_notional_usd,
        time_window_sec=remaining_time_sec,
        market_data=market_data,
    )

    # If no volume info, treat as very risky.
    if score is None:
        return UNKNOWN_LIQUIDITY_PENALTY

    # Convert [0,1] liquidity score into [0, λ] penalty
    penalty = LIQUIDITY_HEURISTIC_WEIGHT * (1.0 - score)
    return penalty
