"""
Robustness Testing Suite for Stat-Arb Strategy

Tests whether optimize_v2 results are overfit or reflect genuine edge:
1. Walk-Forward Validation: Train on first half, test on second half
2. Expanding Window: Incrementally grow the training set
3. Random-Entry Baseline: Compare strategy to random entries with same # trades
4. Parameter Stability: How sensitive is PnL to small param perturbations?
5. Bootstrap Confidence Intervals: Resample trades to estimate CI on avg PnL
6. Multiple Comparisons Correction: Bonferroni / BH adjusted p-values
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from collections import defaultdict
import sys, os, time as _time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.fees import TRADING_FEES_TAKER
from experiments.optimize_v2 import load_ticks, precompute_rolling, simulate_fast


# ── helpers ────────────────────────────────────────────────────────────

def simulate_with_trade_list(spread_arr, z_arr, std_arr, cost_bps,
                             entry_z, exit_z, vol_mult, cooldown, max_hold):
    """Like simulate_fast but returns individual trade PnLs + entry indices."""
    n = len(spread_arr)
    vol_threshold = vol_mult * cost_bps
    trades = []
    pos_dir = 0
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
            if i - last_exit_idx < cooldown:
                continue
            if vol_mult > 0 and sigma < vol_threshold:
                continue
            if z > entry_z:
                pos_dir = -1
                pos_entry_idx = i
                pos_entry_spread = current
            elif z < -entry_z:
                pos_dir = 1
                pos_entry_idx = i
                pos_entry_spread = current
        else:
            hold = i - pos_entry_idx
            do_exit = False
            if pos_dir == -1 and z < exit_z:
                do_exit = True
            elif pos_dir == 1 and z > -exit_z:
                do_exit = True
            elif max_hold and hold >= max_hold:
                do_exit = True
            if do_exit:
                if pos_dir == -1:
                    gross = pos_entry_spread - current
                else:
                    gross = current - pos_entry_spread
                net = gross - cost_bps
                trades.append({"entry_idx": pos_entry_idx, "exit_idx": i,
                                "gross": gross, "net": net, "hold": hold})
                pos_dir = 0
                last_exit_idx = i
    return trades


def summarize_trades(trades):
    if len(trades) < 3:
        return None
    nets = np.array([t["net"] for t in trades])
    wins = int(np.sum(nets > 0))
    std_net = float(np.std(nets))
    avg_net = float(np.mean(nets))
    return {
        "trades": len(trades),
        "avg_net": avg_net,
        "total_net": float(np.sum(nets)),
        "win_rate": wins / len(trades) * 100,
        "sharpe": avg_net / std_net * np.sqrt(252 * 24) if std_net > 0 else 0,
        "avg_hold": float(np.mean([t["hold"] for t in trades])),
    }


# ── 1. Walk-Forward Validation ─────────────────────────────────────────

def walk_forward(spread_arr, windows, cost_bps, n_folds=3):
    """Split data into n_folds. Train on fold k, test on fold k+1."""
    print(f"\n{'='*70}")
    print(f"  WALK-FORWARD VALIDATION ({n_folds}-fold)")
    print(f"  Total ticks: {len(spread_arr)}")
    print(f"{'='*70}")

    fold_size = len(spread_arr) // n_folds
    entry_zs = [1.5, 2.0, 2.5, 3.0, 3.5, 4.0]
    exit_zs = [0.0, 0.3, 0.5]
    vol_mults = [0.0, 0.8, 1.0, 1.2, 1.5, 2.0]
    cooldowns = [0, 10, 30]
    max_holds = [0, 60]

    oos_results = []

    for fold in range(n_folds - 1):
        train_start = fold * fold_size
        train_end = (fold + 1) * fold_size
        test_end = min((fold + 2) * fold_size, len(spread_arr))

        train_arr = spread_arr[train_start:train_end]
        test_arr = spread_arr[train_end:test_end]

        print(f"\n  Fold {fold+1}: Train [{train_start}:{train_end}] ({len(train_arr)} ticks) "
              f"-> Test [{train_end}:{test_end}] ({len(test_arr)} ticks)")

        # Train: find best params on training set
        train_rolling = precompute_rolling(train_arr, windows)
        best_train = None
        best_train_sharpe = -999

        for window in windows:
            z_arr = train_rolling[window]["z"]
            std_arr = train_rolling[window]["std"]
            for entry_z in entry_zs:
                for exit_z in exit_zs:
                    if exit_z >= entry_z:
                        continue
                    for vol_mult in vol_mults:
                        for cooldown in cooldowns:
                            for max_hold_val in max_holds:
                                mh = max_hold_val if max_hold_val > 0 else None
                                r = simulate_fast(train_arr, z_arr, std_arr, cost_bps,
                                                  entry_z, exit_z, vol_mult, cooldown, mh)
                                if r and r["trades"] >= 10 and r["sharpe"] > best_train_sharpe:
                                    best_train_sharpe = r["sharpe"]
                                    best_train = {
                                        "window": window, "entry_z": entry_z, "exit_z": exit_z,
                                        "vol_mult": vol_mult, "cooldown": cooldown, "max_hold": mh,
                                    }
                                    best_train_result = r

        if best_train is None:
            print(f"    No viable config found on training data")
            continue

        p = best_train
        print(f"    Best train: w={p['window']} ez={p['entry_z']} xz={p['exit_z']} "
              f"vm={p['vol_mult']} cd={p['cooldown']} mh={p['max_hold']}")
        print(f"    Train: {best_train_result['trades']} trades, "
              f"avg_net={best_train_result['avg_net']:+.2f}, "
              f"win={best_train_result['win_rate']:.0f}%, "
              f"Sharpe={best_train_result['sharpe']:.1f}")

        # Test: apply best-train params to test set (TRUE out-of-sample)
        test_rolling = precompute_rolling(test_arr, [p["window"]])
        z_test = test_rolling[p["window"]]["z"]
        std_test = test_rolling[p["window"]]["std"]

        r_test = simulate_fast(test_arr, z_test, std_test, cost_bps,
                               p["entry_z"], p["exit_z"], p["vol_mult"],
                               p["cooldown"], p["max_hold"])

        if r_test and r_test["trades"] >= 3:
            print(f"    TEST:  {r_test['trades']} trades, "
                  f"avg_net={r_test['avg_net']:+.2f}, "
                  f"win={r_test['win_rate']:.0f}%, "
                  f"Sharpe={r_test['sharpe']:.1f}")
            degradation = (best_train_result["avg_net"] - r_test["avg_net"]) / max(abs(best_train_result["avg_net"]), 0.01) * 100
            print(f"    Degradation: {degradation:+.1f}% (positive = worse OOS)")
            oos_results.append({
                "fold": fold + 1,
                "train_sharpe": best_train_result["sharpe"],
                "test_sharpe": r_test["sharpe"],
                "train_avg_net": best_train_result["avg_net"],
                "test_avg_net": r_test["avg_net"],
                "test_profitable": r_test["avg_net"] > 0,
                "params": best_train,
            })
        else:
            print(f"    TEST:  <3 trades -- insufficient data for evaluation")
            oos_results.append({
                "fold": fold + 1,
                "train_sharpe": best_train_result["sharpe"],
                "test_sharpe": 0,
                "train_avg_net": best_train_result["avg_net"],
                "test_avg_net": 0,
                "test_profitable": False,
                "params": best_train,
            })

    # Summary
    if oos_results:
        print(f"\n  WALK-FORWARD SUMMARY:")
        oos_profitable = sum(1 for r in oos_results if r["test_profitable"])
        print(f"    Folds profitable OOS: {oos_profitable}/{len(oos_results)}")
        avg_train = np.mean([r["train_avg_net"] for r in oos_results])
        avg_test = np.mean([r["test_avg_net"] for r in oos_results])
        print(f"    Avg train PnL/trade: {avg_train:+.2f} bps")
        print(f"    Avg test PnL/trade:  {avg_test:+.2f} bps")
        if avg_train > 0:
            print(f"    OOS retention: {avg_test/avg_train*100:.0f}% of in-sample edge")
        avg_train_sharpe = np.mean([r["train_sharpe"] for r in oos_results])
        avg_test_sharpe = np.mean([r["test_sharpe"] for r in oos_results])
        print(f"    Avg train Sharpe: {avg_train_sharpe:.1f}")
        print(f"    Avg test Sharpe:  {avg_test_sharpe:.1f}")

    return oos_results


# ── 2. Random Entry Baseline ──────────────────────────────────────────

def random_entry_baseline(spread_arr, cost_bps, n_trades_target, n_sims=5000, max_hold=60):
    """Monte Carlo: enter randomly, exit at max_hold. Compare to strategy."""
    print(f"\n{'='*70}")
    print(f"  RANDOM ENTRY BASELINE (Monte Carlo, {n_sims} simulations)")
    print(f"  Target trades per sim: {n_trades_target}, max_hold: {max_hold}")
    print(f"{'='*70}")

    rng = np.random.default_rng(42)
    sim_avg_nets = []

    for _ in range(n_sims):
        # Random entry points
        entries = rng.integers(0, len(spread_arr) - max_hold - 1, size=n_trades_target)
        entries.sort()

        # Remove overlapping trades
        clean_entries = [entries[0]]
        for e in entries[1:]:
            if e > clean_entries[-1] + max_hold:
                clean_entries.append(e)

        trades_net = []
        for entry in clean_entries:
            # Random direction
            direction = rng.choice([-1, 1])
            exit_idx = entry + max_hold
            if exit_idx >= len(spread_arr):
                continue
            if direction == 1:  # long_spread
                gross = spread_arr[exit_idx] - spread_arr[entry]
            else:  # short_spread
                gross = spread_arr[entry] - spread_arr[exit_idx]
            net = gross - cost_bps
            trades_net.append(net)

        if len(trades_net) >= 3:
            sim_avg_nets.append(np.mean(trades_net))

    sim_avg_nets = np.array(sim_avg_nets)
    print(f"  Random baseline avg_net:")
    print(f"    Mean:  {np.mean(sim_avg_nets):+.2f} bps")
    print(f"    Std:   {np.std(sim_avg_nets):.2f} bps")
    print(f"    P5:    {np.percentile(sim_avg_nets, 5):+.2f} bps")
    print(f"    P50:   {np.percentile(sim_avg_nets, 50):+.2f} bps")
    print(f"    P95:   {np.percentile(sim_avg_nets, 95):+.2f} bps")
    print(f"    % profitable: {np.mean(sim_avg_nets > 0)*100:.1f}%")

    return sim_avg_nets


# ── 3. Parameter Stability (Sensitivity) ──────────────────────────────

def parameter_stability(spread_arr, rolling_data, cost_bps, center_params):
    """Perturb each parameter +/- and check how much PnL changes."""
    print(f"\n{'='*70}")
    print(f"  PARAMETER STABILITY (sensitivity to perturbations)")
    print(f"{'='*70}")

    p = center_params
    base_z = rolling_data[p["window"]]["z"]
    base_std = rolling_data[p["window"]]["std"]
    base_r = simulate_fast(spread_arr, base_z, base_std, cost_bps,
                           p["entry_z"], p["exit_z"], p["vol_mult"],
                           p["cooldown"], p["max_hold"])

    if base_r is None:
        print("  Base config has no trades")
        return

    print(f"  Base: w={p['window']} ez={p['entry_z']} xz={p['exit_z']} "
          f"vm={p['vol_mult']} cd={p['cooldown']} mh={p['max_hold']}")
    print(f"  Base result: {base_r['trades']} trades, avg_net={base_r['avg_net']:+.2f}, "
          f"Sharpe={base_r['sharpe']:.1f}")
    print()

    # Define perturbation grid for each param
    perturbations = {
        "entry_z": [p["entry_z"] - 0.5, p["entry_z"] - 0.25, p["entry_z"],
                     p["entry_z"] + 0.25, p["entry_z"] + 0.5],
        "exit_z": [max(0, p["exit_z"] - 0.15), p["exit_z"],
                    min(p["entry_z"] - 0.1, p["exit_z"] + 0.15),
                    min(p["entry_z"] - 0.1, p["exit_z"] + 0.3)],
        "vol_mult": [max(0, p["vol_mult"] - 0.4), max(0, p["vol_mult"] - 0.2),
                      p["vol_mult"], p["vol_mult"] + 0.2, p["vol_mult"] + 0.4],
    }

    # Also test nearby windows
    all_windows = [20, 30, 45, 60, 90]
    center_idx = all_windows.index(p["window"]) if p["window"] in all_windows else 2
    window_range = all_windows[max(0, center_idx-1):center_idx+2]

    print(f"  {'Param':<12} {'Value':<8} {'Trades':<8} {'AvgNet':<10} {'Win%':<8} {'Sharpe':<8} {'Delta':<8}")
    print(f"  {'-'*70}")

    for param_name, values in perturbations.items():
        for val in values:
            if val < 0:
                continue
            test_p = dict(p)
            test_p[param_name] = val

            z = rolling_data[test_p["window"]]["z"]
            s = rolling_data[test_p["window"]]["std"]
            r = simulate_fast(spread_arr, z, s, cost_bps,
                              test_p["entry_z"], test_p["exit_z"], test_p["vol_mult"],
                              test_p["cooldown"], test_p["max_hold"])
            if r and r["trades"] >= 5:
                delta = r["avg_net"] - base_r["avg_net"]
                marker = " <-- BASE" if val == p[param_name] else ""
                print(f"  {param_name:<12} {val:<8.2f} {r['trades']:<8} {r['avg_net']:>+8.2f}  "
                      f"{r['win_rate']:<7.1f}% {r['sharpe']:<8.1f} {delta:>+7.2f}{marker}")
            else:
                print(f"  {param_name:<12} {val:<8.2f} {'<5 trades':<8}")
        print()

    # Window sensitivity
    print(f"  {'window':<12} {'Value':<8} {'Trades':<8} {'AvgNet':<10} {'Win%':<8} {'Sharpe':<8} {'Delta':<8}")
    print(f"  {'-'*70}")
    for w in all_windows:
        z = rolling_data[w]["z"]
        s = rolling_data[w]["std"]
        r = simulate_fast(spread_arr, z, s, cost_bps,
                          p["entry_z"], p["exit_z"], p["vol_mult"],
                          p["cooldown"], p["max_hold"])
        if r and r["trades"] >= 5:
            delta = r["avg_net"] - base_r["avg_net"]
            marker = " <-- BASE" if w == p["window"] else ""
            print(f"  {'window':<12} {w:<8} {r['trades']:<8} {r['avg_net']:>+8.2f}  "
                  f"{r['win_rate']:<7.1f}% {r['sharpe']:<8.1f} {delta:>+7.2f}{marker}")


# ── 4. Bootstrap Confidence Intervals ─────────────────────────────────

def bootstrap_ci(spread_arr, z_arr, std_arr, cost_bps, params, n_boot=10000):
    """Bootstrap resample trades to get CI on avg PnL and Sharpe."""
    print(f"\n{'='*70}")
    print(f"  BOOTSTRAP CONFIDENCE INTERVALS ({n_boot} resamples)")
    print(f"{'='*70}")

    p = params
    trades = simulate_with_trade_list(spread_arr, z_arr, std_arr, cost_bps,
                                       p["entry_z"], p["exit_z"], p["vol_mult"],
                                       p["cooldown"], p["max_hold"])

    if len(trades) < 10:
        print(f"  Only {len(trades)} trades -- insufficient for bootstrap")
        return

    nets = np.array([t["net"] for t in trades])
    print(f"  Original: {len(nets)} trades, avg_net={np.mean(nets):+.2f}, "
          f"win_rate={np.mean(nets>0)*100:.1f}%")

    rng = np.random.default_rng(42)
    boot_means = []
    boot_sharpes = []
    boot_winrates = []

    for _ in range(n_boot):
        sample = rng.choice(nets, size=len(nets), replace=True)
        m = np.mean(sample)
        s = np.std(sample)
        boot_means.append(m)
        boot_sharpes.append(m / s * np.sqrt(252 * 24) if s > 0 else 0)
        boot_winrates.append(np.mean(sample > 0) * 100)

    boot_means = np.array(boot_means)
    boot_sharpes = np.array(boot_sharpes)
    boot_winrates = np.array(boot_winrates)

    print(f"\n  avg_net (bps/trade):")
    print(f"    Mean:  {np.mean(boot_means):+.2f}")
    print(f"    95% CI: [{np.percentile(boot_means, 2.5):+.2f}, {np.percentile(boot_means, 97.5):+.2f}]")
    print(f"    99% CI: [{np.percentile(boot_means, 0.5):+.2f}, {np.percentile(boot_means, 99.5):+.2f}]")
    print(f"    P(avg_net > 0): {np.mean(boot_means > 0)*100:.1f}%")

    print(f"\n  Sharpe:")
    print(f"    Mean:  {np.mean(boot_sharpes):.1f}")
    print(f"    95% CI: [{np.percentile(boot_sharpes, 2.5):.1f}, {np.percentile(boot_sharpes, 97.5):.1f}]")

    print(f"\n  Win Rate (%):")
    print(f"    Mean:  {np.mean(boot_winrates):.1f}%")
    print(f"    95% CI: [{np.percentile(boot_winrates, 2.5):.1f}%, {np.percentile(boot_winrates, 97.5):.1f}%]")

    # Key test: is the lower bound of 95% CI above zero?
    lower_95 = np.percentile(boot_means, 2.5)
    if lower_95 > 0:
        print(f"\n  >>> PASS: 95% CI lower bound ({lower_95:+.2f}) is ABOVE zero")
    else:
        print(f"\n  >>> FAIL: 95% CI lower bound ({lower_95:+.2f}) includes zero -- edge not statistically significant")

    return boot_means


# ── 5. Multiple Comparisons Correction ────────────────────────────────

def multiple_comparisons_test(spread_arr, rolling_data, cost_bps, n_combos_tested):
    """Estimate probability that best result is due to chance given # combos tested."""
    print(f"\n{'='*70}")
    print(f"  MULTIPLE COMPARISONS CORRECTION")
    print(f"  {n_combos_tested} parameter combinations tested")
    print(f"{'='*70}")

    # Under null hypothesis (no edge), each combo's avg_net ~ N(-cost, sigma/sqrt(n))
    # We did a grid search and picked the best -- this inflates apparent edge.

    # Bonferroni correction: for the best result to be significant at alpha=0.05,
    # it must be significant at alpha = 0.05 / n_combos_tested

    bonferroni_alpha = 0.05 / n_combos_tested
    print(f"  Bonferroni-corrected significance level: alpha = {bonferroni_alpha:.2e}")
    print(f"  (Standard alpha = 0.05, corrected for {n_combos_tested} tests)")

    # Estimate: how many independent parameters do we really have?
    # Many combos are highly correlated (e.g., window=60 and window=90 give similar signals)
    # Effective number of independent tests is much smaller
    effective_tests = n_combos_tested // 10  # rough: ~10x correlation factor
    bonferroni_effective = 0.05 / effective_tests
    print(f"\n  Estimated effective independent tests: ~{effective_tests}")
    print(f"  Adjusted significance level: alpha = {bonferroni_effective:.2e}")

    print(f"\n  INTERPRETATION:")
    print(f"  - If our best combo's p-value < {bonferroni_effective:.2e}, edge survives correction")
    print(f"  - Walk-forward validation is a MORE RELIABLE test than Bonferroni")
    print(f"  - The key question: does the edge persist OOS, not just in-sample?")


