# ======================================================================
# overnight_multi_snapshot.py — Multi-snapshot temporal data collection
# ======================================================================
#
# PURPOSE: Addresses Hang Ma's feedback:
#   "19 nodes, 3 start nodes, and a single snapshot do not stress the
#    search or generate cases where heuristics meaningfully change outcomes."
#
# This script runs continuously for a configurable number of hours,
# taking a fresh price snapshot every SNAPSHOT_INTERVAL_SEC seconds.
# On each snapshot it runs all heuristics from multiple start nodes
# and records structured results including:
#   - Timestamp & market conditions
#   - Profit found (or not) by each heuristic
#   - Node expansions / generated
#   - Runtime (pure compute, excluding I/O)
#   - Path details
#
# Output: JSON-lines file in results/ for downstream analysis.
# ======================================================================

from __future__ import annotations

import json
import random
import signal
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Project imports
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId

from scripts.astar_vol import (
    astar_best_path_with_liquidity,
    PlanResult as AStarPlanResult,
)
from scripts.weighted_astar import (
    weighted_astar_best_path,
    PlanResult as WeightedPlanResult,
)
from scripts.three_hop_baseline import (
    three_hop_enumeration,
    PlanResult as ThreeHopPlanResult,
)
from scripts.baseline_algorithms import (
    dijkstra_like_search,
    PlanResult as BaselinePlanResult,
)

# ── Configuration ──────────────────────────────────────────────────────
TOTAL_HOURS: float = 8.0                   # how long to run (hours)
SNAPSHOT_INTERVAL_SEC: float = 300.0        # 5 minutes between snapshots
CASH_LEVELS: List[float] = [1_000.0, 10_000.0, 100_000.0]
NUM_START_NODES: int = 5                    # random starts per snapshot
MAX_DEPTH: int = 6                          # deeper search (was 4-5, now 6)
MAX_TIME_SEC: float = 120.0                 # per-search time budget (seconds)
MIN_PROFIT: float = 0.0
EARLY_EXIT: bool = True                     # stop early after finding profit?
EARLY_EXIT_ITERS: int = 200                 # iterations to keep searching after first profit

# Heuristics to test on every snapshot
HEURISTICS = [
    "h1_liquidity",
    "h2_slippage",
    "h3_chaincongestion_exchange_risk",
    "dijkstra",
    "3hop_enum",
]

# Graceful shutdown
_RUNNING = True

def _signal_handler(sig, frame):
    global _RUNNING
    print("\n[SIGNAL] Graceful shutdown requested. Finishing current snapshot...")
    _RUNNING = False

signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ── Helpers ────────────────────────────────────────────────────────────

def _pick_start_nodes(nodes: Dict[NodeId, dict], n: int) -> List[NodeId]:
    """Pick n random start nodes, preferring major exchanges."""
    preferred = [
        ("binance", "USDT"), ("binance", "USDC"), ("kraken", "USDT"),
        ("kucoin", "USDT"), ("okx", "USDC"), ("bybit", "USDT"),
        ("gateio", "USDT"), ("coinbase", "USDC"),
    ]
    available = list(nodes.keys())
    selected = [p for p in preferred if p in available]
    remaining = [x for x in available if x not in selected]
    random.shuffle(remaining)
    selected.extend(remaining)
    return selected[:n]


def _run_search(
    heuristic: str,
    start_node: NodeId,
    cash_usd: float,
) -> Dict[str, Any]:
    """Run a single search and return a structured result dict."""
    t0 = time.perf_counter()
    result = None
    error = None

    try:
        if heuristic in ("h1_liquidity", "h2_slippage"):
            result = astar_best_path_with_liquidity(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                min_profit_usd=MIN_PROFIT,
                heuristic=heuristic,
                early_exit_after_profit=EARLY_EXIT,
                early_exit_iterations=EARLY_EXIT_ITERS,
            )
        elif heuristic == "h3_chaincongestion_exchange_risk":
            result = weighted_astar_best_path(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                min_profit_usd=MIN_PROFIT,
                early_exit_after_profit=EARLY_EXIT,
                early_exit_iterations=EARLY_EXIT_ITERS,
            )
        elif heuristic == "dijkstra":
            result = dijkstra_like_search(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_depth=MAX_DEPTH,
                max_time_sec=MAX_TIME_SEC,
                min_profit_usd=MIN_PROFIT,
            )
        elif heuristic == "3hop_enum":
            result = three_hop_enumeration(
                start_node=start_node,
                liquid_cash_usd=cash_usd,
                max_time_sec=MAX_TIME_SEC,
                min_profit_usd=MIN_PROFIT,
            )
    except Exception as e:
        error = f"{type(e).__name__}: {e}"
        import traceback
        traceback.print_exc()

    duration = time.perf_counter() - t0

    rec: Dict[str, Any] = {
        "heuristic": heuristic,
        "start_node": f"{start_node[0]}:{start_node[1]}",
        "cash_usd": cash_usd,
        "duration_sec": round(duration, 5),
        "success": result is not None,
    }

    if result is not None:
        rec["final_cash_usd"] = round(result.final_cash_usd, 4)
        rec["profit_usd"] = round(result.profit_usd, 4)
        rec["path_len"] = len(result.path)
        rec["path"] = [f"{ex}:{c}" for ex, c in result.path]
        rec["nodes_expanded"] = getattr(result, "nodes_expanded", None)
        rec["nodes_generated"] = getattr(result, "nodes_generated", None)
    else:
        rec["final_cash_usd"] = None
        rec["profit_usd"] = None
        rec["path_len"] = None
        rec["path"] = None
        rec["nodes_expanded"] = None
        rec["nodes_generated"] = None
        rec["error"] = error or "no_profitable_path"

    return rec


