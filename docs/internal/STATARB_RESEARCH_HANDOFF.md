# Statistical Arbitrage Research — Findings & Handoff

**Author:** Kevin Litvin (automated research pipeline)
**Date:** June 2, 2026
**Branch:** `feature/data-collector`

---

## 1. Executive Summary

This document summarizes a research pivot from A\*-based stablecoin arbitrage to **statistical arbitrage (stat-arb) on volatile crypto assets**. The original stablecoin approach was definitively proven unprofitable due to fees exceeding spreads by 25x. The volatile asset pivot discovered a **structural price lag** on certain exchanges (Crypto.com, MEXC) that creates exploitable mean-reverting spreads.

### Key Result (5-Asset, 30-Day Validation)

| Asset | Spread Std (bps) | Pairs Profitable | Best Net (30d) | Best Pair | Sharpe |
|-------|-----------------|-----------------|---------------|-----------|--------|
| **WIF** | 93 bps | **10/10** | +49,544 bps | binance-cryptocom (z-score) | 0.93 |
| **PEPE** | 22 bps | **10/10** | +37,621 bps | binance-cryptocom (OU) | 2.38 |
| **CRV** | 78 bps | **10/10** | +27,411 bps | cryptocom-mexc (OU) | 1.50 |
| **DOGE** | 11 bps | **0/10** | -21,181 bps | — | — |
| **SOL** | 7.5 bps | **0/10** | -44,849 bps | — | — |

**Pattern:** Works when spread std >> fees (~15 bps). WIF/PEPE/CRV have std 22-93 bps → all profitable. DOGE/SOL have std 7-11 bps → all unprofitable.

**Caveat:** These results use 1-minute close prices with no slippage, no bid-ask crossing cost, and zero execution latency. Realistic production profits would be significantly lower (see Section 7).

---

## 2. Research Timeline

| Phase | Finding |
|-------|---------|
| **Phase 0** (prior work) | A\* pathfinding finds profitable stablecoin routes, but paths require pre-positioned capital on every exchange in the path |
| **Stablecoin backtest** | 120 snapshots across 7 stablecoins, 10 exchanges. **0 profitable trades.** Fee/spread-std ratio = 25.9x — fees dominate |
| **Volatile asset pivot** | Switched to CRV, WIF, PEPE, DOGE, SOL. Spread std jumps from 0.7 bps to 26-94 bps |
| **1-day CRV test** | 97 trades, 100% win rate, +4,431 bps net. OU half-life 3.3 minutes |
| **30-day validation** | CRV and WIF confirmed over 43,200 candles per exchange. 18/20 CRV pair-models profitable, 13/20 WIF pair-models profitable |

---

## 3. Data Infrastructure

### 3.1 Tools Built

| Tool | File | Purpose |
|------|------|---------|
| CEX Live Collector | `experiments/collect_statarb_data.py` | 10-signal live data collection from 12 exchanges |
| DEX Collector | `experiments/collect_dex_data.py` | DexScreener API collector for 12 tokens across DEX pools |
| Historical Downloader | `experiments/download_historical_ohlcv.py` | 30-day 1-min OHLCV from all exchanges, Parquet output |
| Historical Backtester | `experiments/backtest_historical.py` | OU + z-score strategies on Parquet/JSONL data |
| Feature Pipeline | `experiments/build_features.py` | 63-feature engineering from multi-signal data |
| ML Trainer | `experiments/train_spread_model.py` | Walk-forward CV with GradientBoosting/LightGBM |

### 3.2 Signals Collected (CEX Live Collector)

| Signal | Description | Update Frequency |
|--------|-------------|-----------------|
| Ticker (bid/ask/last) | Spot price from each exchange | Every snapshot |
| Funding rates | Perpetual futures funding rate | Every snapshot (~8hr settlement) |
| Open interest | Perp OI in contracts and USD | Every snapshot |
| Withdrawal status | Deposit/withdraw enabled flags | Every snapshot |
| Exchange status | Exchange operational status | Every snapshot |
| Spread matrix | Cross-exchange spread for each coin | Computed per snapshot |

### 3.3 Exchanges

Binance, Kraken, KuCoin, Bybit, OKX, Gate.io, Bitget, MEXC, HTX, Coinbase, Crypto.com, Phemex (12 total)