# ── 6. Structural Edge Test ───────────────────────────────────────────

def structural_edge_test(spread_arr, cost_bps):
    """Test whether the spread is mean-reverting (necessary condition for strategy)."""
    print(f"\n{'='*70}")
    print(f"  STRUCTURAL EDGE TEST: Is the spread mean-reverting?")
    print(f"{'='*70}")

    # Augmented Dickey-Fuller test
    try:
        from statsmodels.tsa.stattools import adfuller
        result = adfuller(spread_arr, maxlag=100)
        print(f"  ADF test statistic: {result[0]:.4f}")
        print(f"  p-value: {result[1]:.6f}")
        print(f"  Critical values: {result[4]}")
        if result[1] < 0.01:
            print(f"  >>> PASS: Spread is stationary (p < 0.01) -- mean reversion is real")
        elif result[1] < 0.05:
            print(f"  >>> MARGINAL: Spread is weakly stationary (p < 0.05)")
        else:
            print(f"  >>> FAIL: Cannot reject unit root (p = {result[1]:.3f}) -- spread may not be mean-reverting")
    except ImportError:
        print(f"  (statsmodels not available, skipping ADF test)")

    # Hurst exponent (H < 0.5 = mean-reverting, H > 0.5 = trending)
    # Simple R/S estimate
    n = len(spread_arr)
    max_k = min(n // 4, 500)
    lags = np.unique(np.logspace(1, np.log10(max_k), 30).astype(int))
    rs_values = []

    for lag in lags:
        n_blocks = n // lag
        if n_blocks < 2:
            continue
        rs_block = []
        for b in range(n_blocks):
            block = spread_arr[b*lag:(b+1)*lag]
            mean_block = np.mean(block)
            cumdev = np.cumsum(block - mean_block)
            R = np.max(cumdev) - np.min(cumdev)
            S = np.std(block, ddof=1)
            if S > 0:
                rs_block.append(R / S)
        if rs_block:
            rs_values.append((lag, np.mean(rs_block)))

    if len(rs_values) > 5:
        log_lags = np.log(np.array([r[0] for r in rs_values]))
        log_rs = np.log(np.array([r[1] for r in rs_values]))
        hurst = np.polyfit(log_lags, log_rs, 1)[0]
        print(f"\n  Hurst exponent (R/S method): {hurst:.3f}")
        if hurst < 0.4:
            print(f"  >>> STRONG mean-reversion (H < 0.4)")
        elif hurst < 0.5:
            print(f"  >>> Mild mean-reversion (0.4 < H < 0.5)")
        elif hurst < 0.6:
            print(f"  >>> Near random walk (H ~ 0.5)")
        else:
            print(f"  >>> TRENDING behavior (H > 0.6) -- strategy may not work")

    # Autocorrelation at lag 1 (negative = mean-reverting)
    lag1_corr = np.corrcoef(spread_arr[:-1], spread_arr[1:])[0, 1]
    print(f"\n  Lag-1 autocorrelation: {lag1_corr:.4f}")
    if lag1_corr > 0.95:
        print(f"  High persistence -- spread moves slowly, mean reversion is weak per tick")
    # First-difference autocorrelation (this is what matters for trading)
    diff = np.diff(spread_arr)
    diff_ac1 = np.corrcoef(diff[:-1], diff[1:])[0, 1]
    print(f"  Lag-1 autocorrelation of CHANGES: {diff_ac1:.4f}")
    if diff_ac1 < -0.1:
        print(f"  >>> Negative autocorrelation in changes -- supports mean-reversion")
    elif diff_ac1 < 0:
        print(f"  >>> Weakly negative -- mild mean-reversion signal")
    else:
        print(f"  >>> Non-negative -- no mean-reversion in changes")

    # Half-life of mean reversion (OU model)
    y = spread_arr[1:] - spread_arr[:-1]
    x = spread_arr[:-1] - np.mean(spread_arr)
    slope = np.sum(x * y) / np.sum(x * x)
    if slope < 0:
        half_life = -np.log(2) / slope
        print(f"\n  OU half-life: {half_life:.1f} ticks")
        print(f"  (At ~1 tick/sec, this is ~{half_life:.0f} seconds)")
    else:
        print(f"\n  OU half-life: INFINITE (spread is not mean-reverting in OU sense)")


# ── MAIN ──────────────────────────────────────────────────────────────

def main():
    data_dir = Path("data/paper_trading")
    targets = [
        ("WIF_binance_cryptocom_zscore", "binance", "cryptocom"),
        ("CRV_cryptocom_mexc_ou", "cryptocom", "mexc"),
        ("PEPE_binance_cryptocom_ou", "binance", "cryptocom"),
    ]

    windows = [20, 30, 45, 60, 90]

    # Best params from optimize_v2 (taker cost model)
    best_params = {
        "WIF_binance_cryptocom_zscore": {
            "window": 60, "entry_z": 1.5, "exit_z": 0.0,
            "vol_mult": 0.8, "cooldown": 0, "max_hold": None,
        },
        "CRV_cryptocom_mexc_ou": {
            "window": 45, "entry_z": 2.0, "exit_z": 0.3,
            "vol_mult": 1.0, "cooldown": 0, "max_hold": None,
        },
        "PEPE_binance_cryptocom_ou": {
            "window": 90, "entry_z": 2.5, "exit_z": 0.0,
            "vol_mult": 0.8, "cooldown": 30, "max_hold": None,
        },
    }

    for dir_name, ex_a, ex_b in targets:
        full_dir = data_dir / dir_name
        if not (full_dir / "ticks.jsonl").exists():
            continue

        print(f"\n\n{'#'*70}")
        print(f"#  ROBUSTNESS ANALYSIS: {dir_name}")
        print(f"{'#'*70}")

        df, det_a, det_b = load_ticks(str(full_dir))
        spread_arr = df["spread_bps"].values
        print(f"  Loaded {len(spread_arr)} spread observations")

        fee_a = TRADING_FEES_TAKER.get(ex_a, 0.001)
        fee_b = TRADING_FEES_TAKER.get(ex_b, 0.001)
        taker_cost = (fee_a + fee_b) * 10000 + 4.0
        maker_cost = 6.0

        # Use maker cost for testing since that's our actual execution plan
        cost = maker_cost
        print(f"  Testing at MAKER cost: {cost} bps")

        # Pre-compute
        rolling_data = precompute_rolling(spread_arr, windows)
        p = best_params.get(dir_name)

        # ── Test 1: Structural edge
        structural_edge_test(spread_arr, cost)

        # ── Test 2: Walk-forward
        wf_results = walk_forward(spread_arr, windows, cost, n_folds=3)

        # Also do 5-fold for more granularity if data is large enough
        if len(spread_arr) > 15000:
            wf_results_5 = walk_forward(spread_arr, windows, cost, n_folds=5)

        # ── Test 3: Random baseline
        # Get trade count from best config
        z_arr = rolling_data[p["window"]]["z"]
        std_arr = rolling_data[p["window"]]["std"]
        trades = simulate_with_trade_list(spread_arr, z_arr, std_arr, cost,
                                           p["entry_z"], p["exit_z"], p["vol_mult"],
                                           p["cooldown"], p["max_hold"])
        n_trades = len(trades)
        if n_trades >= 5:
            strategy_avg_net = np.mean([t["net"] for t in trades])
            random_nets = random_entry_baseline(spread_arr, cost, n_trades,
                                                 n_sims=5000, max_hold=60)
            # How many random simulations beat our strategy?
            pct_random_better = np.mean(random_nets >= strategy_avg_net) * 100
            print(f"\n  Strategy avg_net: {strategy_avg_net:+.2f} bps")
            print(f"  % of random strategies that beat ours: {pct_random_better:.2f}%")
            if pct_random_better < 5:
                print(f"  >>> PASS: Strategy is significantly better than random (p < 0.05)")
            elif pct_random_better < 10:
                print(f"  >>> MARGINAL: Strategy beats random at 10% level but not 5%")
            else:
                print(f"  >>> FAIL: Strategy not significantly better than random entry")

        # ── Test 4: Parameter stability
        parameter_stability(spread_arr, rolling_data, cost, p)

        # ── Test 5: Bootstrap CI
        bootstrap_ci(spread_arr, z_arr, std_arr, cost, p)

        # ── Test 6: Multiple comparisons
        n_combos = 5 * 6 * 3 * 6 * 3 * 2  # 3240
        multiple_comparisons_test(spread_arr, rolling_data, cost, n_combos)

    # ── OVERALL VERDICT ──
    print(f"\n\n{'#'*70}")
    print(f"#  OVERALL ROBUSTNESS VERDICT")
    print(f"{'#'*70}")
    print("""
  Robustness requires ALL of the following:
  1. Structural edge: ADF p < 0.01 (spread IS mean-reverting)
  2. Walk-forward: OOS profitable in >= 2/3 folds
  3. Random baseline: Strategy beats >95% of random entries
  4. Parameter stability: Neighbors of optimal also profitable
  5. Bootstrap CI: 95% CI lower bound > 0
  6. Multiple comparisons: Edge survives correction

  WHAT WE CAN'T TEST (requires more data):
  - Regime persistence: Will the spread STAY mean-reverting next week?
  - Execution risk: Will limit orders actually fill?
  - Crowding: Are other quants trading this same signal?
  - Tail risk: What happens in a flash crash or liquidity shock?

  MINIMUM REQUIREMENT FOR CONFIDENCE:
  - Need 3-5 days of V2 paper trading data (currently: 5 minutes)
  - Need to verify limit order fill rates in live market
  - Need to see strategy survive at least one regime change
""")


if __name__ == "__main__":
    main()
