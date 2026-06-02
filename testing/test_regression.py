"""
Offline regression tests for core algorithm integrity.

These tests use synthetic/mock data and do NOT require network access.
Run with: python -m pytest testing/test_regression.py -v
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from unittest.mock import patch
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

NodeId = Tuple[str, str]
Adjacency = Dict[NodeId, List[Dict[str, Any]]]


# ── Fixture: build a deterministic toy graph ─────────────────────────

def make_test_graph() -> Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]:
    """
    4-node graph across 2 exchanges, 2 coins:

        binance:USDT ──trade──> binance:USDC  (rate 0.9990, fee included)
        binance:USDC ──trade──> binance:USDT  (rate 1.0010, fee included)
        binance:USDT ──xfer──>  kraken:USDT   (rate 0.9995, withdrawal cost)
        kraken:USDT  ──trade──> kraken:USDC   (rate 1.0042, fee included)

    Profitable path: binance:USDT -> kraken:USDT -> kraken:USDC
    Return = 0.9995 * 1.0042 ≈ 1.0037  ($37 profit on $10k)
    """
    nodes = {
        ("binance", "USDT"): {"exchange": "binance", "coin": "USDT", "price_usd": 1.0, "snapshot_ts": 0.0},
        ("binance", "USDC"): {"exchange": "binance", "coin": "USDC", "price_usd": 1.0, "snapshot_ts": 0.0},
        ("kraken", "USDT"):  {"exchange": "kraken",  "coin": "USDT", "price_usd": 1.0, "snapshot_ts": 0.0},
        ("kraken", "USDC"):  {"exchange": "kraken",  "coin": "USDC", "price_usd": 1.0, "snapshot_ts": 0.0},
    }

    def edge(from_n, to_n, rate, kind="trade", **extra):
        cost = -math.log(rate)
        return {
            "from": from_n, "to": to_n, "rate": rate, "cost": cost,
            "kind": kind, "exchange": from_n[0],
            "coin_from": from_n[1], "coin_to": to_n[1],
            "taker_fee": extra.get("taker_fee", 0.001),
            "withdrawal_fee_units": extra.get("withdrawal_fee_units", 0.0),
            "chain": extra.get("chain"),
            "transfer_time_sec": extra.get("transfer_time_sec", 0.0),
            "volume_24h": extra.get("volume_24h", 1_000_000),
        }

    adj: Adjacency = defaultdict(list)

    adj[("binance", "USDT")].append(
        edge(("binance", "USDT"), ("binance", "USDC"), 0.9990))
    adj[("binance", "USDC")].append(
        edge(("binance", "USDC"), ("binance", "USDT"), 1.0010))
    adj[("binance", "USDT")].append(
        edge(("binance", "USDT"), ("kraken", "USDT"), 0.9995,
             kind="transfer", chain="SOL", transfer_time_sec=1.0,
             withdrawal_fee_units=0.25, taker_fee=0.0))
    adj[("kraken", "USDT")].append(
        edge(("kraken", "USDT"), ("kraken", "USDC"), 1.0042))

    return nodes, adj


# ── 1. Fee model integrity ───────────────────────────────────────────

class TestFeeModel:
    def test_all_12_exchanges_have_taker_fees(self):
        from scripts.fees import TRADING_FEES_TAKER
        expected = {
            "binance", "kraken", "kucoin", "bybit", "okx", "gateio",
            "bitget", "mexc", "htx", "coinbase", "cryptocom", "phemex",
        }
        assert set(TRADING_FEES_TAKER.keys()) == expected

    def test_taker_fees_are_positive_and_bounded(self):
        from scripts.fees import TRADING_FEES_TAKER
        for ex, fee in TRADING_FEES_TAKER.items():
            assert 0.0 <= fee <= 0.01, f"{ex} taker fee {fee} out of range"

    def test_withdrawal_fees_cover_all_exchanges(self):
        from scripts.fees import WITHDRAWAL_FEES
        from scripts.data import EXCHANGES
        for ex in EXCHANGES:
            assert ex in WITHDRAWAL_FEES, f"Missing withdrawal fees for {ex}"

    def test_get_taker_fee_returns_float(self):
        from scripts.fees import get_taker_fee
        for ex in ["binance", "kraken", "kucoin", "bybit"]:
            fee = get_taker_fee(ex)
            assert isinstance(fee, float)
            assert fee > 0

    def test_known_fee_values(self):
        """Pin specific fee values to catch accidental edits."""
        from scripts.fees import TRADING_FEES_TAKER
        assert TRADING_FEES_TAKER["binance"] == 0.0010
        assert TRADING_FEES_TAKER["kraken"] == 0.0040
        assert TRADING_FEES_TAKER["coinbase"] == 0.0060


# ── 2. Data module integrity ─────────────────────────────────────────

class TestDataModule:
    def test_12_exchanges_configured(self):
        from scripts.data import EXCHANGES
        assert len(EXCHANGES) == 12

    def test_10_stablecoins_configured(self):
        from scripts.data import STABLE_COINS
        assert len(STABLE_COINS) == 10
        assert "USDT" in STABLE_COINS
        assert "USDC" in STABLE_COINS

    def test_coin_markets_cover_all_coins(self):
        from scripts.data import STABLE_COINS, COIN_MARKETS
        for coin in STABLE_COINS:
            assert coin in COIN_MARKETS, f"Missing market config for {coin}"

    def test_exchange_timeout_is_set(self):
        from scripts.data import EXCHANGES, EXCHANGE_TIMEOUT_MS
        assert EXCHANGE_TIMEOUT_MS <= 10000
        for name, ex in EXCHANGES.items():
            assert ex.timeout == EXCHANGE_TIMEOUT_MS, (
                f"{name} timeout is {ex.timeout}, expected {EXCHANGE_TIMEOUT_MS}"
            )


# ── 3. Transfer time data ────────────────────────────────────────────

class TestTransferTime:
    def test_common_chains_present(self):
        from scripts.transfer_time import CHAIN_TRANSFER_TIME_SEC
        for chain in ["ETH", "SOL", "TRX", "BNB", "ARB", "APT"]:
            assert chain in CHAIN_TRANSFER_TIME_SEC, f"Missing chain {chain}"

    def test_times_are_positive(self):
        from scripts.transfer_time import CHAIN_TRANSFER_TIME_SEC
        for chain, t in CHAIN_TRANSFER_TIME_SEC.items():
            assert t >= 0, f"{chain} has negative transfer time"

    def test_get_chain_time_returns_value(self):
        from scripts.transfer_time import get_chain_time_seconds
        assert get_chain_time_seconds("ETH") > 0
        assert get_chain_time_seconds("SOL") > 0


# ── 4. Graph edge math ───────────────────────────────────────────────

class TestGraphEdgeMath:
    """Verify the log-cost / multiplicative-rate math that underpins the search."""

    def test_cost_equals_neg_log_rate(self):
        _, adj = make_test_graph()
        for node, edges in adj.items():
            for e in edges:
                expected_cost = -math.log(e["rate"])
                assert abs(e["cost"] - expected_cost) < 1e-12, (
                    f"Edge {e['from']}->{e['to']}: cost={e['cost']} != -log({e['rate']})={expected_cost}"
                )

    def test_profitable_path_return(self):
        """The 2-hop path binance:USDT -> kraken:USDT -> kraken:USDC should be profitable."""
        _, adj = make_test_graph()
        rate_product = 0.9995 * 1.0042
        assert rate_product > 1.0, "Expected profitable path"

        total_cost = 0.0
        total_cost += adj[("binance", "USDT")][1]["cost"]  # transfer edge
        total_cost += adj[("kraken", "USDT")][0]["cost"]    # trade edge

        final_cash = 10_000 * math.exp(-total_cost)
        profit = final_cash - 10_000
        assert profit > 0, f"Expected positive profit, got {profit}"
        assert abs(profit - 37.0) < 1.0, f"Expected ~$37 profit, got ${profit:.2f}"

    def test_unprofitable_single_trade(self):
        """A single trade with rate < 1.0 should lose money."""
        _, adj = make_test_graph()
        trade_edge = adj[("binance", "USDT")][0]  # rate 0.9990
        final = 10_000 * math.exp(-trade_edge["cost"])
        assert final < 10_000

    def test_cash_from_log_cost_formula(self):
        """Verify the exp(-sum_log_cost) formula used in A* and weighted A*."""
        initial = 10_000.0
        rates = [0.9995, 1.0042, 0.998]
        total_log_cost = sum(-math.log(r) for r in rates)
        final = initial * math.exp(-total_log_cost)
        expected = initial * 0.9995 * 1.0042 * 0.998
        assert abs(final - expected) < 1e-6


# ── 5. A* search on toy graph (mocked build_graph) ──────────────────

class TestAStarSearch:
    def _run_astar_on_toy_graph(self, heuristic="h1_liquidity"):
        """Run A* with build_graph mocked to return our toy graph."""
        from scripts.astar_vol import astar_best_path_with_liquidity

        nodes, adj = make_test_graph()

        with patch("scripts.astar_vol.build_graph", return_value=(nodes, adj)):
            result = astar_best_path_with_liquidity(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
                heuristic=heuristic,
            )
        return result

    def test_astar_finds_profitable_path(self):
        result = self._run_astar_on_toy_graph()
        assert result is not None, "A* should find a path"
        assert result.profit_usd > 0, f"Expected profit, got {result.profit_usd}"

    def test_astar_path_starts_at_origin(self):
        result = self._run_astar_on_toy_graph()
        assert result is not None
        assert result.path[0] == ("binance", "USDT")

    def test_astar_tracks_expansion_counts(self):
        result = self._run_astar_on_toy_graph()
        assert result is not None
        assert result.nodes_expanded > 0
        assert result.nodes_generated > 0

    def test_astar_result_fields_consistent(self):
        result = self._run_astar_on_toy_graph()
        assert result is not None
        assert len(result.edges) == len(result.path) - 1
        assert abs(result.final_cash_usd - (10_000 + result.profit_usd)) < 0.01


# ── 6. Weighted A* / h3 on toy graph ────────────────────────────────

class TestWeightedAStarSearch:
    def test_weighted_astar_finds_path(self):
        from scripts.weighted_astar import weighted_astar_best_path

        nodes, adj = make_test_graph()

        with patch("scripts.weighted_astar.build_graph", return_value=(nodes, adj)):
            result = weighted_astar_best_path(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
            )

        assert result is not None, "Weighted A* should find a path"
        assert result.profit_usd > 0

    def test_weighted_astar_path_valid(self):
        from scripts.weighted_astar import weighted_astar_best_path

        nodes, adj = make_test_graph()

        with patch("scripts.weighted_astar.build_graph", return_value=(nodes, adj)):
            result = weighted_astar_best_path(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
            )

        assert result is not None
        assert result.path[0] == ("binance", "USDT")
        assert len(result.edges) == len(result.path) - 1


# ── 7. Graph construction logic (mocked fetchers) ────────────────────

class TestBuildGraphLogic:
    def test_empty_prices_returns_empty_graph(self):
        """If no exchange data is available, build_graph should return empty structures."""
        with patch("scripts.graph.fetch_price_snapshot", return_value=({}, 0.0)):
            from scripts.graph import build_graph
            nodes, adj = build_graph(force_refresh=True)
            assert len(nodes) == 0
            assert len(adj) == 0

    def test_build_nx_graph_returns_tuple(self):
        """build_nx_graph should return (G, error_msg) tuple."""
        from scripts.ui import build_nx_graph
        import networkx as nx

        nodes, adj = make_test_graph()
        with patch("scripts.ui.build_graph", return_value=(nodes, adj)):
            G, err = build_nx_graph(show_all=False)
            assert isinstance(G, nx.DiGraph)
            assert err is None
            assert G.number_of_nodes() == 4

    def test_build_nx_graph_error_on_empty_data(self):
        """build_nx_graph should return an error string when no data loads."""
        from scripts.ui import build_nx_graph

        with patch("scripts.ui.build_graph", return_value=({}, defaultdict(list))):
            G, err = build_nx_graph(show_all=False)
            assert err is not None
            assert "network" in err.lower() or "exchange" in err.lower()


# ── 8. Cost breakdown calculation ─────────────────────────────────────

class TestCostBreakdown:
    def test_trade_fee_accumulation(self):
        from scripts.astar_vol import _calculate_cost_breakdown

        edges = [
            {"kind": "trade", "taker_fee": 0.001, "rate": 0.999,
             "withdrawal_fee_units": 0, "chain": None,
             "transfer_time_sec": 0},
            {"kind": "trade", "taker_fee": 0.001, "rate": 1.002,
             "withdrawal_fee_units": 0, "chain": None,
             "transfer_time_sec": 0},
        ]
        breakdown = _calculate_cost_breakdown(edges, 10_000.0)
        assert breakdown["num_trades"] == 2
        assert breakdown["num_transfers"] == 0
        assert breakdown["total_trading_fees"] > 0

    def test_transfer_fees_tracked(self):
        from scripts.astar_vol import _calculate_cost_breakdown

        edges = [
            {"kind": "transfer", "taker_fee": 0, "rate": 0.9995,
             "withdrawal_fee_units": 0.25, "chain": "SOL",
             "transfer_time_sec": 1.0,
             "network_gas_fee": 0.01},
        ]
        breakdown = _calculate_cost_breakdown(edges, 10_000.0)
        assert breakdown["num_transfers"] == 1
        assert breakdown["num_trades"] == 0


# ── Run with python directly ──────────────────────────────────────────

if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
