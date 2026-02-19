
"""
Rough end-to-end transfer times per network.

These are *ballpark* values:
- They include on-chain finality + typical exchange processing delay.
- They're meant for comparing routes, not guaranteeing latency.

Units: **seconds**
"""

from typing import Optional, List, Tuple


CHAIN_TRANSFER_TIME_SEC: dict[str, float] = {
    # Fast L1s
    "SOL":      1.0,    # Solana (~0.4s finality)
    "XLM":      4.0,    # Stellar
    "APT":      2.0,    # Aptos (~1-2s finality)
    "SUI":      2.0,    # Sui (~2s finality)
    "TON":      5.0,    # TON (~5s finality)
    "NEAR":     2.0,    # Near Protocol (~1-2s finality)
    "AVAX":     2.0,    # Avalanche (~2s finality)

    # EVM sidechains / L1s
    "BNB":      4.0,    # BNB Smart Chain (BEP-20)
    "BSC":      4.0,    # alias if we ever use it
    "TRX":      30.0,   # Tron (TRC-20)
    "POLYGON":  5.0,    # Polygon PoS
    "MATIC":    5.0,    # Polygon alias
    "XDC":      5.0,    # XDC Network

    # Ethereum L2s (Arbitrum / Base etc.)
    "ARB":      120.0,  # Arbitrum
    "BASE":     120.0,  # Base
    "OP":       120.0,  # Optimism
    "MANTLE":   120.0,  # Mantle
    "SONIC":    5.0,    # Sonic (fast L2)

    # Mainnet Ethereum
    "ETH":      600.0,  # ERC-20 on Ethereum

    # Other
    "KCC":      5.0,    # KuCoin Community Chain
    "ALGO":     4.0,    # Algorand
    "DOT":      6.0,    # Polkadot
    "XTZ":      30.0,   # Tezos
    "HBAR":     5.0,    # Hedera
    "SEI":      1.0,    # Sei (fast L1)
    "FLR":      3.0,    # Flare
    "INK":      5.0,    # Ink
    "NOBLE":    6.0,    # Noble (Cosmos)
    "PLASMA":   5.0,    # Plasma
    "UNI":      120.0,  # Unichain (L2)
    "MONAD":    2.0,    # Monad (fast EVM)
    "CODEX":    5.0,    # Codex
}

def get_chain_time_seconds(chain: str) -> Optional[float]:
    """
    Return the approximate transfer time for a given network
    (in seconds), or None if unknown.
    """
    return CHAIN_TRANSFER_TIME_SEC.get(chain.upper())


def get_chain_time_minutes(chain: str) -> Optional[float]:
    """
    Same as get_chain_time_seconds(), but in minutes.
    """
    sec = get_chain_time_seconds(chain)
    return None if sec is None else sec / 60.0

BENCHMARK_USER_EXECUTION_OVERHEAD_SEC: float = 45.0 


def get_user_execution_overhead_seconds() -> float:
    """Return the assumed user/UI execution overhead (45 seconds)."""
    return BENCHMARK_USER_EXECUTION_OVERHEAD_SEC

# This allows you to compute: blockchain time + user overhead.

def estimate_total_cycle_time_seconds(
    transfer_hops: List[Tuple[str, str]],
    include_user_overhead: bool = True,
) -> float:
    """
    Estimate total arbitrage cycle duration in seconds.

    Args:
        transfer_hops:
            A list of tuples (exchange_name, chain_name)
            representing each withdrawal hop.
        include_user_overhead:
            Whether to include the 45-second user delay.

    Returns:
        float — total seconds.
    """
    total = 0.0

    # Sum blockchain transfer times
    for _, chain in transfer_hops:
        t = get_chain_time_seconds(chain)
        if t is not None:
            total += t

    # Add user overhead (45s)
    if include_user_overhead:
        total += BENCHMARK_USER_EXECUTION_OVERHEAD_SEC

    return total
