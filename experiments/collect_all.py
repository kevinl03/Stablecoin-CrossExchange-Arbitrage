"""
Continuous Data Collection Orchestrator
=======================================
Launches and supervises all three data collectors simultaneously:
  1. Paper traders (WIF, PEPE, CRV) — live signal + trade PnL data
  2. Fill-rate trackers (same pairs) — passive execution quality data
  3. Stat-arb collector — broad microstructure data (order book, funding, OI)

Each subprocess auto-restarts on crash. The orchestrator:
  - Prevents Windows sleep
  - Logs all subprocess restarts with timestamps
  - Prints unified status every 5 minutes
  - Gracefully shuts down on Ctrl+C (saves all state)

Usage:
    python experiments/collect_all.py                    # default 5-day run
    python experiments/collect_all.py --hours 120        # 5 days
    python experiments/collect_all.py --hours 24 --no-ws # 1 day, REST only
    python experiments/collect_all.py --skip-statarb     # paper + fill only
    python experiments/collect_all.py --skip-fill-rate   # paper + statarb only

This is the "leave it running for 5 days" script that builds the full dataset
needed for credible resume claims:
  - 50+ live trades per asset for Sharpe ratio
  - Fill-rate and adverse selection measurements
  - Multi-day microstructure history for regime analysis
"""

import subprocess
import sys
import os
import time
import signal
import ctypes
import json
from datetime import datetime, timezone
from pathlib import Path
import argparse


# ---------------------------------------------------------------------------
# Windows sleep prevention
# ---------------------------------------------------------------------------

def prevent_sleep():
    if sys.platform == "win32":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )
        print("  [POWER] Windows sleep inhibited.")


def allow_sleep():
    if sys.platform == "win32":
        ES_CONTINUOUS = 0x80000000
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS)


# ---------------------------------------------------------------------------
# Subprocess manager
# ---------------------------------------------------------------------------

class ManagedProcess:
    """A subprocess that auto-restarts on crash."""

    def __init__(self, name: str, cmd: list[str], cwd: str):
        self.name = name
        self.cmd = cmd
        self.cwd = cwd
        self.process: subprocess.Popen | None = None
        self.restart_count = 0
        self.start_time = 0.0
        self.total_uptime = 0.0
        self.last_crash_time = 0.0
        self.backoff = 1.0

    def start(self):
        """Start or restart the subprocess."""
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        if self.restart_count == 0:
            print(f"  [{ts}] LAUNCH {self.name}")
        else:
            print(f"  [{ts}] RESTART {self.name} (attempt #{self.restart_count})")

        self.process = subprocess.Popen(
            self.cmd,
            cwd=self.cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,  # line-buffered
            env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"},
        )
        self.start_time = time.time()

    def check(self) -> bool:
        """Check if process is alive. Returns True if alive, False if exited."""
        if self.process is None:
            return False
        ret = self.process.poll()
        if ret is None:
            return True

        # Process exited
        uptime = time.time() - self.start_time
        self.total_uptime += uptime
        self.last_crash_time = time.time()

        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        print(f"  [{ts}] CRASHED {self.name} | exit={ret} | uptime={uptime/60:.1f}m | "
              f"restarts={self.restart_count}")

        # Drain any remaining output
        if self.process.stdout:
            remaining = self.process.stdout.read()
            if remaining and remaining.strip():
                for line in remaining.strip().split("\n")[-5:]:  # last 5 lines
                    print(f"    [{self.name}] {line.rstrip()}")

        self.process = None
        return False

    def maybe_restart(self):
        """Restart with exponential backoff if crashed."""
        if self.process is not None:
            return  # still running

        # Backoff: don't restart too fast
        if time.time() - self.last_crash_time < self.backoff:
            return

        self.restart_count += 1
        self.backoff = min(self.backoff * 2, 120.0)  # max 2 min backoff
        self.start()

    def stop(self):
        """Gracefully stop the subprocess."""
        if self.process is None:
            return
        try:
            self.process.terminate()
            self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        except Exception:
            pass
        self.total_uptime += time.time() - self.start_time
        self.process = None


# ---------------------------------------------------------------------------
# Process definitions
# ---------------------------------------------------------------------------

# Optimal pairs from optimization results
PAPER_TRADER_CONFIGS = [
    {
        "name": "PT-WIF",
        "asset": "WIF",
        "exchanges": "binance,cryptocom",
        "strategy": "zscore",
        "entry_z": "1.5",
        "exit_z": "0.3",
        "warmup": "20",
        "vol_filter": "0.8",
    },
    {
        "name": "PT-PEPE",
        "asset": "PEPE",
        "exchanges": "binance,cryptocom",
        "strategy": "ou",
        "entry_z": "1.5",
        "exit_z": "0.3",
        "warmup": "20",
        "vol_filter": "0.8",
    },
    {
        "name": "PT-CRV",
        "asset": "CRV",
        "exchanges": "cryptocom,mexc",
        "strategy": "ou",
        "entry_z": "1.5",
        "exit_z": "0.3",
        "warmup": "20",
        "vol_filter": "0.8",
    },
]

FILL_RATE_CONFIGS = [
    {"name": "FR-WIF", "asset": "WIF", "exchanges": "binance,cryptocom"},
    {"name": "FR-PEPE", "asset": "PEPE", "exchanges": "binance,cryptocom"},
    {"name": "FR-CRV", "asset": "CRV", "exchanges": "cryptocom,mexc"},
]


