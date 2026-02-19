#!/usr/bin/env python3
# ======================================================================
# run_all_overnight.py — Master runner with subprocess isolation
# ======================================================================
#
# Launches each experiment as a SEPARATE PROCESS so that:
#   - If one crashes, the others keep running
#   - Each has its own memory space (no shared state corruption)
#   - We can monitor their status
#   - Results are written independently
#
# Usage:
#   python experiments/run_all_overnight.py              # run all
#   python experiments/run_all_overnight.py --quick      # skip overnight
#   python experiments/run_all_overnight.py --smoke-only # just smoke test
# ======================================================================

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

project_root = Path(__file__).resolve().parent.parent


# ── Experiment definitions ─────────────────────────────────────────────

EXPERIMENTS = [
    {
        "name": "cached_graph",
        "script": "experiments/cached_graph_experiment.py",
        "description": "Cached graph: heuristic vs Dijkstra node expansions",
        "expected_duration_min": 30,
        "group": "short",
    },
    {
        "name": "slippage_vwap",
        "script": "experiments/slippage_vwap_test.py",
        "description": "VWAP slippage verification",
        "expected_duration_min": 30,
        "group": "short",
    },
    {
        "name": "sensitivity_sweep",
        "script": "experiments/sensitivity_sweep.py",
        "description": "λ-weight and order-size sensitivity",
        "expected_duration_min": 90,
        "group": "medium",
    },
    {
        "name": "graph_scaling",
        "script": "experiments/graph_scaling_test.py",
        "description": "Graph scaling (4/6/8/10/12 exchanges)",
        "expected_duration_min": 60,
        "group": "medium",
    },
    {
        "name": "monte_carlo",
        "script": "experiments/monte_carlo_simulation.py",
        "description": "Monte Carlo 500-trial backtesting",
        "expected_duration_min": 120,
        "group": "medium",
    },
    {
        "name": "quote_staleness",
        "script": "experiments/quote_staleness_test.py",
        "description": "Quote staleness path survival",
        "expected_duration_min": 120,
        "group": "long",
    },
    {
        "name": "overnight_snapshots",
        "script": "experiments/overnight_multi_snapshot.py",
        "description": "8-hour multi-snapshot temporal data",
        "expected_duration_min": 480,
        "group": "overnight",
    },
]


