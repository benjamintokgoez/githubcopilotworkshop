# Copilot instructions - QuantCore

## Mission and baseline

QuantCore (`qxm`) is a Python 3.12 educational trading simulation and the
substrate for a supervised GitHub Copilot workshop. It is not connected to live
markets, is not production trading software, and must not be presented as
investment advice.

A clean checkout is healthy. Deliberate defects and legacy code belong only in
the isolated scenario payloads under `workshop/scenarios/`; do not plant defects
in `qxm/` or the baseline tests.

## Architecture

- `qxm/core/`: Pydantic v2 domain models, Decimal-based FIFO order book,
  asynchronous matching engine, positions, and event log/bus.
- `qxm/risk/`: non-negative VaR/CVaR loss magnitudes, stress tests,
  Black-Scholes-Merton pricing and Greeks, and portfolio algebra.
- `qxm/data/`: deterministic simulated feeds, a reconnecting WebSocket adapter,
  SQLAlchemy 2 storage, and OHLC/VWAP/TWAP transforms.
- `qxm/strategy/`: metaclass-registered momentum and mean-reversion strategies.
- `qxm/auth/`: HMAC-SHA256 request signing and in-memory API-key lifecycle.
- `qxm/api/`: per-application FastAPI services and typed `/api/v1` routes.
- `qxm/mcp_server/`: official MCP Python SDK v2 server; read-only by default.
- `qxm/utils/`: strict JSON, sync/async decorators, metrics, and security checks.
- `dashboard/`: self-contained DE/EN dashboard with no CDN or telemetry.
- `scripts/workshop.py`: transactional scenario start/verify/reset/fallback tool.

## Contracts that must remain consistent

- Use Pydantic v2 APIs: `ConfigDict`, `field_validator`, `model_validator`,
  `model_validate()`, and `model_dump()`. Do not add v1 compatibility idioms.
- Prices, quantities, and monetary values use `Decimal`; do not introduce binary
  float at storage or API boundaries.
- Persist and exchange timezone-aware UTC. Convert to `Europe/Berlin` only at the
  presentation edge; never hard-code CET or CEST offsets.
- Bids are ordered highest first, asks lowest first, with FIFO within a price
  level. A fill executes at the resting maker's price.
- `MatchingEngine.submit_order()` and `cancel_order()` are async. Order IDs are
  permanently reserved on first submission attempt; duplicates are conflicts.
- The engine supports LIMIT/MARKET with GTC, IOC, and FOK. STOP/STOP_LIMIT and
  DAY/GTD are represented by the domain model but rejected until their required
  trigger/session subsystems exist.
- VaR and CVaR are non-negative loss magnitudes. Empty portfolios return zero;
  short books use gross exposure.
- Position fields use `average_entry_price`, `realized_pnl`, and
  `unrealized_pnl`.
- REST routes use `/api/v1` and `X-API-Key`. Client identity comes from the key,
  never from an order body. Missing keys are 401; invalid, expired, revoked, or
  under-permissioned keys are 403.
- The MCP server uses `MCPServer` from SDK v2. Read-only tools are the default;
  mutation tools are registered only through explicit construction-time opt-in
  with a bound client identity. Tool annotations are metadata, not authorization.
- Machine JSON uses a dot decimal separator. DACH formatting (`de-DE`, 24-hour
  time, decimal comma) belongs only in human-facing output. Currency must be
  explicit; do not imply an FX conversion that did not happen.

## Workshop content

- Preserve the loop: `Understand/Plan -> Implement/Test -> Review -> Explain`.
- Keep Supported, Core, Extension, Solo, and captured/offline routes usable.
- Do not add answer keys, solution maps, revealing comments, or test names that
  disclose a scenario's repair.
- Scenario payloads stay inert as `*.txt`; `start` creates working copies under a
  scenario's `work/` directory. Reset must not use destructive Git commands.
- Use synthetic, non-sensitive data only. Do not add credentials, personal data,
  private URLs, telemetry, or network-only critical paths.
- Use plain international English. Apply the privacy, accessibility, and DACH
  conventions in `challenges/reference/` and `workshop/ops/`.

## Development

- Type all public functions and follow the existing module conventions.
- Reuse domain validators and serializers instead of duplicating boundary logic.
- New strategies subclass `BaseStrategy`; `StrategyMeta` handles registration.
- New API endpoints use the router/dependency/service pattern and remain
  application-instance isolated.
- New MCP tools use typed parameters, bounded outputs, explicit annotations,
  in-memory `Client(server)` tests, and a real stdio smoke path. Never print to
  stdout in stdio server code.
- Add deterministic tests for behavior changes and keep failure handling explicit;
  do not use broad catches or success-shaped fallbacks.

Run the smallest relevant checks first, then the release baseline:

```bash
python -m compileall -q qxm main.py scripts security_check.py tests
python -m pytest tests/ -v
python -m ruff check .
python -m ruff format --check .
python -m mypy qxm main.py scripts
python -m pip check
python -m bandit -r qxm main.py -ll
python security_check.py
python scripts/workshop_doctor.py --strict
```
