import ccxt
from math import isnan  # not strictly needed now, but harmless to keep

EXCHANGE_TIMEOUT_MS = 5000

# 1. Exchanges — expanded to 12 for larger graph coverage
#    CCXT Pro (async websocket) features are available via ccxt.pro;
#    here we use the synchronous REST API for snapshot-based experiments.
EXCHANGES = {
    "binance": ccxt.binance({"timeout": EXCHANGE_TIMEOUT_MS}),
    "kraken": ccxt.kraken({"timeout": EXCHANGE_TIMEOUT_MS}),
    "kucoin": ccxt.kucoin({"timeout": EXCHANGE_TIMEOUT_MS}),
    "bybit": ccxt.bybit({"timeout": EXCHANGE_TIMEOUT_MS}),
    "okx": ccxt.okx({"timeout": EXCHANGE_TIMEOUT_MS}),
    "gateio": ccxt.gateio({"timeout": EXCHANGE_TIMEOUT_MS}),
    "bitget": ccxt.bitget({"timeout": EXCHANGE_TIMEOUT_MS}),
    "mexc": ccxt.mexc({"timeout": EXCHANGE_TIMEOUT_MS}),
    "htx": ccxt.htx({"timeout": EXCHANGE_TIMEOUT_MS}),
    "coinbase": ccxt.coinbase({"timeout": EXCHANGE_TIMEOUT_MS}),
    "cryptocom": ccxt.cryptocom({"timeout": EXCHANGE_TIMEOUT_MS}),
    "phemex": ccxt.phemex({"timeout": EXCHANGE_TIMEOUT_MS}),
}

# 2. Top 10 common stablecoins we’ll track
STABLE_COINS = [
    "USDT",
    "USDC",
    "DAI",
    "TUSD",
    "FDUSD",
    "BUSD",
    "PYUSD",
    "USDP",   # Pax Dollar
    "GUSD",   # Gemini Dollar
    # FRAX removed — depegged (~$0.46 as of Apr 2026), no longer a stablecoin
]

# Volatile crypto assets for cross-exchange arb (wider spreads, more opportunity)
VOLATILE_COINS = [
    "BTC", "ETH", "SOL",           # majors
    "DOGE", "XRP", "ADA", "AVAX",  # large caps
    "CRV", "LDO", "UNI", "AAVE",  # DeFi tokens
    "ARB", "OP",                    # L2 tokens
    "PEPE", "WIF",                  # memecoins
]

# All coins combined
ALL_COINS = STABLE_COINS + VOLATILE_COINS

