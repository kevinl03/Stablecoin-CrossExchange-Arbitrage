# Complete Fee Breakdown for Stablecoin Cross-Exchange Arbitrage

This document lists **all fees** that apply when exchanging stablecoins across different exchanges.

---

## 1. Trading Fees (Percentage-Based)

Trading fees are charged **per trade** and are **percentage-based** (scale with trade size).

### Taker Fees (Market Orders)
Used when you place an order that immediately matches with an existing order.

| Exchange | Taker Fee | Example: $10,000 Trade |
|----------|-----------|------------------------|
| **Binance** | 0.10% | $10.00 |
| **Kraken** | 0.40% | $40.00 |
| **KuCoin** | 0.10% | $10.00 |
| **Bybit** | 0.10% | $10.00 |

### Maker Fees (Limit Orders)
Used when you place an order that adds liquidity to the order book.

| Exchange | Maker Fee | Example: $10,000 Trade |
|----------|-----------|------------------------|
| **Binance** | 0.10% | $10.00 |
| **Kraken** | 0.25% | $25.00 |
| **KuCoin** | 0.10% | $10.00 |
| **Bybit** | 0.10% | $10.00 |

**Note**: Arbitrage typically uses **taker fees** since speed is critical.

---

## 2. Withdrawal Fees (Flat Fees)

Withdrawal fees are **flat fees in coin units** (not percentages). This means they have a **disproportionate impact on small portfolios**.

### Binance Withdrawal Fees

#### USDT
| Chain | Fee (USDT) |
|-------|------------|
| TRX (Tron) | 0.8 USDT |
| SOL (Solana) | 0.25 USDT |
| ETH (Ethereum) | 0.75 USDT |
| BNB (BEP20) | 0.3 USDT |

#### USDC
| Chain | Fee (USDC) |
|-------|------------|
| ETH (Ethereum) | 0.8 USDC |
| TRX (Tron) | 0.8 USDC |
| SOL (Solana) | 0.2 USDC |
| BNB (BEP20) | 0.25 USDC |

#### DAI
| Chain | Fee (DAI) |
|-------|-----------|
| ETH (Ethereum) | 0.8 DAI |
| BNB (BEP20) | 0.1 DAI |

### Kraken Withdrawal Fees

#### USDT
| Chain | Fee (USDT) |
|-------|------------|
| APT (Aptos) | 0.30 USDT |
| ARB (Arbitrum) | 2.0 USDT |
| AVAX (Avalanche) | 1.0 USDT |
| ETH (Ethereum) | 0.62 USDT |
| SOL (Solana) | 0.84 USDT |
| TRX (Tron) | 4.0 USDT |
| OP (Optimism) | 2.0 USDT |
| POLYGON | 1.0 USDT |
| TON | 2.0 USDT |

#### USDC
| Chain | Fee (USDC) |
|-------|------------|
| ARB (Arbitrum) | 2.0 USDC |
| AVAX (Avalanche) | 1.0 USDC |
| BASE | 0.5 USDC |
| ETH (Ethereum) | 0.63 USDC |
| SOL (Solana) | 0.84 USDC |
| OP (Optimism) | 2.0 USDC |
| POLYGON | 1.0 USDC |
| SUI | 2.0 USDC |

#### DAI
| Chain | Fee (DAI) |
|-------|-----------|
| ARB (Arbitrum) | 2.0 DAI |
| ETH (Ethereum) | 0.52 DAI |
| MATIC (Polygon) | 1.0 DAI |

### KuCoin Withdrawal Fees

#### USDT
| Chain | Fee (USDT) |
|-------|------------|
| TON | 0.0 USDT (Free) |
| PLASMA | 0.4 USDT |
| NEAR | 0.5 USDT |
| KCC (KuCoin Chain) | 0.5 USDT |
| APT (Aptos) | 0.5 USDT |
| POLYGON | 0.8 USDT |
| DOT (Polkadot) | 1.0 USDT |
| AVAX (Avalanche) | 1.0 USDT |
| ARB (Arbitrum) | 1.0 USDT |
| OP (Optimism) | 1.0 USDT |
| BNB (BEP20) | 1.0 USDT |
| SOL (Solana) | 1.5 USDT |
| TRX (Tron) | 1.5 USDT |
| ETH (Ethereum) | 5.5 USDT |

