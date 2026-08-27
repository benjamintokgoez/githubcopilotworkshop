# MittelWerk architecture

## Purpose

MittelWerk is a deterministic educational simulation of industrial equipment
service operations for a supervised GitHub Copilot workshop. It gives
participants a coherent system for incident response, migration, review,
least-privilege tooling, and operational handover practice.

MittelWerk is fictional. Every organisation, site, asset, provider, work order,
telemetry reading, and scenario is synthetic. The application is not connected
to real equipment and is not a maintenance or safety decision system.

## Runtime view

```text
                               same-origin browser
                            +------------------------+
                            | dashboard/index.html   |
                            +-----------+------------+
                                        |
                                        | HTTP + X-API-Key
                                        v
+---------------+       +-----------------------------------------------+
| REST clients  +------>| FastAPI application (main.py, mittelwerk/api) |
+---------------+       |                                               |
                        | middleware -> identity/permission -> routes    |
                        |                         |                     |
                        |                    DispatchService             |
                        +-------------+-----------+-----------+----------+
                                      |                       |
                                      v                       v
                          +----------------------+  +----------------------+
                          | DispatchEngine       |  | TelemetryStore       |
                          | DispatchQueue        |  | SQLite / SQLAlchemy  |
                          | WorkloadManager      |  | readings/assignments |
                          | EventBus / EventLog  |  | equipment            |
                          +----------+-----------+  +----------------------+
                                     ^
                                     | synthetic readings
                          +----------+-----------+
                          | deterministic feed   |
                          | aware UTC telemetry  |
                          +----------------------+

+----------------+       injected isolated engine/equipment
| MCP v2 client  +-----------------------------------------------+
+-------+--------+                                               |
        | stdio                                                  v
        +-------------------------------------------->+----------------------+
                                                     | MCPServer factory    |
                                                     | read-only by default |
                                                     +----------------------+
```

The REST application and the default MCP process construct separate in-memory
dispatch engines. They do not silently share work orders or workloads. An
explicit local integration can inject an engine into `create_mcp_server()`.

## Core domain (`mittelwerk/core/`)

### Models

`mittelwerk/core/models.py` uses Pydantic v2 and `Decimal` at rate, hours, cost,
and workload boundaries.

- `Equipment` defines an asset, service interval, standard hourly rate, rate
  increment, hour lot size, currency, and site.
- `WorkOrder` represents either an organisation request or a provider capacity
  offer, with its mode, dispatch window, requested and assigned hours, rate
  constraints, status, and aware-UTC timestamps.
- `ServiceAssignment` records the requester, provider, accepted hours, and the
  authoritative hourly rate.
- `Workload` tracks signed hours, average service rate, realised cost,
  unrealised cost, and the latest reference rate.
- `OrganizationSnapshot`, `OperationalRiskMetrics`, and `TelemetryReading`
  provide typed reporting and telemetry surfaces.

External timestamps reject naive values and normalise aware offsets to UTC.
Asset and currency identifiers are normalised at validation boundaries.
JSON-facing decimal values are emitted as strings, without conversion through
binary float.

### Dispatch queue

`mittelwerk/core/queue.py` implements two-sided rate-time priority:

- requests use negated keys in `SortedDict`, yielding the highest acceptable
  rate first;
- provider offers use natural ascending keys, yielding the lowest offered rate
  first;
- each rate level owns a FIFO `deque`;
- snapshots aggregate remaining hours and work-order counts;
- cancellation keeps the rate index and work-order lookup coherent.

### Dispatch engine

`DispatchEngine` is constructed with an `EventBus`, equipment map, and optional
structurally typed `PreDispatchCheck`.

```python
submission = await engine.submit_work_order(work_order)
cancelled = await engine.cancel_work_order(work_order_id, asset_id=None)
```

The engine reserves a work-order ID synchronously before its first `await`, so
concurrent submissions cannot both pass the duplicate check. Every attempted
ID, including one later rejected, remains reserved.

The dispatch rules are:

- best eligible rate, then FIFO at that rate;
- an assignment uses the resting provider or requester work order's rate;
- `RATE_CAPPED` and `ANY_RATE` modes are supported;
- `OPEN`, `IMMEDIATE`, and `COMPLETE` dispatch windows are supported;
- an unassigned `IMMEDIATE` or `ANY_RATE` remainder stands down;
- an unfulfillable `COMPLETE` request does not consume capacity;
- `ESCALATION` modes and `SHIFT`/`SCHEDULED_END` windows are represented but
  rejected until trigger and scheduling subsystems exist.

Every assignment updates both work orders and both organisations' workloads,
adds one `ServiceAssignment`, and publishes lifecycle and assignment events.

### Events

`mittelwerk/core/events.py` contains:

