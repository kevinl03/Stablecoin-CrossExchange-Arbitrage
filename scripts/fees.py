from typing import Dict

TRADING_FEES_TAKER = {
    # Binance Spot — Regular user, no BNB discount
    # Maker/Taker = 0.100% / 0.100%
    "binance": 0.0010,

    # Kraken Pro Spot — lowest tier
    # Maker/Taker = 0.25% / 0.40%
    # Arbitrage traditionally uses taker fees:
    "kraken":  0.0040,

    # KuCoin Spot — LV0
    # Maker/Taker = 0.100% / 0.100%
    "kucoin":  0.0010,

    # Bybit Spot — default retail user
    # Maker/Taker = 0.10% / 0.10%
    "bybit":   0.0010,

    # OKX Spot — Level 1 (default)
    # Maker/Taker = 0.08% / 0.10%
    "okx":     0.0010,

    # Gate.io Spot — VIP0
    # Maker/Taker = 0.20% / 0.20%
    "gateio":  0.0020,

    # Bitget Spot — Regular
    # Maker/Taker = 0.10% / 0.10%
    "bitget":  0.0010,

    # MEXC Spot — Regular
    # Maker/Taker = 0.00% / 0.05% (zero maker, low taker)
    "mexc":    0.0005,

    # HTX (Huobi) Spot — Regular
    # Maker/Taker = 0.20% / 0.20%
    "htx":     0.0020,

    # Coinbase Advanced — default tier
    # Maker/Taker = 0.40% / 0.60%
    "coinbase": 0.0060,

    # Crypto.com Exchange — Starter
    # Maker/Taker = 0.075% / 0.075%
    "cryptocom": 0.00075,

    # Phemex Spot — Regular
    # Maker/Taker = 0.10% / 0.10%
    "phemex":  0.0010,
}

TRADING_FEES_MAKER = {
    "binance":  0.0010,   # 0.10%
    "kraken":   0.0025,   # 0.25%
    "kucoin":   0.0010,   # 0.10%
    "bybit":    0.0010,   # 0.10%
    "okx":      0.0008,   # 0.08%
    "gateio":   0.0020,   # 0.20%
    "bitget":   0.0010,   # 0.10%
    "mexc":     0.0000,   # 0.00% (zero maker)
    "htx":      0.0020,   # 0.20%
    "coinbase": 0.0040,   # 0.40%
    "cryptocom":0.00075,  # 0.075%
    "phemex":   0.0010,   # 0.10%
}



