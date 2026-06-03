"""
Limit Order Fill-Rate Tracker
=============================
Simulates passive (maker) limit orders on two exchanges and measures:
1. Fill rate: % of simulated limit orders that would have filled within N seconds
2. Fill time distribution: p50, p90, p99 time-to-fill
3. Adverse selection: correlation between fills and subsequent price movement
4. Maker fee savings vs taker: quantifies the execution cost advantage

Usage:
    python experiments/fill_rate_tracker.py --asset WIF --exchanges binance,cryptocom
    python experiments/fill_rate_tracker.py --asset PEPE --exchanges binance,mexc --duration 3600

Does NOT place real orders. Watches the order book and simulates whether a
limit order at mid-price (or best bid/ask) would have been filled by
subsequent trades/ticks.
"""

import asyncio
import argparse
import json
import sys
import os
import time
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from collections import deque
from pathlib import Path
import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.data import COIN_MARKETS
from scripts.fees import TRADING_FEES_TAKER, TRADING_FEES_MAKER

try:
    import ccxt.pro as ccxtpro
except ImportError:
    ccxtpro = None


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SimulatedOrder:
    """A simulated limit order placed at a point in time."""
    order_id: int
    exchange: str
    side: str           # "buy" or "sell"
    price: float        # limit price
    placed_at: float    # time.time()
    filled_at: float | None = None
    fill_price: float | None = None
    # Price movement after fill (adverse selection)
    mid_at_place: float = 0.0
    mid_at_fill: float | None = None
    mid_1s_after_fill: float | None = None
    mid_5s_after_fill: float | None = None


@dataclass
class FillStats:
    """Aggregate fill statistics for one exchange."""
    exchange: str = ""
    total_orders: int = 0
    filled_orders: int = 0
    fill_rate_pct: float = 0.0
    fill_times: list = field(default_factory=list)        # seconds to fill
    adverse_selection_bps: list = field(default_factory=list)  # bps move against us after fill
    taker_fee_bps: float = 0.0
    maker_fee_bps: float = 0.0
    fee_savings_bps: float = 0.0


@dataclass
class Config:
    asset: str = "WIF"
    exchange_a: str = "binance"
    exchange_b: str = "cryptocom"
    duration_sec: int = 3600       # how long to run (1 hour default)
    order_interval_sec: float = 5  # place simulated order every N seconds
    fill_timeout_sec: float = 30   # max time to wait for fill
    output_dir: str = "data/fill_rate"
    use_websocket: bool = True
    poll_interval_ms: int = 1000


# ---------------------------------------------------------------------------
# Fill-rate tracking engine
# ---------------------------------------------------------------------------

