"""
Multi-asset opportunity scanner: compare cross-exchange arb potential across
different asset classes using live data from 12 CEX exchanges.

Scans: BTC, ETH, SOL, XRP, DOGE, AVAX, LINK, MATIC, ARB, OP, UNI, AAVE
+ stablecoins (baseline) + funding rates on perps.

Outputs a ranked comparison of which assets have the best arb economics.

Usage:
    python -m experiments.scan_opportunities
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import ccxt

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fees import TRADING_FEES_TAKER

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Assets to scan, grouped by category
ASSET_CLASSES = {
    "stablecoins": ["USDT", "USDC", "DAI"],
    "majors": ["BTC", "ETH", "SOL"],
    "large_caps": ["XRP", "DOGE", "ADA", "AVAX", "LINK"],
    "defi_tokens": ["UNI", "AAVE", "MKR", "CRV", "LDO"],
    "l2_tokens": ["ARB", "OP", "MATIC", "IMX"],
    "memecoins": ["DOGE", "SHIB", "PEPE", "WIF", "BONK"],
}

# Exchanges (public, no API key needed for tickers)
EXCHANGE_IDS = [
    "binance", "kraken", "kucoin", "bybit", "okx",
    "gateio", "bitget", "mexc", "htx", "phemex",
]

# Perp symbols for funding rate scan
PERP_ASSETS = ["BTC", "ETH", "SOL", "XRP", "DOGE", "AVAX", "ARB", "OP",
               "LINK", "UNI", "AAVE", "PEPE", "WIF", "BONK"]


@dataclass
class AssetOpportunity:
    asset: str
    category: str
    num_exchanges: int
    price_usd: float
    spread_max_bps: float       # max cross-exchange spread
    spread_mean_bps: float      # avg pairwise spread
    spread_std_bps: float       # std of pairwise spreads
    best_buy_exchange: str
    best_sell_exchange: str
    avg_fee_bps: float          # avg round-trip taker fee for the best pair
    net_spread_bps: float       # max spread minus fees
    volume_proxy: float         # sum of 24h volumes
    funding_rate_max_abs: float # max |funding rate| seen across exchanges
    funding_arb_bps: float      # max funding spread between exchanges


def create_exchanges() -> Dict[str, ccxt.Exchange]:
    exs = {}
    for eid in EXCHANGE_IDS:
        try:
            cls = getattr(ccxt, eid)
            exs[eid] = cls({"timeout": 8000, "enableRateLimit": True})
        except Exception:
            pass
    return exs


def scan_asset_tickers(
    exchanges: Dict[str, ccxt.Exchange],
    asset: str,
) -> Dict[str, Dict]:
    """Fetch ticker for asset/USDT (or asset/USD) across all exchanges."""
    results = {}
    # Try both USDT and USD quote
    symbols_to_try = [f"{asset}/USDT", f"{asset}/USD"]
    if asset in ("USDT", "USDC", "DAI"):
        symbols_to_try = [f"{asset}/USD", f"{asset}/USDT", f"USDC/USDT"]
        if asset == "USDT":
            symbols_to_try = ["USDT/USD", "USDC/USDT"]
        elif asset == "USDC":
            symbols_to_try = ["USDC/USD", "USDC/USDT"]
        elif asset == "DAI":
            symbols_to_try = ["DAI/USD", "DAI/USDT"]

    for ex_name, ex in exchanges.items():
        for sym in symbols_to_try:
            try:
                ticker = ex.fetch_ticker(sym)
                if ticker and ticker.get("last"):
                    results[ex_name] = {
                        "symbol": sym,
                        "bid": ticker.get("bid"),
                        "ask": ticker.get("ask"),
                        "last": ticker["last"],
                        "mid": (ticker.get("bid", 0) + ticker.get("ask", 0)) / 2
                               if ticker.get("bid") and ticker.get("ask") else ticker["last"],
                        "volume_24h": ticker.get("quoteVolume") or ticker.get("baseVolume", 0),
                    }
                    break
            except Exception:
                continue
    return results


def scan_funding_rates(
    exchanges: Dict[str, ccxt.Exchange],
    asset: str,
) -> Dict[str, float]:
    """Fetch current funding rate for asset perp across exchanges."""
    results = {}
    sym = f"{asset}/USDT:USDT"
    for ex_name, ex in exchanges.items():
        if not ex.has.get("fetchFundingRate"):
            continue
        try:
            fr = ex.fetch_funding_rate(sym)
            if fr and fr.get("fundingRate") is not None:
                results[ex_name] = fr["fundingRate"]
        except Exception:
            continue
    return results


def analyze_asset(
    asset: str,
    category: str,
    tickers: Dict[str, Dict],
    funding: Dict[str, float],
) -> Optional[AssetOpportunity]:
    """Compute arb opportunity metrics for a single asset."""
    if len(tickers) < 2:
        return None

    prices = {ex: t["mid"] for ex, t in tickers.items() if t["mid"] > 0}
    if len(prices) < 2:
        return None

    ex_names = list(prices.keys())
    price_vals = list(prices.values())
    avg_price = sum(price_vals) / len(price_vals)

    # Pairwise spreads
    pairwise_bps = []
    best_spread = 0
    best_buy = ""
    best_sell = ""
    for i in range(len(ex_names)):
        for j in range(i + 1, len(ex_names)):
            p1, p2 = prices[ex_names[i]], prices[ex_names[j]]
            mid = (p1 + p2) / 2
            spread_bps = abs(p1 - p2) / mid * 10_000
            pairwise_bps.append(spread_bps)
            if spread_bps > best_spread:
                best_spread = spread_bps
                if p1 < p2:
                    best_buy, best_sell = ex_names[i], ex_names[j]
                else:
                    best_buy, best_sell = ex_names[j], ex_names[i]

    if not pairwise_bps:
        return None

    # Fee for the best pair
    fee1 = TRADING_FEES_TAKER.get(best_buy, 0.001)
    fee2 = TRADING_FEES_TAKER.get(best_sell, 0.001)
    avg_fee_bps = (fee1 + fee2) * 10_000

    # Funding rate analysis
    fr_values = list(funding.values()) if funding else []
    max_abs_fr = max(abs(f) for f in fr_values) * 10_000 if fr_values else 0
    # Funding arb = max spread between exchanges' funding rates
    if len(fr_values) >= 2:
        funding_arb = (max(fr_values) - min(fr_values)) * 10_000
    else:
        funding_arb = 0

    total_vol = sum(t.get("volume_24h", 0) or 0 for t in tickers.values())

    import numpy as np
    return AssetOpportunity(
        asset=asset,
        category=category,
        num_exchanges=len(tickers),
        price_usd=avg_price,
        spread_max_bps=best_spread,
        spread_mean_bps=float(np.mean(pairwise_bps)),
        spread_std_bps=float(np.std(pairwise_bps)),
        best_buy_exchange=best_buy,
        best_sell_exchange=best_sell,
        avg_fee_bps=avg_fee_bps,
        net_spread_bps=best_spread - avg_fee_bps,
        volume_proxy=total_vol,
        funding_rate_max_abs=max_abs_fr,
        funding_arb_bps=funding_arb,
    )


def main():
    import numpy as np

    print("=" * 90)
    print("  MULTI-ASSET OPPORTUNITY SCANNER")
    print("  Scanning live cross-exchange spreads and funding rates")
    print("=" * 90)

    exchanges = create_exchanges()
    print(f"\n  Exchanges: {', '.join(exchanges.keys())}")

    # Flatten unique assets
    all_assets = []
    asset_category = {}
    for cat, assets in ASSET_CLASSES.items():
        for a in assets:
            if a not in asset_category:
                asset_category[a] = cat
                all_assets.append(a)

    print(f"  Assets to scan: {len(all_assets)}")
    print()

    results: List[AssetOpportunity] = []

    for i, asset in enumerate(all_assets, 1):
        cat = asset_category[asset]
        print(f"  [{i:>2}/{len(all_assets)}] {asset:<6} ({cat})...", end="", flush=True)

        tickers = scan_asset_tickers(exchanges, asset)
        funding = {}
        if asset in PERP_ASSETS:
            funding = scan_funding_rates(exchanges, asset)

        opp = analyze_asset(asset, cat, tickers, funding)
        if opp:
            results.append(opp)
            sign = "+" if opp.net_spread_bps > 0 else ""
            fr_str = f"  FR={opp.funding_rate_max_abs:.1f}bps" if opp.funding_rate_max_abs > 0 else ""
            print(f" {opp.num_exchanges} exs, spread={opp.spread_max_bps:.1f}bps, "
                  f"fee={opp.avg_fee_bps:.0f}bps, net={sign}{opp.net_spread_bps:.1f}bps{fr_str}")
        else:
            print(f" insufficient data ({len(tickers)} exchanges)")

    # Sort by net spread
    results.sort(key=lambda x: x.net_spread_bps, reverse=True)

    # === CROSS-EXCHANGE SPOT ARB RANKING ===
    print(f"\n{'=' * 90}")
    print(f"  CROSS-EXCHANGE SPOT ARB RANKING (by net spread after fees)")
    print(f"{'=' * 90}\n")

    print(f"  {'#':<3} {'Asset':<7} {'Category':<13} {'Exs':>4} {'MaxSpread':>10} "
          f"{'Fee':>7} {'Net':>8} {'Buy':>10} {'Sell':>10} {'Vol24h':>12}")
    print("  " + "-" * 88)

    for rank, r in enumerate(results, 1):
        vol_str = f"${r.volume_proxy/1e6:.0f}M" if r.volume_proxy > 1e6 else f"${r.volume_proxy/1e3:.0f}K"
        sign = "+" if r.net_spread_bps > 0 else ""
        marker = " ✓" if r.net_spread_bps > 0 else ""
        print(f"  {rank:<3} {r.asset:<7} {r.category:<13} {r.num_exchanges:>4} "
              f"{r.spread_max_bps:>9.1f}  {r.avg_fee_bps:>6.0f}  {sign}{r.net_spread_bps:>6.1f} "
              f"{r.best_buy_exchange:>10} {r.best_sell_exchange:>10} {vol_str:>12}{marker}")

    # === FUNDING RATE ARB RANKING ===
    fr_results = [r for r in results if r.funding_rate_max_abs > 0]
    fr_results.sort(key=lambda x: x.funding_arb_bps, reverse=True)

    if fr_results:
        print(f"\n{'=' * 90}")
        print(f"  FUNDING RATE ARB RANKING (cross-exchange funding spread)")
        print(f"{'=' * 90}\n")

        print(f"  {'#':<3} {'Asset':<7} {'MaxFR(bps)':>11} {'FRSpread':>9} "
              f"{'Annualized':>11} {'Category':<13}")
        print("  " + "-" * 60)

        for rank, r in enumerate(fr_results[:15], 1):
            # Funding every 8h = 3x/day = 1095x/year
            annual = r.funding_arb_bps * 3 * 365
            print(f"  {rank:<3} {r.asset:<7} {r.funding_rate_max_abs:>10.1f}  "
                  f"{r.funding_arb_bps:>8.1f}  {annual:>10.0f}%  {r.category:<13}")

    # === CATEGORY SUMMARY ===
    print(f"\n{'=' * 90}")
    print(f"  CATEGORY SUMMARY")
    print(f"{'=' * 90}\n")

    categories = {}
    for r in results:
        categories.setdefault(r.category, []).append(r)

    print(f"  {'Category':<15} {'Assets':>7} {'AvgSpread':>10} {'AvgFee':>8} "
          f"{'AvgNet':>8} {'BestAsset':<8} {'BestNet':>8}")
    print("  " + "-" * 70)

    cat_summary = []
    for cat, items in categories.items():
        avg_spread = np.mean([r.spread_max_bps for r in items])
        avg_fee = np.mean([r.avg_fee_bps for r in items])
        avg_net = np.mean([r.net_spread_bps for r in items])
        best = max(items, key=lambda x: x.net_spread_bps)
        cat_summary.append((cat, len(items), avg_spread, avg_fee, avg_net, best))

    cat_summary.sort(key=lambda x: x[4], reverse=True)
    for cat, n, avg_s, avg_f, avg_n, best in cat_summary:
        sign = "+" if avg_n > 0 else ""
        bsign = "+" if best.net_spread_bps > 0 else ""
        print(f"  {cat:<15} {n:>7} {avg_s:>9.1f}  {avg_f:>7.0f}  "
              f"{sign}{avg_n:>6.1f}  {best.asset:<8} {bsign}{best.net_spread_bps:>6.1f}")

    # === RECOMMENDATIONS ===
    print(f"\n{'=' * 90}")
    print(f"  RECOMMENDATIONS")
    print(f"{'=' * 90}\n")

    profitable_spot = [r for r in results if r.net_spread_bps > 0]
    if profitable_spot:
        print(f"  SPOT ARB: {len(profitable_spot)} assets show positive net spread right now:")
        for r in profitable_spot[:5]:
            print(f"    {r.asset}: buy {r.best_buy_exchange} → sell {r.best_sell_exchange} "
                  f"= +{r.net_spread_bps:.1f} bps net")
    else:
        print(f"  SPOT ARB: No assets show positive net spread right now (normal for calm markets)")

    if fr_results:
        top_fr = fr_results[0]
        annual = top_fr.funding_arb_bps * 3 * 365
        print(f"\n  FUNDING ARB: {top_fr.asset} has {top_fr.funding_arb_bps:.1f} bps funding spread "
              f"(~{annual:.0f}% annualized)")

    # Overall verdict
    all_nets = [r.net_spread_bps for r in results]
    avg_net = np.mean(all_nets) if all_nets else 0
    best_overall = results[0] if results else None

    print(f"\n  VERDICT:")
    if best_overall and best_overall.net_spread_bps > 5:
        print(f"    → {best_overall.asset} cross-exchange arb looks viable at "
              f"+{best_overall.net_spread_bps:.1f} bps net")
    elif fr_results and fr_results[0].funding_arb_bps > 5:
        print(f"    → Funding rate arb on {fr_results[0].asset} is the best opportunity")
    else:
        print(f"    → CEX arb margins are thin across all assets in current conditions")
        print(f"    → Consider: DEX-CEX arb, options vol arb, or event-driven strategies")

    # Save raw results
    out_path = Path(__file__).resolve().parent.parent / "data" / "opportunity_scan.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scan_data = {
        "scan_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "results": [
            {
                "asset": r.asset, "category": r.category,
                "num_exchanges": r.num_exchanges, "price_usd": r.price_usd,
                "spread_max_bps": r.spread_max_bps, "spread_mean_bps": r.spread_mean_bps,
                "net_spread_bps": r.net_spread_bps, "avg_fee_bps": r.avg_fee_bps,
                "best_buy": r.best_buy_exchange, "best_sell": r.best_sell_exchange,
                "funding_rate_max_abs_bps": r.funding_rate_max_abs,
                "funding_arb_bps": r.funding_arb_bps,
                "volume_24h": r.volume_proxy,
            }
            for r in results
        ],
    }
    with open(out_path, "w") as f:
        json.dump(scan_data, f, indent=2)
    print(f"\n  Raw data saved to {out_path}")


if __name__ == "__main__":
    main()