WITHDRAWAL_FEES = {

    "binance": {
        # ---------- USDT ----------
        "USDT": {
            "TRX":  0.8,   # Tether USD (Tron)     — 0.8 USDT
            "SOL":  0.25,  # Tether USD (Solana)   — 0.25 USDT
            "ETH":  0.75,  # Tether USD (Ethereum) — 0.75 USDT
            "BNB":  0.3,   # Tether USD (BEP20)    — 0.3 USDT
        },

        # ---------- USDC ----------
        "USDC": {
            "ETH":  0.8,   # USDC (Ethereum)
            "TRX":  0.8,   # USDC (Tron)
            "SOL":  0.2,   # USDC (Solana)
            "BNB":  0.25,  # USDC (BEP20)
        },

        # ---------- DAI ----------
        "DAI": {
            "ETH":  0.8,   # DAI (Ethereum)
            "BNB":  0.1,   # DAI (BEP20)
        },

        # ---------- majors (optional, handy for routing) ----------
        "BTC": {
            "BTC": 0.0002,   # Bitcoin network
            "TRX": 0.00001,  # e.g. wrapped variant on Tron
        },
        "ETH": {
            "ETH": 0.0012,
            "ARB": 0.0004,   # Arbitrum One
        },
    },


    "kraken": {
        # ---------- USDT ----------
        "USDT": {
            "APT":  0.30,  # Tether USD (Aptos)      — 0.30 USDT
            "ARB":  2.0,   # Tether USD (Arbitrum)   — 2 USDT
            "AVAX": 1.0,   # Tether USD (Avalanche)  — 1 USDT
            "ETH":  0.62,  # Tether USD (Ethereum)   — 0.62 USDT
            "FLR":  2.0,   # Tether USD (Flare)      — 2 USDT
            "INK":  0.0,   # Tether USD (Ink)        — 0 USDT
            "OP":   2.0,   # Tether USD (Optimism)   — 2 USDT
            "PLASMA": 1.0, # Tether USD (Plasma)     — 1 USDT
            "POLYGON": 1.0,# Tether USD (Polygon)    — 1 USDT
            "SOL":  0.84,  # Tether USD (Solana)     — 0.84 USDT
            "TON":  2.0,   # Tether USD (TON)        — 2 USDT
            "TRX":  4.0,   # Tether USD (Tron)       — 4 USDT
            "UNI":  2.0,   # Tether USD (Unichain)   — 2 USDT
        },

        # ---------- USDC ----------
        "USDC": {
            "ARB":  2.0,   # USDC (Arbitrum One)
            "AVAX": 1.0,   # USDC (Avalanche)
            "BASE": 0.5,   # USDC (Base)
            "ETH":  0.63,  # USDC (Ethereum)
            "INK":  0.0,   # USDC (Ink)
            "NOBLE":1.0,   # USDC (Noble)
            "OP":   2.0,   # USDC (Optimism)
            "POLYGON":1.0, # USDC (Polygon)
            "SOL":  0.84,  # USDC (Solana)
            "SONIC":1.0,   # USDC (Sonic)
            "SUI":  2.0,   # USDC (Sui)
            "XDC":  0.0,   # USDC (XDC Network) — free, fee in XDC
        },

        # ---------- DAI ----------
        "DAI": {
            "ARB":  2.0,   # Dai (Arbitrum One)
            "ETH":  0.52,  # Dai (Ethereum)
            "MATIC":1.0,   # Dai (Polygon)
        },

        # ---------- majors ----------
        "BTC": {
            "BTC": 0.000015,  # Bitcoin
            "LIGHTNING": 0.0  # BTC Lightning
        },
        "ETH": {
            "ETH": 0.000100,
            "ARB": 0.00015,
            "OP":  0.00015,
        },
    },

    "kucoin": {
        # ---------- USDT ----------
        "USDT": {
            "TON":   0.0,   # USDT (TON)         — Free
            "PLASMA":0.4,   # USDT (Plasma)      — 0.4 USDT
            "NEAR":  0.5,   # USDT (Near)        — 0.5 USDT
            "KCC":   0.5,   # USDT (KuCoin Chain)— 0.5 USDT
            "APT":   0.5,   # USDT (Aptos)       — 0.5 USDT
            "POLYGON":0.8,  # USDT (Polygon POS) — 0.8 USDT
            "DOT":   1.0,   # USDT (Polkadot)    — 1 USDT
            "AVAX":  1.0,   # USDT (Avalanche)   — 1 USDT
            "ARB":   1.0,   # USDT (Arbitrum)    — 1 USDT
            "OP":    1.0,   # USDT (Optimism)    — 1 USDT
            "BNB":   1.0,   # USDT (BNB Smart)   — 1 USDT
            "XTZ":   1.0,   # USDT (Tezos)       — 1 USDT
            "SOL":   1.5,   # USDT (Solana)      — 1.5 USDT
            "TRX":   1.5,   # USDT (Tron)        — 1.5 USDT
            "ETH":   5.5,   # USDT (Ethereum)    — 5.5 USDT
        },

        # ---------- USDC ----------
        "USDC": {
            "XDC":   0.0,   # USDC (XDC)         — Free
            "MONAD": 0.1,   # USDC (Monad)       — 0.1 USDC
            "SONIC": 0.21,  # USDC (Sonic)       — 0.21 USDC
            "KCC":   0.5,   # USDC (KCC)         — 0.5 USDC
            "BASE":  0.5,   # USDC (Base)        — 0.5 USDC
            "SUI":   0.5,   # USDC (Sui)         — 0.5 USDC
            "NEAR":  0.5,   # USDC (Near)        — 0.5 USDC
            "ARB":   1.0,   # USDC (Arbitrum)    — 1 USDC
            "ALGO":  1.0,   # USDC (Algorand)    — 1 USDC
            "SOL":   1.0,   # USDC (Solana)      — 1 USDC
            "DOT":   1.0,   # USDC (Polkadot)    — 1 USDC
            "AVAX":  1.0,   # USDC (Avalanche)   — 1 USDC
            "NOBLE": 1.0,   # USDC (Noble)       — 1 USDC
            "OP":    1.0,   # USDC (Optimism)    — 1 USDC
            "ETH":   5.5,   # USDC (Ethereum)    — 5.5 USDC
            "HBAR":  34.95, # USDC (Hedera)      — 35 USDC
        },

        # ---------- USDT/USDC majors & routing coins ----------
        "BTC": {
            "BTC": 0.00009,
            "ARB": 0.0001,
            "BSC": 0.000004,
        },
        "ETH": {
            "ETH": 0.0015,
            "ARB": 0.0002,
            "OP":  0.0002,
        },
        "XRP": {
            "XRP": 0.3,
        },
    },

    "bybit": {
        # ---------- USDT ----------
        "USDT": {
            "TON": 1.0,   # USDT (TON network)
            "TRX": 3.5,   # USDT (TRC-20)
            "ETH": 6.0,   # USDT (ERC-20), midpoint 4–8
        },

        # ---------- USDC ----------
        "USDC": {
            "SUI":   0.0,   # USDC (Sui)           — Free
            "MANTLE":0.0,   # USDC (Mantle)        — Free
            "XDC":   0.0,   # USDC (XDC Network)   — Free
            "SONIC": 0.05,  # USDC (Sonic)         — 0.05 USDC
            "APT":   0.05,  # USDC (Aptos)         — 0.05 USDC
            "BNB":   0.2,   # USDC (BNB Smart)     — 0.2 USDC
            "BASE":  0.5,   # USDC (Base)          — 0.5 USDC
            "SEI":   0.5,   # USDC (Sei)           — 0.5 USDC
            "HBAR":  0.5,   # USDC (Hedera)        — 0.5 USDC
            "AVAX":  1.0,   # USDC (Avalanche)     — 1 USDC
            "SOL":   1.0,   # USDC (Solana)        — 1 USDC
            "ARB":   1.0,   # USDC (Arbitrum One)  — 1 USDC
            "CODEX": 1.0,   # USDC (Codex)         — 1 USDC
            "MONAD": 1.0,   # USDC (Monad)         — 1 USDC
            "OP":    1.0,   # USDC (Optimism)      — 1 USDC
            "POLYGON":1.0,  # USDC (Polygon POS)   — 1 USDC
            "ETH":   4.99,  # USDC (Ethereum)      — 4.99 USDC
        },

        # ---------- DAI ----------
        "DAI": {
            "BNB": 0.8,   # DAI (BNB Smart Chain) — 0.8 DAI
            "ETH": 4.0,   # DAI (Ethereum)        — 4 DAI
        },
    },

    # ===== NEW EXCHANGES =====

    "okx": {
        "USDT": {
            "TRX":  0.0,     # USDT (Tron)       — Free
            "SOL":  0.1,     # USDT (Solana)      — 0.1 USDT
            "POLYGON": 0.4,  # USDT (Polygon)     — 0.4 USDT
            "ARB":  0.4,     # USDT (Arbitrum)    — 0.4 USDT
            "OP":   0.4,     # USDT (Optimism)    — 0.4 USDT
            "AVAX": 0.8,     # USDT (Avalanche)   — 0.8 USDT
            "BNB":  0.8,     # USDT (BEP20)       — 0.8 USDT
            "ETH":  1.0,     # USDT (Ethereum)    — 1 USDT
        },
        "USDC": {
            "SOL":  0.1,     # USDC (Solana)      — 0.1 USDC
            "POLYGON": 0.4,  # USDC (Polygon)     — 0.4 USDC
            "ARB":  0.4,     # USDC (Arbitrum)    — 0.4 USDC
            "BASE": 0.4,     # USDC (Base)        — 0.4 USDC
            "OP":   0.4,     # USDC (Optimism)    — 0.4 USDC
            "AVAX": 0.8,     # USDC (Avalanche)   — 0.8 USDC
            "ETH":  1.0,     # USDC (Ethereum)    — 1 USDC
        },
        "DAI": {
            "ETH":  1.0,     # DAI (Ethereum)     — 1 DAI
            "ARB":  0.4,     # DAI (Arbitrum)     — 0.4 DAI
        },
    },

    "gateio": {
        "USDT": {
            "TRX":  1.0,     # USDT (Tron)        — 1 USDT
            "SOL":  1.0,     # USDT (Solana)       — 1 USDT
            "BNB":  0.5,     # USDT (BEP20)        — 0.5 USDT
            "POLYGON": 1.0,  # USDT (Polygon)      — 1 USDT
            "ARB":  1.0,     # USDT (Arbitrum)     — 1 USDT
            "OP":   1.0,     # USDT (Optimism)     — 1 USDT
            "ETH":  4.0,     # USDT (Ethereum)     — 4 USDT
        },
        "USDC": {
            "SOL":  1.0,     # USDC (Solana)       — 1 USDC
            "BNB":  0.5,     # USDC (BEP20)        — 0.5 USDC
            "ARB":  1.0,     # USDC (Arbitrum)     — 1 USDC
            "BASE": 1.0,     # USDC (Base)         — 1 USDC
            "ETH":  4.0,     # USDC (Ethereum)     — 4 USDC
        },
    },

    "bitget": {
        "USDT": {
            "TRX":  1.0,     # USDT (Tron)        — 1 USDT
            "SOL":  0.5,     # USDT (Solana)       — 0.5 USDT
            "BNB":  0.5,     # USDT (BEP20)        — 0.5 USDT
            "POLYGON": 0.5,  # USDT (Polygon)      — 0.5 USDT
            "ARB":  0.5,     # USDT (Arbitrum)     — 0.5 USDT
            "OP":   0.5,     # USDT (Optimism)     — 0.5 USDT
            "ETH":  3.5,     # USDT (Ethereum)     — 3.5 USDT
        },
        "USDC": {
            "SOL":  0.5,     # USDC (Solana)       — 0.5 USDC
            "BNB":  0.5,     # USDC (BEP20)        — 0.5 USDC
            "ARB":  0.5,     # USDC (Arbitrum)     — 0.5 USDC
            "BASE": 0.5,     # USDC (Base)         — 0.5 USDC
            "ETH":  3.5,     # USDC (Ethereum)     — 3.5 USDC
        },
    },

    "mexc": {
        "USDT": {
            "TRX":  1.0,     # USDT (Tron)        — 1 USDT
            "SOL":  1.0,     # USDT (Solana)       — 1 USDT
            "BNB":  1.5,     # USDT (BEP20)        — 1.5 USDT
            "POLYGON": 1.0,  # USDT (Polygon)      — 1 USDT
            "ARB":  1.0,     # USDT (Arbitrum)     — 1 USDT
            "ETH":  5.0,     # USDT (Ethereum)     — 5 USDT
        },
        "USDC": {
            "SOL":  1.0,     # USDC (Solana)       — 1 USDC
            "BNB":  1.5,     # USDC (BEP20)        — 1.5 USDC
            "ARB":  1.0,     # USDC (Arbitrum)     — 1 USDC
            "ETH":  5.0,     # USDC (Ethereum)     — 5 USDC
        },
    },

    "htx": {
        "USDT": {
            "TRX":  1.0,     # USDT (Tron)        — 1 USDT
            "SOL":  0.5,     # USDT (Solana)       — 0.5 USDT
            "BNB":  1.0,     # USDT (BEP20)        — 1 USDT
            "POLYGON": 0.5,  # USDT (Polygon)      — 0.5 USDT
            "ARB":  1.0,     # USDT (Arbitrum)     — 1 USDT
            "ETH":  3.0,     # USDT (Ethereum)     — 3 USDT
        },
        "USDC": {
            "SOL":  0.5,     # USDC (Solana)       — 0.5 USDC
            "ARB":  1.0,     # USDC (Arbitrum)     — 1 USDC
            "ETH":  3.0,     # USDC (Ethereum)     — 3 USDC
        },
    },

    "coinbase": {
        # Coinbase primarily supports USDC
        "USDC": {
            "SOL":  0.0,     # USDC (Solana)       — Free
            "BASE": 0.0,     # USDC (Base)         — Free (Coinbase's own L2)
            "POLYGON": 0.5,  # USDC (Polygon)      — 0.5 USDC
            "ARB":  0.5,     # USDC (Arbitrum)     — 0.5 USDC
            "ETH":  2.0,     # USDC (Ethereum)     — 2 USDC
        },
    },

    "cryptocom": {
        "USDT": {
            "TRX":  0.0,     # USDT (Tron)        — Free
            "SOL":  0.5,     # USDT (Solana)       — 0.5 USDT
            "BNB":  0.8,     # USDT (BEP20)        — 0.8 USDT
            "POLYGON": 0.8,  # USDT (Polygon)      — 0.8 USDT
            "ARB":  0.8,     # USDT (Arbitrum)     — 0.8 USDT
            "ETH":  5.0,     # USDT (Ethereum)     — 5 USDT
        },
        "USDC": {
            "SOL":  0.5,     # USDC (Solana)       — 0.5 USDC
            "POLYGON": 0.8,  # USDC (Polygon)      — 0.8 USDC
            "ARB":  0.8,     # USDC (Arbitrum)     — 0.8 USDC
            "ETH":  5.0,     # USDC (Ethereum)     — 5 USDC
        },
    },

    "phemex": {
        "USDT": {
            "TRX":  1.0,     # USDT (Tron)        — 1 USDT
            "SOL":  1.0,     # USDT (Solana)       — 1 USDT
            "BNB":  0.5,     # USDT (BEP20)        — 0.5 USDT
            "ETH":  4.0,     # USDT (Ethereum)     — 4 USDT
        },
        "USDC": {
            "SOL":  1.0,     # USDC (Solana)       — 1 USDC
            "ETH":  4.0,     # USDC (Ethereum)     — 4 USDC
        },
    },
}



