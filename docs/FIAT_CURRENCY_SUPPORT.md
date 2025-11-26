# Fiat Currency Support in Arbitrage System

## Overview

The system now supports **fiat currencies** (USD, CAD, EUR, etc.) as nodes in the arbitrage graph, enabling stablecoin ↔ fiat conversions and creating significantly more arbitrage opportunities.

---

## What This Adds

### 1. New Node Type: Fiat Nodes

Fiat currencies are represented as special nodes in the graph:
- **USD on Kraken**: `FiatNode("Kraken", "USD", 1.0)`
- **CAD on Coinbase**: `FiatNode("Coinbase", "CAD", 1.0)`
- **EUR on Binance**: `FiatNode("Binance", "EUR", 1.0)`

Fiat nodes are treated similarly to stablecoin nodes but with special properties:
- Price typically = 1.0 (base currency) or exchange rate
- Can be converted to/from stablecoins on the same exchange
- Can be transferred between exchanges

### 2. New Edge Types

#### A. Stablecoin ↔ Fiat Conversion (Same Exchange)
- **USDT → USD on Kraken**: Instant conversion, ~0.1% fee
- **USD → USDC on Coinbase**: Instant conversion, ~0.1% fee
- **Transfer time**: 0 seconds (instant on-exchange conversion)

#### B. Fiat → Fiat Transfer (Between Exchanges)
- **USD (Kraken) → USD (Coinbase)**: Bank transfer, ~0.15% fee
- **Transfer time**: ~60 seconds (faster than crypto transfers)

### 3. New Arbitrage Paths

**Example Path 1**: Using fiat as intermediate step
```
USDT (Kraken) → USD (Kraken) → USD (Coinbase) → USDC (Coinbase)
```

**Example Path 2**: Full cycle with fiat
```
USDT (Kraken) → USD (Kraken) → USD (Coinbase) → USDC (Coinbase)
→ USD (Coinbase) → USD (Kraken) → USDT (Kraken)
```

---

## Implementation

### FiatEnabledGraphBuilder

The `FiatEnabledGraphBuilder` class extends the standard graph builder to include fiat currencies:

```python
from src.graph_builder_fiat import FiatEnabledGraphBuilder
from src.connectors.kraken_connector import KrakenConnector
from src.connectors.coinbase_connector import CoinbaseConnector

# Create builder with fiat support
builder = FiatEnabledGraphBuilder()

# Add connectors with supported fiat currencies
kraken = KrakenConnector()
coinbase = CoinbaseConnector()

builder.add_connector(kraken, supported_fiats=['USD', 'CAD'])
builder.add_connector(coinbase, supported_fiats=['USD'])

# Build graph with fiat nodes
graph = builder.build_graph(
    fiat_conversion_fee=0.001,      # 0.1% for stablecoin <-> fiat
    fiat_transfer_fee=0.0015,        # 0.15% for fiat transfers
    include_fiat_to_fiat=True       # Enable fiat transfers between exchanges
)
```

### Graph Structure

**Without Fiat** (3 exchanges × 3 stablecoins):
- Nodes: 9
- Edges: 72 (all stablecoin transfers)

**With Fiat** (3 exchanges × 3 stablecoins + USD):
- Nodes: 12 (9 stablecoins + 3 USD nodes)
- Edges: 96+ (includes conversions and fiat transfers)
- **Expansion**: ~1.3-2x more edges, significantly more paths

---

## Benefits

### 1. More Arbitrage Opportunities

Fiat nodes create additional paths that weren't possible before:
- **Direct stablecoin transfers**: Limited by blockchain networks
- **Fiat intermediaries**: Can use bank transfers, which are often faster and cheaper

### 2. Instant Conversions

Stablecoin ↔ fiat conversions on the same exchange are typically:
- **Instant** (0 seconds transfer time)
- **Lower fees** (0.1% vs 0.2% for cross-exchange transfers)
- **More reliable** (no blockchain confirmation needed)

### 3. Real-World Applicability

Many exchanges support fiat trading:
- **Kraken**: USD, CAD, EUR, GBP, JPY
- **Coinbase**: USD, EUR, GBP
- **Binance**: USD, EUR (via fiat partners)

This makes the system more realistic and applicable to real trading scenarios.

---

## Cost Structure

### Conversion Fees

