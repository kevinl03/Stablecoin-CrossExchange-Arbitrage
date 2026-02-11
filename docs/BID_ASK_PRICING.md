# Bid-Ask Spread Pricing Implementation

## Problem

The original implementation used **mid prices** (average of bid and ask), which is optimistic and creates false arbitrage opportunities. In reality:

- When **buying**, you pay the **ASK price** (higher)
- When **selling**, you receive the **BID price** (lower)

Small profits (0.01-0.05%) shown in results were likely **not real** after accounting for bid-ask spread.

## Solution

Updated the code to use **conservative execution prices**:

### Trading Pair Rates (`_fetch_actual_trading_pair_rate`)

When trading **FROM coin_from TO coin_to**:
- We're **selling** coin_from → receive **BID price** (lower, conservative)
- We're **buying** coin_to → pay **ASK price** (higher, conservative)

**For direct pair "coin_from/coin_to":**
- `bid` = how many coin_to buyers offer for 1 coin_from
- We receive `bid` when selling coin_from
- **Rate = bid** (conservative)

**For inverted pair "coin_to/coin_from":**
- `ask` = how many coin_from sellers want for 1 coin_to
- We pay `ask` when buying coin_to
- **Rate = 1/ask** (conservative)

### Price Normalization (`fetch_price_snapshot`)

When normalizing coin prices to USD:
- Use **bid price** (what we'd receive if selling)
- This gives a conservative (lower bound) estimate of coin value
- Prevents overestimating coin values

## Impact

This change will:
1. **Filter out false arbitrage opportunities** (0.01-0.05% profits)
2. **Show more realistic profit estimates** that account for bid-ask spread
3. **Reduce the number of "profitable" paths** found (more conservative)
4. **Increase confidence** that remaining profitable paths are executable

## Example

**Before (mid price):**
- BUSD/TUSD: bid=0.9995, ask=1.0005, mid=1.0000
- Trade $100 BUSD → TUSD: $100 × 1.0000 × 0.999 (after fee) = $99.90
- **Shows profit** if TUSD > $0.9990

**After (conservative):**
- BUSD/TUSD: bid=0.9995, ask=1.0005
- Trade $100 BUSD → TUSD: $100 × 0.9995 × 0.999 (after fee) = $99.85
- **Requires larger spread** to be profitable

The conservative approach ensures profits are **realistic and executable**.