# Network gas fees (in USD) - estimated average costs for transfers
# These are additional costs on top of exchange withdrawal fees
NETWORK_GAS_FEES = {
    "ETH": 10.0,      # Ethereum: $10 average (varies with congestion)
    "ARB": 0.5,       # Arbitrum: $0.50 average
    "OP": 0.5,        # Optimism: $0.50 average
    "POLYGON": 0.1,   # Polygon: $0.10 average
    "BASE": 0.1,      # Base: $0.10 average
    "SOL": 0.00025,   # Solana: $0.00025 (very cheap)
    "TRX": 0.0,       # Tron: Free
    "BNB": 0.1,       # BNB Smart Chain: $0.10
    "AVAX": 0.1,      # Avalanche: $0.10
    "APT": 0.1,       # Aptos: $0.10
    "SUI": 0.1,       # Sui: $0.10
    "TON": 0.0,       # TON: Free
    "XDC": 0.0,       # XDC: Free
    "KCC": 0.1,       # KuCoin Chain: $0.10
    "MATIC": 0.1,     # Polygon (alias): $0.10
    "NEAR": 0.01,     # Near: $0.01
    "ALGO": 0.001,    # Algorand: $0.001
    "DOT": 0.1,       # Polkadot: $0.10
    "XTZ": 0.1,       # Tezos: $0.10
    "HBAR": 0.001,    # Hedera: $0.001
    "SEI": 0.01,      # Sei: $0.01
    "FLR": 0.01,      # Flare: $0.01
    "INK": 0.1,       # Ink: $0.10
    "NOBLE": 0.01,    # Noble: $0.01
    "PLASMA": 0.1,    # Plasma: $0.10
    "SONIC": 0.01,    # Sonic: $0.01
    "UNI": 0.5,       # Unichain: $0.50
    "MANTLE": 0.1,    # Mantle: $0.10
    "MONAD": 0.01,    # Monad: $0.01
    "CODEX": 0.1,     # Codex: $0.10
}

