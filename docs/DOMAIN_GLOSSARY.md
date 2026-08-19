# Domain glossary - QuantCore

QuantCore is a teaching simulation. Familiar public symbols may appear, but all
prices, orders, positions, events, and scenarios are synthetic. Nothing in this
repository is investment advice.

Domain knowledge is not assessed in the workshop. The normative rules and worked
numbers are in
[the business invariants](../challenges/reference/invariants.md); this glossary
explains the vocabulary.

## Orders and market microstructure

| Term | Meaning in QuantCore |
|---|---|
| **Instrument** | A simulated tradeable definition: symbol, type, tick size, lot size, currency, exchange, and optional option metadata. |
| **Order book** | Outstanding bids and asks for one symbol. Bids sort highest first; asks sort lowest first. |
| **Bid / ask** | A bid is an order to buy; an ask (offer) is an order to sell. |
| **Best bid / best ask** | The highest resting bid and lowest resting ask. |
| **Spread** | `best ask - best bid`. It is absent when either side is empty. |
| **Depth** | Aggregated resting quantity and order count at each price level. |
| **Price-time priority** | Better price wins first. At one price, earlier arrival wins (FIFO). |
| **Maker / resting order** | The order already on the book. QuantCore executions use the maker's price. |
| **Aggressor / incoming order** | The order that crosses resting liquidity and causes an execution. |
| **Market order** | An order to execute against available liquidity without setting a limit price. Any unfilled remainder is cancelled. |
| **Limit order** | An order with a maximum buy price or minimum sell price. A GTC remainder may rest on the book. |
| **Fill / trade** | One execution between a buy and a sell. A single order can produce several trades. |
| **Partial fill** | An order has executed some, but not all, of its quantity. |
| **Tick size** | The permitted price increment, such as `0.01`. |
| **Lot size** | The permitted quantity increment, such as `1` share or `0.001` BTC. |

## Order lifecycle

| Term | Meaning in QuantCore |
|---|---|
| **Side** | `BUY` or `SELL`. Buys add signed quantity; sells subtract it. |
| **GTC** | Good Till Cancelled. An unfilled LIMIT remainder may rest until cancelled. |
| **IOC** | Immediate Or Cancel. Execute available quantity now and cancel any remainder. |
| **FOK** | Fill Or Kill. Execute the complete quantity immediately or cancel without consuming liquidity. |
| **DAY / GTD** | Represented in the domain enum but rejected by the engine because no trading-session calendar or expiry scheduler exists. |
| **STOP / STOP_LIMIT** | Represented in the domain enum but rejected because no trigger subsystem exists. |
| **NEW** | Constructed but not yet processed by the matching engine. |
| **ACCEPTED** | Accepted and resting without a fill. |
| **PARTIALLY_FILLED** | Some quantity executed and an active remainder still rests. |
| **FILLED** | All quantity executed; terminal. |
| **CANCELLED** | Explicitly cancelled or ended with an unfilled IOC/FOK/market remainder; terminal. |
| **REJECTED** | Failed a boundary, instrument, order-type, time-in-force, or risk rule; terminal. |
| **EXPIRED** | Terminal status reserved for expiry-capable subsystems. |
| **Order ID reservation** | The first submission attempt permanently reserves its ID, including a rejected attempt. A reuse is a duplicate conflict. |

## Positions and P&L

| Term | Meaning in QuantCore |
|---|---|
| **Position** | A client-and-symbol holding. Positive quantity is long; negative quantity is short. |
| **Average entry price** | Volume-weighted entry price. It changes when exposure increases, not when exposure is reduced. Field: `average_entry_price`. |
| **Realized P&L** | Profit or loss crystallised by reducing/closing exposure. Field: `realized_pnl`. |
| **Unrealized P&L** | Mark-to-market result for open exposure: `(last_price - average_entry_price) * quantity`. Field: `unrealized_pnl`. |
| **Market value** | `quantity * last_price`; negative for a short position. |
| **Gross exposure** | Sum of absolute market values. Risk sizing uses this so a short-only portfolio is not treated as zero exposure. |
| **Netting** | Opposing quantities in the same client/symbol position offset each other while preserving the value and P&L history required by the position rules. |

## Risk analytics

All VaR-family outputs in QuantCore are **non-negative loss magnitudes**. A
negative VaR is a defect.

