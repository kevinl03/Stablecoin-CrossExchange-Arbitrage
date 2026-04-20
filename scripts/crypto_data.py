"""
Crypto arbitrage data layer.

Defines target cryptocurrencies, exchange configuration, and provides
functions for dynamic market discovery and real-time price fetching
using CCXT.

Unlike the stablecoin version (data.py), this module:
  - Tracks volatile cryptocurrencies (BTC, ETH, SOL, etc.) instead of stablecoins
  - Uses dynamic market discovery instead of hardcoded COIN_MARKETS
  - Does not apply a $1 peg tolerance filter
  - Normalizes all prices to USD via USDT/USD quote pairs
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import ccxt

# ────────────────────────────────────────────────────────────
# 1. Exchanges — same 12 as stablecoin version, fresh instances
# ────────────────────────────────────────────────────────────
EXCHANGES: Dict[str, ccxt.Exchange] = {
    "binance":   ccxt.binance(),
    "kraken":    ccxt.kraken(),
    "kucoin":    ccxt.kucoin(),
    "bybit":     ccxt.bybit(),
    "okx":       ccxt.okx(),
    "gateio":    ccxt.gateio(),
    "bitget":    ccxt.bitget(),
    "mexc":      ccxt.mexc(),
    "htx":       ccxt.htx(),
    "coinbase":  ccxt.coinbase(),
    "cryptocom": ccxt.cryptocom(),
    "phemex":    ccxt.phemex(),
}

# ────────────────────────────────────────────────────────────
# 2. Target cryptocurrencies
# ────────────────────────────────────────────────────────────
# Major cryptos likely to show cross-exchange price discrepancies
# during periods of high volatility. USDT/USDC included as anchors
# (entry/exit currency for arbitrage cycles).
CRYPTO_COINS: List[str] = [
    # Mega-cap
    "BTC", "ETH",
    # Large-cap
    "SOL", "XRP", "BNB", "ADA", "DOGE", "AVAX",
    # Mid-cap (higher beta → more volatility → more arb potential)
    "LINK", "DOT", "NEAR", "APT", "SUI", "UNI", "AAVE",
    # Anchor stablecoins (start/end of arb cycles)
    "USDT", "USDC",
]

# Quotes we accept for normalizing prices to USD
_USD_QUOTES = {"USDT", "USD", "USDC", "BUSD", "FDUSD"}

# ────────────────────────────────────────────────────────────
# 3. Market discovery cache
# ────────────────────────────────────────────────────────────
_MARKETS_CACHE: Dict[str, Dict[str, Any]] = {}


def load_exchange_markets(ex_name: str) -> Dict[str, Any]:
    """
    Load and cache the full market structure for an exchange.
    CCXT caches internally too, but we add our own layer for safety.
    """
    if ex_name in _MARKETS_CACHE:
        return _MARKETS_CACHE[ex_name]

    ex_obj = EXCHANGES.get(ex_name)
    if ex_obj is None:
        return {}

    try:
        ex_obj.load_markets()
        _MARKETS_CACHE[ex_name] = ex_obj.markets or {}
    except Exception:
        _MARKETS_CACHE[ex_name] = {}

    return _MARKETS_CACHE[ex_name]


def discover_relevant_pairs(ex_name: str) -> Dict[str, Dict[str, Any]]:
    """
    Find all spot trading pairs on *ex_name* where **both** base and quote
    are in CRYPTO_COINS.

    Returns:
        dict[symbol_string -> market_info]   e.g. {"BTC/USDT": {...}, ...}
    """
    markets = load_exchange_markets(ex_name)
    coin_set = set(CRYPTO_COINS)
    relevant: Dict[str, Dict[str, Any]] = {}

    for symbol, info in markets.items():
        if info.get("type", "spot") != "spot":
            continue
        base = info.get("base", "")
        quote = info.get("quote", "")
        if base in coin_set and quote in coin_set:
            relevant[symbol] = info

    return relevant


# ────────────────────────────────────────────────────────────
# 4. Ticker / price fetching
# ────────────────────────────────────────────────────────────

TickerCache = Dict[str, Dict[str, Any]]           # symbol -> ticker
ExchangeTickers = Dict[str, TickerCache]           # ex_name -> tickers


def fetch_exchange_tickers(ex_name: str) -> TickerCache:
    """
    Fetch tickers for all relevant pairs on one exchange.

    Strategy:
      1. Try batch ``fetch_tickers(symbols)`` (one HTTP call).
      2. Fall back to individual ``fetch_ticker(symbol)`` calls.
    """
    ex_obj = EXCHANGES.get(ex_name)
    if ex_obj is None:
        return {}

    relevant = discover_relevant_pairs(ex_name)
    symbols = list(relevant.keys())
    if not symbols:
        return {}

    tickers: TickerCache = {}

    # Attempt batch fetch
    try:
        batch = ex_obj.fetch_tickers(symbols)
        for sym in symbols:
            if sym in batch:
                tickers[sym] = batch[sym]
        if tickers:
            return tickers
    except Exception:
        pass

    # Fallback: individual fetches
    for sym in symbols:
        try:
            tickers[sym] = ex_obj.fetch_ticker(sym)
        except Exception:
            continue

    return tickers


def fetch_all_tickers() -> ExchangeTickers:
    """
    Fetch tickers from **every** configured exchange.

    Returns:
        dict[ex_name -> dict[symbol -> ticker_dict]]
    """
    all_tickers: ExchangeTickers = {}
    for ex_name in EXCHANGES:
        print(f"  Fetching tickers from {ex_name} …")
        tickers = fetch_exchange_tickers(ex_name)
        all_tickers[ex_name] = tickers
        print(f"    → {len(tickers)} relevant pairs found")
    return all_tickers


NodeId = Tuple[str, str]  # (exchange, coin)


def derive_usd_prices(
    all_tickers: ExchangeTickers,
) -> Tuple[Dict[NodeId, float], float]:
    """
    Derive a USD-normalized price for every (exchange, coin) pair
    from the fetched tickers.

    Heuristic:
      - For USDT / USDC: assume $1.00 if the exchange lists them.
      - For everything else: use the bid from COIN/USDT, COIN/USD,
        or COIN/USDC (in that priority order, first match wins).
        Bid is conservative (what you'd receive when selling).

    Returns:
        (prices, snapshot_ts)
    """
    prices: Dict[NodeId, float] = {}
    snapshot_ts = time.time()

    for ex_name, tickers in all_tickers.items():
        # Determine which coins are present on this exchange at all
        coins_on_exchange: set[str] = set()
        for sym in tickers:
            parts = sym.split("/")
            if len(parts) == 2:
                coins_on_exchange.update(parts)

        # Anchor stablecoins
        for stable in ("USDT", "USDC"):
            if stable in coins_on_exchange:
                prices[(ex_name, stable)] = 1.0

        # Best-effort USD price for each non-stable coin
        best: Dict[str, float] = {}
        quote_priority = ["USDT", "USD", "USDC"]

        for sym, ticker in tickers.items():
            parts = sym.split("/")
            if len(parts) != 2:
                continue
            base, quote = parts

            if base in ("USDT", "USDC"):
                continue  # already handled
            if quote not in _USD_QUOTES:
                continue

            bid = ticker.get("bid")
            ask = ticker.get("ask")
            last = ticker.get("last")

            if isinstance(bid, (int, float)) and bid > 0:
                price = bid
            elif isinstance(last, (int, float)) and last > 0:
                price = float(last)
            else:
                continue

            # Keep highest-priority quote
            current_prio = best.get(base)
            try:
                new_prio = quote_priority.index(quote)
            except ValueError:
                new_prio = len(quote_priority)

            if current_prio is None or new_prio < current_prio:
                prices[(ex_name, base)] = price
                best[base] = new_prio

    return prices, snapshot_ts


# ────────────────────────────────────────────────────────────
# 5. CLI entry-point: quick snapshot & spread report
# ────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  CRYPTO ARBITRAGE — Live Price Snapshot")
    print("=" * 70)

    all_tickers = fetch_all_tickers()
    prices, ts = derive_usd_prices(all_tickers)

    # ── Per-coin price table ──
    for coin in CRYPTO_COINS:
        rows = [
            (ex, prices[(ex, coin)])
            for ex in EXCHANGES
            if (ex, coin) in prices
        ]
        if not rows:
            continue
        print(f"\n─── {coin} ───")
        for ex, p in sorted(rows, key=lambda r: -r[1]):
            print(f"  {ex:12s}  ${p:>12,.4f}")

    # ── Cross-exchange spreads ──
    print("\n" + "=" * 70)
    print("  Cross-Exchange Spreads (same coin, different exchanges)")
    print("=" * 70)

    for coin in CRYPTO_COINS:
        ex_prices = {
            ex: prices[(ex, coin)]
            for ex in EXCHANGES
            if (ex, coin) in prices
        }
        if len(ex_prices) < 2:
            continue

        names = sorted(ex_prices.keys())
        max_spread = 0.0
        best_pair = ("", "")

        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                pa, pb = ex_prices[a], ex_prices[b]
                spread_pct = abs(pb - pa) / min(pa, pb) * 100.0
                if spread_pct > max_spread:
                    max_spread = spread_pct
                    best_pair = (a, b) if pb > pa else (b, a)

        if max_spread > 0.01:
            high_ex, low_ex = best_pair
            print(
                f"  {coin:6s}  spread={max_spread:+.4f}%  "
                f"(high: {high_ex} ${ex_prices[high_ex]:,.4f}  "
                f"low: {low_ex} ${ex_prices[low_ex]:,.4f})"
            )

    # ── Summary stats ──
    print(f"\nTotal (exchange, coin) pairs with prices: {len(prices)}")
    print(f"Total tickers fetched: {sum(len(t) for t in all_tickers.values())}")
    print(f"Snapshot timestamp: {ts:.0f}")


if __name__ == "__main__":
    main()