# Minimum portfolio thresholds for profitable arbitrage (in USD)
# Below these thresholds, flat fees dominate and arbitrage is rarely profitable
MIN_PORTFOLIO_THRESHOLDS = {
    "ETH": 5_000.0,   # Ethereum needs larger portfolio due to high gas fees
    "ARB": 1_000.0,   # Arbitrum: $1,000 minimum
    "OP": 1_000.0,    # Optimism: $1,000 minimum
    "POLYGON": 500.0, # Polygon: $500 minimum
    "BASE": 500.0,    # Base: $500 minimum
    "SOL": 100.0,     # Solana: $100 minimum (very cheap)
    "TRX": 100.0,     # Tron: $100 minimum (free)
    "BNB": 500.0,     # BNB Smart Chain: $500 minimum
    "AVAX": 500.0,    # Avalanche: $500 minimum
    "APT": 500.0,     # Aptos: $500 minimum
    "SUI": 500.0,     # Sui: $500 minimum
    "TON": 100.0,     # TON: $100 minimum
    "XDC": 100.0,     # XDC: $100 minimum
    "KCC": 500.0,     # KuCoin Chain: $500 minimum
    "MATIC": 500.0,   # Polygon: $500 minimum
    "NEAR": 100.0,    # Near: $100 minimum
    "ALGO": 100.0,    # Algorand: $100 minimum
    "DOT": 500.0,     # Polkadot: $500 minimum
    "XTZ": 500.0,     # Tezos: $500 minimum
    "HBAR": 100.0,    # Hedera: $100 minimum
    "SEI": 100.0,     # Sei: $100 minimum
    "FLR": 100.0,     # Flare: $100 minimum
    "INK": 500.0,     # Ink: $500 minimum
    "NOBLE": 100.0,   # Noble: $100 minimum
    "PLASMA": 500.0,  # Plasma: $500 minimum
    "SONIC": 100.0,   # Sonic: $100 minimum
    "UNI": 1_000.0,   # Unichain: $1,000 minimum
    "MANTLE": 500.0,  # Mantle: $500 minimum
    "MONAD": 100.0,   # Monad: $100 minimum
    "CODEX": 500.0,   # Codex: $500 minimum
}

