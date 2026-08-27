"""Focused contract tests for the MittelWerk MCP v2 server."""

from __future__ import annotations

import inspect
import json
import subprocess
import sys
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from mcp import Client, MCPError
from mcp.types import CallToolResult

from mittelwerk import __version__
from mittelwerk.core.engine import DispatchEngine
from mittelwerk.core.events import EventBus
from mittelwerk.core.models import (
    DispatchSide,
    DispatchWindow,
    Equipment,
    EquipmentCategory,
    WorkOrder,
    WorkOrderMode,
    WorkOrderStatus,
)
from mittelwerk.mcp_server import server as server_module
from mittelwerk.mcp_server.server import create_default_mcp_server, create_mcp_server


def _runtime(
    *,
    rate_increment: Decimal = Decimal("0.50"),
    hour_lot_size: Decimal = Decimal("0.25"),
) -> tuple[DispatchEngine, dict[str, Equipment]]:
    equipment = {
        "PRESS-17": Equipment(
            asset_id="PRESS-17",
            name="Hydraulic Press 17",
            equipment_type=EquipmentCategory.HYDRAULIC_PRESS,
            service_interval_days=30,
            hourly_service_rate=Decimal("120.00"),
            rate_increment=rate_increment,
            hour_lot_size=hour_lot_size,
            currency="EUR",
            site_code="MW-MUC",
        ),
        "PUMP-04": Equipment(
            asset_id="PUMP-04",
            name="Cooling Pump 04",
            equipment_type=EquipmentCategory.COMPRESSOR,
            service_interval_days=14,
            hourly_service_rate=Decimal("95.00"),
            rate_increment=rate_increment,
            hour_lot_size=hour_lot_size,
            currency="EUR",
            site_code="MW-HAM",
        ),
    }
    return DispatchEngine(event_bus=EventBus(), equipment=equipment), equipment


def _structured(result: CallToolResult) -> dict[str, object]:
    payload = result.structured_content
    assert isinstance(payload, dict)
    return payload


def _assert_utc(value: object) -> None:
    assert isinstance(value, str)
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    assert parsed.utcoffset() == timedelta(0)


def _equipment_payload(asset_id: str = "PRESS-17") -> dict[str, Any]:
    return {
        "asset_id": asset_id,
        "name": f"Synthetic {asset_id}",
        "equipment_type": "HYDRAULIC_PRESS",
        "service_interval_days": 30,
        "hourly_service_rate": "120.00",
        "rate_increment": "0.50",
        "hour_lot_size": "0.25",
        "currency": "EUR",
        "site_code": "MW-MUC",
    }


@pytest.mark.asyncio
async def test_read_only_surface_schemas_annotations_and_write_absence() -> None:
    engine, equipment = _runtime()
    server = create_mcp_server(engine, equipment)

    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
        tools = {tool.name: tool for tool in listed.tools}

        assert set(tools) == {
            "calculate_service_risk",
            "get_dispatch_queue",
            "list_equipment",
        }
        for tool in tools.values():
            assert tool.annotations is not None
            assert tool.annotations.read_only_hint is True
            assert tool.annotations.destructive_hint is False
            assert tool.annotations.idempotent_hint is True
            assert tool.annotations.open_world_hint is False

        assert tools["list_equipment"].input_schema["properties"]["limit"]["maximum"] == 50
        assert tools["get_dispatch_queue"].input_schema["properties"]["depth"]["maximum"] == 20
        risk_schema = json.dumps(tools["calculate_service_risk"].input_schema)
        assert '"maxItems": 256' in risk_schema

        invalid_depth = await client.call_tool(
            "get_dispatch_queue", {"asset_id": "PRESS-17", "depth": 21}
        )
        assert invalid_depth.is_error is True
        oversized_history = await client.call_tool(
            "calculate_service_risk",
            {
                "open_backlog_hours": "1000",
                "backlog_history": ["-1"] * 257,
            },
        )
        assert oversized_history.is_error is True

        missing_tool = await client.call_tool(
            "submit_work_order",
            {
                "asset_id": "PRESS-17",
                "side": "REQUEST",
                "requested_hours": "4",
                "max_hourly_rate": "120.00",
            },
        )
        assert missing_tool.is_error is True
        assert missing_tool.structured_content is None
        assert len(missing_tool.content) == 1
        assert missing_tool.content[0].text == "Unknown tool: submit_work_order"