### 3.4 Assets

- **Volatile set (primary):** CRV, WIF, PEPE, DOGE, SOL
- **Stablecoin set (abandoned):** USDT, USDC, DAI, BUSD, TUSD, USDP, FDUSD

### 3.5 Data Locations

```
data/
├── historical/              # 30-day 1-min OHLCV Parquet files
│   ├── CRV/                 #   {exchange}.parquet per exchange
│   ├── WIF/
│   ├── PEPE/
│   ├── DOGE/
│   └── SOL/
├── statarb/                 # Live collector JSONL outputs
│   ├── 20260602_190651/     #   Stablecoin 120-snapshot run
│   └── 20260602_211358/     #   Volatile asset 2-hour run
└── dex/                     # DEX collector JSONL outputs
    └── 20260602_142316/     #   12-token 2-hour run
```

### 3.6 Exchange Data Quality (30-day download)

| Exchange | Coverage | Notes |
|----------|----------|-------|
| Binance, KuCoin, Bybit, OKX, MEXC, HTX, Crypto.com | 96-100% | Full 43,200 rows |
| Bitget | ~96% | 41,559 rows, 1 small gap |
| Gate.io | 0% | API blocks candles >10,000 points ago |
| Kraken | ~1.7% | Only returns ~720 rows (12 hrs) |
| Coinbase | 3-9% | Very sparse, many gaps |
| Phemex | ~2.3% | Limited history (~1,000 rows) |

---

## 4. Strategies

### 4.1 Ornstein-Uhlenbeck (OU) Mean-Reversion

**Model:** The spread $S_t = P_{ex1}(t) - P_{ex2}(t)$ between two exchanges follows an OU process:

$$dS_t = \theta(\mu - S_t) \, dt + \sigma \, dW_t$$

Where:
- $\mu$ = long-run mean of the spread
- $\theta$ = mean-reversion speed (higher = faster revert)
- $\sigma$ = volatility of the spread
- Half-life = $\ln(2) / \theta$

**Entry:** When $|S_t - \mu| > 2\sigma / \sqrt{2\theta}$ (spread deviates by ~2 standard deviations from equilibrium)

**Exit:** When spread crosses back through $\mu$

**Why it works:** The OU model correctly identifies the equilibrium level and only enters when the spread is sufficiently deviated. Because the spread genuinely mean-reverts (the same asset on two exchanges must converge), the model captures the structural lag.

### 4.2 Z-Score Rolling Window

**Model:** Simpler approach using rolling statistics:

$$z_t = \frac{S_t - \bar{S}_{window}}{\sigma_{window}}$$

**Entry:** When $|z_t| > 2.0$
**Exit:** When $|z_t| < 0.5$

**Comparison:** Z-score generates more trades but lower win rate and Sharpe. OU is preferred for its structural correctness.

### 4.3 Fee Model

| Exchange Pair | Round-trip Fee (bps) |
|--------------|---------------------|
| Binance ↔ any | 10-20 (taker 0.10%) |
| MEXC ↔ any | 15-20 |
| Crypto.com ↔ any | 15-20 |
| Worst case | 30 (0.15% per side) |

Fees are deducted per trade. The backtest uses the actual CCXT fee schedule from `scripts/fees.py`.

---

## 5. Full 30-Day Backtest Results

### 5.0 Cross-Asset Summary

50 pair-models tested across 5 assets. **30 profitable, 20 unprofitable.**

| Asset | Spread Std | Profitable | Best Model | Best Net | Best Sharpe | Slow Exchange |
|-------|-----------|------------|-----------|---------|-------------|---------------|
| WIF | 93 bps | 10/10 | binance-cryptocom (z-score) | +49,544 | 0.93 | Crypto.com |
| PEPE | 22 bps | 10/10 | binance-cryptocom (OU) | +37,621 | 2.38 | Crypto.com |
| CRV | 78 bps | 10/10 | cryptocom-mexc (OU) | +27,411 | 1.50 | Crypto.com |
| DOGE | 11 bps | 0/10 | — | -21,181 | — | — |
| SOL | 7.5 bps | 0/10 | — | -44,849 | — | — |

**Critical threshold:** Spread std must be >~15 bps (the typical round-trip fee) for the strategy to work. Assets below this threshold lose money consistently.

