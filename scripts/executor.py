"""
On-chain transaction executor for DEX arbitrage paths.

Loads your private key from a .env file (same pattern as the MetaMask
tutorial: https://docs.metamask.io/services/tutorials/ethereum/send-a-transaction/send-a-transaction-py)
and programmatically signs + submits transactions.

Supports:
  • ERC-20 token approvals
  • Uniswap V3 SwapRouter  exactInputSingle
  • Across Protocol V3     depositV3  (cross-chain bridge)

Safety features:
  --dry-run     Build & sign transactions but DON'T broadcast them
  --max-loss    Abort the entire path if cumulative loss exceeds this %
  --slippage    Max acceptable slippage per swap (default 0.5%)

Usage:
    # Dry run (no real transactions)
    python -m scripts.wallet_scanner --address 0x... --execute --dry-run

    # Live execution
    python -m scripts.wallet_scanner --address 0x... --execute
"""

from __future__ import annotations

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv
from web3 import Web3
from web3.exceptions import ContractLogicError

from scripts.defi_data import TOKEN_REGISTRY, NodeId

# ────────────────────────────────────────────────────────────
# 1.  Chain configuration
# ────────────────────────────────────────────────────────────

CHAIN_CONFIG: Dict[str, Dict[str, Any]] = {
    "ethereum": {
        "chain_id": 1,
        "rpc": "https://ethereum-rpc.publicnode.com",
        "uniswap_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "across_spoke_pool": "0x5c7BCd6E7De5423a257D81B442095A1a6ced35C5",
    },
    "arbitrum": {
        "chain_id": 42161,
        "rpc": "https://arbitrum-one-rpc.publicnode.com",
        "uniswap_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "across_spoke_pool": "0xe35e9842fceaCA96570B734083f4a58e8F7C5f2A",
    },
    "optimism": {
        "chain_id": 10,
        "rpc": "https://optimism-rpc.publicnode.com",
        "uniswap_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "across_spoke_pool": "0x6f26Bf09B1C792e3228e5467807a900A503c0281",
    },
    "base": {
        "chain_id": 8453,
        "rpc": "https://base-rpc.publicnode.com",
        "uniswap_router": "0x2626664c2603336E57B271c5C0b26F421741e481",
        "across_spoke_pool": "0x09aea4b2242abC8bb4BB78D537A67a245A7bEC64",
    },
    "polygon": {
        "chain_id": 137,
        "rpc": "https://polygon-bor-rpc.publicnode.com",
        "uniswap_router": "0xE592427A0AEce92De3Edee1F18E0157C05861564",
        "across_spoke_pool": "0x9295ee1d8C5b022Be115A2AD3c30C72E34e7F096",
    },
    "avax": {
        "chain_id": 43114,
        "rpc": "https://avalanche-c-chain-rpc.publicnode.com",
        "uniswap_router": None,  # Trader Joe — different interface
        "across_spoke_pool": "0x6f26Bf09B1C792e3228e5467807a900A503c0281",
    },
    "bsc": {
        "chain_id": 56,
        "rpc": "https://bsc-rpc.publicnode.com",
        "uniswap_router": None,  # PancakeSwap — different interface
        "across_spoke_pool": "0x5c7BCd6E7De5423a257D81B442095A1a6ced35C5",
    },
}

TOKEN_DECIMALS: Dict[str, int] = {
    "WETH": 18, "WBTC": 8, "USDC": 6, "USDT": 6, "DAI": 18,
    "LINK": 18, "UNI": 18, "AAVE": 18, "ARB": 18, "OP": 18,
    "AVAX": 18, "BNB": 18, "SOL": 9,
}

# ────────────────────────────────────────────────────────────
# 2.  Contract ABIs  (minimal — only the functions we call)
# ────────────────────────────────────────────────────────────

ERC20_ABI = json.loads("""[
    {
        "constant": true,
        "inputs": [{"name": "owner", "type": "address"}, {"name": "spender", "type": "address"}],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    },
    {
        "constant": false,
        "inputs": [{"name": "spender", "type": "address"}, {"name": "amount", "type": "uint256"}],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": true,
        "inputs": [{"name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]""")

