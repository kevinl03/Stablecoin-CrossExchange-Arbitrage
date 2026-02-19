# ======================================================================
# sensitivity_sweep.py — Hyperparameter sensitivity analysis
# ======================================================================
#
# PURPOSE: Addresses Hang Ma's feedback:
#   "Heuristic parameters (λ weights, thresholds, scoring scales, and
#    exchange reliability priors) are left unspecified; sensitivity
#    analyses to order size, path depth, and heuristic weights are
#    missing, despite being central to the paper's research questions."
#
# METHOD:
#   1. Build graph once (freeze snapshot)
#   2. Systematically sweep:
#      a) H1 λ_liquidity ∈ {0.1, 0.5, 1.0, 2.0, 5.0}
#      b) H2 λ_slippage ∈ {0.1, 0.25, 0.5, 1.0, 2.0}
#      c) H2 threshold_bps ∈ {5, 10, 20, 50}
#      d) Order sizes ∈ {100, 1K, 10K, 50K, 100K}
#      e) Max path depth ∈ {3, 4, 5, 6}
#   3. For each configuration, run from 5 start nodes
#   4. Record: profit, node expansions, runtime, path structure
# ======================================================================

from __future__ import annotations

import json
import random
import sys
from datetime import datetime, timezone
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId

from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)

import scripts.h1_vol as h1_module
import scripts.h2_slippage as h2_module

# ── Sweep configurations ──────────────────────────────────────────────
H1_LAMBDA_VALUES = [0.1, 0.5, 1.0, 2.0, 5.0]
H2_LAMBDA_VALUES = [0.1, 0.25, 0.5, 1.0, 2.0]
H2_THRESHOLD_BPS_VALUES = [5.0, 10.0, 20.0, 50.0]
ORDER_SIZES = [100.0, 1_000.0, 10_000.0, 50_000.0, 100_000.0]
MAX_DEPTHS = [3, 4, 5, 6]

NUM_START_NODES = 5
MAX_TIME_SEC = 60.0


def _run_h1_sweep(
    start_nodes: List[NodeId],
    cash_usd: float,
    max_depth: int,
    lambda_val: float,
) -> List[Dict[str, Any]]:
    """Run H1 with a specific λ value."""
    # Temporarily override the module-level weight
    original_weight = h1_module.LIQUIDITY_HEURISTIC_WEIGHT
    h1_module.LIQUIDITY_HEURISTIC_WEIGHT = lambda_val

    results = []
    for start in start_nodes:
        t0 = time.perf_counter()
        try:
            result = astar_best_path_with_liquidity(
                start_node=start,
                liquid_cash_usd=cash_usd,
                max_depth=max_depth,
                max_time_sec=MAX_TIME_SEC,
                heuristic="h1_liquidity",
                early_exit_after_profit=True,
                early_exit_iterations=100,
            )
        except Exception as e:
            result = None
        duration = time.perf_counter() - t0

        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sweep": "h1_lambda",
            "lambda": lambda_val,
            "cash_usd": cash_usd,
            "max_depth": max_depth,
            "start": f"{start[0]}:{start[1]}",
            "compute_sec": round(duration, 5),
            "success": result is not None,
            "profit": round(result.profit_usd, 4) if result else None,
            "path_len": len(result.path) if result else None,
            "nodes_expanded": getattr(result, "nodes_expanded", None) if result else None,
            "nodes_generated": getattr(result, "nodes_generated", None) if result else None,
        }
        results.append(rec)

    # Restore original weight
    h1_module.LIQUIDITY_HEURISTIC_WEIGHT = original_weight
    return results


def _run_h2_sweep(
    start_nodes: List[NodeId],
    cash_usd: float,
    max_depth: int,
    lambda_val: float,
    threshold_bps: float,
) -> List[Dict[str, Any]]:
    """Run H2 with specific λ and threshold values."""
    original_weight = h2_module.SLIPPAGE_HEURISTIC_WEIGHT
    original_threshold = h2_module.SLIPPAGE_THRESHOLD_BPS
    h2_module.SLIPPAGE_HEURISTIC_WEIGHT = lambda_val
    h2_module.SLIPPAGE_THRESHOLD_BPS = threshold_bps

    results = []
    for start in start_nodes:
        t0 = time.perf_counter()
        try:
            result = astar_best_path_with_liquidity(
                start_node=start,
                liquid_cash_usd=cash_usd,
                max_depth=max_depth,
                max_time_sec=MAX_TIME_SEC,
                heuristic="h2_slippage",
                early_exit_after_profit=True,
                early_exit_iterations=100,
            )
        except Exception as e:
            result = None
        duration = time.perf_counter() - t0

        rec = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sweep": "h2_lambda_threshold",
            "lambda": lambda_val,
            "threshold_bps": threshold_bps,
            "cash_usd": cash_usd,
            "max_depth": max_depth,
            "start": f"{start[0]}:{start[1]}",
            "compute_sec": round(duration, 5),
            "success": result is not None,
            "profit": round(result.profit_usd, 4) if result else None,
            "path_len": len(result.path) if result else None,
            "nodes_expanded": getattr(result, "nodes_expanded", None) if result else None,
            "nodes_generated": getattr(result, "nodes_generated", None) if result else None,
        }
        results.append(rec)

    h2_module.SLIPPAGE_HEURISTIC_WEIGHT = original_weight
    h2_module.SLIPPAGE_THRESHOLD_BPS = original_threshold
    return results