@pytest.mark.asyncio
async def test_default_factory_loads_supplied_configuration_read_only(tmp_path: Path) -> None:
    equipment_path = tmp_path / "equipment.json"
    equipment_path.write_text(
        json.dumps([_equipment_payload("PRESS-17"), _equipment_payload("PUMP-04")]),
        encoding="utf-8",
    )

    server = create_default_mcp_server(equipment_path=equipment_path)
    assert server.version == __version__

    async with Client(server, raise_exceptions=True) as client:
        tools = {tool.name for tool in (await client.list_tools()).tools}
        listed = _structured(await client.call_tool("list_equipment", {"limit": 50}))

    assert tools == {"calculate_service_risk", "get_dispatch_queue", "list_equipment"}
    assert listed["total"] == 2
    assert listed["environment"] == "SIMULATION"


def test_server_construction_requires_matching_equipment_mapping() -> None:
    engine, equipment = _runtime()
    mismatched = dict(equipment)
    mismatched["PUMP-04"] = Equipment(
        asset_id="PUMP-04",
        name="Cooling Pump 04",
        equipment_type=EquipmentCategory.COMPRESSOR,
        service_interval_days=14,
        hourly_service_rate=Decimal("95.00"),
        rate_increment=Decimal("0.50"),
        hour_lot_size=Decimal("0.25"),
        currency="EUR",
        site_code="MW-BER",
    )

    with pytest.raises(ValueError, match="must match the MCP equipment mapping"):
        create_mcp_server(engine, mismatched)


@pytest.mark.asyncio
async def test_empty_dispatch_queue_returns_known_asset_with_no_levels() -> None:
    engine, equipment = _runtime()
    server = create_mcp_server(engine, equipment)

    async with Client(server, raise_exceptions=True) as client:
        snapshot = _structured(
            await client.call_tool("get_dispatch_queue", {"asset_id": "press-17", "depth": 5})
        )

    assert snapshot["asset_id"] == "PRESS-17"
    assert snapshot["best_request_rate"] is None
    assert snapshot["best_offer_rate"] is None
    assert snapshot["rate_spread"] is None
    assert snapshot["representative_rate"] is None
    assert snapshot["requests"] == []
    assert snapshot["offers"] == []
    _assert_utc(snapshot["as_of"])


@pytest.mark.asyncio
async def test_decimal_utc_and_bounded_read_results() -> None:
    engine, equipment = _runtime(hour_lot_size=Decimal("0.001"))
    await engine.submit_work_order(
        WorkOrder(
            work_order_id="request-one",
            organization_id="maker-org",
            asset_id="PRESS-17",
            side=DispatchSide.REQUEST,
            mode=WorkOrderMode.RATE_CAPPED,
            requested_hours=Decimal("2.500"),
            max_hourly_rate=Decimal("120.5000"),
            dispatch_window=DispatchWindow.OPEN,
        )
    )
    await engine.submit_work_order(
        WorkOrder(
            work_order_id="request-two",
            organization_id="maker-org",
            asset_id="PRESS-17",
            side=DispatchSide.REQUEST,
            mode=WorkOrderMode.RATE_CAPPED,
            requested_hours=Decimal("1.000"),
            max_hourly_rate=Decimal("120.0000"),
            dispatch_window=DispatchWindow.OPEN,
        )
    )
    server = create_mcp_server(engine, equipment)

    async with Client(server, raise_exceptions=True) as client:
        listed = _structured(await client.call_tool("list_equipment", {"limit": 1}))
        assert listed["returned"] == 1
        assert len(listed["equipment"]) == 1
        first_equipment = listed["equipment"][0]
        assert isinstance(first_equipment, dict)
        assert first_equipment["hour_lot_size"] == "0.001"

        snapshot = _structured(
            await client.call_tool("get_dispatch_queue", {"asset_id": "press-17", "depth": 1})
        )
        assert snapshot["asset_id"] == "PRESS-17"
        assert len(snapshot["requests"]) == 1
        assert snapshot["requests"][0]["rate"] == "120.5000"
        assert snapshot["requests"][0]["hours"] == "2.500"
        _assert_utc(snapshot["as_of"])

        risk = _structured(
            await client.call_tool(
                "calculate_service_risk",
                {
                    "open_backlog_hours": "1000.00",
                    "hours_volatility": "0.02",
                    "backlog_history": ["10.00", "-25.50", "-5.25"],
                    "confidence": "0.95",
                    "horizon_days": 1,
                },
            )
        )
        assert isinstance(risk["parametric_backlog_risk"], str)
        assert isinstance(risk["historical_backlog_risk"], str)
        assert isinstance(risk["conditional_backlog_risk"], str)
        assert Decimal(risk["parametric_backlog_risk"]) >= 0
        assert Decimal(risk["historical_backlog_risk"]) >= 0
        assert Decimal(risk["conditional_backlog_risk"]) >= 0
        _assert_utc(risk["as_of"])