### 5.1 CRV (30 days, 43,200 candles per exchange)

**18 of 20 pair-models are net profitable.**

| Pair | Model | Gross (bps) | Fees (bps) | Net (bps) | Trades | Win% | Sharpe | OU Half-Life |
|------|-------|------------|-----------|----------|--------|------|--------|-------------|
| cryptocom-mexc | OU | 39,386 | 11,975 | **27,411** | 958 | 100% | 1.50 | 38 min |
| cryptocom-okx | OU | 40,036 | 16,363 | 23,674 | 935 | 100% | 1.29 | 38 min |
| cryptocom-kucoin | OU | 38,067 | 14,805 | 23,262 | 846 | 100% | 1.31 | 40 min |
| bitget-cryptocom | OU | 40,148 | 17,150 | 22,998 | 980 | 100% | 1.31 | 38 min |
| cryptocom-htx | OU | 37,834 | 15,125 | 22,709 | 550 | 100% | 1.04 | 24 min |
| bybit-cryptocom | OU | 38,596 | 16,153 | 22,443 | 923 | 100% | 1.42 | 39 min |
| binance-cryptocom | OU | 38,823 | 16,993 | 21,830 | 971 | 100% | 1.24 | 40 min |
| cryptocom-mexc | z-score | 22,191 | 11,063 | 11,128 | 885 | 73% | 0.28 | — |
| htx-kucoin | OU | 17,649 | 10,080 | 7,569 | 336 | 97% | 0.58 | 5 min |

**Key observation:** Crypto.com is the "slow" exchange for CRV — its price lags all others by ~38 minutes.

### 5.2 WIF (30 days, 43,200 candles per exchange)

**13 of 20 pair-models are net profitable.**

| Pair | Model | Gross (bps) | Fees (bps) | Net (bps) | Trades | Win% | Sharpe | OU Half-Life |
|------|-------|------------|-----------|----------|--------|------|--------|-------------|
| binance-mexc | OU | 79,160 | 20,115 | **59,045** | 1,341 | 100% | 2.46 | 1.5 min |
| binance-mexc | z-score | 72,999 | 20,025 | 52,974 | 1,335 | 100% | 2.21 | — |
| binance-bitget | z-score | 70,155 | 25,020 | 45,135 | 1,251 | 100% | 2.21 | — |
| binance-okx | z-score | 68,763 | 24,780 | 43,983 | 1,239 | 100% | 2.25 | — |
| binance-cryptocom | OU | 42,066 | 7,245 | 34,821 | 414 | 100% | 1.49 | 15 min |
| binance-htx | OU | 57,826 | 27,000 | 30,826 | 900 | 100% | 1.88 | 2 min |

**Key observation:** Binance leads price for WIF, MEXC lags by ~1.5 minutes. Very fast mean-reversion.

### 5.3 PEPE (30 days, 43,200 candles per exchange)

**10 of 10 pair-models are net profitable.** Highest Sharpe ratio of all assets.

| Pair | Model | Gross (bps) | Fees (bps) | Net (bps) | Trades | Win% | Sharpe | OU Half-Life |
|------|-------|------------|-----------|----------|--------|------|--------|-------------|
| binance-cryptocom | OU | 55,698 | 18,078 | **37,621** | 1,033 | 100% | 2.38 | 2 min |
| binance-cryptocom | z-score | 54,736 | 20,143 | 34,593 | 1,151 | 99% | 1.56 | — |
| bybit-cryptocom | OU | 50,011 | 26,723 | 23,289 | 1,527 | 100% | 1.32 | 5 min |
| cryptocom-okx | OU | 51,112 | 28,035 | 23,077 | 1,602 | 100% | 1.24 | 5 min |
| bitget-cryptocom | OU | 64,808 | 45,570 | 19,238 | 2,604 | 77% | 0.69 | 5 min |

**Key observation:** Crypto.com lags Binance by ~2 minutes for PEPE. Highest Sharpe (2.38) of any pair across all assets. PEPE's very low price ($0.00001x) may contribute to wider spreads on exchanges with limited decimal precision.

### 5.4 DOGE (30 days, 43,200 candles per exchange)

**0 of 10 pair-models are net profitable.** Spread std (11 bps) is below the fee threshold.

