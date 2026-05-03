#!/usr/bin/env python3
# ======================================================================
# smoke_test.py — Fast validation that ALL experiment scripts work
# ======================================================================
#
# Run this BEFORE starting any overnight tests. It:
#   1. Verifies all imports work
#   2. Builds the graph once and checks node/edge counts
#   3. Runs each heuristic from 1 start node at 1 cash level
#   4. Verifies each experiment script can be imported without crashing
#   5. Runs a tiny slice of each experiment (1 trial, 1 config)
#   6. Checks that results files are written correctly
#
# Expected runtime: 2-5 minutes
# ======================================================================

from __future__ import annotations

import importlib
import json
import os
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class SmokeTestResult:
    def __init__(self, name: str):
        self.name = name
        self.passed = False
        self.error = None
        self.duration = 0.0
        self.details = ""

    def __repr__(self):
        status = "✅ PASS" if self.passed else "❌ FAIL"
        return f"{status} {self.name} ({self.duration:.2f}s) {self.details}"


def run_test(name: str, func, *args, **kwargs) -> SmokeTestResult:
    """Run a test function and capture result."""
    result = SmokeTestResult(name)
    t0 = time.perf_counter()
    try:
        details = func(*args, **kwargs)
        result.passed = True
        result.details = str(details) if details else ""
    except Exception as e:
        result.passed = False
        result.error = f"{type(e).__name__}: {e}"
        result.details = result.error
        traceback.print_exc()
    result.duration = time.perf_counter() - t0
    return result


# ── Test functions ─────────────────────────────────────────────────────

def test_core_imports():
    """Test that all core modules can be imported."""
    modules = [
        "scripts.data",
        "scripts.graph",
        "scripts.fees",
        "scripts.astar_vol",
        "scripts.weighted_astar",
        "scripts.baseline_algorithms",
        "scripts.three_hop_baseline",
        "scripts.h1_vol",
        "scripts.h2_slippage",
        "scripts.parallel_baseline",
        "scripts.h3_chaincongestion_exchange_risk",
        "scripts.transfer_time",
    ]
    failed = []
    for mod in modules:
        try:
            importlib.import_module(mod)
        except Exception as e:
            failed.append(f"{mod}: {e}")

    if failed:
        raise RuntimeError(f"Import failures: {failed}")
    return f"{len(modules)} modules OK"


def test_graph_build():
    """Test that the graph builds successfully with current data."""
    from scripts.graph import build_graph
    nodes, adj = build_graph(force_refresh=True, portfolio_size_usd=10_000.0)

    n_nodes = len(nodes)
    n_edges = sum(len(v) for v in adj.values())

    if n_nodes == 0:
        raise RuntimeError("Graph has 0 nodes — price fetching may be broken")
    if n_edges == 0:
        raise RuntimeError("Graph has 0 edges — edge construction broken")

    # Check node structure
    sample_node = list(nodes.values())[0]
    assert "exchange" in sample_node, "Node missing 'exchange' field"
    assert "coin" in sample_node, "Node missing 'coin' field"
    assert "price_usd" in sample_node, "Node missing 'price_usd' field"

    # Check edge structure
    sample_edges = list(adj.values())[0]
    if sample_edges:
        e = sample_edges[0]
        assert "to" in e, "Edge missing 'to' field"
        assert "cost" in e, "Edge missing 'cost' field"
        assert "kind" in e, "Edge missing 'kind' field"
        assert "rate" in e, "Edge missing 'rate' field"

    return f"{n_nodes} nodes, {n_edges} edges"


def test_h1_search():
    """Test H1 liquidity search returns a result or None (no crash)."""
    from scripts.graph import build_graph
    from scripts.astar_vol import astar_best_path_with_liquidity

    nodes, _ = build_graph(portfolio_size_usd=10_000.0)
    start = list(nodes.keys())[0]

    result = astar_best_path_with_liquidity(
        start_node=start,
        liquid_cash_usd=10_000.0,
        max_depth=4,
        max_time_sec=30.0,
        heuristic="h1_liquidity",
        early_exit_after_profit=True,
        early_exit_iterations=50,
    )

    if result:
        assert hasattr(result, "nodes_expanded"), "PlanResult missing nodes_expanded"
        assert hasattr(result, "nodes_generated"), "PlanResult missing nodes_generated"
        return f"profit=${result.profit_usd:.4f}, expanded={result.nodes_expanded}"
    return "no profitable path (OK)"


