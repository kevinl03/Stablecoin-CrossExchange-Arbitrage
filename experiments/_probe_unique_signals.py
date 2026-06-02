"""Probe unique data signals: withdrawal fee dynamics, currency network info, and batch tickers."""
import ccxt
import json
import time

exchanges = {
    'binance': ccxt.binance({'timeout': 8000}),
    'kucoin': ccxt.kucoin({'timeout': 8000}),
    'bitget': ccxt.bitget({'timeout': 8000}),
    'htx': ccxt.htx({'timeout': 8000}),
    'kraken': ccxt.kraken({'timeout': 8000}),
}

COINS = ['USDT', 'USDC', 'DAI', 'TUSD', 'FDUSD', 'BUSD', 'PYUSD', 'USDP', 'GUSD']

# 1. fetchCurrencies — shows deposit/withdrawal status, min amounts, network details
print("=== fetchCurrencies: withdrawal enable/disable status (KuCoin) ===")
try:
    currencies = exchanges['kucoin'].fetch_currencies()
    for coin in COINS:
        c = currencies.get(coin, {})
        if not c:
            continue
        active = c.get('active')
        deposit = c.get('deposit')
        withdraw = c.get('withdraw')
        networks = c.get('networks', {})
        net_summary = []
        for net_name, net_info in list(networks.items())[:5]:
            net_summary.append({
                'network': net_name,
                'active': net_info.get('active'),
                'deposit': net_info.get('deposit'),
                'withdraw': net_info.get('withdraw'),
                'fee': net_info.get('fee'),
                'min_withdraw': net_info.get('limits', {}).get('withdraw', {}).get('min'),
            })
        print(f"  {coin}: active={active} deposit={deposit} withdraw={withdraw}")
        for ns in net_summary:
            print(f"    {ns['network']}: deposit={ns['deposit']} withdraw={ns['withdraw']} fee={ns['fee']} min={ns['min_withdraw']}")
except Exception as e:
    print(f"  ERROR: {e}")

# 2. fetchTickers — get ALL stablecoin tickers in ONE call (much faster than per-pair)
print("\n=== fetchTickers: batch ticker fetch (Binance) ===")
try:
    stablecoin_pairs = [
        'USDC/USDT', 'DAI/USDT', 'TUSD/USDT', 'FDUSD/USDT',
        'BUSD/USDT', 'PYUSD/USDT', 'USDP/USDT',
    ]
    t0 = time.time()
    tickers = exchanges['binance'].fetch_tickers(stablecoin_pairs)
    t1 = time.time()
    print(f"  Fetched {len(tickers)} tickers in {t1-t0:.2f}s (vs ~{len(stablecoin_pairs)*1.5:.0f}s individual)")
    for sym, t in tickers.items():
        spread = None
        if t.get('bid') and t.get('ask'):
            spread = round((t['ask'] - t['bid']) / ((t['ask'] + t['bid'])/2) * 10000, 2)
        print(f"  {sym}: bid={t.get('bid')} ask={t.get('ask')} spread={spread}bps vol24h={t.get('quoteVolume')}")
except Exception as e:
    print(f"  ERROR: {e}")

# 3. Funding rate history — shows how funding rates evolve for stablecoin perps
print("\n=== fetchFundingRateHistory: USDC/USDT perp (Binance) ===")
try:
    history = exchanges['binance'].fetch_funding_rate_history('USDC/USDT:USDT', limit=10)
    for h in history[-5:]:
        ts = h.get('datetime', '')
        rate = h.get('fundingRate')
        print(f"  {ts}: rate={rate}")
except Exception as e:
    print(f"  ERROR: {e}")

# 4. Open interest for stablecoin perps
print("\n=== fetchOpenInterest: stablecoin perps ===")
for name in ['binance', 'kucoin']:
    ex = exchanges[name]
    if not ex.has.get('fetchOpenInterest', False):
        print(f"  {name}: not supported")
        continue
    try:
        oi = ex.fetch_open_interest('USDC/USDT:USDT')
        print(f"  {name} USDC/USDT:USDT OI={oi.get('openInterestAmount')} {oi.get('baseVolume')} timestamp={oi.get('datetime')}")
    except Exception as e:
        print(f"  {name}: ERROR {str(e)[:80]}")

# 5. Borrow rate history (shows margin market demand for stablecoins)
print("\n=== fetchBorrowRateHistory: USDT (Binance) ===")
try:
    if exchanges['binance'].has.get('fetchBorrowRateHistory', False):
        borrow = exchanges['binance'].fetch_borrow_rate_history('USDT', limit=5)
        for b in borrow:
            print(f"  {b.get('datetime')}: rate={b.get('rate')} period={b.get('period')}")
    else:
        print("  not supported")
except Exception as e:
    print(f"  ERROR: {str(e)[:100]}")

# 6. Check trading fee differences across exchanges (some have VIP tiers)
print("\n=== fetchTradingFee for USDC/USDT ===")
for name in ['bitget', 'htx', 'kraken']:
    ex = exchanges[name]
    if not ex.has.get('fetchTradingFee', False):
        print(f"  {name}: not supported")
        continue
    try:
        fee = ex.fetch_trading_fee('USDC/USDT')
        print(f"  {name}: maker={fee.get('maker')} taker={fee.get('taker')} percentage={fee.get('percentage')}")
    except Exception as e:
        try:
            fee = ex.fetch_trading_fee('USDT/USD')
            print(f"  {name} USDT/USD: maker={fee.get('maker')} taker={fee.get('taker')}")
        except:
            print(f"  {name}: ERROR {str(e)[:80]}")