# ── Main loop ──────────────────────────────────────────────────────────

def main():
    random.seed(int(time.time()))

    results_dir = project_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    out_path = results_dir / f"overnight_snapshots_{timestamp}.jsonl"

    total_sec = TOTAL_HOURS * 3600
    end_time = time.time() + total_sec
    snapshot_idx = 0

    print(f"=== Overnight Multi-Snapshot Experiment ===")
    print(f"Duration:  {TOTAL_HOURS} hours ({int(total_sec)} seconds)")
    print(f"Interval:  {SNAPSHOT_INTERVAL_SEC}s between snapshots")
    print(f"Cash:      {CASH_LEVELS}")
    print(f"Starts:    {NUM_START_NODES} per snapshot")
    print(f"Heuristics: {HEURISTICS}")
    print(f"Output:    {out_path}")
    print(f"Started:   {datetime.now(timezone.utc).isoformat()}")
    print()

    with out_path.open("w", encoding="utf-8") as fout:
        # Write header line
        fout.write(json.dumps({
            "type": "header",
            "config": {
                "total_hours": TOTAL_HOURS,
                "snapshot_interval_sec": SNAPSHOT_INTERVAL_SEC,
                "cash_levels": CASH_LEVELS,
                "max_depth": MAX_DEPTH,
                "max_time_sec": MAX_TIME_SEC,
                "early_exit": EARLY_EXIT,
                "early_exit_iters": EARLY_EXIT_ITERS,
                "heuristics": HEURISTICS,
            },
            "started": datetime.now(timezone.utc).isoformat(),
        }) + "\n")
        fout.flush()

        while time.time() < end_time and _RUNNING:
            snapshot_idx += 1
            snapshot_start = time.time()
            snap_ts = datetime.now(timezone.utc).isoformat()

            print(f"\n{'='*60}")
            print(f"Snapshot #{snapshot_idx} at {snap_ts}")
            print(f"{'='*60}")

            # 1. Build fresh graph (force refresh to get new prices)
            try:
                nodes, adj = build_graph(force_refresh=True)
            except Exception as e:
                print(f"  [ERROR] Graph build failed: {e}")
                fout.write(json.dumps({
                    "type": "error",
                    "snapshot_idx": snapshot_idx,
                    "timestamp": snap_ts,
                    "error": f"graph_build_failed: {e}",
                }) + "\n")
                fout.flush()
                time.sleep(SNAPSHOT_INTERVAL_SEC)
                continue

            num_nodes = len(nodes)
            num_edges = sum(len(v) for v in adj.values())
            print(f"  Graph: {num_nodes} nodes, {num_edges} edges")

            # Capture price snapshot
            price_snapshot = {
                f"{ex}:{c}": meta.get("price_usd")
                for (ex, c), meta in nodes.items()
            }

            # 2. Pick start nodes
            starts = _pick_start_nodes(nodes, NUM_START_NODES)
            print(f"  Start nodes: {[f'{e}:{c}' for e, c in starts]}")

            # 3. Run all heuristic × start × cash combinations
            #    Write EACH result immediately so data survives a crash
            snapshot_results: List[Dict[str, Any]] = []

            for cash in CASH_LEVELS:
                for start in starts:
                    for heur in HEURISTICS:
                        try:
                            rec = _run_search(heur, start, cash)
                        except Exception as e:
                            rec = {
                                "heuristic": heur,
                                "start_node": f"{start[0]}:{start[1]}",
                                "cash_usd": cash,
                                "duration_sec": 0.0,
                                "success": False,
                                "error": f"crash: {type(e).__name__}: {e}",
                            }

                        # Immediately write each result as its own line
                        result_line = {
                            "type": "result",
                            "snapshot_idx": snapshot_idx,
                            "timestamp": snap_ts,
                            **rec,
                        }
                        fout.write(json.dumps(result_line) + "\n")
                        fout.flush()  # <-- flush after EVERY single result

                        snapshot_results.append(rec)

                        # Quick status
                        status = "✓" if rec["success"] else "✗"
                        profit = rec.get("profit_usd")
                        pstr = f"${profit:.2f}" if profit is not None else "N/A"
                        exp = rec.get("nodes_expanded", "?")
                        print(
                            f"  [{status}] {heur:40s} "
                            f"start={rec['start_node']:15s} "
                            f"cash=${cash:>10,.2f} "
                            f"profit={pstr:>10s} "
                            f"exp={str(exp):>6s} "
                            f"time={rec['duration_sec']:.5f}s"
                        )

            # Summary for this snapshot
            successes = [r for r in snapshot_results if r["success"]]
            print(f"\n  Snapshot #{snapshot_idx} summary: "
                  f"{len(successes)}/{len(snapshot_results)} successful searches, "
                  f"{len(snapshot_results)} total")

            if successes:
                avg_profit = sum(r["profit_usd"] for r in successes) / len(successes)
                max_profit = max(r["profit_usd"] for r in successes)
                print(f"  Avg profit: ${avg_profit:.4f}, Max profit: ${max_profit:.4f}")

            # 5. Sleep until next snapshot
            elapsed = time.time() - snapshot_start
            sleep_time = max(0, SNAPSHOT_INTERVAL_SEC - elapsed)
            if sleep_time > 0 and _RUNNING:
                print(f"\n  Sleeping {sleep_time:.0f}s until next snapshot...")
                sleep_end = time.time() + sleep_time
                while time.time() < sleep_end and _RUNNING:
                    time.sleep(min(5.0, sleep_end - time.time()))

    print(f"\n\n=== Experiment Complete ===")
    print(f"Total snapshots: {snapshot_idx}")
    print(f"Results saved to: {out_path}")


if __name__ == "__main__":
    main()