class FillRateTracker:
    def __init__(self, config: Config):
        self.config = config
        self.order_counter = 0

        # Per-exchange state
        self.exchanges = [config.exchange_a, config.exchange_b]
        self.last_bid: dict[str, float] = {}
        self.last_ask: dict[str, float] = {}
        self.last_mid: dict[str, float] = {}

        # Active simulated orders (waiting for fill)
        self.active_orders: list[SimulatedOrder] = []
        # Completed orders (filled or expired)
        self.completed_orders: list[SimulatedOrder] = []

        # Track mid prices for adverse selection measurement
        self.mid_history: dict[str, deque] = {
            ex: deque(maxlen=300) for ex in self.exchanges
        }

        # Timing
        self.start_time = time.time()
        self.last_order_time: dict[str, float] = {ex: 0.0 for ex in self.exchanges}

        # Output
        self.output_dir = Path(config.output_dir) / f"{config.asset}_{config.exchange_a}_{config.exchange_b}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.order_log = open(self.output_dir / "orders.jsonl", "a")

        print(f"\n{'='*60}")
        print(f"  FILL-RATE TRACKER — {config.asset}")
        print(f"  {config.exchange_a} vs {config.exchange_b}")
        print(f"  Duration: {config.duration_sec}s | Order interval: {config.order_interval_sec}s")
        print(f"  Fill timeout: {config.fill_timeout_sec}s")

        # Fee comparison
        for ex in self.exchanges:
            taker = TRADING_FEES_TAKER.get(ex, 0.001) * 10_000
            maker = TRADING_FEES_MAKER.get(ex, 0.001) * 10_000
            print(f"  {ex}: taker={taker:.1f} bps, maker={maker:.1f} bps, savings={taker-maker:.1f} bps")
        print(f"  Output: {self.output_dir}")
        print(f"{'='*60}\n")

    def on_tick(self, exchange: str, bid: float, ask: float, mid: float):
        """Process a new price update."""
        now = time.time()
        self.last_bid[exchange] = bid
        self.last_ask[exchange] = ask
        self.last_mid[exchange] = mid
        self.mid_history[exchange].append((now, mid))

        # Check if any active orders would have filled
        self._check_fills(exchange, bid, ask, now)

        # Place new simulated orders periodically
        if now - self.last_order_time[exchange] >= self.config.order_interval_sec:
            self._place_simulated_orders(exchange, bid, ask, mid, now)
            self.last_order_time[exchange] = now

        # Expire old unfilled orders
        self._expire_orders(now)

        # Update adverse selection for recently filled orders
        self._update_adverse_selection(exchange, mid, now)

    def _place_simulated_orders(self, exchange: str, bid: float, ask: float, mid: float, now: float):
        """Place simulated buy and sell limit orders at best bid/ask."""
        # Simulated BUY limit at best bid (passive)
        self.order_counter += 1
        buy_order = SimulatedOrder(
            order_id=self.order_counter,
            exchange=exchange,
            side="buy",
            price=bid,  # post at best bid
            placed_at=now,
            mid_at_place=mid,
        )
        self.active_orders.append(buy_order)

        # Simulated SELL limit at best ask (passive)
        self.order_counter += 1
        sell_order = SimulatedOrder(
            order_id=self.order_counter,
            exchange=exchange,
            side="sell",
            price=ask,  # post at best ask
            placed_at=now,
            mid_at_place=mid,
        )
        self.active_orders.append(sell_order)

    def _check_fills(self, exchange: str, bid: float, ask: float, now: float):
        """Check if price has crossed any simulated limit orders."""
        still_active = []
        for order in self.active_orders:
            if order.exchange != exchange:
                still_active.append(order)
                continue

            filled = False
            if order.side == "buy" and ask <= order.price:
                # Someone sold at or below our bid → we'd get filled
                filled = True
                order.fill_price = order.price
            elif order.side == "sell" and bid >= order.price:
                # Someone bought at or above our ask → we'd get filled
                filled = True
                order.fill_price = order.price

            if filled:
                order.filled_at = now
                order.mid_at_fill = (bid + ask) / 2
                self.completed_orders.append(order)
                self._log_order(order)
            else:
                still_active.append(order)

        self.active_orders = still_active

    def _expire_orders(self, now: float):
        """Move orders past timeout to completed (unfilled)."""
        still_active = []
        for order in self.active_orders:
            if now - order.placed_at > self.config.fill_timeout_sec:
                self.completed_orders.append(order)
                self._log_order(order)
            else:
                still_active.append(order)
        self.active_orders = still_active

    def _update_adverse_selection(self, exchange: str, mid: float, now: float):
        """Update post-fill price movement for recently filled orders."""
        for order in self.completed_orders:
            if order.exchange != exchange or order.filled_at is None:
                continue

            elapsed = now - order.filled_at
            if order.mid_1s_after_fill is None and elapsed >= 1.0:
                order.mid_1s_after_fill = mid
            if order.mid_5s_after_fill is None and elapsed >= 5.0:
                order.mid_5s_after_fill = mid

    def _log_order(self, order: SimulatedOrder):
        """Write completed order to JSONL log."""
        record = {
            "order_id": order.order_id,
            "exchange": order.exchange,
            "side": order.side,
            "price": order.price,
            "placed_at": datetime.fromtimestamp(order.placed_at, tz=timezone.utc).isoformat(),
            "filled": order.filled_at is not None,
            "fill_time_sec": round(order.filled_at - order.placed_at, 3) if order.filled_at else None,
            "mid_at_place": order.mid_at_place,
            "mid_at_fill": order.mid_at_fill,
        }
        self.order_log.write(json.dumps(record) + "\n")
        self.order_log.flush()

    def compute_stats(self) -> dict:
        """Compute aggregate fill statistics."""
        results = {}

        for ex in self.exchanges:
            orders = [o for o in self.completed_orders if o.exchange == ex]
            filled = [o for o in orders if o.filled_at is not None]

            stats = FillStats(
                exchange=ex,
                total_orders=len(orders),
                filled_orders=len(filled),
                fill_rate_pct=round(len(filled) / len(orders) * 100, 1) if orders else 0,
                taker_fee_bps=TRADING_FEES_TAKER.get(ex, 0.001) * 10_000,
                maker_fee_bps=TRADING_FEES_MAKER.get(ex, 0.001) * 10_000,
            )
            stats.fee_savings_bps = stats.taker_fee_bps - stats.maker_fee_bps

            # Fill time distribution
            fill_times = [o.filled_at - o.placed_at for o in filled]
            stats.fill_times = fill_times

            # Adverse selection (bps move against us within 5s of fill)
            for o in filled:
                if o.mid_5s_after_fill is not None and o.mid_at_fill is not None and o.mid_at_fill > 0:
                    price_move_bps = (o.mid_5s_after_fill - o.mid_at_fill) / o.mid_at_fill * 10_000
                    # For buys, adverse = price drops after fill. For sells, adverse = price rises.
                    if o.side == "buy":
                        adverse = -price_move_bps  # negative price move = adverse for buyer
                    else:
                        adverse = price_move_bps   # positive price move = adverse for seller
                    stats.adverse_selection_bps.append(adverse)

            results[ex] = stats

        return results

    def print_summary(self):
        """Print and save final summary."""
        stats = self.compute_stats()
        elapsed = time.time() - self.start_time

        print(f"\n{'='*60}")
        print(f"  FILL-RATE RESULTS — {self.config.asset}")
        print(f"  Runtime: {elapsed/60:.1f} min")
        print(f"{'='*60}")

        summary = {
            "asset": self.config.asset,
            "runtime_sec": round(elapsed, 1),
            "exchanges": {},
        }

        for ex, st in stats.items():
            print(f"\n  [{ex}]")
            print(f"    Orders: {st.total_orders} | Filled: {st.filled_orders} | "
                  f"Fill rate: {st.fill_rate_pct:.1f}%")

            ex_summary = {
                "total_orders": st.total_orders,
                "filled_orders": st.filled_orders,
                "fill_rate_pct": st.fill_rate_pct,
                "taker_fee_bps": st.taker_fee_bps,
                "maker_fee_bps": st.maker_fee_bps,
                "fee_savings_bps": st.fee_savings_bps,
            }

            if st.fill_times:
                ft = np.array(st.fill_times)
                print(f"    Fill time (s): p50={np.percentile(ft,50):.2f} "
                      f"p90={np.percentile(ft,90):.2f} p99={np.percentile(ft,99):.2f}")
                ex_summary["fill_time_s"] = {
                    "p50": round(float(np.percentile(ft, 50)), 3),
                    "p90": round(float(np.percentile(ft, 90)), 3),
                    "p99": round(float(np.percentile(ft, 99)), 3),
                }

            if st.adverse_selection_bps:
                adv = np.array(st.adverse_selection_bps)
                mean_adv = np.mean(adv)
                print(f"    Adverse selection (5s): mean={mean_adv:+.2f} bps "
                      f"(positive = adverse)")
                print(f"    Fee savings: {st.fee_savings_bps:.1f} bps | "
                      f"Net edge vs taker: {st.fee_savings_bps - max(0, mean_adv):+.1f} bps")
                ex_summary["adverse_selection_bps"] = {
                    "mean": round(float(mean_adv), 2),
                    "std": round(float(np.std(adv)), 2),
                    "p25": round(float(np.percentile(adv, 25)), 2),
                    "p75": round(float(np.percentile(adv, 75)), 2),
                }
                ex_summary["net_edge_vs_taker_bps"] = round(
                    st.fee_savings_bps - max(0, mean_adv), 2
                )

            summary["exchanges"][ex] = ex_summary

        print(f"\n{'='*60}\n")

        # Save summary
        with open(self.output_dir / "fill_rate_summary.json", "w") as f:
            json.dump(summary, f, indent=2)
        print(f"  Results saved to: {self.output_dir}")

    def close(self):
        self.order_log.close()


