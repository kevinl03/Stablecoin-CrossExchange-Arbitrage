"""
Baseline regression tests run against the ORIGINAL integration branch
(the code used to produce the research paper results).

These validate fundamental data and algorithm invariants that must hold
across ALL branches. No network access required.

Run with: python3.14 -m pytest testing/test_regression_baseline.py -v
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


def make_test_graph() -> Tuple[Dict[NodeId, Dict[str, Any]], Adjacency]:
    """
    4-node graph across 2 exchanges, 2 coins.
    Profitable path: binance:USDT -> kraken:USDT -> kraken:USDC
    Return = 0.9995 * 1.0042 ~ 1.0037
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


# ── 1. Fee model (pinned values from the paper) ──────────────────────

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

    def test_known_fee_values_pinned(self):
        """These exact values were used in the paper's experiments."""
        from scripts.fees import TRADING_FEES_TAKER
        assert TRADING_FEES_TAKER["binance"] == 0.0010
        assert TRADING_FEES_TAKER["kraken"] == 0.0040
        assert TRADING_FEES_TAKER["kucoin"] == 0.0010
        assert TRADING_FEES_TAKER["bybit"] == 0.0010
        assert TRADING_FEES_TAKER["coinbase"] == 0.0060
        assert TRADING_FEES_TAKER["mexc"] == 0.0005
        assert TRADING_FEES_TAKER["gateio"] == 0.0020
        assert TRADING_FEES_TAKER["htx"] == 0.0020


# ── 2. Data module ───────────────────────────────────────────────────

class TestDataModule:
    def test_12_exchanges_configured(self):
        from scripts.data import EXCHANGES
        assert len(EXCHANGES) == 12

    def test_exchange_names(self):
        from scripts.data import EXCHANGES
        expected = {
            "binance", "kraken", "kucoin", "bybit", "okx", "gateio",
            "bitget", "mexc", "htx", "coinbase", "cryptocom", "phemex",
        }
        assert set(EXCHANGES.keys()) == expected

    def test_10_stablecoins_configured(self):
        from scripts.data import STABLE_COINS
        assert len(STABLE_COINS) == 10
        assert "USDT" in STABLE_COINS
        assert "USDC" in STABLE_COINS
        assert "DAI" in STABLE_COINS

    def test_stablecoin_list_exact(self):
        """Pin the exact stablecoin list used in the paper."""
        from scripts.data import STABLE_COINS
        expected = ["USDT", "USDC", "DAI", "TUSD", "FDUSD",
                    "BUSD", "PYUSD", "USDP", "GUSD", "FRAX"]
        assert STABLE_COINS == expected

    def test_coin_markets_cover_all_coins(self):
        from scripts.data import STABLE_COINS, COIN_MARKETS
        for coin in STABLE_COINS:
            assert coin in COIN_MARKETS, f"Missing market config for {coin}"

    def test_non_none_market_count(self):
        """The paper reports experiments across a specific graph size."""
        from scripts.data import COIN_MARKETS, EXCHANGES
        count = sum(
            1 for coin in COIN_MARKETS
            for ex in COIN_MARKETS[coin]
            if COIN_MARKETS[coin][ex] is not None
        )
        assert count >= 50, f"Expected at least 50 non-None markets, got {count}"


# ── 3. Transfer times ────────────────────────────────────────────────

class TestTransferTime:
    def test_common_chains_present(self):
        from scripts.transfer_time import CHAIN_TRANSFER_TIME_SEC
        for chain in ["ETH", "SOL", "TRX", "BNB", "ARB", "APT"]:
            assert chain in CHAIN_TRANSFER_TIME_SEC, f"Missing chain {chain}"

    def test_times_are_positive(self):
        from scripts.transfer_time import CHAIN_TRANSFER_TIME_SEC
        for chain, t in CHAIN_TRANSFER_TIME_SEC.items():
            assert t >= 0, f"{chain} has negative transfer time"

    def test_eth_slower_than_sol(self):
        from scripts.transfer_time import CHAIN_TRANSFER_TIME_SEC
        assert CHAIN_TRANSFER_TIME_SEC["ETH"] > CHAIN_TRANSFER_TIME_SEC["SOL"]


