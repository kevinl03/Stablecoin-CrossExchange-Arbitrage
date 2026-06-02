#!/usr/bin/env python3
"""
Historical backtester for cross-exchange statistical arbitrage.

Runs OU/z-score strategies on 30-day historical OHLCV data (Parquet format)
downloaded by download_historical_ohlcv.py.

Builds cross-exchange spread time series from 1-minute close prices and
simulates mean-reversion trading with realistic fee models.

Usage:
    # Backtest all assets in data/historical/
    python experiments/backtest_historical.py

    # Specific asset
    python experiments/backtest_historical.py --asset CRV

    # Tune parameters
    python experiments/backtest_historical.py --entry-z 1.5 --exit-z 0.3 --window 60

    # Use JSONL data from live collector instead
    python experiments/backtest_historical.py --jsonl data/statarb/20260602_211358
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fees import TRADING_FEES_TAKER


# ── Data Loading ──────────────────────────────────────────────────────────────

def load_parquet_data(data_dir: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Load historical Parquet data into nested dict: {asset: {exchange: DataFrame}}.
    Each DataFrame has columns: timestamp, open, high, low, close, volume, datetime.
    """
    data = {}
    base = Path(data_dir)

    for asset_dir in sorted(base.iterdir()):
        if not asset_dir.is_dir():
            continue
        asset = asset_dir.name
        data[asset] = {}
        for parquet_file in sorted(asset_dir.glob("*.parquet")):
            exchange = parquet_file.stem
            df = pd.read_parquet(parquet_file)
            if not df.empty and "close" in df.columns:
                data[asset][exchange] = df

    return data


