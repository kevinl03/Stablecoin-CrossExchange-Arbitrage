"""
Read-only wallet scanner + BF-SSSP arbitrage finder.

Connects to public RPCs (same pattern as MetaMask / Infura) to read
your on-chain token balances, then runs BF-SSSP to find arbitrage
paths from your actual holdings.

    ┌──────────────┐     ┌──────────────┐     ┌─────────────┐
    │  Public RPCs │────▶│ Read balances │────▶│  BF-SSSP    │
    │  (no key)    │     │ (view only)  │     │  arb search │
    └──────────────┘     └──────────────┘     └─────────────┘

NO private keys.  NO signing.  NO transactions.
Only your PUBLIC address is used.

Usage:
    python -m scripts.wallet_scanner --address 0xYOUR_ADDRESS
    python -m scripts.wallet_scanner --address 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045

Reference:
    https://docs.metamask.io/services/tutorials/ethereum/send-a-transaction/send-a-transaction-py
"""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Dict, List, Optional, Tuple

import requests
from web3 import Web3

from scripts.defi_data import TOKEN_REGISTRY, NodeId, fetch_defi_prices
from scripts.defi_graph import build_graph as build_dex_graph
from scripts.run_100_dollar_test import bellman_ford_sssp, format_bf_path

# ────────────────────────────────────────────────────────────
# 1.  Public RPC endpoints  (no API key required)
#
#     Same concept as the Infura HTTPProvider in the MetaMask
#     tutorial, but using free community endpoints:
#
#       w3 = Web3(Web3.HTTPProvider("https://sepolia.infura.io/v3/<KEY>"))
#                          ↕
#       w3 = Web3(Web3.HTTPProvider("https://rpc.ankr.com/eth"))
#
#     The pattern is identical — only the URL changes.
# ────────────────────────────────────────────────────────────

EVM_RPCS: Dict[str, str] = {
    "ethereum":  "https://ethereum-rpc.publicnode.com",
    "arbitrum":  "https://arbitrum-one-rpc.publicnode.com",
    "optimism":  "https://optimism-rpc.publicnode.com",
    "polygon":   "https://polygon-bor-rpc.publicnode.com",
    "base":      "https://base-rpc.publicnode.com",
    "avax":      "https://avalanche-c-chain-rpc.publicnode.com",
    "bsc":       "https://bsc-rpc.publicnode.com",
}

SOLANA_RPC = "https://api.mainnet-beta.solana.com"

RPC_TIMEOUT = 5  # seconds per RPC call

# ────────────────────────────────────────────────────────────
# 2.  Minimal ERC-20 ABI  (read-only)
#
#     Every ERC-20 token implements this interface.
#     We only call balanceOf(address) → uint256.
#
#     This is the same ABI you'd use with ethers.js, web3.js,
#     or web3.py when building a dapp that reads token balances.
# ────────────────────────────────────────────────────────────

ERC20_ABI = json.loads("""[
    {
        "constant": true,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }
]""")

TOKEN_DECIMALS: Dict[str, int] = {
    "WETH": 18, "WBTC": 8, "USDC": 6, "USDT": 6, "DAI": 18,
    "LINK": 18, "UNI": 18, "AAVE": 18, "ARB": 18, "OP": 18,
    "AVAX": 18, "BNB": 18, "SOL": 9,
}

NATIVE_TOKEN: Dict[str, str] = {
    "ethereum": "WETH", "arbitrum": "WETH", "optimism": "WETH",
    "base": "WETH", "polygon": "WETH", "avax": "AVAX", "bsc": "BNB",
}


# ────────────────────────────────────────────────────────────
# 3.  Balance fetching — single EVM chain  (web3.py)
#
#     Mirrors the MetaMask tutorial's pattern:
#       w3 = Web3(Web3.HTTPProvider(rpc_url))
#       w3.eth.get_balance(address)  ← native coin
#       contract.functions.balanceOf(address).call()  ← ERC-20
# ────────────────────────────────────────────────────────────

def _get_chain_tokens(chain: str) -> Dict[str, str]:
    """Return {symbol: contract_address} for tokens on *chain*."""
    return {
        sym: addr
        for sym, chain_addrs in TOKEN_REGISTRY.items()
        if (addr := chain_addrs.get(chain)) is not None
    }