class ExperimentProcess:
    def __init__(self, experiment: Dict, log_dir: Path):
        self.name = experiment["name"]
        self.script = experiment["script"]
        self.description = experiment["description"]
        self.expected_min = experiment["expected_duration_min"]
        self.group = experiment["group"]

        self.log_path = log_dir / f"{self.name}.log"
        self.process: Optional[subprocess.Popen] = None
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.return_code: Optional[int] = None

    def start(self, python_exe: str):
        """Launch the experiment as a subprocess."""
        script_path = project_root / self.script
        self.log_file = self.log_path.open("w", encoding="utf-8")
        self.log_file.write(f"=== {self.name} ===\n")
        self.log_file.write(f"Script: {self.script}\n")
        self.log_file.write(f"Started: {datetime.now().isoformat()}\n")
        self.log_file.write(f"{'='*60}\n\n")
        self.log_file.flush()

        self.process = subprocess.Popen(
            [python_exe, str(script_path)],
            cwd=str(project_root),
            stdout=self.log_file,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )
        self.start_time = time.time()
        print(f"  [STARTED] {self.name} (PID {self.process.pid})")

    def poll(self) -> Optional[int]:
        """Check if process is still running."""
        if self.process is None:
            return None
        rc = self.process.poll()
        if rc is not None and self.end_time is None:
            self.end_time = time.time()
            self.return_code = rc
        return rc

    def elapsed_str(self) -> str:
        end = self.end_time or time.time()
        start = self.start_time or end
        elapsed = end - start
        mins = int(elapsed // 60)
        secs = int(elapsed % 60)
        return f"{mins}m {secs}s"

    def status_str(self) -> str:
        rc = self.poll()
        if rc is None:
            return f"🔄 RUNNING ({self.elapsed_str()})"
        elif rc == 0:
            return f"✅ DONE ({self.elapsed_str()})"
        else:
            return f"❌ FAILED rc={rc} ({self.elapsed_str()})"

    def terminate(self):
        if self.process and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()

    def cleanup(self):
        if hasattr(self, "log_file") and self.log_file:
            self.log_file.close()


def find_python() -> str:
    """Find the right Python executable (prefer venv)."""
    venv_python = project_root / "venv312" / "bin" / "python"
    if venv_python.exists():
        return str(venv_python)
    return sys.executable


def run_smoke_test(python_exe: str) -> bool:
    """Run smoke test and return True if passed."""
    print("\n" + "=" * 70)
    print("🔍 RUNNING SMOKE TEST")
    print("=" * 70 + "\n")

    result = subprocess.run(
        [python_exe, str(project_root / "experiments" / "smoke_test.py")],
        cwd=str(project_root),
        capture_output=False,
    )
    return result.returncode == 0


def main():
    args = sys.argv[1:]
    smoke_only = "--smoke-only" in args
    quick_mode = "--quick" in args

    python_exe = find_python()
    print(f"Python: {python_exe}")
    print(f"Project: {project_root}")
    print()

    # Step 1: Smoke test
    if not run_smoke_test(python_exe):
        print("\n❌ SMOKE TEST FAILED — fix errors before running overnight!")
        sys.exit(1)

    print("\n✅ Smoke test passed!\n")

    if smoke_only:
        print("--smoke-only flag set, exiting.")
        sys.exit(0)

    # Step 2: Set up log directory
    log_dir = project_root / "results" / f"overnight_run_{time.strftime('%Y%m%d_%H%M%S')}"
    log_dir.mkdir(parents=True, exist_ok=True)
    print(f"Log directory: {log_dir}")

    # Step 3: Select experiments based on mode
    if quick_mode:
        groups_to_run = {"short", "medium"}
        print("\n--quick mode: skipping overnight and long experiments")
    else:
        groups_to_run = {"short", "medium", "long", "overnight"}

    experiments_to_run = [e for e in EXPERIMENTS if e["group"] in groups_to_run]

    # Step 4: Launch experiments
    # Strategy: run short ones first (sequential), then medium+long in parallel
    print(f"\nWill run {len(experiments_to_run)} experiments:")
    for exp in experiments_to_run:
        print(f"  [{exp['group']:>10s}] {exp['name']:25s} — ~{exp['expected_duration_min']}min — {exp['description']}")

    # Separate into sequential (short) and parallel (everything else)
    sequential = [e for e in experiments_to_run if e["group"] == "short"]
    parallel = [e for e in experiments_to_run if e["group"] != "short"]

    processes: List[ExperimentProcess] = []

    # Run short experiments sequentially first (fast, validates everything)
    print(f"\n{'='*70}")
    print("Phase 1: Running short experiments sequentially")
    print(f"{'='*70}")

    for exp in sequential:
        proc = ExperimentProcess(exp, log_dir)
        proc.start(python_exe)
        processes.append(proc)

        # Wait for it to finish
        while proc.poll() is None:
            time.sleep(5)
            print(f"  [{proc.elapsed_str():>10s}] {proc.name} still running...", flush=True)

        print(f"  {proc.status_str()}")

        if proc.return_code != 0:
            print(f"  ⚠️  {proc.name} failed, but continuing with other experiments")

    # Launch parallel experiments
    if parallel:
        print(f"\n{'='*70}")
        print(f"Phase 2: Launching {len(parallel)} experiments in parallel")
        print(f"{'='*70}")

        parallel_procs: List[ExperimentProcess] = []
        for exp in parallel:
            proc = ExperimentProcess(exp, log_dir)
            proc.start(python_exe)
            parallel_procs.append(proc)
            processes.append(proc)

        # Monitor until all done
        print("\nMonitoring (Ctrl+C to gracefully stop all)...")
        try:
            while True:
                still_running = [p for p in parallel_procs if p.poll() is None]
                if not still_running:
                    break

                print(f"\n  --- Status at {datetime.now().strftime('%H:%M:%S')} ---")
                for p in parallel_procs:
                    print(f"    {p.name:25s} {p.status_str()}")

                time.sleep(60)  # check every minute

        except KeyboardInterrupt:
            print("\n\n⚠️  Ctrl+C received — gracefully stopping all experiments...")
            for p in parallel_procs:
                p.terminate()
            time.sleep(3)

    # Final summary
    print(f"\n\n{'='*70}")
    print("FINAL SUMMARY")
    print(f"{'='*70}")

    for p in processes:
        p.poll()
        print(f"  {p.name:25s} {p.status_str()}")
        print(f"    Log: {p.log_path}")
        p.cleanup()

    passed = sum(1 for p in processes if p.return_code == 0)
    failed = sum(1 for p in processes if p.return_code is not None and p.return_code != 0)
    running = sum(1 for p in processes if p.return_code is None)

    print(f"\n  Passed: {passed}, Failed: {failed}, Still running: {running}")
    print(f"  All logs in: {log_dir}")


if __name__ == "__main__":
    main()