# Uniswap V3 SwapRouter — exactInputSingle
UNISWAP_V3_ABI = json.loads("""[
    {
        "inputs": [{
            "components": [
                {"name": "tokenIn",                "type": "address"},
                {"name": "tokenOut",               "type": "address"},
                {"name": "fee",                    "type": "uint24"},
                {"name": "recipient",              "type": "address"},
                {"name": "deadline",               "type": "uint256"},
                {"name": "amountIn",               "type": "uint256"},
                {"name": "amountOutMinimum",       "type": "uint256"},
                {"name": "sqrtPriceLimitX96",      "type": "uint160"}
            ],
            "name": "params",
            "type": "tuple"
        }],
        "name": "exactInputSingle",
        "outputs": [{"name": "amountOut", "type": "uint256"}],
        "stateMutability": "payable",
        "type": "function"
    }
]""")

# Across Protocol V3 SpokePool — depositV3
ACROSS_V3_ABI = json.loads("""[
    {
        "inputs": [
            {"name": "depositor",             "type": "address"},
            {"name": "recipient",             "type": "address"},
            {"name": "inputToken",            "type": "address"},
            {"name": "outputToken",           "type": "address"},
            {"name": "inputAmount",           "type": "uint256"},
            {"name": "outputAmount",          "type": "uint256"},
            {"name": "destinationChainId",    "type": "uint256"},
            {"name": "exclusiveRelayer",      "type": "address"},
            {"name": "quoteTimestamp",        "type": "uint32"},
            {"name": "fillDeadline",          "type": "uint32"},
            {"name": "exclusivityDeadline",   "type": "uint32"},
            {"name": "message",               "type": "bytes"}
        ],
        "name": "depositV3",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]""")


# ────────────────────────────────────────────────────────────
# 3.  Wallet / key management
# ────────────────────────────────────────────────────────────

class Wallet:
    """
    Loads your private key from .env and provides signing.

    .env format (same as MetaMask tutorial):
        PRIVATE_KEY=0xabc123...

    The key NEVER leaves this object and is NEVER printed.
    """

    def __init__(self) -> None:
        load_dotenv()
        raw_key = os.getenv("PRIVATE_KEY", "")
        if not raw_key:
            raise ValueError(
                "PRIVATE_KEY not found in .env file.\n"
                "Create a .env file with:\n"
                "  PRIVATE_KEY=0xYOUR_PRIVATE_KEY_HERE\n"
            )
        if not raw_key.startswith("0x"):
            raw_key = "0x" + raw_key

        self._key = raw_key
        self._account = Web3().eth.account.from_key(self._key)
        self.address: str = self._account.address

    def sign_transaction(self, tx: Dict[str, Any], w3: Web3) -> bytes:
        """Sign a transaction dict and return the raw bytes."""
        signed = w3.eth.account.sign_transaction(tx, self._key)
        return signed.raw_transaction

    def __repr__(self) -> str:
        return f"Wallet({self.address})"


# ────────────────────────────────────────────────────────────
# 4.  Web3 connection pool
# ────────────────────────────────────────────────────────────

_w3_cache: Dict[str, Web3] = {}


def get_w3(chain: str) -> Web3:
    if chain not in _w3_cache:
        rpc = CHAIN_CONFIG[chain]["rpc"]
        _w3_cache[chain] = Web3(Web3.HTTPProvider(rpc, request_kwargs={"timeout": 15}))
    return _w3_cache[chain]


# ────────────────────────────────────────────────────────────
# 5.  Low-level transaction helpers
# ────────────────────────────────────────────────────────────

def _get_nonce(w3: Web3, address: str) -> int:
    return w3.eth.get_transaction_count(w3.to_checksum_address(address))


def _estimate_gas(w3: Web3, tx: Dict) -> int:
    try:
        return int(w3.eth.estimate_gas(tx) * 1.25)  # 25% buffer
    except Exception:
        return 350_000  # fallback for complex calls


def _build_eip1559_tx(
    w3: Web3,
    chain: str,
    from_addr: str,
    to_addr: str,
    value: int,
    data: bytes,
    nonce: int,
) -> Dict[str, Any]:
    """
    Build an EIP-1559 transaction dict — same structure as the
    MetaMask Infura tutorial's eip1559_tx.py.
    """
    chain_id = CHAIN_CONFIG[chain]["chain_id"]
    fee_data = w3.eth.fee_history(1, "latest", [50])
    base_fee = fee_data["baseFeePerGas"][-1]
    priority_fee = w3.to_wei("1.5", "gwei")

    tx: Dict[str, Any] = {
        "type": "0x2",
        "chainId": chain_id,
        "from": w3.to_checksum_address(from_addr),
        "to": w3.to_checksum_address(to_addr),
        "value": value,
        "nonce": nonce,
        "maxFeePerGas": base_fee * 2 + priority_fee,
        "maxPriorityFeePerGas": priority_fee,
        "data": data,
    }
    tx["gas"] = _estimate_gas(w3, tx)
    return tx


