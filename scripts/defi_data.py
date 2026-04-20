"""
DeFi / DEX arbitrage data layer.

Fetches on-chain token prices from DeFi-Llama's coins API, which
aggregates real-time pricing from decentralised exchanges (Uniswap,
Curve, Jupiter, Raydium, etc.) across multiple blockchains.

Also pulls mid-market prices from Hyperliquid's perpetual DEX for
comparison.

Nodes in the arbitrage graph are (chain, token_symbol).
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any, Dict, List, Optional, Tuple

import requests

# ────────────────────────────────────────────────────────────
# 1.  Chain configuration
# ────────────────────────────────────────────────────────────

CHAINS: List[str] = [
    "ethereum",
    "arbitrum",
    "base",
    "optimism",
    "polygon",
    "solana",
    "avax",
    "bsc",
]

# ────────────────────────────────────────────────────────────
# 2.  Token registry — contract addresses per chain
#     DeFi-Llama key format:  "chain:address"
# ────────────────────────────────────────────────────────────

# Each entry: { chain: address }
# None = token doesn't exist on that chain
TOKEN_REGISTRY: Dict[str, Dict[str, Optional[str]]] = {
    "WETH": {
        "ethereum":  "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",
        "arbitrum":  "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",
        "base":      "0x4200000000000000000000000000000000000006",
        "optimism":  "0x4200000000000000000000000000000000000006",
        "polygon":   "0x7ceB23fD6bC0adD59E62ac25578270cFf1b9f619",
    },
    "WBTC": {
        "ethereum":  "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",
        "arbitrum":  "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",
        "polygon":   "0x1BFD67037B42Cf73acF2047067bd4F2C47D9BfD6",
        "optimism":  "0x68f180fcCe6836688e9084f035309E29Bf0A2095",
        "avax":      "0x50b7545627a5162F82A992c33b87aDc75187B218",
    },
    "USDC": {
        "ethereum":  "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48",
        "arbitrum":  "0xaf88d065e77c8cC2239327C5EDb3A432268e5831",
        "base":      "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913",
        "optimism":  "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85",
        "polygon":   "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359",
        "solana":    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
        "avax":      "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E",
        "bsc":       "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d",
    },
    "USDT": {
        "ethereum":  "0xdAC17F958D2ee523a2206206994597C13D831ec7",
        "arbitrum":  "0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9",
        "optimism":  "0x94b008aA00579c1307B0EF2c499aD98a8ce58e58",
        "polygon":   "0xc2132D05D31c914a87C6611C10748AEb04B58e8F",
        "bsc":       "0x55d398326f99059fF775485246999027B3197955",
        "avax":      "0x9702230A8Ea53601f5cD2dc00fDBc13d4dF4A8c7",
        "solana":    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
    },
    "SOL": {
        "solana":    "So11111111111111111111111111111111111111112",
    },
    "LINK": {
        "ethereum":  "0x514910771AF9Ca656af840dff83E8264EcF986CA",
        "arbitrum":  "0xf97f4df75117a78c1A5a0DBb814Af92458539FB4",
        "polygon":   "0x53E0bca35eC356BD5ddDFebbD1Fc0fD03FaBad39",
        "optimism":  "0x350a791Bfc2C21F9Ed5d10980Dad2e2638ffa7f6",
        "avax":      "0x5947BB275c521040051D82396e4B9d3f7694cD96",
    },
    "UNI": {
        "ethereum":  "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "arbitrum":  "0xFa7F8980b0f1E64A2062791cc3b0871572f1F7f0",
        "polygon":   "0xb33EaAd8d922B1083446DC23f610c2567fB5180f",
        "optimism":  "0x6fd9d7AD17242c41f7131d257212c54A0e816691",
    },
    "AAVE": {
        "ethereum":  "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "arbitrum":  "0xba5DdD1f9d7F570dc94a51479a000E3BCE967196",
        "polygon":   "0xD6DF932A45C0f255f85145f286eA0b292B21C90B",
        "optimism":  "0x76FB31fb4af56892A25e32cFC43De717950c9278",
        "avax":      "0x63a72806098Bd3D9520cC43356dD78afe5D386D9",
    },
    "DAI": {
        "ethereum":  "0x6B175474E89094C44Da98b954EedeAC495271d0F",
        "arbitrum":  "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
        "polygon":   "0x8f3Cf7ad23Cd3CaDbD9735AFf958023239c6A063",
        "optimism":  "0xDA10009cBd5D07dd0CeCc66161FC93D7c9000da1",
    },
    "ARB": {
        "arbitrum":  "0x912CE59144191C1204E64559FE8253a0e49E6548",
    },
    "OP": {
        "optimism":  "0x4200000000000000000000000000000000000042",
    },
    "AVAX": {
        "avax":      "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",
    },
    "BNB": {
        "bsc":       "0xbb4CdB9CBd36B01bD1cBaEBF2De08d9173bc095c",
    },
}

# Tokens we actively track (keys of TOKEN_REGISTRY)
TOKEN_SYMBOLS: List[str] = list(TOKEN_REGISTRY.keys())

NodeId = Tuple[str, str]  # (chain, token_symbol)

# ────────────────────────────────────────────────────────────
# 3.  DeFi-Llama price fetcher
# ────────────────────────────────────────────────────────────

_LLAMA_BASE = "https://coins.llama.fi/prices/current"


def _build_llama_keys() -> Dict[str, NodeId]:
    """
    Build the DeFi-Llama coin keys and map each key back to our
    (chain, symbol) NodeId.

    Returns:
        dict["chain:address" -> (chain, symbol)]
    """
    mapping: Dict[str, NodeId] = {}
    for symbol, chain_addrs in TOKEN_REGISTRY.items():
        for chain, addr in chain_addrs.items():
            if addr is None:
                continue
            key = f"{chain}:{addr}"
            mapping[key] = (chain, symbol)
    return mapping


def fetch_defi_prices() -> Tuple[Dict[NodeId, float], float]:
    """
    Fetch USD prices for every (chain, token) pair from DeFi-Llama.

    Returns:
        prices:     dict[(chain, symbol)] -> price_usd
        timestamp:  unix snapshot time
    """
    key_map = _build_llama_keys()
    all_keys = list(key_map.keys())

    # DeFi-Llama accepts comma-separated keys in URL
    # Batch into chunks of 50 to avoid URL length limits
    prices: Dict[NodeId, float] = {}
    snapshot_ts = time.time()

    for start in range(0, len(all_keys), 50):
        chunk = all_keys[start : start + 50]
        url = _LLAMA_BASE + "/" + ",".join(chunk)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            coins = resp.json().get("coins", {})
        except Exception as exc:
            print(f"  [warn] DeFi-Llama batch failed: {exc}")
            continue

        for llama_key, info in coins.items():
            node = key_map.get(llama_key)
            if node is None:
                continue
            price = info.get("price")
            conf = info.get("confidence", 0)
            if price is not None and price > 0 and conf >= 0.5:
                prices[node] = price

    return prices, snapshot_ts


# ────────────────────────────────────────────────────────────
# 4.  Hyperliquid perpetual mid-prices (supplemental)
# ────────────────────────────────────────────────────────────

_HL_INFO = "https://api.hyperliquid.xyz/info"

# Mapping from Hyperliquid perp symbols to our token symbols
_HL_SYMBOL_MAP = {
    "BTC": "WBTC",
    "ETH": "WETH",
    "SOL": "SOL",
    "AVAX": "AVAX",
    "LINK": "LINK",
    "UNI": "UNI",
    "AAVE": "AAVE",
    "ARB": "ARB",
    "OP": "OP",
}


def fetch_hyperliquid_mids() -> Dict[str, float]:
    """
    Fetch mid-market prices from Hyperliquid's perp DEX.

    Returns:
        dict[our_symbol -> mid_price_usd]
    """
    try:
        resp = requests.post(
            _HL_INFO,
            json={"type": "allMids"},
            timeout=10,
        )
        resp.raise_for_status()
        raw = resp.json()  # dict: HL_symbol -> mid_str
    except Exception:
        return {}

    result: Dict[str, float] = {}
    for hl_sym, our_sym in _HL_SYMBOL_MAP.items():
        mid_str = raw.get(hl_sym)
        if mid_str is not None:
            try:
                result[our_sym] = float(mid_str)
            except ValueError:
                continue
    return result


# ────────────────────────────────────────────────────────────
# 5.  CLI: snapshot & spread report
# ────────────────────────────────────────────────────────────

def main() -> None:
    print("=" * 70)
    print("  DeFi / DEX — Cross-Chain Price Snapshot  (DeFi-Llama)")
    print("=" * 70)

    prices, ts = fetch_defi_prices()
    hl_mids = fetch_hyperliquid_mids()

    # Group by token
    grouped: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for (chain, symbol), price in prices.items():
        grouped[symbol].append((chain, price))

    for symbol in TOKEN_SYMBOLS:
        rows = grouped.get(symbol, [])
        if not rows:
            continue
        rows.sort(key=lambda r: -r[1])
        print(f"\n─── {symbol} ───")
        for chain, p in rows:
            print(f"  {chain:12s}  ${p:>14,.6f}")
        # Show Hyperliquid perp mid for comparison
        hl_price = hl_mids.get(symbol)
        if hl_price is not None:
            print(f"  {'hyperliquid':12s}  ${hl_price:>14,.6f}  (perp mid)")

        if len(rows) >= 2:
            hi_chain, hi_p = rows[0]
            lo_chain, lo_p = rows[-1]
            spread = (hi_p - lo_p) / lo_p * 100.0
            print(
                f"  SPREAD: {spread:+.4f}%  "
                f"(high: {hi_chain} | low: {lo_chain})"
            )

    print(f"\n{'─'*70}")
    print(f"Total (chain, token) pairs: {len(prices)}")
    print(f"Hyperliquid perp mids: {len(hl_mids)}")
    print(f"Snapshot: {ts:.0f}")


if __name__ == "__main__":
    main()
