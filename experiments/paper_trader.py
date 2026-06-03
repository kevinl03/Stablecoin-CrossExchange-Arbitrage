"""
Live Paper Trading System for Cross-Exchange Stat-Arb

Uses ccxt.pro WebSocket feeds to get real-time bid/ask prices,
runs OU/z-score signals on the live spread, and simulates trades
with realistic execution assumptions (slippage, latency).

Usage:
    python experiments/paper_trader.py --asset WIF --exchanges binance,cryptocom --strategy ou
    python experiments/paper_trader.py --asset PEPE --exchanges binance,cryptocom --strategy zscore
    python experiments/paper_trader.py --asset CRV --exchanges cryptocom,mexc --strategy ou

Press Ctrl+C to stop gracefully.
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

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.fees import TRADING_FEES_TAKER
from scripts.data import COIN_MARKETS

import ccxt.pro as ccxtpro


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@dataclass
class Config:
    asset: str = "WIF"
    exchange_a: str = "binance"       # "fast" exchange (price leader)
    exchange_b: str = "cryptocom"     # "slow" exchange (price lagger)
    strategy: str = "ou"              # "ou" or "zscore"
    # Strategy params
    entry_z: float = 2.0
    exit_z: float = 0.0               # 0.0 = wait for full mean reversion
    warmup: int = 60                  # seconds of data before trading
    max_holding_sec: int = 300        # max hold time (5 min)
    vol_filter_mult: float = 0.8      # only trade when spread_std > mult * cost
    cooldown_ticks: int = 0           # min ticks between trades
    # OU params (rolling window for estimation)
    ou_window: int = 60              # seconds for OU param estimation
    zscore_window: int = 60           # ticks for rolling z-score (was 30)
    # Execution
    slippage_bps: float = 2.0         # additional slippage per side
    capital_usd: float = 1000.0       # notional per trade
    max_position: int = 1             # max concurrent positions
    # Logging
    output_dir: str = "data/paper_trading"
    poll_interval_ms: int = 1000      # REST polling interval (ms)
    use_websocket: bool = True        # try WS first, fallback to REST


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Tick:
    ts: float           # unix timestamp
    exchange: str
    bid: float
    ask: float
    mid: float


@dataclass
class Position:
    entry_time: float
    direction: str      # "long_spread" or "short_spread"
    entry_spread: float
    entry_price_a: float  # mid on exchange A at entry
    entry_price_b: float  # mid on exchange B at entry
    entry_bid_a: float
    entry_ask_a: float
    entry_bid_b: float
    entry_ask_b: float


@dataclass
class Trade:
    entry_time: str
    exit_time: str
    direction: str
    entry_spread_bps: float
    exit_spread_bps: float
    gross_pnl_bps: float
    fee_bps: float
    slippage_bps: float
    net_pnl_bps: float
    holding_sec: float
    exit_reason: str  # "signal", "timeout", "manual"


@dataclass
class State:
    position: Position | None = None
    trades: list = field(default_factory=list)
    spread_history: deque = field(default_factory=lambda: deque(maxlen=600))
    tick_count: int = 0
    start_time: float = 0.0
    total_net_pnl_bps: float = 0.0


# ---------------------------------------------------------------------------
# Signal generators
# ---------------------------------------------------------------------------

def estimate_ou_params(spreads: np.ndarray, dt: float = 1.0):
    """Estimate OU parameters from spread time series."""
    if len(spreads) < 20:
        return None, None, None

    S = spreads[:-1]
    dS = np.diff(spreads)

    # OLS: dS = a + b*S + residual
    X = np.column_stack([np.ones(len(S)), S])
    try:
        beta = np.linalg.lstsq(X, dS, rcond=None)[0]
    except np.linalg.LinAlgError:
        return None, None, None

    a, b = beta
    if b >= 0:
        return None, None, None  # not mean-reverting

    theta = -b / dt
    mu = a / (theta * dt)
    residuals = dS - X @ beta
    sigma = np.std(residuals) / np.sqrt(dt)

    if sigma < 1e-10:
        return None, None, None

    return theta, mu, sigma


def compute_zscore_rolling(spreads: np.ndarray, window: int):
    """Compute z-score of last spread relative to rolling window."""
    if len(spreads) < window:
        return None
    recent = spreads[-window:]
    mu = np.mean(recent)
    sigma = np.std(recent)
    if sigma < 1e-10:
        return None
    return (spreads[-1] - mu) / sigma


def compute_ou_zscore(spreads: np.ndarray, window: int):
    """Compute z-score using OU-estimated parameters."""
    if len(spreads) < window:
        return None
    recent = spreads[-window:]
    theta, mu, sigma = estimate_ou_params(recent)
    if theta is None:
        return None
    current = spreads[-1]
    z = (current - mu) / sigma
    return z


# ---------------------------------------------------------------------------
# Execution simulator
# ---------------------------------------------------------------------------

def compute_entry_cost(config: Config):
    """Total cost per round-trip in bps (fees + slippage)."""
    fee_a = TRADING_FEES_TAKER.get(config.exchange_a, 0.001)
    fee_b = TRADING_FEES_TAKER.get(config.exchange_b, 0.001)
    total_fee_bps = (fee_a + fee_b) * 10_000
    total_slippage_bps = config.slippage_bps * 2  # both sides
    return total_fee_bps, total_slippage_bps


def compute_spread_bps(mid_a: float, mid_b: float) -> float:
    """Spread in bps: (B - A) / A * 10000."""
    if mid_a <= 0:
        return 0.0
    return (mid_b - mid_a) / mid_a * 10_000


# ---------------------------------------------------------------------------
# Paper trading engine
# ---------------------------------------------------------------------------

class PaperTrader:
    def __init__(self, config: Config):
        self.config = config
        self.state = State(start_time=time.time())
        self.fee_bps, self.slippage_bps = compute_entry_cost(config)
        self.total_cost_bps = self.fee_bps + self.slippage_bps

        # Latest ticks
        self.last_tick_a: Tick | None = None
        self.last_tick_b: Tick | None = None

        # Output
        self.output_dir = Path(config.output_dir) / f"{config.asset}_{config.exchange_a}_{config.exchange_b}_{config.strategy}"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.trade_log = open(self.output_dir / "trades.jsonl", "a")
        self.tick_log = open(self.output_dir / "ticks.jsonl", "a")
        self.signal_log = open(self.output_dir / "signals.jsonl", "a")

        print(f"\n{'='*60}")
        print(f"  PAPER TRADER — {config.asset}")
        print(f"  {config.exchange_a} (fast) vs {config.exchange_b} (slow)")
        print(f"  Strategy: {config.strategy.upper()}")
        print(f"  Entry z: {config.entry_z}, Exit z: {config.exit_z}")
        print(f"  Fee: {self.fee_bps:.1f} bps, Slippage: {self.slippage_bps:.1f} bps")
        self.vol_threshold = config.vol_filter_mult * self.total_cost_bps
        self.last_trade_tick = -config.cooldown_ticks - 1

        print(f"  Total cost per round-trip: {self.total_cost_bps:.1f} bps")
        print(f"  Vol filter: spread_std > {config.vol_filter_mult}x cost = {self.vol_threshold:.1f} bps")
        print(f"  Cooldown: {config.cooldown_ticks} ticks between trades")
        print(f"  Capital: ${config.capital_usd:.0f} per trade")
        print(f"  Max hold: {config.max_holding_sec}s")
        print(f"  Output: {self.output_dir}")
        print(f"{'='*60}\n")

    def on_tick(self, tick: Tick):
        """Process a new tick from either exchange."""
        if tick.exchange == self.config.exchange_a:
            self.last_tick_a = tick
        else:
            self.last_tick_b = tick
        self.state.tick_count += 1

        # Log tick
        self.tick_log.write(json.dumps({
            "ts": datetime.fromtimestamp(tick.ts, tz=timezone.utc).isoformat(),
            "exchange": tick.exchange,
            "bid": tick.bid,
            "ask": tick.ask,
            "mid": tick.mid,
        }) + "\n")
        self.tick_log.flush()

        # Only compute spread when we have both sides
        if self.last_tick_a is None or self.last_tick_b is None:
            return

        # Check staleness (>10s old = skip)
        now = time.time()
        if abs(now - self.last_tick_a.ts) > 10 or abs(now - self.last_tick_b.ts) > 10:
            return

        spread_bps = compute_spread_bps(self.last_tick_a.mid, self.last_tick_b.mid)
        self.state.spread_history.append((now, spread_bps))

    def check_signals(self):
        """Check strategy signals and manage positions."""
        if len(self.state.spread_history) < self.config.warmup:
            return

        spreads = np.array([s[1] for s in self.state.spread_history])
        now = time.time()

        # Compute z-score based on strategy
        if self.config.strategy == "ou":
            z = compute_ou_zscore(spreads, self.config.ou_window)
        else:
            z = compute_zscore_rolling(spreads, self.config.zscore_window)

        if z is None:
            # Debug: print why signal is None every 30 checks
            if self.state.tick_count % 30 == 0:
                std = np.std(spreads)
                print(f"  [DEBUG] z=None | spreads={len(spreads)} | std={std:.2f} bps | "
                      f"range=[{spreads.min():.2f}, {spreads.max():.2f}]")
            return

        current_spread = spreads[-1]
        rolling_std = np.std(spreads[-self.config.zscore_window:]) if len(spreads) >= self.config.zscore_window else np.std(spreads)

        # Log signal
        self.signal_log.write(json.dumps({
            "ts": datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            "spread_bps": round(current_spread, 2),
            "z_score": round(z, 4),
            "rolling_std": round(rolling_std, 2),
            "position": self.state.position.direction if self.state.position else None,
        }) + "\n")
        self.signal_log.flush()

        # Position management
        if self.state.position is None:
            # Cooldown check
            if self.state.tick_count - self.last_trade_tick < self.config.cooldown_ticks:
                return
            # Volatility filter: skip low-vol regimes
            if self.config.vol_filter_mult > 0 and rolling_std < self.vol_threshold:
                return
            # Entry logic
            if z > self.config.entry_z:
                self._open_position("short_spread", current_spread)
            elif z < -self.config.entry_z:
                self._open_position("long_spread", current_spread)
        else:
            # Exit logic
            pos = self.state.position
            holding_time = now - pos.entry_time

            exit_reason = None
            if pos.direction == "short_spread" and z < self.config.exit_z:
                exit_reason = "signal"
            elif pos.direction == "long_spread" and z > -self.config.exit_z:
                exit_reason = "signal"
            elif holding_time > self.config.max_holding_sec:
                exit_reason = "timeout"

            if exit_reason:
                self._close_position(current_spread, exit_reason)

    def _open_position(self, direction: str, spread_bps: float):
        """Open a paper position."""
        if self.last_tick_a is None or self.last_tick_b is None:
            return

        self.state.position = Position(
            entry_time=time.time(),
            direction=direction,
            entry_spread=spread_bps,
            entry_price_a=self.last_tick_a.mid,
            entry_price_b=self.last_tick_b.mid,
            entry_bid_a=self.last_tick_a.bid,
            entry_ask_a=self.last_tick_a.ask,
            entry_bid_b=self.last_tick_b.bid,
            entry_ask_b=self.last_tick_b.ask,
        )

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"  [{ts}] OPEN {direction} | spread={spread_bps:+.1f} bps | "
              f"A={self.last_tick_a.mid:.6f} B={self.last_tick_b.mid:.6f}")

    def _close_position(self, exit_spread_bps: float, reason: str):
        """Close paper position and record trade."""
        pos = self.state.position
        if pos is None:
            return

        now = time.time()
        holding_sec = now - pos.entry_time

        # PnL calculation
        if pos.direction == "short_spread":
            # Entered when spread was high, exit when low → profit = entry - exit
            gross_pnl = pos.entry_spread - exit_spread_bps
        else:
            # Entered when spread was low, exit when high → profit = exit - entry
            gross_pnl = exit_spread_bps - pos.entry_spread

        net_pnl = gross_pnl - self.fee_bps - self.slippage_bps

        trade = Trade(
            entry_time=datetime.fromtimestamp(pos.entry_time, tz=timezone.utc).isoformat(),
            exit_time=datetime.fromtimestamp(now, tz=timezone.utc).isoformat(),
            direction=pos.direction,
            entry_spread_bps=round(pos.entry_spread, 2),
            exit_spread_bps=round(exit_spread_bps, 2),
            gross_pnl_bps=round(gross_pnl, 2),
            fee_bps=round(self.fee_bps, 2),
            slippage_bps=round(self.slippage_bps, 2),
            net_pnl_bps=round(net_pnl, 2),
            holding_sec=round(holding_sec, 1),
            exit_reason=reason,
        )

        self.state.trades.append(trade)
        self.state.total_net_pnl_bps += net_pnl
        self.state.position = None
        self.last_trade_tick = self.state.tick_count

        # Log
        self.trade_log.write(json.dumps(asdict(trade)) + "\n")
        self.trade_log.flush()

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        win = "WIN" if net_pnl > 0 else "LOSS"
        print(f"  [{ts}] CLOSE {pos.direction} | {win} net={net_pnl:+.1f} bps | "
              f"gross={gross_pnl:+.1f} cost={self.total_cost_bps:.1f} | "
              f"hold={holding_sec:.0f}s | reason={reason} | "
              f"cumulative={self.state.total_net_pnl_bps:+.1f} bps")

    def print_status(self):
        """Print periodic status update."""
        elapsed = time.time() - self.state.start_time
        n_trades = len(self.state.trades)
        wins = sum(1 for t in self.state.trades if t.net_pnl_bps > 0)
        win_rate = (wins / n_trades * 100) if n_trades > 0 else 0

        spread_std = 0
        if len(self.state.spread_history) > 10:
            spreads = np.array([s[1] for s in self.state.spread_history])
            spread_std = np.std(spreads)

        print(f"\n  --- STATUS ({elapsed/60:.1f} min) ---")
        print(f"  Ticks: {self.state.tick_count} | Spreads: {len(self.state.spread_history)}")
        print(f"  Spread std: {spread_std:.1f} bps | Cost: {self.total_cost_bps:.1f} bps | "
              f"Vol gate: {'OPEN' if spread_std > self.vol_threshold else 'CLOSED'} (need >{self.vol_threshold:.1f})")
        print(f"  Trades: {n_trades} | Win rate: {win_rate:.0f}% | Net PnL: {self.state.total_net_pnl_bps:+.1f} bps")
        if self.state.position:
            hold = time.time() - self.state.position.entry_time
            print(f"  Open: {self.state.position.direction} for {hold:.0f}s")
        print()

    def save_summary(self):
        """Save final summary."""
        elapsed = time.time() - self.state.start_time
        n_trades = len(self.state.trades)
        wins = sum(1 for t in self.state.trades if t.net_pnl_bps > 0)

        summary = {
            "config": asdict(self.config) if hasattr(self.config, '__dataclass_fields__') else vars(self.config),
            "runtime_sec": round(elapsed, 1),
            "total_ticks": self.state.tick_count,
            "total_trades": n_trades,
            "wins": wins,
            "losses": n_trades - wins,
            "win_rate": round(wins / n_trades * 100, 1) if n_trades > 0 else 0,
            "total_net_pnl_bps": round(self.state.total_net_pnl_bps, 2),
            "avg_pnl_per_trade_bps": round(self.state.total_net_pnl_bps / n_trades, 2) if n_trades > 0 else 0,
            "fee_bps_per_trade": self.fee_bps,
            "slippage_bps_per_trade": self.slippage_bps,
        }

        with open(self.output_dir / "summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print(f"\n{'='*60}")
        print(f"  PAPER TRADING COMPLETE")
        print(f"  Runtime: {elapsed/60:.1f} min | Trades: {n_trades}")
        print(f"  Win rate: {summary['win_rate']}% | Net PnL: {self.state.total_net_pnl_bps:+.1f} bps")
        print(f"  Avg per trade: {summary['avg_pnl_per_trade_bps']:+.1f} bps")
        print(f"  Results saved to: {self.output_dir}")
        print(f"{'='*60}\n")

    def close(self):
        """Clean up file handles."""
        self.trade_log.close()
        self.tick_log.close()
        self.signal_log.close()


# ---------------------------------------------------------------------------
# Feed managers (WebSocket primary, REST polling fallback)
# ---------------------------------------------------------------------------

async def run_feed_ws(exchange_id: str, market: str, tick_queue: asyncio.Queue):
    """Connect to exchange WebSocket and push ticks to queue."""
    exchange_class = getattr(ccxtpro, exchange_id)
    exchange = exchange_class({"timeout": 10000})

    try:
        while True:
            ticker = await exchange.watch_ticker(market)
            bid = ticker.get("bid") or ticker.get("last", 0)
            ask = ticker.get("ask") or ticker.get("last", 0)
            mid = (bid + ask) / 2 if (bid and ask) else ticker.get("last", 0)

            if mid > 0:
                tick = Tick(
                    ts=time.time(),
                    exchange=exchange_id,
                    bid=bid,
                    ask=ask,
                    mid=mid,
                )
                await tick_queue.put(tick)
    except asyncio.CancelledError:
        pass
    finally:
        await exchange.close()


async def run_feed_rest(exchange_id: str, market: str, tick_queue: asyncio.Queue,
                        poll_interval: float = 1.0):
    """Fallback: poll REST API for tickers using thread executor."""
    import ccxt as ccxt_sync

    exchange_class = getattr(ccxt_sync, exchange_id)
    exchange = exchange_class({"timeout": 5000})
    loop = asyncio.get_event_loop()

    try:
        while True:
            try:
                ticker = await loop.run_in_executor(
                    None, exchange.fetch_ticker, market
                )
                bid = ticker.get("bid") or ticker.get("last", 0)
                ask = ticker.get("ask") or ticker.get("last", 0)
                mid = (bid + ask) / 2 if (bid and ask) else ticker.get("last", 0)

                if mid > 0:
                    tick = Tick(
                        ts=time.time(),
                        exchange=exchange_id,
                        bid=bid,
                        ask=ask,
                        mid=mid,
                    )
                    await tick_queue.put(tick)
            except Exception as e:
                print(f"  [WARN] REST poll error ({exchange_id}): {e}")

            await asyncio.sleep(poll_interval)
    except asyncio.CancelledError:
        pass


async def run_feed(exchange_id: str, market: str, tick_queue: asyncio.Queue,
                   use_ws: bool = True, poll_interval: float = 1.0):
    """Try WebSocket first, fall back to REST polling."""
    if use_ws:
        try:
            # Try one WebSocket tick to see if it works
            exchange_class = getattr(ccxtpro, exchange_id)
            exchange = exchange_class({"timeout": 10000})
            ticker = await asyncio.wait_for(exchange.watch_ticker(market), timeout=10)
            await exchange.close()
            print(f"  [{exchange_id}] WebSocket connected OK")
            await run_feed_ws(exchange_id, market, tick_queue)
            return
        except Exception as e:
            print(f"  [{exchange_id}] WebSocket failed ({e}), falling back to REST polling")

    await run_feed_rest(exchange_id, market, tick_queue, poll_interval)


async def run_paper_trader(config: Config):
    """Main async loop: feeds + signal checking."""
    trader = PaperTrader(config)

    # Resolve markets
    market_a = COIN_MARKETS.get(config.asset, {}).get(config.exchange_a)
    market_b = COIN_MARKETS.get(config.asset, {}).get(config.exchange_b)

    if not market_a or not market_b:
        print(f"ERROR: No market found for {config.asset} on {config.exchange_a} or {config.exchange_b}")
        print(f"  {config.exchange_a}: {market_a}")
        print(f"  {config.exchange_b}: {market_b}")
        return

    print(f"  Markets: {config.exchange_a}={market_a}, {config.exchange_b}={market_b}")
    print(f"  Warming up ({config.warmup} ticks)...\n")

    tick_queue = asyncio.Queue()

    # Start feeds (try WS, fall back to REST)
    feed_a = asyncio.create_task(run_feed(config.exchange_a, market_a, tick_queue,
                                          use_ws=config.use_websocket,
                                          poll_interval=config.poll_interval_ms / 1000))
    feed_b = asyncio.create_task(run_feed(config.exchange_b, market_b, tick_queue,
                                          use_ws=config.use_websocket,
                                          poll_interval=config.poll_interval_ms / 1000))

    # Status timer
    last_status = time.time()
    status_interval = 60  # print status every 60s

    try:
        while True:
            try:
                tick = await asyncio.wait_for(tick_queue.get(), timeout=1.0)
                trader.on_tick(tick)
            except asyncio.TimeoutError:
                pass

            # Check signals periodically
            trader.check_signals()

            # Status update
            if time.time() - last_status > status_interval:
                trader.print_status()
                last_status = time.time()

    except asyncio.CancelledError:
        pass
    finally:
        feed_a.cancel()
        feed_b.cancel()
        await asyncio.gather(feed_a, feed_b, return_exceptions=True)

        # Close any open position at current spread
        if trader.state.position and trader.last_tick_a and trader.last_tick_b:
            current_spread = compute_spread_bps(trader.last_tick_a.mid, trader.last_tick_b.mid)
            trader._close_position(current_spread, "manual")

        trader.save_summary()
        trader.close()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Live paper trading for cross-exchange stat-arb")
    parser.add_argument("--asset", default="WIF", help="Asset to trade (WIF, CRV, PEPE)")
    parser.add_argument("--exchanges", default="binance,cryptocom",
                        help="Comma-separated exchange pair (fast,slow)")
    parser.add_argument("--strategy", default="ou", choices=["ou", "zscore"],
                        help="Strategy: ou or zscore")
    parser.add_argument("--entry-z", type=float, default=2.0, help="Entry z-score threshold")
    parser.add_argument("--exit-z", type=float, default=0.0, help="Exit z-score threshold (0=full reversion)")
    parser.add_argument("--warmup", type=int, default=60, help="Warmup ticks before trading")
    parser.add_argument("--max-hold", type=int, default=300, help="Max holding time in seconds")
    parser.add_argument("--vol-filter", type=float, default=0.8,
                        help="Vol filter: only trade when spread_std > N * cost (0=disabled)")
    parser.add_argument("--cooldown", type=int, default=0, help="Min ticks between trades")
    parser.add_argument("--slippage", type=float, default=2.0, help="Slippage per side in bps")
    parser.add_argument("--capital", type=float, default=1000.0, help="Capital per trade in USD")
    parser.add_argument("--no-ws", action="store_true", help="Force REST polling (skip WebSocket)")
    parser.add_argument("--poll-interval", type=int, default=1000, help="REST poll interval in ms")
    parser.add_argument("--output-dir", default="data/paper_trading", help="Output directory")

    args = parser.parse_args()
    exchanges = args.exchanges.split(",")
    if len(exchanges) != 2:
        print("ERROR: --exchanges must be exactly two comma-separated exchange IDs")
        sys.exit(1)

    config = Config(
        asset=args.asset.upper(),
        exchange_a=exchanges[0].strip(),
        exchange_b=exchanges[1].strip(),
        strategy=args.strategy,
        entry_z=args.entry_z,
        exit_z=args.exit_z,
        warmup=args.warmup,
        max_holding_sec=args.max_hold,
        vol_filter_mult=args.vol_filter,
        cooldown_ticks=args.cooldown,
        slippage_bps=args.slippage,
        capital_usd=args.capital,
        output_dir=args.output_dir,
        use_websocket=not args.no_ws,
        poll_interval_ms=args.poll_interval,
    )

    print(f"\n  Starting paper trader at {datetime.now(timezone.utc).isoformat()}")
    print(f"  Press Ctrl+C to stop.\n")

    try:
        asyncio.run(run_paper_trader(config))
    except KeyboardInterrupt:
        print("\n  Shutting down...")


if __name__ == "__main__":
    main()
