"""
Multi-signal data collector for statistical arbitrage research.

Collects 10 data types per snapshot at configurable intervals:
  1. Ticker (bid/ask/last/volume/24h stats)
  2. L2 Order Book (top N levels per side)
  3. OHLCV 1-minute candles (latest N candles)
  4. Recent trades (latest N trades)
  5. Cross-exchange spread matrix (computed)
  6. Bid-ask spread width (computed)
  7. Perpetual funding rates (stablecoin perps)
  8. Open interest (stablecoin perps)
  9. Withdrawal/deposit status per coin per chain
 10. Exchange health status

Output: JSONL files in data/statarb/<run_id>/, one per data type.
Each line is a JSON object with a UTC ISO-8601 timestamp.

Usage:
    python -m experiments.collect_statarb_data [--interval 30] [--hours 24] [--ob-depth 20]
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.data import EXCHANGES, STABLE_COINS, VOLATILE_COINS, ALL_COINS, COIN_MARKETS, normalize_price_to_usd


# ---------------------------------------------------------------------------
# Prevent Windows from sleeping while collecting data
# ---------------------------------------------------------------------------
def _prevent_sleep():
    """Tell Windows to keep the system awake (display can turn off)."""
    if sys.platform == "win32":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        print("  [POWER] Windows sleep inhibited for this process.")


def _allow_sleep():
    """Restore normal Windows sleep behavior."""
    if sys.platform == "win32":
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_INTERVAL_SEC = 30       # seconds between snapshots
DEFAULT_HOURS = 24              # total runtime
DEFAULT_OB_DEPTH = 20           # order book levels per side
DEFAULT_OHLCV_CANDLES = 5       # number of 1m candles to fetch
DEFAULT_TRADES_LIMIT = 50       # recent trades per pair

# Stablecoin perpetual symbols to check for funding rates & OI.
# Format: CCXT unified symbol for the perpetual contract.
STABLECOIN_PERP_SYMBOLS = [
    "USDC/USDT:USDT",
    "DAI/USDT:USDT",
    "FDUSD/USDT:USDT",
    "TUSD/USDT:USDT",
]

# Volatile asset perpetual symbols
VOLATILE_PERP_SYMBOLS = [
    "BTC/USDT:USDT", "ETH/USDT:USDT", "SOL/USDT:USDT",
    "DOGE/USDT:USDT", "XRP/USDT:USDT", "ADA/USDT:USDT", "AVAX/USDT:USDT",
    "CRV/USDT:USDT", "LDO/USDT:USDT", "UNI/USDT:USDT", "AAVE/USDT:USDT",
    "ARB/USDT:USDT", "OP/USDT:USDT",
    "PEPE/USDT:USDT", "WIF/USDT:USDT",
]

ALL_PERP_SYMBOLS = STABLECOIN_PERP_SYMBOLS + VOLATILE_PERP_SYMBOLS


def _resolve_asset_config(asset_mode: str):
    """Return (coin_list, perp_symbols) based on the --assets flag."""
    if asset_mode == "stablecoins":
        return STABLE_COINS, STABLECOIN_PERP_SYMBOLS
    elif asset_mode == "volatile":
        return VOLATILE_COINS, VOLATILE_PERP_SYMBOLS
    elif asset_mode == "all":
        return ALL_COINS, ALL_PERP_SYMBOLS
    else:
        raise ValueError(f"Unknown asset mode: {asset_mode}")

# Active coin list and perp symbols — set by main() based on --assets flag.
# Default to stablecoins for backward compatibility.
ACTIVE_COINS = STABLE_COINS
ACTIVE_PERPS = STABLECOIN_PERP_SYMBOLS

# Graceful shutdown
_RUNNING = True


def _handle_signal(signum, frame):
    global _RUNNING
    _RUNNING = False
    print("\n[SHUTDOWN] Signal received, finishing current snapshot...")


signal.signal(signal.SIGINT, _handle_signal)
signal.signal(signal.SIGTERM, _handle_signal)


# ---------------------------------------------------------------------------
# Data collection functions
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_float(v: Any) -> Optional[float]:
    """Convert to float if numeric, else None."""
    if isinstance(v, (int, float)) and not (isinstance(v, float) and v != v):
        return float(v)
    return None


def collect_tickers(
    snapshot_idx: int,
) -> Tuple[List[Dict], Dict[Tuple[str, str], Dict]]:
    """
    Fetch ticker data for every (exchange, coin) pair.
    Returns (list of ticker records, raw_tickers_by_node for downstream use).
    """
    records = []
    raw_tickers: Dict[Tuple[str, str], Dict] = {}
    ts = _now_iso()
    failed_exchanges: set = set()

    for coin in ACTIVE_COINS:
        for ex_name, ex in EXCHANGES.items():
            if ex_name in failed_exchanges:
                continue

            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue

            try:
                t = ex.fetch_ticker(market)
                bid = _safe_float(t.get("bid"))
                ask = _safe_float(t.get("ask"))
                last = _safe_float(t.get("last"))
                vol = _safe_float(t.get("baseVolume"))
                quote_vol = _safe_float(t.get("quoteVolume"))
                high = _safe_float(t.get("high"))
                low = _safe_float(t.get("low"))
                vwap = _safe_float(t.get("vwap"))
                pct_change = _safe_float(t.get("percentage"))

                # Normalize mid to USD
                mid = None
                if bid is not None and ask is not None:
                    mid = (bid + ask) / 2.0
                elif last is not None:
                    mid = last

                price_usd = None
                if mid is not None:
                    price_usd = normalize_price_to_usd(coin, market, mid)

                spread_bps = None
                if bid is not None and ask is not None and mid and mid > 0:
                    spread_bps = ((ask - bid) / mid) * 10_000

                rec = {
                    "type": "ticker",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "bid": bid,
                    "ask": ask,
                    "last": last,
                    "mid": mid,
                    "price_usd": price_usd,
                    "spread_bps": spread_bps,
                    "base_volume_24h": vol,
                    "quote_volume_24h": quote_vol,
                    "high_24h": high,
                    "low_24h": low,
                    "vwap": vwap,
                    "pct_change_24h": pct_change,
                }
                records.append(rec)
                raw_tickers[(ex_name, coin)] = rec

            except Exception as e:
                failed_exchanges.add(ex_name)
                records.append({
                    "type": "ticker",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "error": str(e),
                })

    return records, raw_tickers


def collect_orderbooks(
    snapshot_idx: int,
    depth: int = DEFAULT_OB_DEPTH,
) -> List[Dict]:
    """
    Fetch L2 order book snapshots (top `depth` levels per side).
    """
    records = []
    ts = _now_iso()
    failed_exchanges: set = set()

    for coin in ACTIVE_COINS:
        for ex_name, ex in EXCHANGES.items():
            if ex_name in failed_exchanges:
                continue

            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue

            try:
                ob = ex.fetch_order_book(market, limit=depth)

                bids = ob.get("bids", [])[:depth]
                asks = ob.get("asks", [])[:depth]

                # Summarize: total bid/ask depth in base units
                bid_depth = sum(b[1] for b in bids) if bids else 0.0
                ask_depth = sum(a[1] for a in asks) if asks else 0.0

                # Top-of-book
                best_bid = bids[0][0] if bids else None
                best_ask = asks[0][0] if asks else None

                # Weighted average prices (volume-weighted top N)
                bid_vwap = (
                    sum(b[0] * b[1] for b in bids) / bid_depth
                    if bid_depth > 0 else None
                )
                ask_vwap = (
                    sum(a[0] * a[1] for a in asks) / ask_depth
                    if ask_depth > 0 else None
                )

                # Imbalance ratio: >0.5 = more bids (buy pressure)
                total_depth = bid_depth + ask_depth
                imbalance = bid_depth / total_depth if total_depth > 0 else 0.5

                # Slippage at various notional sizes
                slippage_levels = _compute_slippage(bids, asks, [1000, 5000, 10000, 50000])

                rec = {
                    "type": "orderbook",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "depth_levels": depth,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                    "bid_depth_units": round(bid_depth, 4),
                    "ask_depth_units": round(ask_depth, 4),
                    "bid_vwap": bid_vwap,
                    "ask_vwap": ask_vwap,
                    "imbalance": round(imbalance, 6),
                    "slippage_bps": slippage_levels,
                    "bids_raw": [[round(p, 8), round(q, 4)] for p, q in bids],
                    "asks_raw": [[round(p, 8), round(q, 4)] for p, q in asks],
                }
                records.append(rec)

            except Exception as e:
                # Some exchanges may not support order books for all pairs
                records.append({
                    "type": "orderbook",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "error": str(e),
                })
                if "not support" in str(e).lower() or "not available" in str(e).lower():
                    continue
                failed_exchanges.add(ex_name)

    return records


def _compute_slippage(
    bids: List[List[float]],
    asks: List[List[float]],
    notional_sizes_usd: List[int],
) -> Dict[str, Optional[float]]:
    """
    Compute slippage in bps for selling/buying at various notional sizes.
    Returns {f"sell_{size}": bps, f"buy_{size}": bps, ...}
    """
    result = {}

    for size in notional_sizes_usd:
        # Sell slippage (walk down bids)
        sell_slip = _walk_book(bids, size, side="sell")
        result[f"sell_{size}"] = sell_slip

        # Buy slippage (walk up asks)
        buy_slip = _walk_book(asks, size, side="buy")
        result[f"buy_{size}"] = buy_slip

    return result


def _walk_book(
    levels: List[List[float]],
    notional_usd: float,
    side: str,
) -> Optional[float]:
    """Walk order book levels to compute execution price vs top-of-book."""
    if not levels:
        return None

    top_price = levels[0][0]
    if top_price <= 0:
        return None

    remaining = notional_usd
    total_cost = 0.0

    for price, qty in levels:
        level_value = price * qty
        fill = min(remaining, level_value)
        total_cost += fill
        remaining -= fill
        if remaining <= 0:
            break

    if remaining > 0:
        return None  # Not enough depth

    avg_price = total_cost / notional_usd * top_price if notional_usd > 0 else top_price

    # For stablecoins ~$1, slippage is deviation from top price
    # Sell: avg execution < top bid = negative slip
    # Buy: avg execution > top ask = positive slip
    if side == "sell":
        slip_bps = ((top_price - avg_price) / top_price) * 10_000
    else:
        slip_bps = ((avg_price - top_price) / top_price) * 10_000

    return round(slip_bps, 2)


def collect_ohlcv(
    snapshot_idx: int,
    num_candles: int = DEFAULT_OHLCV_CANDLES,
) -> List[Dict]:
    """
    Fetch recent 1-minute OHLCV candles.
    """
    records = []
    ts = _now_iso()
    failed_exchanges: set = set()

    for coin in ACTIVE_COINS:
        for ex_name, ex in EXCHANGES.items():
            if ex_name in failed_exchanges:
                continue

            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue

            try:
                candles = ex.fetch_ohlcv(market, timeframe="1m", limit=num_candles)

                for candle in candles:
                    # CCXT format: [timestamp, open, high, low, close, volume]
                    c_ts = candle[0]
                    rec = {
                        "type": "ohlcv",
                        "ts": ts,
                        "snapshot_idx": snapshot_idx,
                        "exchange": ex_name,
                        "coin": coin,
                        "market": market,
                        "candle_ts": c_ts,
                        "candle_dt": datetime.fromtimestamp(
                            c_ts / 1000, tz=timezone.utc
                        ).isoformat() if c_ts else None,
                        "open": candle[1],
                        "high": candle[2],
                        "low": candle[3],
                        "close": candle[4],
                        "volume": candle[5],
                    }
                    records.append(rec)

            except Exception as e:
                records.append({
                    "type": "ohlcv",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "error": str(e),
                })
                if "not support" in str(e).lower():
                    continue
                failed_exchanges.add(ex_name)

    return records


def collect_trades(
    snapshot_idx: int,
    limit: int = DEFAULT_TRADES_LIMIT,
) -> List[Dict]:
    """
    Fetch recent trades — useful for trade flow analysis and realized spread.
    """
    records = []
    ts = _now_iso()
    failed_exchanges: set = set()

    for coin in ACTIVE_COINS:
        for ex_name, ex in EXCHANGES.items():
            if ex_name in failed_exchanges:
                continue

            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue

            try:
                trades = ex.fetch_trades(market, limit=limit)

                # Summarize rather than storing every trade
                if not trades:
                    continue

                prices = [t["price"] for t in trades if t.get("price")]
                amounts = [t["amount"] for t in trades if t.get("amount")]
                sides = [t.get("side") for t in trades]

                buy_count = sum(1 for s in sides if s == "buy")
                sell_count = sum(1 for s in sides if s == "sell")
                buy_volume = sum(
                    t["amount"] for t in trades
                    if t.get("side") == "buy" and t.get("amount")
                )
                sell_volume = sum(
                    t["amount"] for t in trades
                    if t.get("side") == "sell" and t.get("amount")
                )

                # Time span of trades
                timestamps = [t["timestamp"] for t in trades if t.get("timestamp")]
                ts_min = min(timestamps) if timestamps else None
                ts_max = max(timestamps) if timestamps else None

                rec = {
                    "type": "trades",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "trade_count": len(trades),
                    "price_min": min(prices) if prices else None,
                    "price_max": max(prices) if prices else None,
                    "price_mean": sum(prices) / len(prices) if prices else None,
                    "total_volume": sum(amounts) if amounts else None,
                    "buy_count": buy_count,
                    "sell_count": sell_count,
                    "buy_volume": round(buy_volume, 4),
                    "sell_volume": round(sell_volume, 4),
                    "buy_sell_ratio": (
                        round(buy_volume / sell_volume, 4)
                        if sell_volume > 0 else None
                    ),
                    "time_span_sec": (
                        round((ts_max - ts_min) / 1000, 2)
                        if ts_min and ts_max else None
                    ),
                    # Store individual trades for fine-grained analysis
                    "trades_raw": [
                        {
                            "ts": t.get("timestamp"),
                            "price": t.get("price"),
                            "amount": t.get("amount"),
                            "side": t.get("side"),
                        }
                        for t in trades[-20:]  # keep last 20 for storage efficiency
                    ],
                }
                records.append(rec)

            except Exception as e:
                records.append({
                    "type": "trades",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "coin": coin,
                    "market": market,
                    "error": str(e),
                })
                if "not support" in str(e).lower():
                    continue
                failed_exchanges.add(ex_name)

    return records


def compute_spread_matrix(
    raw_tickers: Dict[Tuple[str, str], Dict],
    snapshot_idx: int,
) -> List[Dict]:
    """
    For each coin, compute pairwise cross-exchange spread matrix.
    This is the primary stat arb signal.
    """
    records = []
    ts = _now_iso()

    for coin in ACTIVE_COINS:
        # Gather all exchanges with valid price_usd for this coin
        ex_prices = {}
        for (ex, c), ticker in raw_tickers.items():
            if c == coin and ticker.get("price_usd") is not None:
                ex_prices[ex] = ticker["price_usd"]

        if len(ex_prices) < 2:
            continue

        exchanges = sorted(ex_prices.keys())
        prices_list = [ex_prices[e] for e in exchanges]

        # Global stats
        p_min = min(prices_list)
        p_max = max(prices_list)
        p_mean = sum(prices_list) / len(prices_list)
        p_spread_bps = ((p_max - p_min) / p_mean) * 10_000 if p_mean > 0 else 0

        # Find best pair
        min_ex = min(ex_prices, key=ex_prices.get)
        max_ex = max(ex_prices, key=ex_prices.get)

        # Pairwise spreads (upper triangle)
        pairwise = []
        for i in range(len(exchanges)):
            for j in range(i + 1, len(exchanges)):
                e1, e2 = exchanges[i], exchanges[j]
                p1, p2 = ex_prices[e1], ex_prices[e2]
                spread = abs(p2 - p1)
                spread_bps = (spread / ((p1 + p2) / 2)) * 10_000
                pairwise.append({
                    "ex1": e1,
                    "ex2": e2,
                    "p1": round(p1, 8),
                    "p2": round(p2, 8),
                    "spread_abs": round(spread, 8),
                    "spread_bps": round(spread_bps, 2),
                })

        rec = {
            "type": "spread_matrix",
            "ts": ts,
            "snapshot_idx": snapshot_idx,
            "coin": coin,
            "num_exchanges": len(exchanges),
            "price_min": round(p_min, 8),
            "price_max": round(p_max, 8),
            "price_mean": round(p_mean, 8),
            "total_spread_bps": round(p_spread_bps, 2),
            "cheapest_exchange": min_ex,
            "most_expensive_exchange": max_ex,
            "pairwise_spreads": pairwise,
        }
        records.append(rec)

    return records


# ---------------------------------------------------------------------------
# Non-public signals: funding rates, OI, withdrawal status, exchange health
# ---------------------------------------------------------------------------

def collect_funding_rates(snapshot_idx: int) -> List[Dict]:
    """
    Fetch perpetual funding rates for stablecoin perp contracts.
    Shows market positioning — negative = shorts pay longs (USDC expected to rise).
    """
    records = []
    ts = _now_iso()

    for ex_name, ex in EXCHANGES.items():
        if not ex.has.get("fetchFundingRate", False):
            continue

        for sym in ACTIVE_PERPS:
            try:
                fr = ex.fetch_funding_rate(sym)
                rec = {
                    "type": "funding_rate",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "symbol": sym,
                    "funding_rate": fr.get("fundingRate"),
                    "funding_datetime": fr.get("fundingDatetime"),
                    "funding_timestamp": fr.get("fundingTimestamp"),
                    "next_funding_datetime": fr.get("nextFundingDatetime"),
                    "next_funding_timestamp": fr.get("nextFundingTimestamp"),
                    "next_funding_rate": fr.get("nextFundingRate"),
                    "mark_price": fr.get("markPrice"),
                    "index_price": fr.get("indexPrice"),
                    "interest_rate": fr.get("interestRate"),
                }
                records.append(rec)
            except Exception:
                pass  # Symbol may not exist on this exchange

    return records


def collect_open_interest(snapshot_idx: int) -> List[Dict]:
    """
    Fetch open interest for stablecoin perpetual contracts.
    OI spikes precede funding rate moves and liquidity shifts.
    """
    records = []
    ts = _now_iso()

    for ex_name, ex in EXCHANGES.items():
        if not ex.has.get("fetchOpenInterest", False):
            continue

        for sym in ACTIVE_PERPS:
            try:
                oi = ex.fetch_open_interest(sym)
                rec = {
                    "type": "open_interest",
                    "ts": ts,
                    "snapshot_idx": snapshot_idx,
                    "exchange": ex_name,
                    "symbol": sym,
                    "open_interest_amount": oi.get("openInterestAmount"),
                    "open_interest_value": oi.get("openInterestValue"),
                    "datetime": oi.get("datetime"),
                }
                records.append(rec)
            except Exception:
                pass

    return records


def collect_withdrawal_status(snapshot_idx: int) -> List[Dict]:
    """
    Fetch deposit/withdrawal enable/disable status per coin per chain.
    When withdrawals are disabled, trapped capital creates price dislocations.
    Changes in fees are also captured here.
    """
    records = []
    ts = _now_iso()

    for ex_name, ex in EXCHANGES.items():
        try:
            currencies = ex.fetch_currencies()
        except Exception:
            continue

        for coin in ACTIVE_COINS:
            c = currencies.get(coin)
            if not c:
                continue

            networks = c.get("networks") or {}
            net_records = []
            for net_name, net_info in networks.items():
                limits = net_info.get("limits", {})
                w_limits = limits.get("withdraw", {})
                d_limits = limits.get("deposit", {})
                net_records.append({
                    "network": net_name,
                    "active": net_info.get("active"),
                    "deposit": net_info.get("deposit"),
                    "withdraw": net_info.get("withdraw"),
                    "fee": net_info.get("fee"),
                    "withdraw_min": w_limits.get("min"),
                    "withdraw_max": w_limits.get("max"),
                    "deposit_min": d_limits.get("min"),
                })

            rec = {
                "type": "withdrawal_status",
                "ts": ts,
                "snapshot_idx": snapshot_idx,
                "exchange": ex_name,
                "coin": coin,
                "active": c.get("active"),
                "deposit": c.get("deposit"),
                "withdraw": c.get("withdraw"),
                "num_networks": len(net_records),
                "networks": net_records,
            }
            records.append(rec)

    return records


def collect_exchange_status(snapshot_idx: int) -> List[Dict]:
    """
    Fetch exchange operational status (ok/maintenance/error).
    Maintenance windows cause temporary price dislocations.
    """
    records = []
    ts = _now_iso()

    for ex_name, ex in EXCHANGES.items():
        if not ex.has.get("fetchStatus", False):
            continue
        try:
            status = ex.fetch_status()
            rec = {
                "type": "exchange_status",
                "ts": ts,
                "snapshot_idx": snapshot_idx,
                "exchange": ex_name,
                "status": status.get("status"),
                "updated": status.get("updated"),
                "message": status.get("info", {}).get("msg") if isinstance(status.get("info"), dict) else None,
            }
            records.append(rec)
        except Exception:
            pass

    return records


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------

class DataWriter:
    """Manages JSONL output files with crash-safe flushing."""

    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._files: Dict[str, Any] = {}

    def _get_file(self, data_type: str):
        if data_type not in self._files:
            path = self.output_dir / f"{data_type}.jsonl"
            self._files[data_type] = open(path, "a", encoding="utf-8")
        return self._files[data_type]

    def write(self, records: List[Dict]):
        for rec in records:
            data_type = rec.get("type", "unknown")
            f = self._get_file(data_type)
            f.write(json.dumps(rec, default=str) + "\n")
            f.flush()

    def close(self):
        for f in self._files.values():
            f.close()
        self._files.clear()


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Multi-signal stat arb data collector")
    parser.add_argument("--interval", type=int, default=DEFAULT_INTERVAL_SEC,
                        help=f"Seconds between snapshots (default: {DEFAULT_INTERVAL_SEC})")
    parser.add_argument("--hours", type=float, default=DEFAULT_HOURS,
                        help=f"Total hours to run (default: {DEFAULT_HOURS})")
    parser.add_argument("--ob-depth", type=int, default=DEFAULT_OB_DEPTH,
                        help=f"Order book depth per side (default: {DEFAULT_OB_DEPTH})")
    parser.add_argument("--candles", type=int, default=DEFAULT_OHLCV_CANDLES,
                        help=f"Number of 1m OHLCV candles (default: {DEFAULT_OHLCV_CANDLES})")
    parser.add_argument("--trades", type=int, default=DEFAULT_TRADES_LIMIT,
                        help=f"Recent trades limit (default: {DEFAULT_TRADES_LIMIT})")
    parser.add_argument("--skip-orderbook", action="store_true",
                        help="Skip order book collection (faster snapshots)")
    parser.add_argument("--skip-ohlcv", action="store_true",
                        help="Skip OHLCV collection")
    parser.add_argument("--skip-trades", action="store_true",
                        help="Skip trades collection")
    parser.add_argument("--skip-funding", action="store_true",
                        help="Skip funding rate collection")
    parser.add_argument("--skip-oi", action="store_true",
                        help="Skip open interest collection")
    parser.add_argument("--skip-withdrawal-status", action="store_true",
                        help="Skip withdrawal/deposit status collection")
    parser.add_argument("--skip-exchange-status", action="store_true",
                        help="Skip exchange health status collection")
    parser.add_argument("--assets", type=str, default="stablecoins",
                        choices=["stablecoins", "volatile", "all"],
                        help="Asset group to collect (default: stablecoins)")
    parser.add_argument("--output-dir", type=str, default=None,
                        help="Custom output directory")
    parser.add_argument("--resume", type=str, default=None, metavar="DIR",
                        help="Resume a previous run from its output directory")
    args = parser.parse_args()

    # --- Resolve asset configuration ---
    global ACTIVE_COINS, ACTIVE_PERPS
    ACTIVE_COINS, ACTIVE_PERPS = _resolve_asset_config(args.assets)
    print(f"  [CONFIG] Asset mode: {args.assets} → {len(ACTIVE_COINS)} coins, {len(ACTIVE_PERPS)} perps")

    # --- Resume or fresh start ---
    if args.resume:
        out_dir = Path(args.resume)
        state_file = out_dir / "_state.json"
        if not state_file.exists():
            print(f"[ERROR] No _state.json in {out_dir}, cannot resume.")
            sys.exit(1)
        with open(state_file) as f:
            state = json.load(f)
        snapshot_idx = state["snapshot_idx"]
        # Restore skip flags and params from original config
        cfg = state.get("config", {})
        args.interval = cfg.get("interval_sec", args.interval)
        args.hours = cfg.get("hours", args.hours)
        args.ob_depth = cfg.get("ob_depth", args.ob_depth)
        args.candles = cfg.get("candles", args.candles)
        args.trades = cfg.get("trades_limit", args.trades)
        args.skip_orderbook = cfg.get("skip_orderbook", args.skip_orderbook)
        args.skip_ohlcv = cfg.get("skip_ohlcv", args.skip_ohlcv)
        args.skip_trades = cfg.get("skip_trades", args.skip_trades)
        args.skip_funding = cfg.get("skip_funding", args.skip_funding)
        args.skip_oi = cfg.get("skip_oi", args.skip_oi)
        args.skip_withdrawal_status = cfg.get("skip_withdrawal_status", args.skip_withdrawal_status)
        args.skip_exchange_status = cfg.get("skip_exchange_status", args.skip_exchange_status)
        # Restore asset mode
        resumed_mode = cfg.get("asset_mode", "stablecoins")
        ACTIVE_COINS, ACTIVE_PERPS = _resolve_asset_config(resumed_mode)
        print(f"  [RESUME] Asset mode: {resumed_mode} \u2192 {len(ACTIVE_COINS)} coins, {len(ACTIVE_PERPS)} perps")
        # Compute remaining time
        original_start = datetime.fromisoformat(state["start_ts"])
        elapsed_h = (datetime.now(timezone.utc) - original_start).total_seconds() / 3600
        remaining_h = max(0, args.hours - elapsed_h)
        total_sec = remaining_h * 3600
        end_time = time.time() + total_sec
        expected_snapshots = snapshot_idx + int(total_sec / args.interval)
        run_id = out_dir.name
        writer = DataWriter(out_dir)
        # Log resume event
        writer.write([{
            "type": "run_config",
            "event": "resume",
            "resume_ts": _now_iso(),
            "resumed_from_snapshot": snapshot_idx,
            "remaining_hours": round(remaining_h, 3),
        }])
        print(f"[RESUME] Continuing from snapshot {snapshot_idx}, {remaining_h:.2f}h remaining")
    else:
        # Fresh start
        run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        if args.output_dir:
            out_dir = Path(args.output_dir)
        else:
            out_dir = (
                Path(__file__).resolve().parent.parent
                / "data"
                / "statarb"
                / run_id
            )

        writer = DataWriter(out_dir)

        # Write run config
        config = {
            "type": "run_config",
            "run_id": run_id,
            "start_ts": _now_iso(),
            "interval_sec": args.interval,
            "hours": args.hours,
            "ob_depth": args.ob_depth,
            "candles": args.candles,
            "trades_limit": args.trades,
            "skip_orderbook": args.skip_orderbook,
            "skip_ohlcv": args.skip_ohlcv,
            "skip_trades": args.skip_trades,
            "skip_funding": args.skip_funding,
            "skip_oi": args.skip_oi,
            "skip_withdrawal_status": args.skip_withdrawal_status,
            "skip_exchange_status": args.skip_exchange_status,
            "exchanges": list(EXCHANGES.keys()),
            "coins": list(ACTIVE_COINS),
            "perp_symbols": list(ACTIVE_PERPS),
            "asset_mode": args.assets,
        }
        writer.write([config])

        total_sec = args.hours * 3600
        end_time = time.time() + total_sec
        expected_snapshots = int(total_sec / args.interval)
        snapshot_idx = 0

    # State file for crash recovery
    _state_file = out_dir / "_state.json"
    _state_config = {
        "interval_sec": args.interval,
        "hours": args.hours,
        "ob_depth": args.ob_depth,
        "candles": args.candles,
        "trades_limit": args.trades,
        "skip_orderbook": args.skip_orderbook,
        "skip_ohlcv": args.skip_ohlcv,
        "skip_trades": args.skip_trades,
        "skip_funding": args.skip_funding,
        "skip_oi": args.skip_oi,
        "skip_withdrawal_status": args.skip_withdrawal_status,
        "skip_exchange_status": args.skip_exchange_status,
    }
    _state_start_ts = _now_iso() if not args.resume else state["start_ts"]

    def _save_state(snap_idx: int):
        """Save checkpoint so we can resume after crash/sleep."""
        s = {
            "snapshot_idx": snap_idx,
            "last_ts": _now_iso(),
            "start_ts": _state_start_ts,
            "config": _state_config,
        }
        tmp = _state_file.with_suffix(".tmp")
        with open(tmp, "w") as f:
            json.dump(s, f)
        tmp.replace(_state_file)  # atomic on Windows NTFS

    print(f"=== Stat Arb Data Collector ===")
    print(f"  Output: {out_dir}")
    print(f"  Interval: {args.interval}s | Duration: {args.hours}h")
    print(f"  Expected snapshots: ~{expected_snapshots}")
    print(f"  Signals: ticker", end="")
    if not args.skip_orderbook:
        print(f" + orderbook(L{args.ob_depth})", end="")
    if not args.skip_ohlcv:
        print(f" + ohlcv(1m×{args.candles})", end="")
    if not args.skip_trades:
        print(f" + trades({args.trades})", end="")
    if not args.skip_funding:
        print(f" + funding_rates", end="")
    if not args.skip_oi:
        print(f" + open_interest", end="")
    if not args.skip_withdrawal_status:
        print(f" + withdrawal_status", end="")
    if not args.skip_exchange_status:
        print(f" + exchange_status", end="")
    print(f" + spread_matrix")
    print(f"  Press Ctrl+C to stop gracefully.\n")

    _prevent_sleep()

    try:
        while _RUNNING and time.time() < end_time:
            snapshot_idx += 1
            snap_start = time.time()

            # 1) Tickers (always — foundation of everything else)
            ticker_recs, raw_tickers = collect_tickers(snapshot_idx)
            writer.write(ticker_recs)
            valid_tickers = sum(1 for r in ticker_recs if "error" not in r)

            # 2) Order books
            ob_count = 0
            if not args.skip_orderbook:
                ob_recs = collect_orderbooks(snapshot_idx, depth=args.ob_depth)
                writer.write(ob_recs)
                ob_count = sum(1 for r in ob_recs if "error" not in r)

            # 3) OHLCV
            ohlcv_count = 0
            if not args.skip_ohlcv:
                ohlcv_recs = collect_ohlcv(snapshot_idx, num_candles=args.candles)
                writer.write(ohlcv_recs)
                ohlcv_count = sum(1 for r in ohlcv_recs if "error" not in r)

            # 4) Recent trades
            trade_count = 0
            if not args.skip_trades:
                trade_recs = collect_trades(snapshot_idx, limit=args.trades)
                writer.write(trade_recs)
                trade_count = sum(1 for r in trade_recs if "error" not in r)

            # 5) Funding rates
            fr_count = 0
            if not args.skip_funding:
                fr_recs = collect_funding_rates(snapshot_idx)
                writer.write(fr_recs)
                fr_count = len(fr_recs)

            # 6) Open interest
            oi_count = 0
            if not args.skip_oi:
                oi_recs = collect_open_interest(snapshot_idx)
                writer.write(oi_recs)
                oi_count = len(oi_recs)

            # 7) Withdrawal/deposit status
            ws_count = 0
            if not args.skip_withdrawal_status:
                ws_recs = collect_withdrawal_status(snapshot_idx)
                writer.write(ws_recs)
                ws_count = len(ws_recs)

            # 8) Exchange status
            es_count = 0
            if not args.skip_exchange_status:
                es_recs = collect_exchange_status(snapshot_idx)
                writer.write(es_recs)
                es_count = len(es_recs)

            # 9) Spread matrix (computed, no API calls)
            spread_recs = compute_spread_matrix(raw_tickers, snapshot_idx)
            writer.write(spread_recs)

            # Save state for crash recovery
            _save_state(snapshot_idx)

            snap_dur = time.time() - snap_start
            print(
                f"  [{snapshot_idx:>4}/{expected_snapshots}] "
                f"tick={valid_tickers} ob={ob_count} "
                f"ohlcv={ohlcv_count} trades={trade_count} "
                f"fr={fr_count} oi={oi_count} ws={ws_count} es={es_count} "
                f"spr={len(spread_recs)} "
                f"({snap_dur:.1f}s)",
                flush=True,
            )

            # Sleep until next interval
            elapsed = time.time() - snap_start
            sleep_time = max(0, args.interval - elapsed)
            if sleep_time > 0 and _RUNNING:
                time.sleep(sleep_time)

    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Interrupted by user.")
    finally:
        _allow_sleep()
        writer.close()
        print(f"\n=== Collection complete ===")
        print(f"  Snapshots: {snapshot_idx}")
        print(f"  Output: {out_dir}")


if __name__ == "__main__":
    main()