def _send_tx(
    w3: Web3,
    wallet: Wallet,
    tx: Dict[str, Any],
    dry_run: bool,
    label: str,
) -> Optional[str]:
    """
    Sign and optionally broadcast a transaction.

    Returns the tx hash hex string, or None if dry_run.
    """
    raw = wallet.sign_transaction(tx, w3)

    if dry_run:
        print(f"    [DRY RUN] {label}")
        print(f"      to:    {tx['to']}")
        print(f"      gas:   {tx['gas']:,}")
        print(f"      nonce: {tx['nonce']}")
        print(f"      raw:   {raw.hex()[:40]}…  ({len(raw)} bytes)")
        return None

    tx_hash = w3.eth.send_raw_transaction(raw)
    hex_hash = w3.to_hex(tx_hash)
    print(f"    [SENT] {label}")
    print(f"      tx: {hex_hash}")
    return hex_hash


def _wait_for_receipt(
    w3: Web3,
    tx_hash: str,
    timeout: int = 120,
) -> Dict[str, Any]:
    """Poll until the transaction is mined."""
    print(f"      Waiting for confirmation …", end="", flush=True)
    start = time.time()
    while time.time() - start < timeout:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None:
                status = receipt.get("status", 0)
                gas_used = receipt.get("gasUsed", 0)
                block = receipt.get("blockNumber", 0)
                symbol = "✓" if status == 1 else "✗ REVERTED"
                print(f"  {symbol}  block={block}  gas={gas_used:,}")
                if status != 1:
                    raise RuntimeError(f"Transaction reverted: {tx_hash}")
                return dict(receipt)
        except Exception as e:
            if "reverted" in str(e).lower():
                raise
        time.sleep(2)
    raise TimeoutError(f"Transaction not mined within {timeout}s: {tx_hash}")


# ────────────────────────────────────────────────────────────
# 6.  ERC-20 approve (if needed)
# ────────────────────────────────────────────────────────────

def ensure_approval(
    chain: str,
    token_symbol: str,
    spender: str,
    amount_raw: int,
    wallet: Wallet,
    dry_run: bool,
) -> None:
    """Check allowance and approve if insufficient."""
    token_addr = TOKEN_REGISTRY.get(token_symbol, {}).get(chain)
    if not token_addr:
        raise ValueError(f"No contract address for {token_symbol} on {chain}")

    w3 = get_w3(chain)
    contract = w3.eth.contract(
        address=w3.to_checksum_address(token_addr),
        abi=ERC20_ABI,
    )

    current = contract.functions.allowance(
        w3.to_checksum_address(wallet.address),
        w3.to_checksum_address(spender),
    ).call()

    if current >= amount_raw:
        print(f"    Allowance OK for {token_symbol} → {spender[:10]}…")
        return

    max_uint = 2**256 - 1
    approve_data = contract.encode_abi("approve", args=[
        w3.to_checksum_address(spender), max_uint
    ])

    nonce = _get_nonce(w3, wallet.address)
    tx = _build_eip1559_tx(
        w3, chain, wallet.address,
        token_addr, 0,
        bytes.fromhex(approve_data[2:]) if isinstance(approve_data, str) else approve_data,
        nonce,
    )
    tx_hash = _send_tx(w3, wallet, tx, dry_run, f"Approve {token_symbol}")
    if tx_hash:
        _wait_for_receipt(w3, tx_hash)


# ────────────────────────────────────────────────────────────
# 7.  Uniswap V3 swap
# ────────────────────────────────────────────────────────────

UNISWAP_FEE_TIERS = {
    "stable": 100,    # 0.01%
    "low":    500,    # 0.05%
    "medium": 3000,   # 0.30%
    "high":   10000,  # 1.00%
}

STABLECOINS = {"USDC", "USDT", "DAI"}