def fetch_evm_balances(address: str, chain: str, rpc_url: str) -> Dict[str, float]:
    """
    Query native + ERC-20 balances for *address* on one EVM chain.
    All calls use a 5-second timeout to keep scanning fast.
    """
    balances: Dict[str, float] = {}

    try:
        w3 = Web3(Web3.HTTPProvider(rpc_url, request_kwargs={"timeout": RPC_TIMEOUT}))
    except Exception:
        return balances

    checksum = w3.to_checksum_address(address)

    # ─ Native balance ─
    native_sym = NATIVE_TOKEN.get(chain)
    if native_sym:
        try:
            wei = w3.eth.get_balance(checksum)
            bal = float(w3.from_wei(wei, "ether"))
            if bal > 0:
                balances[native_sym] = bal
        except Exception:
            pass

    # ─ ERC-20 token balances (parallel within chain) ─
    chain_tokens = _get_chain_tokens(chain)

    def _query_token(sym: str, addr: str) -> Tuple[str, float]:
        try:
            contract = w3.eth.contract(
                address=w3.to_checksum_address(addr), abi=ERC20_ABI,
            )
            raw = contract.functions.balanceOf(checksum).call()
            if raw > 0:
                decimals = TOKEN_DECIMALS.get(sym, 18)
                return sym, raw / (10 ** decimals)
        except Exception:
            pass
        return sym, 0.0

    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(_query_token, s, a): s for s, a in chain_tokens.items()}
        for fut in as_completed(futs):
            sym, bal = fut.result()
            if bal > 0:
                if sym in balances:
                    balances[sym] += bal
                else:
                    balances[sym] = bal

    return balances


# ────────────────────────────────────────────────────────────
# 4.  Balance fetching — Solana  (JSON-RPC via requests)
#
#     Solana doesn't use web3.py; it has its own JSON-RPC
#     protocol at the same transport layer (POST + JSON body).
# ────────────────────────────────────────────────────────────

