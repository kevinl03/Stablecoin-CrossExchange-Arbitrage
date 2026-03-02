"""
Withdrawal fees for major cryptocurrencies across 12 exchanges.

Fee values are approximate as of early 2026 and will drift over time.
The graph builder can optionally attempt live fee fetches via CCXT and
fall back to these hardcoded values.

Structure:
    CRYPTO_WITHDRAWAL_FEES[exchange][coin][chain] = fee_in_coin_units

For most non-stablecoin cryptos the only supported withdrawal chain is
the coin's native chain (e.g. BTC on Bitcoin, SOL on Solana).  A few
tokens that also live as ERC-20s have additional chain options.
"""

from __future__ import annotations

from typing import Dict

# Re-export trading fees — identical across stablecoin and crypto trades
from scripts.fees import (
    TRADING_FEES_TAKER,
    TRADING_FEES_MAKER,
    NETWORK_GAS_FEES,
    MIN_PORTFOLIO_THRESHOLDS,
    DEFAULT_MIN_PORTFOLIO,
    get_taker_fee,
    get_maker_fee,
    get_network_gas_fee,
    get_min_portfolio_threshold,
    fetch_live_trading_fees,
    fetch_live_withdrawal_fees,
)

# ────────────────────────────────────────────────────────────
# Crypto withdrawal fees  (fee in coin's own units)
# ────────────────────────────────────────────────────────────