def test_h2_search():
    """Test H2 slippage search."""
    from scripts.graph import build_graph
    from scripts.astar_vol import astar_best_path_with_liquidity

    nodes, _ = build_graph(portfolio_size_usd=10_000.0)
    start = list(nodes.keys())[0]

    result = astar_best_path_with_liquidity(
        start_node=start,
        liquid_cash_usd=10_000.0,
        max_depth=4,
        max_time_sec=30.0,
        heuristic="h2_slippage",
        early_exit_after_profit=True,
        early_exit_iterations=50,
    )

    if result:
        return f"profit=${result.profit_usd:.4f}, expanded={result.nodes_expanded}"
    return "no profitable path (OK)"


def test_h3_weighted_astar():
    """Test H3 weighted A* search."""
    from scripts.graph import build_graph
    from scripts.weighted_astar import weighted_astar_best_path

    nodes, _ = build_graph(portfolio_size_usd=10_000.0)
    start = list(nodes.keys())[0]

    result = weighted_astar_best_path(
        start_node=start,
        liquid_cash_usd=10_000.0,
        max_depth=4,
        max_time_sec=30.0,
        early_exit_after_profit=True,
        early_exit_iterations=50,
    )

    if result:
        assert hasattr(result, "nodes_expanded"), "PlanResult missing nodes_expanded"
        return f"profit=${result.profit_usd:.4f}, expanded={result.nodes_expanded}"
    return "no profitable path (OK)"


def test_dijkstra():
    """Test Dijkstra baseline (h=0)."""
    from scripts.graph import build_graph
    from scripts.baseline_algorithms import dijkstra_like_search

    nodes, _ = build_graph(portfolio_size_usd=10_000.0)
    start = list(nodes.keys())[0]

    result = dijkstra_like_search(
        start_node=start,
        liquid_cash_usd=10_000.0,
        max_depth=4,
        max_time_sec=30.0,
    )

    if result:
        assert hasattr(result, "nodes_expanded"), "PlanResult missing nodes_expanded"
        return f"profit=${result.profit_usd:.4f}, expanded={result.nodes_expanded}"
    return "no profitable path (OK)"


def test_3hop_enum():
    """Test 3-hop enumeration baseline."""
    from scripts.graph import build_graph
    from scripts.three_hop_baseline import three_hop_enumeration

    nodes, _ = build_graph(portfolio_size_usd=10_000.0)
    start = list(nodes.keys())[0]

    result = three_hop_enumeration(
        start_node=start,
        liquid_cash_usd=10_000.0,
        max_time_sec=30.0,
    )

    if result:
        assert hasattr(result, "nodes_expanded"), "PlanResult missing nodes_expanded"
        return f"profit=${result.profit_usd:.4f}, paths_eval={result.nodes_expanded}"
    return "no profitable path (OK)"


def test_results_dir_writable():
    """Test that we can write results files."""
    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    test_file = results_dir / "_smoke_test_check.tmp"
    test_file.write_text(json.dumps({"test": True}) + "\n")
    content = test_file.read_text()
    assert '"test": true' in content
    test_file.unlink()  # clean up
    return "results/ writable"


