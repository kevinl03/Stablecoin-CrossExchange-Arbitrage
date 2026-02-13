"""
Live fee fetcher (CCXT):
- Trading fees: maker/taker (best-effort)
- Withdrawal fees: per-coin, per-network (best-effort)
- Network name normalization
- Simple in-memory TTL cache

Install:
  pip install ccxt

Usage:
  python live_fees.py --exchanges binance kraken kucoin bybit --coins USDT USDC DAI
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import ccxt


# ---------------------------
# Network normalization
# ---------------------------

NETWORK_ALIASES = {
    # Tron
    "TRC20": "TRX",
    "TRON": "TRX",
    "TRX": "TRX",

    # BSC/BEP20
    "BEP20": "BNB",
    "BSC": "BNB",
    "BSC20": "BNB",
    "BNB": "BNB",

    # Ethereum
    "ERC20": "ETH",
    "ETH": "ETH",

    # Polygon
    "POLYGON": "POLYGON",
    "MATIC": "POLYGON",

    # L2s
    "ARBITRUM": "ARB",
    "ARBITRUMONE": "ARB",
    "ARBONE": "ARB",  # KuCoin uses this
    "ARB": "ARB",
    "OPTIMISM": "OP",
    "OP": "OP",
    "BASE": "BASE",

    # Solana
    "SOL": "SOL",
    "SOLANA": "SOL",

    # Avalanche
    "AVAX": "AVAX",
    "AVAXC": "AVAX",  # KuCoin uses this (Avalanche C-Chain)
    "AVALANCHE": "AVAX",

    # Aptos / Sui
    "APT": "APT",
    "APTOS": "APT",
    "SUI": "SUI",

    # TON
    "TON": "TON",
    "TON2": "TON",  # KuCoin variant

    # Other networks (map to themselves or closest match)
    "STATEMINT": "POLYGON",  # Polkadot parachain, treat as Polygon-like
    "KAVAEVM": "AVAX",  # Kava EVM, treat as Avalanche-like
    "ALGO": "ALGO",  # Algorand
    "NEAR": "NEAR",
    "DOT": "DOT",  # Polkadot
    "XTZ": "XTZ",  # Tezos
    "HBAR": "HBAR",  # Hedera
    "XDC": "XDC",
    "KCC": "KCC",  # KuCoin Chain
    "MONAD": "MONAD",
    "NOBLE": "NOBLE",
    "SONIC": "SONIC",
    "PLASMA": "PLASMA",
}

def norm_network(net: str) -> str:
    """Normalize exchange-specific network labels to canonical names."""
    n = (net or "").strip().upper()
    n = n.replace(" ", "").replace("-", "").replace("_", "")
    # common patterns
    if n in ("TRC", "TRC20", "TRON"): n = "TRC20"
    if n in ("ERC", "ERC20"): n = "ERC20"
    if n in ("BEP", "BEP20"): n = "BEP20"
    # final alias map
    return NETWORK_ALIASES.get(n, n)


# ---------------------------
# TTL cache
# ---------------------------

@dataclass
class CacheEntry:
    value: Any
    expires_at: float

class TTLCache:
    def __init__(self, ttl_seconds: int = 600):
        self.ttl = ttl_seconds
        self._store: Dict[str, CacheEntry] = {}

    def get(self, key: str) -> Optional[Any]:
        ent = self._store.get(key)
        if not ent:
            return None
        if time.time() >= ent.expires_at:
            self._store.pop(key, None)
            return None
        return ent.value

    def set(self, key: str, value: Any) -> None:
        self._store[key] = CacheEntry(value=value, expires_at=time.time() + self.ttl)


# ---------------------------
# Fee fetch helpers (CCXT)
# ---------------------------

def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

def fetch_trading_fees(exchange: ccxt.Exchange) -> Dict[str, Optional[float]]:
    """
    Best-effort fetch maker/taker.
    - Some exchanges support fetch_trading_fees() (per market or global).
    - Otherwise use exchange.fees['trading'] as fallback.
    """
    maker = taker = None

    # 1) Try unified method (may be per-symbol or global)
    if exchange.has.get("fetchTradingFees"):
        try:
            fees = exchange.fetch_trading_fees()
            if isinstance(fees, dict) and fees:
                # Some exchanges return dict of markets -> {maker,taker}
                # Some return {maker,taker}
                if "maker" in fees and "taker" in fees:
                    maker = safe_float(fees.get("maker"))
                    taker = safe_float(fees.get("taker"))
                else:
                    # pick a common liquid market if present
                    preferred = ["BTC/USDT", "ETH/USDT", "BTC/USDC", "ETH/USDC"]
                    for sym in preferred:
                        if sym in fees and isinstance(fees[sym], dict):
                            maker = safe_float(fees[sym].get("maker"))
                            taker = safe_float(fees[sym].get("taker"))
                            if maker is not None or taker is not None:
                                break
                    # otherwise: first market entry
                    if maker is None and taker is None:
                        first_sym = next(iter(fees.keys()))
                        if isinstance(fees[first_sym], dict):
                            maker = safe_float(fees[first_sym].get("maker"))
                            taker = safe_float(fees[first_sym].get("taker"))
        except Exception:
            pass

    # 2) Fallback: load markets and read per-market fees
    if (maker is None or taker is None) and exchange.has.get("fetchMarkets"):
        try:
            exchange.load_markets()
            preferred = ["BTC/USDT", "ETH/USDT", "BTC/USDC", "ETH/USDC"]
            for sym in preferred:
                m = exchange.markets.get(sym)
                if isinstance(m, dict):
                    maker = maker if maker is not None else safe_float(m.get("maker"))
                    taker = taker if taker is not None else safe_float(m.get("taker"))
                if maker is not None or taker is not None:
                    break
        except Exception:
            pass

    # 3) Fallback: exchange.fees['trading']
    try:
        trading = getattr(exchange, "fees", {}).get("trading", {})
        maker = maker if maker is not None else safe_float(trading.get("maker"))
        taker = taker if taker is not None else safe_float(trading.get("taker"))
    except Exception:
        pass

    return {"maker": maker, "taker": taker}


def fetch_withdrawal_fees(exchange: ccxt.Exchange, coin: str) -> Dict[str, float]:
    """
    Best-effort fetch withdrawal fees per network for a coin.

    Tries (in order):
      1) fetch_deposit_withdraw_fees([coin]) if supported
      2) fetch_currencies() / exchange.currencies parsing

    Returns: {NETWORK: fee_in_coin_units}
    """
    coin_u = coin.upper()
    out: Dict[str, float] = {}

    # 1) Unified method (best when available)
    if exchange.has.get("fetchDepositWithdrawFees"):
        try:
            fees = exchange.fetch_deposit_withdraw_fees([coin_u])
            # Common shapes vary by exchange; handle a few:
            # fees[coin]['withdraw']['networks'][network]['fee']
            if isinstance(fees, dict) and coin_u in fees:
                info = fees[coin_u]
                withdraw = info.get("withdraw") if isinstance(info, dict) else None
                if isinstance(withdraw, dict):
                    networks = withdraw.get("networks")
                    if isinstance(networks, dict):
                        for net, netinfo in networks.items():
                            if isinstance(netinfo, dict):
                                f = safe_float(netinfo.get("fee"))
                                if f is not None:
                                    out[norm_network(net)] = f
        except Exception:
            pass

    if out:
        return out

    # 2) Currencies parsing (often works even when unified method doesn't)
    try:
        if exchange.has.get("fetchCurrencies"):
            exchange.fetch_currencies()
        else:
            # still attempt load_markets; some exchanges populate currencies there
            if exchange.has.get("fetchMarkets"):
                exchange.load_markets()

        currencies = getattr(exchange, "currencies", None)
        if isinstance(currencies, dict) and coin_u in currencies:
            cinfo = currencies[coin_u]
            # Typical shape:
            # currencies[coin]['networks'][network]['fee'] or ['withdrawFee']
            networks = cinfo.get("networks") if isinstance(cinfo, dict) else None
            if isinstance(networks, dict):
                for net, netinfo in networks.items():
                    if isinstance(netinfo, dict):
                        f = safe_float(netinfo.get("fee"))
                        if f is None:
                            f = safe_float(netinfo.get("withdrawFee"))
                        if f is not None:
                            out[norm_network(net)] = f
            else:
                # Sometimes a flat withdrawFee exists
                f = safe_float(cinfo.get("withdrawFee")) if isinstance(cinfo, dict) else None
                if f is not None:
                    out["UNKNOWN"] = f
    except Exception:
        pass

    return out


# ---------------------------
# Main
# ---------------------------

def make_exchange(exchange_id: str, api_key: str | None, api_secret: str | None) -> ccxt.Exchange:
    if not hasattr(ccxt, exchange_id):
        raise ValueError(f"Unknown exchange id: {exchange_id}")

    cls = getattr(ccxt, exchange_id)
    params: Dict[str, Any] = {
        "enableRateLimit": True,
        "timeout": 30000,
    }
    # Optional auth (some endpoints require it for withdrawal info)
    if api_key and api_secret:
        params["apiKey"] = api_key
        params["secret"] = api_secret

    return cls(params)


def main() -> None:
    ap = argparse.ArgumentParser(
        description="Fetch live trading and withdrawal fees from cryptocurrency exchanges using CCXT",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Fetch fees from all default exchanges and coins
  python live_fees.py

  # Fetch from specific exchanges
  python live_fees.py --exchanges binance kraken

  # Fetch specific coins
  python live_fees.py --coins USDT USDC DAI

  # Pretty print output
  python live_fees.py --pretty

  # With API keys (for exchanges that require auth)
  python live_fees.py --api-key YOUR_KEY --api-secret YOUR_SECRET
        """
    )
    ap.add_argument(
        "--exchanges", 
        nargs="+", 
        default=["binance", "kraken", "kucoin", "bybit"],
        help="CCXT exchange ids (default: binance kraken kucoin bybit)"
    )
    ap.add_argument(
        "--coins", 
        nargs="+", 
        default=["USDT", "USDC", "DAI"],
        help="Coins to fetch withdrawal fees for (default: USDT USDC DAI)"
    )
    ap.add_argument("--cache-ttl", type=int, default=600, help="Cache TTL seconds (default: 600)")
    ap.add_argument("--api-key", default=None, help="Optional API key (if needed)")
    ap.add_argument("--api-secret", default=None, help="Optional API secret (if needed)")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print JSON output")
    args = ap.parse_args()

    cache = TTLCache(ttl_seconds=args.cache_ttl)
    results: Dict[str, Any] = {}

    for ex_id in args.exchanges:
        ex = make_exchange(ex_id, args.api_key, args.api_secret)

        ex_key = ex_id.lower()
        results[ex_key] = {"trading": {}, "withdrawal": {}}

        # --- trading fees ---
        tkey = f"{ex_key}:trading"
        trading = cache.get(tkey)
        if trading is None:
            trading = fetch_trading_fees(ex)
            cache.set(tkey, trading)
        results[ex_key]["trading"] = trading

        # --- withdrawal fees ---
        for coin in args.coins:
            wkey = f"{ex_key}:withdraw:{coin.upper()}"
            wfees = cache.get(wkey)
            if wfees is None:
                wfees = fetch_withdrawal_fees(ex, coin)
                cache.set(wkey, wfees)
            results[ex_key]["withdrawal"][coin.upper()] = wfees

        try:
            ex.close()
        except Exception:
            pass

    # Debug: ensure we always output something
    if not results:
        print("{}", file=sys.stderr)
        results = {"error": "No results collected"}
    
    if args.pretty:
        print(json.dumps(results, indent=2, sort_keys=True))
    else:
        print(json.dumps(results))

if __name__ == "__main__":
    main()
