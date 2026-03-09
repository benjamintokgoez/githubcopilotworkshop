# Domain Glossary — Quantitative Trading

## Market Microstructure

| Term | Definition |
|------|-----------|
| **Order Book** | A record of all outstanding buy (bid) and sell (ask) orders for an instrument, organised by price level |
| **Bid** | An order to buy at a specified price; the bid side is sorted highest-first |
| **Ask (Offer)** | An order to sell at a specified price; the ask side is sorted lowest-first |
| **Spread** | The difference between the best ask and best bid price |
| **Depth** | The total quantity available at each price level in the order book |
| **FIFO** | First In, First Out — orders at the same price level are matched in the order they were submitted |
| **Market Order** | An order to buy/sell immediately at the best available price |
| **Limit Order** | An order to buy/sell at a specified price or better |
| **Fill** | The execution of an order (fully or partially) |
| **Resting Order** | An order sitting in the order book waiting to be matched |
| **Tick** | The smallest price increment for an instrument (e.g., $0.01 for equities) |
| **Lot Size** | The minimum quantity increment for an instrument |

## Order Properties

| Term | Definition |
|------|-----------|
| **Side** | BUY or SELL |
| **Time-in-Force (TIF)** | How long an order remains active: GTC (Good Till Cancelled), IOC (Immediate or Cancel), FOK (Fill or Kill), DAY |
| **Quantity** | Number of units to trade |
| **Remaining Quantity** | Unfilled portion of a partially filled order |
| **Client ID** | Identifier for the client who submitted the order |

## Risk Management

| Term | Definition |
|------|-----------|
| **VaR (Value at Risk)** | The maximum potential loss at a given confidence level over a time horizon. E.g., "95% 1-day VaR of $100K" means there's a 5% chance of losing more than $100K in one day |
| **Parametric VaR** | VaR calculated assuming returns follow a normal distribution: $VaR = \mu + z_{1-\alpha} \cdot \sigma \cdot \sqrt{t}$ |
| **Historical VaR** | VaR calculated from the actual historical return distribution |
| **CVaR (Conditional VaR)** | Also called Expected Shortfall — the average loss given that the loss exceeds VaR |
| **Confidence Level** | The probability that the actual loss will not exceed VaR (e.g., 95%, 99%) |
| **Stress Test** | Applying extreme market scenarios to evaluate portfolio impact |

## Options & Greeks

| Term | Definition |
|------|-----------|
| **Call Option** | The right (not obligation) to buy an asset at the strike price |
| **Put Option** | The right (not obligation) to sell an asset at the strike price |
| **Strike Price** | The price at which an option can be exercised |
| **Expiry** | The date when the option contract expires |
| **Premium** | The price paid for the option contract |
| **Implied Volatility (IV)** | The market's expectation of future volatility, derived from option prices |
| **BSM (Black-Scholes-Merton)** | The standard option pricing model: $C = SN(d_1) - Ke^{-rT}N(d_2)$ |
| **Delta ($\Delta$)** | Rate of change of option price with respect to underlying price. Call: $N(d_1)$, Put: $N(d_1) - 1$ |
| **Gamma ($\Gamma$)** | Rate of change of delta with respect to underlying price |
| **Theta ($\Theta$)** | Rate of change of option price with respect to time (time decay) |
| **Vega ($\nu$)** | Rate of change of option price with respect to volatility |
| **Rho ($\rho$)** | Rate of change of option price with respect to the risk-free rate |
| **Put-Call Parity** | $C - P = S - Ke^{-rT}$ — fundamental relationship between call and put prices |

## Portfolio Analytics

| Term | Definition |
|------|-----------|
| **Position** | A holding in an instrument (long = positive quantity, short = negative) |
| **P&L (Profit & Loss)** | Realised: from closed trades. Unrealised: from open positions at current market price |
| **Sharpe Ratio** | Risk-adjusted return: $\frac{R_p - R_f}{\sigma_p}$ where $R_p$ is portfolio return, $R_f$ is risk-free rate, $\sigma_p$ is portfolio volatility |
| **Max Drawdown** | Largest peak-to-trough decline in portfolio value |
| **VWAP** | Volume Weighted Average Price — average price weighted by volume at each level |
| **TWAP** | Time Weighted Average Price — average price over equal time intervals |
| **OHLC** | Open, High, Low, Close — standard bar representation for a time period |

## Data & Simulation

| Term | Definition |
|------|-----------|
| **GBM (Geometric Brownian Motion)** | A stochastic process used to simulate asset prices: $dS = \mu S \, dt + \sigma S \, dW$ |
| **Drift ($\mu$)** | Expected return rate in the GBM model |
| **Volatility ($\sigma$)** | Standard deviation of returns; measures price uncertainty |
| **EMA (Exponential Moving Average)** | A weighted moving average giving more weight to recent prices |
| **Bollinger Bands** | A volatility indicator: middle band ± k standard deviations |
| **Donchian Channel** | Highest high and lowest low over a lookback period |
| **Z-Score** | Number of standard deviations from the mean: $z = \frac{x - \mu}{\sigma}$ |

## Strategy Types

| Term | Definition |
|------|-----------|
| **Momentum** | Buy assets that are rising, sell assets that are falling |
| **Mean Reversion** | Buy assets that have fallen below their historical average, expecting a return to the mean |
| **Statistical Arbitrage** | Trading correlated pairs when their price relationship deviates from the historical norm |
| **Signal** | A trading recommendation (BUY/SELL) with a strength indicator |

## Infrastructure

| Term | Definition |
|------|-----------|
| **MCP (Model Context Protocol)** | A protocol for AI assistants to interact with external tools and services |
| **Event Sourcing** | Storing all state changes as an append-only sequence of events |
| **HMAC** | Hash-based Message Authentication Code — used for request signing |
| **Replay Protection** | Preventing replay attacks by validating request timestamps |
