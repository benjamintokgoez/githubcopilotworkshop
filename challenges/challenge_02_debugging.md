# Challenge 2 — Debugging

## Objective

The QuantCore application won't start. Use GitHub Copilot to find and fix 5 bugs that prevent the system from running correctly.

## Recommended Model

**Claude Sonnet 4** — Strong at stack trace analysis and identifying subtle code issues.

## Background

Someone made several changes to the codebase last sprint and introduced bugs. The application crashes on import, and even after fixing that, there are runtime issues.

## Bug Hunt

### Bug 1: Import Error (Severity: Critical)

**Symptom**: `python main.py` crashes immediately with an `ImportError`.

**Starting point**: Try running the application:

```bash
python -c "import qxm"
```

Use Copilot to:
1. Understand the error message
2. Find the root cause
3. Fix it

**Hint**: The error is in `qxm/__init__.py`. A module was renamed but the import wasn't updated.

### Bug 2: Configuration Type Error (Severity: High)

**Symptom**: After fixing Bug 1, the server fails to start with a type error from uvicorn.

**Starting point**: Run the application:

```bash
python main.py
```

Use Copilot to:
1. Inspect `settings.yaml`
2. Identify why the port value causes issues
3. Fix the configuration

**Hint**: Look at the YAML value for `port` — is it what you'd expect?

### Bug 3: Missing Await (Severity: High)

**Symptom**: Market data feed produces `<coroutine object>` instead of actual prices.

**Starting point**: Open `qxm/data/feed.py` and look at the `start()` method.

Use Copilot to:
1. Identify the async/await issue
2. Explain why the coroutine isn't being awaited
3. Fix the code

**Hint**: Ask Copilot *"Is there a missing await in MarketDataFeed.start()?"*

### Bug 4: Broken Decorator (Severity: Medium)

**Symptom**: Functions decorated with `@timed` lose their `__name__` and `__doc__` attributes. Test discovery is broken for decorated functions.

**Starting point**: Open `qxm/utils/decorators.py`.

Use Copilot to:
1. Identify what's missing from the `timed` decorator
2. Explain why this matters (introspection, docs, testing)
3. Fix it

**Hint**: Compare `timed` with `retry` — what does `retry` do differently?

### Bug 5: Renamed Module Reference (Severity: Medium)

**Symptom**: If Bug 1 is fixed by changing the import *target* rather than the *source*, some functionality might still reference the old name. Check for any other references to the old module name `qxm.data.handler`.

Use Copilot to:
1. Search the codebase for remaining references to the old name
2. Verify all imports are consistent

## Verification

After fixing all bugs:

```bash
# Should import without errors
python -c "import qxm; print(qxm.__version__)"

# Tests should pass (except known challenge-3 failures)
pytest tests/test_models.py -v
```

## Stretch Goals

- Use Copilot Agent Mode to fix all 5 bugs in a single prompt
- Ask Copilot to write a pre-commit hook that catches missing `@functools.wraps`
- Add type checking to `settings.yaml` loading to prevent the port bug class entirely
- Write a test that verifies decorated functions preserve their metadata

## Time

~45 minutes

---

*Next: [Challenge 3 — Mathematical Bug Fixes](./challenge_03_math_bugs.md)*