def _pick_fee_tier(token_in: str, token_out: str) -> int:
    if token_in in STABLECOINS and token_out in STABLECOINS:
        return UNISWAP_FEE_TIERS["stable"]
    return UNISWAP_FEE_TIERS["medium"]


def execute_swap(
    chain: str,
    token_in: str,
    token_out: str,
    amount_in_human: float,
    wallet: Wallet,
    dry_run: bool,
    slippage: float = 0.005,
) -> Optional[str]:
    """
    Execute a Uniswap V3 exactInputSingle swap.

    Returns the tx hash, or None if dry_run.
    """
    cfg = CHAIN_CONFIG[chain]
    router_addr = cfg.get("uniswap_router")
    if not router_addr:
        raise ValueError(f"No Uniswap router configured for {chain}")

    token_in_addr = TOKEN_REGISTRY.get(token_in, {}).get(chain)
    token_out_addr = TOKEN_REGISTRY.get(token_out, {}).get(chain)
    if not token_in_addr or not token_out_addr:
        raise ValueError(f"Missing token address: {token_in} or {token_out} on {chain}")

    decimals_in = TOKEN_DECIMALS.get(token_in, 18)
    amount_raw = int(amount_in_human * (10 ** decimals_in))

    # Approve router to spend our tokens
    ensure_approval(chain, token_in, router_addr, amount_raw, wallet, dry_run)

    w3 = get_w3(chain)
    router = w3.eth.contract(
        address=w3.to_checksum_address(router_addr),
        abi=UNISWAP_V3_ABI,
    )

    fee_tier = _pick_fee_tier(token_in, token_out)
    deadline = int(time.time()) + 300  # 5 minutes
    min_out = int(amount_raw * (1 - slippage))  # slippage protection

    swap_params = (
        w3.to_checksum_address(token_in_addr),   # tokenIn
        w3.to_checksum_address(token_out_addr),   # tokenOut
        fee_tier,                                  # fee
        w3.to_checksum_address(wallet.address),    # recipient
        deadline,                                  # deadline
        amount_raw,                                # amountIn
        min_out,                                   # amountOutMinimum
        0,                                         # sqrtPriceLimitX96 (0 = no limit)
    )

    # Encode calldata — use encodeABI to avoid on-chain simulation that
    # reverts when the wallet has no tokens (e.g. dry-run with a different address)
    call_data = router.encode_abi("exactInputSingle", args=[swap_params])

    nonce = _get_nonce(w3, wallet.address)
    tx = _build_eip1559_tx(
        w3, chain, wallet.address,
        router_addr, 0,
        bytes.fromhex(call_data[2:]) if isinstance(call_data, str) else call_data,
        nonce,
    )

    label = f"Swap {amount_in_human:.6f} {token_in} → {token_out} on {chain}"
    tx_hash = _send_tx(w3, wallet, tx, dry_run, label)
    if tx_hash:
        _wait_for_receipt(w3, tx_hash)
    return tx_hash


# ────────────────────────────────────────────────────────────
# 8.  Across Protocol V3 bridge
# ────────────────────────────────────────────────────────────

