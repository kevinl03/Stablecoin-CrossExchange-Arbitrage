"""Quick analysis of paper trading results."""
import json, sys
from pathlib import Path

dirs = list(Path("data/paper_trading").iterdir())
for d in sorted(dirs):
    trades_file = d / "trades.jsonl"
    if not trades_file.exists():
        continue
    trades = [json.loads(l) for l in open(trades_file)]
    if not trades:
        print(f"\n{d.name}: 0 trades")
        continue

    total_net = sum(t["net_pnl_bps"] for t in trades)
    wins = sum(1 for t in trades if t["net_pnl_bps"] > 0)
    losses = len(trades) - wins
    avg_pnl = total_net / len(trades)
    avg_gross = sum(t["gross_pnl_bps"] for t in trades) / len(trades)
    avg_hold = sum(t["holding_sec"] for t in trades) / len(trades)

    print(f"\n{'='*60}")
    print(f"  {d.name}")
    print(f"{'='*60}")
    print(f"  Trades: {len(trades)}")
    print(f"  Wins: {wins} | Losses: {losses} | Win rate: {wins/len(trades)*100:.1f}%")
    print(f"  Total net PnL: {total_net:+.1f} bps")
    print(f"  Avg net/trade: {avg_pnl:+.2f} bps")
    print(f"  Avg gross/trade: {avg_gross:+.2f} bps")
    print(f"  Avg hold: {avg_hold:.1f}s")
    print(f"  First: {trades[0]['entry_time']}")
    print(f"  Last:  {trades[-1]['entry_time']}")