@pytest.mark.asyncio
async def test_calculate_service_risk_requires_at_least_one_input() -> None:
    engine, equipment = _runtime()
    server = create_mcp_server(engine, equipment)

    async with Client(server, raise_exceptions=True) as client:
        with pytest.raises(MCPError, match="Provide hours_volatility, backlog_history, or both"):
            await client.call_tool(
                "calculate_service_risk",
                {"open_backlog_hours": "1000.00"},
            )


@pytest.mark.asyncio
async def test_unknown_assets_are_protocol_errors() -> None:
    engine, equipment = _runtime()
    server = create_mcp_server(engine, equipment)

    async with Client(server, raise_exceptions=True) as client:
        with pytest.raises(MCPError, match="Unknown simulated asset: NOPE"):
            await client.call_tool("get_dispatch_queue", {"asset_id": "NOPE"})


def test_writes_require_a_conservative_bound_organization_identity() -> None:
    engine, equipment = _runtime()
    invalid_organization_ids = (
        None,
        "",
        " leading",
        "trailing ",
        "contains space",
        "forged\nentry",
        "control\x00character",
        "non-ascii-\N{LATIN SMALL LETTER E WITH ACUTE}",
        "x" * 65,
    )
    for organization_id in invalid_organization_ids:
        with pytest.raises(ValueError, match="organization_id"):
            create_mcp_server(
                engine,
                equipment,
                allow_writes=True,
                organization_id=organization_id,
            )


