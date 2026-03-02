"""
Fee model for on-chain DeFi / DEX arbitrage.

Three cost categories:
  1. DEX swap fees   — percentage per swap (varies by pool/tier)
  2. Gas per swap    — flat USD cost per on-chain transaction
  3. Bridge fees     — percentage + flat cost to move tokens cross-chain

All values are conservative estimates; real costs fluctuate with
network congestion and bridge liquidity.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple

# ────────────────────────────────────────────────────────────
# 1. DEX swap fees (fraction of trade notional)
# ────────────────────────────────────────────────────────────

# Dominant DEX per chain and its standard fee tier.
# Uniswap V3 has multiple tiers (0.01%, 0.05%, 0.30%, 1.00%) —
# we use 0.30% as the default for volatile pairs and 0.05% for
# stablecoin pairs.  The graph builder selects the appropriate tier.

DEX_SWAP_FEE: Dict[str, float] = {
    "ethereum":  0.0030,  # Uniswap V3 — 0.30% standard tier
    "arbitrum":  0.0030,  # Uniswap V3 (Arbitrum) — 0.30%
    "base":      0.0030,  # Uniswap V3 / Aerodrome — 0.30%
    "optimism":  0.0030,  # Uniswap V3 / Velodrome — 0.30%
    "polygon":   0.0030,  # Uniswap V3 / QuickSwap — 0.30%
    "solana":    0.0025,  # Jupiter aggregator — ~0.25% effective
    "avax":      0.0030,  # Trader Joe / Pangolin — 0.30%
    "bsc":       0.0025,  # PancakeSwap V3 — 0.25%
}

# Lower fee tier for stablecoin-to-stablecoin swaps
STABLE_SWAP_FEE: Dict[str, float] = {
    "ethereum":  0.0001,  # Curve / Uniswap 0.01% pool
    "arbitrum":  0.0001,
    "base":      0.0005,
    "optimism":  0.0005,
    "polygon":   0.0001,
    "solana":    0.0005,
    "avax":      0.0004,  # Curve
    "bsc":       0.0004,
}

STABLECOINS = {"USDC", "USDT", "DAI"}


def get_dex_swap_fee(chain: str, token_from: str, token_to: str) -> float:
    """Return the DEX swap fee (fraction) for a given trade."""
    if token_from in STABLECOINS and token_to in STABLECOINS:
        return STABLE_SWAP_FEE.get(chain, 0.0005)
    return DEX_SWAP_FEE.get(chain, 0.0030)


# ────────────────────────────────────────────────────────────
# 2. Gas cost per on-chain swap (USD)
# ────────────────────────────────────────────────────────────

GAS_PER_SWAP_USD: Dict[str, float] = {
    "ethereum":  5.00,   # ~150k gas × ~30 gwei × $1850 ETH ≈ $5-10
    "arbitrum":  0.20,   # L2 — very cheap
    "base":      0.05,   # L2 — extremely cheap
    "optimism":  0.20,   # L2
    "polygon":   0.02,   # PoS chain — near-free
    "solana":    0.002,  # ~0.000005 SOL × $78
    "avax":      0.10,   # C-Chain
    "bsc":       0.10,   # BSC
}


def get_gas_per_swap(chain: str) -> float:
    """Return the estimated gas cost in USD for one swap on *chain*."""
    return GAS_PER_SWAP_USD.get(chain, 1.0)


# ────────────────────────────────────────────────────────────
# 3. Cross-chain bridge fees
# ────────────────────────────────────────────────────────────
# Modelled after fast bridges (Across Protocol, Stargate, Hop).
# Native rollup bridges are free but take 7+ days for L2→L1, so
# we only model fast bridges for practical arbitrage.

# (pct_fee, flat_fee_usd, time_seconds)
BridgeCost = Tuple[float, float, float]

# Default bridge cost: 0.06% + $0.50 flat + 120s
_DEFAULT_BRIDGE: BridgeCost = (0.0006, 0.50, 120.0)

# Chain-pair specific overrides (from_chain, to_chain) -> cost
# Symmetric: if (A,B) is defined, (B,A) uses the same cost.
BRIDGE_FEES: Dict[Tuple[str, str], BridgeCost] = {
    # ── Ethereum ↔ L2s (fast bridge: Across/Stargate) ──
    ("ethereum", "arbitrum"):  (0.0006, 5.0,  180.0),   # $5 gas on ETH side
    ("ethereum", "optimism"):  (0.0006, 5.0,  180.0),
    ("ethereum", "base"):      (0.0006, 5.0,  180.0),
    ("ethereum", "polygon"):   (0.0006, 5.0,  300.0),

    # ── L2 ↔ L2 (fast bridge, cheap gas both sides) ──
    ("arbitrum", "optimism"):  (0.0008, 0.30, 120.0),
    ("arbitrum", "base"):      (0.0008, 0.30, 120.0),
    ("arbitrum", "polygon"):   (0.0008, 0.30, 120.0),
    ("optimism", "base"):      (0.0008, 0.20, 90.0),
    ("optimism", "polygon"):   (0.0008, 0.30, 120.0),
    ("base", "polygon"):       (0.0008, 0.20, 120.0),

    # ── Solana ↔ EVM (Wormhole / deBridge) ──
    ("solana", "ethereum"):    (0.0010, 5.0,  300.0),
    ("solana", "arbitrum"):    (0.0010, 0.50, 180.0),
    ("solana", "base"):        (0.0010, 0.50, 180.0),

    # ── Avalanche ↔ EVM (Stargate) ──
    ("avax", "ethereum"):      (0.0006, 5.0,  180.0),
    ("avax", "arbitrum"):      (0.0008, 0.30, 120.0),

    # ── BSC ↔ EVM (Stargate) ──
    ("bsc", "ethereum"):       (0.0006, 5.0,  180.0),
    ("bsc", "arbitrum"):       (0.0008, 0.30, 120.0),
    ("bsc", "polygon"):        (0.0008, 0.20, 120.0),
}


def get_bridge_cost(chain_from: str, chain_to: str) -> BridgeCost:
    """
    Return (pct_fee, flat_fee_usd, time_sec) for bridging between
    two chains.  Symmetric lookup.
    """
    cost = BRIDGE_FEES.get((chain_from, chain_to))
    if cost is not None:
        return cost
    cost = BRIDGE_FEES.get((chain_to, chain_from))
    if cost is not None:
        return cost
    return _DEFAULT_BRIDGE


# Minimum portfolio (USD) for a bridge to be worthwhile
MIN_BRIDGE_PORTFOLIO: Dict[str, float] = {
    "ethereum":  2_000.0,   # High gas makes small portfolios unprofitable
    "arbitrum":  100.0,
    "base":      50.0,
    "optimism":  100.0,
    "polygon":   50.0,
    "solana":    50.0,
    "avax":      100.0,
    "bsc":       100.0,
}


def get_min_bridge_portfolio(chain: str) -> float:
    """Minimum portfolio size (USD) for bridging involving *chain*."""
    return MIN_BRIDGE_PORTFOLIO.get(chain, 500.0)
