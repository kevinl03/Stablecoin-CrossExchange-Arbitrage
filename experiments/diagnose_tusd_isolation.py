#!/usr/bin/env python3
# ======================================================================
# diagnose_tusd_isolation.py — Why is mexc:TUSD completely isolated?
# ======================================================================

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.graph import build_graph, NodeId

# ── Main ───────────────────────────────────────────────────────────────

def main() -> int:
    print()
    print("=" * 80)
    print("DIAGNOSING TUSD ISOLATION")
    print("=" * 80)
    print()

    print("[1] Building graph...")
    start = time.time()
    nodes, edges = build_graph()
    elapsed = time.time() - start
    print(f"    ✓ Graph ready ({len(nodes)} nodes, {len(edges)} edges) in {elapsed:.1f}s")
    print()

    # Find all nodes and edges related to TUSD
    print("[2] Finding all TUSD-related nodes...")
    tusd_nodes = [(ex, coin) for ex, coin in nodes.keys() if coin == "TUSD"]
    print(f"    ✓ Found {len(tusd_nodes)} TUSD nodes:")
    for node in sorted(tusd_nodes):
        print(f"      - {node[0]}:{node[1]}")
    print()

    # Find all edges involving TUSD
    print("[3] Finding all edges involving TUSD...")
    print()
    
    tusd_edges = []
    for from_node, edge_list in edges.items():
        if from_node[1] == "TUSD":  # From a TUSD node
            for edge in edge_list:
                to_node = edge.get("to")
                if to_node:
                    tusd_edges.append((from_node, to_node, edge))
        # Check edges TO TUSD nodes
        for edge in edge_list:
            to_node = edge.get("to")
            if to_node and to_node[1] == "TUSD":
                tusd_edges.append((from_node, to_node, edge))

    print(f"    Found {len(tusd_edges)} edges involving TUSD")
    print()
    
    # Group by exchange
    by_exchange = {}
    for from_node, to_node, edge in tusd_edges:
        key = f"{from_node[0]}:{from_node[1]} → {to_node[0]}:{to_node[1]}"
        by_exchange[key] = edge
    
    if tusd_edges:
        print("    Edges FROM TUSD nodes:")
        for key, edge in sorted(by_exchange.items()):
            if key.split(" → ")[0].endswith(":TUSD"):
                print(f"      {key}")
                print(f"        Kind: {edge.get('kind')}, Profit: ${edge.get('profit_usd', 0):.2f}")
        print()
        
        print("    Edges TO TUSD nodes:")
        for key, edge in sorted(by_exchange.items()):
            if key.split(" → ")[1].endswith(":TUSD"):
                print(f"      {key}")
                print(f"        Kind: {edge.get('kind')}, Profit: ${edge.get('profit_usd', 0):.2f}")
    else:
        print("    ⚠ NO EDGES INVOLVING TUSD FOUND!")
    
    print()
    print("=" * 80)
    print("DIAGNOSIS")
    print("=" * 80)
    print()
    
    # Check outgoing edges from mexc:TUSD
    print("[4] Checking outgoing edges from mexc:TUSD specifically...")
    mexc_tusd_edges = edges.get(("mexc", "TUSD"), [])
    print(f"    Found {len(mexc_tusd_edges)} outgoing edges from mexc:TUSD")
    
    if mexc_tusd_edges:
        for edge in mexc_tusd_edges:
            to_node = edge.get("to")
            profit = edge.get("profit_usd", 0)
            kind = edge.get("kind")
            print(f"      → {to_node[0]}:{to_node[1]} ({kind}, profit=${profit:.2f})")
    else:
        print("    ✗ NO OUTGOING EDGES FROM mexc:TUSD!")
        print("    ✗ This explains why it's trapped!")
    
    print()
    print("[5] Checking incoming edges to mexc:TUSD...")
    incoming = []
    for from_node, edge_list in edges.items():
        for edge in edge_list:
            if edge.get("to") == ("mexc", "TUSD"):
                incoming.append((from_node, edge))
    
    print(f"    Found {len(incoming)} incoming edges to mexc:TUSD")
    if incoming:
        for from_node, edge in incoming:
            profit = edge.get("profit_usd", 0)
            kind = edge.get("kind")
            print(f"      ← {from_node[0]}:{from_node[1]} ({kind}, profit=${profit:.2f})")
    
    print()
    print("=" * 80)
    print("ROOT CAUSE ANALYSIS")
    print("=" * 80)
    print()
    
    if not mexc_tusd_edges:
        print("✓ ROOT CAUSE FOUND:")
        print()
        print("  mexc:TUSD has NO OUTGOING EDGES in the arbitrage graph!")
        print()
        print("  This means:")
        print("  1. There are no profitable trading pairs FROM TUSD on mexc")
        print("  2. There are no transfer routes OUT of mexc:TUSD")
        print("  3. The wallet is completely trapped with no way to exit")
        print()
        print("  Why?")
        print("  - TUSD is a niche stablecoin (not widely traded)")
        print("  - The arbitrage graph only includes edges with POSITIVE profit")
        print("  - Converting TUSD → USDT/USDC on mexc loses money")
        print("  - No other exchange has mexc:TUSD → transfer path configured")
    else:
        print(f"⚠ Unexpected: Found {len(mexc_tusd_edges)} outgoing edges")
        print("  This contradicts the escape analysis finding no paths!")
    
    print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