- `DomainEvent`: frozen, aware-UTC event with source, correlation ID, and
  payload;
- `EventLog`: bounded append-only sequence with replay filters;
- `EventBus`: callbacks and async-generator streams, bounded subscriber queues,
  collision-safe subscriber IDs, and explicit async start/stop.

The event log is an in-process educational audit trail, not a durable
production event store.

## Operational analytics (`mittelwerk/analytics/`)

`backlog_risk.py` reports parametric, historical, and conditional backlog risk
as non-negative hour magnitudes. Inputs are finite and bounded, covariance
matrices must be positive semidefinite, and demand shocks below `-100%` are
rejected.

`capacity.py` estimates completion time, service cost, and sensitivity to crew,
rate, and backlog changes. `CachedMetric` invalidates descriptor-cached results
when capacity parameters change.

`operations.py` reads workloads through a provider so API analytics follow the
engine. It computes gross committed hours, utilisation, SLA indicators,
backlog risk, service-level consistency, and organisation snapshots. Algebraic
composition returns new analytics objects and does not mutate its operands.

Numerical algorithms may use finite floats internally. Exact hours, rates, and
costs remain `Decimal` at domain and API boundaries.

## Telemetry and persistence (`mittelwerk/telemetry/`)

### Feed

`ReadingSimulator` and `TelemetryFeed` are seedable and offline. The
application passes the bounded integer seed from `settings.yaml` so workshop
runs are reproducible. The FastAPI lifespan starts the feed, consumes each
reading, publishes its event, and updates workload reference rates. Unexpected
feed completion or failure is supervised, logged, and reflected as degraded
liveness.

`WebSocketFeedAdapter` is a reusable reconnecting adapter. It validates
subscribed assets and aware timestamps and stops without turning a disconnect
into a busy loop. It is not wired into the workshop's critical path.

### Transforms

`mittelwerk/telemetry/transform.py` supplies asset-separated interval
aggregation, sample-weighted and arithmetic averages, reading deltas,
variability, normalisation, rolling statistics, and exponential moving
averages. Empty or invalid windows and non-finite inputs fail explicitly.

### Store

`TelemetryStore` uses SQLAlchemy 2 typed mappings and short-lived transactions.
SQLite is the local default, including `StaticPool` for thread-compatible
in-memory tests.

- `DecimalText` stores exact finite decimal text.
- `UTCDateTime` rejects naive values, normalises to UTC, and restores UTC after
  SQLite round trips.
- Equipment search escapes `LIKE` wildcards and uses bound parameters.
- Reading, interval, assignment, and equipment queries have hard limits.
- Batch insertion validates rows before one atomic transaction.

The API persists assignments after dispatch. This boundary is deliberately
non-atomic: an in-memory assignment cannot be rolled back if storage fails.
The API therefore reports a reconciliation error that states the real work
order and assignment state and tells the caller not to resubmit.

## Dispatch policies (`mittelwerk/dispatch_policies/`)

`DispatchPolicyMeta` registers concrete `BasePolicy` subclasses automatically.
The included policies cover capacity thresholds, telemetry trends, telemetry
band deviations, and cross-asset telemetry imbalance. Recommendations use
bounded confidence, aware-UTC readings, and synthetic metadata.

Policies produce recommendations and work-order candidates only. The
application does not automatically route a recommendation into dispatch.

## Authentication and REST API

### Authentication (`mittelwerk/auth/`)

`KeyManager` creates high-entropy `mwk_` keys, stores only keyed HMAC-SHA256
digests, uses `hmac.compare_digest`, and supports expiry, revocation, rotation,
permissions, and safe metadata. Raw keys are returned only when issued or
registered and must not enter logs or representations.

The signing helper canonicalises method, path, query, body, and timestamp and
enforces a configurable past/future replay window. REST authentication uses
the `X-API-Key` header; request signing is available for explicit integrations
but is not an additional hidden API requirement.

### Application factory (`main.py`, `mittelwerk/api/`)

`main.create_app()` builds isolated services for each FastAPI instance:

- dispatch engine, event bus, service layer, key manager, and equipment;
- optional owned or caller-injected telemetry store;
- optional deterministic feed;
- typed `/api/v1` routes and a same-origin static dashboard.

No mutable API dependency is a module-level singleton. Lifespan startup and
teardown track acquired resources and surface cleanup failures. Injected stores
remain caller-owned; stores created by the app are disposed by it.

Protected routes derive organisation identity and permissions from the
validated key. Work-order bodies cannot select an organisation. CORS is
opt-in, wraps authentication errors, and never combines wildcard origins with
credentials.

`settings.yaml` has an implemented-key allowlist. Unknown or malformed
settings fail before resources open. UTC and Europe/Berlin are fixed
cross-surface contracts. Credentials are environment-only; MittelWerk does not
load `.env` automatically.

