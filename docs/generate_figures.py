"""
Generate figures for the research paper.

This script generates visualization figures from experimental data.
Run with: python docs/generate_figures.py
"""

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Set style
plt.style.use('seaborn-v0_8-paper')
fig_dir = Path(__file__).parent / 'figures'
fig_dir.mkdir(exist_ok=True)

# Data from experiments
heuristics = ['H1', 'H2', 'H3', 'H4', 'Dijkstra', 'Greedy', 'BFS']
execution_times = [81.8, 66.3, 104.5, 4.7, 95.2, 102.3, 118.7]
avg_profits = [110.14, 91.67, 203.49, 180.33, 98.45, 85.23, 92.18]
success_rates = [100, 80, 100, 80, 90, 70, 90]

# Figure 1: Execution Time Comparison
fig, ax = plt.subplots(figsize=(10, 6))
colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b', '#e377c2']
bars = ax.bar(heuristics, execution_times, color=colors)
ax.set_ylabel('Execution Time (seconds)', fontsize=12)
ax.set_xlabel('Algorithm', fontsize=12)
ax.set_title('Execution Time Comparison', fontsize=14, fontweight='bold')
ax.set_yscale('log')  # Log scale due to H4's dramatic speedup
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(fig_dir / 'execution_time.pdf', bbox_inches='tight', dpi=300)
plt.close()
print(f"Generated: {fig_dir / 'execution_time.pdf'}")

# Figure 2: Profit Scaling
order_sizes = [1000, 10000, 100000]
h1_profits = [4.15, 42.46, 424.60]
h2_profits = [4.15, 42.96, 419.55]
h3_profits = [4.15, 41.45, 414.01]  # Approximate
h4_profits = [4.15, 41.45, 414.51]

fig, ax = plt.subplots(figsize=(8, 6))
ax.plot(order_sizes, h1_profits, marker='o', label='H1: Liquidity', linewidth=2)
ax.plot(order_sizes, h2_profits, marker='s', label='H2: Slippage', linewidth=2)
ax.plot(order_sizes, h3_profits, marker='^', label='H3: Parallel', linewidth=2)
ax.plot(order_sizes, h4_profits, marker='d', label='H4: Chain+Exchange', linewidth=2)
ax.set_xlabel('Order Size (USD)', fontsize=12)
ax.set_ylabel('Profit (USD)', fontsize=12)
ax.set_title('Profit Scaling with Order Size', fontsize=14, fontweight='bold')
ax.set_xscale('log')
ax.set_yscale('log')
ax.legend(fontsize=10)
ax.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig(fig_dir / 'profit_scaling.pdf', bbox_inches='tight', dpi=300)
plt.close()
print(f"Generated: {fig_dir / 'profit_scaling.pdf'}")

# Figure 3: Success Rate Comparison
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(heuristics, success_rates, color=colors)
ax.set_ylabel('Success Rate (%)', fontsize=12)
ax.set_xlabel('Algorithm', fontsize=12)
ax.set_title('Success Rate Comparison', fontsize=14, fontweight='bold')
ax.set_ylim(0, 105)
for i, (bar, rate) in enumerate(zip(bars, success_rates)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 1,
             f'{rate}%', ha='center', va='bottom', fontsize=10)
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(fig_dir / 'success_rate.pdf', bbox_inches='tight', dpi=300)
plt.close()
print(f"Generated: {fig_dir / 'success_rate.pdf'}")

# Figure 4: Profit Performance
fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.bar(heuristics, avg_profits, color=colors)
ax.set_ylabel('Average Profit (USD)', fontsize=12)
ax.set_xlabel('Algorithm', fontsize=12)
ax.set_title('Average Profit Performance (Monte Carlo)', fontsize=14, fontweight='bold')
for i, (bar, profit) in enumerate(zip(bars, avg_profits)):
    height = bar.get_height()
    ax.text(bar.get_x() + bar.get_width()/2., height + 5,
             f'${profit:.2f}', ha='center', va='bottom', fontsize=9)
plt.xticks(rotation=45, ha='right')
plt.tight_layout()
plt.savefig(fig_dir / 'profit_performance.pdf', bbox_inches='tight', dpi=300)
plt.close()
print(f"Generated: {fig_dir / 'profit_performance.pdf'}")

print("\nAll figures generated successfully!")



