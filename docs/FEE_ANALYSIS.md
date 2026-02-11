# Fee Structure Analysis for Real Wallet Arbitrage

## Current Fee Model

### 1. Trading Fees (Percentage-Based)
All exchanges charge **percentage-based trading fees**:

| Exchange | Taker Fee | Maker Fee |
|----------|-----------|-----------|
| Binance  | 0.10%     | 0.10%     |
| Kraken   | 0.40%     | 0.25%     |
| KuCoin   | 0.10%     | 0.10%     |
| Bybit    | 0.10%     | 0.10%     |

**Impact**: These scale linearly with trade size. For a $10,000 trade:
- Binance: $10 fee
- Kraken: $40 fee (highest)

### 2. Withdrawal Fees (Flat Fees)
Withdrawal fees are **flat fees in coin units**, not percentages:

| Exchange | Coin | Chain | Fee (flat) |
|----------|------|-------|------------|
| Binance  | USDT | ETH   | 0.75 USDT  |
| Binance  | USDT | TRX   | 0.8 USDT   |
| Binance  | USDT | SOL   | 0.25 USDT  |
| Kraken   | USDT | ETH   | 0.62 USDT  |
| Kraken   | USDT | TRX   | 4.0 USDT   |
| Bybit    | USDT | ETH   | 6.0 USDT   |

**Critical Issue**: Flat fees have **disproportionate impact on small portfolios**.

## Fee Impact by Portfolio Size

### Example: 2-hop arbitrage path
- Trade 1: Exchange A (taker fee)
- Transfer: Withdrawal fee (flat)
- Trade 2: Exchange B (taker fee)

### Scenario 1: $100 Portfolio
```
Starting: $100
Trade 1 (0.1%): $100 → $99.90
Withdrawal (0.8 USDT flat): $99.90 → $99.10 (0.8% loss!)
Trade 2 (0.1%): $99.10 → $99.00
Final: $99.00
Profit: -$1.00 (LOSS due to flat withdrawal fee)
```

### Scenario 2: $1,000 Portfolio
```
Starting: $1,000
Trade 1 (0.1%): $1,000 → $999.00
Withdrawal (0.8 USDT flat): $999.00 → $998.20 (0.08% loss)
Trade 2 (0.1%): $998.20 → $997.20
Final: $997.20
Profit: -$2.80 (Still a loss, but smaller percentage)
```

### Scenario 3: $10,000 Portfolio
```
Starting: $10,000
Trade 1 (0.1%): $10,000 → $9,990.00
Withdrawal (0.8 USDT flat): $9,990.00 → $9,989.20 (0.008% loss)
Trade 2 (0.1%): $9,989.20 → $9,979.20
Final: $9,979.20
Profit: -$20.80 (Loss, but flat fee is now only 0.008% of portfolio)
```

### Scenario 4: $100,000 Portfolio
```
Starting: $100,000
Trade 1 (0.1%): $100,000 → $99,900.00
Withdrawal (0.8 USDT flat): $99,900.00 → $99,899.20 (0.0008% loss)
Trade 2 (0.1%): $99,899.20 → $99,799.20
Final: $99,799.20
Profit: -$200.80 (Loss, but flat fee impact is minimal)
```

## Key Insights

### 1. Flat Fees Kill Small Portfolio Arbitrage
- **$100 portfolio**: 0.8 USDT withdrawal = **0.8% loss** (devastating)
- **$10,000 portfolio**: 0.8 USDT withdrawal = **0.008% loss** (manageable)
- **Break-even point**: Need ~$1,000+ to make flat fees < 0.1% impact

### 2. Percentage Fees Scale Linearly
- Trading fees are always the same percentage regardless of size
- $100 trade: $0.10 fee (0.1%)
- $100,000 trade: $100 fee (0.1%)

### 3. Current Model Uses Reference Notional
The code uses `REFERENCE_NOTIONAL_USD = 10_000.0` to calculate withdrawal fee impact:
```python
amount_start_units = REFERENCE_NOTIONAL_USD / price_usd
rate = 1.0 - (fee_units / amount_start_units)
```

This means:
- For $10,000: 0.8 USDT = 0.008% impact (accurate)
- For $100: 0.8 USDT = 0.8% impact (should be higher, but model uses $10k reference)

**Problem**: The model doesn't dynamically adjust withdrawal fee impact based on actual portfolio size!

## Additional Fees with Real Wallets

### 1. Network Gas Fees (Blockchain)
When withdrawing, you may pay:
- **Ethereum**: $5-50+ in gas fees (varies with network congestion)
- **Arbitrum**: $0.10-1.00 in gas fees
- **Polygon**: $0.01-0.10 in gas fees
- **Solana**: $0.00025 (very cheap)
- **Tron**: Free (or very cheap)

**Impact**: These are **additional flat fees** on top of exchange withdrawal fees!

### 2. Deposit Fees
Most exchanges don't charge deposit fees, but some networks charge:
- **Ethereum**: Gas fee to receive (paid by sender, but affects timing)
- Some exchanges: Small deposit fees for certain networks

### 3. CCXT Fee Structure
CCXT provides fee information via:
- `exchange.markets[symbol]['taker']` - Taker fee
- `exchange.markets[symbol]['maker']` - Maker fee
- `exchange.fetchTradingFees()` - Current trading fees
- `exchange.fetchDepositWithdrawFees()` - Withdrawal fees

**Note**: Our current model uses hardcoded fees, but CCXT can fetch live fees!

## Recommendations

### 1. Dynamic Fee Calculation
Update `_build_transfer_edges()` to use actual portfolio size:
```python
# Instead of REFERENCE_NOTIONAL_USD, use actual trade size
def _build_transfer_edges(prices, portfolio_size_usd):
    amount_start_units = portfolio_size_usd / price_from_usd
    rate = 1.0 - (fee_units / amount_start_units)
```

### 2. Include Network Gas Fees
Add network gas fees to withdrawal costs:
```python
network_gas_fees = {
    "ETH": 10.0,  # $10 average gas fee
    "ARB": 0.5,   # $0.50 average
    "SOL": 0.00025,
    "TRX": 0.0,
}
```

### 3. Fetch Live Fees from CCXT
Use CCXT to get real-time fees:
```python
exchange.fetchTradingFees()  # Get current trading fees
exchange.fetchDepositWithdrawFees()  # Get withdrawal fees
```

### 4. Portfolio Size Thresholds
Set minimum portfolio sizes for profitable arbitrage:
- **$100**: Only viable for very large spreads (>2%)
- **$1,000**: Viable for moderate spreads (>0.5%)
- **$10,000+**: Viable for small spreads (>0.1%)

## Current Code Limitations

1. **Fixed Reference Notional**: Uses $10,000 for all calculations, regardless of actual portfolio size
2. **No Network Gas Fees**: Only includes exchange withdrawal fees
3. **Hardcoded Fees**: Doesn't fetch live fees from CCXT
4. **No Deposit Fees**: Assumes deposits are free

## Impact on Profit Calculations

For a typical 3-hop arbitrage:
- **Trade fees**: 2-3 trades × 0.1-0.4% = 0.2-1.2% total
- **Withdrawal fees**: 1-2 transfers × 0.8-6 USDT = 0.008-0.6% (at $10k) or 0.8-6% (at $100)
- **Gas fees**: $0-50 per transfer (if on Ethereum)
- **Total cost**: 0.2-7.8% depending on portfolio size and chains used

**Conclusion**: Small portfolios (<$1,000) are likely unprofitable due to flat fees dominating the cost structure.

