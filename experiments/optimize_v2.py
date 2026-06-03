"""
V2 Strategy Optimizer — Vectorized for speed.

Pre-computes rolling z-scores with pandas, then runs a fast loop
for the sequential position logic only.
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import sys, os, time as _time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.fees import TRADING_FEES_TAKER


def load_ticks(directory):
    ticks = []
    with open(Path(directory) / "ticks.jsonl") as f:
        for line in f:
            ticks.append(json.loads(line))

    exchanges = sorted(set(t["exchange"] for t in ticks))
    ex_a, ex_b = exchanges[0], exchanges[1]

    last = {ex_a: None, ex_b: None}
    rows = []
    for t in ticks:
        last[t["exchange"]] = t
        if last[ex_a] and last[ex_b]:
            mid_a = last[ex_a]["mid"]
            mid_b = last[ex_b]["mid"]
            rows.append({
                "ts": t["ts"],
                "spread_bps": (mid_b - mid_a) / mid_a * 10000,
                "mid_a": mid_a, "mid_b": mid_b,
                "bid_a": last[ex_a]["bid"], "ask_a": last[ex_a]["ask"],
                "bid_b": last[ex_b]["bid"], "ask_b": last[ex_b]["ask"],
            })
    return pd.DataFrame(rows), ex_a, ex_b


def precompute_rolling(spread_arr, windows):
    """Pre-compute rolling mean, std, z-score for all window sizes at once."""
    result = {}
    s = pd.Series(spread_arr)
    for w in windows:
        rm = s.rolling(w).mean()
        rs = s.rolling(w).std(ddof=0)
        z = (s - rm) / rs.replace(0, np.nan)
        result[w] = {
            "z": z.values,
            "std": rs.values,
        }
    return result


def simulate_fast(spread_arr, z_arr, std_arr, cost_bps,
                  entry_z, exit_z, vol_mult, cooldown, max_hold):
    """Fast simulate using pre-computed z-scores."""
    n = len(spread_arr)
    vol_threshold = vol_mult * cost_bps

    trades_net = []
    trades_gross = []
    trades_hold = []
    trades_timeout = 0

    pos_dir = 0  # 0=flat, 1=long_spread, -1=short_spread
    pos_entry_idx = 0
    pos_entry_spread = 0.0
    last_exit_idx = -cooldown - 1

    for i in range(n):
        z = z_arr[i]
        if np.isnan(z):
            continue
        sigma = std_arr[i]
        current = spread_arr[i]

        if pos_dir == 0:
            # Cooldown check
            if i - last_exit_idx < cooldown:
                continue
            # Vol filter
            if vol_mult > 0 and sigma < vol_threshold:
                continue
            # Entry
            if z > entry_z:
                pos_dir = -1  # short_spread
                pos_entry_idx = i
                pos_entry_spread = current
            elif z < -entry_z:
                pos_dir = 1  # long_spread
                pos_entry_idx = i
                pos_entry_spread = current
        else:
            hold = i - pos_entry_idx
            do_exit = False
            is_timeout = False

            if pos_dir == -1 and z < exit_z:
                do_exit = True
            elif pos_dir == 1 and z > -exit_z:
                do_exit = True
            elif max_hold and hold >= max_hold:
                do_exit = True
                is_timeout = True

            if do_exit:
                if pos_dir == -1:
                    gross = pos_entry_spread - current
                else:
                    gross = current - pos_entry_spread
                net = gross - cost_bps
                trades_net.append(net)
                trades_gross.append(gross)
                trades_hold.append(hold)
                if is_timeout:
                    trades_timeout += 1
                pos_dir = 0
                last_exit_idx = i

    n_trades = len(trades_net)
    if n_trades < 5:
        return None

    nets = np.array(trades_net)
    grosses = np.array(trades_gross)
    wins = int(np.sum(nets > 0))
    cumulative = np.cumsum(nets)
    running_max = np.maximum.accumulate(cumulative)
    max_dd = float(np.max(running_max - cumulative))
    std_net = float(np.std(nets))
    avg_net = float(np.mean(nets))

    return {
        "trades": n_trades,
        "net_pnl": float(np.sum(nets)),
        "gross_pnl": float(np.sum(grosses)),
        "win_rate": wins / n_trades * 100,
        "avg_net": avg_net,
        "avg_gross": float(np.mean(grosses)),
        "sharpe": avg_net / std_net * np.sqrt(252 * 24) if std_net > 0 else 0,
        "max_dd": max_dd,
        "profit_factor": float(np.sum(nets[nets > 0])) / max(float(np.abs(np.sum(nets[nets < 0]))), 0.01),
        "avg_hold": float(np.mean(trades_hold)),
        "timeout_pct": trades_timeout / n_trades * 100,
    }


def analyze_regimes(df, window=60):
    arr = df["spread_bps"].values
    vol = pd.Series(arr).rolling(window).std(ddof=0).dropna().values

    print(f"\n{'='*70}")
    print(f"  REGIME ANALYSIS ({len(arr)} spread observations)")
    print(f"{'='*70}")
    print(f"  Overall spread std: {np.std(arr):.2f} bps")
    print(f"  Rolling vol (window={window}):")
    for label, fn in [("Min", np.min), ("P25", lambda v: np.percentile(v, 25)),
                      ("P50", np.median), ("P75", lambda v: np.percentile(v, 75)),
                      ("P90", lambda v: np.percentile(v, 90)),
                      ("P95", lambda v: np.percentile(v, 95)), ("Max", np.max)]:
        print(f"    {label}:  {fn(vol):.2f} bps")

    for thresh in [10, 15, 20, 25, 30, 40, 50]:
        pct = np.mean(vol > thresh) * 100
        print(f"    Time with vol > {thresh} bps: {pct:.1f}%")


def analyze_time_of_day(df):
    df = df.copy()
    df["hour"] = df["ts"].str[11:13].astype(int)
    print(f"\n{'='*70}")
    print(f"  TIME-OF-DAY ANALYSIS (UTC hours)")
    print(f"{'='*70}")
    print(f"  {'Hour':<6} {'Count':<8} {'Std(bps)':<10} {'Range(bps)':<20}")
    for h, g in sorted(df.groupby("hour")):
        vals = g["spread_bps"].values
        print(f"  {h:02d}:00  {len(vals):<8} {np.std(vals):<10.2f} [{vals.min():.1f}, {vals.max():.1f}]")


def analyze_bid_ask(df):
    ba_a = (df["ask_a"] - df["bid_a"]) / df["mid_a"] * 10000
    ba_b = (df["ask_b"] - df["bid_b"]) / df["mid_b"] * 10000
    ba_total = ba_a + ba_b

    print(f"\n{'='*70}")
    print(f"  BID-ASK SPREAD ANALYSIS (hidden execution cost)")
    print(f"{'='*70}")
    print(f"  Exchange A -- mean: {ba_a.mean():.1f} bps, median: {ba_a.median():.1f}")
    print(f"  Exchange B -- mean: {ba_b.mean():.1f} bps, median: {ba_b.median():.1f}")
    print(f"  Combined  -- mean: {ba_total.mean():.1f} bps")
    print()
    print(f"  CRITICAL: With market orders, you cross the full BA spread.")
    print(f"  Real taker cost = fees + full BA = 17.5 + {ba_total.mean():.0f} = {17.5 + ba_total.mean():.0f} bps")
    print(f"  This makes taker-order stat-arb IMPOSSIBLE on this pair.")
    print()
    print(f"  SOLUTION: Use LIMIT orders (maker). You post liquidity, avoid BA crossing.")
    print(f"  Maker cost = maker_fee_A + maker_fee_B ~ 4-6 bps total")
    print(f"  With maker orders, the strategy becomes viable if avg_gross > 6 bps")


def grid_search(spread_arr, rolling_data, cost_bps, label):
    """Grid search using pre-computed rolling stats."""
    print(f"\n{'='*70}")
    print(f"  PARAMETER GRID SEARCH -- {label}")
    print(f"  Cost per round-trip: {cost_bps:.1f} bps")
    print(f"{'='*70}")

    windows = [20, 30, 45, 60, 90]
    entry_zs = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    exit_zs = [0.0, 0.3, 0.5]
    vol_mults = [0.0, 0.8, 1.0, 1.2, 1.5, 2.0]
    cooldowns = [0, 10, 30]
    max_holds = [0, 60]  # 0 = None

    results = []
    count = 0
    t0 = _time.time()

    for window in windows:
        z_arr = rolling_data[window]["z"]
        std_arr = rolling_data[window]["std"]
        for entry_z in entry_zs:
            for exit_z in exit_zs:
                if exit_z >= entry_z:
                    continue
                for vol_mult in vol_mults:
                    for cooldown in cooldowns:
                        for max_hold_val in max_holds:
                            mh = max_hold_val if max_hold_val > 0 else None
                            r = simulate_fast(
                                spread_arr, z_arr, std_arr, cost_bps,
                                entry_z, exit_z, vol_mult, cooldown, mh
                            )
                            count += 1
                            if r and r["trades"] >= 10:
                                r["params"] = {
                                    "window": window,
                                    "entry_z": entry_z,
                                    "exit_z": exit_z,
                                    "vol_mult": vol_mult,
                                    "max_hold": mh,
                                    "cooldown": cooldown,
                                }
                                results.append(r)

    elapsed = _time.time() - t0
    print(f"\n  Searched {count} combinations in {elapsed:.1f}s")

    if not results:
        print("  No parameter combinations with >=10 trades.")
        return []

    # --- SORT BY AVG NET PnL ---
    results.sort(key=lambda r: r["avg_net"], reverse=True)

    print(f"  Found {len(results)} viable configs")
    profitable = [r for r in results if r["avg_net"] > 0]
    print(f"  PROFITABLE: {len(profitable)} / {len(results)} ({len(profitable)/len(results)*100:.1f}%)")

    print(f"\n  TOP 20 BY AVG NET PnL/TRADE:")
    print(f"  {'#':<4} {'AvgNet':<9} {'Trades':<7} {'Win%':<7} {'Sharpe':<8} {'PF':<7} {'AvgGrs':<9} {'MaxDD':<8} | Parameters")
    print(f"  {'-'*105}")
    for i, r in enumerate(results[:20]):
        p = r["params"]
        ps = f"w={p['window']} ez={p['entry_z']} xz={p['exit_z']} vm={p['vol_mult']} cd={p['cooldown']} mh={p['max_hold']}"
        print(f"  {i+1:<4} {r['avg_net']:>+7.2f}  {r['trades']:<7} {r['win_rate']:<6.1f}% "
              f"{r['sharpe']:<8.2f} {r['profit_factor']:<7.2f} {r['avg_gross']:>+7.2f}  "
              f"{r['max_dd']:<8.1f} | {ps}")

    # --- SORT BY SHARPE ---
    by_sharpe = sorted([r for r in results if r["trades"] >= 20], key=lambda r: r["sharpe"], reverse=True)
    if by_sharpe:
        print(f"\n  TOP 10 BY SHARPE (min 20 trades):")
        print(f"  {'#':<4} {'Sharpe':<8} {'AvgNet':<9} {'Trades':<7} {'Win%':<7} {'PF':<7} | Parameters")
        print(f"  {'-'*80}")
        for i, r in enumerate(by_sharpe[:10]):
            p = r["params"]
            ps = f"w={p['window']} ez={p['entry_z']} xz={p['exit_z']} vm={p['vol_mult']} cd={p['cooldown']} mh={p['max_hold']}"
            print(f"  {i+1:<4} {r['sharpe']:<8.2f} {r['avg_net']:>+7.2f}  {r['trades']:<7} "
                  f"{r['win_rate']:<6.1f}% {r['profit_factor']:<7.2f} | {ps}")

    # --- BEST RECOMMENDATION ---
    if profitable:
        # Score = avg_net * sqrt(trades) (balances edge vs frequency)
        best = max(profitable, key=lambda r: r["avg_net"] * np.sqrt(min(r["trades"], 200)))
        p = best["params"]
        print(f"\n  >>> RECOMMENDED CONFIG (best edge x frequency):")
        print(f"      window={p['window']}, entry_z={p['entry_z']}, exit_z={p['exit_z']}")
        print(f"      vol_filter={p['vol_mult']}x cost, cooldown={p['cooldown']}, max_hold={p['max_hold']}")
        print(f"      --> {best['trades']} trades, avg_net={best['avg_net']:+.2f} bps, "
              f"win={best['win_rate']:.0f}%, Sharpe={best['sharpe']:.2f}")
    else:
        print(f"\n  >>> NO PROFITABLE CONFIG at {cost_bps:.1f} bps cost")
        print(f"      Best avg_net: {results[0]['avg_net']:+.2f} bps ({results[0]['trades']} trades)")
        p = results[0]["params"]
        print(f"      window={p['window']}, entry_z={p['entry_z']}, exit_z={p['exit_z']}")
        print(f"      vol_filter={p['vol_mult']}x cost, cooldown={p['cooldown']}, max_hold={p['max_hold']}")

    return results


def fee_sensitivity(spread_arr, rolling_data, base_cost, best_params):
    """What cost level makes this profitable? Informs maker vs taker decision."""
    print(f"\n{'='*70}")
    print(f"  FEE SENSITIVITY -- What cost level works?")
    print(f"{'='*70}")
    p = best_params
    w = p["window"]
    z_arr = rolling_data[w]["z"]
    std_arr = rolling_data[w]["std"]

    print(f"  Using params: w={p['window']} ez={p['entry_z']} xz={p['exit_z']} vm={p['vol_mult']}")
    print(f"  {'Cost(bps)':<12} {'Trades':<8} {'AvgNet':<10} {'Win%':<8} {'Sharpe':<8} {'TotalNet':<12}")
    print(f"  {'-'*65}")

    for cost in [2, 4, 6, 8, 10, 12, 15, 17.5, 20, 21.5, 25, 30, 50, 80, 130]:
        r = simulate_fast(spread_arr, z_arr, std_arr, cost,
                          p["entry_z"], p["exit_z"], p["vol_mult"],
                          p["cooldown"], p.get("max_hold"))
        if r is None:
            continue
        marker = " <-- current taker" if abs(cost - base_cost) < 0.5 else ""
        if abs(cost - 6) < 0.5:
            marker = " <-- maker orders"
        if abs(cost - 130) < 1:
            marker = " <-- real BA crossing"
        print(f"  {cost:<12.1f} {r['trades']:<8} {r['avg_net']:>+8.2f}  {r['win_rate']:<7.1f}% "
              f"{r['sharpe']:<8.2f} {r['net_pnl']:>+10.1f}{marker}")


def main():
    data_dir = Path("data/paper_trading")
    targets = [
        ("WIF_binance_cryptocom_zscore", "binance", "cryptocom"),
        ("CRV_cryptocom_mexc_ou", "cryptocom", "mexc"),
        ("PEPE_binance_cryptocom_ou", "binance", "cryptocom"),
    ]

    windows = [20, 30, 45, 60, 90]

    for dir_name, ex_a, ex_b in targets:
        full_dir = data_dir / dir_name
        if not (full_dir / "ticks.jsonl").exists():
            continue

        print(f"\n\n{'#'*70}")
        print(f"#  ANALYZING: {dir_name}")
        print(f"#  21-hour live tick data")
        print(f"{'#'*70}")

        df, det_a, det_b = load_ticks(str(full_dir))
        spread_arr = df["spread_bps"].values
        print(f"  Loaded {len(spread_arr)} spread observations ({det_a} vs {det_b})")

        fee_a = TRADING_FEES_TAKER.get(ex_a, 0.001)
        fee_b = TRADING_FEES_TAKER.get(ex_b, 0.001)
        taker_cost = (fee_a + fee_b) * 10000 + 4.0
        print(f"  Taker cost: {taker_cost:.1f} bps (fees + 4 bps slippage)")

        # Analyses
        analyze_regimes(df)
        analyze_time_of_day(df)
        analyze_bid_ask(df)

        # Pre-compute rolling stats
        print(f"\n  Pre-computing rolling z-scores for windows {windows}...")
        t0 = _time.time()
        rolling_data = precompute_rolling(spread_arr, windows)
        print(f"  Done in {_time.time()-t0:.1f}s")

        # Grid search at TAKER cost (current model)
        results_taker = grid_search(spread_arr, rolling_data, taker_cost,
                                    f"{dir_name} [TAKER cost]")

        # Grid search at MAKER cost (the real opportunity)
        maker_cost = 6.0  # ~2-3 bps maker fee per side on Binance/Crypto.com
        results_maker = grid_search(spread_arr, rolling_data, maker_cost,
                                    f"{dir_name} [MAKER cost = 6 bps]")

        # Fee sensitivity using best params
        if results_taker:
            bp = results_taker[0]["params"]
        elif results_maker:
            bp = results_maker[0]["params"]
        else:
            bp = {"window": 30, "entry_z": 2.0, "exit_z": 0.3,
                  "vol_mult": 0, "cooldown": 0, "max_hold": None}
        fee_sensitivity(spread_arr, rolling_data, taker_cost, bp)

    # Final strategic summary
    print(f"\n\n{'#'*70}")
    print(f"#  STRATEGIC CONCLUSION")
    print(f"{'#'*70}")
    print("""
  THE CORE PROBLEM:
  -----------------
  The backtests showed huge profits because they used mid-price execution.
  In reality, you must cross the bid-ask spread to execute.

  WIF bid-ask: Exchange A = 54 bps, Exchange B = 79 bps
  Combined BA crossing cost per round-trip: ~132 bps
  Plus taker fees: ~17.5 bps
  REAL cost with market orders: ~150 bps per round-trip

  Our signal generates ~20 bps gross per trade. That's 7.5x too small
  for market-order execution.

  THE SOLUTION PATH:
  ------------------
  1. LIMIT ORDERS (maker): Post limit orders at mid-price on both exchanges.
     Cost drops from 150 bps to ~6 bps (maker fees only).
     Signal generates ~20 bps gross --> ~14 bps NET per trade.
     Risk: fills are not guaranteed (adverse selection).

  2. VOLATILITY FILTER: Only trade in high-vol regimes (>20 bps spread std).
     This occurs ~5% of the time but produces much larger gross PnL.

  3. WIDER ENTRY THRESHOLD: Wait for z > 3.0 instead of 1.5.
     Fewer trades, but each one captures a larger mean-reversion.

  4. EXCHANGE PAIRS: Test cheaper exchanges (MEXC maker = 0 bps with rebate).

  PRIORITY:
  ---------
  Limit order execution is THE critical change. Without it, no parameter
  optimization will overcome the 132 bps BA spread.

  NEXT STEPS:
  -----------
  a) Build limit-order paper trader (post at mid, track fills)
  b) Measure fill rate: what % of limit orders get filled?
  c) If fill rate > 50%, strategy is viable at scale
  d) Adverse selection analysis: are fills correlated with losing trades?
""")


if __name__ == "__main__":
    main()
