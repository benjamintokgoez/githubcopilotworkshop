# Proctor Guide — Challenge 2: Debugging

## Bug Catalogue with Solutions

### Bug 1: Circular Import (`qxm/__init__.py`)

**Location**: `qxm/__init__.py`, line with `from qxm.data.handler import MarketDataFeed`

**Problem**: The module was renamed from `handler` to `feed`. This causes an `ImportError` on any `import qxm`.

**Fix**:
```python
# Before (BROKEN):
from qxm.data.handler import MarketDataFeed

# After (FIXED):
from qxm.data.feed import MarketDataFeed
```

**Copilot Prompt**:
> "I'm getting an ImportError when importing qxm. The error says 'No module named qxm.data.handler'. Can you find the wrong import and fix it?"

**How attendees find it**: `python -c "import qxm"` → immediate ImportError.

---

### Bug 2: Config Type Bug (`settings.yaml`)

**Location**: `settings.yaml`, `port: "8443"`

**Problem**: Port is a quoted string `"8443"` instead of integer `8443`. When `main.py` passes this to uvicorn, it fails because uvicorn expects `int`.

**Fix**:
```yaml
# Before (BROKEN):
port: "8443"

# After (FIXED):
port: 8443
```

**Copilot Prompt**:
> "The server fails to start with a type error about the port. Review settings.yaml and main.py — is the port value the right type?"

**How attendees find it**: Starting the server → `TypeError: 'str' for port`.

---

### Bug 3: Missing Await (`qxm/data/feed.py`)

**Location**: `qxm/data/feed.py`, `MarketDataFeed.start()` method

**Problem**: `self._fetch_initial_prices()` is an async method but called without `await`. This silently creates a coroutine object that's never executed — prices are never initialised.

**Fix**:
```python
# Before (BROKEN):
async def start(self):
    self._fetch_initial_prices()
    self._running = True

# After (FIXED):
async def start(self):
    await self._fetch_initial_prices()
    self._running = True
```

**Copilot Prompt**:
> "In qxm/data/feed.py, the MarketDataFeed.start() method calls self._fetch_initial_prices() — is this correct? _fetch_initial_prices is an async method."

**How attendees find it**: Running the feed produces `RuntimeWarning: coroutine '_fetch_initial_prices' was never awaited` or prices are all zero.

---

### Bug 4: Missing `@functools.wraps` (`qxm/utils/decorators.py`)

**Location**: `qxm/utils/decorators.py`, `timed` decorator

**Problem**: The `timed` decorator doesn't use `@functools.wraps(func)`, so decorated functions lose their `__name__`, `__doc__`, and `__module__` attributes. This breaks introspection, logging, and test discovery.

**Fix**:
```python
# Before (BROKEN):
def timed(func):
    async def async_wrapper(*args, **kwargs):
        # ...

    def sync_wrapper(*args, **kwargs):
        # ...

# After (FIXED):
def timed(func):
    @functools.wraps(func)
    async def async_wrapper(*args, **kwargs):
        # ...

    @functools.wraps(func)
    def sync_wrapper(*args, **kwargs):
        # ...
```

**Copilot Prompt**:
> "Review the decorators in qxm/utils/decorators.py. Is the 'timed' decorator preserving the wrapped function's metadata correctly?"

**How attendees find it**: `print(some_decorated_function.__name__)` returns `"wrapper"` instead of the function's real name. Or pointed to by the tests.

---

### Bug 5: Startup Sequence

**Problem**: The combination of bugs 1-4 means the application cannot start at all. After fixing all four, the application boots.

**Verification sequence**:
```bash
# Step 1: Fix the import
python -c "import qxm"  # Should work now

# Step 2: Fix the config
python -c "import yaml; c = yaml.safe_load(open('settings.yaml')); assert isinstance(c['server']['port'], int)"

# Step 3: Verify all fixes together
python main.py  # Should start the server
```

## Debugging Strategy Guidance

### If attendees are stuck:

1. **"Start from the error"**: Run `python main.py` and read the first traceback line
2. **"Use Copilot's workspace context"**: In Agent Mode, ask "Why does this project fail to start? Analyze the import chain."
3. **"Use the tests"**: `pytest tests/ -v` — failing tests point to bugs
4. **"Read the warnings"**: Python RuntimeWarnings about unawaited coroutines are a strong signal

### Recommended Copilot approach:

> "This Python project fails to start. Run through the import chain starting from main.py and identify all import errors, type mismatches, and missing awaits."

## Common Pitfalls

- Attendees may fix bug 1 but create a new circular import — remind them to check `from qxm.data.feed import MarketDataFeed`
- For bug 3, some attendees add `await` but forget the function calling it also needs to be `async`
- For bug 4, attendees may add `@wraps` to only one branch (async or sync) — both need it