def load_jsonl_tickers(data_dir: str) -> Dict[str, Dict[str, pd.DataFrame]]:
    """
    Load JSONL ticker data from the live collector into the same format.
    Returns {asset: {exchange: DataFrame}} with 'timestamp' and 'close' columns.
    """
    ticker_path = Path(data_dir) / "ticker.jsonl"
    if not ticker_path.exists():
        print(f"  Error: {ticker_path} not found")
        return {}

    records = []
    with open(ticker_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") != "ticker" or "error" in rec:
                continue
            price = rec.get("price_usd")
            if price is None:
                continue
            records.append({
                "coin": rec["coin"],
                "exchange": rec["exchange"],
                "timestamp": int(pd.Timestamp(rec["ts"]).timestamp() * 1000),
                "close": price,
                "snapshot_idx": rec.get("snapshot_idx", 0),
            })

    if not records:
        return {}

    df = pd.DataFrame(records)
    data = {}
    for coin in df["coin"].unique():
        coin_df = df[df["coin"] == coin]
        data[coin] = {}
        for exchange in coin_df["exchange"].unique():
            ex_df = coin_df[coin_df["exchange"] == exchange].copy()
            ex_df = ex_df.sort_values("timestamp").reset_index(drop=True)
            data[coin][exchange] = ex_df

    return data


# ── Spread Construction ──────────────────────────────────────────────────────

def build_spread_from_ohlcv(
    df1: pd.DataFrame, df2: pd.DataFrame,
    resample: str = "1min",
) -> pd.DataFrame:
    """
    Build spread time series from two exchange OHLCV DataFrames.
    Aligns on timestamp, computes spread = close1 - close2 in bps.
    """
    # Use timestamp for merging
    s1 = df1[["timestamp", "close"]].rename(columns={"close": "p1"}).drop_duplicates("timestamp")
    s2 = df2[["timestamp", "close"]].rename(columns={"close": "p2"}).drop_duplicates("timestamp")

    merged = pd.merge(s1, s2, on="timestamp", how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged = merged.sort_values("timestamp").reset_index(drop=True)
    mid = (merged["p1"] + merged["p2"]) / 2
    merged["spread"] = merged["p1"] - merged["p2"]
    merged["spread_bps"] = (merged["spread"] / mid) * 10_000
    merged["datetime"] = pd.to_datetime(merged["timestamp"], unit="ms", utc=True)

    return merged


# ── OU Estimation ─────────────────────────────────────────────────────────────

@dataclass
class OUParams:
    mu: float
    theta: float
    sigma: float
    half_life: float  # in data-point units


def estimate_ou_params(spread: np.ndarray, dt: float = 1.0) -> OUParams:
    S = spread[:-1]
    dS = np.diff(spread)

    if len(S) < 5:
        return OUParams(mu=np.mean(spread), theta=0, sigma=np.std(spread), half_life=float("inf"))

    X = np.column_stack([np.ones_like(S), S])
    beta, _, _, _ = np.linalg.lstsq(X, dS, rcond=None)
    a, b = beta

    theta = -b / dt
    mu = a / (theta * dt) if abs(theta) > 1e-10 else np.mean(spread)
    residuals = dS - (a + b * S)
    sigma = np.std(residuals) / np.sqrt(dt) if np.std(residuals) > 0 else 1e-10
    half_life = np.log(2) / theta if theta > 0 else float("inf")

    return OUParams(mu=mu, theta=theta, sigma=sigma, half_life=half_life)


# ── Trading Strategies ────────────────────────────────────────────────────────

@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    direction: str
    entry_spread_bps: float
    exit_spread_bps: float
    pnl_gross_bps: float
    fee_bps: float
    pnl_net_bps: float
    holding_periods: int
    entry_time: str
    exit_time: str


def compute_fees_bps(ex1: str, ex2: str) -> float:
    fee1 = TRADING_FEES_TAKER.get(ex1, 0.001)
    fee2 = TRADING_FEES_TAKER.get(ex2, 0.001)
    return (fee1 + fee2) * 10_000


def run_ou_strategy(
    spread_bps: np.ndarray,
    timestamps: np.ndarray,
    fee_bps: float,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    warmup: int = 60,
    max_holding: int = 1440,  # max holding period (1440 = 1 day of 1min bars)
) -> List[Trade]:
    """OU mean-reversion strategy on spread_bps array."""
    if len(spread_bps) < warmup + 10:
        return []

    ou = estimate_ou_params(spread_bps[:warmup * 2] if len(spread_bps) > warmup * 2 else spread_bps)

    trades = []
    position = None
    entry_idx = 0
    entry_spread = 0.0

    for i in range(warmup, len(spread_bps)):
        s = spread_bps[i]
        z = (s - ou.mu) / ou.sigma if ou.sigma > 1e-10 else 0

        if position is None:
            if z > entry_z:
                position = "short_spread"
                entry_idx = i
                entry_spread = s
            elif z < -entry_z:
                position = "long_spread"
                entry_idx = i
                entry_spread = s
        else:
            should_exit = False
            # Normal exit on mean reversion
            if position == "short_spread" and z < exit_z:
                should_exit = True
            elif position == "long_spread" and z > -exit_z:
                should_exit = True
            # Stop-loss: max holding period
            if (i - entry_idx) >= max_holding:
                should_exit = True

            if should_exit:
                pnl_gross = (entry_spread - s) if position == "short_spread" else (s - entry_spread)
                trades.append(Trade(
                    entry_idx=entry_idx, exit_idx=i,
                    direction=position,
                    entry_spread_bps=entry_spread,
                    exit_spread_bps=s,
                    pnl_gross_bps=pnl_gross,
                    fee_bps=fee_bps,
                    pnl_net_bps=pnl_gross - fee_bps,
                    holding_periods=i - entry_idx,
                    entry_time=str(timestamps[entry_idx]) if entry_idx < len(timestamps) else "",
                    exit_time=str(timestamps[i]) if i < len(timestamps) else "",
                ))
                position = None

    return trades


def run_zscore_strategy(
    spread_bps: np.ndarray,
    timestamps: np.ndarray,
    fee_bps: float,
    window: int = 60,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    max_holding: int = 1440,
) -> List[Trade]:
    """Rolling z-score mean-reversion strategy."""
    if len(spread_bps) < window + 10:
        return []

    trades = []
    position = None
    entry_idx = 0
    entry_spread = 0.0

    for i in range(window, len(spread_bps)):
        lookback = spread_bps[i - window:i]
        mu = np.mean(lookback)
        sigma = np.std(lookback)
        s = spread_bps[i]
        z = (s - mu) / sigma if sigma > 1e-10 else 0

        if position is None:
            if z > entry_z:
                position = "short_spread"
                entry_idx = i
                entry_spread = s
            elif z < -entry_z:
                position = "long_spread"
                entry_idx = i
                entry_spread = s
        else:
            should_exit = False
            if position == "short_spread" and z < exit_z:
                should_exit = True
            elif position == "long_spread" and z > -exit_z:
                should_exit = True
            if (i - entry_idx) >= max_holding:
                should_exit = True

            if should_exit:
                pnl_gross = (entry_spread - s) if position == "short_spread" else (s - entry_spread)
                trades.append(Trade(
                    entry_idx=entry_idx, exit_idx=i,
                    direction=position,
                    entry_spread_bps=entry_spread,
                    exit_spread_bps=s,
                    pnl_gross_bps=pnl_gross,
                    fee_bps=fee_bps,
                    pnl_net_bps=pnl_gross - fee_bps,
                    holding_periods=i - entry_idx,
                    entry_time=str(timestamps[entry_idx]) if entry_idx < len(timestamps) else "",
                    exit_time=str(timestamps[i]) if i < len(timestamps) else "",
                ))
                position = None

    return trades


# ── Results ───────────────────────────────────────────────────────────────────

@dataclass
class PairResult:
    asset: str
    ex1: str
    ex2: str
    model: str
    ou_params: Optional[OUParams]
    trades: List[Trade]
    n_datapoints: int
    spread_mean_bps: float
    spread_std_bps: float
    spread_min_bps: float
    spread_max_bps: float
    # Computed
    n_trades: int = 0
    total_gross_bps: float = 0
    total_fees_bps: float = 0
    total_net_bps: float = 0
    win_rate: float = 0
    sharpe: float = 0
    max_drawdown_bps: float = 0
    avg_holding: float = 0
    profit_factor: float = 0

    def __post_init__(self):
        self.n_trades = len(self.trades)
        if not self.trades:
            return
        pnls = [t.pnl_net_bps for t in self.trades]
        self.total_gross_bps = sum(t.pnl_gross_bps for t in self.trades)
        self.total_fees_bps = sum(t.fee_bps for t in self.trades)
        self.total_net_bps = sum(pnls)
        self.win_rate = sum(1 for p in pnls if p > 0) / len(pnls)
        self.avg_holding = np.mean([t.holding_periods for t in self.trades])

        if len(pnls) > 1 and np.std(pnls) > 0:
            self.sharpe = float(np.mean(pnls) / np.std(pnls))

        # Max drawdown
        cum = np.cumsum(pnls)
        peak = np.maximum.accumulate(cum)
        self.max_drawdown_bps = float(np.max(peak - cum)) if len(cum) > 0 else 0

        # Profit factor
        gains = sum(p for p in pnls if p > 0)
        losses = abs(sum(p for p in pnls if p < 0))
        self.profit_factor = gains / losses if losses > 0 else float("inf") if gains > 0 else 0


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Historical cross-exchange backtester")
    parser.add_argument("--data-dir", type=str, default="data/historical",
                        help="Path to Parquet data directory (default: data/historical)")
    parser.add_argument("--jsonl", type=str, default=None,
                        help="Path to JSONL data directory (from live collector)")
    parser.add_argument("--asset", type=str, default=None,
                        help="Specific asset to backtest (default: all)")
    parser.add_argument("--model", choices=["ou", "zscore", "both"], default="both",
                        help="Strategy model (default: both)")
    parser.add_argument("--entry-z", type=float, default=2.0,
                        help="Z-score entry threshold (default: 2.0)")
    parser.add_argument("--exit-z", type=float, default=0.5,
                        help="Z-score exit threshold (default: 0.5)")
    parser.add_argument("--window", type=int, default=60,
                        help="Rolling window for z-score (default: 60 = 1hr of 1min bars)")
    parser.add_argument("--max-holding", type=int, default=1440,
                        help="Max holding period in bars (default: 1440 = 1 day)")
    parser.add_argument("--top-n", type=int, default=10,
                        help="Top N pairs by spread std to backtest")
    parser.add_argument("--min-datapoints", type=int, default=500,
                        help="Min overlapping datapoints to consider a pair (default: 500)")
    args = parser.parse_args()

    # Load data
    if args.jsonl:
        print(f"Loading JSONL data from {args.jsonl}...")
        data = load_jsonl_tickers(args.jsonl)
    else:
        print(f"Loading Parquet data from {args.data_dir}...")
        data = load_parquet_data(args.data_dir)

    if not data:
        print("No data found.")
        sys.exit(1)

    # Filter to specific asset if requested
    assets = [args.asset] if args.asset else sorted(data.keys())
    assets = [a for a in assets if a in data]

    print(f"  Assets: {', '.join(assets)} ({len(assets)})")
    for asset in assets:
        exchanges = sorted(data[asset].keys())
        rows = {ex: len(data[asset][ex]) for ex in exchanges}
        print(f"    {asset}: {', '.join(f'{ex}({rows[ex]:,})' for ex in exchanges)}")
    print()

    all_results: List[PairResult] = []

    for asset in assets:
        exchanges = sorted(data[asset].keys())
        if len(exchanges) < 2:
            print(f"  {asset}: only {len(exchanges)} exchange(s), skipping")
            continue

        print(f"{'=' * 80}")
        print(f"=== {asset} — {len(exchanges)} exchanges ===\n")

        # Build all exchange pair spreads
        pairs = []
        for i, ex1 in enumerate(exchanges):
            for ex2 in exchanges[i + 1:]:
                spread_df = build_spread_from_ohlcv(data[asset][ex1], data[asset][ex2])
                if len(spread_df) >= args.min_datapoints:
                    pairs.append((ex1, ex2, spread_df))

        if not pairs:
            print(f"  No pairs with >= {args.min_datapoints} overlapping datapoints")
            continue

        # Sort by spread volatility
        pairs.sort(key=lambda x: x[2]["spread_bps"].std(), reverse=True)

        # Spread analysis table
        print(f"  {'Pair':<25} {'Mean':>8} {'Std':>8} {'Min':>8} {'Max':>8} {'Range':>8} {'Points':>8}")
        print(f"  {'-'*25} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8} {'-'*8}")
        for ex1, ex2, sdf in pairs[:args.top_n]:
            s = sdf["spread_bps"]
            print(f"  {ex1}-{ex2:<20} {s.mean():>8.2f} {s.std():>8.2f} "
                  f"{s.min():>8.2f} {s.max():>8.2f} {s.max()-s.min():>8.2f} {len(s):>8,}")
        print()

        # Run strategies
        for ex1, ex2, spread_df in pairs[:args.top_n]:
            spread_bps = spread_df["spread_bps"].values
            timestamps = spread_df["datetime"].values if "datetime" in spread_df.columns else spread_df["timestamp"].values
            fee_bps = compute_fees_bps(ex1, ex2)
            ou = estimate_ou_params(spread_bps)

            if args.model in ("ou", "both"):
                trades = run_ou_strategy(spread_bps, timestamps, fee_bps,
                                         entry_z=args.entry_z, exit_z=args.exit_z,
                                         max_holding=args.max_holding)
                result = PairResult(
                    asset=asset, ex1=ex1, ex2=ex2, model="ou",
                    ou_params=ou, trades=trades, n_datapoints=len(spread_bps),
                    spread_mean_bps=float(np.mean(spread_bps)),
                    spread_std_bps=float(np.std(spread_bps)),
                    spread_min_bps=float(np.min(spread_bps)),
                    spread_max_bps=float(np.max(spread_bps)),
                )
                all_results.append(result)

            if args.model in ("zscore", "both"):
                trades = run_zscore_strategy(spread_bps, timestamps, fee_bps,
                                              window=args.window,
                                              entry_z=args.entry_z, exit_z=args.exit_z,
                                              max_holding=args.max_holding)
                result = PairResult(
                    asset=asset, ex1=ex1, ex2=ex2, model="zscore",
                    ou_params=ou, trades=trades, n_datapoints=len(spread_bps),
                    spread_mean_bps=float(np.mean(spread_bps)),
                    spread_std_bps=float(np.std(spread_bps)),
                    spread_min_bps=float(np.min(spread_bps)),
                    spread_max_bps=float(np.max(spread_bps)),
                )
                all_results.append(result)

    # ── Results table ─────────────────────────────────────────────────────

    print(f"\n{'=' * 120}")
    print(f"=== BACKTEST RESULTS — ALL ASSETS ===\n")

    # Sort by net PnL
    all_results.sort(key=lambda r: r.total_net_bps, reverse=True)

    print(f"  {'Asset':<6} {'Pair':<22} {'Model':<7} {'Trades':>6} {'Gross':>8} {'Fees':>8} "
          f"{'Net':>8} {'Win%':>6} {'Sharpe':>7} {'PF':>6} {'AvgHold':>7} {'MaxDD':>7} {'HL':>6}")
    print(f"  {'-'*6} {'-'*22} {'-'*7} {'-'*6} {'-'*8} {'-'*8} "
          f"{'-'*8} {'-'*6} {'-'*7} {'-'*6} {'-'*7} {'-'*7} {'-'*6}")

    for r in all_results:
        hl = f"{r.ou_params.half_life:.0f}" if r.ou_params and r.ou_params.half_life < 1e6 else "inf"
        pf = f"{r.profit_factor:.2f}" if r.profit_factor < 100 else "inf"
        print(f"  {r.asset:<6} {r.ex1}-{r.ex2:<17} {r.model:<7} {r.n_trades:>6} "
              f"{r.total_gross_bps:>8.1f} {r.total_fees_bps:>8.1f} "
              f"{r.total_net_bps:>8.1f} {r.win_rate:>5.1%} "
              f"{r.sharpe:>7.2f} {pf:>6} {r.avg_holding:>7.0f} "
              f"{r.max_drawdown_bps:>7.1f} {hl:>6}")

    # ── Profitable pairs detail ───────────────────────────────────────────

    profitable = [r for r in all_results if r.total_net_bps > 0]
    unprofitable = [r for r in all_results if r.total_net_bps <= 0 and r.n_trades > 0]

    print(f"\n{'=' * 80}")
    print(f"=== SUMMARY ===\n")
    print(f"  Total pair-models tested: {len(all_results)}")
    print(f"  With trades:              {sum(1 for r in all_results if r.n_trades > 0)}")
    print(f"  Profitable (net > 0):     {len(profitable)}")

    if profitable:
        print(f"\n  Top profitable pairs:")
        for r in profitable[:10]:
            print(f"    {r.asset} {r.ex1}-{r.ex2} ({r.model}): "
                  f"+{r.total_net_bps:.1f} bps net, {r.n_trades} trades, "
                  f"{r.win_rate:.0%} win, Sharpe {r.sharpe:.2f}")

        # Show trade detail for top result
        best = profitable[0]
        if best.trades:
            print(f"\n  {'=' * 70}")
            print(f"  Top pair detail: {best.asset} {best.ex1}-{best.ex2} ({best.model})")
            print(f"    OU params: mu={best.ou_params.mu:.2f} theta={best.ou_params.theta:.4f} "
                  f"sigma={best.ou_params.sigma:.2f} HL={best.ou_params.half_life:.1f}")
            print(f"    Spread: mean={best.spread_mean_bps:.2f} std={best.spread_std_bps:.2f} "
                  f"range=[{best.spread_min_bps:.2f}, {best.spread_max_bps:.2f}]")
            print()

            print(f"    {'#':>3} {'Dir':<14} {'Entry':>8} {'Exit':>8} {'Gross':>7} {'Fee':>7} "
                  f"{'Net':>7} {'Hold':>5} {'Entry Time'}")
            print(f"    {'---':>3} {'-'*14} {'-'*8} {'-'*8} {'-'*7} {'-'*7} {'-'*7} {'-'*5} {'-'*22}")
            for i, t in enumerate(best.trades[:20], 1):
                print(f"    {i:>3} {t.direction:<14} {t.entry_spread_bps:>8.2f} {t.exit_spread_bps:>8.2f} "
                      f"{t.pnl_gross_bps:>7.2f} {t.fee_bps:>7.2f} {t.pnl_net_bps:>7.2f} "
                      f"{t.holding_periods:>5} {str(t.entry_time)[:22]}")
            if len(best.trades) > 20:
                print(f"    ... and {len(best.trades) - 20} more trades")

    else:
        print(f"\n  ⚠  No profitable pairs found.")
        if unprofitable:
            avg_fee = np.mean([r.total_fees_bps / r.n_trades for r in unprofitable if r.n_trades > 0])
            avg_std = np.mean([r.spread_std_bps for r in unprofitable])
            print(f"  Avg fee per trade: {avg_fee:.1f} bps")
            print(f"  Avg spread std:    {avg_std:.2f} bps")
            print(f"  Fee/Std ratio:     {avg_fee/avg_std:.1f}x" if avg_std > 0 else "")

    # Key metrics by asset
    print(f"\n  Per-asset summary:")
    for asset in assets:
        asset_results = [r for r in all_results if r.asset == asset and r.n_trades > 0]
        if not asset_results:
            print(f"    {asset}: no trades triggered")
            continue
        best_net = max(r.total_net_bps for r in asset_results)
        n_profitable = sum(1 for r in asset_results if r.total_net_bps > 0)
        avg_std = np.mean([r.spread_std_bps for r in asset_results])
        print(f"    {asset}: {len(asset_results)} pair-models, {n_profitable} profitable, "
              f"best={best_net:+.1f} bps, avg spread std={avg_std:.2f} bps")

    # Save results to JSON
    results_path = os.path.join(args.jsonl or args.data_dir, "backtest_results.json")
    results_json = [{
        "asset": r.asset, "ex1": r.ex1, "ex2": r.ex2, "model": r.model,
        "n_trades": r.n_trades, "total_net_bps": round(r.total_net_bps, 2),
        "total_gross_bps": round(r.total_gross_bps, 2), "total_fees_bps": round(r.total_fees_bps, 2),
        "win_rate": round(r.win_rate, 3), "sharpe": round(r.sharpe, 3),
        "profit_factor": round(r.profit_factor, 3) if r.profit_factor < 1e6 else None,
        "avg_holding": round(r.avg_holding, 1) if r.avg_holding else 0,
        "max_drawdown_bps": round(r.max_drawdown_bps, 2),
        "spread_std_bps": round(r.spread_std_bps, 2),
        "ou_half_life": round(r.ou_params.half_life, 1) if r.ou_params and r.ou_params.half_life < 1e6 else None,
        "n_datapoints": r.n_datapoints,
    } for r in all_results]

    try:
        with open(results_path, "w") as f:
            json.dump(results_json, f, indent=2)
        print(f"\n  Results saved to: {results_path}")
    except Exception:
        pass


if __name__ == "__main__":
    main()
