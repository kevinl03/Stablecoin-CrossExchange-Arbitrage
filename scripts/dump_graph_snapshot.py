"""Fetch a live graph once and save it as a JSON fixture for offline UI dev."""

import json
import sys
import math
import time
from pathlib import Path
from collections import defaultdict

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.data import EXCHANGES, STABLE_COINS, COIN_MARKETS, normalize_price_to_usd
from scripts.fees import WITHDRAWAL_FEES, get_taker_fee, get_network_gas_fee
from scripts.transfer_time import get_chain_time_seconds
from scripts.graph import _fetch_actual_trading_pair_rate

OUT = project_root / "scripts" / "graph_snapshot.json"


def _key(k):
    return f"{k[0]}|{k[1]}"


def _edge(e: dict) -> dict:
    out = {}
    for key, val in e.items():
        if isinstance(val, tuple) and len(val) == 2:
            out[key] = _key(val)
        else:
            out[key] = val
    return out


def main():
    print("Fetching live data …")
    prices = {}
    snapshot_ts = time.time()

    for coin in STABLE_COINS:
        for ex_name, ex in EXCHANGES.items():
            market = COIN_MARKETS.get(coin, {}).get(ex_name)
            if not market:
                continue
            try:
                ticker = ex.fetch_ticker(market)
            except Exception:
                continue
            bid, ask, last = ticker.get("bid"), ticker.get("ask"), ticker.get("last")
            if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
                conservative_price = bid
            elif isinstance(last, (int, float)):
                conservative_price = float(last)
            else:
                continue
            price_usd = normalize_price_to_usd(coin, market, conservative_price)
            if price_usd is not None:
                prices[(ex_name, coin)] = price_usd

    nodes = {
        (ex, coin): {"exchange": ex, "coin": coin, "price_usd": p, "snapshot_ts": snapshot_ts}
        for (ex, coin), p in prices.items()
    }

    adj = defaultdict(list)

    for ex_name in EXCHANGES:
        coins_here = [c for c in STABLE_COINS if (ex_name, c) in prices]
        if len(coins_here) < 2:
            continue
        taker_fee = get_taker_fee(ex_name) or 0.0
        for i, c_from in enumerate(coins_here):
            for j, c_to in enumerate(coins_here):
                if i == j:
                    continue
                actual = _fetch_actual_trading_pair_rate(ex_name, c_from, c_to)
                raw = actual if actual is not None else prices[(ex_name, c_from)] / prices[(ex_name, c_to)]
                eff = raw * (1.0 - taker_fee)
                if eff <= 0:
                    continue
                fn, tn = (ex_name, c_from), (ex_name, c_to)
                adj[fn].append({"from": fn, "to": tn, "kind": "trade",
                                "exchange": ex_name, "coin_from": c_from, "coin_to": c_to,
                                "rate": eff, "cost": -math.log(eff),
                                "taker_fee": taker_fee, "withdrawal_fee_units": None,
                                "chain": None, "transfer_time_sec": 0.0})

    coin_exs = {coin: [ex for (ex, c) in prices if c == coin] for coin in STABLE_COINS}
    for coin in STABLE_COINS:
        for ex_from in coin_exs.get(coin, []):
            cfg = WITHDRAWAL_FEES.get(ex_from, {}).get(coin)
            if not cfg:
                continue
            for ex_to in coin_exs[coin]:
                if ex_to == ex_from:
                    continue
                chains_to = WITHDRAWAL_FEES.get(ex_to, {}).get(coin, {})
                common = set(cfg) & set(chains_to) if chains_to else set(cfg)
                for chain in common:
                    fee_u = cfg[chain]
                    gas = get_network_gas_fee(chain)
                    wf = fee_u * prices[(ex_from, coin)]
                    total = wf + gas
                    ref = 10000.0
                    if total >= ref:
                        continue
                    rate = 1.0 - total / ref
                    fn, tn = (ex_from, coin), (ex_to, coin)
                    adj[fn].append({"from": fn, "to": tn, "kind": "transfer",
                                    "exchange": ex_from, "target_exchange": ex_to,
                                    "coin": coin, "rate": rate, "cost": -math.log(rate),
                                    "taker_fee": None, "withdrawal_fee_units": fee_u,
                                    "gas_fee_usd": gas, "total_fee_usd": total,
                                    "chain": chain, "transfer_time_sec": get_chain_time_seconds(chain) or 0.0})

    payload = {
        "nodes": {_key(k): v for k, v in nodes.items()},
        "adj": {_key(k): [_edge(e) for e in edges] for k, edges in adj.items()},
    }
    OUT.write_text(json.dumps(payload, indent=2))
    print(f"Saved {len(payload['nodes'])} nodes, "
          f"{sum(len(v) for v in payload['adj'].values())} edges → {OUT}")


if __name__ == "__main__":
    main()
