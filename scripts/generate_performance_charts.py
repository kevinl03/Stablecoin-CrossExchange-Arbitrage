"""Generate performance charts from experimental data."""

import pandas as pd
import matplotlib.pyplot as plt
import os
import sys

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def generate_graph_construction_chart():
    """Generate graph construction time comparison chart."""
    df = pd.read_csv('data/graph_construction_times.csv')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Time comparison
    ax1.plot(df['nodes'], df['dense_time_s'], 'o-', label='Dense (Baseline)', linewidth=2)
    ax1.plot(df['nodes'], df['sparse_time_s'], 's-', label='Sparse (Optimized)', linewidth=2)
    ax1.set_xlabel('Number of Nodes', fontsize=12)
    ax1.set_ylabel('Construction Time (seconds)', fontsize=12)
    ax1.set_title('Graph Construction Time Comparison', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    # Speedup
    ax2.bar(df['nodes'], df['speedup'], color='green', alpha=0.7)
    ax2.set_xlabel('Number of Nodes', fontsize=12)
    ax2.set_ylabel('Speedup Factor', fontsize=12)
    ax2.set_title('Speedup Factor by Graph Size', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    plt.tight_layout()
    plt.savefig('docs/figures/graph_construction_performance.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: docs/figures/graph_construction_performance.png")


def generate_search_performance_chart():
    """Generate search algorithm performance chart."""
    df = pd.read_csv('data/search_performance.csv')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # Time comparison
    ax1.plot(df['nodes'], df['standard_astar_ms'], 'o-', label='Standard A*', linewidth=2)
    ax1.plot(df['nodes'], df['weighted_astar_ms'], 's-', label='Weighted A* (w=1.5)', linewidth=2)
    ax1.set_xlabel('Number of Nodes', fontsize=12)
    ax1.set_ylabel('Search Time (milliseconds)', fontsize=12)
    ax1.set_title('Search Algorithm Performance', fontsize=14, fontweight='bold')
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3)
    
    # Speedup and optimality
    ax2_twin = ax2.twinx()
    bars = ax2.bar(df['nodes'] - 5, df['speedup'], width=10, label='Speedup', alpha=0.7, color='green')
    line = ax2_twin.plot(df['nodes'], df['optimality_gap_pct'], 'ro-', label='Optimality Gap (%)', linewidth=2)
    
    ax2.set_xlabel('Number of Nodes', fontsize=12)
    ax2.set_ylabel('Speedup Factor', fontsize=12, color='green')
    ax2_twin.set_ylabel('Optimality Gap (%)', fontsize=12, color='red')
    ax2.set_title('Speedup vs. Optimality Trade-off', fontsize=14, fontweight='bold')
    ax2.grid(True, alpha=0.3, axis='y')
    
    # Combine legends
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper left', fontsize=10)
    
    plt.tight_layout()
    plt.savefig('docs/figures/search_performance.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: docs/figures/search_performance.png")


def generate_volatility_analysis_chart():
    """Generate volatility tracking analysis chart."""
    df = pd.read_csv('data/volatility_analysis.csv')
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14, 5))
    
    # False positive rate comparison
    x = range(len(df))
    width = 0.35
    ax1.bar([i - width/2 for i in x], df['static_fpr_pct'], width, label='Static Model', alpha=0.7)
    ax1.bar([i + width/2 for i in x], df['dynamic_fpr_pct'], width, label='Dynamic Model', alpha=0.7)
    ax1.set_xlabel('Market Condition', fontsize=12)
    ax1.set_ylabel('False Positive Rate (%)', fontsize=12)
    ax1.set_title('False Positive Rate by Market Volatility', fontsize=14, fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(df['market_condition'], rotation=15, ha='right')
    ax1.legend(fontsize=11)
    ax1.grid(True, alpha=0.3, axis='y')
    
    # Correlation comparison
    ax2.bar([i - width/2 for i in x], df['correlation_static'], width, label='Static Model', alpha=0.7)
    ax2.bar([i + width/2 for i in x], df['correlation_dynamic'], width, label='Dynamic Model', alpha=0.7)
    ax2.set_xlabel('Market Condition', fontsize=12)
    ax2.set_ylabel('Profit Prediction Correlation', fontsize=12)
    ax2.set_title('Prediction Accuracy by Market Volatility', fontsize=14, fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(df['market_condition'], rotation=15, ha='right')
    ax2.legend(fontsize=11)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.set_ylim([0, 1])
    
    plt.tight_layout()
    plt.savefig('docs/figures/volatility_analysis.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: docs/figures/volatility_analysis.png")


def generate_summary_chart():
    """Generate overall performance summary chart."""
    # Create summary data
    categories = ['Graph\nConstruction', 'Search\nAlgorithm', 'Memory\nUsage', 'False\nPositives', 'Survival\nRate']
    improvements = [10.9, 3.0, 9.9, 0.52, 0.40]  # Last two are percentages, not multipliers
    labels = ['10.9x', '3.0x', '9.9x', '52%', '40%']
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    colors = ['#2ecc71', '#3498db', '#9b59b6', '#e74c3c', '#f39c12']
    bars = ax.bar(categories, improvements, color=colors, alpha=0.8)
    
    # Add value labels on bars
    for i, (bar, label) in enumerate(zip(bars, labels)):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height,
                label, ha='center', va='bottom', fontsize=12, fontweight='bold')
    
    ax.set_ylabel('Improvement Factor', fontsize=12)
    ax.set_title('Overall Performance Improvements', fontsize=16, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim([0, max(improvements) * 1.2])
    
    plt.tight_layout()
    plt.savefig('docs/figures/overall_improvements.png', dpi=300, bbox_inches='tight')
    print("✓ Generated: docs/figures/overall_improvements.png")


def main():
    """Generate all performance charts."""
    print("Generating performance charts from experimental data...")
    print("="*60)
    
    # Create figures directory
    os.makedirs('docs/figures', exist_ok=True)
    
    try:
        generate_graph_construction_chart()
        generate_search_performance_chart()
        generate_volatility_analysis_chart()
        generate_summary_chart()
        
        print("="*60)
        print("✓ All charts generated successfully!")
        print("  Location: docs/figures/")
    except Exception as e:
        print(f"✗ Error generating charts: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()

