"""Decorators and synchronization helpers for cross-cutting concerns."""

from __future__ import annotations

import asyncio
import inspect
import logging
import math
import threading
import time
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import ParamSpec, TypeVar, cast, overload

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


@overload
def timed[**P, R](func: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]: ...


@overload
def timed[**P, R](func: Callable[P, R]) -> Callable[P, R]: ...


def timed[**P, R](
    func: Callable[P, R],
) -> Callable[P, R] | Callable[P, Awaitable[R]]:
    """Log elapsed execution time for either a synchronous or async callable."""
    if inspect.iscoroutinefunction(func):
        async_func = cast(Callable[P, Awaitable[R]], func)

        @wraps(async_func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            start = time.perf_counter()
            try:
                return await async_func(*args, **kwargs)
            finally:
                logger.info(
                    "%s executed in %.4f seconds",
                    async_func.__name__,
                    time.perf_counter() - start,
                )

        return async_wrapper

    @wraps(func)
    def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            logger.info(
                "%s executed in %.4f seconds",
                func.__name__,
                time.perf_counter() - start,
            )

    return sync_wrapper


def _validate_retry_options(
    max_attempts: int,
    delay: float,
    backoff: float,
    exceptions: tuple[type[BaseException], ...],
) -> None:
    if isinstance(max_attempts, bool) or not isinstance(max_attempts, int) or max_attempts < 1:
        raise ValueError("max_attempts must be a positive integer")
    if (
        isinstance(delay, bool)
        or not isinstance(delay, (int, float))
        or not math.isfinite(delay)
        or delay < 0
    ):
        raise ValueError("delay must be finite and non-negative")
    if (
        isinstance(backoff, bool)
        or not isinstance(backoff, (int, float))
        or not math.isfinite(backoff)
        or backoff <= 0
    ):
        raise ValueError("backoff must be finite and positive")
    if (
        not isinstance(exceptions, tuple)
        or not exceptions
        or not all(
            isinstance(exception, type) and issubclass(exception, BaseException)
            for exception in exceptions
        )
    ):
        raise TypeError("exceptions must contain exception classes")


def retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Retry a synchronous callable with exponential backoff."""
    _validate_retry_options(max_attempts, delay, backoff, exceptions)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        if inspect.iscoroutinefunction(func):
            raise TypeError("retry cannot decorate async functions; use async_retry")

        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning(
                        "%s attempt %d/%d failed: %s; retrying in %.3fs",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        current_delay,
                    )
                    if current_delay:
                        time.sleep(current_delay)
                    current_delay *= backoff
            raise RuntimeError("unreachable retry state")

        return wrapper

    return decorator


def async_retry(
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple[type[BaseException], ...] = (Exception,),
) -> Callable[[Callable[P, Awaitable[R]]], Callable[P, Awaitable[R]]]:
    """Retry an async callable with non-blocking exponential backoff."""
    _validate_retry_options(max_attempts, delay, backoff, exceptions)

    def decorator(
        func: Callable[P, Awaitable[R]],
    ) -> Callable[P, Awaitable[R]]:
        if not inspect.iscoroutinefunction(func):
            raise TypeError("async_retry requires an async function")

        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return await func(*args, **kwargs)
                except exceptions as exc:
                    if attempt == max_attempts:
                        raise
                    logger.warning(
                        "%s attempt %d/%d failed: %s; retrying in %.3fs",
                        func.__name__,
                        attempt,
                        max_attempts,
                        exc,
                        current_delay,
                    )
                    if current_delay:
                        await asyncio.sleep(current_delay)
                    current_delay *= backoff
            raise RuntimeError("unreachable retry state")

        return wrapper

    return decorator


class RateLimiter:
    """Thread-safe token bucket with non-blocking ``acquire`` and blocking ``wait``."""

    def __init__(self, rate: float, burst: int = 1) -> None:
        if (
            isinstance(rate, bool)
            or not isinstance(rate, (int, float))
            or not math.isfinite(rate)
            or rate <= 0
        ):
            raise ValueError("rate must be finite and positive")
        if isinstance(burst, bool) or not isinstance(burst, int) or burst <= 0:
            raise ValueError("burst must be a positive integer")
        self.rate = float(rate)
        self.burst = burst
        self._tokens = float(burst)
        self._last_refill = time.monotonic()
        self._lock = threading.Lock()

    def _validate_tokens(self, tokens: float) -> float:
        if (
            isinstance(tokens, bool)
            or not isinstance(tokens, (int, float))
            or not math.isfinite(tokens)
            or tokens <= 0
        ):
            raise ValueError("tokens must be finite and positive")
        if tokens > self.burst:
            raise ValueError("tokens cannot exceed burst capacity")
        return float(tokens)

    def _refill_locked(self, now: float) -> None:
        elapsed = max(0.0, now - self._last_refill)
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate)
        self._last_refill = now

    def acquire(self, tokens: float = 1) -> bool:
        """Attempt to consume ``tokens`` immediately without blocking."""
        requested = self._validate_tokens(tokens)
        with self._lock:
            self._refill_locked(time.monotonic())
            if self._tokens < requested:
                return False
            self._tokens -= requested
            return True

    def wait(self, tokens: float = 1) -> float:
        """Block until ``tokens`` are consumed and return total seconds waited."""
        requested = self._validate_tokens(tokens)
        waited = 0.0
        while True:
            with self._lock:
                self._refill_locked(time.monotonic())
                if self._tokens >= requested:
                    self._tokens -= requested
                    return waited
                sleep_for = (requested - self._tokens) / self.rate
            time.sleep(sleep_for)
            waited += sleep_for