# 3. For each coin+exchange, specify which market symbol to use.
#    Some markets may not exist; we'll skip those gracefully.
#    Expanded to cover all 12 exchanges.
COIN_MARKETS = {
    "USDT": {
        "binance":   "USDC/USDT",   # USDC priced in USDT (invert to get USDT in USD)
        "kraken":    "USDT/USD",    # direct
        "kucoin":    "USDT/USDC",   # USDT priced in USDC
        "bybit":     "USDC/USDT",   # same trick as binance (invert)
        "okx":       "USDC/USDT",   # invert
        "gateio":    "USDC/USDT",   # invert
        "bitget":    "USDC/USDT",   # invert
        "mexc":      "USDC/USDT",   # invert
        "htx":       "USDC/USDT",   # invert
        "coinbase":  None,          # no direct USDT market on Coinbase
        "cryptocom": "USDC/USDT",   # invert
        "phemex":    "USDC/USDT",   # invert
    },
    "USDC": {
        "binance":   "USDC/USDT",
        "kraken":    "USDC/USD",
        "kucoin":    "USDC/USDT",
        "bybit":     "USDC/USDT",
        "okx":       "USDC/USDT",
        "gateio":    "USDC/USDT",
        "bitget":    "USDC/USDT",
        "mexc":      "USDC/USDT",
        "htx":       "USDC/USDT",
        "coinbase":  "USDC/USD",
        "cryptocom": "USDC/USDT",
        "phemex":    "USDC/USDT",
    },
    "DAI": {
        "binance":   "DAI/USDT",
        "kraken":    "DAI/USD",
        "kucoin":    "USDT/DAI",    # USDT priced in DAI -> invert to get DAI in USD
        "bybit":     "DAI/USDT",
        "okx":       "DAI/USDT",
        "gateio":    "DAI/USDT",
        "bitget":    None,
        "mexc":      "DAI/USDT",
        "htx":       "DAI/USDT",
        "coinbase":  None,
        "cryptocom": "DAI/USDT",
        "phemex":    None,
    },
    "TUSD": {
        "binance":   "TUSD/USDT",
        "kraken":    None,
        "kucoin":    "TUSD/USDT",
        "bybit":     "TUSD/USDT",
        "okx":       "TUSD/USDT",
        "gateio":    "TUSD/USDT",
        "bitget":    None,
        "mexc":      "TUSD/USDT",
        "htx":       "TUSD/USDT",
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
    "FDUSD": {
        "binance":   "FDUSD/USDT",
        "kraken":    None,
        "kucoin":    None,
        "bybit":     "FDUSD/USDT",
        "okx":       "FDUSD/USDT",
        "gateio":    "FDUSD/USDT",
        "bitget":    None,
        "mexc":      None,
        "htx":       None,
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
    "BUSD": {
        "binance":   "BUSD/USDT",      # legacy but still sometimes listed
        "kraken":    "BUSD/USD",
        "kucoin":    "BUSD/USDT",
        "bybit":     None,
        "okx":       None,
        "gateio":    "BUSD/USDT",
        "bitget":    None,
        "mexc":      "BUSD/USDT",
        "htx":       None,
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
    "PYUSD": {
        "binance":   None,
        "kraken":    "PYUSD/USD",
        "kucoin":    None,
        "bybit":     None,
        "okx":       None,
        "gateio":    None,
        "bitget":    None,
        "mexc":      None,
        "htx":       None,
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
    "USDP": {
        "binance":   "USDP/USDT",
        "kraken":    None,
        "kucoin":    "USDP/USDT",
        "bybit":     "USDP/USDT",
        "okx":       None,
        "gateio":    "USDP/USDT",
        "bitget":    None,
        "mexc":      "USDP/USDT",
        "htx":       None,
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
    "GUSD": {
        "binance":   "GUSD/USDT",
        "kraken":    "GUSD/USD",
        "kucoin":    None,
        "bybit":     None,
        "okx":       None,
        "gateio":    None,
        "bitget":    None,
        "mexc":      None,
        "htx":       None,
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
    "FRAX": {
        "binance":   "FRAX/USDT",
        "kraken":    "FRAX/USD",
        "kucoin":    "FRAX/USDT",
        "bybit":     "FRAX/USDT",
        "okx":       None,
        "gateio":    "FRAX/USDT",
        "bitget":    None,
        "mexc":      "FRAX/USDT",
        "htx":       None,
        "coinbase":  None,
        "cryptocom": None,
        "phemex":    None,
    },
}

# Auto-generate COIN_MARKETS for volatile assets.
# Most trade as ASSET/USDT on all exchanges; Kraken and Coinbase use /USD.
_VOLATILE_DEFAULTS = {
    ex: "/USDT" for ex in EXCHANGES
}
_VOLATILE_DEFAULTS["kraken"] = "/USD"
_VOLATILE_DEFAULTS["coinbase"] = "/USD"

for _coin in VOLATILE_COINS:
    COIN_MARKETS[_coin] = {
        ex: f"{_coin}{suffix}" for ex, suffix in _VOLATILE_DEFAULTS.items()
    }


def normalize_price_to_usd(coin: str, market: str, mid: float) -> float | None:
    """
    Convert a mid price for the given market into '1 COIN ≈ X USD'.

    Rules:
      - If market is COIN/USD: mid is already USD per COIN.
      - If market is COIN/USDT or COIN/USDC/...: treat quote ≈ 1 USD.
      - Special cases:
          * USDC/USDT used to infer USDT price -> invert.
          * USDT/DAI used to infer DAI price  -> invert.
    """
    base, quote = market.split("/")

    # Direct USD quote
    if quote == "USD" and base == coin:
        return mid  # USD per COIN

    # Coin priced in another stable (approx 1 USD)
    if base == coin and quote in ("USDT", "USDC", "FDUSD", "BUSD", "TUSD",
                                  "PYUSD", "USDP", "GUSD", "FRAX"):
        return mid  # treat quote as ≈ 1 USD

    # Special case: use USDC/USDT to infer USDT price
    if coin == "USDT" and base == "USDC" and quote == "USDT":
        return 1.0 / mid  # USDT in USD (assuming 1 USDC ≈ 1 USD)

    # Special case: KuCoin's USDT/DAI but we want DAI in USD
    # market = "USDT/DAI" => mid = DAI per 1 USDT; if 1 USDT ≈ 1 USD then 1 DAI ≈ 1/mid USD
    if coin == "DAI" and base == "USDT" and quote == "DAI":
        return 1.0 / mid

    # Volatile asset priced in USDT (e.g. BTC/USDT) — quote ≈ 1 USD
    if base == coin and quote == "USDT":
        return mid

    # Otherwise, we don't know how to normalize this pair for this coin
    return None


def main():
    # prices[coin][exchange] = coin_in_usd
    prices: dict[str, dict[str, float]] = {c: {} for c in STABLE_COINS}

    # ========== FETCH & NORMALIZE PRICES ==========
    for coin in STABLE_COINS:
        print(f"\n=== {coin} prices across exchanges ===")
        for ex_name, ex in EXCHANGES.items():
            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                print(f"{ex_name:8} | no market configured")
                continue

            try:
                ticker = ex.fetch_ticker(market)
                bid = ticker.get("bid")
                ask = ticker.get("ask")
                last = ticker.get("last")

                # Handle missing bid/ask/last cleanly
                if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                    mid = (bid + ask) / 2.0
                elif isinstance(last, (int, float)):
                    mid = float(last)
                else:
                    print(f"{ex_name:8} | {market:10} | no recent transactions")
                    continue

                coin_in_usd = normalize_price_to_usd(coin, market, mid)
                if coin_in_usd is None:
                    print(f"{ex_name:8} | {market:10} | cannot normalize")
                    continue

                prices[coin][ex_name] = coin_in_usd
                print(f"{ex_name:8} | {market:10} | mid={mid:.8f} | {coin}≈{coin_in_usd:.8f} USD")

            except Exception as e:
                msg = str(e)
                if "does not have market symbol" in msg or "symbol" in msg.lower():
                    desc = "no market data (symbol not listed)"
                else:
                    desc = f"exchange error: {msg}"
                print(f"{ex_name:8} | {market:10} | {desc}")

    # ========== CROSS-EXCHANGE (SAME COIN) ==========
    print("\n==============================")
    print("Cross-exchange stablecoin diffs")
    print("==============================")

    for coin in STABLE_COINS:
        ex_price = prices[coin]
        if len(ex_price) < 2:
            continue  # need at least two exchanges to compare

        print(f"\n--- {coin} ---")
        names = list(ex_price.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a, b = names[i], names[j]
                pa, pb = ex_price[a], ex_price[b]
                diff_percent = (pb - pa) / pa * 100.0
                print(f"{a:8} -> {b:8} | {pa:.8f} -> {pb:.8f} | diff={diff_percent:+.4f}%")

    # ========== INTRA-EXCHANGE (DIFFERENT COINS) ==========
    print("\n==============================")
    print("Intra-exchange stablecoin conversions")
    print("==============================")

    # For each exchange, compare all pairs of coins that have a price there.
    for ex_name in EXCHANGES.keys():
        # Collect all coins that have a price for this exchange
        coin_prices_here = {
            coin: prices[coin][ex_name]
            for coin in STABLE_COINS
            if ex_name in prices[coin]
        }

        if len(coin_prices_here) < 2:
            continue  # need at least two coins to compare

        print(f"\n--- {ex_name} ---")
        coins_here = list(coin_prices_here.keys())

        for i in range(len(coins_here)):
            for j in range(len(coins_here)):
                if i == j:
                    continue
                c_from = coins_here[i]
                c_to = coins_here[j]
                p_from = coin_prices_here[c_from]  # USD per 1 c_from
                p_to = coin_prices_here[c_to]      # USD per 1 c_to

                # How many units of c_to do you get for 1 unit of c_from?
                # Intuition: value in USD stays ~1, so rate ≈ p_from / p_to
                rate = p_from / p_to
                diff_percent = (rate - 1.0) * 100.0

                print(
                    f"1 {c_from} -> {rate:.6f} {c_to} | "
                    f"spread_vs_1: {diff_percent:+.4f}%"
                )


if __name__ == "__main__":
    main()