#### USDC
| Chain | Fee (USDC) |
|-------|------------|
| XDC | 0.0 USDC (Free) |
| MONAD | 0.1 USDC |
| SONIC | 0.21 USDC |
| KCC (KuCoin Chain) | 0.5 USDC |
| BASE | 0.5 USDC |
| SUI | 0.5 USDC |
| NEAR | 0.5 USDC |
| ARB (Arbitrum) | 1.0 USDC |
| ALGO (Algorand) | 1.0 USDC |
| SOL (Solana) | 1.0 USDC |
| DOT (Polkadot) | 1.0 USDC |
| AVAX (Avalanche) | 1.0 USDC |
| NOBLE | 1.0 USDC |
| OP (Optimism) | 1.0 USDC |
| ETH (Ethereum) | 5.5 USDC |
| HBAR (Hedera) | 34.95 USDC |

### Bybit Withdrawal Fees

#### USDT
| Chain | Fee (USDT) |
|-------|------------|
| TON | 1.0 USDT |
| TRX (Tron) | 3.5 USDT |
| ETH (Ethereum) | 6.0 USDT |

#### USDC
| Chain | Fee (USDC) |
|-------|------------|
| SUI | 0.0 USDC (Free) |
| MANTLE | 0.0 USDC (Free) |
| XDC | 0.0 USDC (Free) |
| SONIC | 0.05 USDC |
| APT (Aptos) | 0.05 USDC |
| BNB (BEP20) | 0.2 USDC |
| BASE | 0.5 USDC |
| SEI | 0.5 USDC |
| HBAR (Hedera) | 0.5 USDC |
| AVAX (Avalanche) | 1.0 USDC |
| SOL (Solana) | 1.0 USDC |
| ARB (Arbitrum) | 1.0 USDC |
| OP (Optimism) | 1.0 USDC |
| POLYGON | 1.0 USDC |
| ETH (Ethereum) | 4.99 USDC |

#### DAI
| Chain | Fee (DAI) |
|-------|-----------|
| BNB (BEP20) | 0.8 DAI |
| ETH (Ethereum) | 4.0 DAI |

---

## 3. Network Gas Fees (Flat Fees in USD)

Network gas fees are charged by the **blockchain network** (not the exchange) for processing transactions. These are **flat fees in USD** and vary by network congestion.

| Network | Average Gas Fee (USD) | Notes |
|---------|----------------------|-------|
| **Ethereum (ETH)** | $10.00 | High, varies with congestion |
| **Arbitrum (ARB)** | $0.50 | Layer 2, much cheaper |
| **Optimism (OP)** | $0.50 | Layer 2, much cheaper |
| **Polygon (POLYGON)** | $0.10 | Very cheap |
| **Base** | $0.10 | Very cheap |
| **Solana (SOL)** | $0.00025 | Extremely cheap |
| **Tron (TRX)** | $0.00 | Free |
| **BNB Smart Chain (BNB)** | $0.10 | Very cheap |
| **Avalanche (AVAX)** | $0.10 | Very cheap |
| **Aptos (APT)** | $0.10 | Very cheap |
| **Sui (SUI)** | $0.10 | Very cheap |
| **TON** | $0.00 | Free |
| **XDC** | $0.00 | Free |
| **KuCoin Chain (KCC)** | $0.10 | Very cheap |

**Note**: Gas fees on Ethereum can spike to $50+ during high congestion.

---

## 4. Deposit Fees

**Most exchanges do NOT charge deposit fees** for stablecoins. However, some exchanges may charge fees for:
- Fiat deposits (bank transfers, credit cards)
- Deposits on certain networks during maintenance
- Very small deposits below minimum thresholds

**For stablecoin arbitrage, deposit fees are typically $0.00.**

---

## 5. Total Fee Calculation Example

### Example: Cross-Exchange Arbitrage Path

**Path**: Binance USDT → Transfer to KuCoin (via SOL) → Trade USDT→TUSD on KuCoin

