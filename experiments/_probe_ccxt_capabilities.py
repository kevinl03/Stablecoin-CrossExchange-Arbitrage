"""Quick probe: what CCXT methods does each exchange support?"""
import ccxt

exchanges = {
    'binance': ccxt.binance({'timeout': 5000}),
    'kraken': ccxt.kraken({'timeout': 5000}),
    'kucoin': ccxt.kucoin({'timeout': 5000}),
    'bybit': ccxt.bybit({'timeout': 5000}),
    'okx': ccxt.okx({'timeout': 5000}),
    'gateio': ccxt.gateio({'timeout': 5000}),
    'bitget': ccxt.bitget({'timeout': 5000}),
    'mexc': ccxt.mexc({'timeout': 5000}),
    'htx': ccxt.htx({'timeout': 5000}),
    'coinbase': ccxt.coinbase({'timeout': 5000}),
    'cryptocom': ccxt.cryptocom({'timeout': 5000}),
    'phemex': ccxt.phemex({'timeout': 5000}),
}

methods = [
    'fetchTicker', 'fetchTickers', 'fetchOrderBook', 'fetchTrades', 'fetchOHLCV',
    'fetchFundingRate', 'fetchFundingRateHistory', 'fetchFundingRates',
    'fetchBorrowRate', 'fetchBorrowRates', 'fetchBorrowRateHistory',
    'fetchOpenInterest', 'fetchOpenInterestHistory',
    'fetchDepositWithdrawFees', 'fetchTradingFees', 'fetchTradingFee',
    'fetchCurrencies', 'fetchStatus',
    'fetchBidsAsks', 'fetchMarkOHLCV', 'fetchIndexOHLCV',
    'fetchLeverageTiers', 'fetchMarketLeverageTiers',
    'fetchLiquidations', 'fetchMyLiquidations',
    'fetchGreeks',
    'fetchTransactionFees', 'fetchDepositWithdrawFee',
]

header = f"{'Method':<35}"
for name in exchanges:
    header += f"{name[:5]:>6}"
print(header)
print("-" * len(header))

for method in methods:
    row = f"{method:<35}"
    for name, ex in exchanges.items():
        has = ex.has.get(method, False)
        if has is True:
            row += f"{'Y':>6}"
        elif has == 'emulated':
            row += f"{'emu':>6}"
        else:
            row += f"{'-':>6}"
    print(row)

# Now try to actually fetch currencies for each exchange to see what data we get
print("\n\n=== LIVE: fetchDepositWithdrawFees for USDT ===")
for name, ex in exchanges.items():
    if not ex.has.get('fetchDepositWithdrawFees', False):
        print(f"  {name}: not supported")
        continue
    try:
        fees = ex.fetch_deposit_withdraw_fees(['USDT'])
        usdt = fees.get('USDT', {})
        networks = usdt.get('networks', {})
        net_names = list(networks.keys())[:5]
        print(f"  {name}: networks={net_names}")
        if net_names:
            sample = networks[net_names[0]]
            w = sample.get('withdraw', {})
            print(f"    {net_names[0]}: fee={w.get('fee')}, min={w.get('min')}, max={w.get('max')}")
    except Exception as e:
        print(f"  {name}: ERROR {str(e)[:80]}")

print("\n\n=== LIVE: fetchFundingRate for USDT perp (where supported) ===")
perp_symbols = {
    'binance': 'USDT/USDC:USDC',
    'bybit': 'USDT/USDC:USDC',
    'okx': 'USDT/USDC:USDC',
    'gateio': 'USDT/USDC:USDC',
    'bitget': 'USDT/USDC:USDC',
}
for name in ['binance', 'bybit', 'okx', 'gateio', 'bitget']:
    ex = exchanges[name]
    if not ex.has.get('fetchFundingRate', False):
        print(f"  {name}: fetchFundingRate not supported")
        continue
    try:
        # Try common stablecoin perp symbols
        for sym in ['USDT/USDC:USDC', 'USDT/USD:USD', 'USDC/USDT:USDT']:
            try:
                fr = ex.fetch_funding_rate(sym)
                print(f"  {name} [{sym}]: rate={fr.get('fundingRate')}, next={fr.get('fundingTimestamp')}")
                break
            except:
                continue
        else:
            print(f"  {name}: no stablecoin perp found")
    except Exception as e:
        print(f"  {name}: ERROR {str(e)[:80]}")

print("\n\n=== LIVE: fetchStatus (exchange health) ===")
for name, ex in exchanges.items():
    if not ex.has.get('fetchStatus', False):
        continue
    try:
        status = ex.fetch_status()
        print(f"  {name}: status={status.get('status')}, updated={status.get('updated')}")
    except Exception as e:
        print(f"  {name}: ERROR {str(e)[:60]}")