# ---------------------------------------------------------------------------
# Feed with reconnection (reuses pattern from paper_trader.py)
# ---------------------------------------------------------------------------

async def run_feed_ws(exchange_id: str, market: str, tick_queue: asyncio.Queue):
    """WebSocket feed with auto-reconnect."""
    backoff = 1.0
    max_backoff = 60.0

    while True:
        exchange = None
        try:
            exchange_class = getattr(ccxtpro, exchange_id)
            exchange = exchange_class({"timeout": 10000})
            backoff = 1.0

            while True:
                ticker = await exchange.watch_ticker(market)
                bid = ticker.get("bid") or ticker.get("last", 0)
                ask = ticker.get("ask") or ticker.get("last", 0)
                mid = (bid + ask) / 2 if (bid and ask) else ticker.get("last", 0)

                if mid > 0:
                    await tick_queue.put((exchange_id, bid, ask, mid))

        except asyncio.CancelledError:
            break
        except Exception as e:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"  [{ts}] [RECONNECT] {exchange_id} WS: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)
        finally:
            if exchange:
                try:
                    await exchange.close()
                except Exception:
                    pass


async def run_feed_rest(exchange_id: str, market: str, tick_queue: asyncio.Queue,
                        poll_interval: float = 1.0):
    """REST polling feed with auto-reconnect."""
    import ccxt as ccxt_sync
    backoff = 1.0
    max_backoff = 60.0
    consecutive_errors = 0

    while True:
        try:
            exchange_class = getattr(ccxt_sync, exchange_id)
            exchange = exchange_class({"timeout": 5000})
            loop = asyncio.get_event_loop()
            backoff = 1.0
            consecutive_errors = 0

            while True:
                try:
                    ticker = await loop.run_in_executor(None, exchange.fetch_ticker, market)
                    bid = ticker.get("bid") or ticker.get("last", 0)
                    ask = ticker.get("ask") or ticker.get("last", 0)
                    mid = (bid + ask) / 2 if (bid and ask) else ticker.get("last", 0)

                    if mid > 0:
                        await tick_queue.put((exchange_id, bid, ask, mid))
                    consecutive_errors = 0
                    await asyncio.sleep(poll_interval)
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    consecutive_errors += 1
                    if consecutive_errors <= 3:
                        print(f"  [WARN] REST error ({exchange_id}): {e}")
                        await asyncio.sleep(poll_interval)
                    else:
                        raise
        except asyncio.CancelledError:
            break
        except Exception as e:
            ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
            print(f"  [{ts}] [RECONNECT] {exchange_id} REST: {e}")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)