def build_processes(args) -> list[ManagedProcess]:
    """Build the list of managed subprocesses based on CLI flags."""
    repo_root = str(Path(__file__).parent.parent.resolve())
    python = sys.executable
    procs = []

    ws_flag = ["--no-ws"] if args.no_ws else []

    # 1. Paper traders
    if not args.skip_paper:
        for cfg in PAPER_TRADER_CONFIGS:
            cmd = [
                python, "experiments/paper_trader.py",
                "--asset", cfg["asset"],
                "--exchanges", cfg["exchanges"],
                "--strategy", cfg["strategy"],
                "--entry-z", cfg["entry_z"],
                "--exit-z", cfg["exit_z"],
                "--warmup", cfg["warmup"],
                "--vol-filter", cfg["vol_filter"],
            ] + ws_flag
            procs.append(ManagedProcess(cfg["name"], cmd, repo_root))

    # 2. Fill-rate trackers
    if not args.skip_fill_rate:
        duration = str(int(args.hours * 3600))
        for cfg in FILL_RATE_CONFIGS:
            cmd = [
                python, "experiments/fill_rate_tracker.py",
                "--asset", cfg["asset"],
                "--exchanges", cfg["exchanges"],
                "--duration", duration,
            ] + ws_flag
            procs.append(ManagedProcess(cfg["name"], cmd, repo_root))

    # 3. Stat-arb broad collector
    if not args.skip_statarb:
        cmd = [
            python, "-m", "experiments.collect_statarb_data",
            "--hours", str(args.hours),
            "--interval", "30",
            "--assets", "volatile",
        ]
        procs.append(ManagedProcess("STATARB", cmd, repo_root))

    return procs


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Continuous data collection orchestrator — runs paper traders, "
                    "fill-rate trackers, and stat-arb collector simultaneously"
    )
    parser.add_argument("--hours", type=float, default=120,
                        help="Total hours to run (default: 120 = 5 days)")
    parser.add_argument("--no-ws", action="store_true",
                        help="Force REST polling for all feeds")
    parser.add_argument("--skip-paper", action="store_true",
                        help="Skip paper trader processes")
    parser.add_argument("--skip-fill-rate", action="store_true",
                        help="Skip fill-rate tracker processes")
    parser.add_argument("--skip-statarb", action="store_true",
                        help="Skip broad stat-arb collector")
    args = parser.parse_args()

    total_sec = args.hours * 3600
    end_time = time.time() + total_sec

    print(f"\n{'='*60}")
    print(f"  CONTINUOUS DATA COLLECTION ORCHESTRATOR")
    print(f"  Started: {datetime.now(timezone.utc).isoformat()}")
    print(f"  Duration: {args.hours:.0f} hours ({args.hours/24:.1f} days)")
    print(f"  Feed mode: {'REST polling' if args.no_ws else 'WebSocket (REST fallback)'}")
    print(f"{'='*60}")

    # Build subprocess list
    procs = build_processes(args)
    if not procs:
        print("ERROR: All collectors disabled. Nothing to run.")
        sys.exit(1)

    print(f"\n  Launching {len(procs)} processes:")
    for p in procs:
        print(f"    - {p.name}: {' '.join(p.cmd[1:3])}")
    print()

    # Prevent Windows sleep
    prevent_sleep()

    # Start all
    for p in procs:
        p.start()
        time.sleep(0.5)  # stagger launches slightly

    # Status tracking
    last_status = time.time()
    status_interval = 300  # every 5 min
    log_path = Path(procs[0].cwd) / "data" / "orchestrator_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Signal handler for graceful shutdown
    shutdown = False

    def handle_signal(sig, frame):
        nonlocal shutdown
        shutdown = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while time.time() < end_time and not shutdown:
            time.sleep(5)

            # Check all processes and restart crashed ones
            for p in procs:
                if not p.check():
                    p.maybe_restart()

            # Periodic status
            if time.time() - last_status > status_interval:
                elapsed = time.time() - (end_time - total_sec)
                remaining = end_time - time.time()
                alive = sum(1 for p in procs if p.process is not None)
                total_restarts = sum(p.restart_count for p in procs)

                ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
                print(f"\n  [{ts}] ORCHESTRATOR STATUS")
                print(f"    Elapsed: {elapsed/3600:.1f}h | Remaining: {remaining/3600:.1f}h")
                print(f"    Alive: {alive}/{len(procs)} | Total restarts: {total_restarts}")
                for p in procs:
                    status = "RUNNING" if p.process else "RESTARTING"
                    uptime = (time.time() - p.start_time) if p.process else 0
                    print(f"    {p.name:12s} {status:10s} uptime={uptime/60:.0f}m restarts={p.restart_count}")
                print()

                # Log to file
                log_entry = {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "elapsed_h": round(elapsed / 3600, 2),
                    "alive": alive,
                    "total": len(procs),
                    "restarts": total_restarts,
                    "processes": {
                        p.name: {
                            "alive": p.process is not None,
                            "restarts": p.restart_count,
                            "uptime_min": round((time.time() - p.start_time) / 60, 1) if p.process else 0,
                        }
                        for p in procs
                    },
                }
                with open(log_path, "a") as f:
                    f.write(json.dumps(log_entry) + "\n")

                last_status = time.time()

    finally:
        print(f"\n  Shutting down {len(procs)} processes...")
        for p in procs:
            p.stop()

        allow_sleep()

        # Final summary
        total_uptime = sum(p.total_uptime for p in procs)
        total_restarts = sum(p.restart_count for p in procs)
        elapsed = time.time() - (end_time - total_sec)

        print(f"\n{'='*60}")
        print(f"  ORCHESTRATOR SHUTDOWN")
        print(f"  Total runtime: {elapsed/3600:.1f} hours")
        print(f"  Total restarts: {total_restarts}")
        for p in procs:
            print(f"    {p.name:12s} uptime={p.total_uptime/3600:.1f}h restarts={p.restart_count}")
        print(f"  Log: {log_path}")
        print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
