# Proctor Guide — Challenge 5: Security Hardening

## Vulnerability Solutions

### Vuln 1: SQL Injection (`qxm/api/routes.py`)

**Location**: `search_instruments` endpoint

**Problem**:
```python
# VULNERABLE:
query = f"SELECT * FROM instruments WHERE name LIKE '%{search_term}%'"
result = db.execute(query)
```

**Fix**:
```python
# SECURE — parameterised query:
from sqlalchemy import text

query = text("SELECT * FROM instruments WHERE name LIKE :term")
result = db.execute(query, {"term": f"%{search_term}%"})
```

**Why it's dangerous**: An attacker can input `'; DROP TABLE instruments; --` as the search term, which would execute arbitrary SQL.

---

### Vuln 2: Insecure Random (`qxm/auth/keys.py`)

**Location**: `KeyManager.generate_key()` method

**Problem**:
```python
# VULNERABLE:
import random
key = ''.join(random.choice(CHARSET) for _ in range(length))
```

**Fix**:
```python
# SECURE:
import secrets
key = ''.join(secrets.choice(CHARSET) for _ in range(length))
```

**Why it's dangerous**: `random.choice` uses a Mersenne Twister PRNG which is not cryptographically secure. An attacker who observes enough keys can predict future keys.

---

### Vuln 3: Hardcoded Secret (`qxm/auth/keys.py`)

**Location**: Module-level `MASTER_SECRET` variable

**Problem**:
```python
# VULNERABLE:
MASTER_SECRET = "super-secret-master-key-do-not-share"
```

**Fix**:
```python
# SECURE:
import os
MASTER_SECRET = os.environ.get("QXM_MASTER_SECRET")
if not MASTER_SECRET:
    raise RuntimeError("QXM_MASTER_SECRET environment variable must be set")
```

**Why it's dangerous**: Anyone with access to the source code (including version control history) can see the secret. Secrets should never be in code.

---

### Vuln 4: Unsafe Deserialisation (`qxm/utils/serializer.py`)

**Location**: `from_binary()` function

**Problem**:
```python
# VULNERABLE:
import pickle
def from_binary(data: bytes) -> Any:
    return pickle.loads(data)
```

**Fix**:
```python
# SECURE — use JSON or msgpack:
import json

def from_binary(data: bytes) -> Any:
    return json.loads(data.decode('utf-8'))
```

Or if binary efficiency is needed:
```python
import msgpack

def from_binary(data: bytes) -> Any:
    return msgpack.unpackb(data, raw=False)
```

**Why it's dangerous**: `pickle.loads()` can execute arbitrary Python code during deserialisation. An attacker who controls the input bytes can achieve remote code execution.

---

### Vuln 5: Timing Attack (`qxm/api/middleware.py`)

**Location**: `APIKeyAuthMiddleware` — key comparison

**Problem**:
```python
# VULNERABLE:
if provided_key == stored_key:
    return True
```

**Fix**:
```python
# SECURE:
import hmac

if hmac.compare_digest(provided_key, stored_key):
    return True
```

**Why it's dangerous**: String `==` comparison short-circuits on the first differing character. An attacker can measure response time differences to guess the key character by character.

---

### Vuln 6: Missing Input Validation (`qxm/api/routes.py`)

**Location**: `submit_order` endpoint

**Problem**:
```python
# VULNERABLE — no validation:
@router.post("/orders")
async def submit_order(order_data: dict):
    order = Order(**order_data)  # Accepts negative quantities, zero prices, etc.
```

**Fix**:
```python
# SECURE — with validation:
from pydantic import BaseModel, Field

class OrderRequest(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20)
    side: Side
    order_type: OrderType
    quantity: int = Field(..., gt=0, le=1_000_000)
    price: float = Field(None, gt=0, le=1_000_000)
    client_id: str = Field(..., min_length=1, max_length=50)
    time_in_force: TimeInForce = TimeInForce.GTC

@router.post("/orders")
async def submit_order(order_data: OrderRequest):
    order = Order(**order_data.model_dump())
```

**Why it's dangerous**: Without validation, an attacker could submit orders with negative quantities (selling shares they don't have), zero prices, or extremely large values.

---

## Copilot Prompts That Work Well

### Broad scan:
```
Perform a comprehensive security audit of this Python project. Check for:
1. SQL injection vulnerabilities
2. Hardcoded secrets or credentials
3. Insecure randomness
4. Unsafe deserialisation (pickle, yaml.load, eval)
5. Timing attacks in authentication
6. Missing input validation on API endpoints
List every issue with file, line number, severity, and fix.
```

### Targeted:
```
Is the key comparison in qxm/api/middleware.py vulnerable to timing attacks? 
Show me the current code and the secure alternative.
```

```
Find all uses of pickle in the codebase. Are any of them deserialising untrusted data?
```

## Common Pitfalls

1. **SQL injection fix**: Some attendees use ORM methods but still interpolate strings — ensure they use parameter binding
2. **Secrets module**: Attendees may use `os.urandom` + base64 instead of `secrets.choice` — both are acceptable
3. **Environment variables**: For the hardcoded secret, some attendees may suggest a config file — explain that environment variables are the standard for secrets management, and in production you'd use a vault service
4. **Pickle replacement**: Some may suggest `json.loads` directly, forgetting that the existing data format may be pickle — they need to handle migration
5. **`hmac.compare_digest`**: Attendees need to ensure both inputs are the same type (both str or both bytes)

## Verification

```bash
# Run the security scanner
python security_check.py

# Run all tests
pytest tests/ -v

# Verify specific fixes
python -c "
import hmac
print('hmac.compare_digest available:', hasattr(hmac, 'compare_digest'))
"

python -c "
import secrets
key = ''.join(secrets.choice('abcdef0123456789') for _ in range(32))
print(f'Secure key generated: {key}')
"
```
