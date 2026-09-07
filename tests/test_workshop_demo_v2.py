"""The optional first win executes real domain behavior and has a faithful capture."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from mittelwerk.core.engine import DispatchEngine, DispatchResult
from mittelwerk.core.events import EventBus
from mittelwerk.core.models import DispatchSide, WorkOrder, WorkOrderStatus
from scripts import workshop_demo

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "scripts" / "workshop_demo.py"


async def test_demonstration_covers_request_capacity_assignment_and_workloads() -> None:
    result = await workshop_demo.run_demo()

    assert result.prepared_request.status is WorkOrderStatus.NEW
    assert result.prepared_request.assigned_hours == Decimal("0")
    assert result.accepted_offer.status is WorkOrderStatus.ACCEPTED
    assert result.accepted_offer.assigned_hours == Decimal("0")
    assert result.request.status is WorkOrderStatus.ASSIGNED
    assert result.offer.status is WorkOrderStatus.PARTIALLY_ASSIGNED
    assert result.request.remaining_hours == Decimal("0")
    assert result.offer.remaining_hours == Decimal("0.50")
    assert result.assignment.requester_work_order_id == result.request.work_order_id
    assert result.assignment.provider_work_order_id == result.offer.work_order_id
    assert result.assignment.initiating_side is DispatchSide.REQUEST
    assert result.requester_workload.organization_id == result.request.organization_id
    assert result.provider_workload.organization_id == result.offer.organization_id
    assert result.requester_workload.net_hours == Decimal("2.50")
    assert result.provider_workload.net_hours == Decimal("-2.50")
    assert result.event_types == (
        "WORK_ORDER_SUBMITTED",
        "WORK_ORDER_ACCEPTED",
        "WORK_ORDER_SUBMITTED",
        "WORK_ORDER_ACCEPTED",
        "ASSIGNMENT_EXECUTED",
        "WORKLOAD_UPDATED",
        "WORK_ORDER_PARTIALLY_ASSIGNED",
        "WORK_ORDER_ASSIGNED",
    )


async def test_demonstration_preserves_decimal_provider_rate_and_cost_meanings() -> None:
    result = await workshop_demo.run_demo()

    assert result.request.max_hourly_rate == Decimal("100.00")
    assert result.assignment.hourly_rate == result.offer.max_hourly_rate == Decimal("80.50")
    assert result.assignment.hourly_rate != result.request.max_hourly_rate
    assert result.assignment.hours == Decimal("2.50")
    assert result.assignment.total_cost == Decimal("201.25")
    assert result.requester_workload.total_cost == Decimal("0")
    assert result.provider_workload.total_cost == Decimal("0")
    assert result.currency == "EUR"
    for value in (
        result.assignment.hourly_rate,
        result.assignment.hours,
        result.assignment.total_cost,
        result.requester_workload.net_hours,
        result.provider_workload.net_hours,
        result.requester_workload.total_cost,
    ):
        assert isinstance(value, Decimal)
    payload = result.assignment.model_dump(mode="json")
    assert payload["hourly_rate"] == "80.50"
    assert payload["hours"] == "2.50"


async def test_demonstration_uses_fixed_input_times_and_preserves_real_utc_metadata() -> None:
    before = datetime.now(UTC)
    result = await workshop_demo.run_demo()
    after = datetime.now(UTC)

    assert result.request.created_at == datetime(2026, 1, 15, 8, tzinfo=UTC)
    assert result.offer.created_at == result.request.created_at
    for timestamp in (
        result.assignment.timestamp,
        result.request.updated_at,
        result.offer.updated_at,
        result.requester_workload.last_updated,
        result.provider_workload.last_updated,
    ):
        assert timestamp is not None
        assert timestamp.tzinfo is UTC
        assert before <= timestamp <= after
    transcript = workshop_demo.render_transcript(result)
    assert "2026-01-15T08:00:00+00:00 (UTC fixture)" in transcript
    assert result.assignment.assignment_id not in transcript
    assert result.assignment.timestamp.isoformat() not in transcript


async def test_repeated_and_concurrent_runs_are_isolated_and_match_capture() -> None:
    first, second = await asyncio.gather(workshop_demo.run_demo(), workshop_demo.run_demo())
    expected = workshop_demo.captured_transcript()
    assert workshop_demo.render_transcript(first) == expected
    assert workshop_demo.render_transcript(second) == expected
    assert first.assignment.assignment_id != second.assignment.assignment_id
    first.request.assigned_hours = Decimal("0")
    first.requester_workload.net_hours = Decimal("0")
    assert second.request.assigned_hours == Decimal("2.50")
    assert second.requester_workload.net_hours == Decimal("2.50")
    third = await workshop_demo.run_demo()
    assert workshop_demo.render_transcript(third) == expected


@pytest.mark.parametrize("fail_submission", [0, 1, 2])
async def test_event_bus_stops_on_success_and_failure(
    monkeypatch: pytest.MonkeyPatch, fail_submission: int
) -> None:
    buses: list[EventBus] = []
    submitted = 0
    original_start = EventBus.start
    original_submit = DispatchEngine.submit_work_order

    async def start(bus: EventBus) -> None:
        buses.append(bus)
        await original_start(bus)

    async def submit(engine: DispatchEngine, order: WorkOrder) -> DispatchResult:
        nonlocal submitted
        submitted += 1
        if submitted == fail_submission:
            raise RuntimeError("Synthetic demonstration failure")
        return await original_submit(engine, order)

    monkeypatch.setattr(EventBus, "start", start)
    monkeypatch.setattr(DispatchEngine, "submit_work_order", submit)
    tasks_before = asyncio.all_tasks()
    if fail_submission:
        with pytest.raises(RuntimeError, match="Synthetic demonstration failure"):
            await workshop_demo.run_demo()
    else:
        await workshop_demo.run_demo()
    assert len(buses) == 1
    assert not buses[0].is_running
    assert asyncio.all_tasks() == tasks_before


def test_captured_cli_needs_no_site_packages_and_identifies_its_mode() -> None:
    captured = subprocess.run(  # noqa: S603 - fixed argv, no shell, checkout-owned path
        [sys.executable, "-B", "-S", str(SCRIPT)],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert captured.stdout == workshop_demo.captured_transcript()
    assert captured.stderr == "Mode: captured; no domain code executed.\n"


def test_executed_cli_matches_capture_without_files_network_or_database() -> None:
    guarded_run = """
import os
import runpy
import sys

def guard(event, args):
    if event in {
        "socket.bind", "socket.connect", "socket.getaddrinfo", "sqlite3.connect",
        "os.mkdir", "os.remove", "os.rename", "os.rmdir", "os.truncate",
    }:
        raise AssertionError("Unexpected side effect: " + event)
    if event == "open":
        flags = args[2]
        if isinstance(flags, int) and flags & (
            os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND
        ):
            raise AssertionError("Unexpected file write: " + str(args[0]))

sys.addaudithook(guard)
sys.argv = ["scripts/workshop_demo.py", "--run"]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
    executed = subprocess.run(  # noqa: S603 - fixed argv and source, no shell
        [sys.executable, "-B", "-c", guarded_run],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert executed.stdout == workshop_demo.captured_transcript()
    assert executed.stderr == ("Mode: executed locally; event bus stopped; no persistent state.\n")


def test_cli_rejects_unknown_arguments_without_printing_capture() -> None:
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell, checkout-owned path
        [sys.executable, "-B", str(SCRIPT), "--unknown"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
    assert result.stdout == ""
    assert "unrecognized arguments" in result.stderr