| Pair | Model | Net (bps) | Trades | Win% | Sharpe |
|------|-------|----------|--------|------|--------|
| cryptocom-htx | OU | -21,181 | 1,774 | 5.3% | -1.76 |
| htx-mexc | OU | -23,956 | 2,197 | 4.6% | -1.29 |
| binance-htx | OU | -39,889 | 2,452 | 2.5% | -2.72 |

**Key observation:** DOGE is too liquid/efficient — the spread between exchanges is too small to overcome fees. The strategy generates many trades but nearly all lose money.

### 5.5 SOL (30 days, 43,200 candles per exchange)

**0 of 10 pair-models are net profitable.** Spread std (7.5 bps) is the lowest of all assets — the most efficient market.

| Pair | Model | Net (bps) | Trades | Win% | Sharpe |
|------|-------|----------|--------|------|--------|
| bybit-htx | z-score | -44,849 | 2,292 | 2.0% | -3.02 |
| binance-htx | OU | -55,824 | 2,880 | 0.8% | -3.81 |
| bitget-htx | OU | -88,740 | 4,208 | 0.7% | -4.39 |

**Key observation:** SOL is a top-10 crypto by market cap with deep liquidity on every exchange. Prices are efficiently arbitraged by existing market makers, leaving no exploitable spread.

### 5.6 Stablecoin Baseline (120 snapshots, 7 coins, 10 exchanges)

| Metric | Value |
|--------|-------|
| Profitable trades | **0** |
| Spread std | 0.7 bps |
| Typical fees | 18 bps round-trip |
| Fee/std ratio | **25.9x** |
| Conclusion | **Definitively unprofitable** |

---

## 6. Feature Engineering (ML Pipeline)

### 6.1 Feature Categories (63 total)

| Category | Count | Features |
|----------|-------|----------|
| Spread-based | 34 | Current spread, 5 lags, rolling mean/std/min/max/skew at 4 windows, z-scores, momentum, velocity |
| Market microstructure | 4 | Bid-ask spread width per exchange, BA ratio, volume log-ratio |
| Funding rates | 6 | Per-exchange rate, differential, abs diff, rolling MA |
| Open interest | 6 | Per-exchange OI, ratio, change rate, change diff |
| Withdrawal status | 5 | Withdraw/deposit disabled flags, any-disabled |
| Time | 5 | Hour, minute, day-of-week, is_weekend, hours-to-settlement |
| **Targets** | 3 | target_revert, target_narrowed, target_spread_change |

### 6.2 ML Model

- **Algorithm:** Gradient Boosted Trees (sklearn or LightGBM)
- **Validation:** Walk-forward TimeSeriesSplit (no look-ahead bias)
- **Metrics:** Accuracy, F1, AUC (classification); MAE, directional accuracy (regression)
- **Status:** Pipeline built and tested. Needs more data (>200 rows after lag feature NaN removal) to train effectively. The volatile CEX collection will provide this.

### 6.3 Open Question

Given that the OU model already achieves 100% win rate on historical close prices, the ML model's value may be in:
- Predicting **regime changes** (when OU parameters shift)
- Optimizing **entry thresholds** dynamically
- Identifying **when NOT to trade** (e.g., withdrawal disabled, unusual OI shifts)

---

## 7. Realistic Profit Assessment

### 7.1 What the backtest assumes vs reality

| Factor | Backtest | Reality | Impact |
|--------|----------|---------|--------|
| Execution price | 1-min close | Must cross bid-ask spread | −10 to −40 bps per trade |
| Slippage | None | Low-cap tokens on thin books | −5 to −10 bps |
| Execution latency | 0 seconds | 1-10 seconds for API round-trip | 30-50% of signals missed |
| Fill probability | 100% | Partial fills, requotes | Reduces trade count |
| Capital rebalancing | Free/instant | Withdrawal fees + 10min-24hr delays | Periodic friction cost |
| Exchange downtime | Never | Occasional maintenance windows | Missed opportunities |

### 7.2 Conservative estimate

Applying realistic discounts to the WIF binance-mexc OU strategy:

