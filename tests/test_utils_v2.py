from __future__ import annotations

import asyncio
import importlib
import pickle
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest
from pydantic import BaseModel

from mittelwerk.core import TelemetryReading
from mittelwerk.utils.decorators import RateLimiter, async_retry, retry, timed
from mittelwerk.utils.metrics import MetricsRegistry
from mittelwerk.utils.serializer import from_binary, from_json, to_binary, to_json
from security_check import scan_file, scan_source


def test_top_level_import_is_lightweight_and_coherent() -> None:
    sys.modules.pop("mittelwerk.api", None)
    sys.modules.pop("mittelwerk.mcp_server", None)
    mittelwerk = importlib.import_module("mittelwerk")

    assert mittelwerk.__version__ == "1.0.0"
    assert mittelwerk.WorkOrder is not None
    assert "TelemetryFeed" in mittelwerk.__all__
    assert "mittelwerk.api" not in sys.modules
    assert "mittelwerk.mcp_server" not in sys.modules


def test_serializes_pydantic_v2_and_slots_deterministically() -> None:
    class Quote(BaseModel):
        asset_id: str
        rate: Decimal
        timestamp: datetime

    @dataclass(slots=True)
    class Envelope:
        quote: Quote

    timestamp = datetime(2026, 8, 19, 9, 0, tzinfo=UTC)
    reading = TelemetryReading(
        "MWK", Decimal("10.1"), Decimal("10.2"), Decimal("10.15"), 7, timestamp
    )
    payload = {
        "reading": reading,
        "envelope": Envelope(Quote(asset_id="MWK", rate=Decimal("10.15"), timestamp=timestamp)),
    }

    encoded = to_json(payload)

    assert encoded == to_json(payload)
    assert '"rate":"10.15"' in encoded
    assert '"asset_id":"MWK"' in encoded
    assert '"timestamp":"2026-08-19T09:00:00Z"' in encoded


def test_binary_json_round_trip_and_rejection() -> None:
    payload = {"amount": Decimal("12.50"), "items": [1, 2]}
    encoded = to_binary(payload)

    assert encoded == b'{"amount":"12.50","items":[1,2]}'
    assert from_binary(encoded) == {"amount": "12.50", "items": [1, 2]}
    with pytest.raises(ValueError, match="UTF-8 JSON"):
        from_binary(b"\xff")
    with pytest.raises(ValueError):
        from_binary(pickle.dumps({"unsafe": True}))


@pytest.mark.parametrize("constant", ["NaN", "Infinity", "-Infinity"])
def test_json_decoding_rejects_non_finite_constants(constant: str) -> None:
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        from_json(f'{{"value":{constant}}}')
    with pytest.raises(ValueError, match="non-finite JSON constant"):
        from_binary(f'{{"value":{constant}}}'.encode())


def test_json_decoding_rejects_duplicate_object_keys() -> None:
    payload = '{"account":{"balance":1,"balance":2}}'

    with pytest.raises(ValueError, match="duplicate JSON object key"):
        from_json(payload)
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        from_binary(payload.encode("utf-8"))


def test_timed_preserves_metadata_and_awaits_async_function() -> None:
    @timed
    async def calculate(value: int) -> int:
        """Calculate asynchronously."""
        await asyncio.sleep(0)
        return value * 2

    assert calculate.__name__ == "calculate"
    assert calculate.__doc__ == "Calculate asynchronously."
    assert asyncio.run(calculate(4)) == 8


def test_retry_does_not_sleep_after_final_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sleeps: list[float] = []
    monkeypatch.setattr("mittelwerk.utils.decorators.time.sleep", sleeps.append)
    attempts = 0

    @retry(max_attempts=3, delay=0.25, backoff=2)
    def fail() -> None:
        nonlocal attempts
        attempts += 1
        raise RuntimeError("no")

    with pytest.raises(RuntimeError, match="no"):
        fail()
    assert fail.__name__ == "fail"
    assert attempts == 3
    assert sleeps == [0.25, 0.5]


def test_async_retry_preserves_metadata_and_retries() -> None:
    attempts = 0

    @async_retry(max_attempts=2, delay=0)
    async def eventually() -> str:
        """Return after one retry."""
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise LookupError("retry")
        return "ok"

    assert eventually.__name__ == "eventually"
    assert asyncio.run(eventually()) == "ok"
    assert attempts == 2


@pytest.mark.parametrize(
    ("rate", "burst"),
    [(0, 1), (-1, 1), (float("inf"), 1), (1, 0), (1, -1)],
)
def test_rate_limiter_validates_configuration(rate: float, burst: int) -> None:
    with pytest.raises(ValueError):
        RateLimiter(rate, burst)


def test_rate_limiter_non_blocking_acquire_validates_tokens() -> None:
    limiter = RateLimiter(1, burst=2)

    assert limiter.acquire(2)
    assert not limiter.acquire()
    with pytest.raises(ValueError):
        limiter.acquire(0)
    with pytest.raises(ValueError):
        limiter.wait(3)


def test_metrics_are_thread_safe_and_resettable() -> None:
    registry = MetricsRegistry()
    counter = registry.counter("work_orders")
    histogram = registry.histogram("latency", buckets=(1.0, 2.0))

    threads = [
        threading.Thread(target=lambda: [counter.inc() for _ in range(500)]) for _ in range(4)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    histogram.observe(0.5)
    histogram.observe(1.5)
    histogram.observe(3.0)

    snapshot = registry.snapshot()
    assert snapshot["counters"]["work_orders"] == 2000
    assert snapshot["histograms"]["latency"]["buckets"] == {
        "1.0": 1,
        "2.0": 2,
        "+Inf": 3,
    }
    assert snapshot["histograms"]["latency"]["count"] == 3

    registry.reset()
    assert registry.snapshot()["counters"]["work_orders"] == 0
    registry.clear()
    assert registry.snapshot() == {"counters": {}, "gauges": {}, "histograms": {}}


def test_security_scanner_distinguishes_simulation_from_key_generation() -> None:
    feed_path = Path(__file__).parents[1] / "mittelwerk" / "telemetry" / "feed.py"
    simulation_findings = scan_file(feed_path)
    key_findings = scan_source(
        """
import random

def generate_api_key():
    return ''.join(random.choice('abcdef0123456789') for _ in range(32))
""",
        "key_fixture.py",
    )

    assert not any(finding.category == "Weak Key Randomness" for finding in simulation_findings)
    assert any(
        finding.category == "Weak Key Randomness" and finding.severity == "HIGH"
        for finding in key_findings
    )


def test_security_scanner_fails_closed_on_parse_error() -> None:
    findings = scan_source("def broken(:\n    pass", "broken.py")

    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert findings[0].category == "Scanner Integrity"
    assert findings[0].file == "broken.py"
    assert "scan incomplete" in findings[0].description


@pytest.mark.parametrize(
    ("read_error", "description"),
    [
        (PermissionError("denied"), "could not be read"),
        (
            UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid"),
            "not valid UTF-8",
        ),
    ],
)
def test_security_scanner_fails_closed_on_read_error(
    monkeypatch: pytest.MonkeyPatch,
    read_error: OSError | UnicodeDecodeError,
    description: str,
) -> None:
    def fail_read_text(path: Path, encoding: str) -> str:
        raise read_error

    monkeypatch.setattr(Path, "read_text", fail_read_text)

    findings = scan_file(Path("unreadable.py"))

    assert len(findings) == 1
    assert findings[0].severity == "HIGH"
    assert findings[0].category == "Scanner Integrity"
    assert findings[0].file == "unreadable.py"
    assert description in findings[0].description
