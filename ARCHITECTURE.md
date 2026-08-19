# QuantCore architecture

## Purpose

QuantCore (`qxm`) is a deterministic educational trading simulation and the
technical substrate for a supervised GitHub Copilot workshop. It gives attendees
a realistic system for incident response, migration, review, least-privilege
tooling, and handover practice.

It is deliberately not a production exchange, broker, risk platform, or market
data service. Familiar public symbols are reference data; every price, order,
position, event, and scenario is simulated.

## Runtime view

```text
                                  same-origin browser
                               +-----------------------+
                               | dashboard/index.html  |
                               +-----------+-----------+
                                           |
                                           | HTTP + X-API-Key
                                           v
+----------------+        +---------------------------------------------+
| REST clients   +------->| FastAPI application (main.py, qxm/api/)     |
+----------------+        |                                             |
                          | middleware -> identity/permission -> routes  |
                          |                    |                        |
                          |               TradingService                |
                          +----------+----------+-------------+----------+
                                     |                        |
                                     v                        v
                          +--------------------+    +--------------------+
                          | MatchingEngine     |    | TimeSeriesStore    |
                          | OrderBook          |    | SQLite/SQLAlchemy  |
                          | PositionManager    |    | instruments/trades |
                          | EventBus/EventLog  |    +--------------------+
                          +---------+----------+
                                    ^
                                    | marks
                          +---------+----------+
                          | simulated feed     |
                          | (aware UTC ticks)  |
                          +--------------------+

+--------------------+       injected isolated engine/instruments
| MCP v2 client      +----------------------------------------------+
+---------+----------+                                              |
          | stdio                                                   v
          +--------------------------------------------->+----------------------+
                                                        | MCPServer factory    |
                                                        | read-only by default |
                                                        +----------------------+
```

The REST application and the default MCP process create separate in-memory
matching engines. They do not silently share orders or positions. A caller can
inject an engine into `create_mcp_server()` when an explicit integration needs
shared local state.

## Core domain (`qxm/core/`)

### Models

`qxm/core/models.py` uses Pydantic v2 and `Decimal` at financial boundaries.

- `Instrument`: symbol, instrument type, tick/lot sizes, currency/exchange, and
  optional option metadata.
- `Order`: side, type, quantity, prices, time-in-force, lifecycle state, fills,
  client identity, and aware-UTC timestamps.
- `Trade`: maker-price execution with buyer/seller order and client IDs.
- `Position`: signed quantity, average entry price, realized/unrealized P&L, and
  latest mark.
- `PortfolioSnapshot` and `RiskMetrics`: typed reporting models.
- `Tick`: a slot-based immutable-style market observation for low overhead.

External timestamps reject naive values and normalize aware offsets to UTC.
Symbols/currencies are normalized at validation boundaries. JSON-facing Decimal
values are serialized without conversion through binary float.

### Order book

`qxm/core/book.py` implements price-time priority:

- bids use negated keys in `SortedDict`, yielding highest price first;
- asks use natural ascending keys;
- each price level owns a FIFO `deque`;
- snapshots aggregate quantity and order count by level;
- removal/cancellation keeps the price index and order lookup coherent.

### Matching engine

`MatchingEngine` is constructed with an `EventBus`, instrument map, and optional
structurally typed `PreTradeRiskCheck`.

```python
submission = await engine.submit_order(order)
cancelled = await engine.cancel_order(order_id, symbol=None)
```

The engine reserves an order ID synchronously before its first `await`, so two
concurrent submissions cannot both pass the duplicate check. Every attempted ID,
including a rejected one, remains reserved.

The matching rules are:

- best price, then FIFO at that price;
- the resting maker's price is the execution price;
- LIMIT and MARKET are supported;
- GTC, IOC, and FOK are supported;
- an unfilled IOC or MARKET remainder is cancelled;
- an unfillable FOK is accepted then cancelled without touching liquidity;
- STOP/STOP_LIMIT and DAY/GTD are rejected because trigger/session subsystems do
  not exist.

Every fill updates both orders, creates one `Trade`, updates both clients'
positions, and emits lifecycle/trade events. Resting maker state changes are
published as well as incoming-order changes.

### Events

`qxm/core/events.py` contains:

- `DomainEvent`: frozen, aware-UTC event with source, correlation ID, and payload;
- `EventLog`: bounded append-only sequence with replay filters;
- `EventBus`: callbacks and async-generator streams, bounded subscriber queues,
  collision-safe subscriber IDs, and explicit async start/stop.

The event log is an in-process educational audit trail, not a durable production
event store.

## Risk (`qxm/risk/`)

