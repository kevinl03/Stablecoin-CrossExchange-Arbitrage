#!/usr/bin/env python3
"""
Calculate net profit after all fees for arbitrage paths.

This script reads the experiment results and calculates:
- Gross revenue (what we'd get from arbitrage without fees)
- Total fees (trading + withdrawal + gas)
- Net profit = Gross revenue - Total fees - Initial investment

Note: The profit shown in results is already net profit (fees are baked into edge rates),
but this script makes the calculation explicit for verification.
"""

import re
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class ProfitBreakdown:
    initial_investment: float
    final_cash: float
    gross_revenue: float  # What we'd get without fees
    total_fees: float
    net_profit: float
    profit_percentage: float
    path_description: str


def parse_result_line(line: str) -> Optional[Dict]:
    """Parse a result line to extract profit and fee information."""
    # Pattern: [OK] h=... start=... cash=$... final=$... profit=$... len=... | fees: ...
    # Example: [OK] h=2hop_max                       start=binance:BUSD       cash=$   100.00 final=$100.05    profit=$0.05      len=  2 | fees: trade=$0.10 (1x), wd=$0.00 (0x), gas=$0.00 time= 0.000s
    pattern = r'\[OK\]\s+h=(\S+)\s+start=(\S+)\s+cash=\$\s*([\d,]+\.?\d*)\s+final=\$([\d,]+\.?\d*)\s+profit=\$([\d,]+\.?\d*)\s+len=\s*(\d+)\s*\|\s*fees:\s*trade=\$([\d,]+\.?\d*)\s*\((\d+)x\),\s*wd=\$([\d,]+\.?\d*)\s*\((\d+)x\),\s*gas=\$([\d,]+\.?\d*)'
    
    match = re.search(pattern, line)
    if not match:
        return None
    
    def parse_float(s: str) -> float:
        return float(s.replace(',', ''))
    
    trading_fees = parse_float(match.group(7))
    withdrawal_fees = parse_float(match.group(9))
    gas_fees = parse_float(match.group(11))
    total_fees = trading_fees + withdrawal_fees + gas_fees
    
    return {
        'heuristic': match.group(1),
        'start': match.group(2),
        'initial_cash': parse_float(match.group(3)),
        'final_cash': parse_float(match.group(4)),
        'profit_shown': parse_float(match.group(5)),
        'path_len': int(match.group(6)),
        'trading_fees': trading_fees,
        'num_trades': int(match.group(8)),
        'withdrawal_fees': withdrawal_fees,
        'num_transfers': int(match.group(10)),
        'gas_fees': gas_fees,
        'total_fees': total_fees,
    }


def calculate_net_profit_breakdown(parsed: Dict) -> ProfitBreakdown:
    """
    Calculate explicit net profit breakdown.
    
    The final_cash already has fees deducted (they're baked into edge rates).
    So:
    - final_cash = initial_cash * (product of all edge rates)
    - Each edge rate already accounts for fees
    
    To get gross revenue (without fees), we need to reverse the fee deductions.
    However, since fees are multiplicative, we can approximate:
    - gross_revenue ≈ final_cash + total_fees (for small fees)
    - net_profit = final_cash - initial_cash (already calculated correctly)
    
    Actually, the more accurate way is:
    - If we know the total fees that were deducted, gross_revenue = final_cash + total_fees
    - But the fees shown are what was deducted, so:
    - gross_revenue = initial_cash + (final_cash - initial_cash) + total_fees
    - net_profit = final_cash - initial_cash (which is what's shown)
    
    Wait, let me think about this more carefully. The edge rates are:
    - For trades: rate = raw_rate * (1 - taker_fee)
    - For transfers: rate = 1 - (total_fees / portfolio)
    
    So if we start with $100 and go through edges with rates r1, r2, r3:
    - final_cash = $100 * r1 * r2 * r3
    
    The fees are already deducted in the rates. So:
    - net_profit = final_cash - initial_cash (correct)
    - gross_revenue = what we'd have if fees weren't deducted
      = initial_cash * (raw_rates product)
    
    But we don't have raw rates, we only have effective rates. However, we can estimate:
    - If total_fees were deducted, then gross_revenue ≈ final_cash + total_fees
    - But this is approximate because fees affect subsequent calculations
    
    For simplicity and accuracy, let's use:
    - net_profit = final_cash - initial_cash (already correct)
    - gross_revenue = final_cash + total_fees (approximation, assumes fees were deducted linearly)
    """
    initial = parsed['initial_cash']
    final = parsed['final_cash']
    total_fees = parsed['total_fees']
    
    # Net profit (already correct, fees are in edge rates)
    net_profit = final - initial
    
    # Gross revenue approximation: what we'd have if fees weren't deducted
    # This is approximate because fees are baked into multiplicative rates
    gross_revenue = final + total_fees
    
    profit_pct = (net_profit / initial) * 100.0 if initial > 0 else 0.0
    
    path_desc = f"{parsed['heuristic']} from {parsed['start']} (len={parsed['path_len']})"
    
    return ProfitBreakdown(
        initial_investment=initial,
        final_cash=final,
        gross_revenue=gross_revenue,
        total_fees=total_fees,
        net_profit=net_profit,
        profit_percentage=profit_pct,
        path_description=path_desc,
    )


