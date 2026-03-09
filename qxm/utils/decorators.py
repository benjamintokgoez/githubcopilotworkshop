"""Decorators for cross-cutting concerns — timing, retries, caching,
and rate limiting.
"""

from __future__ import annotations

import asyncio
import logging
import time
from functools import lru_cache
from typing import Any, Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


# ---------------------------------------------------------------------------
# Timing decorator
# ---------------------------------------------------------------------------

def timed(func: F) -> F:
    """Log the execution time of a function.

    .. note::
        BUG (Challenge 2 — Debugging): Missing ``@functools.wraps(func)``
        causes the decorated function to lose its ``__name__``,
        ``__doc__``, and ``__module__`` attributes.  This breaks
        introspection, Sphinx docs, and test discovery.
    """
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed = time.perf_counter() - start
        logger.info(
            "%s executed in %.4f seconds",
            func.__name__,
            elapsed,
        )
        return result
    return wrapper  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Retry decorator
# ---------------------------------------------------------------------------

def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable[[F], F]:
    """Retry a function on failure with exponential backoff."""

    def decorator(func: F) -> F:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    logger.warning(
                        "%s attempt %d/%d failed: %s — retrying in %.1fs",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        current_delay,
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff
            raise last_exception  # type: ignore[misc]
        return wrapper  # type: ignore[return-value]
    return decorator


# ---------------------------------------------------------------------------
# Async retry
# ---------------------------------------------------------------------------

def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,),
) -> Callable:
    """Async version of retry with exponential backoff."""

    def decorator(func: Callable) -> Callable:
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Optional[Exception] = None
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    logger.warning(
                        "%s async attempt %d/%d failed: %s",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                    )
                    await asyncio.sleep(current_delay)
                    current_delay *= backoff
            raise last_exception  # type: ignore[misc]
        return wrapper
    return decorator


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, rate: float, burst: int = 1) -> None:
        self.rate = rate       # tokens per second
        self.burst = burst     # max tokens
        self._tokens = float(burst)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens.  Returns True if allowed."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return True
        return False

    def wait(self, tokens: int = 1) -> float:
        """Block until tokens are available.  Returns wait time."""
        self._refill()
        if self._tokens >= tokens:
            self._tokens -= tokens
            return 0.0
        deficit = tokens - self._tokens
        wait_time = deficit / self.rate
        time.sleep(wait_time)
        self._tokens = 0
        self._last_refill = time.monotonic()
        return wait_time
