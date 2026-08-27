# Copilot instructions - MittelWerk

## Mission and baseline

MittelWerk (`mittelwerk`) is a Python 3.12 educational industrial equipment and
field-service simulation for a supervised GitHub Copilot workshop. It is not a
production dispatch, billing, or asset-management system. Every organisation,
site, asset, provider, work order, rate, telemetry reading, and event is
synthetic.

A clean checkout is healthy. Deliberate defects and legacy code belong only in
isolated `workshop/scenarios/` payloads; do not plant defects in `mittelwerk/` or
the baseline tests.

## Architecture

- `mittelwerk/core/`: Pydantic v2 equipment, work-order, assignment, workload,
  and event models plus the asynchronous service-dispatch engine.
- `mittelwerk/analytics/`: non-negative SLA, backlog, cost, and utilization
  metrics.
- `mittelwerk/data/`: deterministic telemetry, SQLAlchemy 2 storage, and
  operational transforms.
- `mittelwerk/dispatch/`: metaclass-registered dispatch policies.
- `mittelwerk/auth/`: HMAC-SHA256 signing and in-memory API-key lifecycle.
- `mittelwerk/api/`: per-application FastAPI services and `/api/v1` routes.
- `mittelwerk/mcp_server/`: official MCP Python SDK v2 server, read-only by
  default.
- `dashboard/`: self-contained DE/EN service-operations dashboard.
- `scripts/workshop.py`: transactional scenario runner.

## Contracts

- Use Pydantic v2 APIs only.
- Service rates, hours, costs, and other exact quantities use `Decimal`.
- Persist and exchange timezone-aware UTC. Convert to `Europe/Berlin` only for
  presentation; never hard-code CET or CEST.
- Provider capacity is assigned by lowest eligible hourly rate and FIFO at the
  same rate. An assignment uses the accepted provider offer's rate.
- Work-order IDs are permanently reserved on first submission attempt.
- Operational magnitudes are non-negative; overdue hours cannot exceed open
  hours; utilization is bounded.
- REST routes use `/api/v1` and `X-API-Key`. Organisation identity comes from
  the key, never a work-order body. Missing keys are 401; invalid, expired,
  revoked, or under-permissioned keys are 403.
- MCP mutation tools require explicit construction-time opt-in and a bound
  organisation identity. Tool annotations are metadata, not authorization.
- Machine JSON uses dot decimals. `de-DE` formatting belongs only in
  human-facing output, with explicit currency and no implied FX conversion.

## Workshop content

- Preserve `Understand/Plan -> Implement/Test -> Review -> Explain`.
- Keep Supported, Core, Extension, Solo, and captured/offline routes usable.
- Do not add answer keys, repair maps, or revealing comments/test names.
- Scenario payloads remain inert `*.txt`; `start` creates working copies under
  the scenario `work/` directory. Reset must not use destructive Git commands.
- Use synthetic, non-sensitive, non-personal data only.
- Use plain international English and the DACH/accessibility conventions under
  `challenges/reference/` and `workshop/ops/`.

## Development

- Type public functions and reuse validators and serializers.
- New dispatch policies subclass the existing base class and use its metaclass
  registration.
- Keep application instances isolated.
- New MCP tools use typed parameters, bounded outputs, explicit annotations,
  in-memory client tests, and a real stdio smoke test. Never print to stdout in
  stdio server code.
- Add deterministic tests and keep failures explicit; no broad catches or
  success-shaped fallbacks.

Run the smallest relevant check first, then:

```bash
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
