#!/usr/bin/env python3
"""
generate_paper_figures.py — Comprehensive analysis of overnight experiment data.

Generates publication-quality figures for the Canadian AI 2026 paper.
Outputs PNGs to docs/latex/StablecoinArbitrage_CanadianAI2026/figures/
Also prints summary statistics tables for LaTeX.

Usage:
    python analysis/generate_paper_figures.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

# ── Paths ──────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = PROJECT_ROOT / "results"
FIGURES_DIR = PROJECT_ROOT / "docs" / "latex" / "StablecoinArbitrage_CanadianAI2026" / "figures"
FIGURES_DIR.mkdir(parents=True, exist_ok=True)

# ── Data files (latest timestamped run) ────────────────────────────────
# Auto-detect the latest file for each experiment type
def _latest_jsonl(prefix: str) -> Path:
    candidates = sorted(RESULTS_DIR.glob(f"{prefix}_*.jsonl"), reverse=True)
    if not candidates:
        raise FileNotFoundError(f"No JSONL file found for prefix: {prefix}")
    return candidates[0]

CACHED_GRAPH_FILE = _latest_jsonl("cached_graph_experiment")
MONTE_CARLO_FILE = _latest_jsonl("monte_carlo_heuristics")
GRAPH_SCALING_FILE = _latest_jsonl("graph_scaling")
OVERNIGHT_FILE = _latest_jsonl("overnight_snapshots")
STALENESS_FILE = _latest_jsonl("quote_staleness")
SENSITIVITY_FILE = _latest_jsonl("sensitivity_sweep")
SLIPPAGE_FILE = _latest_jsonl("slippage_vwap")

# ── Style ──────────────────────────────────────────────────────────────
plt.rcParams.update({
    "font.size": 11,
    "axes.titlesize": 13,
    "axes.labelsize": 12,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "legend.fontsize": 9,
    "figure.dpi": 150,
    "savefig.dpi": 300,
    "savefig.bbox": "tight",
    "axes.grid": True,
    "grid.alpha": 0.3,
})

HEURISTIC_COLORS = {
    "dijkstra": "#888888",
    "h1_liquidity": "#2196F3",
    "h2_slippage": "#4CAF50",
    "parallel_baseline": "#FF9800",
    "h3_chaincongestion_exchange_risk": "#9C27B0",
    "3hop_enum": "#F44336",
    "bellman_ford": "#795548",
    "simple_1hop": "#BDBDBD",
    "simple_2hop": "#9E9E9E",
}

HEURISTIC_LABELS = {
    "dijkstra": "Dijkstra (h=0)",
    "h1_liquidity": "H1: Liquidity",
    "h2_slippage": "H2: Slippage",
    "parallel_baseline": "H3: Parallel",
    "h3_chaincongestion_exchange_risk": "H4: Congestion/Risk",
    "3hop_enum": "3-Hop Baseline",
    "bellman_ford": "Bellman-Ford",
    "simple_1hop": "1-Hop Baseline",
    "simple_2hop": "2-Hop Baseline",
}

HEURISTIC_LABEL_MAP = {
    "h4_chaincongestion_exchange_risk": "h3_chaincongestion_exchange_risk",
    "h3_parallel": "parallel_baseline",
}

def _label(h: str) -> str:
    return HEURISTIC_LABELS.get(h, h)

def _color(h: str) -> str:
    return HEURISTIC_COLORS.get(h, "#000000")

def _load_jsonl(path: Path) -> list[dict]:
    recs = []
    with path.open() as f:
        for line in f:
            line = line.strip()
            if line:
                recs.append(json.loads(line))
    return recs

def _save(fig, name: str):
    out = FIGURES_DIR / f"{name}.png"
    fig.savefig(out)
    plt.close(fig)
    print(f"  ✅ Saved: {out.name}")


# ======================================================================
# FIGURE 1: Node Expansion Comparison (PRIORITY 1)
# Conclusion: H2 prunes ~30% of nodes vs Dijkstra
# ======================================================================
def fig01_node_expansion_bar():
    recs = _load_jsonl(CACHED_GRAPH_FILE)
    # Filter to successful searches only
    recs = [r for r in recs if r["success"] and r.get("nodes_expanded")]

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "h3_chaincongestion_exchange_risk", "3hop_enum"]
    data = {}
    for h in heur_order:
        vals = [r["nodes_expanded"] for r in recs if r["heuristic"] == h]
        if vals:
            data[h] = {"mean": np.mean(vals), "std": np.std(vals), "vals": vals}

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(data))
    keys = list(data.keys())
    means = [data[k]["mean"] for k in keys]
    stds = [data[k]["std"] for k in keys]
    colors = [_color(k) for k in keys]

    bars = ax.bar(x, means, yerr=stds, color=colors, capsize=5, edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([_label(k) for k in keys], rotation=15, ha="right")
    ax.set_ylabel("Avg. Nodes Expanded")
    ax.set_title("Node Expansions by Search Strategy\n(Cached Graph, Same Market Snapshot)")

    # Add value labels on bars
    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 5,
                f"{mean:.0f}", ha="center", va="bottom", fontsize=9)

    # Add Dijkstra reference line
    dijk_mean = data.get("dijkstra", {}).get("mean", 0)
    if dijk_mean:
        ax.axhline(dijk_mean, color="#888888", linestyle="--", alpha=0.5, label=f"Dijkstra baseline ({dijk_mean:.0f})")
        ax.legend()

    _save(fig, "fig01_node_expansion_bar")


# ======================================================================
# FIGURE 2: Compute Time Comparison (PRIORITY 1)
# Conclusion: Pure compute time differences (no I/O noise)
# ======================================================================
def fig02_compute_time_bar():
    recs = _load_jsonl(CACHED_GRAPH_FILE)

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "h3_chaincongestion_exchange_risk", "3hop_enum"]
    data = {}
    for h in heur_order:
        vals = [r["compute_time_sec"] for r in recs if r["heuristic"] == h]
        if vals:
            data[h] = {"mean": np.mean(vals), "std": np.std(vals)}

    fig, ax = plt.subplots(figsize=(8, 5))
    x = np.arange(len(data))
    keys = list(data.keys())
    means = [data[k]["mean"] * 1000 for k in keys]  # Convert to ms
    stds = [data[k]["std"] * 1000 for k in keys]
    colors = [_color(k) for k in keys]

    bars = ax.bar(x, means, yerr=stds, color=colors, capsize=5, edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels([_label(k) for k in keys], rotation=15, ha="right")
    ax.set_ylabel("Avg. Compute Time (ms)")
    ax.set_title("Pure Compute Time by Search Strategy\n(Cached Graph, I/O Excluded)")

    for bar, mean in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f"{mean:.1f}ms", ha="center", va="bottom", fontsize=9)

    _save(fig, "fig02_compute_time_bar")


# ======================================================================
# FIGURE 3: Profit Distribution Box Plots (PRIORITY 1)
# Conclusion: Heuristic quality & consistency across 500 MC trials
# ======================================================================
def fig03_profit_boxplot():
    recs = _load_jsonl(MONTE_CARLO_FILE)

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage", "parallel_baseline",
                  "h3_chaincongestion_exchange_risk", "3hop_enum"]

    fig, ax = plt.subplots(figsize=(10, 6))
    plot_data = []
    labels = []
    colors = []
    for h in heur_order:
        profits = [r["profit_usd"] for r in recs if r["heuristic"] == h and r["success"]]
        if profits:
            plot_data.append(profits)
            labels.append(_label(h))
            colors.append(_color(h))

    bp = ax.boxplot(plot_data, labels=labels, patch_artist=True, showfliers=True,
                    flierprops=dict(marker=".", markersize=3, alpha=0.3))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Profit (USD)")
    ax.set_title("Profit Distribution by Heuristic\n(Monte Carlo, 500 Trials per Heuristic)")
    ax.set_xticklabels(labels, rotation=15, ha="right")

    _save(fig, "fig03_profit_boxplot")


# ======================================================================
# FIGURE 4: Success Rate Comparison (PRIORITY 1)
# Conclusion: H3 parallel dominates; baselines fail completely
# ======================================================================
def fig04_success_rate():
    recs = _load_jsonl(MONTE_CARLO_FILE)

    heur_order = ["simple_1hop", "simple_2hop", "bellman_ford", "3hop_enum",
                  "dijkstra", "h1_liquidity", "h2_slippage", "parallel_baseline",
                  "h3_chaincongestion_exchange_risk"]

    fig, ax = plt.subplots(figsize=(10, 5))
    rates = []
    labels = []
    colors = []
    for h in heur_order:
        subset = [r for r in recs if r["heuristic"] == h]
        if subset:
            rate = 100 * sum(1 for r in subset if r["success"]) / len(subset)
            rates.append(rate)
            labels.append(_label(h))
            colors.append(_color(h))

    x = np.arange(len(rates))
    bars = ax.bar(x, rates, color=colors, edgecolor="black", linewidth=0.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right")
    ax.set_ylabel("Success Rate (%)")
    ax.set_ylim(0, 105)
    ax.set_title("Arbitrage Path Discovery Rate\n(Monte Carlo, 500 Trials per Strategy)")

    for bar, rate in zip(bars, rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 1,
                f"{rate:.0f}%", ha="center", va="bottom", fontsize=9)

    _save(fig, "fig04_success_rate")


# ======================================================================
# FIGURE 5: Node Expansion vs Profit Scatter (PRIORITY 2)
# Conclusion: H2 achieves high profit with fewer expansions
# ======================================================================
def fig05_expansion_vs_profit():
    recs = _load_jsonl(MONTE_CARLO_FILE)

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "h3_chaincongestion_exchange_risk", "3hop_enum"]

    fig, ax = plt.subplots(figsize=(8, 6))
    for h in heur_order:
        subset = [r for r in recs if r["heuristic"] == h and r["success"]
                  and r.get("nodes_expanded")]
        if subset:
            expanded = [r["nodes_expanded"] for r in subset]
            profits = [r["profit_usd"] for r in subset]
            ax.scatter(expanded, profits, alpha=0.3, s=15, color=_color(h),
                      label=_label(h))

    ax.set_xlabel("Nodes Expanded")
    ax.set_ylabel("Profit (USD)")
    ax.set_title("Search Effort vs. Profit Found\n(Monte Carlo Trials)")
    ax.legend(loc="upper right")
    _save(fig, "fig05_expansion_vs_profit")


# ======================================================================
# FIGURE 6: Graph Scaling — Nodes & Edges vs Exchanges (PRIORITY 2)
# Conclusion: Graph grows quadratically; heuristics help more at scale
# ======================================================================
def fig06_graph_scaling_structure():
    recs = _load_jsonl(GRAPH_SCALING_FILE)

    sizes = sorted(set(r["n_exchanges"] for r in recs))
    nodes_by_size = {}
    edges_by_size = {}
    for sz in sizes:
        subset = [r for r in recs if r["n_exchanges"] == sz]
        nodes_by_size[sz] = subset[0]["n_nodes"]
        edges_by_size[sz] = subset[0]["n_edges"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: graph structure
    ax1.plot(sizes, [nodes_by_size[s] for s in sizes], "o-", color="#2196F3", label="Nodes", linewidth=2)
    ax1.plot(sizes, [edges_by_size[s] for s in sizes], "s-", color="#F44336", label="Edges", linewidth=2)
    ax1.set_xlabel("Number of Exchanges")
    ax1.set_ylabel("Count")
    ax1.set_title("Graph Size vs. Exchange Count")
    ax1.legend()

    # Right: success rate by size
    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage", "h3_chaincongestion_exchange_risk"]
    for h in heur_order:
        rates = []
        for sz in sizes:
            subset = [r for r in recs if r["n_exchanges"] == sz and r["heuristic"] == h]
            if subset:
                rate = 100 * sum(1 for r in subset if r["success"]) / len(subset)
                rates.append(rate)
            else:
                rates.append(0)
        if any(r > 0 for r in rates):
            ax2.plot(sizes, rates, "o-", color=_color(h), label=_label(h), linewidth=2)

    ax2.set_xlabel("Number of Exchanges")
    ax2.set_ylabel("Success Rate (%)")
    ax2.set_title("Path Discovery vs. Graph Size")
    ax2.legend()
    ax2.set_ylim(0, 105)

    fig.suptitle("Graph Scaling Analysis", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig06_graph_scaling")


# ======================================================================
# FIGURE 7: Graph Scaling — Compute Time vs Exchanges (PRIORITY 2)
# Conclusion: Heuristic overhead is constant; Dijkstra scales worse
# ======================================================================
def fig07_graph_scaling_time():
    recs = _load_jsonl(GRAPH_SCALING_FILE)

    sizes = sorted(set(r["n_exchanges"] for r in recs))
    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage", "h3_chaincongestion_exchange_risk"]

    fig, ax = plt.subplots(figsize=(8, 5))
    for h in heur_order:
        times = []
        for sz in sizes:
            subset = [r for r in recs if r["n_exchanges"] == sz and r["heuristic"] == h]
            if subset:
                avg_t = np.mean([r["compute_sec"] for r in subset]) * 1000
                times.append(avg_t)
            else:
                times.append(0)
        ax.plot(sizes, times, "o-", color=_color(h), label=_label(h), linewidth=2)

    ax.set_xlabel("Number of Exchanges")
    ax.set_ylabel("Avg. Compute Time (ms)")
    ax.set_title("Compute Time Scaling with Graph Size")
    ax.legend()
    _save(fig, "fig07_graph_scaling_time")


# ======================================================================
# FIGURE 8: Graph Scaling — Node Expansions vs Exchanges (PRIORITY 2)
# Conclusion: Heuristics keep expansions lower as graph grows
# ======================================================================
def fig08_graph_scaling_expansions():
    recs = _load_jsonl(GRAPH_SCALING_FILE)

    sizes = sorted(set(r["n_exchanges"] for r in recs))
    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage", "h3_chaincongestion_exchange_risk"]

    fig, ax = plt.subplots(figsize=(8, 5))
    for h in heur_order:
        expansions = []
        for sz in sizes:
            subset = [r for r in recs if r["n_exchanges"] == sz
                      and r["heuristic"] == h and r["success"]
                      and r.get("nodes_expanded")]
            if subset:
                avg_exp = np.mean([r["nodes_expanded"] for r in subset])
                expansions.append(avg_exp)
            else:
                expansions.append(0)
        if any(e > 0 for e in expansions):
            ax.plot(sizes, expansions, "o-", color=_color(h), label=_label(h), linewidth=2)

    ax.set_xlabel("Number of Exchanges")
    ax.set_ylabel("Avg. Nodes Expanded")
    ax.set_title("Node Expansions vs. Graph Size\n(Successful Searches Only)")
    ax.legend()
    _save(fig, "fig08_graph_scaling_expansions")


# ======================================================================
# FIGURE 9: Quote Staleness Survival Curve (PRIORITY 1)
# Conclusion: Profits survive up to 5 min; execution window exists
# ======================================================================
def fig09_quote_staleness():
    recs = _load_jsonl(STALENESS_FILE)

    delays = sorted(set(r["delay_sec"] for r in recs))

    # Overall survival
    survival = []
    avg_decay = []
    for d in delays:
        subset = [r for r in recs if r["delay_sec"] == d]
        survived = sum(1 for r in subset if r["still_profitable"])
        rate = 100 * survived / len(subset) if subset else 0
        survival.append(rate)
        decays = [r["profit_decay_pct"] for r in subset if r["profit_decay_pct"] is not None]
        avg_decay.append(np.mean(decays) if decays else 0)

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Left: survival rate
    ax1.plot(delays, survival, "o-", color="#2196F3", linewidth=2, markersize=8)
    ax1.fill_between(delays, survival, alpha=0.2, color="#2196F3")
    ax1.set_xlabel("Delay (seconds)")
    ax1.set_ylabel("Paths Still Profitable (%)")
    ax1.set_title("Arbitrage Path Survival Rate")
    ax1.set_ylim(90, 101)
    ax1.set_xscale("log")
    for d, s in zip(delays, survival):
        ax1.annotate(f"{s:.0f}%", (d, s), textcoords="offset points",
                    xytext=(0, 10), ha="center", fontsize=9)

    # Right: profit change
    ax2.bar(range(len(delays)), avg_decay, color=["#4CAF50" if d < 0 else "#F44336" for d in avg_decay],
            edgecolor="black", linewidth=0.5)
    ax2.set_xticks(range(len(delays)))
    ax2.set_xticklabels([f"{d}s" for d in delays])
    ax2.set_xlabel("Delay")
    ax2.set_ylabel("Avg. Profit Change (%)")
    ax2.set_title("Profit Evolution After Delay")
    ax2.axhline(0, color="black", linewidth=0.5)

    fig.suptitle("Quote Staleness Analysis", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig09_quote_staleness")


# ======================================================================
# FIGURE 10: Overnight Temporal Profit Time Series (PRIORITY 1)
# Conclusion: Arbitrage opportunities exist consistently over 8 hours
# ======================================================================
def fig10_overnight_timeseries():
    recs = _load_jsonl(OVERNIGHT_FILE)
    results = [r for r in recs if r.get("type") == "result"]

    # Group by snapshot
    snapshots = defaultdict(list)
    for r in results:
        snapshots[r["snapshot_idx"]].append(r)

    snap_indices = sorted(snapshots.keys())
    timestamps = []
    avg_profits = []
    max_profits = []
    success_rates = []

    for idx in snap_indices:
        group = snapshots[idx]
        ts = group[0].get("timestamp")
        if ts:
            timestamps.append(datetime.fromisoformat(ts))
        else:
            timestamps.append(None)

        successes = [r for r in group if r["success"]]
        if successes:
            profits = [r["profit_usd"] for r in successes]
            avg_profits.append(np.mean(profits))
            max_profits.append(max(profits))
        else:
            avg_profits.append(0)
            max_profits.append(0)
        success_rates.append(100 * len(successes) / len(group))

    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 8), sharex=True)

    # Top: profit over time
    valid_ts = [t for t in timestamps if t is not None]
    if valid_ts:
        ax1.plot(valid_ts, avg_profits[:len(valid_ts)], "-", color="#2196F3",
                label="Avg Profit", linewidth=1.5, alpha=0.8)
        ax1.fill_between(valid_ts, 0, max_profits[:len(valid_ts)], alpha=0.15, color="#4CAF50")
        ax1.plot(valid_ts, max_profits[:len(valid_ts)], "-", color="#4CAF50",
                label="Max Profit", linewidth=1, alpha=0.6)
        ax1.set_ylabel("Profit (USD)")
        ax1.set_title("Arbitrage Profit Over 8 Hours (96 Snapshots, 5-min Intervals)")
        ax1.legend()

        # Bottom: success rate
        ax2.plot(valid_ts, success_rates[:len(valid_ts)], "-", color="#FF9800", linewidth=1.5)
        ax2.fill_between(valid_ts, success_rates[:len(valid_ts)], alpha=0.2, color="#FF9800")
        ax2.set_ylabel("Success Rate (%)")
        ax2.set_xlabel("Time (UTC)")
        ax2.set_ylim(0, 105)
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    else:
        ax1.plot(snap_indices, avg_profits, "-", color="#2196F3", label="Avg Profit")
        ax1.plot(snap_indices, max_profits, "-", color="#4CAF50", label="Max Profit")
        ax1.set_ylabel("Profit (USD)")
        ax1.legend()
        ax2.plot(snap_indices, success_rates, "-", color="#FF9800")
        ax2.set_ylabel("Success Rate (%)")
        ax2.set_xlabel("Snapshot Index")

    fig.tight_layout()
    _save(fig, "fig10_overnight_timeseries")


# ======================================================================
# FIGURE 11: Overnight Heuristic Comparison Over Time (PRIORITY 2)
# Conclusion: Different heuristics dominate at different market times
# ======================================================================
def fig11_overnight_heuristic_comparison():
    recs = _load_jsonl(OVERNIGHT_FILE)
    results = [r for r in recs if r.get("type") == "result" and r["success"]]

    # Group by snapshot+heuristic, average profit
    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "h3_chaincongestion_exchange_risk", "3hop_enum"]

    snapshots = sorted(set(r["snapshot_idx"] for r in results))

    fig, ax = plt.subplots(figsize=(12, 6))
    for h in heur_order:
        snap_profits = []
        snap_ts = []
        for idx in snapshots:
            subset = [r for r in results if r["snapshot_idx"] == idx and r["heuristic"] == h]
            if subset:
                snap_profits.append(np.mean([r["profit_usd"] for r in subset]))
                ts = subset[0].get("timestamp")
                snap_ts.append(datetime.fromisoformat(ts) if ts else idx)
            else:
                snap_profits.append(0)
                snap_ts.append(None)

        valid = [(t, p) for t, p in zip(snap_ts, snap_profits) if t is not None]
        if valid:
            ts_vals, p_vals = zip(*valid)
            ax.plot(ts_vals, p_vals, "-", color=_color(h), label=_label(h),
                   linewidth=1.2, alpha=0.8)

    ax.set_xlabel("Time (UTC)")
    ax.set_ylabel("Avg. Profit (USD)")
    ax.set_title("Heuristic Performance Over 8 Hours")
    ax.legend(loc="upper right")
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
    _save(fig, "fig11_overnight_heuristic_comparison")


# ======================================================================
# FIGURE 12: Sensitivity — H1 Lambda Effect (PRIORITY 2)
# Conclusion: λ=1.0 is a good default; extremes hurt
# ======================================================================
def fig12_sensitivity_h1_lambda():
    recs = _load_jsonl(SENSITIVITY_FILE)
    h1_recs = [r for r in recs if r["sweep"] == "h1_lambda"]

    lambdas = sorted(set(r["lambda"] for r in h1_recs))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    # Profit vs lambda
    profits_by_lambda = {}
    expanded_by_lambda = {}
    for lam in lambdas:
        subset = [r for r in h1_recs if r["lambda"] == lam and r["success"]]
        if subset:
            profits_by_lambda[lam] = [r["profit"] for r in subset]
            expanded_by_lambda[lam] = [r["nodes_expanded"] for r in subset if r.get("nodes_expanded")]

    bp1 = ax1.boxplot([profits_by_lambda.get(l, [0]) for l in lambdas],
                      labels=[str(l) for l in lambdas], patch_artist=True)
    for patch in bp1["boxes"]:
        patch.set_facecolor("#2196F3")
        patch.set_alpha(0.7)
    ax1.set_xlabel("λ (H1 Weight)")
    ax1.set_ylabel("Profit (USD)")
    ax1.set_title("H1 Lambda vs. Profit")

    # Nodes expanded vs lambda
    means = [np.mean(expanded_by_lambda.get(l, [0])) for l in lambdas]
    ax2.plot(lambdas, means, "o-", color="#4CAF50", linewidth=2, markersize=8)
    ax2.set_xlabel("λ (H1 Weight)")
    ax2.set_ylabel("Avg. Nodes Expanded")
    ax2.set_title("H1 Lambda vs. Search Effort")

    fig.suptitle("H1 Liquidity Heuristic Sensitivity", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig12_sensitivity_h1_lambda")


# ======================================================================
# FIGURE 13: Sensitivity — H2 Lambda/Threshold Heatmap (PRIORITY 2)
# Conclusion: H2 is robust across parameter ranges
# ======================================================================
def fig13_sensitivity_h2_heatmap():
    recs = _load_jsonl(SENSITIVITY_FILE)
    h2_recs = [r for r in recs if r["sweep"] == "h2_lambda_threshold"]

    lambdas = sorted(set(r["lambda"] for r in h2_recs))
    thresholds = sorted(set(r["threshold_bps"] for r in h2_recs))

    # Build profit matrix
    profit_matrix = np.zeros((len(lambdas), len(thresholds)))
    success_matrix = np.zeros((len(lambdas), len(thresholds)))

    for i, lam in enumerate(lambdas):
        for j, thr in enumerate(thresholds):
            subset = [r for r in h2_recs if r["lambda"] == lam and r["threshold_bps"] == thr]
            successes = [r for r in subset if r["success"]]
            if successes:
                profit_matrix[i, j] = np.mean([r["profit"] for r in successes])
            success_matrix[i, j] = 100 * len(successes) / len(subset) if subset else 0

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    im1 = ax1.imshow(profit_matrix, cmap="YlGn", aspect="auto")
    ax1.set_xticks(range(len(thresholds)))
    ax1.set_xticklabels([f"{t}" for t in thresholds])
    ax1.set_yticks(range(len(lambdas)))
    ax1.set_yticklabels([f"{l}" for l in lambdas])
    ax1.set_xlabel("Threshold (bps)")
    ax1.set_ylabel("λ (H2 Weight)")
    ax1.set_title("Avg. Profit (USD)")
    fig.colorbar(im1, ax=ax1, shrink=0.8)
    # Add text annotations
    for i in range(len(lambdas)):
        for j in range(len(thresholds)):
            ax1.text(j, i, f"${profit_matrix[i,j]:.2f}",
                    ha="center", va="center", fontsize=8)

    im2 = ax2.imshow(success_matrix, cmap="RdYlGn", aspect="auto", vmin=0, vmax=100)
    ax2.set_xticks(range(len(thresholds)))
    ax2.set_xticklabels([f"{t}" for t in thresholds])
    ax2.set_yticks(range(len(lambdas)))
    ax2.set_yticklabels([f"{l}" for l in lambdas])
    ax2.set_xlabel("Threshold (bps)")
    ax2.set_ylabel("λ (H2 Weight)")
    ax2.set_title("Success Rate (%)")
    fig.colorbar(im2, ax=ax2, shrink=0.8)
    for i in range(len(lambdas)):
        for j in range(len(thresholds)):
            ax2.text(j, i, f"{success_matrix[i,j]:.0f}%",
                    ha="center", va="center", fontsize=8)

    fig.suptitle("H2 Slippage Heuristic Parameter Sensitivity", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig13_sensitivity_h2_heatmap")


# ======================================================================
# FIGURE 14: Sensitivity — Order Size Effect (PRIORITY 2)
# Conclusion: Larger orders find bigger absolute profit
# ======================================================================
def fig14_sensitivity_order_size():
    recs = _load_jsonl(SENSITIVITY_FILE)
    os_recs = [r for r in recs if r["sweep"] == "order_size"]

    if not os_recs:
        print("  ⚠️  No order_size sweep data, skipping fig14")
        return

    cash_levels = sorted(set(r["cash_usd"] for r in os_recs))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    profits = []
    pct_returns = []
    for cash in cash_levels:
        subset = [r for r in os_recs if r["cash_usd"] == cash and r["success"]]
        if subset:
            avg_p = np.mean([r["profit"] for r in subset])
            profits.append(avg_p)
            pct_returns.append(100 * avg_p / cash)
        else:
            profits.append(0)
            pct_returns.append(0)

    ax1.bar(range(len(cash_levels)), profits, color="#2196F3", edgecolor="black", linewidth=0.5)
    ax1.set_xticks(range(len(cash_levels)))
    ax1.set_xticklabels([f"${c:,.0f}" for c in cash_levels], rotation=15)
    ax1.set_xlabel("Order Size (USD)")
    ax1.set_ylabel("Avg. Profit (USD)")
    ax1.set_title("Absolute Profit vs. Order Size")

    ax2.bar(range(len(cash_levels)), pct_returns, color="#4CAF50", edgecolor="black", linewidth=0.5)
    ax2.set_xticks(range(len(cash_levels)))
    ax2.set_xticklabels([f"${c:,.0f}" for c in cash_levels], rotation=15)
    ax2.set_xlabel("Order Size (USD)")
    ax2.set_ylabel("Return (%)")
    ax2.set_title("Percentage Return vs. Order Size")

    fig.suptitle("Order Size Sensitivity", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig14_sensitivity_order_size")


# ======================================================================
# FIGURE 15: Sensitivity — Max Depth Effect (PRIORITY 3)
# Conclusion: Deeper search doesn't always help
# ======================================================================
def fig15_sensitivity_max_depth():
    recs = _load_jsonl(SENSITIVITY_FILE)
    md_recs = [r for r in recs if r["sweep"] == "max_depth"]

    if not md_recs:
        print("  ⚠️  No max_depth sweep data, skipping fig15")
        return

    depths = sorted(set(r["max_depth"] for r in md_recs))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    profits = []
    times = []
    for d in depths:
        subset = [r for r in md_recs if r["max_depth"] == d]
        successes = [r for r in subset if r["success"]]
        profits.append(np.mean([r["profit"] for r in successes]) if successes else 0)
        times.append(np.mean([r["compute_sec"] for r in subset]) * 1000)

    ax1.bar(range(len(depths)), profits, color="#2196F3", edgecolor="black", linewidth=0.5)
    ax1.set_xticks(range(len(depths)))
    ax1.set_xticklabels([str(d) for d in depths])
    ax1.set_xlabel("Max Depth (hops)")
    ax1.set_ylabel("Avg. Profit (USD)")
    ax1.set_title("Profit vs. Max Depth")

    ax2.bar(range(len(depths)), times, color="#FF9800", edgecolor="black", linewidth=0.5)
    ax2.set_xticks(range(len(depths)))
    ax2.set_xticklabels([str(d) for d in depths])
    ax2.set_xlabel("Max Depth (hops)")
    ax2.set_ylabel("Compute Time (ms)")
    ax2.set_title("Compute Time vs. Max Depth")

    fig.suptitle("Max Depth Sensitivity", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig15_sensitivity_max_depth")


# ======================================================================
# FIGURE 16: Profit by Cash Level — Overnight (PRIORITY 2)
# Conclusion: Higher capital → higher absolute profit, same %
# ======================================================================
def fig16_profit_by_cash():
    recs = _load_jsonl(OVERNIGHT_FILE)
    results = [r for r in recs if r.get("type") == "result" and r["success"]]

    cash_levels = sorted(set(r["cash_usd"] for r in results))

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "h3_chaincongestion_exchange_risk", "3hop_enum"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    width = 0.15
    x = np.arange(len(cash_levels))
    for i, h in enumerate(heur_order):
        abs_profits = []
        pct_returns = []
        for cash in cash_levels:
            subset = [r for r in results if r["cash_usd"] == cash and r["heuristic"] == h]
            if subset:
                avg_p = np.mean([r["profit_usd"] for r in subset])
                abs_profits.append(avg_p)
                pct_returns.append(100 * avg_p / cash)
            else:
                abs_profits.append(0)
                pct_returns.append(0)
        ax1.bar(x + i * width, abs_profits, width, color=_color(h), label=_label(h))
        ax2.bar(x + i * width, pct_returns, width, color=_color(h), label=_label(h))

    ax1.set_xticks(x + width * 2)
    ax1.set_xticklabels([f"${c:,.0f}" for c in cash_levels])
    ax1.set_xlabel("Initial Capital (USD)")
    ax1.set_ylabel("Avg. Profit (USD)")
    ax1.set_title("Absolute Profit by Capital Level")
    ax1.legend(fontsize=7)

    ax2.set_xticks(x + width * 2)
    ax2.set_xticklabels([f"${c:,.0f}" for c in cash_levels])
    ax2.set_xlabel("Initial Capital (USD)")
    ax2.set_ylabel("Return (%)")
    ax2.set_title("Percentage Return by Capital Level")

    fig.suptitle("Capital Sensitivity (8-Hour Overnight Data)", fontsize=14, y=1.02)
    fig.tight_layout()
    _save(fig, "fig16_profit_by_cash")


# ======================================================================
# FIGURE 17: MC — Nodes Expanded Distribution (PRIORITY 2)
# Conclusion: H2 consistently uses fewer expansions
# ======================================================================
def fig17_expansion_distribution():
    recs = _load_jsonl(MONTE_CARLO_FILE)

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "h3_chaincongestion_exchange_risk"]

    fig, ax = plt.subplots(figsize=(8, 5))
    plot_data = []
    labels = []
    colors = []
    for h in heur_order:
        vals = [r["nodes_expanded"] for r in recs
                if r["heuristic"] == h and r["success"] and r.get("nodes_expanded")]
        if vals:
            plot_data.append(vals)
            labels.append(_label(h))
            colors.append(_color(h))

    bp = ax.boxplot(plot_data, labels=labels, patch_artist=True,
                    flierprops=dict(marker=".", markersize=3, alpha=0.3))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.set_ylabel("Nodes Expanded")
    ax.set_title("Search Effort Distribution\n(Monte Carlo, 500 Trials)")
    ax.set_xticklabels(labels, rotation=15, ha="right")
    _save(fig, "fig17_expansion_distribution")


# ======================================================================
# FIGURE 18: Combined Summary — Radar Chart (PRIORITY 3)
# Conclusion: Each heuristic has different strengths
# ======================================================================
def fig18_radar_summary():
    recs_mc = _load_jsonl(MONTE_CARLO_FILE)

    heur_order = ["dijkstra", "h1_liquidity", "h2_slippage",
                  "parallel_baseline", "h3_chaincongestion_exchange_risk"]

    categories = ["Success\nRate", "Avg\nProfit", "Speed\n(1/time)", "Pruning\n(1/expanded)", "Consistency\n(1/std)"]
    N = len(categories)

    fig, ax = plt.subplots(figsize=(8, 8), subplot_kw=dict(polar=True))
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles += angles[:1]

    for h in heur_order:
        subset = [r for r in recs_mc if r["heuristic"] == h]
        successes = [r for r in subset if r["success"]]

        # Normalize metrics to 0-1
        success_rate = len(successes) / len(subset) if subset else 0
        avg_profit = np.mean([r["profit_usd"] for r in successes]) if successes else 0
        avg_time = np.mean([r["duration_sec"] for r in subset]) if subset else 1
        expanded = [r["nodes_expanded"] for r in successes if r.get("nodes_expanded")]
        avg_expanded = np.mean(expanded) if expanded else 500
        profit_std = np.std([r["profit_usd"] for r in successes]) if successes else 100

        values = [
            success_rate,
            min(avg_profit / 50, 1.0),
            min(1.0 / (avg_time + 0.001), 1.0),
            min(200 / (avg_expanded + 1), 1.0),
            min(1.0 / (profit_std + 0.1), 1.0),
        ]
        values += values[:1]

        ax.plot(angles, values, "o-", linewidth=2, label=_label(h), color=_color(h))
        ax.fill(angles, values, alpha=0.1, color=_color(h))

    ax.set_xticks(angles[:-1])
    ax.set_xticklabels(categories)
    ax.set_ylim(0, 1.05)
    ax.set_title("Heuristic Performance Radar\n(Normalized Metrics, Monte Carlo)", pad=20)
    ax.legend(loc="upper right", bbox_to_anchor=(1.3, 1.1))
    _save(fig, "fig18_radar_summary")


# ======================================================================
# FIGURE 19: Path Length Distribution (PRIORITY 3)
# Conclusion: Most profitable paths are 3 hops
# ======================================================================
def fig19_path_length():
    recs = _load_jsonl(OVERNIGHT_FILE)
    results = [r for r in recs if r.get("type") == "result" and r["success"]]

    path_lens = [r["path_len"] for r in results]
    unique_lens = sorted(set(path_lens))

    fig, ax = plt.subplots(figsize=(8, 5))
    counts = [path_lens.count(l) for l in unique_lens]
    ax.bar(unique_lens, counts, color="#2196F3", edgecolor="black", linewidth=0.5)
    ax.set_xlabel("Path Length (hops)")
    ax.set_ylabel("Frequency")
    ax.set_title("Distribution of Profitable Path Lengths\n(8-Hour Overnight Data)")

    for x, c in zip(unique_lens, counts):
        ax.text(x, c + 5, str(c), ha="center", fontsize=9)

    _save(fig, "fig19_path_length")


# ======================================================================
# FIGURE 20: Heuristic Comparison Table (printed, not plotted)
# ======================================================================
def table_summary():
    print("\n" + "=" * 80)
    print("SUMMARY TABLE FOR LATEX")
    print("=" * 80)

    # Monte Carlo summary
    recs = _load_jsonl(MONTE_CARLO_FILE)
    print("\nTable: Monte Carlo Heuristic Comparison (500 trials each)")
    print(f"{'Heuristic':<35s} {'Success':>8s} {'Avg Profit':>12s} {'Avg Expanded':>14s} {'Avg Time':>10s}")
    print("-" * 80)

    heur_order = ["simple_1hop", "simple_2hop", "bellman_ford", "3hop_enum",
                  "dijkstra", "h1_liquidity", "h2_slippage", "parallel_baseline",
                  "h3_chaincongestion_exchange_risk"]
    for h in heur_order:
        subset = [r for r in recs if r["heuristic"] == h]
        successes = [r for r in subset if r["success"]]
        n = len(subset)
        s = len(successes)
        avg_p = np.mean([r["profit_usd"] for r in successes]) if successes else 0
        expanded = [r["nodes_expanded"] for r in successes if r.get("nodes_expanded")]
        avg_e = np.mean(expanded) if expanded else 0
        avg_t = np.mean([r["duration_sec"] for r in subset]) * 1000
        print(f"{_label(h):<35s} {s:>3d}/{n:<4d} ${avg_p:>10.4f} {avg_e:>14.0f} {avg_t:>9.2f}ms")

    # Graph scaling summary
    print("\n\nTable: Graph Scaling")
    recs = _load_jsonl(GRAPH_SCALING_FILE)
    sizes = sorted(set(r["n_exchanges"] for r in recs))
    print(f"{'Exchanges':>10s} {'Nodes':>6s} {'Edges':>6s} {'Success Rate':>13s}")
    print("-" * 40)
    for sz in sizes:
        subset = [r for r in recs if r["n_exchanges"] == sz]
        successes = [r for r in subset if r["success"]]
        print(f"{sz:>10d} {subset[0]['n_nodes']:>6d} {subset[0]['n_edges']:>6d} "
              f"{100*len(successes)/len(subset):>12.0f}%")

    # Quote staleness summary
    print("\n\nTable: Quote Staleness Survival")
    recs = _load_jsonl(STALENESS_FILE)
    delays = sorted(set(r["delay_sec"] for r in recs))
    print(f"{'Delay (s)':>10s} {'Survived':>10s} {'Avg Decay':>10s}")
    print("-" * 35)
    for d in delays:
        subset = [r for r in recs if r["delay_sec"] == d]
        survived = sum(1 for r in subset if r["still_profitable"])
        rate = 100 * survived / len(subset)
        decays = [r["profit_decay_pct"] for r in subset if r["profit_decay_pct"] is not None]
        avg_d = np.mean(decays) if decays else 0
        print(f"{d:>10d} {rate:>9.0f}% {avg_d:>+9.1f}%")


# ======================================================================
# MAIN
# ======================================================================
def main():
    print(f"📊 Generating figures → {FIGURES_DIR}")
    print(f"   Data: {RESULTS_DIR}\n")

    print("Priority 1 — Core Claims:")
    fig01_node_expansion_bar()
    fig02_compute_time_bar()
    fig03_profit_boxplot()
    fig04_success_rate()
    fig09_quote_staleness()
    fig10_overnight_timeseries()

    print("\nPriority 2 — Scalability & Robustness:")
    fig05_expansion_vs_profit()
    fig06_graph_scaling_structure()
    fig07_graph_scaling_time()
    fig08_graph_scaling_expansions()
    fig11_overnight_heuristic_comparison()
    fig12_sensitivity_h1_lambda()
    fig13_sensitivity_h2_heatmap()
    fig14_sensitivity_order_size()
    fig16_profit_by_cash()
    fig17_expansion_distribution()

    print("\nPriority 3 — Supporting:")
    fig15_sensitivity_max_depth()
    fig18_radar_summary()
    fig19_path_length()

    print("\n📋 Summary Tables:")
    table_summary()

    print(f"\n\n✅ Done! {len(list(FIGURES_DIR.glob('*.png')))} figures saved to:")
    print(f"   {FIGURES_DIR}")


if __name__ == "__main__":
    main()

