# Challenge 6 — MCP Server Extension

## Objective

Extend the existing MCP (Model Context Protocol) server with new tools that provide real-time analytics. This challenge teaches you to build and test MCP servers — a key integration pattern for AI-powered development.

## Recommended Model

**Claude Sonnet 4** in **Agent Mode** — Best for understanding the MCP protocol and generating well-structured tool implementations.

## Background

QuantCore already has an MCP server in `qxm/mcp_server/server.py` with 8 tools. Your job is to add **3 new tools** that provide advanced analytics via the MCP protocol.

## Understanding the Existing Server

Before adding tools, explore the existing MCP server:

1. Open `qxm/mcp_server/server.py`
2. Ask Copilot: "Explain how this MCP server works. What tools does it expose and what protocol does it use?"
3. Understand the pattern: each tool is a function decorated to register with the MCP framework

## New Tools to Implement

### Tool 1: `calculate_portfolio_var`

Calculate Value at Risk for the current portfolio.

**Inputs:**
- `confidence_level` (float): Confidence level (e.g. 0.95, 0.99)
- `time_horizon_days` (int): Number of days (e.g. 1, 10)
- `method` (string): "parametric", "historical", or "conditional"

**Expected Output:**
```json
{
  "var_value": 125000.50,
  "confidence_level": 0.95,
  "time_horizon_days": 1,
  "method": "parametric",
  "portfolio_value": 5000000.00,
  "var_percentage": 2.5
}
```

**Hint**: Use `qxm/risk/var.py` — the `VaREngine` class.

### Tool 2: `price_option`

Price an option using the Black-Scholes-Merton model and return Greeks.

**Inputs:**
- `spot_price` (float)
- `strike_price` (float)
- `time_to_expiry` (float): In years
- `risk_free_rate` (float)
- `volatility` (float)
- `option_type` (string): "call" or "put"

**Expected Output:**
```json
{
  "price": 8.72,
  "greeks": {
    "delta": 0.62,
    "gamma": 0.019,
    "theta": -0.045,
    "vega": 0.358,
    "rho": 0.041
  },
  "inputs": { ... }
}
```

**Hint**: Use `qxm/risk/greeks.py` — the `OptionPricer` class.

### Tool 3: `get_strategy_signals`

List all registered strategies and their current signals.

**Inputs:**
- `symbol` (string): Instrument symbol
- `strategy_name` (string, optional): Filter to a specific strategy

**Expected Output:**
```json
{
  "symbol": "AAPL",
  "signals": [
    {
      "strategy": "MomentumBreakout",
      "signal": "BUY",
      "strength": "STRONG",
      "metadata": { "channel_high": 155.0 }
    }
  ]
}
```

**Hint**: Use `qxm/strategy/base.py` — the `StrategyMeta._registry`.

## How to Use Copilot

### Step 1: Understand the Pattern

Ask Copilot to explain the existing MCP server:

> "Explain the structure of qxm/mcp_server/server.py. How are tools registered? What pattern should I follow to add new tools?"

### Step 2: Generate Tool Code

For each tool:

> "Add a new MCP tool called 'calculate_portfolio_var' to the server. It should accept confidence_level (float), time_horizon_days (int), and method (string). Use the VaREngine from qxm/risk/var.py to compute the result. Follow the same pattern as existing tools."

### Step 3: Test the Server

```bash
# Start the MCP server
python -m qxm.mcp_server.server

# In another terminal, test using the MCP inspector (if available)
# Or test by importing directly:
python -c "
import asyncio
from qxm.mcp_server.server import mcp
print('Server tools:', [t.name for t in mcp.list_tools()])
"
```

## Configuring the MCP Server in VS Code

To use your MCP server with GitHub Copilot:

1. Create `.vscode/mcp.json`:
```json
{
  "servers": {
    "quantcore": {
      "command": "python",
      "args": ["-m", "qxm.mcp_server.server"],
      "cwd": "${workspaceFolder}"
    }
  }
}
```

2. Restart VS Code
3. In Copilot Chat, you should see the QuantCore tools available as MCP tools

## Verification

After implementing all 3 tools:

```bash
# Verify the server starts without errors
python -c "from qxm.mcp_server.server import mcp; print('Server loaded OK')"

# Count the tools (should be 11 = 8 original + 3 new)
python -c "
from qxm.mcp_server.server import mcp
tools = mcp.list_tools()
print(f'Total tools: {len(tools)}')
for t in tools:
    print(f'  - {t.name}')
"
```

## Stretch Goals

- Add a **`run_backtest`** MCP tool that runs a strategy against historical data and returns performance metrics
- Add **input validation** with clear error messages for all tool parameters
- Create a **`get_market_data`** tool that returns recent tick data for a given symbol
- Write **unit tests** for each new MCP tool
- Add **tool descriptions** rich enough that Copilot can intelligently choose when to call each tool

## Time

~60 minutes

---

*Next: [Challenge 7 — Dashboard Feature Build](./challenge_07_dashboard.md)*
