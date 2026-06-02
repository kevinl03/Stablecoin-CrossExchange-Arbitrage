#!/usr/bin/env python3
"""
Feature engineering pipeline for ML spread predictor.

Builds features from the multi-signal data collected by collect_statarb_data.py
for training a gradient-boosted spread direction model.

Features:
  - Spread-based: current, lagged, rolling stats, z-scores
  - Funding rate: differential, rolling avg, settlement proximity
  - Open interest: change rate, imbalance
  - Withdrawal status: disabled flags, recent changes
  - Volume: imbalance, momentum
  - Time: hour, day-of-week, funding settlement proximity

Output: A single Parquet file per exchange pair with features and target.

Usage:
    python experiments/build_features.py data/statarb/20260602_211358 --target-horizon 5
    python experiments/build_features.py data/statarb/20260602_211358 --output-dir features/
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.fees import TRADING_FEES_TAKER


# ── Data Loading ──────────────────────────────────────────────────────────────

def _load_jsonl(path: Path, type_filter: str = None) -> list[dict]:
    """Load JSONL file, optionally filtering by record type."""
    if not path.exists():
        return []
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            if type_filter and rec.get("type") != type_filter:
                continue
            if "error" in rec:
                continue
            records.append(rec)
    return records


def load_all_signals(data_dir: str) -> dict:
    """Load all signal types from a collector run."""
    base = Path(data_dir)
    return {
        "tickers": _load_jsonl(base / "ticker.jsonl", "ticker"),
        "funding_rates": _load_jsonl(base / "funding_rate.jsonl", "funding_rate"),
        "open_interest": _load_jsonl(base / "open_interest.jsonl", "open_interest"),
        "withdrawal_status": _load_jsonl(base / "withdrawal_status.jsonl", "withdrawal_status"),
        "exchange_status": _load_jsonl(base / "exchange_status.jsonl", "exchange_status"),
        "spread_matrix": _load_jsonl(base / "spread_matrix.jsonl", "spread_matrix"),
    }


def tickers_to_df(tickers: list[dict]) -> pd.DataFrame:
    """Convert ticker records to DataFrame."""
    records = []
    for r in tickers:
        records.append({
            "ts": pd.Timestamp(r["ts"]),
            "snapshot_idx": r["snapshot_idx"],
            "exchange": r["exchange"],
            "coin": r["coin"],
            "price_usd": r.get("price_usd"),
            "bid": r.get("bid"),
            "ask": r.get("ask"),
            "mid": r.get("mid"),
            "volume_24h": r.get("base_volume_24h"),
        })
    df = pd.DataFrame(records)
    return df.dropna(subset=["price_usd"]).sort_values(["snapshot_idx", "exchange", "coin"])


def funding_to_df(records: list[dict]) -> pd.DataFrame:
    """Convert funding rate records to DataFrame."""
    if not records:
        return pd.DataFrame()
    rows = []
    for r in records:
        rows.append({
            "ts": pd.Timestamp(r["ts"]),
            "snapshot_idx": r["snapshot_idx"],
            "exchange": r["exchange"],
            "symbol": r["symbol"],
            "funding_rate": r.get("funding_rate"),
        })
    return pd.DataFrame(rows).dropna(subset=["funding_rate"])


def oi_to_df(records: list[dict]) -> pd.DataFrame:
    """Convert open interest records to DataFrame."""
    if not records:
        return pd.DataFrame()
    rows = []
    for r in records:
        rows.append({
            "ts": pd.Timestamp(r["ts"]),
            "snapshot_idx": r["snapshot_idx"],
            "exchange": r["exchange"],
            "symbol": r["symbol"],
            "open_interest": r.get("open_interest"),
            "open_interest_usd": r.get("open_interest_usd"),
        })
    return pd.DataFrame(rows)


def withdrawal_to_df(records: list[dict]) -> pd.DataFrame:
    """Convert withdrawal status records to DataFrame."""
    if not records:
        return pd.DataFrame()
    rows = []
    for r in records:
        rows.append({
            "ts": pd.Timestamp(r["ts"]),
            "snapshot_idx": r["snapshot_idx"],
            "exchange": r["exchange"],
            "coin": r.get("coin") or r.get("currency"),
            "withdraw_enabled": r.get("withdraw_enabled"),
            "deposit_enabled": r.get("deposit_enabled"),
        })
    return pd.DataFrame(rows)


# ── Feature Building ─────────────────────────────────────────────────────────

def build_spread_features(
    tickers_df: pd.DataFrame,
    coin: str,
    ex1: str,
    ex2: str,
    windows: list[int] = [3, 5, 10, 20],
) -> pd.DataFrame:
    """
    Build spread-based features for one exchange pair and coin.
    """
    t1 = tickers_df[(tickers_df["exchange"] == ex1) & (tickers_df["coin"] == coin)]
    t2 = tickers_df[(tickers_df["exchange"] == ex2) & (tickers_df["coin"] == coin)]

    if t1.empty or t2.empty:
        return pd.DataFrame()

    s1 = t1.set_index("snapshot_idx")[["ts", "price_usd", "bid", "ask", "volume_24h"]].rename(
        columns={"price_usd": "p1", "bid": "bid1", "ask": "ask1", "volume_24h": "vol1"}
    )
    s2 = t2.set_index("snapshot_idx")[["price_usd", "bid", "ask", "volume_24h"]].rename(
        columns={"price_usd": "p2", "bid": "bid2", "ask": "ask2", "volume_24h": "vol2"}
    )

    df = s1.join(s2, how="inner").reset_index()
    if len(df) < max(windows) + 5:
        return pd.DataFrame()

    mid = (df["p1"] + df["p2"]) / 2
    df["spread_bps"] = (df["p1"] - df["p2"]) / mid * 10_000

    # Bid-ask spread width
    df["ba_spread1_bps"] = (df["ask1"] - df["bid1"]) / df["p1"] * 10_000
    df["ba_spread2_bps"] = (df["ask2"] - df["bid2"]) / df["p2"] * 10_000
    df["ba_ratio"] = df["ba_spread1_bps"] / df["ba_spread2_bps"].replace(0, np.nan)

    # Volume imbalance
    df["vol_ratio"] = df["vol1"] / df["vol2"].replace(0, np.nan)
    df["vol_log_ratio"] = np.log1p(df["vol1"]) - np.log1p(df["vol2"])

    # Lagged spreads
    for lag in [1, 2, 3, 5, 10]:
        df[f"spread_lag_{lag}"] = df["spread_bps"].shift(lag)

    # Rolling statistics
    for w in windows:
        roll = df["spread_bps"].rolling(w, min_periods=w)
        df[f"spread_mean_{w}"] = roll.mean()
        df[f"spread_std_{w}"] = roll.std()
        df[f"spread_zscore_{w}"] = (df["spread_bps"] - df[f"spread_mean_{w}"]) / df[f"spread_std_{w}"].replace(0, np.nan)
        df[f"spread_min_{w}"] = roll.min()
        df[f"spread_max_{w}"] = roll.max()
        df[f"spread_skew_{w}"] = roll.skew()

    # Spread momentum (change from N periods ago)
    for lag in [1, 3, 5, 10]:
        df[f"spread_momentum_{lag}"] = df["spread_bps"] - df["spread_bps"].shift(lag)

    # Spread velocity (rate of change)
    df["spread_velocity_3"] = df["spread_bps"].diff(3) / 3
    df["spread_velocity_5"] = df["spread_bps"].diff(5) / 5

    return df


def add_funding_features(
    features_df: pd.DataFrame,
    funding_df: pd.DataFrame,
    coin: str,
    ex1: str,
    ex2: str,
) -> pd.DataFrame:
    """Add funding rate features."""
    if funding_df.empty:
        return features_df

    # Map coin to perp symbol
    perp_symbol = f"{coin}/USDT:USDT"

    fr1 = funding_df[(funding_df["exchange"] == ex1) & (funding_df["symbol"] == perp_symbol)]
    fr2 = funding_df[(funding_df["exchange"] == ex2) & (funding_df["symbol"] == perp_symbol)]

    if fr1.empty and fr2.empty:
        features_df["funding_rate_1"] = np.nan
        features_df["funding_rate_2"] = np.nan
        features_df["funding_diff"] = np.nan
        return features_df

    # Merge funding rates by snapshot_idx (forward fill since funding updates less frequently)
    for label, fr_df, col in [("1", fr1, "funding_rate_1"), ("2", fr2, "funding_rate_2")]:
        if not fr_df.empty:
            fr_mapped = fr_df.set_index("snapshot_idx")["funding_rate"].rename(col)
            features_df = features_df.join(fr_mapped, on="snapshot_idx", how="left")
            features_df[col] = features_df[col].ffill()
        else:
            features_df[col] = np.nan

    features_df["funding_diff"] = features_df["funding_rate_1"] - features_df["funding_rate_2"]
    features_df["funding_diff_abs"] = features_df["funding_diff"].abs()

    # Rolling average of funding differential
    for w in [3, 5]:
        features_df[f"funding_diff_ma_{w}"] = features_df["funding_diff"].rolling(w, min_periods=1).mean()

    return features_df


def add_oi_features(
    features_df: pd.DataFrame,
    oi_df: pd.DataFrame,
    coin: str,
    ex1: str,
    ex2: str,
) -> pd.DataFrame:
    """Add open interest features."""
    if oi_df.empty:
        features_df["oi_1"] = np.nan
        features_df["oi_2"] = np.nan
        features_df["oi_ratio"] = np.nan
        features_df["oi_change_1"] = np.nan
        features_df["oi_change_2"] = np.nan
        return features_df

    perp_symbol = f"{coin}/USDT:USDT"

    for label, ex_name, col in [("1", ex1, "oi_1"), ("2", ex2, "oi_2")]:
        ex_oi = oi_df[(oi_df["exchange"] == ex_name) & (oi_df["symbol"] == perp_symbol)]
        if not ex_oi.empty:
            oi_mapped = ex_oi.set_index("snapshot_idx")["open_interest"].rename(col)
            features_df = features_df.join(oi_mapped, on="snapshot_idx", how="left")
            features_df[col] = features_df[col].ffill()
        else:
            features_df[col] = np.nan

    # OI ratio
    features_df["oi_ratio"] = features_df["oi_1"] / features_df["oi_2"].replace(0, np.nan)

    # OI change rate
    features_df["oi_change_1"] = features_df["oi_1"].pct_change()
    features_df["oi_change_2"] = features_df["oi_2"].pct_change()
    features_df["oi_change_diff"] = features_df["oi_change_1"] - features_df["oi_change_2"]

    return features_df


def add_withdrawal_features(
    features_df: pd.DataFrame,
    withdrawal_df: pd.DataFrame,
    coin: str,
    ex1: str,
    ex2: str,
) -> pd.DataFrame:
    """Add withdrawal/deposit status features."""
    if withdrawal_df.empty:
        features_df["withdraw_disabled_1"] = 0
        features_df["withdraw_disabled_2"] = 0
        features_df["deposit_disabled_1"] = 0
        features_df["deposit_disabled_2"] = 0
        features_df["any_disabled"] = 0
        return features_df

    for label, ex_name in [("1", ex1), ("2", ex2)]:
        ws = withdrawal_df[
            (withdrawal_df["exchange"] == ex_name) &
            (withdrawal_df["coin"] == coin)
        ]
        if not ws.empty:
            ws_mapped = ws.set_index("snapshot_idx")[["withdraw_enabled", "deposit_enabled"]]
            ws_mapped = ws_mapped.rename(columns={
                "withdraw_enabled": f"withdraw_enabled_{label}",
                "deposit_enabled": f"deposit_enabled_{label}",
            })
            # Take last per snapshot
            ws_mapped = ws_mapped[~ws_mapped.index.duplicated(keep="last")]
            features_df = features_df.join(ws_mapped, on="snapshot_idx", how="left")
            features_df[f"withdraw_enabled_{label}"] = features_df[f"withdraw_enabled_{label}"].ffill().fillna(True)
            features_df[f"deposit_enabled_{label}"] = features_df[f"deposit_enabled_{label}"].ffill().fillna(True)
        else:
            features_df[f"withdraw_enabled_{label}"] = True
            features_df[f"deposit_enabled_{label}"] = True

        # Convert to "disabled" flags (more useful for features)
        features_df[f"withdraw_disabled_{label}"] = (~features_df[f"withdraw_enabled_{label}"].astype(bool)).astype(int)
        features_df[f"deposit_disabled_{label}"] = (~features_df[f"deposit_enabled_{label}"].astype(bool)).astype(int)

    features_df["any_disabled"] = (
        features_df["withdraw_disabled_1"] |
        features_df["withdraw_disabled_2"] |
        features_df["deposit_disabled_1"] |
        features_df["deposit_disabled_2"]
    ).astype(int)

    # Drop intermediate columns
    for col in ["withdraw_enabled_1", "withdraw_enabled_2", "deposit_enabled_1", "deposit_enabled_2"]:
        features_df.drop(columns=[col], errors="ignore", inplace=True)

    return features_df


def add_time_features(features_df: pd.DataFrame) -> pd.DataFrame:
    """Add time-based features."""
    ts = pd.to_datetime(features_df["ts"])

    features_df["hour"] = ts.dt.hour
    features_df["minute"] = ts.dt.minute
    features_df["day_of_week"] = ts.dt.dayofweek
    features_df["is_weekend"] = (ts.dt.dayofweek >= 5).astype(int)

    # Distance to funding settlement times (00:00, 08:00, 16:00 UTC)
    hours_in_day = ts.dt.hour + ts.dt.minute / 60
    settlement_times = [0, 8, 16]
    min_dist = pd.Series(np.inf, index=features_df.index)
    for st in settlement_times:
        dist = (hours_in_day - st).abs()
        dist = dist.where(dist <= 12, 24 - dist)  # wrap around
        min_dist = min_dist.where(min_dist < dist, dist)
    features_df["hours_to_settlement"] = min_dist

    return features_df


def add_target(
    features_df: pd.DataFrame,
    horizon: int = 5,
) -> pd.DataFrame:
    """
    Add target variable: will spread widen or narrow in the next N periods?

    target = 1 if spread moves toward mean (profitable for mean-reversion)
    target = 0 if spread moves away from mean (unprofitable)
    """
    spread = features_df["spread_bps"]
    future_spread = spread.shift(-horizon)
    current_spread = spread
    spread_mean = spread.rolling(20, min_periods=5).mean()

    # Direction: did the spread move toward the mean?
    current_deviation = (current_spread - spread_mean).abs()
    future_deviation = (future_spread - spread_mean).abs()

    features_df["target_revert"] = (future_deviation < current_deviation).astype(int)

    # Also add a regression target: actual future spread change
    features_df["target_spread_change"] = future_spread - current_spread

    # Binary: spread narrowed (positive for short_spread position)
    features_df["target_narrowed"] = (future_spread.abs() < current_spread.abs()).astype(int)

    return features_df


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Build ML features from collector data")
    parser.add_argument("data_dir", help="Path to collector output directory")
    parser.add_argument("--target-horizon", type=int, default=5,
                        help="Target prediction horizon in snapshots (default: 5)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Output directory (default: <data_dir>/features/)")
    parser.add_argument("--min-snapshots", type=int, default=30,
                        help="Min snapshots for a valid pair (default: 30)")
    parser.add_argument("--top-n", type=int, default=5,
                        help="Top N pairs by spread std to build features for")
    args = parser.parse_args()

    output_dir = args.output_dir or os.path.join(args.data_dir, "features")
    os.makedirs(output_dir, exist_ok=True)

    print(f"=== Feature Engineering Pipeline ===")
    print(f"  Data: {args.data_dir}")
    print(f"  Target horizon: {args.target_horizon} snapshots")
    print(f"  Output: {output_dir}")
    print()

    # Load all signals
    print("Loading signals...")
    signals = load_all_signals(args.data_dir)
    print(f"  Tickers: {len(signals['tickers'])}")
    print(f"  Funding rates: {len(signals['funding_rates'])}")
    print(f"  Open interest: {len(signals['open_interest'])}")
    print(f"  Withdrawal status: {len(signals['withdrawal_status'])}")
    print()

    tickers_df = tickers_to_df(signals["tickers"])
    funding_df = funding_to_df(signals["funding_rates"])
    oi_df = oi_to_df(signals["open_interest"])
    withdrawal_df = withdrawal_to_df(signals["withdrawal_status"])

    # Discover coins and exchanges
    coins = sorted(tickers_df["coin"].unique())
    exchanges = sorted(tickers_df["exchange"].unique())
    snapshots = tickers_df["snapshot_idx"].nunique()
    print(f"  Coins: {', '.join(coins)} ({len(coins)})")
    print(f"  Exchanges: {', '.join(exchanges)} ({len(exchanges)})")
    print(f"  Snapshots: {snapshots}")
    print()

    total_pairs = 0
    total_features = 0

    for coin in coins:
        # Find exchange pairs with enough data
        coin_tickers = tickers_df[tickers_df["coin"] == coin]
        coin_exchanges = sorted(coin_tickers["exchange"].unique())

        if len(coin_exchanges) < 2:
            continue

        # Build all pairs, rank by spread std
        pair_data = []
        for i, ex1 in enumerate(coin_exchanges):
            for ex2 in coin_exchanges[i + 1:]:
                spread_df = build_spread_features(tickers_df, coin, ex1, ex2)
                if len(spread_df) >= args.min_snapshots:
                    spread_std = spread_df["spread_bps"].std()
                    pair_data.append((ex1, ex2, spread_df, spread_std))

        if not pair_data:
            continue

        pair_data.sort(key=lambda x: x[3], reverse=True)

        print(f"  {coin}: {len(pair_data)} pairs, top by spread std:")
        for ex1, ex2, sdf, std in pair_data[:args.top_n]:
            print(f"    {ex1}-{ex2}: std={std:.2f} bps, {len(sdf)} snapshots")

        # Build full features for top pairs
        for ex1, ex2, features_df, _ in pair_data[:args.top_n]:
            # Add all signal features
            features_df = add_funding_features(features_df, funding_df, coin, ex1, ex2)
            features_df = add_oi_features(features_df, oi_df, coin, ex1, ex2)
            features_df = add_withdrawal_features(features_df, withdrawal_df, coin, ex1, ex2)
            features_df = add_time_features(features_df)
            features_df = add_target(features_df, horizon=args.target_horizon)

            # Drop rows with NaN target (last N rows)
            valid = features_df.dropna(subset=["target_revert"])

            # Save
            filename = f"{coin}_{ex1}_{ex2}.parquet"
            out_path = os.path.join(output_dir, filename)
            valid.to_parquet(out_path, index=False, engine="pyarrow")

            feature_cols = [c for c in valid.columns if c not in
                           ["ts", "snapshot_idx", "p1", "p2", "bid1", "ask1", "bid2", "ask2",
                            "vol1", "vol2", "spread", "target_revert", "target_spread_change",
                            "target_narrowed"]]

            total_pairs += 1
            total_features += len(feature_cols)

            print(f"    -> {filename}: {len(valid)} rows, {len(feature_cols)} features")

    print(f"\n{'=' * 60}")
    print(f"=== Summary ===")
    print(f"  Pairs processed: {total_pairs}")
    print(f"  Features per pair: ~{total_features // max(total_pairs, 1)}")
    print(f"  Output: {output_dir}")

    # List feature columns for documentation
    if total_pairs > 0:
        sample_file = sorted(Path(output_dir).glob("*.parquet"))[0]
        sample_df = pd.read_parquet(sample_file)
        feature_cols = sorted([c for c in sample_df.columns if c not in
                              ["ts", "snapshot_idx", "p1", "p2", "bid1", "ask1", "bid2", "ask2",
                               "vol1", "vol2", "spread", "target_revert", "target_spread_change",
                               "target_narrowed"]])
        print(f"\n  Feature columns ({len(feature_cols)}):")
        for i, col in enumerate(feature_cols):
            print(f"    {i+1:>3}. {col}")


if __name__ == "__main__":
    main()