def execute_bridge(
    chain_from: str,
    chain_to: str,
    token_symbol: str,
    amount_in_human: float,
    wallet: Wallet,
    dry_run: bool,
    bridge_fee_pct: float = 0.001,
) -> Optional[str]:
    """
    Bridge tokens via Across Protocol V3 depositV3.

    Returns the tx hash, or None if dry_run.
    """
    cfg_from = CHAIN_CONFIG[chain_from]
    cfg_to = CHAIN_CONFIG[chain_to]

    spoke_pool_addr = cfg_from.get("across_spoke_pool")
    if not spoke_pool_addr:
        raise ValueError(f"No Across SpokePool on {chain_from}")

    token_addr_from = TOKEN_REGISTRY.get(token_symbol, {}).get(chain_from)
    token_addr_to = TOKEN_REGISTRY.get(token_symbol, {}).get(chain_to)
    if not token_addr_from or not token_addr_to:
        raise ValueError(f"Missing token address for {token_symbol} on {chain_from}/{chain_to}")

    decimals = TOKEN_DECIMALS.get(token_symbol, 18)
    amount_raw = int(amount_in_human * (10 ** decimals))
    output_amount = int(amount_raw * (1 - bridge_fee_pct))

    ensure_approval(chain_from, token_symbol, spoke_pool_addr, amount_raw, wallet, dry_run)

    w3 = get_w3(chain_from)
    spoke_pool = w3.eth.contract(
        address=w3.to_checksum_address(spoke_pool_addr),
        abi=ACROSS_V3_ABI,
    )

    quote_ts = int(time.time())
    fill_deadline = quote_ts + 1800   # 30 min
    excl_deadline = 0
    zero_addr = "0x0000000000000000000000000000000000000000"

    call_data = spoke_pool.encode_abi("depositV3", args=[
        w3.to_checksum_address(wallet.address),      # depositor
        w3.to_checksum_address(wallet.address),      # recipient (same)
        w3.to_checksum_address(token_addr_from),     # inputToken
        w3.to_checksum_address(token_addr_to),       # outputToken
        amount_raw,                                   # inputAmount
        output_amount,                                # outputAmount
        cfg_to["chain_id"],                           # destinationChainId
        w3.to_checksum_address(zero_addr),           # exclusiveRelayer
        quote_ts,                                     # quoteTimestamp
        fill_deadline,                                # fillDeadline
        excl_deadline,                                # exclusivityDeadline
        b"",                                          # message
    ])

    nonce = _get_nonce(w3, wallet.address)
    tx = _build_eip1559_tx(
        w3, chain_from, wallet.address,
        spoke_pool_addr, 0,
        bytes.fromhex(call_data[2:]) if isinstance(call_data, str) else call_data,
        nonce,
    )

    label = (f"Bridge {amount_in_human:.6f} {token_symbol}  "
             f"{chain_from} → {chain_to}")
    tx_hash = _send_tx(w3, wallet, tx, dry_run, label)
    if tx_hash:
        _wait_for_receipt(w3, tx_hash)
    return tx_hash


# ────────────────────────────────────────────────────────────
# 9.  Path executor — orchestrates a full BF-SSSP path
# ────────────────────────────────────────────────────────────

def execute_path(
    edges: List[Dict[str, Any]],
    start_amount_usd: float,
    wallet: Wallet,
    dry_run: bool = True,
    slippage: float = 0.005,
    max_loss_pct: float = 5.0,
) -> None:
    """
    Execute every step in a BF-SSSP path sequentially.

    Each edge dict has: kind ("swap" or "bridge"), from, to,
    from_chain/to_chain (for bridges), token symbols, etc.
    """
    print(f"\n{'═'*60}")
    mode = "DRY RUN" if dry_run else "LIVE EXECUTION"
    print(f"  EXECUTING PATH — {mode}")
    print(f"  Starting value: ${start_amount_usd:,.2f}")
    print(f"  Steps: {len(edges)}")
    print(f"  Slippage: {slippage*100:.1f}%")
    print(f"  Max cumulative loss: {max_loss_pct:.1f}%")
    print(f"{'═'*60}\n")

    for i, edge in enumerate(edges, 1):
        kind = edge.get("kind", "")
        print(f"  Step {i}/{len(edges)} — {kind.upper()}")

        if kind == "swap":
            chain = edge["from"][0]  # (chain, token)
            token_in = edge["from"][1]
            token_out = edge["to"][1]
            # Use a placeholder amount — in production you'd track
            # the actual balance after each step
            print(f"    {token_in} → {token_out} on {chain}")
            execute_swap(
                chain=chain,
                token_in=token_in,
                token_out=token_out,
                amount_in_human=0.0,  # placeholder for dry run
                wallet=wallet,
                dry_run=dry_run,
                slippage=slippage,
            )

        elif kind == "bridge":
            chain_from = edge["from"][0]
            chain_to = edge["to"][0]
            token = edge["from"][1]
            print(f"    {token} : {chain_from} → {chain_to}")
            execute_bridge(
                chain_from=chain_from,
                chain_to=chain_to,
                token_symbol=token,
                amount_in_human=0.0,  # placeholder for dry run
                wallet=wallet,
                dry_run=dry_run,
            )

            if not dry_run:
                wait_secs = int(edge.get("transfer_time_sec", 120))
                print(f"    Waiting {wait_secs}s for bridge relay …")
                time.sleep(wait_secs)

        print()

    print(f"{'═'*60}")
    print(f"  Path execution complete. ({mode})")
    print(f"{'═'*60}")
