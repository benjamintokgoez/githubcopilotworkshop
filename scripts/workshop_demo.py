"""Optional, read-only workshop entry point: captured output or a local domain run."""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mittelwerk.core.models import ServiceAssignment, Workload, WorkOrder

ROOT = Path(__file__).resolve().parent.parent
CAPTURE_PATH = ROOT / "docs" / "fixtures" / "simulator_first_win.txt"
FIXTURE_TIME = datetime(2026, 1, 15, 8, tzinfo=UTC)


@dataclass(frozen=True)
class DemoResult:
    """Detached domain records; generated assignment metadata stays unmodified."""

    prepared_request: WorkOrder
    accepted_offer: WorkOrder
    request: WorkOrder
    offer: WorkOrder
    assignment: ServiceAssignment
    requester_workload: Workload
    provider_workload: Workload
    event_types: tuple[str, ...]
    currency: str


def captured_transcript() -> str:
    """Read the checked-in example without importing any application dependency."""
    return CAPTURE_PATH.read_text(encoding="utf-8")


async def run_demo() -> DemoResult:
    """Execute fresh domain objects, retain no shared state, and stop the event bus."""
    from mittelwerk.core.engine import DispatchEngine
    from mittelwerk.core.events import EventBus
    from mittelwerk.core.models import (
        DispatchSide,
        Equipment,
        EquipmentCategory,
        WorkOrder,
        WorkOrderMode,
    )

    equipment = Equipment(
        asset_id="DEMO-CNC-01",
        name="Synthetic demonstration machine",
        equipment_type=EquipmentCategory.CNC_MACHINE,
        service_interval_days=30,
        hourly_service_rate=Decimal("85.00"),
        rate_increment=Decimal("0.50"),
        hour_lot_size=Decimal("0.25"),
        currency="EUR",
        site_code="DEMO-SITE",
    )
    request = WorkOrder(
        work_order_id="DEMO-REQUEST-001",
        organization_id="demo-requester",
        asset_id=equipment.asset_id,
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=Decimal("2.50"),
        max_hourly_rate=Decimal("100.00"),
        created_at=FIXTURE_TIME,
    )
    prepared_request = request.model_copy(deep=True)
    offer = WorkOrder(
        work_order_id="DEMO-OFFER-001",
        organization_id="demo-provider",
        asset_id=equipment.asset_id,
        side=DispatchSide.OFFER,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=Decimal("3.00"),
        max_hourly_rate=Decimal("80.50"),
        created_at=FIXTURE_TIME,
    )
    bus = EventBus()
    engine = DispatchEngine(bus, {equipment.asset_id: equipment})
    try:
        await bus.start()
        # Publish capacity before submitting the prepared request, as shown in the guide.
        capacity = await engine.submit_work_order(offer)
        if not capacity.accepted:
            raise RuntimeError(f"Demonstration offer rejected: {capacity.rejection_reason}")
        accepted_offer = offer.model_copy(deep=True)
        dispatched = await engine.submit_work_order(request)
        if not dispatched.accepted:
            raise RuntimeError(f"Demonstration request rejected: {dispatched.rejection_reason}")
        if len(dispatched.assignments) != 1:
            raise RuntimeError("Demonstration expected exactly one service assignment")
        requester_workload = engine.workload_manager.peek_workload(
            request.organization_id, equipment.asset_id
        )
        provider_workload = engine.workload_manager.peek_workload(
            offer.organization_id, equipment.asset_id
        )
        if requester_workload is None or provider_workload is None:
            raise RuntimeError("Demonstration assignment did not create both workloads")
        return DemoResult(
            prepared_request=prepared_request,
            accepted_offer=accepted_offer,
            request=request.model_copy(deep=True),
            offer=offer.model_copy(deep=True),
            assignment=dispatched.assignments[0].model_copy(deep=True),
            requester_workload=requester_workload.model_copy(deep=True),
            provider_workload=provider_workload.model_copy(deep=True),
            event_types=tuple(event.event_type.value for event in bus.replay()),
            currency=equipment.currency,
        )
    finally:
        await bus.stop()


def render_transcript(result: DemoResult) -> str:
    """Render exact domain quantities, omitting variable execution IDs and clocks."""
    request = result.request
    offer = result.offer
    assignment = result.assignment
    currency = result.currency
    return "\n".join(
        [
            "MittelWerk optional first win - synthetic field-service simulation",
            "",
            "1. Prepare a service request (not submitted yet)",
            f"   Asset: {request.asset_id} | organisation: {request.organization_id}",
            f"   {request.work_order_id}: {request.requested_hours:.2f} h, "
            f"cap {request.max_hourly_rate:.2f} {currency}/h",
            f"   Created: {request.created_at.isoformat()} (UTC fixture)",
            "",
            "2. Offer provider capacity",
            f"   {offer.work_order_id} / {offer.organization_id}: "
            f"{offer.requested_hours:.2f} h at {offer.max_hourly_rate:.2f} {currency}/h"
            f" -> {result.accepted_offer.status.value}",
            "",
            "3. Submit the request and inspect the assignment",
            f"   {request.work_order_id} -> {request.status.value}",
            f"   {offer.work_order_id} -> {offer.status.value}",
            f"   Assigned: {assignment.hours:.2f} h at {assignment.hourly_rate:.2f} {currency}/h",
            f"   Unassigned request: {request.remaining_hours:.2f} h"
            f" | available provider capacity: {offer.remaining_hours:.2f} h",
            "",
            "4. Read workload and estimated service cost",
            f"   Requester net workload: {result.requester_workload.net_hours:+.2f} h",
            f"   Provider net workload: {result.provider_workload.net_hours:+.2f} h",
            f"   Estimated assigned service cost: {assignment.hours:.2f} h"
            f" x {assignment.hourly_rate:.2f} {currency}/h"
            f" = {assignment.total_cost:.2f} {currency}",
            f"   Requester workload revaluation cost: "
            f"{result.requester_workload.total_cost:.2f} {currency} (not an invoice total)",
            "",
            "5. Explain the result",
            f"   The accepted offer is {assignment.hourly_rate:.2f} {currency}/h;"
            f" the request cap is {request.max_hourly_rate:.2f} {currency}/h.",
            "   Assigned means allocated, not completed maintenance.",
            "   No state is sent to the application, dashboard, or scenario workspaces.",
            "",
        ]
    )


def main(argv: Sequence[str] | None = None) -> int:
    """Print a captured journey by default; opt in to real local domain execution."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run",
        action="store_true",
        help="execute the installed domain in memory; no network, server, or database",
    )
    args = parser.parse_args(argv)
    if args.run:
        transcript = render_transcript(asyncio.run(run_demo()))
        print("Mode: executed locally; event bus stopped; no persistent state.", file=sys.stderr)
    else:
        transcript = captured_transcript()
        print("Mode: captured; no domain code executed.", file=sys.stderr)
    print(transcript, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
