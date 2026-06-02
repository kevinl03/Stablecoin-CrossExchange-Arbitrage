#!/usr/bin/env python3
"""
Historical OHLCV Downloader — Fetch 30 days of 1-minute candles from all exchanges.

Downloads historical OHLCV data via CCXT's paginated fetch_ohlcv() for cross-exchange
backtesting. Saves per-asset per-exchange Parquet files.

Usage:
    # Download all 5 target assets, all exchanges, 30 days
    python experiments/download_historical_ohlcv.py

    # Specific assets and exchanges
    python experiments/download_historical_ohlcv.py --assets CRV WIF PEPE --exchanges binance htx kraken --days 14

    # Resume interrupted download
    python experiments/download_historical_ohlcv.py --resume

    # Custom output directory
    python experiments/download_historical_ohlcv.py --output-dir data/historical_v2
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import ccxt

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.data import EXCHANGES, COIN_MARKETS

# ── Configuration ─────────────────────────────────────────────────────────────

# Top assets from live opportunity scan (sorted by net spread)
DEFAULT_ASSETS = ["CRV", "WIF", "PEPE", "DOGE", "SOL"]

# All 12 exchanges
DEFAULT_EXCHANGES = list(EXCHANGES.keys())

# CCXT rate limits per exchange (requests per second, conservative)
# Most exchanges allow 10-20 req/s for public endpoints
RATE_LIMITS = {
    "binance":   0.1,   # 1200/min = 20/s → be conservative
    "kraken":    0.5,   # 1/s public
    "kucoin":    0.15,  # 10/s public
    "bybit":     0.1,   # 10/s public
    "okx":       0.1,   # 10/s public
    "gateio":    0.15,  # 10/s public
    "bitget":    0.1,   # 10/s public
    "mexc":      0.15,  # 10/s public
    "htx":       0.15,  # 10/s public
    "coinbase":  0.15,  # 10/s public
    "cryptocom": 0.2,   # conservative
    "phemex":    0.2,   # conservative
}

# Max candles per request (varies by exchange, CCXT handles this but we paginate manually)
MAX_CANDLES_PER_REQUEST = {
    "binance":   1000,
    "kraken":    720,
    "kucoin":    1500,
    "bybit":     1000,
    "okx":       300,
    "gateio":    1000,
    "bitget":    1000,
    "mexc":      1000,
    "htx":       2000,
    "coinbase":  300,
    "cryptocom": 300,
    "phemex":    1000,
}

TIMEFRAME = "1m"
CANDLE_MS = 60_000  # 1 minute in milliseconds


# ── Progress tracking ─────────────────────────────────────────────────────────

class DownloadProgress:
    """Track download progress for resume capability."""

    def __init__(self, output_dir: str):
        self._path = os.path.join(output_dir, "_progress.json")
        self._data = self._load()

    def _load(self) -> dict:
        if os.path.exists(self._path):
            with open(self._path) as f:
                return json.load(f)
        return {"completed": {}, "partial": {}}

    def save(self):
        with open(self._path, "w") as f:
            json.dump(self._data, f, indent=2, default=str)

    def is_completed(self, asset: str, exchange: str) -> bool:
        key = f"{asset}/{exchange}"
        return key in self._data.get("completed", {})

    def mark_completed(self, asset: str, exchange: str, rows: int):
        key = f"{asset}/{exchange}"
        self._data["completed"][key] = {
            "rows": rows,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        # Remove from partial if present
        self._data.get("partial", {}).pop(key, None)
        self.save()

    def get_last_timestamp(self, asset: str, exchange: str) -> Optional[int]:
        """Get the last downloaded timestamp (ms) for resume."""
        key = f"{asset}/{exchange}"
        return self._data.get("partial", {}).get(key, {}).get("last_ts")

    def update_partial(self, asset: str, exchange: str, last_ts: int, rows: int):
        key = f"{asset}/{exchange}"
        self._data.setdefault("partial", {})[key] = {
            "last_ts": last_ts,
            "rows_so_far": rows,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()

    def mark_skipped(self, asset: str, exchange: str, reason: str):
        key = f"{asset}/{exchange}"
        self._data["completed"][key] = {
            "rows": 0,
            "skipped": True,
            "reason": reason,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        self.save()


# ── Download logic ────────────────────────────────────────────────────────────

def get_symbol(asset: str, exchange_name: str) -> Optional[str]:
    """Get the trading symbol for an asset on an exchange."""
    markets = COIN_MARKETS.get(asset, {})
    return markets.get(exchange_name)


def download_ohlcv(
    exchange: ccxt.Exchange,
    exchange_name: str,
    symbol: str,
    since_ms: int,
    until_ms: int,
    progress: DownloadProgress,
    asset: str,
) -> list[list]:
    """
    Download OHLCV candles with pagination and rate limiting.

    Returns list of [timestamp, open, high, low, close, volume] arrays.
    """
    limit = MAX_CANDLES_PER_REQUEST.get(exchange_name, 500)
    delay = RATE_LIMITS.get(exchange_name, 0.2)
    all_candles = []
    current_since = since_ms
    retries = 0
    max_retries = 5

    while current_since < until_ms:
        try:
            candles = exchange.fetch_ohlcv(
                symbol,
                timeframe=TIMEFRAME,
                since=current_since,
                limit=limit,
            )
            retries = 0  # reset on success

            if not candles:
                break

            # Filter out candles beyond our end time
            candles = [c for c in candles if c[0] < until_ms]
            if not candles:
                break

            all_candles.extend(candles)

            # Move to next page
            last_ts = candles[-1][0]
            if last_ts <= current_since:
                # No progress — avoid infinite loop
                break
            current_since = last_ts + CANDLE_MS

            # Update partial progress every 5000 candles
            if len(all_candles) % 5000 < limit:
                progress.update_partial(asset, exchange_name, last_ts, len(all_candles))

            time.sleep(delay)

        except ccxt.RateLimitExceeded:
            retries += 1
            wait = min(2 ** retries, 60)
            print(f"      Rate limited, waiting {wait}s...")
            time.sleep(wait)
            if retries >= max_retries:
                print(f"      Max retries exceeded, stopping pagination")
                break

        except (ccxt.NetworkError, ccxt.ExchangeNotAvailable) as e:
            retries += 1
            wait = min(2 ** retries, 30)
            print(f"      Network error: {e}, retry {retries}/{max_retries} in {wait}s")
            time.sleep(wait)
            if retries >= max_retries:
                print(f"      Max retries exceeded, stopping")
                break

        except ccxt.BadSymbol:
            print(f"      Symbol {symbol} not available")
            return []

        except Exception as e:
            print(f"      Unexpected error: {e}")
            retries += 1
            if retries >= max_retries:
                break
            time.sleep(2)

    return all_candles


def candles_to_dataframe(candles: list[list]) -> pd.DataFrame:
    """Convert CCXT candle data to a pandas DataFrame."""
    if not candles:
        return pd.DataFrame(columns=["timestamp", "open", "high", "low", "close", "volume"])

    df = pd.DataFrame(candles, columns=["timestamp", "open", "high", "low", "close", "volume"])

    # Remove duplicates (pagination overlap)
    df = df.drop_duplicates(subset=["timestamp"], keep="last")
    df = df.sort_values("timestamp").reset_index(drop=True)

    # Convert timestamp to datetime for readability (keep ms column too)
    df["datetime"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)

    return df


def validate_data(df: pd.DataFrame, expected_start: int, expected_end: int) -> dict:
    """Validate downloaded data quality."""
    if df.empty:
        return {"valid": False, "reason": "empty", "rows": 0}

    total_expected = (expected_end - expected_start) // CANDLE_MS
    coverage = len(df) / total_expected if total_expected > 0 else 0

    # Check for gaps > 5 minutes
    ts_diff = df["timestamp"].diff().dropna()
    large_gaps = ts_diff[ts_diff > 5 * CANDLE_MS]

    # Check for outlier prices (> 50% change in 1 candle)
    price_change = df["close"].pct_change().abs()
    outliers = price_change[price_change > 0.5]

    return {
        "valid": True,
        "rows": len(df),
        "expected_rows": total_expected,
        "coverage_pct": round(coverage * 100, 1),
        "gaps_gt_5min": len(large_gaps),
        "largest_gap_min": round(large_gaps.max() / CANDLE_MS, 1) if len(large_gaps) > 0 else 0,
        "price_outliers": len(outliers),
        "start": df["datetime"].iloc[0].isoformat(),
        "end": df["datetime"].iloc[-1].isoformat(),
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Download historical OHLCV data for cross-exchange backtesting")
    parser.add_argument("--assets", nargs="+", default=DEFAULT_ASSETS,
                        help=f"Assets to download (default: {' '.join(DEFAULT_ASSETS)})")
    parser.add_argument("--exchanges", nargs="+", default=DEFAULT_EXCHANGES,
                        help="Exchanges to download from (default: all 12)")
    parser.add_argument("--days", type=int, default=30,
                        help="Number of days of history to download (default: 30)")
    parser.add_argument("--output-dir", type=str, default="data/historical",
                        help="Output directory (default: data/historical)")
    parser.add_argument("--resume", action="store_true",
                        help="Resume interrupted download")
    args = parser.parse_args()

    output_dir = args.output_dir
    os.makedirs(output_dir, exist_ok=True)
    progress = DownloadProgress(output_dir)

    # Time range
    now = datetime.now(timezone.utc)
    end_time = now.replace(second=0, microsecond=0)
    start_time = end_time - timedelta(days=args.days)
    since_ms = int(start_time.timestamp() * 1000)
    until_ms = int(end_time.timestamp() * 1000)
    expected_candles = (until_ms - since_ms) // CANDLE_MS

    # Create exchange instances with longer timeout for historical queries
    exchanges = {}
    for name in args.exchanges:
        if name in EXCHANGES:
            ex_class = type(EXCHANGES[name])
            exchanges[name] = ex_class({"timeout": 30000, "enableRateLimit": True})

    # Summary
    total_jobs = len(args.assets) * len(args.exchanges)
    completed = sum(1 for a in args.assets for e in args.exchanges if progress.is_completed(a, e))
    remaining = total_jobs - completed if args.resume else total_jobs

    print(f"=== Historical OHLCV Downloader ===")
    print(f"  Assets: {', '.join(args.assets)} ({len(args.assets)})")
    print(f"  Exchanges: {', '.join(args.exchanges)} ({len(args.exchanges)})")
    print(f"  Period: {start_time.strftime('%Y-%m-%d')} → {end_time.strftime('%Y-%m-%d')} ({args.days} days)")
    print(f"  Expected candles per pair: ~{expected_candles:,}")
    print(f"  Total jobs: {total_jobs} ({remaining} remaining)")
    print(f"  Output: {os.path.abspath(output_dir)}")
    print(f"  Format: Parquet (one file per asset/exchange)")
    print()

    job_num = 0
    success_count = 0
    skip_count = 0
    fail_count = 0
    validation_results = []

    for asset in args.assets:
        asset_dir = os.path.join(output_dir, asset)
        os.makedirs(asset_dir, exist_ok=True)

        for exchange_name in args.exchanges:
            job_num += 1

            # Skip if already completed (resume mode)
            if args.resume and progress.is_completed(asset, exchange_name):
                print(f"  [{job_num:>3}/{total_jobs}] {asset}/{exchange_name}: already completed, skipping")
                skip_count += 1
                continue

            # Get symbol
            symbol = get_symbol(asset, exchange_name)
            if not symbol:
                print(f"  [{job_num:>3}/{total_jobs}] {asset}/{exchange_name}: no symbol mapped, skipping")
                progress.mark_skipped(asset, exchange_name, "no_symbol")
                skip_count += 1
                continue

            exchange = exchanges.get(exchange_name)
            if not exchange:
                print(f"  [{job_num:>3}/{total_jobs}] {asset}/{exchange_name}: exchange not available, skipping")
                progress.mark_skipped(asset, exchange_name, "exchange_unavailable")
                skip_count += 1
                continue

            # Check for resume point
            resume_ts = progress.get_last_timestamp(asset, exchange_name) if args.resume else None
            effective_since = resume_ts + CANDLE_MS if resume_ts else since_ms

            print(f"  [{job_num:>3}/{total_jobs}] {asset}/{exchange_name} ({symbol})...", end=" ", flush=True)
            if resume_ts:
                pct = (resume_ts - since_ms) / (until_ms - since_ms) * 100
                print(f"resuming from {pct:.0f}%...", end=" ", flush=True)

            t0 = time.time()

            # Download
            candles = download_ohlcv(
                exchange, exchange_name, symbol,
                effective_since, until_ms,
                progress, asset,
            )

            if not candles:
                elapsed = time.time() - t0
                print(f"NO DATA ({elapsed:.1f}s)")
                progress.mark_skipped(asset, exchange_name, "no_data")
                fail_count += 1
                continue

            # If resuming, load existing data and merge
            parquet_path = os.path.join(asset_dir, f"{exchange_name}.parquet")
            if resume_ts and os.path.exists(parquet_path):
                existing_df = pd.read_parquet(parquet_path)
                new_df = candles_to_dataframe(candles)
                df = pd.concat([existing_df, new_df]).drop_duplicates(
                    subset=["timestamp"], keep="last"
                ).sort_values("timestamp").reset_index(drop=True)
            else:
                df = candles_to_dataframe(candles)

            # Validate
            validation = validate_data(df, since_ms, until_ms)

            # Save to Parquet
            df.to_parquet(parquet_path, index=False, engine="pyarrow")

            elapsed = time.time() - t0
            print(f"{len(df):,} rows, {validation['coverage_pct']}% coverage, "
                  f"{validation['gaps_gt_5min']} gaps ({elapsed:.1f}s)")

            if validation.get("price_outliers", 0) > 0:
                print(f"           ⚠ {validation['price_outliers']} price outliers detected")

            progress.mark_completed(asset, exchange_name, len(df))
            validation_results.append({
                "asset": asset,
                "exchange": exchange_name,
                **validation,
            })
            success_count += 1

    # ── Summary report ────────────────────────────────────────────────────

    print(f"\n{'=' * 70}")
    print(f"=== Download Summary ===\n")
    print(f"  Successful: {success_count}")
    print(f"  Skipped:    {skip_count}")
    print(f"  Failed:     {fail_count}")
    print(f"  Output:     {os.path.abspath(output_dir)}")

    if validation_results:
        print(f"\n  {'Asset':<8} {'Exchange':<12} {'Rows':>8} {'Coverage':>8} {'Gaps':>5} {'Start':<22} {'End':<22}")
        print(f"  {'-'*8} {'-'*12} {'-'*8} {'-'*8} {'-'*5} {'-'*22} {'-'*22}")
        for v in validation_results:
            print(f"  {v['asset']:<8} {v['exchange']:<12} {v['rows']:>8,} {v['coverage_pct']:>7}% {v['gaps_gt_5min']:>5} "
                  f"{v.get('start',''):<22} {v.get('end',''):<22}")

        # Save validation report
        report_path = os.path.join(output_dir, "_validation_report.json")
        with open(report_path, "w") as f:
            json.dump(validation_results, f, indent=2, default=str)
        print(f"\n  Validation report: {report_path}")

    # Data size
    total_size = 0
    for root, dirs, files in os.walk(output_dir):
        for fname in files:
            if fname.endswith(".parquet"):
                total_size += os.path.getsize(os.path.join(root, fname))
    print(f"  Total data size: {total_size / (1024*1024):.1f} MB")


if __name__ == "__main__":
    main()