# ── 4. Graph edge math ───────────────────────────────────────────────

class TestGraphEdgeMath:
    def test_cost_equals_neg_log_rate(self):
        _, adj = make_test_graph()
        for node, edges in adj.items():
            for e in edges:
                expected_cost = -math.log(e["rate"])
                assert abs(e["cost"] - expected_cost) < 1e-12

    def test_profitable_path_return(self):
        _, adj = make_test_graph()
        total_cost = adj[("binance", "USDT")][1]["cost"] + adj[("kraken", "USDT")][0]["cost"]
        final_cash = 10_000 * math.exp(-total_cost)
        profit = final_cash - 10_000
        assert profit > 0
        assert abs(profit - 37.0) < 1.0

    def test_unprofitable_single_trade(self):
        _, adj = make_test_graph()
        trade_edge = adj[("binance", "USDT")][0]
        final = 10_000 * math.exp(-trade_edge["cost"])
        assert final < 10_000

    def test_cash_from_log_cost_formula(self):
        initial = 10_000.0
        rates = [0.9995, 1.0042, 0.998]
        total_log_cost = sum(-math.log(r) for r in rates)
        final = initial * math.exp(-total_log_cost)
        expected = initial * 0.9995 * 1.0042 * 0.998
        assert abs(final - expected) < 1e-6


# ── 5. A* search on toy graph ────────────────────────────────────────

class TestAStarSearch:
    def test_astar_finds_profitable_path(self):
        from scripts.astar_vol import astar_best_path_with_liquidity
        nodes, adj = make_test_graph()
        with patch("scripts.astar_vol.build_graph", return_value=(nodes, adj)):
            result = astar_best_path_with_liquidity(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
                heuristic="h1_liquidity",
            )
        assert result is not None
        assert result.profit_usd > 0

    def test_astar_path_starts_at_origin(self):
        from scripts.astar_vol import astar_best_path_with_liquidity
        nodes, adj = make_test_graph()
        with patch("scripts.astar_vol.build_graph", return_value=(nodes, adj)):
            result = astar_best_path_with_liquidity(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
                heuristic="h1_liquidity",
            )
        assert result is not None
        assert result.path[0] == ("binance", "USDT")

    def test_astar_edges_match_path_length(self):
        from scripts.astar_vol import astar_best_path_with_liquidity
        nodes, adj = make_test_graph()
        with patch("scripts.astar_vol.build_graph", return_value=(nodes, adj)):
            result = astar_best_path_with_liquidity(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
                heuristic="h1_liquidity",
            )
        assert result is not None
        assert len(result.edges) == len(result.path) - 1

    def test_astar_final_cash_consistent(self):
        from scripts.astar_vol import astar_best_path_with_liquidity
        nodes, adj = make_test_graph()
        with patch("scripts.astar_vol.build_graph", return_value=(nodes, adj)):
            result = astar_best_path_with_liquidity(
                start_node=("binance", "USDT"),
                liquid_cash_usd=10_000.0,
                max_depth=4,
                heuristic="h1_liquidity",
            )
        assert result is not None
        assert abs(result.final_cash_usd - (10_000 + result.profit_usd)) < 0.01


# ── 6. Weighted A* (h4) on toy graph ─────────────────────────────────

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
        assert result is not None
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


# ── 7. Cost breakdown ────────────────────────────────────────────────

class TestCostBreakdown:
    def test_trade_fee_accumulation(self):
        from scripts.astar_vol import _calculate_cost_breakdown
        edges = [
            {"kind": "trade", "taker_fee": 0.001, "rate": 0.999,
             "withdrawal_fee_units": 0, "chain": None, "transfer_time_sec": 0},
            {"kind": "trade", "taker_fee": 0.001, "rate": 1.002,
             "withdrawal_fee_units": 0, "chain": None, "transfer_time_sec": 0},
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
             "transfer_time_sec": 1.0, "network_gas_fee": 0.01},
        ]
        breakdown = _calculate_cost_breakdown(edges, 10_000.0)
        assert breakdown["num_transfers"] == 1
        assert breakdown["num_trades"] == 0


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
