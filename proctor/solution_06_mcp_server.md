# Proctor Guide — Challenge 6: MCP Server Extension

## Solution Code

### Tool 1: `calculate_portfolio_var`

Add to `qxm/mcp_server/server.py`:

```python
@mcp.tool()
async def calculate_portfolio_var(
    confidence_level: float = 0.95,
    time_horizon_days: int = 1,
    method: str = "parametric",
) -> str:
    """Calculate Value at Risk for the current portfolio.
    
    Args:
        confidence_level: Confidence level (0.90, 0.95, 0.99)
        time_horizon_days: Time horizon in trading days
        method: VaR method - 'parametric', 'historical', or 'conditional'
    """
    from qxm.risk.var import VaREngine
    
    engine = VaREngine()
    
    # Get portfolio positions and compute values
    positions = position_manager.get_all_positions()
    if not positions:
        return json.dumps({"error": "No positions in portfolio"})
    
    portfolio_value = sum(
        p.quantity * p.average_price for p in positions.values()
    )
    
    # Estimate portfolio volatility (simplified)
    daily_vol = 0.02  # Default; in production, compute from returns
    
    var_value = engine.calculate(
        portfolio_value=portfolio_value,
        volatility=daily_vol,
        confidence=confidence_level,
        horizon_days=time_horizon_days,
        method=method,
    )
    
    result = {
        "var_value": round(var_value, 2),
        "confidence_level": confidence_level,
        "time_horizon_days": time_horizon_days,
        "method": method,
        "portfolio_value": round(portfolio_value, 2),
        "var_percentage": round(abs(var_value / portfolio_value) * 100, 2) if portfolio_value else 0,
    }
    return json.dumps(result, indent=2)
```

### Tool 2: `price_option`

```python
@mcp.tool()
async def price_option(
    spot_price: float,
    strike_price: float,
    time_to_expiry: float,
    risk_free_rate: float,
    volatility: float,
    option_type: str = "call",
) -> str:
    """Price an option using Black-Scholes-Merton and return Greeks.
    
    Args:
        spot_price: Current price of the underlying
        strike_price: Strike price of the option
        time_to_expiry: Time to expiry in years
        risk_free_rate: Risk-free interest rate (e.g. 0.05 for 5%)
        volatility: Implied volatility (e.g. 0.20 for 20%)
        option_type: 'call' or 'put'
    """
    from qxm.risk.greeks import OptionPricer
    
    pricer = OptionPricer(
        S=spot_price,
        K=strike_price,
        T=time_to_expiry,
        r=risk_free_rate,
        sigma=volatility,
        option_type=option_type,
    )
    
    result = {
        "price": round(pricer.price, 4),
        "greeks": {
            "delta": round(pricer.delta, 6),
            "gamma": round(pricer.gamma, 6),
            "theta": round(pricer.theta, 6),
            "vega": round(pricer.vega, 6),
            "rho": round(pricer.rho, 6),
        },
        "inputs": {
            "spot_price": spot_price,
            "strike_price": strike_price,
            "time_to_expiry": time_to_expiry,
            "risk_free_rate": risk_free_rate,
            "volatility": volatility,
            "option_type": option_type,
        },
    }
    return json.dumps(result, indent=2)
```

### Tool 3: `get_strategy_signals`

```python
@mcp.tool()
async def get_strategy_signals(
    symbol: str,
    strategy_name: str | None = None,
) -> str:
    """List registered strategies and their current signals for a symbol.
    
    Args:
        symbol: Instrument symbol (e.g. 'AAPL')
        strategy_name: Optional filter for a specific strategy
    """
    from qxm.strategy.base import StrategyMeta
    
    registry = StrategyMeta._registry
    signals = []
    
    for name, strategy_cls in registry.items():
        if strategy_name and name != strategy_name:
            continue
        
        try:
            strategy = strategy_cls()
            signal = strategy.evaluate(symbol)
            if signal:
                signals.append({
                    "strategy": name,
                    "signal": signal.direction.value,
                    "strength": signal.strength.value,
                    "metadata": signal.metadata or {},
                })
        except Exception as e:
            signals.append({
                "strategy": name,
                "signal": "ERROR",
                "error": str(e),
            })
    
    result = {
        "symbol": symbol,
        "strategies_checked": len(registry),
        "signals": signals,
    }
    return json.dumps(result, indent=2)
```

## MCP Server Configuration

### `.vscode/mcp.json`

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

## Copilot Prompts That Work Well

### Understanding the pattern:
```
Explain the MCP server in qxm/mcp_server/server.py. How are tools registered 
and what pattern should I follow to add new tools?
```

### Generating tools:
```
Add an MCP tool called 'calculate_portfolio_var' to qxm/mcp_server/server.py. 
It should accept confidence_level (float), time_horizon_days (int), and method 
(string). Use the VaREngine from qxm/risk/var.py. Follow the same decorator 
pattern as existing tools.
```

### Testing guidance:
```
How do I test this MCP server locally? Show me how to start it and verify 
the tools are registered.
```

## Common Pitfalls

1. **Import paths**: Attendees may import from wrong modules — ensure they use `qxm.risk.var`, `qxm.risk.greeks`, `qxm.strategy.base`
2. **Async/sync mismatch**: MCP tools are async but the underlying risk/strategy code is sync — wrapping in `asyncio.to_thread()` is optional but good practice for CPU-bound work
3. **JSON serialisation**: Return values must be JSON-serialisable strings — `Decimal`, `numpy` types need conversion
4. **Strategy instantiation**: `StrategyMeta._registry` contains classes, not instances — attendees need to instantiate them
5. **Error handling**: Tools should return error messages as JSON, not raise exceptions

## Verification

```bash
# Verify server loads with all 11 tools
python -c "
from qxm.mcp_server.server import mcp
tools = mcp.list_tools()
print(f'Total tools: {len(tools)}')
for t in tools:
    print(f'  - {t.name}')
assert len(tools) >= 11, f'Expected 11+ tools, got {len(tools)}'
print('✓ All tools registered')
"

# Test individual tools (if the server supports direct invocation)
python -c "
import asyncio
from qxm.mcp_server.server import price_option
result = asyncio.run(price_option(100, 100, 1.0, 0.05, 0.2, 'call'))
print(result)
"
```