`qxm/risk/var.py` reports VaR and CVaR as **non-negative loss magnitudes**.
Parametric VaR uses square-root-of-time scaling; historical VaR uses an observed
order statistic; CVaR averages tail losses. Inputs are finite and bounded, empty
portfolio facades return zero, short-only books use gross exposure, covariance
matrices must be positive semidefinite, and stress shocks below -100% are
rejected.

`qxm/risk/greeks.py` implements Black-Scholes-Merton call/put prices, delta,
gamma, theta, vega, rho, and bounded implied-volatility solving. `CachedGreek` is
a descriptor cache invalidated by the option parameter hash. Workshop conventions
quote theta per calendar day and vega/rho per one percentage point.

`qxm/risk/portfolio.py` can read positions from a provider so API analytics follow
the engine. `+`, `-`, and `*` return new portfolios, preserve value/P&L through
netting, and never mutate their operands.

## Market data and persistence (`qxm/data/`)

### Feed

`GBMSimulator` and `MarketDataFeed` are seedable and offline. The application
passes the bounded integer seed from `settings.yaml` (default `7`) so local runs
are reproducible. The FastAPI lifespan starts the feed, consumes each tick,
publishes its event, and marks open positions at `tick.last`. Unexpected feed
completion/failure is supervised, logged, and reflected as degraded liveness.

`WebSocketFeedAdapter` is an optional reconnecting adapter. It validates subscribed
symbols and aware timestamps and stops without turning a disconnect into a busy
loop. Live network data is not part of the workshop critical path.

### Transforms

`qxm/data/transform.py` supplies symbol-separated OHLC resampling, VWAP, TWAP,
returns, volatility, normalization, rolling statistics, and exponential moving
averages. Empty/invalid windows and non-finite inputs fail explicitly.

### Store

`TimeSeriesStore` uses SQLAlchemy 2 typed mappings and short-lived transactions.
SQLite is the local default, including a `StaticPool` configuration for
thread-compatible in-memory tests.

- `DecimalText` stores exact finite decimal text rather than binary float.
- `UTCDateTime` rejects naive binds, normalizes to UTC, and restores UTC after a
  SQLite round trip.
- Instrument search escapes `LIKE` wildcards and uses bound parameters.
- Tick, OHLC, trade, and instrument query limits are bounded.
- Batch trade insertion validates every row before one atomic transaction.

The API persists all trades from an incoming submission after matching. That is a
documented non-atomic boundary: an engine execution cannot be rolled back if the
database write fails. The API therefore returns an explicit reconciliation error
that states the real order/fill state and tells the caller not to resubmit.
High-frequency generated ticks are intentionally not persisted by the app.

## Strategies (`qxm/strategy/`)

`StrategyMeta` registers concrete `BaseStrategy` subclasses automatically. The
included strategies are momentum breakout, EMA crossover, Bollinger mean
reversion, and statistical arbitrage. Parameter models reject bool-as-int and
fractional integer settings. Signals carry aware-UTC timestamps, bounded strength,
and metadata. Strategy order creation validates the configured symbol and infers
LIMIT versus MARKET coherently; the engine remains the authority for tick/lot
rules.

Strategies generate simulated decisions only. The application does not
automatically route strategy signals into orders.

## Authentication and REST API (`qxm/auth/`, `qxm/api/`, `main.py`)

### Authentication

`KeyManager` creates high-entropy raw keys, stores only keyed HMAC-SHA256 digests,
uses `hmac.compare_digest`, and supports expiry, revocation, rotation, permission
sets, and safe metadata. Raw keys are returned only at creation/registration and
must not enter logs or representations.

The request-signing helper canonicalizes method/path/query/body/timestamp and
enforces a configurable past/future replay window. REST authentication currently
uses the `X-API-Key` header; signed-request verification is available for explicit
integrations but is not an additional hidden API requirement.

### Application factory and lifecycle

`main.create_app()` builds isolated services per FastAPI instance:

- engine, event bus, trading service, key manager, instruments;
- optional owned or caller-injected store;
- optional simulated feed;
- typed routes and same-origin static dashboard.

No mutable API dependency is stored in a module-level singleton. Lifespan startup
and teardown track each acquired resource, attempt every cleanup step, and surface
failures. Injected stores remain caller-owned; stores created by the app are
disposed by it.

Protected routes derive client identity and permissions from the validated key.
Order bodies cannot select a client. CORS is opt-in, wraps authentication errors,
and never combines wildcard origins with credentials.

`settings.yaml` has a strict implemented-key allowlist: unknown or malformed
settings fail before resources open. The development default binds loopback,
keeps CORS same-origin, labels nominal aggregates in EUR, and seeds the simulator
with `7`. UTC/Europe-Berlin values are fixed cross-surface contracts rather than
runtime timezone switches. Secrets and bootstrap credentials are environment
only; QuantCore never auto-loads `.env`.