| Conversion Type | Fee | Transfer Time |
|----------------|-----|---------------|
| Stablecoin → Fiat (same exchange) | 0.1% | 0s (instant) |
| Fiat → Stablecoin (same exchange) | 0.1% | 0s (instant) |
| Fiat → Fiat (between exchanges) | 0.15% | ~60s |

### Example: Full Arbitrage Path

**Path**: USDT (Kraken) → USD (Kraken) → USD (Coinbase) → USDC (Coinbase)

**Costs**:
1. USDT → USD on Kraken: 0.1% fee, 0s
2. USD Kraken → Coinbase: 0.15% fee, 60s
3. USD → USDC on Coinbase: 0.1% fee, 0s
4. **Total**: 0.35% fee, 60s transfer time

**Profitability**: Requires price difference > 0.35%

---

## Usage Examples

### Example 1: Basic Fiat-Enabled Graph

```python
from src.graph_builder_fiat import FiatEnabledGraphBuilder
from src import ArbitrageAgent

# Build graph with fiat
builder = FiatEnabledGraphBuilder()
# ... add connectors ...
graph = builder.build_graph()

# Use with arbitrage agent (works the same way)
agent = ArbitrageAgent(graph)
opportunities = agent.find_all_opportunities(algorithm='astar')

# Opportunities now include fiat paths!
for path, profit, cost, desc in opportunities:
    print(f"{desc}: ${profit:.2f} profit, ${cost:.2f} cost")
```

### Example 2: Finding Fiat Arbitrage Paths

```python
from src.graph_builder_fiat import FiatEnabledGraphBuilder

builder = FiatEnabledGraphBuilder()
# ... setup ...

# Get specific fiat paths
paths = builder.get_fiat_arbitrage_paths(
    start_stablecoin="USDT",
    target_stablecoin="USDC",
    fiat_currency="USD"
)

for path in paths:
    print("Path:", " -> ".join(f"{ex}({curr})" for ex, curr in path))
```

---

## Supported Fiat Currencies

The system recognizes these fiat currencies:
- **USD** (US Dollar)
- **CAD** (Canadian Dollar)
- **EUR** (Euro)
- **GBP** (British Pound)
- **JPY** (Japanese Yen)
- **AUD** (Australian Dollar)
- **CHF** (Swiss Franc)
- **CNY** (Chinese Yuan)
- **HKD** (Hong Kong Dollar)
- **SGD** (Singapore Dollar)
- **NZD** (New Zealand Dollar)
- **MXN** (Mexican Peso)
- **BRL** (Brazilian Real)
- **INR** (Indian Rupee)
- **KRW** (South Korean Won)
- **TRY** (Turkish Lira)

---

## Technical Details

### FiatNode Class

```python
from src.models.fiat_node import FiatNode

# Create a fiat node
usd_node = FiatNode("Kraken", "USD", 1.0)

# Check if currency is fiat
is_fiat = FiatNode.is_fiat_currency("USD")  # True
is_fiat = FiatNode.is_fiat_currency("USDT")  # False
```

### Graph Building Process

1. **Add stablecoin nodes** (existing functionality)
2. **Add fiat nodes** (new: one per exchange per fiat currency)
3. **Add stablecoin edges** (existing: cross-exchange transfers)
4. **Add conversion edges** (new: stablecoin ↔ fiat on same exchange)
5. **Add fiat transfer edges** (new: fiat between exchanges)

---

## Limitations

1. **Fiat Transfer Times**: Bank transfers can take 1-3 business days in reality, but we model as ~60s for algorithmic purposes
2. **Regulatory Constraints**: Some exchanges may not support fiat trading in all jurisdictions
3. **Liquidity**: Fiat markets may have different liquidity than crypto markets
4. **KYC Requirements**: Fiat trading typically requires identity verification

---

## Future Enhancements

Potential improvements:
1. **Multi-fiat support**: Arbitrage across different fiat currencies (USD → EUR → CAD)
2. **Exchange rate tracking**: Real-time fiat exchange rates
3. **Regional pricing**: Different prices for fiat in different regions
4. **Bank transfer optimization**: Model actual bank transfer times and fees

---

## Summary

✅ **Fiat currency support significantly expands arbitrage opportunities**

- **More paths**: 1.3-2x more edges in the graph
- **Instant conversions**: 0s transfer time for on-exchange conversions
- **Real-world applicability**: Matches how many traders actually operate
- **Lower fees**: Often cheaper than direct crypto transfers

The `FiatEnabledGraphBuilder` handles all of this automatically, making it easy to add fiat support to any arbitrage system!