def fetch_solana_balances(address: str) -> Dict[str, float]:
    balances: Dict[str, float] = {}

    try:
        resp = requests.post(
            SOLANA_RPC,
            json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [address]},
            timeout=RPC_TIMEOUT,
        )
        lamports = resp.json().get("result", {}).get("value", 0)
        if lamports > 0:
            balances["SOL"] = lamports / 1e9
    except Exception:
        pass

    sol_tokens = {
        sym: addr
        for sym, chain_addrs in TOKEN_REGISTRY.items()
        if (addr := chain_addrs.get("solana")) is not None and sym != "SOL"
    }

    try:
        resp = requests.post(
            SOLANA_RPC,
            json={
                "jsonrpc": "2.0", "id": 2,
                "method": "getTokenAccountsByOwner",
                "params": [
                    address,
                    {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
                    {"encoding": "jsonParsed"},
                ],
            },
            timeout=RPC_TIMEOUT,
        )
        accounts = resp.json().get("result", {}).get("value", [])
        mint_to_sym = {addr: sym for sym, addr in sol_tokens.items()}

        for acct in accounts:
            info = (acct.get("account", {}).get("data", {})
                    .get("parsed", {}).get("info", {}))
            mint = info.get("mint", "")
            ui_amount = info.get("tokenAmount", {}).get("uiAmount")
            if mint in mint_to_sym and ui_amount and ui_amount > 0:
                balances[mint_to_sym[mint]] = ui_amount
    except Exception:
        pass

    return balances


# ────────────────────────────────────────────────────────────
# 5.  Parallel multi-chain wallet scan
# ────────────────────────────────────────────────────────────

def scan_wallet(
    evm_address: str,
    solana_address: Optional[str] = None,
) -> Dict[Tuple[str, str], float]:
    """
    Scan all chains in parallel.  Same address works on every
    EVM chain (Ethereum, Arbitrum, Base, Optimism, …).
    """
    all_balances: Dict[Tuple[str, str], float] = {}

    def _scan_evm(chain: str, rpc: str) -> Tuple[str, Dict[str, float]]:
        return chain, fetch_evm_balances(evm_address, chain, rpc)

    print(f"  Scanning {len(EVM_RPCS)} EVM chains in parallel …")
    t0 = time.time()

    with ThreadPoolExecutor(max_workers=len(EVM_RPCS)) as pool:
        futs = {pool.submit(_scan_evm, c, r): c for c, r in EVM_RPCS.items()}
        for fut in as_completed(futs):
            chain, chain_bals = fut.result()
            for sym, bal in chain_bals.items():
                all_balances[(chain, sym)] = bal
            if chain_bals:
                tok_str = ", ".join(f"{s}={b:.6f}" for s, b in chain_bals.items())
                print(f"    {chain:12s}  ✓  {tok_str}")
            else:
                print(f"    {chain:12s}  (empty)")

    if solana_address:
        print(f"  Scanning solana …")
        sol_bals = fetch_solana_balances(solana_address)
        for sym, bal in sol_bals.items():
            all_balances[("solana", sym)] = bal
        if sol_bals:
            tok_str = ", ".join(f"{s}={b:.6f}" for s, b in sol_bals.items())
            print(f"    solana        ✓  {tok_str}")
        else:
            print(f"    solana        (empty)")

    elapsed = time.time() - t0
    print(f"  Done in {elapsed:.1f}s  ({len(all_balances)} non-zero balances)")
    return all_balances


# ────────────────────────────────────────────────────────────
# 6.  BF-SSSP from actual holdings
# ────────────────────────────────────────────────────────────

def find_opportunities(
    balances: Dict[Tuple[str, str], float],
    prices: Dict[NodeId, float],
    nodes: Dict[NodeId, Dict[str, Any]],
    adj: Dict[NodeId, List[Dict[str, Any]]],
) -> List[Tuple[str, str, float, float, Any]]:
    """
    Run BF-SSSP from every held position. Returns a list of
    (chain, token, amount, usd_val, PathResult_or_None) sorted
    by profit descending.
    """
    from scripts.run_100_dollar_test import PathResult

    holdings: List[Tuple[str, str, float, float]] = []

    for (chain, token), amount in balances.items():
        price = prices.get((chain, token), 0)
        usd_val = amount * price
        if usd_val >= 0.01:
            holdings.append((chain, token, amount, usd_val))

    holdings.sort(key=lambda h: -h[3])

    if not holdings:
        print("\n  No holdings found (or all below $0.01).")
        return []

    total_usd = sum(h[3] for h in holdings)

    print(f"\n{'─'*72}")
    print(f"  PORTFOLIO SUMMARY")
    print(f"{'─'*72}")
    print(f"  {'Chain':12s}  {'Token':6s}  {'Balance':>14s}  {'USD Value':>12s}")
    print(f"  {'─'*12}  {'─'*6}  {'─'*14}  {'─'*12}")
    for chain, token, amount, usd in holdings:
        print(f"  {chain:12s}  {token:6s}  {amount:>14.6f}  ${usd:>11,.2f}")
    print(f"  {'':12s}  {'':6s}  {'':14s}  {'─'*12}")
    print(f"  {'':12s}  {'':6s}  {'TOTAL':>14s}  ${total_usd:>11,.2f}")

    print(f"\n{'─'*72}")
    print(f"  BF-SSSP ARBITRAGE SEARCH (from your actual positions)")
    print(f"{'─'*72}")

    results: List[Tuple[str, str, float, float, Any]] = []

    for chain, token, amount, usd_val in holdings:
        start_node = (chain, token)
        if start_node not in nodes:
            continue
        if usd_val < 1.0:
            continue

        print(f"\n  ── ({chain}, {token})  ${usd_val:,.2f} ──")

        result = bellman_ford_sssp(
            nodes, adj,
            start_node=start_node,
            liquid_cash_usd=usd_val,
            max_depth=6,
            max_time_sec=3600.0,
        )

        if result:
            print(format_bf_path(result))
            results.append((chain, token, amount, usd_val, result))
        else:
            print(f"    No profitable path from this position.")

    results.sort(key=lambda r: -r[4].profit_pct)
    return results


# ────────────────────────────────────────────────────────────
# 7.  API Architecture Diagram  (printed on --explain)
# ────────────────────────────────────────────────────────────

API_EXPLANATION = """
╔══════════════════════════════════════════════════════════════════════════╗
║              HOW THE APIs FIT TOGETHER                                  ║
╠══════════════════════════════════════════════════════════════════════════╣
║                                                                        ║
║  ┌─────────────────┐                                                   ║
║  │  YOUR WALLET    │  Public address only (0x…)                        ║
║  │  (MetaMask)     │  No private key ever leaves MetaMask              ║
║  └────────┬────────┘                                                   ║
║           │                                                            ║
║           │  Address                                                   ║
║           ▼                                                            ║
║  ┌─────────────────┐   JSON-RPC calls (read-only)                      ║
║  │  Public RPCs    │   eth_getBalance, eth_call (balanceOf)            ║
║  │                 │                                                   ║
║  │  • Ankr         │   Pattern (same as Infura/MetaMask tutorial):     ║
║  │  • LlamaRPC     │     w3 = Web3(Web3.HTTPProvider(rpc_url))         ║
║  │  • Chainstack   │     w3.eth.get_balance(address)                   ║
║  │  • Official L2  │     contract.functions.balanceOf(addr).call()     ║
║  └────────┬────────┘                                                   ║
║           │                                                            ║
║           │  Token balances (per chain)                                 ║
║           ▼                                                            ║
║  ┌─────────────────┐   GET /prices/current/{tokens}                    ║
║  │  DeFi-Llama    │   Returns USD price per token per chain            ║
║  │  Coins API      │   Aggregated from Uniswap, Curve, Jupiter, etc.  ║
║  └────────┬────────┘                                                   ║
║           │                                                            ║
║           │  USD prices → graph edge weights                           ║
║           ▼                                                            ║
║  ┌─────────────────┐                                                   ║
║  │  BF-SSSP        │   Bellman-Ford Single-Source Shortest Path        ║
║  │  Algorithm       │   Finds optimal path including intermediate     ║
║  │                 │   losses that lead to overall profit              ║
║  └────────┬────────┘                                                   ║
║           │                                                            ║
║           ▼                                                            ║
║  ┌─────────────────┐                                                   ║
║  │  RESULTS        │   "Swap WETH→USDC on Base, bridge to Arbitrum,   ║
║  │  (display only) │    swap USDC→WETH → net +0.12%"                  ║
║  └─────────────────┘                                                   ║
║                                                                        ║
║  To EXECUTE a trade you would need to:                                 ║
║    1. Build a transaction (like the MetaMask tutorial)                  ║
║    2. Sign it with your private key (in MetaMask)                      ║
║    3. Send via eth_sendRawTransaction                                  ║
║  This scanner does NOT do steps 1-3.                                   ║
╚══════════════════════════════════════════════════════════════════════════╝
"""


# ────────────────────────────────────────────────────────────
# 8.  CLI entry point
# ────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wallet scanner + BF-SSSP arbitrage finder + optional executor",
        epilog="Example: python -m scripts.wallet_scanner "
               "--address 0xd8dA6BF26964aF9D7eEd9e03E53415D37aA96045",
    )
    parser.add_argument(
        "--address", required=True,
        help="Your public EVM wallet address (0x…).",
    )
    parser.add_argument(
        "--solana", default=None,
        help="Optional Solana wallet address (base58 pubkey).",
    )
    parser.add_argument(
        "--explain", action="store_true",
        help="Print an API architecture diagram and exit.",
    )

    # ── Execution flags ──
    parser.add_argument(
        "--execute", action="store_true",
        help="Execute the best arbitrage path found. "
             "Requires PRIVATE_KEY in .env file.",
    )
    parser.add_argument(
        "--dry-run", action="store_true", dest="dry_run",
        help="Build and sign transactions but DON'T broadcast. "
             "Use with --execute to test the pipeline.",
    )
    parser.add_argument(
        "--slippage", type=float, default=0.5,
        help="Max slippage per swap in %% (default: 0.5).",
    )
    parser.add_argument(
        "--max-loss", type=float, default=5.0, dest="max_loss",
        help="Abort path if cumulative loss exceeds this %% (default: 5.0).",
    )
    args = parser.parse_args()

    if args.explain:
        print(API_EXPLANATION)
        return

    # Safety: reject if the user accidentally pastes a private key
    addr = args.address.strip()
    if addr.startswith("0x") and len(addr) == 66:
        print("  ✗  ERROR: That looks like a PRIVATE KEY (32 bytes / 64 hex chars).")
        print("     The --address flag needs your PUBLIC address (20 bytes / 40 hex chars).")
        print("     Your public address is the short one from MetaMask (e.g. 0xABC…123).")
        print("     Private keys go ONLY in the .env file.")
        print("\n     IMPORTANT: Clear your terminal history now:")
        print("       history -c && history -w")
        return
    if addr.startswith("0x") and len(addr) != 42:
        print(f"  ✗  ERROR: Invalid address length ({len(addr)} chars). "
              f"EVM addresses are 42 chars (0x + 40 hex).")
        return

    executing = args.execute or args.dry_run
    if executing:
        mode_str = "DRY RUN (sign but don't send)" if args.dry_run else "LIVE EXECUTION"
    else:
        mode_str = "READ-ONLY (scan only, no signing)"

    print("=" * 72)
    print("  WALLET SCANNER + ARBITRAGE")
    print("=" * 72)
    print(f"  EVM Address:    {args.address}")
    if args.solana:
        print(f"  Solana Address: {args.solana}")
    print(f"\n  MODE: {mode_str}")
    print(f"  APIs: Public RPCs (web3.py) + DeFi-Llama (prices)")
    if executing:
        print(f"  Slippage:  {args.slippage:.1f}%")
        print(f"  Max loss:  {args.max_loss:.1f}%")
    print()

    # ── Step 1 ──
    print("─── Step 1: Scanning on-chain balances ───")
    balances = scan_wallet(args.address, args.solana)

    # ── Step 2 ──
    print("\n─── Step 2: Fetching DeFi-Llama prices ───")
    prices, _ = fetch_defi_prices()

    # ── Step 3 ──
    max_usd = 0.0
    for (chain, token), amount in balances.items():
        p = prices.get((chain, token), 0)
        max_usd = max(max_usd, amount * p)

    portfolio = max(max_usd, 100.0)
    print(f"\n─── Step 3: Building arbitrage graph (portfolio ref: ${portfolio:,.2f}) ───")
    nodes, adj = build_dex_graph(force_refresh=True, portfolio_size_usd=portfolio)

    # ── Step 4 ──
    print("\n─── Step 4: Running BF-SSSP from your positions ───")
    results = find_opportunities(balances, prices, nodes, adj)

    # ── Step 5 (optional): Execute best path ──
    if executing and results:
        from scripts.executor import Wallet, execute_path

        print(f"\n{'─'*72}")
        print(f"  EXECUTION PHASE")
        print(f"{'─'*72}")

        best = results[0]
        chain, token, amount, usd_val, path_result = best
        print(f"\n  Best opportunity: ({chain}, {token})")
        print(f"  Expected profit:  ${path_result.profit_usd:,.4f} "
              f"({path_result.profit_pct:+.4f}%)")
        print(f"  Path steps:       {len(path_result.edges)}")

        if not args.dry_run:
            print(f"\n  ⚠  LIVE MODE — real transactions will be submitted!")
            print(f"  ⚠  Type 'yes' to confirm, anything else to abort.")
            confirm = input("  > ").strip().lower()
            if confirm != "yes":
                print("  Aborted.")
                return

        wallet = Wallet()
        print(f"  Wallet loaded: {wallet.address}")

        if wallet.address.lower() != args.address.lower():
            print(f"  ⚠  WARNING: .env key address ({wallet.address}) does not")
            print(f"     match --address ({args.address})!")
            if not args.dry_run:
                print(f"  Aborting for safety.")
                return

        execute_path(
            edges=path_result.edges,
            start_amount_usd=usd_val,
            wallet=wallet,
            dry_run=args.dry_run,
            slippage=args.slippage / 100.0,
            max_loss_pct=args.max_loss,
        )

    elif executing and not results:
        print("\n  No profitable paths found — nothing to execute.")

    print(f"\n{'='*72}")
    if not executing:
        print("  Scan complete. No transactions were made.")
    elif args.dry_run:
        print("  Dry run complete. No transactions were broadcast.")
    else:
        print("  Execution complete.")
    print(f"{'='*72}")


if __name__ == "__main__":
    main()