@pytest.mark.asyncio
async def test_opt_in_writes_execute_cancel_reject_and_enforce_identity() -> None:
    engine, equipment = _runtime()
    await engine.submit_work_order(
        WorkOrder(
            work_order_id="foreign-offer",
            organization_id="external-provider",
            asset_id="PRESS-17",
            side=DispatchSide.OFFER,
            mode=WorkOrderMode.RATE_CAPPED,
            requested_hours=Decimal("2"),
            max_hourly_rate=Decimal("119.50"),
            dispatch_window=DispatchWindow.OPEN,
        )
    )
    server = create_mcp_server(
        engine,
        equipment,
        allow_writes=True,
        organization_id="workshop-org",
    )

    async with Client(server, raise_exceptions=True) as client:
        listed = await client.list_tools()
        tools = {tool.name: tool for tool in listed.tools}
        assert set(tools) == {
            "calculate_service_risk",
            "cancel_work_order",
            "get_dispatch_queue",
            "list_equipment",
            "submit_work_order",
        }
        submit_schema = tools["submit_work_order"].input_schema
        assert "organization_id" not in submit_schema["properties"]
        assert submit_schema["$defs"]["SupportedWorkOrderMode"]["enum"] == [
            "RATE_CAPPED",
            "ANY_RATE",
        ]
        assert submit_schema["$defs"]["SupportedDispatchWindow"]["enum"] == [
            "OPEN",
            "IMMEDIATE",
            "COMPLETE",
        ]
        hours_schema = submit_schema["properties"]["requested_hours"]
        assert hours_schema["anyOf"][0]["maximum"] == 10_000
        assert tools["submit_work_order"].output_schema is not None
        output_properties = tools["submit_work_order"].output_schema["properties"]
        assert output_properties["assignments"]["maxItems"] == 100
        assert output_properties["returned_assignment_count"]["maximum"] == 100
        assert output_properties["rejection_reason"]["anyOf"][0]["maxLength"] == 256
        assert tools["submit_work_order"].annotations is not None
        assert tools["submit_work_order"].annotations.read_only_hint is False
        assert tools["submit_work_order"].annotations.destructive_hint is True
        assert tools["submit_work_order"].annotations.idempotent_hint is False
        assert tools["submit_work_order"].annotations.open_world_hint is False
        assert tools["cancel_work_order"].annotations is not None
        assert tools["cancel_work_order"].annotations.idempotent_hint is True

        work_order_count = engine.work_order_count
        oversized = await client.call_tool(
            "submit_work_order",
            {
                "work_order_id": "mcp-oversized",
                "asset_id": "PRESS-17",
                "side": "REQUEST",
                "requested_hours": "10001",
                "max_hourly_rate": "120.00",
            },
        )
        assert oversized.is_error is True
        assert engine.work_order_count == work_order_count

        with pytest.raises(MCPError, match="RATE_CAPPED work orders require a max_hourly_rate"):
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "missing-rate",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "1",
                },
            )
        with pytest.raises(
            MCPError, match="ANY_RATE work orders must not include a max_hourly_rate"
        ):
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "any-rate-with-cap",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "1",
                    "mode": "ANY_RATE",
                    "max_hourly_rate": "120.00",
                },
            )

        fill = _structured(
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "mcp-fill",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "1",
                    "mode": "RATE_CAPPED",
                    "max_hourly_rate": "120.00",
                },
            )
        )
        assert fill["status"] == WorkOrderStatus.ASSIGNED.value
        assert fill["accepted"] is True
        assert fill["rejection_reason"] is None
        assert fill["assignment_count"] == 1
        assert fill["returned_assignment_count"] == 1
        assert fill["assignments_truncated"] is False
        assert fill["assignments"][0]["hourly_rate"] == "119.50"
        assert fill["assignments"][0]["hours"] == "1"
        _assert_utc(fill["assignments"][0]["timestamp"])

        resting = _structured(
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "mcp-resting",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "2",
                    "max_hourly_rate": "100.00",
                },
            )
        )
        assert resting["status"] == WorkOrderStatus.ACCEPTED.value
        cancelled = _structured(
            await client.call_tool("cancel_work_order", {"work_order_id": "mcp-resting"})
        )
        assert cancelled["status"] == WorkOrderStatus.CANCELLED.value
        _assert_utc(cancelled["updated_at"])

        rejected = _structured(
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "mcp-rejected",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "1.10",
                    "max_hourly_rate": "90.00",
                },
            )
        )
        assert rejected["status"] == WorkOrderStatus.REJECTED.value
        assert rejected["accepted"] is False
        assert rejected["rejection_reason"] == "Hours 1.10 is not a multiple of hour lot size 0.25"
        assert rejected["assignment_count"] == 0
        assert rejected["returned_assignment_count"] == 0

        with pytest.raises(MCPError, match="already been submitted"):
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "mcp-rejected",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "1",
                    "max_hourly_rate": "90.00",
                },
            )

        with pytest.raises(MCPError, match="not found for this MCP organization"):
            await client.call_tool("cancel_work_order", {"work_order_id": "foreign-offer"})
        queue = engine.get_queue("PRESS-17")
        assert queue is not None
        assert queue.contains("foreign-offer")


def test_rejection_reason_is_bounded_without_losing_engine_context() -> None:
    work_order = WorkOrder(
        work_order_id="bounded-rejection",
        organization_id="mcp-org",
        asset_id="PRESS-17",
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=Decimal("1"),
        max_hourly_rate=Decimal("90"),
        dispatch_window=DispatchWindow.OPEN,
        status=WorkOrderStatus.REJECTED,
    )
    result = server_module._work_order_result(
        server_module.DispatchResult(
            work_order=work_order,
            rejection_reason="dispatch policy: " + "x" * 300,
        )
    )

    assert result.rejection_reason is not None
    assert result.rejection_reason.startswith("dispatch policy: ")
    assert result.rejection_reason.endswith("...")
    assert len(result.rejection_reason) == server_module.MAX_REJECTION_REASON_LENGTH


