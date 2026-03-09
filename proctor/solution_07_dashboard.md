# Proctor Guide — Challenge 7: Dashboard Feature Build

## Solution Code

### Task 1: Dashboard API Endpoint

Add to `qxm/api/routes.py`:

```python
@router.get("/api/dashboard")
async def get_dashboard_data():
    """Aggregate data for the trading dashboard."""
    positions = position_manager.get_all_positions()
    
    # KPIs
    total_pnl = sum(p.unrealised_pnl for p in positions.values())
    
    var_engine = VaREngine()
    portfolio_value = sum(
        p.quantity * p.average_price for p in positions.values()
    )
    portfolio_var = var_engine.calculate(
        portfolio_value=portfolio_value,
        volatility=0.02,
        confidence=0.95,
        horizon_days=1,
    ) if portfolio_value else 0
    
    # Positions
    position_list = []
    for symbol, pos in positions.items():
        current_price = pos.average_price * (1 + pos.unrealised_pnl / (pos.quantity * pos.average_price)) if pos.quantity else pos.average_price
        position_list.append({
            "symbol": symbol,
            "quantity": pos.quantity,
            "avg_price": round(pos.average_price, 2),
            "current_price": round(current_price, 2),
            "pnl": round(pos.unrealised_pnl, 2),
            "pnl_pct": round(
                (pos.unrealised_pnl / (pos.quantity * pos.average_price)) * 100, 2
            ) if pos.quantity and pos.average_price else 0,
        })
    
    # Order book for first instrument
    order_book_data = {"bids": [], "asks": []}
    if matching_engine.books:
        first_book = next(iter(matching_engine.books.values()))
        snapshot = first_book.depth_snapshot(levels=10)
        order_book_data = {
            "bids": [{"price": p, "quantity": q} for p, q in snapshot.get("bids", [])],
            "asks": [{"price": p, "quantity": q} for p, q in snapshot.get("asks", [])],
        }
    
    return {
        "kpis": {
            "total_pnl": round(total_pnl, 2),
            "portfolio_var": round(portfolio_var, 2),
            "active_positions": len(positions),
            "open_orders": sum(
                len(book.asks) + len(book.bids) 
                for book in matching_engine.books.values()
            ) if matching_engine.books else 0,
        },
        "positions": position_list,
        "price_history": {},  # Populated from data store
        "order_book": order_book_data,
    }
```

### Task 2: Static File Serving

Add to `main.py` in `create_app()`:

```python
from fastapi.staticfiles import StaticFiles
import os

def create_app():
    app = FastAPI(title="QuantCore")
    # ... existing setup ...
    
    # Serve dashboard
    dashboard_dir = os.path.join(os.path.dirname(__file__), "dashboard")
    if os.path.isdir(dashboard_dir):
        app.mount("/dashboard", StaticFiles(directory=dashboard_dir, html=True), name="dashboard")
    
    return app
```

### Task 3: JavaScript (dashboard/index.html)

Replace TODO comments with:

```javascript
// Configuration
const API_BASE = window.location.origin;
const REFRESH_INTERVAL = 5000;

// Fetch and render
async function fetchDashboardData() {
    try {
        const response = await fetch(`${API_BASE}/api/dashboard`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();
        updateKPIs(data.kpis);
        updatePositionsTable(data.positions);
        updatePriceChart(data.price_history);
        updateOrderBook(data.order_book);
    } catch (error) {
        console.error('Dashboard fetch error:', error);
    }
}

function updateKPIs(kpis) {
    document.getElementById('total-pnl').textContent = 
        `$${kpis.total_pnl.toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    document.getElementById('portfolio-var').textContent = 
        `$${Math.abs(kpis.portfolio_var).toLocaleString('en-US', {minimumFractionDigits: 2})}`;
    document.getElementById('active-positions').textContent = kpis.active_positions;
    document.getElementById('open-orders').textContent = kpis.open_orders;
    
    // Conditional coloring
    const pnlEl = document.getElementById('total-pnl');
    pnlEl.style.color = kpis.total_pnl >= 0 ? '#00c853' : '#ff1744';
}