**Portfolio Size**: $10,000

#### Step 1: Trade on Binance (USDT → TUSD)
- Trading fee: $10,000 × 0.10% = **$10.00**
- Remaining: $9,990.00

#### Step 2: Withdraw from Binance (USDT on SOL)
- Withdrawal fee: **0.25 USDT** ≈ **$0.25**
- Network gas fee (SOL): **$0.00025**
- Total transfer cost: **$0.25**
- Remaining: $9,989.75

#### Step 3: Trade on KuCoin (USDT → TUSD)
- Trading fee: $9,989.75 × 0.10% = **$9.99**
- Remaining: $9,979.76

#### Total Fees:
- Trading fees: $10.00 + $9.99 = **$19.99**
- Withdrawal fee: **$0.25**
- Gas fee: **$0.00025**
- **Total: $20.24**

#### Net Profit Calculation:
If the arbitrage opportunity provides a 0.25% spread:
- Gross profit: $10,000 × 0.25% = $25.00
- Net profit: $25.00 - $20.24 = **$4.76** (0.0476%)

---

## 6. Fee Impact by Portfolio Size

### Key Insight: Flat Fees Disproportionately Impact Small Portfolios

| Portfolio Size | Trading Fees (0.2% total) | Withdrawal + Gas ($0.25) | Total Fees | Fee % |
|----------------|---------------------------|-------------------------|------------|-------|
| $100 | $0.20 | $0.25 | $0.45 | 0.45% |
| $1,000 | $2.00 | $0.25 | $2.25 | 0.225% |
| $10,000 | $20.00 | $0.25 | $20.25 | 0.2025% |
| $100,000 | $200.00 | $0.25 | $200.25 | 0.20025% |

**Observation**: As portfolio size increases, the flat withdrawal fee becomes a smaller percentage of total costs, making larger portfolios more profitable for arbitrage.

---

## 7. Minimum Portfolio Thresholds

Due to flat fees, certain chains require **minimum portfolio sizes** to be profitable:

| Chain | Minimum Portfolio | Reason |
|-------|------------------|--------|
| Ethereum (ETH) | $5,000 | High gas fees ($10+) |
| Arbitrum (ARB) | $1,000 | Moderate fees |
| Optimism (OP) | $1,000 | Moderate fees |
| Polygon | $500 | Low fees |
| Base | $500 | Low fees |
| Solana (SOL) | $100 | Very low fees |
| Tron (TRX) | $100 | Free gas |
| BNB Smart Chain | $500 | Low fees |
| Avalanche | $500 | Low fees |
| Aptos | $500 | Low fees |
| Sui | $500 | Low fees |
| TON | $100 | Free gas |
| XDC | $100 | Free gas |

---

## 8. Summary: All Fee Types

1. **Trading Fees** (Percentage-based)
   - Maker fees (limit orders)
   - Taker fees (market orders) ← Used in arbitrage

2. **Withdrawal Fees** (Flat, in coin units)
   - Charged by exchange
   - Varies by coin and blockchain network

3. **Network Gas Fees** (Flat, in USD)
   - Charged by blockchain network
   - Varies by network and congestion

4. **Deposit Fees** (Typically $0.00)
   - Usually free for stablecoins

**Total Cost = Trading Fees + Withdrawal Fees + Gas Fees**

---

## 9. Fee Optimization Strategies

1. **Choose cheaper networks**: Solana, Tron, Polygon instead of Ethereum
2. **Minimize transfers**: Prefer intra-exchange trades when possible
3. **Use larger portfolios**: Flat fees become less significant
4. **Monitor gas prices**: Avoid Ethereum during high congestion
5. **Consider Layer 2s**: Arbitrum, Optimism are much cheaper than Ethereum mainnet

---

## 10. Live Fee Fetching

The system can optionally fetch **live fees** from exchanges using CCXT:
- Trading fees may vary by VIP level or volume
- Withdrawal fees may change based on network conditions
- Gas fees fluctuate with network congestion

Use `use_live_fees=True` in `build_graph()` to enable real-time fee fetching.