CRYPTO_WITHDRAWAL_FEES: Dict[str, Dict[str, Dict[str, float]]] = {

    # ═══════════════════ BINANCE ═══════════════════
    "binance": {
        "BTC":  {"BTC": 0.0002,  "LIGHTNING": 0.0},
        "ETH":  {"ETH": 0.0012,  "ARB": 0.0004,  "OP": 0.0004, "BASE": 0.0004},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.15},
        "BNB":  {"BNB": 0.001},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 5.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.3,  "ARB": 0.05},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.03},
        "UNI":  {"ETH": 0.5,  "ARB": 0.1},
        "AAVE": {"ETH": 0.1,  "ARB": 0.02},
        "USDT": {"TRX": 0.8, "SOL": 0.25, "ETH": 0.75, "BNB": 0.3},
        "USDC": {"ETH": 0.8, "TRX": 0.8, "SOL": 0.2, "BNB": 0.25},
    },

    # ═══════════════════ KRAKEN ═══════════════════
    "kraken": {
        "BTC":  {"BTC": 0.00002, "LIGHTNING": 0.0},
        "ETH":  {"ETH": 0.0001,  "ARB": 0.00015, "OP": 0.00015},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.02},
        "ADA":  {"ADA": 0.6},
        "DOGE": {"DOGE": 2.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.1},
        "DOT":  {"DOT": 0.05},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.02},
        "UNI":  {"ETH": 0.3},
        "AAVE": {"ETH": 0.05},
        "USDT": {"ETH": 0.62, "SOL": 0.84, "TRX": 4.0, "ARB": 2.0},
        "USDC": {"ETH": 0.63, "SOL": 0.84, "ARB": 2.0, "BASE": 0.5},
    },

    # ═══════════════════ KUCOIN ═══════════════════
    "kucoin": {
        "BTC":  {"BTC": 0.00009},
        "ETH":  {"ETH": 0.0015, "ARB": 0.0002, "OP": 0.0002},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.3},
        "BNB":  {"BNB": 0.002},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 5.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.3},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.02},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.03},
        "UNI":  {"ETH": 0.6},
        "AAVE": {"ETH": 0.08},
        "USDT": {"ETH": 5.5, "SOL": 1.5, "TRX": 1.5, "ARB": 1.0, "BNB": 1.0},
        "USDC": {"ETH": 5.5, "SOL": 1.0, "ARB": 1.0, "BASE": 0.5},
    },

    # ═══════════════════ BYBIT ═══════════════════
    "bybit": {
        "BTC":  {"BTC": 0.0002},
        "ETH":  {"ETH": 0.0015, "ARB": 0.0004},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.25},
        "ADA":  {"ADA": 2.0},
        "DOGE": {"DOGE": 5.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.3},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.03},
        "UNI":  {"ETH": 0.5},
        "AAVE": {"ETH": 0.08},
        "USDT": {"TRX": 3.5, "ETH": 6.0, "TON": 1.0},
        "USDC": {"SOL": 1.0, "ARB": 1.0, "ETH": 4.99, "BASE": 0.5},
    },

    # ═══════════════════ OKX ═══════════════════
    "okx": {
        "BTC":  {"BTC": 0.0001, "LIGHTNING": 0.0},
        "ETH":  {"ETH": 0.001, "ARB": 0.0002, "OP": 0.0002},
        "SOL":  {"SOL": 0.008},
        "XRP":  {"XRP": 0.1},
        "ADA":  {"ADA": 0.8},
        "DOGE": {"DOGE": 4.0},
        "AVAX": {"AVAX": 0.008},
        "LINK": {"ETH": 0.2, "ARB": 0.04},
        "DOT":  {"DOT": 0.08},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.02},
        "UNI":  {"ETH": 0.4, "ARB": 0.08},
        "AAVE": {"ETH": 0.06},
        "USDT": {"TRX": 0.0, "SOL": 0.1, "ARB": 0.4, "ETH": 1.0},
        "USDC": {"SOL": 0.1, "ARB": 0.4, "ETH": 1.0, "BASE": 0.4},
    },

    # ═══════════════════ GATE.IO ═══════════════════
    "gateio": {
        "BTC":  {"BTC": 0.0005},
        "ETH":  {"ETH": 0.003, "ARB": 0.0005},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.5},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 10.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.5},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.02},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.04},
        "UNI":  {"ETH": 0.8},
        "AAVE": {"ETH": 0.1},
        "USDT": {"TRX": 1.0, "SOL": 1.0, "ETH": 4.0, "ARB": 1.0},
        "USDC": {"SOL": 1.0, "ETH": 4.0, "ARB": 1.0, "BASE": 1.0},
    },

    # ═══════════════════ BITGET ═══════════════════
    "bitget": {
        "BTC":  {"BTC": 0.0002},
        "ETH":  {"ETH": 0.002, "ARB": 0.0003},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.25},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 5.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.3},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.03},
        "UNI":  {"ETH": 0.5},
        "AAVE": {"ETH": 0.08},
        "USDT": {"TRX": 1.0, "SOL": 0.5, "ETH": 3.5, "ARB": 0.5},
        "USDC": {"SOL": 0.5, "ETH": 3.5, "ARB": 0.5, "BASE": 0.5},
    },

    # ═══════════════════ MEXC ═══════════════════
    "mexc": {
        "BTC":  {"BTC": 0.0002},
        "ETH":  {"ETH": 0.002, "ARB": 0.0004},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.25},
        "BNB":  {"BNB": 0.002},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 5.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.4},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.04},
        "UNI":  {"ETH": 0.6},
        "AAVE": {"ETH": 0.1},
        "USDT": {"TRX": 1.0, "SOL": 1.0, "ETH": 5.0, "ARB": 1.0},
        "USDC": {"SOL": 1.0, "ETH": 5.0, "ARB": 1.0},
    },

    # ═══════════════════ HTX (HUOBI) ═══════════════════
    "htx": {
        "BTC":  {"BTC": 0.0004},
        "ETH":  {"ETH": 0.003, "ARB": 0.0005},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.3},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 10.0},
        "AVAX": {"AVAX": 0.02},
        "LINK": {"ETH": 0.4},
        "DOT":  {"DOT": 0.2},
        "NEAR": {"NEAR": 0.02},
        "APT":  {"APT": 0.02},
        "UNI":  {"ETH": 0.6},
        "AAVE": {"ETH": 0.1},
        "USDT": {"TRX": 1.0, "SOL": 0.5, "ETH": 3.0, "ARB": 1.0},
        "USDC": {"SOL": 0.5, "ETH": 3.0, "ARB": 1.0},
    },

    # ═══════════════════ COINBASE ═══════════════════
    "coinbase": {
        "BTC":  {"BTC": 0.0},
        "ETH":  {"ETH": 0.0},
        "SOL":  {"SOL": 0.0},
        "XRP":  {"XRP": 0.0},
        "ADA":  {"ADA": 0.0},
        "DOGE": {"DOGE": 0.0},
        "AVAX": {"AVAX": 0.0},
        "LINK": {"ETH": 0.0},
        "DOT":  {"DOT": 0.0},
        "NEAR": {"NEAR": 0.0},
        "APT":  {"APT": 0.0},
        "SUI":  {"SUI": 0.0},
        "UNI":  {"ETH": 0.0},
        "AAVE": {"ETH": 0.0},
        "USDC": {"SOL": 0.0, "BASE": 0.0, "ETH": 2.0, "ARB": 0.5},
    },

    # ═══════════════════ CRYPTO.COM ═══════════════════
    "cryptocom": {
        "BTC":  {"BTC": 0.0002},
        "ETH":  {"ETH": 0.002, "ARB": 0.0004},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.15},
        "ADA":  {"ADA": 1.0},
        "DOGE": {"DOGE": 5.0},
        "AVAX": {"AVAX": 0.01},
        "LINK": {"ETH": 0.3},
        "DOT":  {"DOT": 0.1},
        "NEAR": {"NEAR": 0.01},
        "APT":  {"APT": 0.01},
        "SUI":  {"SUI": 0.03},
        "UNI":  {"ETH": 0.5},
        "AAVE": {"ETH": 0.08},
        "USDT": {"TRX": 0.0, "SOL": 0.5, "ETH": 5.0, "ARB": 0.8},
        "USDC": {"SOL": 0.5, "ETH": 5.0, "ARB": 0.8},
    },

    # ═══════════════════ PHEMEX ═══════════════════
    "phemex": {
        "BTC":  {"BTC": 0.0003},
        "ETH":  {"ETH": 0.003},
        "SOL":  {"SOL": 0.01},
        "XRP":  {"XRP": 0.3},
        "ADA":  {"ADA": 1.5},
        "DOGE": {"DOGE": 10.0},
        "AVAX": {"AVAX": 0.02},
        "LINK": {"ETH": 0.5},
        "DOT":  {"DOT": 0.2},
        "UNI":  {"ETH": 0.8},
        "USDT": {"TRX": 1.0, "SOL": 1.0, "ETH": 4.0},
        "USDC": {"SOL": 1.0, "ETH": 4.0},
    },
}