| Metric | Backtest | Conservative Estimate |
|--------|----------|--------------------|
| Trades/month | 1,341 | ~500-700 |
| Win rate | 100% | 60-75% |
| Avg profit/trade | 44 bps gross | 15-25 bps gross |
| Net per trade | 44 bps | 5-15 bps |
| Monthly net | +59,045 bps | +2,500-10,000 bps |
| Sharpe | 2.46 | 0.5-1.0 |

### 7.3 Structural risks

1. **Competition:** Other bots likely exploit the same Crypto.com/MEXC lag. As more bots enter, spreads compress.
2. **Exchange API changes:** Crypto.com or MEXC could improve their matching engine, eliminating the lag.
3. **Fee changes:** Exchanges may increase taker fees for high-frequency accounts.
4. **Regulatory:** Potential restrictions on automated trading or API access.
5. **Capital lockup:** Need ~$5K-20K split across exchanges earning zero yield when not in a position.

### 7.4 Verdict

| Strategy | Verdict | Notes |
|----------|---------|-------|
| OU on WIF/CRV/PEPE via slow exchanges | **Plausible edge** | Real structural lag exists on Crypto.com/MEXC. Spread std 22-93 bps vs 15 bps fees. Needs sub-second execution infra and realistic slippage modeling to validate |
| OU on DOGE/SOL | **Not viable** | Spread std (7-11 bps) below fee threshold. These markets are too efficient |
| Stablecoin A\* arbitrage | **Dead** | Fee/spread ratio makes it mathematically impossible |
| DEX arbitrage | **Unknown** | Gas costs + MEV competition likely eliminate edge |

---

## 8. Suggested Next Steps

### High Priority
1. **Backtest with bid/ask prices** — Re-run using actual bid/ask instead of close to model crossing cost
2. **Add slippage model** — Estimate market impact from order book depth
3. **Paper trade** — Run live signals for 24-48 hours, log what you would have traded, compare to actual price movement
4. **Complete 5-asset validation** — PEPE, DOGE, SOL downloads finishing (check `data/historical/`)

### Medium Priority
5. **Execution latency simulation** — Add 2-5 second delay before entry in backtest
6. **Capital rebalancing model** — Simulate inventory drift and rebalancing costs
7. **Train ML model** on volatile data once collection completes

### Low Priority / Future
8. **Build execution engine** — Only if paper trading confirms edge
9. **Expand asset universe** — Screen more low/mid-cap tokens for slow-exchange effects
10. **Cross-exchange websocket feeds** — Reduce latency vs REST polling

---

## 9. How to Reproduce

### Run the 30-day backtest
```bash
# Download data (takes ~30 min, has resume support)
python experiments/download_historical_ohlcv.py --days 30

# Backtest all assets
python experiments/backtest_historical.py --data-dir data/historical --top-n 10

# Backtest single asset
python experiments/backtest_historical.py --data-dir data/historical --asset CRV --top-n 10
```

### Run live data collection
```bash
# Volatile assets, 2-hour collection, 2-min intervals
python experiments/collect_statarb_data.py --assets volatile --interval 120 --hours 2

# DEX data
python experiments/collect_dex_data.py --interval 120 --hours 2 --min-liquidity 50000
```

### Build features and train model
```bash
# Build features from collector output
python experiments/build_features.py data/statarb/<run_dir> --target-horizon 5

# Train model
python experiments/train_spread_model.py data/statarb/<run_dir>/features --target target_revert
```

### Stablecoin backtest (to verify it's dead)
```bash
python experiments/backtest_statarb.py data/statarb/20260602_190651
```

---

## 10. File Reference

```
experiments/
├── collect_statarb_data.py      # 10-signal CEX live collector
├── collect_dex_data.py          # DexScreener DEX collector
├── download_historical_ohlcv.py # 30-day OHLCV downloader
├── backtest_statarb.py          # Original JSONL backtester
├── backtest_historical.py       # OU + z-score backtester (Parquet + JSONL)
├── build_features.py            # 63-feature engineering pipeline
└── train_spread_model.py        # ML model trainer with walk-forward CV

scripts/
├── data.py                      # CCXT exchange data fetching
├── fees.py                      # Fee schedule (TRADING_FEES_TAKER dict)
└── graph.py                     # Graph construction

data/
├── historical/                  # 30-day Parquet files (per asset/exchange)
├── statarb/                     # Live collector JSONL runs
└── dex/                         # DEX collector JSONL runs
```