async def run_feed(exchange_id: str, market: str, tick_queue: asyncio.Queue,
                   use_ws: bool = True, poll_interval: float = 1.0):
    """Try WS first, fall back to REST. Both auto-reconnect."""
    if use_ws and ccxtpro is not None:
        try:
            exchange_class = getattr(ccxtpro, exchange_id)
            exchange = exchange_class({"timeout": 10000})
            await asyncio.wait_for(exchange.watch_ticker(market), timeout=10)
            await exchange.close()
            print(f"  [{exchange_id}] WebSocket connected OK")
            await run_feed_ws(exchange_id, market, tick_queue)
            return
        except Exception as e:
            print(f"  [{exchange_id}] WebSocket failed ({e}), falling back to REST")

    await run_feed_rest(exchange_id, market, tick_queue, poll_interval)


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

async def run_tracker(config: Config):
    """Main async loop."""
    tracker = FillRateTracker(config)

    market_a = COIN_MARKETS.get(config.asset, {}).get(config.exchange_a)
    market_b = COIN_MARKETS.get(config.asset, {}).get(config.exchange_b)

    if not market_a or not market_b:
        print(f"ERROR: No market for {config.asset} on {config.exchange_a} or {config.exchange_b}")
        return

    print(f"  Markets: {config.exchange_a}={market_a}, {config.exchange_b}={market_b}")
    print(f"  Running for {config.duration_sec}s...\n")

    tick_queue = asyncio.Queue()

    feed_a = asyncio.create_task(run_feed(config.exchange_a, market_a, tick_queue,
                                          use_ws=config.use_websocket,
                                          poll_interval=config.poll_interval_ms / 1000))
    feed_b = asyncio.create_task(run_feed(config.exchange_b, market_b, tick_queue,
                                          use_ws=config.use_websocket,
                                          poll_interval=config.poll_interval_ms / 1000))

    last_status = time.time()
    status_interval = 120  # every 2 min

    try:
        while time.time() - tracker.start_time < config.duration_sec:
            try:
                exchange_id, bid, ask, mid = await asyncio.wait_for(tick_queue.get(), timeout=1.0)
                tracker.on_tick(exchange_id, bid, ask, mid)
            except asyncio.TimeoutError:
                pass

            if time.time() - last_status > status_interval:
                elapsed = time.time() - tracker.start_time
                remaining = config.duration_sec - elapsed
                n_filled = sum(1 for o in tracker.completed_orders if o.filled_at is not None)
                n_total = len(tracker.completed_orders) + len(tracker.active_orders)
                rate = n_filled / n_total * 100 if n_total > 0 else 0
                print(f"  [{elapsed/60:.0f}m] Orders: {n_total} | "
                      f"Filled: {n_filled} ({rate:.0f}%) | "
                      f"Remaining: {remaining/60:.0f}m")
                last_status = time.time()

    except asyncio.CancelledError:
        pass
    finally:
        feed_a.cancel()
        feed_b.cancel()
        await asyncio.gather(feed_a, feed_b, return_exceptions=True)

        tracker.print_summary()
        tracker.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Limit order fill-rate tracker")
    parser.add_argument("--asset", default="WIF")
    parser.add_argument("--exchanges", default="binance,cryptocom",
                        help="Comma-separated exchange pair")
    parser.add_argument("--duration", type=int, default=3600,
                        help="Duration in seconds (default: 1 hour)")
    parser.add_argument("--order-interval", type=float, default=5,
                        help="Seconds between simulated order placements")
    parser.add_argument("--fill-timeout", type=float, default=30,
                        help="Max seconds to wait for fill")
    parser.add_argument("--no-ws", action="store_true",
                        help="Force REST polling")
    parser.add_argument("--poll-interval", type=int, default=1000,
                        help="REST poll interval in ms")
    parser.add_argument("--output-dir", default="data/fill_rate")

    args = parser.parse_args()
    exchanges = args.exchanges.split(",")
    if len(exchanges) != 2:
        print("ERROR: --exchanges must be exactly two comma-separated exchange IDs")
        sys.exit(1)

    config = Config(
        asset=args.asset.upper(),
        exchange_a=exchanges[0].strip(),
        exchange_b=exchanges[1].strip(),
        duration_sec=args.duration,
        order_interval_sec=args.order_interval,
        fill_timeout_sec=args.fill_timeout,
        output_dir=args.output_dir,
        use_websocket=not args.no_ws,
        poll_interval_ms=args.poll_interval,
    )

    print(f"\n  Starting fill-rate tracker at {datetime.now(timezone.utc).isoformat()}")
    print(f"  Auto-reconnect: ENABLED")
    print(f"  Press Ctrl+C to stop early.\n")

    try:
        asyncio.run(run_tracker(config))
    except KeyboardInterrupt:
        print("\n  Shutting down...")


if __name__ == "__main__":
    main()