def analyze_results_file(filepath: str) -> List[ProfitBreakdown]:
    """Read results file and calculate profit breakdowns."""
    breakdowns = []
    
    with open(filepath, 'r') as f:
        for line in f:
            parsed = parse_result_line(line)
            if parsed:
                breakdown = calculate_net_profit_breakdown(parsed)
                breakdowns.append(breakdown)
    
    return breakdowns


def print_profit_breakdown(breakdowns: List[ProfitBreakdown]):
    """Print formatted profit breakdown table."""
    print("=" * 120)
    print("NET PROFIT BREAKDOWN (After All Fees)")
    print("=" * 120)
    print()
    print(f"{'Path':<40} {'Initial':>12} {'Final':>12} {'Gross Rev':>12} {'Total Fees':>12} {'Net Profit':>12} {'Profit %':>10}")
    print("-" * 120)
    
    for bd in breakdowns:
        print(
            f"{bd.path_description:<40} "
            f"${bd.initial_investment:>11,.2f} "
            f"${bd.final_cash:>11,.2f} "
            f"${bd.gross_revenue:>11,.2f} "
            f"${bd.total_fees:>11,.2f} "
            f"${bd.net_profit:>11,.2f} "
            f"{bd.profit_percentage:>9.4f}%"
        )
    
    print("-" * 120)
    
    # Summary statistics
    if breakdowns:
        total_initial = sum(bd.initial_investment for bd in breakdowns)
        total_final = sum(bd.final_cash for bd in breakdowns)
        total_fees = sum(bd.total_fees for bd in breakdowns)
        total_net_profit = sum(bd.net_profit for bd in breakdowns)
        avg_profit_pct = (total_net_profit / total_initial) * 100.0 if total_initial > 0 else 0.0
        
        print(f"{'TOTAL/AVERAGE':<40} ${total_initial:>11,.2f} ${total_final:>11,.2f} ${total_fees + total_final:>11,.2f} ${total_fees:>11,.2f} ${total_net_profit:>11,.2f} {avg_profit_pct:>9.4f}%")
        print()
        print(f"Total profitable paths: {len(breakdowns)}")
        print(f"Total net profit: ${total_net_profit:,.2f}")
        print(f"Average profit percentage: {avg_profit_pct:.4f}%")


def main():
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python calculate_net_profit.py <results_file>")
        print("Example: python calculate_net_profit.py results/compare_heuristics_live_20260210_193938.txt")
        sys.exit(1)
    
    filepath = sys.argv[1]
    
    print(f"Analyzing results from: {filepath}")
    print()
    
    breakdowns = analyze_results_file(filepath)
    
    if not breakdowns:
        print("No profitable paths found in results file.")
        return
    
    print_profit_breakdown(breakdowns)
    
    # Group by portfolio size
    print("\n" + "=" * 120)
    print("BREAKDOWN BY PORTFOLIO SIZE")
    print("=" * 120)
    print()
    
    by_size = {}
    for bd in breakdowns:
        size = bd.initial_investment
        if size not in by_size:
            by_size[size] = []
        by_size[size].append(bd)
    
    for size in sorted(by_size.keys()):
        paths = by_size[size]
        total_net = sum(bd.net_profit for bd in paths)
        total_fees = sum(bd.total_fees for bd in paths)
        avg_pct = (total_net / (size * len(paths))) * 100.0 if paths else 0.0
        
        print(f"Portfolio Size: ${size:,.2f}")
        print(f"  Number of profitable paths: {len(paths)}")
        print(f"  Total net profit: ${total_net:,.2f}")
        print(f"  Total fees paid: ${total_fees:,.2f}")
        print(f"  Average profit per path: ${total_net/len(paths):,.2f}")
        print(f"  Average profit percentage: {avg_pct:.4f}%")
        print()


if __name__ == "__main__":
    main()