The exact endpoint and error contracts are in
[`docs/API_REFERENCE.md`](docs/API_REFERENCE.md).

## MCP v2 (`mittelwerk/mcp_server/`)

The MCP integration uses the official Python SDK v2 `MCPServer` API.
`create_mcp_server()` receives an engine and equipment map, preserving
application and test isolation.

Default tools are bounded and read-only:

- `list_equipment`
- `get_dispatch_queue`
- `calculate_service_risk`

`submit_work_order` and `cancel_work_order` are registered only when
construction sets `allow_writes=True` and binds an organisation identity.
Identity and credentials are never tool arguments. Tool annotations describe
read-only, destructive, idempotent, and open-world intent, but registration
and bound identity are the authorisation boundary.

Write requests are bounded to 10,000 hours. Submission output retains at most
100 assignments while reporting total and returned counts and whether results
were truncated. Rejection reasons are capped at 256 characters.

`run_server()` constructs a fresh read-only simulation and runs synchronously
over stdio. Server code never prints to stdout because stdout carries protocol
traffic. Tests cover the in-memory `Client(server)` transport and a real stdio
initialise/list-tools path.

## Dashboard (`dashboard/index.html`)

The dashboard is a self-contained HTML/CSS/JavaScript application:

- same-origin REST calls with no CDN, analytics, fonts, or external assets;
- API key held only in `sessionStorage`;
- German and English copy;
- `de-DE`/`en-GB` formatting and Europe/Berlin time;
- explicit asset currency and nominal aggregate labels because no FX
  conversion is performed;
- semantic structure, keyboard operation, focus visibility, reduced motion,
  retry/error/empty states, and non-colour status cues.

It consumes `as_of`, `currency`, `kpis`, `workloads`, `cost_history`, `risk`,
and `dispatch_queues` from `/api/v1/dashboard`.

## Workshop scenario system

The baseline remains green. `scripts/workshop.py` stages seven deterministic
scenario IDs under their own `work/` directories:

```text
incident-service-rate
migration-legacy-models
review-pr
elective-mcp
elective-cli
elective-customization
capstone-transfer
```

Manifests declare inert `payloads/*.txt`, artifacts, acceptance commands, and
captured fallbacks. Runtime state lives under ignored `.workshop-state/`.
Start is transactional; verify runs bounded checks or validates structured
evidence; reset archives participant work and restores original bytes and
modes without destructive Git commands.

## Time, number, and currency boundaries

- Internal and exchanged timestamps: aware UTC.
- Human presentation: `Europe/Berlin`, 24-hour clock, CET/CEST from timezone
  data.
- Machine numbers: dot decimal separator.
- German display: decimal comma and dot thousands separator.
- Exact hours, rates, costs, and monetary values: `Decimal`.
- Asset and reporting currencies: explicit EUR/CHF metadata.
- FX conversion: not implemented; mixed-currency nominal totals are never
  described as converted economic value.

## Entrypoints and checks

```bash
# REST application
mittelwerk
# equivalent during development
python main.py

# read-only local MCP stdio server
mittelwerk-mcp
# equivalent
python -m mittelwerk.mcp_server.server

# workshop scenarios
python scripts/workshop.py list

# release baseline
python -m compileall -q mittelwerk main.py scripts security_check.py tests
python -m pytest tests/ -v
python -m ruff check .
python -m ruff format --check .
python -m mypy mittelwerk main.py scripts
python -m pip check
python -m bandit -r mittelwerk main.py -ll
python security_check.py
python scripts/workshop_doctor.py --strict
```

The supported interpreter is Python 3.12.x; CI pins 3.12.14.

## Principal dependencies

| Dependency | Purpose |
|---|---|
| Pydantic 2.12+ | Domain, API, and MCP validation/serialisation |
| FastAPI / Uvicorn | REST application and ASGI server |
| SQLAlchemy 2 | Local typed persistence |
| sortedcontainers | Rate-level ordering |
| NumPy / SciPy | Operational statistics and capacity analytics |
| websockets | Optional telemetry adapter |
| MCP Python SDK 2.x | Typed stdio tools and in-memory client tests |
| PyYAML | Local configuration |

## Deliberate limitations

- synthetic local state only;
- in-memory queues, workloads, event log, and API-key registry;
- one configured application worker for coherent in-memory state;
- no escalation-trigger subsystem, shift calendar, scheduled-expiry processor,
  FX conversion, or durable event sourcing;
- simplified educational telemetry and backlog assumptions;
- local SQLite default and no high-availability or disaster-recovery claims;
- an isolated, read-only MCP process by default.

These are explicit teaching boundaries, not features to infer or silently work
around.
