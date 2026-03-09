# Challenge 4 — Pydantic v1 → v2 Migration

## Objective

Migrate all domain models from Pydantic v1 to Pydantic v2. This is a real-world task that many Python teams face, and Copilot Agent Mode can dramatically accelerate it.

## Recommended Model

**Claude Sonnet 4** in **Agent Mode** — Best for large-scale, multi-file refactoring with consistent patterns.

## Background

QuantCore currently uses Pydantic v1 (`pydantic>=1.10,<2.0`). We need to upgrade to v2 for:
- 5-50x faster validation
- Stricter type checking
- Better JSON Schema generation
- Long-term support

## Migration Checklist

### Phase 1: Dependency Update

1. Update `pyproject.toml`: Change `pydantic>=1.10,<2.0` → `pydantic>=2.0`
2. Update `requirements.txt` accordingly
3. Install the new version: `pip install pydantic>=2.0`

### Phase 2: Model Migration (`qxm/core/models.py`)

The following v1 patterns need to be converted to v2:

| v1 Pattern | v2 Replacement |
|---|---|
| `class Config:` inner class | `model_config = ConfigDict(...)` |
| `@validator` | `@field_validator` |
| `@root_validator` | `@model_validator` |
| `__get_validators__` | `__get_pydantic_core_schema__` or `Annotated[..., AfterValidator]` |
| `.dict()` | `.model_dump()` |
| `.json()` | `.model_dump_json()` |
| `update_forward_refs()` | `model_rebuild()` |
| `Field(...)` allows extra | `Field(...)` with `model_config` |
| `Optional[X] = None` | Same (but strict mode changes) |

### Phase 3: Usage Updates

Search the entire codebase for v1 API usage:
- `.dict()` → `.model_dump()`
- `.json()` → `.model_dump_json()`
- `.parse_raw()` → `.model_validate_json()`
- `.parse_obj()` → `.model_validate()`
- `update_forward_refs()` → `model_rebuild()`

Files to check:
- `qxm/core/engine.py`
- `qxm/risk/portfolio.py`
- `qxm/api/routes.py`
- `qxm/mcp_server/server.py`
- `qxm/utils/serializer.py`
- `tests/test_models.py`

### Phase 4: Custom Type Migration

The `TickSize` type in `models.py` uses `__get_validators__()` which is removed in v2. Ask Copilot how to migrate this to the v2 pattern using `Annotated` with custom validators.

## How to Use Copilot

### Recommended Approach: Agent Mode

1. Open Copilot Chat in **Agent Mode** (⌘+I → Agent Mode)
2. Give it a comprehensive prompt:

   > "Migrate all Pydantic v1 code in this project to Pydantic v2. This includes:
   > - Converting @validator to @field_validator
   > - Converting @root_validator to @model_validator
   > - Replacing class Config with model_config = ConfigDict(...)
   > - Updating .dict() to .model_dump() throughout
   > - Migrating the TickSize custom type from __get_validators__ to Annotated validators
   > - Updating update_forward_refs() to model_rebuild()
   > - Updating pyproject.toml and requirements.txt"

3. Review each change Copilot proposes
4. Accept or adjust as needed

### Alternative: File-by-File

If you prefer more control:
1. Start with `qxm/core/models.py` — the main model file
2. Ask Copilot to convert one pattern at a time
3. Move to dependent files

## Verification

```bash
# Run model tests
pytest tests/test_models.py -v

# Check all imports work
python -c "from qxm.core.models import Order, Instrument, Position; print('OK')"

# Verify serialisation
python -c "
from qxm.core.models import Order, Side, OrderType, TimeInForce
o = Order(symbol='AAPL', side=Side.BUY, order_type=OrderType.LIMIT, quantity=100, price=150.0, client_id='test', time_in_force=TimeInForce.GTC)
print(o.model_dump())
"
```

## Stretch Goals

- Enable Pydantic v2 **strict mode** and fix any resulting validation errors
- Add `model_json_schema()` export to each model and verify the generated schema
- Benchmark the validation speed improvement (v1 vs v2) for a batch of 10,000 orders
- Migrate the `QuantEncoder` in `utils/serializer.py` to use `model_dump()` instead of checking for `.dict()`

## Time

~60 minutes

---

*Next: [Challenge 5 — Security Hardening](./challenge_05_security.md)*
