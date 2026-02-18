"""
Test script for wallet.execute_plan.

Creates a PlanResult that trades within Kraken only — a full cycle
USDC -> BTC -> USDC — ending back where we started.

Usage:
  python -m scripts.wallet_test           # dry run (default)
  python -m scripts.wallet_test --live    # execute real trades (default: 5 USDC)
"""

import argparse
import os
import logging

# Config path: try script dir (scripts/cfg.json), then project root (cfg.json)
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)


def _find_config_path():
    for name in ("cfg.json", "config.json"):
        for directory in (_SCRIPT_DIR, _PROJECT_ROOT):
            path = os.path.join(directory, name)
            if os.path.isfile(path):
                return path
    return None
from scripts.astar_vol import PlanResult
from scripts.wallet import (
    PathExecutor,
    load_exchange_config,
    create_authenticated_exchanges,
)
from scripts.graph import build_graph
from scripts.data import COIN_MARKETS, EXCHANGES

# Configure logging for visibility
logging.basicConfig(level=logging.INFO, format="%(name)s - %(levelname)s - %(message)s")


def _get_test_coin_markets():
    """
    Build coin_markets for Kraken USDC <-> BTC path.
    Kraken uses BTC/USDC (base=BTC, quote=USDC) for this pair.
    """
    markets = {coin: dict(exchanges) for coin, exchanges in COIN_MARKETS.items()}

    if "USDC" in markets:
        markets["USDC"] = {**markets["USDC"], "kraken": "BTC/USDC"}
    markets["BTC"] = {**markets.get("BTC", {}), "kraken": "BTC/USDC"}
    return markets


def main():
    parser = argparse.ArgumentParser(description="Run wallet.execute_plan (dry run by default)")
    parser.add_argument("--live", action="store_true", help="Execute real trades")
    parser.add_argument("--amount", type=float, default=5.0, help="USDC (or USD) to trade (default 5)")
    args = parser.parse_args()

    # 1. PlanResult: Kraken-only cycle USDC -> BTC -> USDC (ends where we started)
    path = [
        ("kraken", "USDC"),
        ("kraken", "BTC"),
        ("kraken", "USDC"),
    ]
    # Edges: rate = units of coin_to per 1 unit of coin_from (after taker fee)
    kraken_taker = 0.004
    # Fetch live BTC/USDC mid from Kraken (1 USDC ≈ 1 USD)
    try:
        kraken = EXCHANGES.get("kraken")
        ticker = kraken.fetch_ticker("BTC/USDC") if kraken else None
        bid = ticker.get("bid") if ticker else None
        ask = ticker.get("ask") if ticker else None
        last = ticker.get("last") if ticker else None
        if isinstance(bid, (int, float)) and isinstance(ask, (int, float)):
            btc_price_usd = (float(bid) + float(ask)) / 2.0
        elif isinstance(last, (int, float)):
            btc_price_usd = float(last)
        else:
            btc_price_usd = 100_000.0  # fallback if fetch fails
    except Exception:
        btc_price_usd = 100_000.0
    logging.getLogger("wallet_test").info("BTC/USDC mid (Kraken): %.2f", btc_price_usd)
    # Rate USDC->BTC = (1/btc_price)*0.996, BTC->USDC = btc_price*0.996
    rate_usdc_to_btc = (1.0 / btc_price_usd) * (1.0 - kraken_taker)
    rate_btc_to_usdc = btc_price_usd * (1.0 - kraken_taker)

    edges = [
        {
            "from": ("kraken", "USDC"),
            "to": ("kraken", "BTC"),
            "kind": "trade",
            "exchange": "kraken",
            "coin_from": "USDC",
            "coin_to": "BTC",
            "rate": rate_usdc_to_btc,
        },
        {
            "from": ("kraken", "BTC"),
            "to": ("kraken", "USDC"),
            "kind": "trade",
            "exchange": "kraken",
            "coin_from": "BTC",
            "coin_to": "USDC",
            "rate": rate_btc_to_usdc,
        },
    ]

    # PlanResult: 2 edges, so final = initial * rate_usdc_to_btc * rate_btc_to_usdc ≈ initial * 0.996^2
    initial_cash_usd = args.amount if args.live else 1000.0
    plan = PlanResult(
        path=path,
        edges=edges,
        final_cash_usd=initial_cash_usd * rate_usdc_to_btc * rate_btc_to_usdc,
        profit_usd=initial_cash_usd * (rate_usdc_to_btc * rate_btc_to_usdc - 1),
    )

    # 2. Build graph nodes (required for price_usd on start node)
    nodes, _ = build_graph()

    # 3. Load exchanges and create executor
    cfg_path = _find_config_path()
    if not cfg_path:
        raise FileNotFoundError(
            "No cfg.json or config.json found. Put one in the project root or in scripts/ "
            f"(e.g. {_PROJECT_ROOT}/cfg.json or {_SCRIPT_DIR}/cfg.json)."
        )
    config = load_exchange_config(cfg_path)
    exchanges = create_authenticated_exchanges(config)

    if "kraken" not in exchanges:
        raise RuntimeError(
            "Kraken not in config. Add a 'kraken' entry with apiKey and secret to your config file."
        )

    dry_run = not args.live
    if args.live:
        # Cap to actual USDC balance to avoid "Insufficient funds"
        kraken = exchanges["kraken"]
        try:
            bal = kraken.fetch_balance()
            # Kraken may use 'USDC' in balance; use .get('free', 0) for available
            free_usdc = float(bal.get("USDC", {}).get("free", 0) or 0)
            # Use 98% of available to leave buffer for fees/rounding
            capped = round(min(free_usdc * 0.98, args.amount), 2)
            if capped <= 0:
                raise RuntimeError(
                    f"No USDC balance found. You have {free_usdc:.2f} USDC free; need some to trade."
                )
            if capped < args.amount:
                logging.getLogger("wallet_test").warning(
                    "Capping trade to %.2f USDC (you have %.2f free, requested %.2f)",
                    capped, free_usdc, args.amount,
                )
            initial_cash_usd = capped
        except Exception as e:
            raise RuntimeError(f"Could not fetch Kraken balance: {e}") from e
        print(f"LIVE MODE: Executing real trades with {initial_cash_usd:.2f} USDC")
        resp = input("Confirm? [y/N]: ")
        if resp.lower() != "y":
            print("Aborted.")
            return

    executor = PathExecutor(
        exchanges=exchanges,
        withdrawal_addresses={},
        dry_run=dry_run,
        coin_markets=_get_test_coin_markets(),
    )

    # 4. Execute plan
    result = executor.execute_plan(plan, initial_cash_usd, nodes)

    # 5. Report
    print("\n--- execute_plan result ---")
    print(f"success: {result.success}")
    print(f"final_coin: {result.final_coin}")
    print(f"final_amount: {result.final_amount}")
    print(f"final_amount_usd: {result.final_amount_usd:.2f}")
    if result.total_error:
        print(f"total_error: {result.total_error}")
    for s in result.steps:
        print(f"  step {s.step_index}: {s.kind} on {s.exchange} | in={s.amount_in:.4f} out={s.amount_out:.4f} | {s.order_id or s.error or 'ok'}")


if __name__ == "__main__":
    main()