The exact endpoint and error contracts are documented in
[`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## MCP v2 (`qxm/mcp_server/`)

The MCP integration uses the official Python SDK v2 high-level `MCPServer` API.
`create_mcp_server()` receives an engine and instruments, which keeps tests and
multiple server instances isolated.

Default tools are bounded and read-only:

- `list_instruments`
- `get_order_book`
- `calculate_risk`

`submit_order` and `cancel_order` are registered only when the constructing code
sets `allow_writes=True` and binds a client identity. Identity and credentials are
never model/tool arguments. Tool annotations communicate read-only,
destructive, idempotent, and open-world intent, but the registration gate is the
authorization boundary. Writes are capped at 10,000 units, and submission output
retains at most 100 trades while reporting total/returned counts and truncation
without hiding engine execution. Rejections carry the engine's reason, capped at
256 characters at the MCP boundary.

`run_server()` constructs a fresh read-only local simulation and calls
`MCPServer.run()` synchronously over stdio. Server code never prints to stdout,
because stdout is protocol traffic. Tests use both the in-memory SDK
`Client(server)` transport and a real stdio initialize/list-tools smoke path.

## Dashboard (`dashboard/index.html`)

The dashboard is a self-contained HTML/CSS/JavaScript application:

- same-origin REST calls; no CDN, analytics, fonts, or external assets;
- API key kept only in `sessionStorage`;
- German and English copy;
- `de-DE`/`en-GB` formatting and Europe/Berlin time;
- instrument currency on each position row, with nominal reporting labels on
  aggregates because no FX conversion is performed;
- semantic structure, keyboard operation, focus visibility, reduced motion,
  retry/error/empty states, and non-colour status cues.

It consumes exactly `as_of`, `currency`, `kpis`, `positions`, `pnl_history`,
`risk`, and `order_books` from `/api/v1/dashboard`.

## Workshop scenario system

The baseline package stays green. `scripts/workshop.py` stages the seven
deterministic scenario IDs under their own `work/` directories:

```text
incident-fill-price
migration-legacy-models
review-pr
elective-mcp
elective-cli
elective-customization
capstone-transfer
```

Scenario manifests declare inert `payloads/*.txt`, artifacts, acceptance checks,
and captured fallbacks. Runtime state lives under ignored `.workshop-state/`.
Start is transactional; verify runs bounded declared checks or validates structured
evidence; reset archives participant work and restores the pre-start bytes/modes
without broad Git commands.

Captured artifacts keep cloud agents, code review, MCP policy, CLI availability,
and network quality off the critical path.

## Time, number, and currency boundaries

- Internal and exchanged timestamps: aware UTC.
- Human presentation: `Europe/Berlin`, 24-hour clock, CET/CEST from timezone data.
- Machine numbers: dot decimal separator.
- German display: decimal comma and dot thousands separator.
- Calculation/storage: Decimal where value must be exact.
- Instrument currencies: explicit EUR/USD metadata.
- FX conversion: not implemented; mixed-currency nominal totals must not be
  described as converted economic value.

## Entrypoints and checks

```bash
# REST application
quantcore
# equivalent during development
python main.py

# read-only local MCP stdio server
quantcore-mcp
# equivalent
python -m qxm.mcp_server.server

# workshop scenarios
python scripts/workshop.py list

# release baseline
pytest tests/ -q
ruff check .
mypy qxm
python -m compileall -q qxm scripts security_check.py main.py
bandit -q -r qxm main.py security_check.py
python security_check.py
python scripts/workshop_doctor.py
```

The workshop-supported interpreter is Python 3.12.x; CI pins 3.12.14.

## Principal dependencies

| Dependency | Purpose |
|---|---|
| Pydantic 2.12+ | Domain, API, and MCP validation/serialization |
| FastAPI / Uvicorn | REST application and ASGI server |
| SQLAlchemy 2 | Local typed persistence |
| sortedcontainers | Price-level ordering |
| NumPy / SciPy | Risk and option mathematics |
| websockets | Optional streaming adapter |
| MCP Python SDK 2.x | Typed stdio tools and in-memory client tests |
| PyYAML | Local configuration |

## Deliberate limitations

- simulated local state, not live trading;
- in-memory order books, positions, event log, and API-key registry;
- one configured application worker for coherent in-memory state;
- no stop triggers, exchange session calendar, DAY/GTD scheduler, FX conversion,
  corporate actions, margin, settlement, or durable event sourcing;
- simplified educational risk assumptions;
- local SQLite default and no operational HA/disaster-recovery claims;
- MCP default process is isolated and read-only.

These limitations are explicit teaching boundaries, not features to infer or
quietly work around.