| Term | Meaning in QuantCore |
|---|---|
| **VaR (Value at Risk)** | A loss threshold at a confidence level and horizon. A one-day 95% VaR of `100` means the model estimates a 5% tail beyond a loss of `100`; it does not mean losses are capped at `100`. |
| **Parametric VaR** | Normal-assumption estimate using portfolio exposure, daily volatility, a normal quantile, and square-root-of-time scaling. |
| **Historical VaR** | An observed loss quantile from a supplied P&L series. |
| **CVaR / Expected Shortfall** | Mean loss at or beyond the historical VaR threshold; it is greater than or equal to VaR for the same sample/confidence. |
| **Confidence level** | Probability mass below the reported loss threshold, commonly 95% or 99%. |
| **Holding period** | Number of days in the risk horizon. Parametric risk scales with `sqrt(days)`. |
| **Stress test** | Reprices positions under explicit percentage shocks. Shocks below -100% are invalid. |
| **PSD covariance** | A covariance matrix must be positive semidefinite; otherwise it cannot describe a valid portfolio variance. |

## Options and Greeks

| Term | Meaning in QuantCore |
|---|---|
| **Call / put** | A call is the right to buy at the strike; a put is the right to sell. |
| **Strike / expiry** | Exercise price and final contract date. |
| **BSM** | Black-Scholes-Merton option pricing under the simplified assumptions used by the workshop. |
| **Delta** | Price sensitivity to the underlying. Call delta is in `[0, 1]`; put delta in `[-1, 0]`. |
| **Gamma** | Sensitivity of delta to the underlying price. |
| **Theta** | Time-decay sensitivity, reported per calendar day here. |
| **Vega** | Volatility sensitivity, reported per one percentage-point move here. |
| **Rho** | Interest-rate sensitivity, reported per one percentage-point move here. |
| **Put-call parity** | `call - put = spot - strike * exp(-rate * time)`. |
| **Implied volatility** | Volatility inferred from an option price by bounded root finding. |
| **Cached Greek** | A descriptor-cached Greek that is invalidated when the option parameter hash changes. |

## Data, time, and presentation

| Term | Meaning in QuantCore |
|---|---|
| **Tick** | One simulated market observation: bid, ask, last, volume, and aware-UTC timestamp. |
| **GBM** | Seedable geometric Brownian motion used to generate deterministic workshop feeds. |
| **OHLC** | Open, high, low, close bar derived separately per symbol and interval. |
| **VWAP / TWAP** | Volume-weighted / time-weighted average price. |
| **Aware UTC** | A timestamp with an offset, normalized to UTC. Persisted and exchanged timestamps must be aware UTC. |
| **Naive timestamp** | A timestamp without timezone information. External domain/store inputs reject it. |
| **Europe/Berlin** | Presentation timezone. It applies CET/CEST from timezone data; code never adds a fixed offset. |
| **Local business day** | Half-open interval `[00:00, next 00:00)` in Europe/Berlin, converted to UTC. It can contain 23, 24, or 25 hours. |
| **Decimal comma** | Human-facing `de-DE` display such as `1.234,56`. JSON, Python, YAML, and SQL continue to use `1234.56`. |
| **Currency basis** | Instrument payloads carry EUR or USD. QuantCore has no FX conversion service; never add unlike currencies or relabel an amount as converted without saying so. |

## Platform and governance

| Term | Meaning in QuantCore |
|---|---|
| **Event sourcing** | Domain events are appended to a bounded `EventLog` and can be replayed by sequence/time/type. |
| **API key principal** | `X-API-Key` resolves to a client ID and permissions. The order body cannot override that identity. |
| **HMAC** | SHA-256 keyed digest used for key storage and canonical request signatures; comparisons are timing-safe. |
| **Replay window** | Allowed age/future skew for a signed timestamp. Timestamp `0` is data, not a missing value. |
| **MCP** | Model Context Protocol. The local SDK v2 server exposes bounded structured tools; its default surface is read-only and simulation-only. |
| **Tool annotation** | Read/write/destructive/idempotent/open-world metadata shown to an MCP client. It communicates intent but is not authorization. |
| **Least privilege** | Offer only the tools, data, file access, and network access required for the task. MCP/server configuration and client approval are separate controls. |
| **Four-eyes principle** | `Vier-Augen-Prinzip`: generated changes still require competent human review. |
| **Traceability** | `Nachvollziehbarkeit`: retain the task, evidence, checks, review decision, and uncertainty without collecting unnecessary personal data. |
