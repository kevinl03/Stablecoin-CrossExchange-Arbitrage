# ==============================================================
# wallet.py — Execute arbitrage path via CCXT (trades and withdrawals)
# ==============================================================
"""
Execute the path found by A* using CCXT:
- Trade edges: market order on the same exchange (coin_from -> coin_to).
- Transfer edges: withdraw from source exchange to destination exchange address.

Requires authenticated exchange instances (API keys). Use dry_run=True to
preview orders and withdrawals without sending.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
import json
from typing import Dict, Any

# NodeId = (exchange_name, coin)
NodeId = Tuple[str, str]

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Trade symbol resolution (using data.COIN_MARKETS)
# ---------------------------------------------------------------------------

def _get_trade_symbol_and_side(
    exchange_name: str,
    coin_from: str,
    coin_to: str,
    coin_markets: Dict[str, Dict[str, str]],
) -> Optional[Tuple[str, str]]:
    """
    Resolve CCXT symbol and side for trading coin_from -> coin_to on exchange.

    Returns:
        (symbol, side) e.g. ("USDC/USDT", "buy") or ("USDT/USDC", "sell").
        side is "buy" or "sell"; amount is always in coin_from for our caller
        (we convert to base/quote amount inside execute).
    """
    # Prefer market that has both coins: base/quote
    for base_coin, quote_coin in [(coin_to, coin_from), (coin_from, coin_to)]:
        symbol = f"{base_coin}/{quote_coin}"
        # Check if this symbol is the one we use for either coin on this exchange
        m_from = coin_markets.get(coin_from, {}).get(exchange_name)
        m_to = coin_markets.get(coin_to, {}).get(exchange_name)
        _match = lambda m, s: s in m if isinstance(m, list) else m == s
        if _match(m_from, symbol) or _match(m_to, symbol):
            if base_coin == coin_to and quote_coin == coin_from:
                return (symbol, "buy")   # buy base (coin_to) with quote (coin_from)
            if base_coin == coin_from and quote_coin == coin_to:
                return (symbol, "sell")  # sell base (coin_from) for quote (coin_to)
    return None


def _round_amount(amount: float, decimals: int = 8) -> float:
    """Round amount to avoid exchange precision errors."""
    return round(amount, decimals)


# ---------------------------------------------------------------------------
# Execution result types
# ---------------------------------------------------------------------------

@dataclass
class StepResult:
    """Result of one step (one edge) in the path."""
    step_index: int
    kind: str  # "trade" | "transfer"
    exchange: str
    symbol_or_chain: Optional[str] = None  # symbol for trade, chain for transfer
    side: Optional[str] = None             # "buy" | "sell" for trade
    amount_in: float = 0.0
    amount_out: float = 0.0
    order_id: Optional[str] = None # Optional means could be a string, or if nothing is assigned, it will assume None. 
    withdraw_id: Optional[str] = None
    error: Optional[str] = None
    dry_run: bool = False


@dataclass
class ExecutionResult:
    """Result of executing a full arbitrage plan."""
    success: bool
    steps: List[StepResult] = field(default_factory=list)
    final_coin: Optional[str] = None
    final_amount: float = 0.0
    final_amount_usd: float = 0.0
    total_error: Optional[str] = None


# ---------------------------------------------------------------------------
# Path executor
# ---------------------------------------------------------------------------

class PathExecutor:
    """
    Executes an arbitrage path (PlanResult) via CCXT: trades and optional
    withdrawals.

    - exchanges: dict[exchange_name, ccxt.Exchange] — authenticated instances.
    - withdrawal_addresses: optional dict[target_exchange][coin][chain] = address.
      If missing, transfer steps are skipped (or fail if required).
    - dry_run: if True, no orders or withdrawals are sent; steps are logged only.
    """

    def __init__(
        self,
        exchanges: Dict[str, Any],
        withdrawal_addresses: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None,
        dry_run: bool = True,
        coin_markets: Optional[Dict[str, Dict[str, str]]] = None,
    ):
        self.exchanges = exchanges
        self.withdrawal_addresses = withdrawal_addresses or {}
        self.dry_run = dry_run
        # Allow override for tests; otherwise import from data
        if coin_markets is not None:
            self._coin_markets = coin_markets
        else:
            from scripts.data import COIN_MARKETS
            self._coin_markets = COIN_MARKETS

    def execute_plan(
        self,
        plan: Any,
        initial_cash_usd: float,
        nodes: Dict[NodeId, Dict[str, Any]],
    ) -> ExecutionResult:
        """
        Execute the path in `plan` starting with `initial_cash_usd` (USD value).
        `nodes` must be the graph nodes dict from build_graph() so we have
        price_usd for the first node to compute initial amount in coin.

        plan must have .path and .edges (e.g. PlanResult from astar_vol or weighted_astar).
        """
        path = getattr(plan, "path", None) # tries to get the path from the plan, and if not possible, then it will return none.
        edges = getattr(plan, "edges", None)
        if not path or not edges or len(path) != len(edges) + 1:
            return ExecutionResult(
                success=False,
                total_error="Invalid plan: path and edges length mismatch or missing.",
            )

        # Start amount in first node's coin
        start_node = path[0]
        if start_node not in nodes:
            return ExecutionResult(
                success=False,
                total_error=f"Start node {start_node} not in nodes.",
            )
        price_usd = float(nodes[start_node].get("price_usd", 0.0))
        if price_usd <= 0:
            return ExecutionResult(
                success=False,
                total_error=f"No price for start node {start_node}.",
            )
        current_coin = start_node[1]
        current_amount = _round_amount(initial_cash_usd / price_usd)
        steps: List[StepResult] = []

        for i, edge in enumerate(edges):
            kind = edge.get("kind", "trade")
            from_node = edge["from"]
            to_node = edge["to"]
            ex_name = edge.get("exchange", from_node[0])

            if kind == "trade":
                coin_from = edge["coin_from"]
                coin_to = edge["coin_to"]
                rate = float(edge.get("rate", 0.0))
                if rate <= 0:
                    steps.append(StepResult(
                        step_index=i,
                        kind="trade",
                        exchange=ex_name,
                        symbol_or_chain=None,
                        amount_in=current_amount,
                        amount_out=0.0,
                        error="Invalid trade rate",
                        dry_run=self.dry_run,
                    ))
                    return ExecutionResult(
                        success=False,
                        steps=steps,
                        total_error="Invalid trade rate on edge.",
                    )
                # Amount we will have in coin_to after trade
                amount_out = _round_amount(current_amount * rate)

                symbol_side = _get_trade_symbol_and_side(
                    ex_name, coin_from, coin_to, self._coin_markets
                )
                if not symbol_side:
                    steps.append(StepResult(
                        step_index=i,
                        kind="trade",
                        exchange=ex_name,
                        amount_in=current_amount,
                        amount_out=amount_out,
                        error=f"No symbol for {coin_from}->{coin_to} on {ex_name}",
                        dry_run=self.dry_run,
                    ))
                    return ExecutionResult(
                        success=False,
                        steps=steps,
                        total_error=f"No market symbol for {coin_from}/{coin_to} on {ex_name}.",
                    )
                symbol, side = symbol_side

                # CCXT amount: for "buy" on BASE/QUOTE, amount is in base (coin_to);
                # for "sell", amount is in base (coin_from).
                if side == "buy":
                    order_amount = amount_out  # amount of base (coin_to) we want
                else:
                    order_amount = current_amount  # amount of base (coin_from) we sell

                exchange = self.exchanges.get(ex_name)
                if not exchange:
                    steps.append(StepResult(
                        step_index=i,
                        kind="trade",
                        exchange=ex_name,
                        symbol_or_chain=symbol,
                        side=side,
                        amount_in=current_amount,
                        amount_out=amount_out,
                        error=f"No authenticated exchange for {ex_name}",
                        dry_run=self.dry_run,
                    ))
                    return ExecutionResult(
                        success=False,
                        steps=steps,
                        total_error=f"Exchange {ex_name} not provided.",
                    )

                if self.dry_run:
                    steps.append(StepResult(
                        step_index=i,
                        kind="trade",
                        exchange=ex_name,
                        symbol_or_chain=symbol,
                        side=side,
                        amount_in=current_amount,
                        amount_out=amount_out,
                        order_id="(dry run)",
                        dry_run=True,
                    ))
                    logger.info(
                        f"[DRY RUN] Trade on {ex_name}: {side} {order_amount} {symbol}"
                    )
                else:
                    try:
                        order = exchange.create_order(
                            symbol, "market", side, order_amount
                        )
                        order_id = order.get("id") or order.get("orderId") or "(created)"
                        steps.append(StepResult(
                            step_index=i,
                            kind="trade",
                            exchange=ex_name,
                            symbol_or_chain=symbol,
                            side=side,
                            amount_in=current_amount,
                            amount_out=amount_out,
                            order_id=str(order_id),
                            dry_run=False,
                        ))
                        logger.info(
                            f"Trade executed on {ex_name}: {side} {order_amount} {symbol} -> {order_id}"
                        )
                    except Exception as e:
                        err_msg = str(e)
                        steps.append(StepResult(
                            step_index=i,
                            kind="trade",
                            exchange=ex_name,
                            symbol_or_chain=symbol,
                            side=side,
                            amount_in=current_amount,
                            amount_out=0.0,
                            error=err_msg,
                            dry_run=False,
                        ))
                        return ExecutionResult(
                            success=False,
                            steps=steps,
                            total_error=err_msg,
                        )

                current_coin = coin_to
                current_amount = amount_out
                continue

            if kind == "transfer":
                coin = edge.get("coin", from_node[1])
                chain = edge.get("chain")
                target_exchange = edge.get("target_exchange", to_node[0])
                fee_units = edge.get("withdrawal_fee_units") or 0.0
                rate = float(edge.get("rate", 0.0))
                if rate <= 0:
                    steps.append(StepResult(
                        step_index=i,
                        kind="transfer",
                        exchange=ex_name,
                        symbol_or_chain=chain or "",
                        amount_in=current_amount,
                        amount_out=0.0,
                        error="Invalid transfer rate",
                        dry_run=self.dry_run,
                    ))
                    return ExecutionResult(
                        success=False,
                        steps=steps,
                        total_error="Invalid transfer rate on edge.",
                    )
                # Amount after withdrawal fee (we model as rate = 1 - fee/amount)
                amount_out = _round_amount(current_amount * rate)

                addr_entry = self.withdrawal_addresses.get(target_exchange, {}).get(coin)
                if isinstance(addr_entry, str):
                    address = addr_entry
                elif isinstance(addr_entry, dict):
                    address = (chain and addr_entry.get(chain)) or addr_entry.get("*") or (list(addr_entry.values())[0] if addr_entry else None)
                else:
                    address = None

                if not address:
                    steps.append(StepResult(
                        step_index=i,
                        kind="transfer",
                        exchange=ex_name,
                        symbol_or_chain=chain or "",
                        amount_in=current_amount,
                        amount_out=amount_out,
                        error=f"No withdrawal address for {target_exchange} / {coin}" + (f" / {chain}" if chain else ""),
                        dry_run=self.dry_run,
                    ))
                    return ExecutionResult(
                        success=False,
                        steps=steps,
                        total_error=f"Withdrawal address required for {target_exchange} {coin}.",
                    )

                exchange = self.exchanges.get(ex_name)
                if not exchange:
                    steps.append(StepResult(
                        step_index=i,
                        kind="transfer",
                        exchange=ex_name,
                        symbol_or_chain=chain or "",
                        amount_in=current_amount,
                        amount_out=amount_out,
                        error=f"No authenticated exchange for {ex_name}",
                        dry_run=self.dry_run,
                    ))
                    return ExecutionResult(
                        success=False,
                        steps=steps,
                        total_error=f"Exchange {ex_name} not provided.",
                    )

                if self.dry_run:
                    steps.append(StepResult(
                        step_index=i,
                        kind="transfer",
                        exchange=ex_name,
                        symbol_or_chain=chain or "",
                        amount_in=current_amount,
                        amount_out=amount_out,
                        withdraw_id="(dry run)",
                        dry_run=True,
                    ))
                    logger.info(
                        f"[DRY RUN] Withdraw {current_amount} {coin} from {ex_name} to {address[:12]}... (chain={chain})"
                    )
                else:
                    try:
                        wd = exchange.withdraw(coin, current_amount, address, params={"chain": chain} if chain else None)
                        wd_id = wd.get("id") or wd.get("withdrawalId") or "(submitted)"
                        steps.append(StepResult(
                            step_index=i,
                            kind="transfer",
                            exchange=ex_name,
                            symbol_or_chain=chain or "",
                            amount_in=current_amount,
                            amount_out=amount_out,
                            withdraw_id=str(wd_id),
                            dry_run=False,
                        ))
                        logger.info(
                            f"Withdraw submitted: {current_amount} {coin} from {ex_name} -> {target_exchange} (chain={chain})"
                        )
                    except Exception as e:
                        err_msg = str(e)
                        steps.append(StepResult(
                            step_index=i,
                            kind="transfer",
                            exchange=ex_name,
                            symbol_or_chain=chain or "",
                            amount_in=current_amount,
                            amount_out=0.0,
                            error=err_msg,
                            dry_run=False,
                        ))
                        return ExecutionResult(
                            success=False,
                            steps=steps,
                            total_error=err_msg,
                        )

                current_coin = coin
                current_amount = amount_out
                continue

            steps.append(StepResult(
                step_index=i,
                kind=kind,
                exchange=ex_name,
                amount_in=current_amount,
                amount_out=0.0,
                error=f"Unknown edge kind: {kind}",
                dry_run=self.dry_run,
            ))
            return ExecutionResult(
                success=False,
                steps=steps,
                total_error=f"Unknown edge kind: {kind}.",
            )

        # Final USD value using last node's price if available
        final_node = path[-1]
        final_price_usd = float(nodes.get(final_node, {}).get("price_usd", 0.0))
        final_amount_usd = current_amount * final_price_usd if final_price_usd > 0 else 0.0

        return ExecutionResult(
            success=True,
            steps=steps,
            final_coin=current_coin,
            final_amount=current_amount,
            final_amount_usd=final_amount_usd,
        )


# ---------------------------------------------------------------------------
# Convenience: build authenticated exchanges from config
# ---------------------------------------------------------------------------

def create_authenticated_exchanges(
    config: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Build a dict of authenticated CCXT instances from config.

    config format:
        {
            "binance": {"apiKey": "...", "secret": "...", "options": {...}},
            "kraken":  {"apiKey": "...", "secret": "...", "password": "..."},
            ...
        }

    Uses the same exchange classes as data.EXCHANGES (binance, kraken, kucoin, bybit).
    """
    import ccxt
    from scripts.data import EXCHANGES

    out = {}
    for ex_name, cfg in config.items():
        if not isinstance(cfg, dict):
            continue
        base = EXCHANGES.get(ex_name)
        if base is None:
            logger.warning(f"Unknown exchange {ex_name}, skipping")
            continue
        # Use the same class as the public instance
        exchange_class = type(base)
        out[ex_name] = exchange_class({
            "apiKey": cfg.get("apiKey", ""),
            "secret": cfg.get("secret", ""),
            "password": cfg.get("password"),
            "enableRateLimit": True,
            "options": cfg.get("options", {}),
        })
    return out

# ---------------------------------------------------------------------------
# Load exchanges from a json file
# should be in this format
# {
#     "binance": {
#         "apiKey": "your_binance_api_key",
#         "secret": "your_binance_secret",
#         "options": {"defaultType": "future"} 
#     },
#     "kraken": {
#         "apiKey": "your_kraken_api_key",
#         "secret": "your_kraken_secret",
#         "password": "your_kraken_password" 
#     }
# }


def load_exchange_config(filepath: str) -> Dict[str, Dict[str, Any]]:
    """
    Reads exchange API keys and secrets from a JSON file 
    and returns them as a nested dictionary.
    """
    try:
        with open(filepath, 'r') as file:
            config_dict = json.load(file)
            return config_dict
            
    except FileNotFoundError:
        print(f"Error: The configuration file '{filepath}' was not found.")
        return {}
    except json.JSONDecodeError:
        print(f"Error: The file '{filepath}' contains invalid JSON formatting.")
        return {}

# --- Example (only when run as script) ---
# if __name__ == "__main__":
#     config = load_exchange_config("cfg.json")  # or config.json
#     exchanges = create_authenticated_exchanges(config)
