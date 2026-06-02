#!/usr/bin/env python3
"""
DEX Data Collector — Cross-DEX price + liquidity snapshots via DexScreener API.

Collects periodic snapshots of DEX pool prices, liquidity, and volume for the
same volatile assets tracked by the CEX collector. Enables CEX-vs-DEX spread
analysis.

Usage:
    python experiments/collect_dex_data.py --interval 120 --hours 2
    python experiments/collect_dex_data.py --interval 60 --hours 4 --min-liquidity 50000
    python experiments/collect_dex_data.py --resume data/dex/20260602_220000
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError, HTTPError

# ── Token contract addresses on major chains ──────────────────────────────────
# Each token maps to {chain: address} for DexScreener lookups.
# Only includes chains where the token has meaningful DEX liquidity.
TOKEN_ADDRESSES = {
    "BTC": {
        # WBTC on Ethereum, BTC on other chains via wrapped versions
        "ethereum": "0x2260FAC5E5542a773Aa44fBCfeDf7C193bc2C599",  # WBTC
        "arbitrum": "0x2f2a2543B76A4166549F7aaB2e75Bef0aefC5B0f",  # WBTC
    },
    "ETH": {
        "ethereum": "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2",  # WETH
        "arbitrum": "0x82aF49447D8a07e3bd95BD0d56f35241523fBab1",  # WETH
        "base": "0x4200000000000000000000000000000000000006",       # WETH
    },
    "SOL": {
        "solana": "So11111111111111111111111111111111111111112",     # native SOL
    },
    "DOGE": {
        # DOGE doesn't have major DEX pools — skip or use bridged version
    },
    "XRP": {
        # XRP doesn't have major DEX pools on EVM chains
    },
    "ADA": {
        # ADA DEX pools are on Cardano DEXes (Minswap, SundaeSwap)
        # DexScreener doesn't cover Cardano well — skip
    },
    "AVAX": {
        "avalanche": "0xB31f66AA3C1e785363F0875A1B74E27b85FD66c7",  # WAVAX
    },
    "CRV": {
        "ethereum": "0xD533a949740bb3306d119CC777fa900bA034cd52",
        "arbitrum": "0x11cDb42B0EB46D95f990BeDD4695A6e3fA034978",
    },
    "LDO": {
        "ethereum": "0x5A98FcBEA516Cf06857215779Fd812CA3beF1B32",
        "arbitrum": "0x13Ad51ed4F1B7e9Dc168d8a00cB3f4dDD85EfA60",
    },
    "UNI": {
        "ethereum": "0x1f9840a85d5aF5bf1D1762F925BDADdC4201F984",
        "arbitrum": "0xFa7F8980b0f1E64A2062791cc3b0871572f1F7f0",
        "base": "0xc3De830EA07524a0761646a6a4e4be0e114a3C83",
    },
    "AAVE": {
        "ethereum": "0x7Fc66500c84A76Ad7e9c93437bFc5Ac33E2DDaE9",
        "arbitrum": "0xba5DdD1f9d7F570dc94a51479a000E3BCE967196",
    },
    "ARB": {
        "arbitrum": "0x912CE59144191C1204E64559FE8253a0e49E6548",
    },
    "OP": {
        "optimism": "0x4200000000000000000000000000000000000042",
    },
    "PEPE": {
        "ethereum": "0x6982508145454Ce325dDbE47a25d4ec3d2311933",
        "arbitrum": "0x25d887Ce7a35172C62FeBFD67a1856F20FaEbB00",
        "base": "0xB0EFaB39b4E720781c24d0cE37A6D6C3b7EAf466",
    },
    "WIF": {
        "solana": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm",
    },
}

# Which DEXes we care about (filter noisy low-liquidity pools)
MAJOR_DEXES = {
    "uniswap", "uniswap_v3", "uniswap_v2",
    "sushiswap", "sushiswap_v3",
    "curve",
    "balancer", "balancer_v2",
    "pancakeswap", "pancakeswap_v3", "pancakeswap_v2",
    "raydium", "raydium_clmm", "raydium_cp",
    "orca", "orca_whirlpool",
    "jupiter",
    "aerodrome", "aerodrome_v2", "aerodrome_slipstream",
    "camelot", "camelot_v3",
    "trader_joe", "trader_joe_v2", "trader_joe_v2.1",
    "velodrome", "velodrome_v2", "velodrome_slipstream",
}

# DexScreener API config
DEXSCREENER_BASE = "https://api.dexscreener.com"
REQUEST_DELAY = 0.25  # 300 req/min = 5 req/s, be conservative


# ── JSONL Writer (same pattern as CEX collector) ─────────────────────────────

class DataWriter:
    """Crash-safe JSONL writer with immediate flushing."""

    def __init__(self, output_dir: str):
        self._dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        self._files = {}

    def write(self, stream: str, record: dict):
        if stream not in self._files:
            path = os.path.join(self._dir, f"{stream}.jsonl")
            self._files[stream] = open(path, "a", encoding="utf-8")
        line = json.dumps(record, default=str)
        self._files[stream].write(line + "\n")
        self._files[stream].flush()

    def close(self):
        for f in self._files.values():
            f.close()


# ── DexScreener API Client ───────────────────────────────────────────────────

def _api_get(path: str) -> dict | list | None:
    """GET from DexScreener API with error handling."""
    url = f"{DEXSCREENER_BASE}{path}"
    req = Request(url, headers={"Accept": "application/json", "User-Agent": "StatArbCollector/1.0"})
    try:
        with urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except (URLError, HTTPError, json.JSONDecodeError, TimeoutError) as e:
        print(f"    [WARN] DexScreener API error: {e}", file=sys.stderr)
        return None


def fetch_dex_pools(token: str, chain: str, address: str, min_liquidity: float = 10000) -> list[dict]:
    """Fetch DEX pools for a token on a specific chain."""
    data = _api_get(f"/token-pairs/v1/{chain}/{address}")
    time.sleep(REQUEST_DELAY)

    if not data or not isinstance(data, list):
        return []

    pools = []
    for pair in data:
        dex_id = (pair.get("dexId") or "").lower()
        price_usd = pair.get("priceUsd")
        liquidity = pair.get("liquidity") or {}
        liq_usd = liquidity.get("usd") or 0

        # Filter: must have price, be a known DEX, and meet liquidity minimum
        if not price_usd:
            continue
        if liq_usd < min_liquidity:
            continue
        # Allow any DEX but tag whether it's "major"
        is_major = any(m in dex_id for m in MAJOR_DEXES)

        base = pair.get("baseToken") or {}
        quote = pair.get("quoteToken") or {}

        # Only include pools where our token is the base token
        # (avoids inverted prices from quote-side pools)
        base_sym = (base.get("symbol") or "").upper()
        if base_sym != token and base_sym != f"W{token}":
            # For wrapped tokens: WETH=ETH, WBTC=BTC, WAVAX=AVAX, WSOL=SOL
            if not (token == "BTC" and base_sym == "WBTC") and \
               not (token == "ETH" and base_sym == "WETH") and \
               not (token == "AVAX" and base_sym == "WAVAX") and \
               not (token == "SOL" and base_sym in ("SOL", "WSOL")):
                continue

        pools.append({
            "token": token,
            "chain": chain,
            "dex": pair.get("dexId", "unknown"),
            "pair_address": pair.get("pairAddress", ""),
            "base_symbol": base.get("symbol", ""),
            "quote_symbol": quote.get("symbol", ""),
            "price_usd": float(price_usd),
            "price_native": pair.get("priceNative", ""),
            "liquidity_usd": liq_usd,
            "liquidity_base": liquidity.get("base", 0),
            "liquidity_quote": liquidity.get("quote", 0),
            "volume_24h": (pair.get("volume") or {}).get("h24", 0),
            "volume_6h": (pair.get("volume") or {}).get("h6", 0),
            "volume_1h": (pair.get("volume") or {}).get("h1", 0),
            "txns_24h_buys": (pair.get("txns") or {}).get("h24", {}).get("buys", 0),
            "txns_24h_sells": (pair.get("txns") or {}).get("h24", {}).get("sells", 0),
            "price_change_24h": (pair.get("priceChange") or {}).get("h24", 0),
            "price_change_1h": (pair.get("priceChange") or {}).get("h1", 0),
            "fdv": pair.get("fdv"),
            "market_cap": pair.get("marketCap"),
            "is_major_dex": is_major,
            "labels": pair.get("labels", []),
            "url": pair.get("url", ""),
        })

    return pools


def compute_dex_spread_matrix(all_pools: list[dict]) -> list[dict]:
    """Compute cross-DEX and cross-chain spread for each token."""
    from collections import defaultdict
    by_token = defaultdict(list)
    for p in all_pools:
        by_token[p["token"]].append(p)

    spreads = []
    for token, pools in by_token.items():
        if len(pools) < 2:
            continue
        prices = [(p["price_usd"], f"{p['dex']}:{p['chain']}", p["liquidity_usd"]) for p in pools]
        prices.sort(key=lambda x: x[0])

        low_price, low_venue, low_liq = prices[0]
        high_price, high_venue, high_liq = prices[-1]

        if low_price <= 0:
            continue

        spread_bps = (high_price - low_price) / low_price * 10000

        spreads.append({
            "token": token,
            "n_pools": len(pools),
            "low_price": low_price,
            "low_venue": low_venue,
            "low_liquidity_usd": low_liq,
            "high_price": high_price,
            "high_venue": high_venue,
            "high_liquidity_usd": high_liq,
            "spread_bps": round(spread_bps, 2),
        })

    spreads.sort(key=lambda x: x["spread_bps"], reverse=True)
    return spreads


# ── State management (crash recovery) ────────────────────────────────────────

def _save_state(output_dir: str, state: dict):
    path = os.path.join(output_dir, "_state.json")
    with open(path, "w") as f:
        json.dump(state, f, default=str)


def _load_state(output_dir: str) -> dict | None:
    path = os.path.join(output_dir, "_state.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


# ── Sleep prevention (Windows) ────────────────────────────────────────────────

def _prevent_sleep():
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)
        print("  [POWER] Windows sleep inhibited for this process.")
    except Exception:
        pass

def _allow_sleep():
    try:
        import ctypes
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)
    except Exception:
        pass


# ── Main collector loop ──────────────────────────────────────────────────────

def collect_snapshot(writer: DataWriter, snapshot_idx: int, ts: str,
                     min_liquidity: float) -> dict:
    """Collect one DEX snapshot for all tokens."""
    all_pools = []
    token_count = 0
    pool_count = 0

    for token, chains in TOKEN_ADDRESSES.items():
        if not chains:
            continue
        token_count += 1
        for chain, address in chains.items():
            pools = fetch_dex_pools(token, chain, address, min_liquidity)
            for pool in pools:
                pool["snapshot"] = snapshot_idx
                pool["timestamp"] = ts
                writer.write("dex_pools", pool)
            all_pools.extend(pools)
            pool_count += len(pools)

    # Compute cross-DEX spreads
    spreads = compute_dex_spread_matrix(all_pools)
    for s in spreads:
        s["snapshot"] = snapshot_idx
        s["timestamp"] = ts
        writer.write("dex_spreads", s)

    return {
        "tokens": token_count,
        "pools": pool_count,
        "spreads": len(spreads),
    }


def main():
    parser = argparse.ArgumentParser(description="DEX Data Collector (DexScreener API)")
    parser.add_argument("--interval", type=int, default=120,
                        help="Seconds between snapshots (default: 120)")
    parser.add_argument("--hours", type=float, default=2.0,
                        help="Collection duration in hours (default: 2)")
    parser.add_argument("--min-liquidity", type=float, default=10000,
                        help="Min pool liquidity in USD to include (default: 10000)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Custom output directory")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from a previous run directory")
    args = parser.parse_args()

    # Output directory
    if args.resume:
        output_dir = args.resume
        state = _load_state(output_dir)
        if state:
            start_snapshot = state.get("last_snapshot", 0) + 1
            start_time_str = state.get("start_time")
            start_time = datetime.fromisoformat(start_time_str) if start_time_str else datetime.now(timezone.utc)
            elapsed = (datetime.now(timezone.utc) - start_time).total_seconds()
            remaining_hours = max(0, args.hours - elapsed / 3600)
            print(f"  [RESUME] Resuming from snapshot {start_snapshot}, {remaining_hours:.1f}h remaining")
        else:
            start_snapshot = 0
            start_time = datetime.now(timezone.utc)
            remaining_hours = args.hours
    else:
        ts_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_dir = args.output_dir or os.path.join("data", "dex", ts_str)
        start_snapshot = 0
        start_time = datetime.now(timezone.utc)
        remaining_hours = args.hours

    total_snapshots = int(remaining_hours * 3600 / args.interval)
    if total_snapshots <= 0:
        print("No snapshots remaining.")
        return

    writer = DataWriter(output_dir)

    # Save run config
    config = {
        "start_time": start_time.isoformat(),
        "interval_s": args.interval,
        "hours": args.hours,
        "min_liquidity": args.min_liquidity,
        "tokens": [t for t, c in TOKEN_ADDRESSES.items() if c],
        "api": "DexScreener",
        "snapshot": 0,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    writer.write("run_config", config)

    tokens_with_addresses = [t for t, c in TOKEN_ADDRESSES.items() if c]
    chains_count = sum(len(c) for c in TOKEN_ADDRESSES.values() if c)

    print(f"=== DEX Data Collector (DexScreener) ===")
    print(f"  Output: {os.path.abspath(output_dir)}")
    print(f"  Tokens: {len(tokens_with_addresses)} ({', '.join(tokens_with_addresses)})")
    print(f"  Chain lookups: {chains_count}")
    print(f"  Interval: {args.interval}s | Duration: {remaining_hours:.1f}h")
    print(f"  Expected snapshots: ~{total_snapshots}")
    print(f"  Min liquidity: ${args.min_liquidity:,.0f}")
    print(f"  Press Ctrl+C to stop gracefully.\n")

    _prevent_sleep()

    try:
        for i in range(total_snapshots):
            snap_idx = start_snapshot + i
            ts = datetime.now(timezone.utc).isoformat()
            t0 = time.time()

            stats = collect_snapshot(writer, snap_idx, ts, args.min_liquidity)

            elapsed = time.time() - t0

            print(f"  [{snap_idx+1:>4}/{start_snapshot + total_snapshots}] "
                  f"tok={stats['tokens']} pools={stats['pools']} "
                  f"spreads={stats['spreads']} ({elapsed:.1f}s)")

            # Save state for crash recovery
            _save_state(output_dir, {
                "last_snapshot": snap_idx,
                "start_time": start_time.isoformat(),
                "min_liquidity": args.min_liquidity,
            })

            # Sleep until next interval
            sleep_time = max(0, args.interval - elapsed)
            if sleep_time > 0 and i < total_snapshots - 1:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n  [STOPPED] Graceful shutdown.")
    finally:
        _allow_sleep()
        writer.close()
        print(f"\n=== Collection complete ===")
        print(f"  Snapshots: {snap_idx + 1 if 'snap_idx' in dir() else 0}")
        print(f"  Output: {os.path.abspath(output_dir)}")


if __name__ == "__main__":
    main()