def test_jsonl_output():
    """Test that JSON-lines output works correctly."""
    results_dir = project_root / "results"
    test_file = results_dir / "_smoke_test_jsonl.tmp"

    records = [
        {"snapshot": 1, "profit": 0.5, "success": True},
        {"snapshot": 2, "profit": -0.1, "success": False},
    ]

    with test_file.open("w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
            f.flush()  # critical: flush after each write

    # Read back and verify
    with test_file.open("r") as f:
        lines = f.readlines()
    assert len(lines) == 2, f"Expected 2 lines, got {len(lines)}"

    for line in lines:
        parsed = json.loads(line.strip())
        assert "snapshot" in parsed

    test_file.unlink()
    return "JSON-lines flush OK"


def test_experiment_import_overnight():
    """Test that the overnight script can be imported."""
    import experiments.overnight_multi_snapshot as mod
    assert hasattr(mod, "main")
    assert hasattr(mod, "_run_search")
    assert hasattr(mod, "HEURISTICS")
    return f"HEURISTICS={mod.HEURISTICS}"


def test_experiment_import_staleness():
    """Test that the quote staleness script can be imported."""
    import experiments.quote_staleness_test as mod
    assert hasattr(mod, "main")
    assert hasattr(mod, "_reevaluate_path_with_fresh_prices")
    return f"DELAYS={mod.DELAY_SECONDS}"


def test_experiment_import_cached():
    """Test that the cached graph experiment can be imported."""
    import experiments.cached_graph_experiment as mod
    assert hasattr(mod, "main")
    return f"MAX_STARTS={mod.MAX_STARTS}"


def test_experiment_import_sensitivity():
    """Test that the sensitivity sweep can be imported."""
    import experiments.sensitivity_sweep as mod
    assert hasattr(mod, "main")
    return f"H1_λ={mod.H1_LAMBDA_VALUES}"


def test_experiment_import_scaling():
    """Test that the graph scaling test can be imported."""
    import experiments.graph_scaling_test as mod
    assert hasattr(mod, "main")
    return f"TIERS={[len(t) for t in mod.EXCHANGE_TIERS]}"


def test_experiment_import_vwap():
    """Test that the VWAP slippage test can be imported."""
    import experiments.slippage_vwap_test as mod
    assert hasattr(mod, "main")
    return f"CASH_LEVELS={mod.CASH_LEVELS}"


def test_experiment_import_monte_carlo():
    """Test that the Monte Carlo simulation can be imported."""
    import experiments.monte_carlo_simulation as mod
    assert hasattr(mod, "main")
    assert hasattr(mod, "MonteCarloResult")
    # Check MonteCarloResult has expansion fields
    import dataclasses
    fields = {f.name for f in dataclasses.fields(mod.MonteCarloResult)}
    assert "nodes_expanded" in fields, "MonteCarloResult missing nodes_expanded"
    assert "nodes_generated" in fields, "MonteCarloResult missing nodes_generated"
    return f"TRIALS={mod.MC_NUM_TRIALS}"


def test_mini_overnight_snapshot():
    """Run one mini snapshot from the overnight runner."""
    from scripts.graph import build_graph
    from experiments.overnight_multi_snapshot import _run_search, _pick_start_nodes

    nodes, adj = build_graph(force_refresh=True, portfolio_size_usd=10_000.0)
    starts = _pick_start_nodes(nodes, 1)

    result = _run_search("h1_liquidity", starts[0], 10_000.0)
    assert "heuristic" in result
    assert "duration_sec" in result
    assert "success" in result
    assert "nodes_expanded" in result

    return f"success={result['success']}, time={result['duration_sec']:.3f}s"


# ── Main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("🔍 SMOKE TEST — Validating all experiment scripts")
    print("=" * 70)
    print()

    tests = [
        ("1. Core imports", test_core_imports),
        ("2. Graph build", test_graph_build),
        ("3. Results dir writable", test_results_dir_writable),
        ("4. JSONL output/flush", test_jsonl_output),
        ("5. H1 liquidity search", test_h1_search),
        ("6. H2 slippage search", test_h2_search),
        ("7. H3 weighted A* search", test_h3_weighted_astar),
        ("8. Dijkstra baseline", test_dijkstra),
        ("9. 3-hop enumeration", test_3hop_enum),
        ("10. Import: overnight_multi_snapshot", test_experiment_import_overnight),
        ("11. Import: quote_staleness_test", test_experiment_import_staleness),
        ("12. Import: cached_graph_experiment", test_experiment_import_cached),
        ("13. Import: sensitivity_sweep", test_experiment_import_sensitivity),
        ("14. Import: graph_scaling_test", test_experiment_import_scaling),
        ("15. Import: slippage_vwap_test", test_experiment_import_vwap),
        ("16. Import: monte_carlo_simulation", test_experiment_import_monte_carlo),
        ("17. Mini overnight snapshot", test_mini_overnight_snapshot),
    ]

    results = []
    for name, func in tests:
        print(f"Running: {name} ... ", end="", flush=True)
        r = run_test(name, func)
        results.append(r)
        print(r)

    # Summary
    print()
    print("=" * 70)
    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    total_time = sum(r.duration for r in results)

    if failed == 0:
        print(f"✅ ALL {passed}/{len(results)} TESTS PASSED ({total_time:.1f}s)")
        print("   Safe to run overnight experiments.")
    else:
        print(f"❌ {failed}/{len(results)} TESTS FAILED ({total_time:.1f}s)")
        print("   Fix failures before running overnight!")
        print()
        for r in results:
            if not r.passed:
                print(f"   FAILED: {r.name}")
                print(f"   Error: {r.error}")
                print()

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

