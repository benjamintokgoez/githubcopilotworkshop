# Proctor Guide — Challenge 4: Pydantic v1 → v2 Migration

## Complete Migration Reference

### File: `qxm/core/models.py` — Main Changes

#### 1. Imports

```python
# Before (v1):
from pydantic import BaseModel, Field, validator, root_validator

# After (v2):
from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict
```

#### 2. `class Config` → `model_config`

```python
# Before (v1):
class Instrument(BaseModel):
    class Config:
        frozen = True
        use_enum_values = True

# After (v2):
class Instrument(BaseModel):
    model_config = ConfigDict(frozen=True, use_enum_values=True)
```

#### 3. `@validator` → `@field_validator`

```python
# Before (v1):
@validator("tick_size")
def validate_tick_size(cls, v):
    if v <= 0:
        raise ValueError("tick_size must be positive")
    return v

# After (v2):
@field_validator("tick_size")
@classmethod
def validate_tick_size(cls, v):
    if v <= 0:
        raise ValueError("tick_size must be positive")
    return v
```

Key difference: v2 requires `@classmethod` decorator explicitly.

#### 4. `@root_validator` → `@model_validator`

```python
# Before (v1):
@root_validator
def validate_option_fields(cls, values):
    if values.get("instrument_type") == InstrumentType.OPTION:
        if not values.get("strike"):
            raise ValueError("Options need strike")
    return values

# After (v2):
@model_validator(mode="before")
@classmethod
def validate_option_fields(cls, values):
    if values.get("instrument_type") == InstrumentType.OPTION:
        if not values.get("strike"):
            raise ValueError("Options need strike")
    return values
```

Or with `mode="after"` for access to the model instance:
```python
@model_validator(mode="after")
def validate_option_fields(self):
    if self.instrument_type == InstrumentType.OPTION:
        if not self.strike:
            raise ValueError("Options need strike")
    return self
```

#### 5. `__get_validators__` → `Annotated` + custom type

```python
# Before (v1):
class TickSize:
    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v):
        if not isinstance(v, (int, float)):
            raise TypeError("numeric required")
        return Decimal(str(v))

# After (v2 — using Annotated):
from typing import Annotated
from pydantic import AfterValidator

def validate_tick_size(v):
    if not isinstance(v, (int, float, Decimal)):
        raise TypeError("numeric required")
    return Decimal(str(v))

TickSize = Annotated[Decimal, AfterValidator(validate_tick_size)]
```

#### 6. `update_forward_refs()` → `model_rebuild()`

```python
# Before (v1):
Order.update_forward_refs()

# After (v2):
Order.model_rebuild()
```

### File: `qxm/core/engine.py` — Usage Changes

```python
# Before (v1):
order.dict()
trade = Trade.parse_obj(data)

# After (v2):
order.model_dump()
trade = Trade.model_validate(data)
```

### File: `qxm/risk/portfolio.py`

```python
# Before (v1):
snapshot = PortfolioSnapshot(**data)
snapshot.dict()

# After (v2):
snapshot = PortfolioSnapshot.model_validate(data)
snapshot.model_dump()
```

### File: `qxm/api/routes.py`

```python
# Before (v1):
return order.dict()

# After (v2):
return order.model_dump()
```

### File: `qxm/utils/serializer.py`

```python
# Before (v1):
if hasattr(obj, "dict"):
    return obj.dict()

# After (v2):
if hasattr(obj, "model_dump"):
    return obj.model_dump()
```

### File: `qxm/mcp_server/server.py`

```python
# Before (v1):
return position.dict()

# After (v2):
return position.model_dump()
```

### File: `pyproject.toml`

```toml
# Before:
pydantic = ">=1.10,<2.0"

# After:
pydantic = ">=2.0"
```

### File: `requirements.txt`

```
# Before:
pydantic>=1.10,<2.0

# After:
pydantic>=2.0
```

## Copilot Prompts That Work Well

### All-at-once (Agent Mode):
```
Migrate all Pydantic v1 code in this project to Pydantic v2. This includes:
- Converting @validator to @field_validator with @classmethod
- Converting @root_validator to @model_validator  
- Replacing class Config with model_config = ConfigDict(...)
- Updating .dict() to .model_dump() throughout all files
- Migrating the TickSize custom type from __get_validators__ to Annotated validators
- Updating update_forward_refs() to model_rebuild()
- Updating pyproject.toml and requirements.txt dependencies
```

### Pattern-specific:
```
Find all uses of .dict() in this project and replace them with .model_dump() for Pydantic v2 compatibility.
```

```
The TickSize type in models.py uses __get_validators__ which was removed in Pydantic v2. Migrate it to use Annotated with AfterValidator.
```

## Common Pitfalls

1. **Missing `@classmethod`**: v2 `@field_validator` requires explicit `@classmethod` — Copilot sometimes forgets this
2. **`mode` parameter**: `@model_validator` requires `mode="before"` or `mode="after"` — v1 didn't have this distinction
3. **`values` vs `self`**: With `mode="after"`, the validator receives `self` (the model instance), not a dict. With `mode="before"`, it receives the raw dict.
4. **`TickSize` migration**: This is the hardest part — attendees may struggle with the `Annotated` pattern
5. **Missed `.dict()` calls**: Use `grep -r "\.dict()" qxm/` to find all occurrences

## Verification

```bash
# Install pydantic v2
pip install pydantic>=2.0

# Run all tests
pytest tests/ -v

# Quick smoke test
python -c "
from qxm.core.models import Order, Instrument, Side, OrderType, TimeInForce
o = Order(symbol='AAPL', side=Side.BUY, order_type=OrderType.LIMIT, quantity=100, price=150.0, client_id='test', time_in_force=TimeInForce.GTC)
print(type(o.model_dump()))
print('Migration successful!')
"
```
