# Contributing — QuantCore

## Development Setup

```bash
# Clone and install in dev mode
git clone <repo-url>
cd githubcopilotworkshop
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Project Conventions

### Code Style

- Python 3.11+ features are encouraged (StrEnum, tomllib, match/case)
- Type hints on all public functions
- Use `from __future__ import annotations` for forward references
- Follow PEP 8 with 100-character line length (configured in pyproject.toml)

### Module Layout

```
qxm/<module>/
├── __init__.py    # Re-exports public API
├── <main>.py      # Core implementation
└── <aux>.py       # Supporting code
```

Each module's `__init__.py` defines the public surface. Import from the module, not sub-files:

```python
# Good:
from qxm.core import Order, MatchingEngine

# Avoid:
from qxm.core.engine import MatchingEngine
```

### Naming Conventions

- Classes: `PascalCase` — `OrderBook`, `VaREngine`, `OptionPricer`
- Functions/methods: `snake_case` — `submit_order()`, `compute_vwap()`
- Constants: `UPPER_SNAKE_CASE` — `MAX_ORDER_QUANTITY`, `DEFAULT_PORT`
- Private: prefix with `_` — `_match_order()`, `_running`
- Test files: `test_<module>.py`

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_risk.py -v

# Run with coverage
pytest tests/ --cov=qxm --cov-report=term-missing
```

Tests live in `tests/` and use `pytest` with fixtures defined in `conftest.py`.

### Domain Model Changes

When modifying Pydantic models in `qxm/core/models.py`:
1. Update the model class
2. Update any validators
3. Check serialisation in `qxm/utils/serializer.py`
4. Update API routes if the model is exposed
5. Run `pytest tests/test_models.py`

### Adding a New Strategy

1. Create a new file in `qxm/strategy/`
2. Subclass `BaseStrategy` — the metaclass auto-registers it
3. Implement `evaluate(symbol)` returning a `Signal`
4. Add to `qxm/strategy/__init__.py` exports

### Adding an MCP Tool

1. Open `qxm/mcp_server/server.py`
2. Add a new function decorated with `@mcp.tool()`
3. Use existing service objects (position_manager, matching_engine, etc.)
4. Return JSON-serialisable strings

## Git Workflow

- `main` branch: Workshop attendee starting point
- `proctor` branch: Superset with solutions and proctor guides
- Feature branches should be named `feature/<description>`

## Useful Commands

```bash
# Start the API server
python main.py

# Generate sample data
python scripts/generate_sample_data.py

# Run security scanner
python security_check.py

# Start MCP server standalone
python -m qxm.mcp_server.server
```