# Default minimum if chain not found
DEFAULT_MIN_PORTFOLIO = 1_000.0


def get_taker_fee(exchange: str) -> float | None:
    """Return the taker fee (decimal)."""
    return TRADING_FEES_TAKER.get(exchange)

def get_maker_fee(exchange: str) -> float | None:
    """Return the maker fee (decimal)."""
    return TRADING_FEES_MAKER.get(exchange)

def get_network_gas_fee(chain: str) -> float:
    """Return the network gas fee in USD for a given chain."""
    return NETWORK_GAS_FEES.get(chain.upper(), 0.0)

def get_min_portfolio_threshold(chain: str) -> float:
    """Return the minimum portfolio size (USD) recommended for profitable arbitrage on a chain."""
    return MIN_PORTFOLIO_THRESHOLDS.get(chain.upper(), DEFAULT_MIN_PORTFOLIO)

def fetch_live_trading_fees(exchange_name: str, exchange_obj) -> Dict[str, float] | None:
    """
    Fetch live trading fees from CCXT exchange object.
    
    Args:
        exchange_name: Name of the exchange
        exchange_obj: CCXT exchange instance
    
    Returns:
        Dict with 'taker' and 'maker' fees (as decimals), or None if unavailable
    """
    try:
        # Try to fetch trading fees
        if hasattr(exchange_obj, 'fetchTradingFees'):
            fees = exchange_obj.fetchTradingFees()
            if fees and isinstance(fees, dict):
                # Some exchanges return fees per symbol, others return general fees
                if 'taker' in fees and 'maker' in fees:
                    return {
                        'taker': float(fees['taker']),
                        'maker': float(fees['maker']),
                    }
                # If it's per-symbol, try to get a representative fee
                elif isinstance(fees, dict) and len(fees) > 0:
                    # Get first symbol's fees as representative
                    first_symbol = list(fees.keys())[0]
                    if isinstance(fees[first_symbol], dict):
                        symbol_fees = fees[first_symbol]
                        if 'taker' in symbol_fees and 'maker' in symbol_fees:
                            return {
                                'taker': float(symbol_fees['taker']),
                                'maker': float(symbol_fees['maker']),
                            }
        
        # Fallback: try markets structure
        if hasattr(exchange_obj, 'markets') and exchange_obj.markets:
            # Look for a common stablecoin pair to get fees
            for symbol, market in exchange_obj.markets.items():
                if 'USDT' in symbol or 'USDC' in symbol:
                    if 'taker' in market and 'maker' in market:
                        return {
                            'taker': float(market['taker']),
                            'maker': float(market['maker']),
                        }
    except Exception:
        # If fetching fails, return None (will use hardcoded fallback)
        pass
    
    return None

def fetch_live_withdrawal_fees(exchange_name: str, exchange_obj, coin: str) -> Dict[str, float] | None:
    """
    Fetch live withdrawal fees from CCXT exchange object.
    
    Args:
        exchange_name: Name of the exchange
        exchange_obj: CCXT exchange instance
        coin: Coin symbol (e.g., 'USDT', 'USDC')
    
    Returns:
        Dict mapping chain names to withdrawal fees (in coin units), or None if unavailable
    """
    try:
        if hasattr(exchange_obj, 'fetchDepositWithdrawFees'):
            fees = exchange_obj.fetchDepositWithdrawFees([coin])
            if fees and coin in fees:
                coin_fees = fees[coin]
                if 'withdraw' in coin_fees and 'networks' in coin_fees['withdraw']:
                    networks = coin_fees['withdraw']['networks']
                    result = {}
                    for network_name, network_info in networks.items():
                        if 'fee' in network_info:
                            result[network_name.upper()] = float(network_info['fee'])
                    if result:
                        return result
    except Exception:
        # If fetching fails, return None (will use hardcoded fallback)
        pass
    
    return None