@pytest.mark.asyncio
async def test_submit_work_order_bounds_serialized_assignments_without_hiding_execution() -> None:
    engine, equipment = _runtime()
    for index in range(105):
        await engine.submit_work_order(
            WorkOrder(
                work_order_id=f"maker-{index:03}",
                organization_id=f"maker-org-{index:03}",
                asset_id="PRESS-17",
                side=DispatchSide.OFFER,
                mode=WorkOrderMode.RATE_CAPPED,
                requested_hours=Decimal("1.000"),
                max_hourly_rate=Decimal("99.50"),
                dispatch_window=DispatchWindow.OPEN,
            )
        )

    server = create_mcp_server(
        engine,
        equipment,
        allow_writes=True,
        organization_id="bounded-output-org",
    )
    async with Client(server, raise_exceptions=True) as client:
        result = _structured(
            await client.call_tool(
                "submit_work_order",
                {
                    "work_order_id": "large-fill",
                    "asset_id": "PRESS-17",
                    "side": "REQUEST",
                    "requested_hours": "105.000",
                    "max_hourly_rate": "100.00",
                },
            )
        )

    assert result["status"] == WorkOrderStatus.ASSIGNED.value
    assert result["assigned_hours"] == "105.000"
    assert result["assignment_count"] == 105
    assert result["returned_assignment_count"] == 100
    assert result["assignments_truncated"] is True
    assert len(result["assignments"]) == 100
    assert len(engine.assignment_log) == 105
    for retained, executed in zip(result["assignments"], engine.assignment_log[:100], strict=True):
        assert retained["hourly_rate"] == str(executed.hourly_rate)
        assert retained["hours"] == str(executed.hours)
        assert retained["timestamp"] == executed.timestamp.isoformat().replace("+00:00", "Z")


@pytest.mark.asyncio
async def test_server_instances_do_not_share_runtime_state() -> None:
    engine_a, equipment_a = _runtime()
    engine_b, equipment_b = _runtime()
    server_a = create_mcp_server(
        engine_a,
        equipment_a,
        allow_writes=True,
        organization_id="org-a",
    )
    server_b = create_mcp_server(
        engine_b,
        equipment_b,
        allow_writes=True,
        organization_id="org-b",
    )

    async with (
        Client(server_a, raise_exceptions=True) as client_a,
        Client(server_b, raise_exceptions=True) as client_b,
    ):
        await client_a.call_tool(
            "submit_work_order",
            {
                "work_order_id": "isolated-order",
                "asset_id": "PRESS-17",
                "side": "REQUEST",
                "requested_hours": "1",
                "max_hourly_rate": "100.00",
            },
        )
        snapshot_a = _structured(
            await client_a.call_tool("get_dispatch_queue", {"asset_id": "PRESS-17"})
        )
        snapshot_b = _structured(
            await client_b.call_tool("get_dispatch_queue", {"asset_id": "PRESS-17"})
        )

    assert len(snapshot_a["requests"]) == 1
    assert snapshot_b["requests"] == []
    assert engine_a.work_order_count == 1
    assert engine_b.work_order_count == 0


def test_load_equipment_validates_missing_malformed_duplicate_and_empty_files(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing-equipment.json"
    with pytest.raises(FileNotFoundError, match="Equipment file not found"):
        server_module._load_equipment(missing_path)

    malformed_path = tmp_path / "malformed-equipment.json"
    malformed_path.write_text(json.dumps({"asset_id": "PRESS-17"}), encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON array"):
        server_module._load_equipment(malformed_path)

    duplicate_path = tmp_path / "duplicate-equipment.json"
    duplicate_path.write_text(
        json.dumps([_equipment_payload("PRESS-17"), _equipment_payload("PRESS-17")]),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="Duplicate equipment asset_id: PRESS-17"):
        server_module._load_equipment(duplicate_path)

    empty_path = tmp_path / "empty-equipment.json"
    empty_path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="contains no equipment"):
        server_module._load_equipment(empty_path)


def test_import_is_silent_and_entrypoint_uses_sync_run(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.run(
        [sys.executable, "-c", "import mittelwerk.mcp_server.server"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert completed.stdout == ""
    assert completed.stderr == ""
    assert inspect.iscoroutinefunction(server_module.run_server) is False

    class StubServer:
        def __init__(self) -> None:
            self.ran = False

        def run(self) -> None:
            self.ran = True

    stub = StubServer()
    monkeypatch.setattr(server_module, "create_default_mcp_server", lambda: stub)
    server_module.run_server()
    assert stub.ran is True
