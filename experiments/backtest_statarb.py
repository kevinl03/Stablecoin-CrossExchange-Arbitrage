"""
Statistical arbitrage backtester for stablecoin cross-exchange spreads.

Models implemented:
  1. Ornstein-Uhlenbeck (OU) mean-reversion
  2. Cointegration + z-score trading

Loads data from JSONL collection runs and simulates trading with realistic fees.

Usage:
    python -m experiments.backtest_statarb data/statarb/20260602_190651
    python -m experiments.backtest_statarb data/statarb/20260602_190651 --model zscore --entry-z 2.5
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fees import TRADING_FEES_TAKER


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_tickers(data_dir: Path) -> pd.DataFrame:
    """Load ticker JSONL into a DataFrame with columns: ts, exchange, coin, price_usd, bid, ask, mid."""
    path = data_dir / "ticker.jsonl"
    records = []
    with open(path, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if rec.get("type") != "ticker" or "error" in rec:
                continue
            records.append({
                "ts": pd.Timestamp(rec["ts"]),
                "snapshot_idx": rec["snapshot_idx"],
                "exchange": rec["exchange"],
                "coin": rec["coin"],
                "price_usd": rec.get("price_usd"),
                "bid": rec.get("bid"),
                "ask": rec.get("ask"),
                "mid": rec.get("mid"),
                "volume_24h": rec.get("base_volume_24h"),
            })
    df = pd.DataFrame(records)
    df = df.dropna(subset=["price_usd"])
    df = df.sort_values(["ts", "exchange", "coin"]).reset_index(drop=True)
    return df


def load_funding_rates(data_dir: Path) -> pd.DataFrame:
    """Load funding rate JSONL."""
    path = data_dir / "funding_rate.jsonl"
    if not path.exists():
        return pd.DataFrame()
    records = []
    with open(path, "r") as f:
        for line in f:
            rec = json.loads(line.strip())
            if rec.get("type") != "funding_rate":
                continue
            records.append({
                "ts": pd.Timestamp(rec["ts"]),
                "snapshot_idx": rec["snapshot_idx"],
                "exchange": rec["exchange"],
                "symbol": rec["symbol"],
                "funding_rate": rec["funding_rate"],
            })
    return pd.DataFrame(records) if records else pd.DataFrame()


def build_spread_series(tickers: pd.DataFrame, ex1: str, ex2: str, coin: str) -> pd.DataFrame:
    """
    Build a time series of the spread between two exchanges for a given coin.
    spread = price_usd(ex1) - price_usd(ex2)
    Returns DataFrame with columns: ts, snapshot_idx, p1, p2, spread, spread_bps
    """
    t1 = tickers[(tickers["exchange"] == ex1) & (tickers["coin"] == coin)].copy()
    t2 = tickers[(tickers["exchange"] == ex2) & (tickers["coin"] == coin)].copy()

    if t1.empty or t2.empty:
        return pd.DataFrame()

    t1 = t1.set_index("snapshot_idx")[["ts", "price_usd", "bid", "ask"]].rename(
        columns={"price_usd": "p1", "bid": "bid1", "ask": "ask1"}
    )
    t2 = t2.set_index("snapshot_idx")[["price_usd", "bid", "ask"]].rename(
        columns={"price_usd": "p2", "bid": "bid2", "ask": "ask2"}
    )

    merged = t1.join(t2, how="inner")
    if merged.empty:
        return pd.DataFrame()

    merged["spread"] = merged["p1"] - merged["p2"]
    mid = (merged["p1"] + merged["p2"]) / 2
    merged["spread_bps"] = (merged["spread"] / mid) * 10_000
    merged = merged.reset_index()
    return merged


# ---------------------------------------------------------------------------
# Ornstein-Uhlenbeck parameter estimation
# ---------------------------------------------------------------------------

@dataclass
class OUParams:
    mu: float       # long-run mean
    theta: float    # mean-reversion speed
    sigma: float    # volatility
    half_life: float  # time to revert halfway (in snapshot units)


def estimate_ou_params(spread: np.ndarray, dt: float = 1.0) -> OUParams:
    """
    Estimate OU process parameters via OLS regression:
      dS = theta * (mu - S) * dt + sigma * dW
    Using the discrete form: S(t+1) - S(t) = a + b * S(t) + e
    """
    S = spread[:-1]
    dS = np.diff(spread)

    # OLS: dS = a + b * S
    X = np.column_stack([np.ones_like(S), S])
    beta, _, _, _ = np.linalg.lstsq(X, dS, rcond=None)
    a, b = beta

    theta = -b / dt
    mu = a / (theta * dt) if abs(theta) > 1e-10 else np.mean(spread)

    # Residual volatility
    residuals = dS - (a + b * S)
    sigma = np.std(residuals) / np.sqrt(dt)

    half_life = np.log(2) / theta if theta > 0 else float("inf")

    return OUParams(mu=mu, theta=theta, sigma=sigma, half_life=half_life)


# ---------------------------------------------------------------------------
# Trading strategies
# ---------------------------------------------------------------------------

@dataclass
class Trade:
    entry_idx: int
    exit_idx: int
    direction: str       # "long_spread" or "short_spread"
    entry_spread: float
    exit_spread: float
    pnl_gross_bps: float
    fee_bps: float
    pnl_net_bps: float
    entry_ts: str
    exit_ts: str


@dataclass
class BacktestResult:
    pair: str
    model: str
    ou_params: Optional[OUParams]
    trades: List[Trade]
    total_pnl_bps: float
    total_pnl_net_bps: float
    num_trades: int
    win_rate: float
    avg_pnl_bps: float
    max_drawdown_bps: float
    sharpe: float
    spread_mean_bps: float
    spread_std_bps: float


def compute_fees_bps(ex1: str, ex2: str) -> float:
    """Round-trip taker fees in bps for trading on both exchanges."""
    fee1 = TRADING_FEES_TAKER.get(ex1, 0.001)
    fee2 = TRADING_FEES_TAKER.get(ex2, 0.001)
    # Buy on one exchange, sell on the other = 2 taker fees
    return (fee1 + fee2) * 10_000


def run_ou_strategy(
    spread_df: pd.DataFrame,
    ex1: str, ex2: str,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
    warmup: int = 10,
) -> BacktestResult:
    """
    OU mean-reversion strategy:
    - Estimate OU params on all data (in-sample for now)
    - Enter when spread deviates > entry_z standard deviations from mean
    - Exit when spread returns within exit_z standard deviations
    """
    spreads_bps = spread_df["spread_bps"].values

    if len(spreads_bps) < warmup + 5:
        return BacktestResult(
            pair=f"{ex1}-{ex2}", model="ou", ou_params=None,
            trades=[], total_pnl_bps=0, total_pnl_net_bps=0,
            num_trades=0, win_rate=0, avg_pnl_bps=0,
            max_drawdown_bps=0, sharpe=0,
            spread_mean_bps=float(np.mean(spreads_bps)),
            spread_std_bps=float(np.std(spreads_bps)),
        )

    ou = estimate_ou_params(spreads_bps)
    fee_bps = compute_fees_bps(ex1, ex2)

    trades: List[Trade] = []
    position = None  # None, "long_spread", "short_spread"
    entry_idx = 0
    entry_spread = 0.0

    for i in range(warmup, len(spreads_bps)):
        s = spreads_bps[i]
        z = (s - ou.mu) / ou.sigma if ou.sigma > 1e-10 else 0

        if position is None:
            # Enter short spread (spread too high, expect reversion down)
            if z > entry_z:
                position = "short_spread"
                entry_idx = i
                entry_spread = s
            # Enter long spread (spread too low, expect reversion up)
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

            if should_exit:
                if position == "short_spread":
                    pnl_gross = entry_spread - s
                else:
                    pnl_gross = s - entry_spread

                trades.append(Trade(
                    entry_idx=entry_idx, exit_idx=i,
                    direction=position,
                    entry_spread=entry_spread, exit_spread=s,
                    pnl_gross_bps=pnl_gross,
                    fee_bps=fee_bps,
                    pnl_net_bps=pnl_gross - fee_bps,
                    entry_ts=str(spread_df.iloc[entry_idx]["ts"]),
                    exit_ts=str(spread_df.iloc[i]["ts"]),
                ))
                position = None

    return _build_result(f"{ex1}-{ex2}", "ou", ou, trades, spreads_bps)


def run_zscore_strategy(
    spread_df: pd.DataFrame,
    ex1: str, ex2: str,
    window: int = 20,
    entry_z: float = 2.0,
    exit_z: float = 0.5,
) -> BacktestResult:
    """
    Rolling z-score strategy:
    - Compute rolling mean and std of the spread
    - Enter when z-score exceeds threshold
    - Exit when z-score reverts
    """
    spreads_bps = spread_df["spread_bps"].values

    if len(spreads_bps) < window + 5:
        return BacktestResult(
            pair=f"{ex1}-{ex2}", model="zscore", ou_params=None,
            trades=[], total_pnl_bps=0, total_pnl_net_bps=0,
            num_trades=0, win_rate=0, avg_pnl_bps=0,
            max_drawdown_bps=0, sharpe=0,
            spread_mean_bps=float(np.mean(spreads_bps)),
            spread_std_bps=float(np.std(spreads_bps)),
        )

    fee_bps = compute_fees_bps(ex1, ex2)

    trades: List[Trade] = []
    position = None
    entry_idx = 0
    entry_spread = 0.0

    for i in range(window, len(spreads_bps)):
        lookback = spreads_bps[i - window:i]
        mu = np.mean(lookback)
        sigma = np.std(lookback)
        s = spreads_bps[i]
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

            if should_exit:
                if position == "short_spread":
                    pnl_gross = entry_spread - s
                else:
                    pnl_gross = s - entry_spread

                trades.append(Trade(
                    entry_idx=entry_idx, exit_idx=i,
                    direction=position,
                    entry_spread=entry_spread, exit_spread=s,
                    pnl_gross_bps=pnl_gross,
                    fee_bps=fee_bps,
                    pnl_net_bps=pnl_gross - fee_bps,
                    entry_ts=str(spread_df.iloc[entry_idx]["ts"]),
                    exit_ts=str(spread_df.iloc[i]["ts"]),
                ))
                position = None

    ou = estimate_ou_params(spreads_bps)
    return _build_result(f"{ex1}-{ex2}", "zscore", ou, trades, spreads_bps)


def _build_result(
    pair: str, model: str, ou: Optional[OUParams],
    trades: List[Trade], spreads_bps: np.ndarray,
) -> BacktestResult:
    pnl_list = [t.pnl_net_bps for t in trades]
    total_net = sum(pnl_list) if pnl_list else 0
    total_gross = sum(t.pnl_gross_bps for t in trades) if trades else 0
    num_trades = len(trades)
    wins = sum(1 for p in pnl_list if p > 0)
    win_rate = wins / num_trades if num_trades > 0 else 0
    avg_pnl = np.mean(pnl_list) if pnl_list else 0

    # Max drawdown of cumulative PnL
    if pnl_list:
        cum = np.cumsum(pnl_list)
        peak = np.maximum.accumulate(cum)
        drawdowns = peak - cum
        max_dd = float(np.max(drawdowns))
    else:
        max_dd = 0

    # Sharpe (annualized is meaningless for sub-hour data, just use raw)
    sharpe = float(np.mean(pnl_list) / np.std(pnl_list)) if len(pnl_list) > 1 and np.std(pnl_list) > 0 else 0

    return BacktestResult(
        pair=pair, model=model, ou_params=ou,
        trades=trades,
        total_pnl_bps=total_gross,
        total_pnl_net_bps=total_net,
        num_trades=num_trades,
        win_rate=win_rate,
        avg_pnl_bps=float(avg_pnl),
        max_drawdown_bps=max_dd,
        sharpe=sharpe,
        spread_mean_bps=float(np.mean(spreads_bps)),
        spread_std_bps=float(np.std(spreads_bps)),
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Stat arb backtester")
    parser.add_argument("data_dir", help="Path to JSONL data directory")
    parser.add_argument("--model", choices=["ou", "zscore", "both"], default="both",
                        help="Which model to run (default: both)")
    parser.add_argument("--coin", default="USDT",
                        help="Which stablecoin to analyze (default: USDT)")
    parser.add_argument("--entry-z", type=float, default=2.0,
                        help="Z-score entry threshold (default: 2.0)")
    parser.add_argument("--exit-z", type=float, default=0.5,
                        help="Z-score exit threshold (default: 0.5)")
    parser.add_argument("--window", type=int, default=20,
                        help="Rolling window for z-score model (default: 20)")
    parser.add_argument("--top-n", type=int, default=10,
                        help="Show top N exchange pairs by spread volatility")
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    print(f"Loading data from {data_dir}...")

    tickers = load_tickers(data_dir)
    funding = load_funding_rates(data_dir)

    coin = args.coin
    coin_tickers = tickers[tickers["coin"] == coin]
    exchanges = sorted(coin_tickers["exchange"].unique())
    snapshots = coin_tickers["snapshot_idx"].nunique()

    print(f"  {coin}: {len(exchanges)} exchanges, {snapshots} snapshots")
    print(f"  Exchanges: {', '.join(exchanges)}")
    print(f"  Time range: {coin_tickers['ts'].min()} → {coin_tickers['ts'].max()}")
    if not funding.empty:
        print(f"  Funding rate records: {len(funding)}")
    print()

    # Build spread series for all exchange pairs
    pairs = []
    for i, ex1 in enumerate(exchanges):
        for ex2 in exchanges[i + 1:]:
            spread_df = build_spread_series(tickers, ex1, ex2, coin)
            if len(spread_df) >= 10:
                pairs.append((ex1, ex2, spread_df))

    if not pairs:
        print("Not enough data to backtest. Need more snapshots.")
        sys.exit(1)

    # Sort by spread volatility (most volatile = most opportunity)
    pairs.sort(key=lambda x: x[2]["spread_bps"].std(), reverse=True)

    print(f"=== Spread Analysis ({coin}, {len(pairs)} exchange pairs) ===\n")
    print(f"{'Pair':<25} {'Mean(bps)':>10} {'Std(bps)':>10} {'Min':>8} {'Max':>8} {'Range':>8} {'Pts':>5}")
    print("-" * 80)
    for ex1, ex2, sdf in pairs[:args.top_n]:
        s = sdf["spread_bps"]
        print(f"{ex1}-{ex2:<20} {s.mean():>10.2f} {s.std():>10.2f} "
              f"{s.min():>8.2f} {s.max():>8.2f} {s.max()-s.min():>8.2f} {len(s):>5}")

    # Run strategies on top pairs
    print(f"\n{'=' * 80}")
    print(f"=== Backtest Results ===\n")

    all_results: List[BacktestResult] = []

    for ex1, ex2, spread_df in pairs[:args.top_n]:
        fee_bps = compute_fees_bps(ex1, ex2)

        if args.model in ("ou", "both"):
            result = run_ou_strategy(spread_df, ex1, ex2,
                                     entry_z=args.entry_z, exit_z=args.exit_z)
            all_results.append(result)

        if args.model in ("zscore", "both"):
            result = run_zscore_strategy(spread_df, ex1, ex2,
                                         window=args.window,
                                         entry_z=args.entry_z, exit_z=args.exit_z)
            all_results.append(result)

    # Print results table
    print(f"{'Pair':<25} {'Model':<8} {'Trades':>7} {'Gross(bps)':>11} {'Fees(bps)':>10} "
          f"{'Net(bps)':>10} {'WinRate':>8} {'Sharpe':>7} {'OU_hl':>7}")
    print("-" * 100)

    for r in sorted(all_results, key=lambda x: x.total_pnl_net_bps, reverse=True):
        hl = f"{r.ou_params.half_life:.1f}" if r.ou_params and r.ou_params.half_life < 1e6 else "inf"
        total_fees = r.num_trades * compute_fees_bps(
            r.pair.split("-")[0], r.pair.split("-", 1)[1]
        ) if r.num_trades > 0 else 0
        print(f"{r.pair:<25} {r.model:<8} {r.num_trades:>7} "
              f"{r.total_pnl_bps:>11.2f} {total_fees:>10.2f} "
              f"{r.total_pnl_net_bps:>10.2f} {r.win_rate:>7.1%} "
              f"{r.sharpe:>7.2f} {hl:>7}")

    # Detailed trade log for best result
    best = max(all_results, key=lambda x: x.total_pnl_net_bps) if all_results else None
    if best and best.trades:
        print(f"\n{'=' * 80}")
        print(f"=== Best: {best.pair} ({best.model}) — {best.num_trades} trades ===\n")

        if best.ou_params:
            ou = best.ou_params
            print(f"  OU Parameters:")
            print(f"    mu (long-run mean):  {ou.mu:.4f} bps")
            print(f"    theta (reversion):   {ou.theta:.4f}")
            print(f"    sigma (volatility):  {ou.sigma:.4f} bps")
            print(f"    half-life:           {ou.half_life:.1f} snapshots")
            print()

        print(f"  {'#':<4} {'Dir':<14} {'Entry_bps':>10} {'Exit_bps':>10} "
              f"{'Gross':>8} {'Fee':>8} {'Net':>8} {'Entry_time'}")
        print("  " + "-" * 90)
        for i, t in enumerate(best.trades[:30], 1):
            print(f"  {i:<4} {t.direction:<14} {t.entry_spread:>10.2f} "
                  f"{t.exit_spread:>10.2f} {t.pnl_gross_bps:>8.2f} "
                  f"{t.fee_bps:>8.2f} {t.pnl_net_bps:>8.2f} "
                  f"{t.entry_ts[:19]}")
        if len(best.trades) > 30:
            print(f"  ... and {len(best.trades) - 30} more trades")

    # Summary
    print(f"\n{'=' * 80}")
    print(f"=== Summary ===\n")
    profitable = [r for r in all_results if r.total_pnl_net_bps > 0]
    print(f"  Total pairs tested: {len(all_results)}")
    print(f"  Profitable (net):   {len(profitable)}")
    if profitable:
        best_p = max(profitable, key=lambda x: x.total_pnl_net_bps)
        print(f"  Best pair:          {best_p.pair} ({best_p.model}) = {best_p.total_pnl_net_bps:.2f} bps net")
    else:
        print(f"  ⚠  No profitable pairs found (fees too high relative to spreads)")
        print(f"  Tip: Try --entry-z 1.5 for more aggressive entry, or collect more data")

    # Key insight about fee viability
    avg_fee = np.mean([compute_fees_bps(
        r.pair.split("-")[0], r.pair.split("-", 1)[1]
    ) for r in all_results])
    avg_std = np.mean([r.spread_std_bps for r in all_results])
    print(f"\n  Avg round-trip fee:  {avg_fee:.1f} bps")
    print(f"  Avg spread std:     {avg_std:.2f} bps")
    print(f"  Fee/Std ratio:      {avg_fee/avg_std:.1f}x" if avg_std > 0 else "")
    if avg_fee > avg_std * 2:
        print(f"  → Fees dominate spread volatility. Pure arb is very tight.")
        print(f"    Better edge: predict regime shifts (depegs, exchange issues)")


if __name__ == "__main__":
    main()
