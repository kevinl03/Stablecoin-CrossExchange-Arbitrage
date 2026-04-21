"""
Parallel per-exchange market data service.

Spawns one background process per exchange to continuously fetch ticker
(and optionally order-book) data.  Updates flow through a
multiprocessing.Queue into a MarketDataStore that lives in the main
process.  A* and graph-building code read from the store with zero
network latency.
"""

from __future__ import annotations

import logging
import multiprocessing
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import ccxt

from scripts.data import (
    COIN_MARKETS,
    EXCHANGE_TIMEOUT_MS,
    STABLE_COINS,
    normalize_price_to_usd,
)

logger = logging.getLogger(__name__)

NodeId = Tuple[str, str]

STABLECOIN_PRICE_TOLERANCE = 0.05


# ── data containers ──────────────────────────────────────────────────

@dataclass
class TickerUpdate:
    exchange: str
    coin: str
    price_usd: float
    bid: Optional[float]
    ask: Optional[float]
    volume_24h: Optional[float]
    timestamp: float


@dataclass
class OrderBookUpdate:
    exchange: str
    coin: str
    bids: list
    asks: list
    timestamp: float


# ── shared store (main-process side) ─────────────────────────────────

class MarketDataStore:
    """Thread-safe store consumed by graph.py / heuristics / A*."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._tickers: Dict[NodeId, TickerUpdate] = {}
        self._orderbooks: Dict[NodeId, OrderBookUpdate] = {}
        self._exchange_status: Dict[str, Dict[str, Any]] = {}

    # ── writes (called by drain thread) ──

    def _apply_ticker(self, t: TickerUpdate) -> None:
        key: NodeId = (t.exchange, t.coin)
        with self._lock:
            self._tickers[key] = t
            status = self._exchange_status.setdefault(t.exchange, {})
            status["last_update"] = t.timestamp
            status["error_count"] = status.get("error_count", 0)

    def _apply_orderbook(self, ob: OrderBookUpdate) -> None:
        key: NodeId = (ob.exchange, ob.coin)
        with self._lock:
            self._orderbooks[key] = ob

    def _record_error(self, exchange: str) -> None:
        with self._lock:
            status = self._exchange_status.setdefault(exchange, {})
            status["error_count"] = status.get("error_count", 0) + 1

    # ── reads (called by graph / heuristics) ──

    def get_price(self, exchange: str, coin: str) -> Optional[float]:
        with self._lock:
            t = self._tickers.get((exchange, coin))
            return t.price_usd if t else None

    def get_ticker(self, exchange: str, coin: str) -> Optional[TickerUpdate]:
        with self._lock:
            return self._tickers.get((exchange, coin))

    def get_price_snapshot(self) -> Dict[NodeId, float]:
        """Return shape matching ``graph.fetch_price_snapshot``."""
        with self._lock:
            return {k: t.price_usd for k, t in self._tickers.items()}

    def get_volume(self, exchange: str, coin: str) -> Optional[float]:
        with self._lock:
            t = self._tickers.get((exchange, coin))
            return t.volume_24h if t else None

    def get_order_book(self, exchange: str, coin: str) -> Optional[dict]:
        with self._lock:
            ob = self._orderbooks.get((exchange, coin))
            if ob is None:
                return None
            return {"bids": ob.bids, "asks": ob.asks}

    def get_exchange_status(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._exchange_status)

    def has_data(self) -> bool:
        with self._lock:
            return len(self._tickers) > 0

    def node_count(self) -> int:
        with self._lock:
            return len(self._tickers)


# ── per-exchange worker (child process) ──────────────────────────────

_EXCHANGE_CONSTRUCTORS: Dict[str, type] = {
    "binance": ccxt.binance,
    "kraken": ccxt.kraken,
    "kucoin": ccxt.kucoin,
    "bybit": ccxt.bybit,
    "okx": ccxt.okx,
    "gateio": ccxt.gateio,
    "bitget": ccxt.bitget,
    "mexc": ccxt.mexc,
    "htx": ccxt.htx,
    "coinbase": ccxt.coinbase,
    "cryptocom": ccxt.cryptocom,
    "phemex": ccxt.phemex,
}


def _worker_loop(
    exchange_name: str,
    queue: multiprocessing.Queue,
    stop_event: multiprocessing.Event,
    poll_interval: float,
    fetch_orderbooks: bool,
) -> None:
    """Entry point for each child process — one per exchange."""
    constructor = _EXCHANGE_CONSTRUCTORS.get(exchange_name)
    if constructor is None:
        return

    ex = constructor({"timeout": EXCHANGE_TIMEOUT_MS})

    while not stop_event.is_set():
        cycle_start = time.time()

        for coin in STABLE_COINS:
            if stop_event.is_set():
                return

            market = COIN_MARKETS.get(coin, {}).get(exchange_name)
            if not market:
                continue

            # ── ticker ──
            try:
                ticker = ex.fetch_ticker(market)
                bid = ticker.get("bid")
                ask = ticker.get("ask")
                last = ticker.get("last")

                if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                    conservative = bid
                elif isinstance(last, (int, float)):
                    conservative = float(last)
                else:
                    continue

                price_usd = normalize_price_to_usd(coin, market, conservative)
                if price_usd is None:
                    continue
                if abs(price_usd - 1.0) > STABLECOIN_PRICE_TOLERANCE:
                    continue

                qv = ticker.get("quoteVolume")
                bv = ticker.get("baseVolume")
                volume = None
                if isinstance(qv, (int, float)) and qv > 0:
                    volume = float(qv)
                elif isinstance(bv, (int, float)) and bv > 0:
                    volume = float(bv)

                queue.put(
                    TickerUpdate(
                        exchange=exchange_name,
                        coin=coin,
                        price_usd=price_usd,
                        bid=bid if isinstance(bid, (int, float)) else None,
                        ask=ask if isinstance(ask, (int, float)) else None,
                        volume_24h=volume,
                        timestamp=time.time(),
                    )
                )

            except Exception:
                queue.put(("error", exchange_name))
                continue

            # ── order book (optional) ──
            if fetch_orderbooks:
                try:
                    ob = ex.fetch_order_book(market, limit=20)
                    queue.put(
                        OrderBookUpdate(
                            exchange=exchange_name,
                            coin=coin,
                            bids=ob.get("bids", []),
                            asks=ob.get("asks", []),
                            timestamp=time.time(),
                        )
                    )
                except Exception:
                    pass

        elapsed = time.time() - cycle_start
        sleep_time = max(0.0, poll_interval - elapsed)
        if sleep_time > 0 and not stop_event.is_set():
            stop_event.wait(timeout=sleep_time)


# ── service (main process) ───────────────────────────────────────────

class MarketDataService:
    """Manages per-exchange worker processes and the drain thread."""

    def __init__(
        self,
        poll_interval: float = 5.0,
        fetch_orderbooks: bool = False,
    ) -> None:
        self.store = MarketDataStore()
        self._poll_interval = poll_interval
        self._fetch_orderbooks = fetch_orderbooks
        self._queue: multiprocessing.Queue = multiprocessing.Queue()
        self._stop_event = multiprocessing.Event()
        self._workers: List[multiprocessing.Process] = []
        self._drain_thread: Optional[threading.Thread] = None
        self._running = False

    # ── lifecycle ──

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._stop_event.clear()

        for ex_name in _EXCHANGE_CONSTRUCTORS:
            p = multiprocessing.Process(
                target=_worker_loop,
                args=(
                    ex_name,
                    self._queue,
                    self._stop_event,
                    self._poll_interval,
                    self._fetch_orderbooks,
                ),
                daemon=True,
                name=f"mds-{ex_name}",
            )
            p.start()
            self._workers.append(p)

        self._drain_thread = threading.Thread(
            target=self._drain_loop, daemon=True, name="mds-drain"
        )
        self._drain_thread.start()
        logger.info(
            "MarketDataService started: %d exchange workers", len(self._workers)
        )

    def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        self._stop_event.set()

        for p in self._workers:
            p.join(timeout=5)
            if p.is_alive():
                p.terminate()
        self._workers.clear()

        if self._drain_thread and self._drain_thread.is_alive():
            self._drain_thread.join(timeout=2)
        self._drain_thread = None
        logger.info("MarketDataService stopped")

    def wait_for_initial_data(self, timeout: float = 60.0) -> bool:
        """Block until the store has at least one ticker, or timeout."""
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self.store.has_data():
                logger.info(
                    "Initial data ready: %d nodes", self.store.node_count()
                )
                return True
            time.sleep(0.25)
        logger.warning("Timed out waiting for initial market data")
        return False

    @property
    def running(self) -> bool:
        return self._running

    # ── internal ──

    def _drain_loop(self) -> None:
        while self._running:
            try:
                msg = self._queue.get(timeout=0.1)
            except Exception:
                continue

            if isinstance(msg, TickerUpdate):
                self.store._apply_ticker(msg)
            elif isinstance(msg, OrderBookUpdate):
                self.store._apply_orderbook(msg)
            elif isinstance(msg, tuple) and msg[0] == "error":
                self.store._record_error(msg[1])
