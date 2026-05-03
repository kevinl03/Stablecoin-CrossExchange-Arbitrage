
from __future__ import annotations
import sys
import io
import contextlib
from pathlib import Path
from datetime import datetime, timezone


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # type: ignore
import scripts.h3_chaincongestion_exchange_risk as h3  # noqa


def _fake_fastest(sec: float):
    def _inner(node):
        return sec
    return _inner


def test_kickback_risk_zero_when_no_remaining_time(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", _fake_fastest(10.0))
    assert h3.estimate_chain_kickback_risk_score("binance", "USDT", 0.0) == 0.0
    assert h3.estimate_chain_kickback_risk_score("binance", "USDT", -5.0) == 0.0


def test_kickback_risk_zero_when_fastest_hop_slower_than_window(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", _fake_fastest(30.0))
    assert h3.estimate_chain_kickback_risk_score("binance", "USDT", 20.0) == 0.0


def test_kickback_risk_between_zero_and_one(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", _fake_fastest(10.0))
    score = h3.estimate_chain_kickback_risk_score("binance", "USDT", 20.0)
    assert score == pytest.approx(0.5, rel=1e-6)


def test_kickback_risk_clamped_to_one(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", _fake_fastest(0.0001))
    score = h3.estimate_chain_kickback_risk_score("binance", "USDT", 10_000.0)
    assert 0.0 <= score <= 1.0


def test_kickback_risk_zero_when_no_transfer_info(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", lambda n: None)
    assert h3.estimate_chain_kickback_risk_score("binance", "USDT", 60.0) == 0.0


def test_chain_congestion_heuristic_uses_weight(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", _fake_fastest(10.0))
    old_weight = h3.CHAIN_HEURISTIC_WEIGHT
    h3.CHAIN_HEURISTIC_WEIGHT = 2.0
    try:
        assert h3.chain_congestion_heuristic_cost("binance", "USDT", 20.0) == pytest.approx(1.0)
    finally:
        h3.CHAIN_HEURISTIC_WEIGHT = old_weight


def test_chain_congestion_heuristic_non_negative(monkeypatch):
    monkeypatch.setattr(h3, "_fastest_transfer_time_for_node", _fake_fastest(10.0))
    assert h3.chain_congestion_heuristic_cost("binance", "USDT", 20.0) >= 0.0


def test_estimate_exchange_reliability_score_known_exchange():
    assert h3.estimate_exchange_reliability_score("binance") == pytest.approx(0.9)


def test_estimate_exchange_reliability_score_unknown_exchange():
    assert h3.estimate_exchange_reliability_score("some_weird_exchange") == 0.0


def test_exchange_risk_heuristic_cost_known_exchange():
    assert h3.exchange_risk_heuristic_cost("binance") == pytest.approx(0.1)


def test_exchange_risk_heuristic_cost_unknown_exchange_uses_fallback():
    assert h3.exchange_risk_heuristic_cost("unknown_exch") == h3.UNKNOWN_EXCHANGE_PENALTY


def test_exchange_risk_respects_weight():
    old_weight = h3.EXCHANGE_HEURISTIC_WEIGHT
    h3.EXCHANGE_HEURISTIC_WEIGHT = 2.0
    try:
        expected = (1 - 0.6) * 2.0  # kucoin = 0.6
        assert h3.exchange_risk_heuristic_cost("kucoin") == pytest.approx(expected)
    finally:
        h3.EXCHANGE_HEURISTIC_WEIGHT = old_weight


def test_chain_exchange_risk_heuristic_is_sum_of_parts(monkeypatch):

    monkeypatch.setattr(
        h3,
        "chain_congestion_heuristic_cost",
        lambda *args, **kwargs: 2.5,
    )
    monkeypatch.setattr(
        h3,
        "exchange_risk_heuristic_cost",
        lambda *args, **kwargs: 0.75,
    )
    assert h3.chain_exchange_risk_heuristic_cost("binance", "USDT", 100) == pytest.approx(3.25)


def main():
    results_dir = REPO_ROOT / "results"
    results_dir.mkdir(exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_file = results_dir / f"unit_tests_h3_{timestamp}.txt"

    buf = io.StringIO()

    with contextlib.redirect_stdout(buf):
        # FULL VERBOSE MODE
        ret = pytest.main([
            "-vv",            # very verbose (prints each test)
            "--durations=0",  # show timing for every test
            __file__,         # run THIS file
        ])

    log_output = buf.getvalue()

    print(log_output)  # show in terminal

    with out_file.open("w", encoding="utf-8") as f:
        # Use timezone-aware UTC to avoid deprecation warning
        f.write(f"Run at {datetime.now(timezone.utc).isoformat()}\n\n")
        f.write(log_output)

    sys.exit(ret)


if __name__ == "__main__":
    main()
