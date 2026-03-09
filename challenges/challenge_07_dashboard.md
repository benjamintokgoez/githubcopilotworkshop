# Challenge 7 — Dashboard Feature Build

## Objective

Wire the pre-built HTML dashboard to the QuantCore API, creating a live trading dashboard that visualises positions, risk metrics, and the order book. This is the capstone challenge — attendees leave with a visible, working product.

## Recommended Model

**GPT-4o** in **Agent Mode** — Best for full-stack feature work spanning HTML, JavaScript, and Python API integration.

## Background

A designer has delivered `dashboard/index.html` — a dark-themed dashboard skeleton with Plotly.js charts and placeholder elements. Your job is to:

1. Add a `/api/dashboard` endpoint that aggregates data for the frontend
2. Serve the dashboard as a static file from FastAPI
3. Write JavaScript to fetch data and render live charts

## Exploring the Dashboard

Open `dashboard/index.html` in a browser to see the skeleton. Notice:
- KPI cards (P&L, VaR, Positions, Alerts) — currently showing placeholder values
- Price chart area — empty
- Positions table — empty
- Order book visualisation — empty
- TODO comments marking where code needs to go

## Tasks

### Task 1: Dashboard API Endpoint

Add a new endpoint to `qxm/api/routes.py`:

```
GET /api/dashboard
```

Response format:
```json
{
  "kpis": {
    "total_pnl": 12500.00,
    "portfolio_var": 45000.00,
    "active_positions": 5,
    "open_orders": 12
  },
  "positions": [
    {
      "symbol": "AAPL",
      "quantity": 100,
      "avg_price": 150.25,
      "current_price": 155.00,
      "pnl": 475.00,
      "pnl_pct": 3.16
    }
  ],
  "price_history": {
    "AAPL": {
      "timestamps": ["2024-01-01T09:30:00", ...],
      "prices": [150.0, 150.5, ...]
    }
  },
  "order_book": {
    "bids": [{"price": 154.90, "quantity": 500}, ...],
    "asks": [{"price": 155.10, "quantity": 300}, ...]
  }
}
```

Ask Copilot:
> "Create a GET /api/dashboard endpoint in routes.py that aggregates data from the PositionManager, OrderBook, and RiskMetrics to serve the dashboard. Return KPIs, positions, price history, and order book data."

### Task 2: Static File Serving

Update `main.py` to serve the dashboard:

```python
from fastapi.staticfiles import StaticFiles

app.mount("/dashboard", StaticFiles(directory="dashboard", html=True), name="dashboard")
```

Ask Copilot:
> "Modify main.py to serve the dashboard/index.html as a static file at the /dashboard route."

### Task 3: JavaScript — Fetch & Render

In `dashboard/index.html`, replace the TODO comments with working JavaScript:

1. **KPI Cards**: Fetch `/api/dashboard` and update the KPI card values
2. **Price Chart**: Use Plotly.js to render a candlestick or line chart from `price_history`
3. **Positions Table**: Populate the table with live position data
4. **Order Book**: Render a depth chart showing bids and asks
5. **Auto-Refresh**: Poll the API every 5 seconds

Ask Copilot:
> "Write JavaScript for dashboard/index.html that fetches /api/dashboard every 5 seconds and updates:
> 1. The KPI cards with total P&L, VaR, position count, and order count
> 2. A Plotly line chart with price history
> 3. The positions table with current positions
> 4. An order book depth visualisation
> Use the existing Plotly.js library already loaded in the page."

### Task 4: Styling Polish

The basic CSS is in place but there are improvements to make:
- Add conditional colouring: green for positive P&L, red for negative
- Add loading spinners while data is being fetched
- Animate KPI value changes

## How to Use Copilot

This challenge benefits most from **Agent Mode** since it requires coordinated changes across Python and HTML files:

> "I need to build a live trading dashboard. The HTML skeleton is in dashboard/index.html and the API is in qxm/api/routes.py. Please:
> 1. Add a /api/dashboard endpoint that returns KPIs, positions, price history, and order book data
> 2. Update main.py to serve the dashboard directory as static files
> 3. Write JavaScript in index.html to fetch the API and render the data with Plotly charts
> 4. Add auto-refresh every 5 seconds"

## Verification

```bash
# Start the server
python main.py

# Open the dashboard in a browser
open http://localhost:8443/dashboard/

# Verify API endpoint
curl http://localhost:8443/api/dashboard | python -m json.tool
```

You should see:
- KPI cards with real values
- A chart rendering price data
- A table showing positions
- An order book depth chart
- Values updating every 5 seconds

## Stretch Goals

- Add **WebSocket** support so the dashboard updates in real-time instead of polling
- Add a **trade submission form** to the dashboard that POSTs to `/api/orders`
- Implement **dark/light theme toggle** with CSS variables
- Add **alert banners** that trigger when VaR exceeds a threshold
- Create a **strategy performance panel** showing backtest results from the MomentumBreakout and BollingerMeanReversion strategies

## Time

~75 minutes

---

*Congratulations — you've completed the QuantCore workshop! 🎉*

*Return to the [Workshop README](../README.md) for wrap-up instructions.*
