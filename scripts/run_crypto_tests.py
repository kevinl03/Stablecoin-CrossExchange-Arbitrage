"""
Comprehensive test run for crypto + DeFi arbitrage systems.
Outputs detailed trading path information to a results text file.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime
from io import StringIO
from typing import List, Optional

# ── CEX (centralized exchange) system ──
from scripts.crypto_graph import build_graph as build_cex_graph
from scripts.crypto_arbitrage import (
    dijkstra_best_path as cex_dijkstra,
    bellman_ford_crypto as cex_bellman_ford,
    PlanResult,
    _format_path,
)

# ── DEX (decentralized exchange) system ──
from scripts.defi_graph import build_graph as build_dex_graph
from scripts.defi_arbitrage import (
    dijkstra_best_path as dex_dijkstra,
    bellman_ford_defi as dex_bellman_ford,
    _format_path as dex_format_path,
)


class Tee:
    """Write to both stdout and a buffer."""
    def __init__(self):
        self.buf = StringIO()
        self.stdout = sys.stdout

    def write(self, s):
        self.stdout.write(s)
        self.buf.write(s)

    def flush(self):
        self.stdout.flush()

    def getvalue(self):
        return self.buf.getvalue()


def run_tests():
    tee = Tee()
    sys.stdout = tee

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print("=" * 80)
    print(f"  CRYPTO & DeFi ARBITRAGE — COMPREHENSIVE TEST RUN")
    print(f"  Timestamp: {ts}")
    print("=" * 80)

    # ────────────────────────────────────────────────────────
    # PART 1: CEX (Centralized Exchange) Crypto Arbitrage
    # ────────────────────────────────────────────────────────
    print("\n")
    print("█" * 80)
    print("  PART 1: CENTRALIZED EXCHANGE (CEX) ARBITRAGE")
    print("  Exchanges: Binance, Kraken, KuCoin, Bybit, OKX, Gate.io,")
    print("             Bitget, MEXC, HTX, Coinbase, Crypto.com, Phemex")
    print("  Algorithm: Dijkstra (A* with h=0) + Bellman-Ford")
    print("█" * 80)

    cex_scenarios = [
        ("binance", "USDT",  10_000, 5),
        ("binance", "BTC",   50_000, 5),
        ("kraken",  "ETH",   20_000, 5),
        ("coinbase","USDT",  10_000, 5),
        ("okx",     "SOL",    5_000, 5),
        ("binance", "XRP",   15_000, 5),
    ]

    print("\n── Building CEX graph (live data from 12 exchanges via CCXT) ──")
    t0 = time.time()

    for exchange, coin, amount, depth in cex_scenarios:
        start_node = (exchange, coin)
        print(f"\n{'─'*70}")
        print(f"  Dijkstra | Start: {start_node} | Portfolio: ${amount:,.0f} | Max depth: {depth}")
        print(f"{'─'*70}")
        try:
            result = cex_dijkstra(
                start_node=start_node,
                liquid_cash_usd=amount,
                max_depth=depth,
                max_time_sec=1800.0,
            )
            if result:
                print(f"  *** PROFITABLE PATH ***")
                print(_format_path(result))
                print(f"  Search stats: expanded={result.nodes_expanded}, generated={result.nodes_generated}")
            else:
                print("  No profitable path found.")
        except ValueError as e:
            print(f"  Skipped: {e}")

    cex_time = time.time() - t0

    # Bellman-Ford on CEX graph
    print(f"\n{'─'*70}")
    print(f"  Bellman-Ford (negative cycle detection) | Portfolio: $10,000")
    print(f"{'─'*70}")
    bf_results = cex_bellman_ford(liquid_cash_usd=10_000.0)
    if bf_results:
        print(f"  *** {len(bf_results)} CYCLE(S) FOUND ***")
        for i, res in enumerate(bf_results[:5], 1):
            print(f"\n  ── Cycle {i} ──")
            print(_format_path(res))
    else:
        print("  No negative cycles detected.")

    print(f"\n  CEX total runtime: {cex_time:.1f}s")

    # ────────────────────────────────────────────────────────
    # PART 2: DEX (Decentralized Exchange) On-Chain Arbitrage
    # ────────────────────────────────────────────────────────
    print("\n\n")
    print("█" * 80)
    print("  PART 2: DECENTRALIZED EXCHANGE (DEX) ON-CHAIN ARBITRAGE")
    print("  DEXes: Uniswap V3, Curve, Jupiter, Raydium, PancakeSwap, …")
    print("  Chains: Ethereum, Arbitrum, Base, Optimism, Polygon, Solana, Avax, BSC")
    print("  Data: DeFi-Llama (on-chain prices) + Hyperliquid (perp mids)")
    print("  Algorithm: Dijkstra (A* with h=0) + Bellman-Ford")
    print("█" * 80)

    dex_scenarios = [
        ("ethereum", "WETH",  10_000, 6),
        ("arbitrum", "WETH",  25_000, 6),
        ("arbitrum", "WBTC",  50_000, 6),
        ("solana",   "SOL",    5_000, 6),
        ("polygon",  "USDC",  10_000, 6),
        ("ethereum", "WBTC",  30_000, 6),
        ("optimism", "WETH",  15_000, 6),
        ("base",     "WETH",   8_000, 6),
    ]

    print("\n── Building DEX graph (live on-chain prices from DeFi-Llama) ──")
    t0 = time.time()

    for chain, token, amount, depth in dex_scenarios:
        start_node = (chain, token)
        print(f"\n{'─'*70}")
        print(f"  Dijkstra | Start: {start_node} | Portfolio: ${amount:,.0f} | Max depth: {depth}")
        print(f"{'─'*70}")
        try:
            result = dex_dijkstra(
                start_node=start_node,
                liquid_cash_usd=amount,
                max_depth=depth,
                max_time_sec=3600.0,
            )
            if result:
                print(f"  *** PROFITABLE PATH ***")
                print(dex_format_path(result))
                print(f"  Search stats: expanded={result.nodes_expanded}, generated={result.nodes_generated}")
            else:
                print("  No profitable path found.")
        except ValueError as e:
            print(f"  Skipped: {e}")

    dex_time = time.time() - t0

    # Bellman-Ford on DEX graph
    print(f"\n{'─'*70}")
    print(f"  Bellman-Ford (negative cycle detection) | Portfolio: $10,000")
    print(f"{'─'*70}")
    bf_results = dex_bellman_ford(liquid_cash_usd=10_000.0)
    if bf_results:
        print(f"  *** {len(bf_results)} CYCLE(S) FOUND ***")
        for i, res in enumerate(bf_results[:5], 1):
            print(f"\n  ── Cycle {i} ──")
            print(dex_format_path(res))
    else:
        print("  No negative cycles detected.")

    print(f"\n  DEX total runtime: {dex_time:.1f}s")

    # ────────────────────────────────────────────────────────
    # PART 3: Summary
    # ────────────────────────────────────────────────────────
    print("\n\n")
    print("█" * 80)
    print("  SUMMARY")
    print("█" * 80)
    print(f"\n  CEX scenarios tested:  {len(cex_scenarios)}")
    print(f"  DEX scenarios tested:  {len(dex_scenarios)}")
    print(f"  CEX runtime:           {cex_time:.1f}s")
    print(f"  DEX runtime:           {dex_time:.1f}s")
    print(f"  Total runtime:         {cex_time + dex_time:.1f}s")
    print(f"\n  Algorithms used:")
    print(f"    1. Dijkstra (uniform-cost search / A* with h=0)")
    print(f"       - Finds single best-profit path from a start node")
    print(f"       - Optimal: guarantees shortest path in log-cost space")
    print(f"       - Early exit after finding profit + 200-300 iterations")
    print(f"    2. Bellman-Ford")
    print(f"       - Detects ALL negative-weight cycles (arbitrage loops)")
    print(f"       - Finds cycles regardless of starting node")
    print(f"       - O(V*E) complexity")
    print(f"\n  Graph cost model:")
    print(f"    - Edge cost = -log(usd_rate)")
    print(f"    - usd_rate = multiplicative factor on portfolio USD value")
    print(f"    - Includes: trading/swap fees, gas costs, withdrawal/bridge fees")
    print(f"    - Cross-exchange/chain price ratios baked into transfer/bridge edges")
    print(f"    - Negative total cost = profitable cycle (product of rates > 1)")

    # Restore stdout and write file
    sys.stdout = tee.stdout
    output = tee.getvalue()

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"results/crypto_defi_arbitrage_test_{timestamp}.txt"
    with open(filepath, "w") as f:
        f.write(output)

    print(f"\n  Results written to: {filepath}")
    return filepath


if __name__ == "__main__":
    run_tests()