function updatePositionsTable(positions) {
    const tbody = document.getElementById('positions-body');
    tbody.innerHTML = positions.map(p => `
        <tr>
            <td>${p.symbol}</td>
            <td>${p.quantity}</td>
            <td>$${p.avg_price.toFixed(2)}</td>
            <td>$${p.current_price.toFixed(2)}</td>
            <td style="color: ${p.pnl >= 0 ? '#00c853' : '#ff1744'}">
                $${p.pnl.toFixed(2)} (${p.pnl_pct.toFixed(2)}%)
            </td>
        </tr>
    `).join('');
}

function updatePriceChart(history) {
    const traces = Object.entries(history).map(([symbol, data]) => ({
        x: data.timestamps,
        y: data.prices,
        type: 'scatter',
        mode: 'lines',
        name: symbol,
    }));
    
    Plotly.react('price-chart', traces, {
        paper_bgcolor: '#1a1a2e',
        plot_bgcolor: '#16213e',
        font: { color: '#e0e0e0' },
        xaxis: { title: 'Time' },
        yaxis: { title: 'Price' },
        margin: { t: 30, r: 30, b: 40, l: 60 },
    });
}

function updateOrderBook(book) {
    const bidPrices = book.bids.map(b => b.price);
    const bidQtys = book.bids.map(b => b.quantity);
    const askPrices = book.asks.map(a => a.price);
    const askQtys = book.asks.map(a => a.quantity);
    
    Plotly.react('order-book-chart', [
        { x: bidPrices, y: bidQtys, type: 'bar', name: 'Bids', marker: { color: '#00c853' } },
        { x: askPrices, y: askQtys, type: 'bar', name: 'Asks', marker: { color: '#ff1744' } },
    ], {
        paper_bgcolor: '#1a1a2e',
        plot_bgcolor: '#16213e',
        font: { color: '#e0e0e0' },
        barmode: 'group',
        xaxis: { title: 'Price' },
        yaxis: { title: 'Quantity' },
        margin: { t: 30, r: 30, b: 40, l: 60 },
    });
}

// Start polling
fetchDashboardData();
setInterval(fetchDashboardData, REFRESH_INTERVAL);
```

## Copilot Prompts That Work Well

### Full feature (Agent Mode):
```
Build a live trading dashboard. The HTML skeleton is in dashboard/index.html 
and the API is in qxm/api/routes.py. Please:
1. Add a GET /api/dashboard endpoint that returns KPIs, positions, 
   price_history, and order_book
2. Update main.py to serve dashboard/ as static files
3. Write JavaScript in index.html to fetch the API, render Plotly charts, 
   and auto-refresh every 5 seconds
```

### Targeted:
```
Add JavaScript to dashboard/index.html that fetches /api/dashboard every 
5 seconds. Update the KPI cards, render a Plotly line chart for prices, 
populate the positions table, and show an order book depth chart.
```

## Common Pitfalls

1. **CORS**: If the dashboard is served from a different origin, attendees need to add CORS middleware. Since we serve from the same FastAPI, this shouldn't be an issue.
2. **Element IDs**: The JavaScript assumes specific element IDs (`total-pnl`, `positions-body`, etc.). Attendees need to check what's in the HTML.
3. **Plotly.react vs Plotly.newPlot**: Use `Plotly.react` for updates (doesn't recreate the chart each time).
4. **Empty data**: The first fetch may return empty positions — JavaScript should handle this gracefully.
5. **Static file mount order**: The `app.mount()` for static files should be AFTER route registration, otherwise it catches all requests.

## Verification

```bash
# Start server
python main.py

# Check API
curl http://localhost:8443/api/dashboard | python -m json.tool

# Open dashboard
open http://localhost:8443/dashboard/
```

Expected result:
- KPI cards show real (or zero) values
- Positions table is populated (if orders were submitted)
- Charts render (even if empty)
- Page auto-refreshes every 5 seconds

## What "Done" Looks Like

Show attendees a screenshot or live demo of the working dashboard. The key takeaway is that Copilot can coordinate changes across Python backend and JavaScript frontend in a single Agent Mode conversation.