def main():
    random.seed(42)

    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"sensitivity_sweep_{timestamp}.jsonl"
    summary_path = results_dir / f"sensitivity_summary_{timestamp}.txt"

    print("=== Sensitivity Sweep Experiment ===")
    print(f"H1 λ values: {H1_LAMBDA_VALUES}")
    print(f"H2 λ values: {H2_LAMBDA_VALUES}")
    print(f"H2 threshold bps: {H2_THRESHOLD_BPS_VALUES}")
    print(f"Order sizes: {ORDER_SIZES}")
    print(f"Max depths: {MAX_DEPTHS}")
    print()

    # Build graph once
    print("Building graph...")
    nodes, adj = build_graph(force_refresh=True)
    print(f"  {len(nodes)} nodes, {sum(len(v) for v in adj.values())} edges")

    # Pick start nodes
    all_starts = list(nodes.keys())
    random.shuffle(all_starts)
    start_nodes = all_starts[:NUM_START_NODES]
    print(f"  Start nodes: {[f'{e}:{c}' for e, c in start_nodes]}")

    all_results: List[Dict[str, Any]] = []

    with out_path.open("w", encoding="utf-8") as fout:
        # ── Sweep 1: H1 λ × order size ──
        print(f"\n{'='*60}")
        print("Sweep 1: H1 λ_liquidity × order size")
        print(f"{'='*60}")

        for lam in H1_LAMBDA_VALUES:
            for cash in ORDER_SIZES:
                recs = _run_h1_sweep(start_nodes, cash, 5, lam)
                for r in recs:
                    fout.write(json.dumps(r) + "\n")
                    fout.flush()
                    all_results.append(r)

                successes = [r for r in recs if r["success"]]
                avg_p = sum(r["profit"] for r in successes) / len(successes) if successes else 0
                avg_e = sum(r["nodes_expanded"] for r in successes if r["nodes_expanded"]) / max(1, len(successes))
                print(
                    f"  λ={lam:<5.2f} cash=${cash:>10,.2f} "
                    f"success={len(successes)}/{len(recs)} "
                    f"avg_profit=${avg_p:.4f} avg_exp={avg_e:.0f}"
                )

        # ── Sweep 2: H2 λ × threshold ──
        print(f"\n{'='*60}")
        print("Sweep 2: H2 λ_slippage × threshold_bps")
        print(f"{'='*60}")

        for lam in H2_LAMBDA_VALUES:
            for thresh in H2_THRESHOLD_BPS_VALUES:
                recs = _run_h2_sweep(start_nodes, 10_000.0, 5, lam, thresh)
                for r in recs:
                    fout.write(json.dumps(r) + "\n")
                    fout.flush()
                    all_results.append(r)

                successes = [r for r in recs if r["success"]]
                avg_p = sum(r["profit"] for r in successes) / len(successes) if successes else 0
                avg_e = sum(r["nodes_expanded"] for r in successes if r["nodes_expanded"]) / max(1, len(successes))
                print(
                    f"  λ={lam:<5.2f} thresh={thresh:<5.1f}bps "
                    f"success={len(successes)}/{len(recs)} "
                    f"avg_profit=${avg_p:.4f} avg_exp={avg_e:.0f}"
                )

        # ── Sweep 3: Order size impact on profitability ──
        print(f"\n{'='*60}")
        print("Sweep 3: Order size impact (H1, default λ)")
        print(f"{'='*60}")

        for cash in ORDER_SIZES:
            recs = _run_h1_sweep(start_nodes, cash, 5, 1.0)
            for r in recs:
                r["sweep"] = "order_size"
                fout.write(json.dumps(r) + "\n")
                fout.flush()
                all_results.append(r)

            successes = [r for r in recs if r["success"]]
            profits = [r["profit"] for r in successes if r["profit"] is not None]
            avg_p = sum(profits) / len(profits) if profits else 0
            pct = (avg_p / cash * 100) if cash > 0 else 0
            print(
                f"  cash=${cash:>10,.2f} "
                f"success={len(successes)}/{len(recs)} "
                f"avg_profit=${avg_p:.4f} ({pct:.4f}%)"
            )

        # ── Sweep 4: Max depth impact ──
        print(f"\n{'='*60}")
        print("Sweep 4: Max depth impact (H1, $10K, default λ)")
        print(f"{'='*60}")

        for depth in MAX_DEPTHS:
            recs = _run_h1_sweep(start_nodes, 10_000.0, depth, 1.0)
            for r in recs:
                r["sweep"] = "max_depth"
                fout.write(json.dumps(r) + "\n")
                fout.flush()
                all_results.append(r)

            successes = [r for r in recs if r["success"]]
            avg_p = sum(r["profit"] for r in successes) / len(successes) if successes else 0
            avg_e = sum(r["nodes_expanded"] for r in successes if r["nodes_expanded"]) / max(1, len(successes))
            avg_len = sum(r["path_len"] for r in successes if r["path_len"]) / max(1, len(successes))
            print(
                f"  depth={depth} "
                f"success={len(successes)}/{len(recs)} "
                f"avg_profit=${avg_p:.4f} "
                f"avg_exp={avg_e:.0f} "
                f"avg_path_len={avg_len:.1f}"
            )

        fout.flush()

    # ── Summary ────────────────────────────────────────────────────────
    summary = []
    summary.append("SENSITIVITY SWEEP SUMMARY")
    summary.append(f"Total experiments: {len(all_results)}")
    summary.append(f"Graph: {len(nodes)} nodes")
    summary.append("")

    # Group by sweep type
    by_sweep: Dict[str, List] = defaultdict(list)
    for r in all_results:
        by_sweep[r["sweep"]].append(r)

    for sweep_name, group in by_sweep.items():
        successes = [g for g in group if g["success"]]
        summary.append(f"\n{sweep_name}: {len(successes)}/{len(group)} successful")

    with summary_path.open("w", encoding="utf-8") as sf:
        sf.write("\n".join(summary) + "\n")

    print(f"\nResults: {out_path}")
    print(f"Summary: {summary_path}")


if __name__ == "__main__":
    main()

