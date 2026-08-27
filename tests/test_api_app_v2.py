"""Focused tests for the MittelWerk application factory and REST surface.

Covers: lifespan and app-instance isolation, public vs protected routes,
401/403 and least-privilege permission checks, explicit CORS, the authenticated
work-order lifecycle (maker/taker, fractional hours, rejections, duplicates,
cancel, ownership), organization-scoped workloads and risk, the dashboard
payload contract, parameterised equipment search, assignment persistence,
feed-driven marking, and exception-safe startup/shutdown without leaked tasks.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import pytest
import yaml
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.exc import OperationalError

import main
from mittelwerk.api.dependencies import API_KEY_HEADER
from mittelwerk.api.service import DispatchService
from mittelwerk.auth.keys import KeyManager
from mittelwerk.core.engine import DispatchEngine
from mittelwerk.core.events import EventBus
from mittelwerk.core.models import (
    DispatchSide,
    Equipment,
    EquipmentCategory,
    WorkOrder,
    WorkOrderMode,
)
from mittelwerk.dispatch_policies.base import DispatchPolicyMeta
from mittelwerk.telemetry.store import TelemetryStore

ALICE_KEY = "mwk_test_alice_key_0123456789abc"
BOB_KEY = "mwk_test_bob_key_0123456789abcde"
READER_KEY = "mwk_test_reader_key_0123456789ab"
DISPATCH_ONLY_KEY = "mwk_test_dispatchonly_key_01234567"

ALICE = {API_KEY_HEADER: ALICE_KEY}
BOB = {API_KEY_HEADER: BOB_KEY}
READER = {API_KEY_HEADER: READER_KEY}
DISPATCH_ONLY = {API_KEY_HEADER: DISPATCH_ONLY_KEY}

DASHBOARD_KEYS = {
    "as_of",
    "currency",
    "kpis",
    "workloads",
    "cost_history",
    "risk",
    "dispatch_queues",
}


def build_equipment() -> dict[str, Equipment]:
    return {
        "CNC-01": Equipment(
            asset_id="CNC-01",
            name="CNC Mill Line 1",
            equipment_type=EquipmentCategory.CNC_MACHINE,
            service_interval_days=30,
            hourly_service_rate="85.00",
            rate_increment="0.50",
            hour_lot_size="0.25",
            currency="EUR",
            site_code="MW-STUTTGART",
        ),
        "PRESS-04": Equipment(
            asset_id="PRESS-04",
            name="Hydraulic Press 400t",
            equipment_type=EquipmentCategory.HYDRAULIC_PRESS,
            service_interval_days=45,
            hourly_service_rate="120.00",
            rate_increment="1.00",
            hour_lot_size="0.5",
            currency="EUR",
            site_code="MW-MUNICH",
        ),
        "ROBOT-07": Equipment(
            asset_id="ROBOT-07",
            name="Robotic Welding Arm 7",
            equipment_type=EquipmentCategory.ROBOTIC_ARM,
            service_interval_days=21,
            hourly_service_rate="110.00",
            rate_increment="1.00",
            hour_lot_size="0.25",
            currency="EUR",
            site_code="MW-STUTTGART",
        ),
        "COMP-03": Equipment(
            asset_id="COMP-03",
            name="Industrial Compressor Unit 3",
            equipment_type=EquipmentCategory.COMPRESSOR,
            service_interval_days=90,
            hourly_service_rate="78.00",
            rate_increment="0.50",
            hour_lot_size="0.5",
            currency="CHF",
            site_code="MW-ZURICH",
        ),
    }


def build_config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "timezone": {"application": "UTC", "presentation": "Europe/Berlin"},
        "server": {
            "host": "127.0.0.1",
            "port": 8443,
            "log_level": "info",
            "cors_origins": [],
            "cors_allow_credentials": False,
        },
        "risk": {},
        "database": {"url": "sqlite://", "echo": False},
        "feed": {"mode": "simulated", "interval_ms": 10, "seed": 7},
        "dashboard": {"currency": "EUR"},
        "auth": {"key_ttl_seconds": 86400},
        "logging": {
            "level": "INFO",
            "format": "%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        },
    }
    config.update(overrides)
    return config


def build_key_manager() -> KeyManager:
    manager = KeyManager("api-test-secret")
    manager.register_key(ALICE_KEY, "alice", permissions=["read", "dispatch"])
    manager.register_key(BOB_KEY, "bob", permissions=["read", "dispatch"])
    manager.register_key(READER_KEY, "reader", permissions=["read"])
    manager.register_key(DISPATCH_ONLY_KEY, "dispatch_only", permissions=["dispatch"])
    return manager


def build_app(**kwargs: Any) -> Any:
    kwargs.setdefault("config", build_config())
    kwargs.setdefault("equipment", build_equipment())
    kwargs.setdefault("key_manager", build_key_manager())
    kwargs.setdefault("enable_feed", False)
    kwargs.setdefault("enable_store", False)
    config = kwargs.pop("config")
    return main.create_app(config, **kwargs)


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(build_app()) as test_client:
        yield test_client


@pytest.fixture
def store() -> Iterator[TelemetryStore]:
    telemetry_store = TelemetryStore("sqlite://")
    try:
        yield telemetry_store
    finally:
        telemetry_store.close()


def submit(client: TestClient, headers: dict[str, str], **payload: Any) -> Any:
    return client.post("/api/v1/work-orders", headers=headers, json=payload)


# ---------------------------------------------------------------------------
# Factory, lifespan, isolation
# ---------------------------------------------------------------------------


def test_app_metadata_describes_an_educational_simulator() -> None:
    app = build_app()
    assert app.version == "1.0.0"
    assert "MittelWerk" in app.title
    assert "Simulator" in app.title
    description = app.description.lower()
    assert "simulation-only" in description
    assert "synthetic" in description
    assert "production" not in description


def test_lifespan_starts_and_stops_event_bus(client: TestClient) -> None:
    services = client.app.state.services
    assert services.event_bus.is_running is True
    assert client.app.state.feed_task is None
    assert client.get("/api/v1/health").status_code == 200


def test_app_instances_are_isolated() -> None:
    first = build_app()
    second_manager = KeyManager("other-secret")
    second_manager.register_key(BOB_KEY, "bob", permissions=["read", "dispatch"])
    second = build_app(key_manager=second_manager)

    assert first.state.services.engine is not second.state.services.engine
    assert first.state.services.dispatch is not second.state.services.dispatch

    with TestClient(first) as first_client, TestClient(second) as second_client:
        created = submit(
            first_client,
            ALICE,
            asset_id="CNC-01",
            side="REQUEST",
            requested_hours="5",
            mode="RATE_CAPPED",
            max_hourly_rate="85.00",
        )
        assert created.status_code == 201

        assert first_client.get("/api/v1/work-orders", headers=ALICE).json()["count"] == 1
        assert second_client.get("/api/v1/work-orders", headers=ALICE).status_code == 403
        assert second_client.get("/api/v1/work-orders", headers=BOB).json()["count"] == 0


def test_missing_config_and_equipment_files_raise(tmp_path: Any) -> None:
    with pytest.raises(FileNotFoundError):
        main.load_config(tmp_path / "absent.yaml")
    with pytest.raises(FileNotFoundError):
        main.load_equipment(tmp_path / "absent.json")

    malformed = tmp_path / "equipment.json"
    malformed.write_text('{"asset_id": "CNC-01"}', encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_equipment(malformed)

    broken_yaml = tmp_path / "settings.yaml"
    broken_yaml.write_text("server: [unclosed\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        main.load_config(broken_yaml)

    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_config(empty_yaml)


def test_repository_config_and_equipment_load() -> None:
    config = main.load_config()
    assert main.coerce_port(config["server"]["port"]) == 8443
    assert config["server"]["host"] == "127.0.0.1"
    assert config["database"]["url"] == "sqlite:///mittelwerk.db"
    assert config["dashboard"]["currency"] == "EUR"
    assert config["feed"]["seed"] == 7
    main.validate_config_keys(config)
    main.validate_config_values(config)

    equipment = main.load_equipment()
    assert {"CNC-01", "PRESS-04", "ROBOT-07"}.issubset(equipment)
    assert equipment["COMP-03"].currency == "CHF"
    assert equipment["ROBOT-07"].hour_lot_size == Decimal("0.25")


def test_app_requires_a_nonempty_consistent_equipment_mapping() -> None:
    with pytest.raises(ValueError, match="At least one simulated equipment asset"):
        build_app(equipment={})

    equipment = build_equipment()
    with pytest.raises(ValueError, match="does not match asset_id"):
        build_app(equipment={"WRONG": equipment["PRESS-04"]})


@pytest.mark.parametrize("value", ["8443", 8443])
def test_port_parsing_accepts_int_and_numeric_string(value: Any) -> None:
    assert main.coerce_port(value) == 8443


@pytest.mark.parametrize("value", ["", "abc", "0", 0, 70000, -1])
def test_port_parsing_rejects_invalid_values(value: Any) -> None:
    with pytest.raises(ValueError):
        main.coerce_port(value)


def test_port_parsing_rejects_bool_and_host_must_be_text() -> None:
    with pytest.raises(TypeError):
        main.coerce_port(True)
    with pytest.raises(ValueError):
        main.coerce_host("   ")


# ---------------------------------------------------------------------------
# Public vs protected surfaces
# ---------------------------------------------------------------------------


def test_health_is_public_and_returns_aware_utc(client: TestClient) -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "healthy"
    assert body["version"] == "1.0.0"
    assert body["mode"] == "simulation"
    assert body["feed"] == "off"

    stamp = datetime.fromisoformat(body["timestamp"])
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timedelta(0)


def test_dashboard_shell_is_served_same_origin_without_auth(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "MittelWerk" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/work-orders",
        "/api/v1/workloads",
        "/api/v1/organization/snapshot",
        "/api/v1/organization/risk",
        "/api/v1/dashboard",
        "/api/v1/metrics",
        "/api/v1/dispatch-policies",
        "/api/v1/equipment/search?q=cnc",
    ],
)
def test_protected_endpoints_require_a_key(client: TestClient, path: str) -> None:
    missing = client.get(path)
    assert missing.status_code == 401
    assert API_KEY_HEADER in missing.json()["detail"]

    invalid = client.get(path, headers={API_KEY_HEADER: "mwk_not_a_real_key"})
    assert invalid.status_code == 403


def test_expired_and_revoked_keys_are_forbidden() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = {"now": now}
    manager = KeyManager("api-test-secret", clock=lambda: clock["now"])
    manager.register_key(ALICE_KEY, "alice", permissions=["read"], ttl_seconds=60)
    revoked = manager.register_key(BOB_KEY, "bob", permissions=["read"])

    with TestClient(build_app(key_manager=manager)) as client:
        assert client.get("/api/v1/workloads", headers=ALICE).status_code == 200

        manager.revoke_key(revoked.key_id)
        assert client.get("/api/v1/workloads", headers=BOB).status_code == 403

        clock["now"] = now + timedelta(seconds=61)
        assert client.get("/api/v1/workloads", headers=ALICE).status_code == 403


def test_permissions_are_least_privilege(client: TestClient) -> None:
    read_only = submit(
        client,
        READER,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
    )
    assert read_only.status_code == 403
    assert "dispatch" in read_only.json()["detail"]

    dispatch_only = client.get("/api/v1/work-orders", headers=DISPATCH_ONLY)
    assert dispatch_only.status_code == 403
    assert "read" in dispatch_only.json()["detail"]

    assert client.get("/api/v1/workloads", headers=READER).status_code == 200


def test_organization_identity_cannot_be_supplied_by_the_caller(client: TestClient) -> None:
    response = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
        organization_id="bob",
    )
    assert response.status_code == 422

    accepted = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
    )
    assert accepted.json()["work_order"]["organization_id"] == "alice"


def test_no_bootstrap_key_leaves_protected_endpoints_inaccessible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(main.BOOTSTRAP_KEY_ENV, raising=False)
    monkeypatch.delenv(main.BOOTSTRAP_ORGANIZATION_ENV, raising=False)
    manager = KeyManager("api-test-secret")
    app = build_app(key_manager=manager)
    assert manager.key_count == 0

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/dashboard").status_code == 401
        assert client.get("/api/v1/dashboard", headers=ALICE).status_code == 403


def test_bootstrap_key_can_be_injected_for_local_use() -> None:
    raw = "mwk_injected_bootstrap_key_00001"
    app = build_app(
        key_manager=KeyManager("api-test-secret"),
        bootstrap_api_key=raw,
        bootstrap_organization_id="operator",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/dashboard", headers={API_KEY_HEADER: raw})
        assert response.status_code == 200
        assert raw not in response.text


# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------


def test_no_cors_headers_by_default(client: TestClient) -> None:
    response = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers


def test_explicit_cors_origin_is_echoed() -> None:
    config = build_config(
        server={
            "host": "127.0.0.1",
            "port": 8443,
            "cors_origins": ["https://dashboard.example"],
            "cors_allow_credentials": True,
        }
    )
    with TestClient(build_app(config=config)) as client:
        allowed = client.get("/api/v1/health", headers={"Origin": "https://dashboard.example"})
        assert allowed.headers["access-control-allow-origin"] == "https://dashboard.example"

        denied = client.get("/api/v1/health", headers={"Origin": "https://evil.example"})
        assert "access-control-allow-origin" not in denied.headers


def test_wildcard_origin_never_combines_with_credentials() -> None:
    config = build_config(
        server={
            "host": "127.0.0.1",
            "port": 8443,
            "cors_origins": ["*"],
            "cors_allow_credentials": True,
        }
    )
    with TestClient(build_app(config=config)) as client:
        response = client.get("/api/v1/health", headers={"Origin": "https://any.example"})
        assert response.headers["access-control-allow-origin"] == "*"
        assert "access-control-allow-credentials" not in response.headers


# ---------------------------------------------------------------------------
# Work-order lifecycle
# ---------------------------------------------------------------------------


def test_maker_taker_match_executes_at_the_resting_rate(client: TestClient) -> None:
    maker = submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="OFFER",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="120.00",
    )
    assert maker.status_code == 201
    assert maker.json()["status"] == "ACCEPTED"
    assert maker.json()["assignments"] == []

    taker = submit(
        client,
        BOB,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="4",
        mode="RATE_CAPPED",
        max_hourly_rate="121.00",
    )
    body = taker.json()
    assert taker.status_code == 201
    assert body["status"] == "ASSIGNED"
    assert body["assigned_hours"] == "4"
    assert [assignment["hourly_rate"] for assignment in body["assignments"]] == ["120.00"]
    assert body["assignments"][0]["initiating_side"] == "REQUEST"

    maker_state = client.get(
        f"/api/v1/work-orders/{maker.json()['work_order_id']}", headers=ALICE
    ).json()
    assert maker_state["status"] == "PARTIALLY_ASSIGNED"
    assert maker_state["assigned_hours"] == "4"


def test_fractional_hours_are_supported(client: TestClient) -> None:
    submit(
        client,
        ALICE,
        asset_id="ROBOT-07",
        side="OFFER",
        requested_hours="0.75",
        mode="RATE_CAPPED",
        max_hourly_rate="110.00",
    )
    taker = submit(
        client,
        BOB,
        asset_id="ROBOT-07",
        side="REQUEST",
        requested_hours="0.25",
        mode="RATE_CAPPED",
        max_hourly_rate="110.00",
    )
    assert taker.status_code == 201
    assert taker.json()["assigned_hours"] == "0.25"
    assert taker.json()["assignments"][0]["hours"] == "0.25"


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        (
            {
                "asset_id": "NOPE",
                "side": "REQUEST",
                "requested_hours": "1",
                "mode": "RATE_CAPPED",
                "max_hourly_rate": "10.00",
            },
            "Unknown asset",
        ),
        (
            {
                "asset_id": "PRESS-04",
                "side": "REQUEST",
                "requested_hours": "1",
                "mode": "RATE_CAPPED",
                "max_hourly_rate": "120.50",
            },
            "rate increment",
        ),
        (
            {
                "asset_id": "ROBOT-07",
                "side": "REQUEST",
                "requested_hours": "0.10",
                "mode": "RATE_CAPPED",
                "max_hourly_rate": "110.00",
            },
            "hour lot size",
        ),
        (
            {
                "asset_id": "CNC-01",
                "side": "REQUEST",
                "requested_hours": "1",
                "mode": "RATE_CAPPED",
                "max_hourly_rate": "85.00",
                "dispatch_window": "SHIFT",
            },
            "SHIFT dispatch window is not supported",
        ),
        (
            {
                "asset_id": "COMP-03",
                "side": "REQUEST",
                "requested_hours": "1",
                "mode": "ESCALATION",
                "escalation_rate": "80.00",
            },
            "ESCALATION work orders are not supported",
        ),
    ],
)
def test_domain_rejections_use_a_stable_contract(
    client: TestClient, payload: dict[str, Any], expected_fragment: str
) -> None:
    response = submit(client, ALICE, **payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "work_order_rejected"
    assert detail["status"] == "REJECTED"
    assert expected_fragment in detail["reason"]
    assert client.get("/api/v1/work-orders", headers=ALICE).json()["count"] == 1


def test_schema_valid_but_domain_invalid_work_orders_are_reported(client: TestClient) -> None:
    response = submit(client, ALICE, asset_id="CNC-01", side="REQUEST", requested_hours="1")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_work_order"
    assert "max_hourly_rate" in detail["reason"]


@pytest.mark.parametrize(
    "payload",
    [
        {
            "asset_id": "CNC-01",
            "side": "SIDEWAYS",
            "requested_hours": "1",
            "mode": "RATE_CAPPED",
            "max_hourly_rate": "85.00",
        },
        {
            "asset_id": "CNC-01",
            "side": "REQUEST",
            "requested_hours": "0",
            "mode": "RATE_CAPPED",
            "max_hourly_rate": "85.00",
        },
        {
            "asset_id": "CNC-01",
            "side": "REQUEST",
            "requested_hours": "-5",
            "mode": "RATE_CAPPED",
            "max_hourly_rate": "85.00",
        },
        {
            "asset_id": "CNC-01",
            "side": "REQUEST",
            "requested_hours": "1",
            "mode": "RATE_CAPPED",
            "max_hourly_rate": "-10.00",
        },
        {
            "side": "REQUEST",
            "requested_hours": "1",
            "mode": "RATE_CAPPED",
            "max_hourly_rate": "85.00",
        },
    ],
)
def test_schema_violations_are_rejected_before_the_engine(
    client: TestClient, payload: dict[str, Any]
) -> None:
    assert submit(client, ALICE, **payload).status_code == 422


def test_duplicate_work_order_id_conflicts_without_mutating_either_work_order(
    client: TestClient,
) -> None:
    first = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
        work_order_id="idem-1",
    )
    assert first.status_code == 201
    original = client.get("/api/v1/work-orders/idem-1", headers=ALICE).json()

    duplicate = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="OFFER",
        requested_hours="99",
        mode="RATE_CAPPED",
        max_hourly_rate="1.00",
        work_order_id="idem-1",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == {
        "error": "duplicate_work_order_id",
        "work_order_id": "idem-1",
    }

    unchanged = client.get("/api/v1/work-orders/idem-1", headers=ALICE).json()
    assert unchanged == original
    assert client.get("/api/v1/work-orders", headers=ALICE).json()["count"] == 1


async def test_service_rejection_reason_does_not_depend_on_event_replay() -> None:
    event_bus = EventBus(persist=False)
    engine = DispatchEngine(event_bus, build_equipment())
    service = DispatchService(engine, event_bus)
    work_order = WorkOrder(
        work_order_id="direct-rejection-reason",
        organization_id="alice",
        asset_id="CNC-01",
        side=DispatchSide.REQUEST,
        mode=WorkOrderMode.RATE_CAPPED,
        requested_hours=Decimal("1.1"),
        max_hourly_rate=Decimal("90"),
    )

    result = await service.submit_work_order("alice", work_order)

    assert event_bus.event_log is None
    assert result.accepted is False
    assert result.rejection_reason == "Hours 1.1 is not a multiple of hour lot size 0.25"


def test_work_order_ids_are_never_reusable_even_after_rejection(client: TestClient) -> None:
    rejected = submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="120.50",
        work_order_id="reserved-1",
    )
    assert rejected.status_code == 400

    retry = submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="120.00",
        work_order_id="reserved-1",
    )
    assert retry.status_code == 409


def test_work_order_listing_is_scoped_to_the_authenticated_organization(client: TestClient) -> None:
    alice_work_order = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
    ).json()["work_order_id"]
    submit(
        client,
        BOB,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="2",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
    )

    alice_work_orders = client.get("/api/v1/work-orders", headers=ALICE).json()
    assert alice_work_orders["count"] == 1
    assert alice_work_orders["work_orders"][0]["work_order_id"] == alice_work_order
    assert all(
        work_order["organization_id"] == "alice" for work_order in alice_work_orders["work_orders"]
    )

    assert client.get("/api/v1/work-orders", headers=BOB).json()["count"] == 1
    assert client.get("/api/v1/work-orders", headers=READER).json()["count"] == 0
    assert client.get(f"/api/v1/work-orders/{alice_work_order}", headers=BOB).status_code == 404


def test_cancel_enforces_ownership_and_reports_terminal_work_orders(
    client: TestClient,
) -> None:
    work_order_id = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
    ).json()["work_order_id"]

    assert client.delete(f"/api/v1/work-orders/{work_order_id}", headers=BOB).status_code == 404
    assert client.delete(f"/api/v1/work-orders/{work_order_id}", headers=READER).status_code == 403

    cancelled = client.delete(f"/api/v1/work-orders/{work_order_id}", headers=ALICE)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["work_order"]["work_order_id"] == work_order_id

    repeat = client.delete(f"/api/v1/work-orders/{work_order_id}", headers=ALICE)
    assert repeat.status_code == 409
    assert repeat.json()["detail"]["error"] == "work_order_not_resting"
    assert repeat.json()["detail"]["status"] == "CANCELLED"

    assert client.delete("/api/v1/work-orders/does-not-exist", headers=ALICE).status_code == 404


# ---------------------------------------------------------------------------
# Workloads, organization, risk
# ---------------------------------------------------------------------------


def test_workloads_and_organization_snapshot_are_organization_scoped(
    client: TestClient,
) -> None:
    submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="OFFER",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    submit(
        client,
        BOB,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )

    alice = client.get("/api/v1/workloads", headers=ALICE).json()
    bob = client.get("/api/v1/workloads", headers=BOB).json()
    assert alice["organization_id"] == "alice"
    assert alice["workloads"][0]["net_hours"] == "-10"
    assert bob["workloads"][0]["net_hours"] == "10"
    assert all(workload["organization_id"] == "alice" for workload in alice["workloads"])

    alice_snapshot = client.get("/api/v1/organization/snapshot", headers=ALICE).json()
    bob_snapshot = client.get("/api/v1/organization/snapshot", headers=BOB).json()
    assert alice_snapshot["organization_id"] == "alice"
    assert Decimal(alice_snapshot["total_exposure_value"]) == Decimal("-1000.00")
    assert Decimal(bob_snapshot["total_exposure_value"]) == Decimal("1000.00")

    assert client.get("/api/v1/workloads", headers=READER).json()["workloads"] == []


def test_risk_payload_is_honest_without_a_volatility_assumption(
    client: TestClient,
) -> None:
    risk = client.get("/api/v1/organization/risk", headers=ALICE).json()
    assert risk["backlog_risk_95"] is None
    assert risk["backlog_risk_99"] is None
    assert risk["service_level_ratio"] is None
    assert risk["max_backlog_overrun"] is None
    assert Decimal(risk["gross_committed_hours"]) == Decimal("0")


def test_backlog_risk_is_computed_when_a_volatility_assumption_is_configured() -> None:
    config = build_config(risk={"hours_volatility": 0.02})
    with TestClient(build_app(config=config)) as client:
        submit(
            client,
            ALICE,
            asset_id="PRESS-04",
            side="OFFER",
            requested_hours="10",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
        )
        submit(
            client,
            BOB,
            asset_id="PRESS-04",
            side="REQUEST",
            requested_hours="10",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
        )
        risk = client.get("/api/v1/organization/risk", headers=ALICE).json()
        assert Decimal(risk["backlog_risk_95"]) > 0
        assert Decimal(risk["backlog_risk_99"]) > Decimal(risk["backlog_risk_95"])


# ---------------------------------------------------------------------------
# Dashboard contract
# ---------------------------------------------------------------------------


def test_dashboard_empty_state_matches_the_contract(client: TestClient) -> None:
    body = client.get("/api/v1/dashboard", headers=READER).json()
    assert set(body) == DASHBOARD_KEYS

    as_of = datetime.fromisoformat(body["as_of"])
    assert as_of.tzinfo is not None
    assert as_of.utcoffset() == timedelta(0)

    assert body["currency"] == "EUR"
    assert body["workloads"] == []
    assert body["cost_history"] == []
    assert body["dispatch_queues"] == {}
    assert set(body["kpis"]) >= {
        "exposure_value",
        "realized_cost",
        "unrealized_cost",
        "backlog_risk_95",
        "active_work_orders",
    }
    assert body["kpis"]["active_work_orders"] == 0


def test_dashboard_populated_state_exposes_workloads_work_orders_and_queues(
    client: TestClient,
) -> None:
    submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="OFFER",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    submit(
        client,
        BOB,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="4",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    submit(
        client,
        BOB,
        asset_id="COMP-03",
        side="REQUEST",
        requested_hours="3",
        mode="RATE_CAPPED",
        max_hourly_rate="78.00",
    )

    body = client.get("/api/v1/dashboard", headers=BOB).json()
    assert set(body) == DASHBOARD_KEYS

    workload = body["workloads"][0]
    assert workload["asset_id"] == "PRESS-04"
    assert workload["currency"] == "EUR"
    assert Decimal(workload["net_hours"]) == Decimal("4")
    assert Decimal(workload["average_service_rate"]) == Decimal("100.00")
    assert Decimal(workload["last_rate"]) == Decimal("100.00")
    assert Decimal(workload["total_cost"]) == Decimal(workload["realized_cost"]) + Decimal(
        workload["unrealized_cost"]
    )

    assert body["kpis"]["active_work_orders"] == 1
    assert Decimal(body["kpis"]["exposure_value"]) == Decimal("400.00")

    queues = body["dispatch_queues"]
    assert set(queues) == {"COMP-03", "PRESS-04"}
    assert queues["COMP-03"]["requests"][0]["rate"] == "78.00"
    assert queues["COMP-03"]["requests"][0]["hours"] == "3"
    assert queues["COMP-03"]["requests"][0]["work_orders"] == 1
    assert queues["COMP-03"]["offers"] == []

    history = body["cost_history"]
    assert len(history) == 1
    stamp = datetime.fromisoformat(history[0]["timestamp"])
    assert stamp.utcoffset() == timedelta(0)
    assert Decimal(history[0]["value"]) == Decimal("0.00")

    alice_body = client.get("/api/v1/dashboard", headers=ALICE).json()
    assert Decimal(alice_body["workloads"][0]["net_hours"]) == Decimal("-4")


def test_workload_payloads_carry_each_equipments_own_currency(
    client: TestClient,
) -> None:
    submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="OFFER",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    submit(
        client,
        BOB,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    submit(
        client,
        ALICE,
        asset_id="COMP-03",
        side="OFFER",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="78.00",
    )
    submit(
        client,
        BOB,
        asset_id="COMP-03",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="78.00",
    )

    workloads = client.get("/api/v1/workloads", headers=BOB).json()["workloads"]
    assert {workload["asset_id"]: workload["currency"] for workload in workloads} == {
        "COMP-03": "CHF",
        "PRESS-04": "EUR",
    }

    dashboard_workloads = client.get("/api/v1/dashboard", headers=BOB).json()["workloads"]
    assert {workload["asset_id"]: workload["currency"] for workload in dashboard_workloads} == {
        "COMP-03": "CHF",
        "PRESS-04": "EUR",
    }


# ---------------------------------------------------------------------------
# Equipment search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    ["' OR 1=1 --", "'; DROP TABLE equipment; --", "%", "_"],
)
def test_equipment_search_injection_payloads_are_inert(store: TelemetryStore, payload: str) -> None:
    app = build_app(store=store, enable_store=True)
    with TestClient(app) as client:
        response = client.get("/api/v1/equipment/search", headers=READER, params={"q": payload})
        assert response.status_code == 200
        assert response.json()["results"] == []
        assert store.count_equipment() == len(build_equipment())


def test_equipment_search_is_seeded_bounded_and_authenticated(
    store: TelemetryStore,
) -> None:
    app = build_app(store=store, enable_store=True)
    with TestClient(app) as client:
        assert client.get("/api/v1/equipment/search", params={"q": "400t"}).status_code == 401

        found = client.get("/api/v1/equipment/search", headers=READER, params={"q": "400t"}).json()
        assert found["count"] == 1
        assert found["results"][0]["asset_id"] == "PRESS-04"
        assert found["results"][0]["currency"] == "EUR"

        limited = client.get(
            "/api/v1/equipment/search", headers=READER, params={"q": "c", "limit": 1}
        ).json()
        assert len(limited["results"]) <= 1

        out_of_bounds = (
            {"q": ""},
            {"q": "x" * 100},
            {"q": "a", "limit": 0},
            {"q": "a", "limit": 5000},
        )
        for params in out_of_bounds:
            assert (
                client.get("/api/v1/equipment/search", headers=READER, params=params).status_code
                == 422
            )


def test_equipment_search_falls_back_to_in_memory_reference_data(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/equipment/search", headers=READER, params={"q": "compressor"})
    assert response.status_code == 200
    assert [row["asset_id"] for row in response.json()["results"]] == ["COMP-03"]
    assert (
        client.get("/api/v1/equipment/search", headers=READER, params={"q": "' OR 1=1 --"}).json()[
            "results"
        ]
        == []
    )


def test_dispatch_policies_and_metrics_require_read_permission(client: TestClient) -> None:
    policies = client.get("/api/v1/dispatch-policies", headers=READER)
    assert policies.status_code == 200
    assert policies.json()["policies"] == sorted(DispatchPolicyMeta.list_policies())

    metrics = client.get("/api/v1/metrics", headers=READER)
    assert metrics.status_code == 200
    assert isinstance(metrics.json(), dict)

    assert client.get("/api/v1/dispatch-policies", headers=DISPATCH_ONLY).status_code == 403
    assert client.get("/api/v1/metrics", headers=DISPATCH_ONLY).status_code == 403


# ---------------------------------------------------------------------------
# Lifecycle: feed and shutdown
# ---------------------------------------------------------------------------


async def test_feed_task_starts_and_shuts_down_without_leaks() -> None:
    app = build_app(enable_feed=True)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.05)
        feed = app.state.services.feed
        assert feed is not None
        assert feed.is_running is True
        assert app.state.feed_task is not None
        assert app.state.feed_task.get_name() == main.FEED_TASK_NAME

    assert app.state.feed_task is None
    assert app.state.services.feed.is_running is False
    assert app.state.services.event_bus.is_running is False

    current = asyncio.current_task()
    leaked = [task for task in asyncio.all_tasks() if task is not current]
    assert leaked == []


async def test_owned_store_is_closed_on_shutdown_and_injected_store_is_not(
    store: TelemetryStore,
) -> None:
    owned_app = main.create_app(
        build_config(database={"url": "sqlite://"}),
        equipment=build_equipment(),
        key_manager=build_key_manager(),
        enable_feed=False,
    )
    owned_store = owned_app.state.services.store
    assert owned_store is not None
    async with owned_app.router.lifespan_context(owned_app):
        assert owned_store.is_closed is False
    assert owned_store.is_closed is True

    injected_app = build_app(store=store, enable_store=True)
    async with injected_app.router.lifespan_context(injected_app):
        assert store.is_closed is False
    assert store.is_closed is False


async def test_feed_can_be_disabled_deterministically() -> None:
    app = build_app(enable_feed=False)
    async with app.router.lifespan_context(app):
        assert app.state.services.feed is None
        assert app.state.feed_task is None


# ---------------------------------------------------------------------------
# Regressions: feed mode is explicit and fails closed
# ---------------------------------------------------------------------------


def feed_app(mode: Any, **kwargs: Any) -> Any:
    config = build_config(feed={"mode": mode, "interval_ms": 10})
    kwargs.setdefault("enable_feed", None)
    return build_app(config=config, **kwargs)


@pytest.mark.parametrize("mode", ["simulated", "SIMULATED", "  simulated  "])
def test_simulated_mode_builds_the_feed(mode: str) -> None:
    assert feed_app(mode).state.services.feed is not None


@pytest.mark.parametrize("mode", ["disabled", "off", "none", "OFF"])
def test_explicit_disabled_modes_run_without_a_feed(mode: str) -> None:
    assert feed_app(mode).state.services.feed is None


@pytest.mark.parametrize("enable_feed", [None, True, False])
def test_websocket_mode_is_refused_with_an_actionable_error(
    enable_feed: bool | None,
) -> None:
    with pytest.raises(ValueError, match="websocket") as excinfo:
        feed_app("websocket", enable_feed=enable_feed)
    message = str(excinfo.value)
    assert "WebSocketFeedAdapter" in message
    assert "simulated" in message
    assert "disabled" in message


@pytest.mark.parametrize("mode", ["simulted", "live", "real", "", "  "])
def test_unknown_feed_modes_are_rejected_instead_of_disabling_telemetry(
    mode: str,
) -> None:
    with pytest.raises(ValueError, match="Unsupported feed.mode") as excinfo:
        feed_app(mode)
    assert "'simulated'" in str(excinfo.value)


@pytest.mark.parametrize("mode", [None, 5, True, ["simulated"]])
def test_non_string_feed_modes_are_rejected(mode: Any) -> None:
    with pytest.raises(ValueError, match="feed.mode must be a string"):
        feed_app(mode)


def test_enable_feed_argument_overrides_only_whether_the_simulator_runs() -> None:
    assert feed_app("simulated", enable_feed=False).state.services.feed is None
    turned_on = feed_app("disabled", enable_feed=True).state.services.feed
    assert turned_on is not None
    assert type(turned_on).__name__ == "TelemetryFeed"


def test_feed_mode_is_validated_even_when_the_argument_disables_the_feed() -> None:
    with pytest.raises(ValueError, match="Unsupported feed.mode"):
        feed_app("simulted", enable_feed=False)


def test_repository_configuration_uses_a_supported_feed_mode() -> None:
    feed = main.load_config()["feed"]
    mode = feed["mode"]
    assert main.resolve_feed_mode(mode) == main.FEED_MODE_SIMULATED
    assert feed["seed"] == main.DEFAULT_FEED_SEED


@pytest.mark.parametrize("interval", [-1, 0, float("nan"), float("inf"), "fast", True, None])
def test_invalid_tick_intervals_are_rejected(interval: Any) -> None:
    config = build_config(feed={"mode": "simulated", "interval_ms": interval})
    with pytest.raises((TypeError, ValueError)):
        build_app(config=config, enable_feed=None)


@pytest.mark.parametrize("seed", [True, -1, 2**32, 1.5, "7", None])
def test_invalid_feed_seeds_are_rejected(seed: Any) -> None:
    config = build_config(feed={"mode": "simulated", "interval_ms": 10, "seed": seed})
    with pytest.raises((TypeError, ValueError)):
        build_app(config=config, enable_feed=None)


def test_feed_seed_is_passed_to_the_simulator(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    real_feed = main.TelemetryFeed

    def recording_feed(*args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return real_feed(*args, **kwargs)

    monkeypatch.setattr(main, "TelemetryFeed", recording_feed)
    build_app(enable_feed=True)
    assert captured["seed"] == 7


@pytest.mark.parametrize(
    ("config", "fragment"),
    [
        ({"unknown": {}}, "Unsupported configuration section"),
        (
            build_config(server={"host": "127.0.0.1", "port": 8443, "workers": 4}),
            "Unsupported configuration key",
        ),
        (
            build_config(auth={"api_key_header": "X-Other"}),
            "Unsupported configuration key",
        ),
    ],
)
def test_unknown_configuration_is_rejected(config: dict[str, Any], fragment: str) -> None:
    with pytest.raises(ValueError, match=fragment):
        build_app(config=config)


@pytest.mark.parametrize("echo", ["false", 0, 1, None])
def test_database_echo_requires_a_real_boolean(echo: Any) -> None:
    config = build_config(database={"url": "sqlite://", "echo": echo})
    with pytest.raises(TypeError, match="database.echo must be a boolean"):
        build_app(config=config, enable_store=True)


@pytest.mark.parametrize("currency", [123, None, True])
def test_dashboard_currency_requires_a_string(currency: Any) -> None:
    config = build_config(dashboard={"currency": currency})
    with pytest.raises(ValueError, match="dashboard.currency"):
        build_app(config=config)


@pytest.mark.parametrize("volatility", [0, -0.1, float("nan"), float("inf"), True])
def test_hours_volatility_must_be_finite_and_positive(volatility: Any) -> None:
    config = build_config(risk={"hours_volatility": volatility})
    with pytest.raises((TypeError, ValueError)):
        build_app(config=config)


# ---------------------------------------------------------------------------
# Regressions: liveness tells the truth about the feed
# ---------------------------------------------------------------------------


async def get_health(app: Any) -> dict[str, Any]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://health.test") as http:
        response = await http.get("/api/v1/health")
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    return body


async def test_running_feed_reports_healthy() -> None:
    app = build_app(enable_feed=True)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.02)
        body = await get_health(app)
        assert body["status"] == "healthy"
        assert body["feed"] == "running"


async def test_disabled_feed_stays_healthy() -> None:
    app = build_app(enable_feed=False)
    async with app.router.lifespan_context(app):
        body = await get_health(app)
        assert body["status"] == "healthy"
        assert body["feed"] == "off"


async def test_failed_feed_pump_degrades_liveness_without_leaking_details() -> None:
    app = build_app(enable_feed=True)
    services = app.state.services

    async def failing_readings() -> Any:
        raise RuntimeError("pump exploded with secret detail")
        yield

    services.feed.generate_readings = failing_readings  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="pump exploded"):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.05)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://health.test") as http:
                response = await http.get("/api/v1/health")

            assert response.status_code == 200
            body = response.json()
            assert body["status"] == "degraded"
            assert body["feed"] == "stopped"
            assert "pump exploded" not in response.text
            assert "secret detail" not in response.text
            assert "RuntimeError" not in response.text
            assert set(body) == {"status", "version", "timestamp", "mode", "feed"}


async def test_early_feed_completion_degrades_liveness() -> None:
    app = build_app(enable_feed=True)
    services = app.state.services

    async def finished_readings() -> Any:
        return
        yield

    services.feed.generate_readings = finished_readings  # type: ignore[method-assign]

    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.05)
        body = await get_health(app)
        assert body["status"] == "degraded"
        assert body["feed"] == "stopped"


async def test_cancelled_feed_task_degrades_liveness() -> None:
    app = build_app(enable_feed=True)
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.02)
        assert (await get_health(app))["status"] == "healthy"

        feed_task = app.state.feed_task
        feed_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await feed_task

        body = await get_health(app)
        assert body["status"] == "degraded"
        assert body["feed"] == "stopped"


# ---------------------------------------------------------------------------
# Regressions: search-term normalisation at the HTTP boundary
# ---------------------------------------------------------------------------


@pytest.fixture
def store_client(store: TelemetryStore) -> Iterator[TestClient]:
    with TestClient(build_app(store=store, enable_store=True)) as test_client:
        yield test_client


@pytest.mark.parametrize("raw_query", ["q=%20", "q=%09", "q=%20%09%20", "q=+"])
def test_blank_search_terms_are_rejected_identically_by_both_backends(
    client: TestClient, store_client: TestClient, raw_query: str
) -> None:
    for backend in (client, store_client):
        response = backend.get(f"/api/v1/equipment/search?{raw_query}", headers=READER)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"][-1] == "q"


def test_search_terms_are_trimmed_before_reaching_either_backend(
    client: TestClient, store_client: TestClient
) -> None:
    for backend in (client, store_client):
        body = backend.get(
            "/api/v1/equipment/search", headers=READER, params={"q": "  cnc  "}
        ).json()
        assert body["query"] == "cnc"
        assert [row["asset_id"] for row in body["results"]] == ["CNC-01"]


def test_in_memory_search_never_returns_everything_for_padded_input(
    client: TestClient,
) -> None:
    total = len(build_equipment())
    padded = client.get("/api/v1/equipment/search", headers=READER, params={"q": " cnc "}).json()
    assert 0 < padded["count"] < total


# ---------------------------------------------------------------------------
# Regressions: work-order ids must stay addressable through the URL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "work_order_id",
    ["a/b", "../escape", "a b", "a?b", "a#b", "a%2Fb", "a\\b", "x" * 65, "ümlaut"],
)
def test_unsafe_client_work_order_ids_are_rejected_before_the_engine(
    client: TestClient, work_order_id: str
) -> None:
    response = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
        work_order_id=work_order_id,
    )
    assert response.status_code == 422
    assert client.app.state.services.engine.work_order_count == 0
    assert client.get("/api/v1/work-orders", headers=ALICE).json()["count"] == 0


@pytest.mark.parametrize(
    "work_order_id",
    [".", "..", "...", ".hidden", "trailing.", "-leading", "trailing-", ":x", "x:"],
)
def test_dot_segment_and_edge_punctuation_ids_are_rejected(
    client: TestClient, work_order_id: str
) -> None:
    response = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
        work_order_id=work_order_id,
    )
    assert response.status_code == 422
    assert client.app.state.services.engine.work_order_count == 0
    assert client.get("/api/v1/work-orders", headers=ALICE).json()["count"] == 0


@pytest.mark.parametrize("work_order_id", ["a", "9", "a.b", "a:b-c_d", "x" * 64])
def test_boundary_safe_ids_are_accepted_and_addressable(
    client: TestClient, work_order_id: str
) -> None:
    created = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
        work_order_id=work_order_id,
    )
    assert created.status_code == 201
    assert client.get(f"/api/v1/work-orders/{work_order_id}", headers=ALICE).status_code == 200
    assert client.delete(f"/api/v1/work-orders/{work_order_id}", headers=ALICE).status_code == 200


@pytest.mark.parametrize("work_order_id", ["plain-1", "ok_id.2:3", "A1-b2_c3.d4:e5"])
def test_safe_client_work_order_ids_round_trip_through_the_url(
    client: TestClient, work_order_id: str
) -> None:
    created = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
        work_order_id=work_order_id,
    )
    assert created.status_code == 201
    assert created.json()["work_order_id"] == work_order_id

    fetched = client.get(f"/api/v1/work-orders/{work_order_id}", headers=ALICE)
    assert fetched.status_code == 200
    assert fetched.json()["work_order_id"] == work_order_id

    cancelled = client.delete(f"/api/v1/work-orders/{work_order_id}", headers=ALICE)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_engine_generated_uuid_ids_remain_addressable(client: TestClient) -> None:
    work_order_id = submit(
        client,
        ALICE,
        asset_id="CNC-01",
        side="REQUEST",
        requested_hours="1",
        mode="RATE_CAPPED",
        max_hourly_rate="85.00",
    ).json()["work_order_id"]
    assert client.get(f"/api/v1/work-orders/{work_order_id}", headers=ALICE).status_code == 200
    assert client.delete(f"/api/v1/work-orders/{work_order_id}", headers=ALICE).status_code == 200


# ---------------------------------------------------------------------------
# Regressions: CORS must wrap authentication failures
# ---------------------------------------------------------------------------


def build_cors_app(origin: str = "https://dashboard.example") -> Any:
    config = build_config(
        server={
            "host": "127.0.0.1",
            "port": 8443,
            "cors_origins": [origin],
            "cors_allow_credentials": False,
        }
    )
    return build_app(config=config)


@pytest.mark.parametrize(
    ("headers", "expected_status"),
    [({}, 401), ({API_KEY_HEADER: "mwk_not_a_real_key"}, 403), (ALICE, 200)],
)
def test_cors_headers_are_present_on_auth_failures_too(
    headers: dict[str, str], expected_status: int
) -> None:
    origin = "https://dashboard.example"
    with TestClient(build_cors_app(origin)) as client:
        response = client.get("/api/v1/dashboard", headers={"Origin": origin, **headers})
        assert response.status_code == expected_status
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_preflight_is_answered_without_a_key() -> None:
    origin = "https://dashboard.example"
    with TestClient(build_cors_app(origin)) as client:
        response = client.options(
            "/api/v1/work-orders",
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": API_KEY_HEADER,
            },
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
        assert API_KEY_HEADER.lower() in response.headers["access-control-allow-headers"].lower()


def test_disallowed_origin_gets_no_cors_header_on_auth_failure() -> None:
    with TestClient(build_cors_app()) as client:
        response = client.get("/api/v1/dashboard", headers={"Origin": "https://evil.example"})
        assert response.status_code == 401
        assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Regressions: CORS configuration is validated before startup
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("origins", "fragment"),
    [
        ("https://dashboard.example", "not a single string"),
        (b"https://dashboard.example", "not a single string"),
        (42, "must be a list of origin strings"),
        (["https://dashboard.example", ""], "must not be blank"),
        (["   "], "must not be blank"),
        ([None], "must be a string"),
        ([1], "must be a string"),
    ],
)
def test_malformed_cors_origins_are_rejected_at_construction(origins: Any, fragment: str) -> None:
    config = build_config(server={"host": "127.0.0.1", "port": 8443, "cors_origins": origins})
    with pytest.raises(ValueError, match=fragment):
        build_app(config=config)


@pytest.mark.parametrize("credentials", ["false", "true", 0, 1, None, "yes"])
def test_non_boolean_cors_credentials_are_rejected(credentials: Any) -> None:
    config = build_config(
        server={
            "host": "127.0.0.1",
            "port": 8443,
            "cors_origins": ["https://dashboard.example"],
            "cors_allow_credentials": credentials,
        }
    )
    with pytest.raises(ValueError, match="must be a boolean"):
        build_app(config=config)


def test_a_single_string_origin_never_becomes_one_origin_per_character() -> None:
    with pytest.raises(ValueError):
        build_app(
            config=build_config(server={"host": "127.0.0.1", "port": 8443, "cors_origins": "abc"})
        )


def test_valid_cors_configuration_is_accepted_and_trimmed() -> None:
    config = build_config(
        server={
            "host": "127.0.0.1",
            "port": 8443,
            "cors_origins": ("  https://dashboard.example  ",),
            "cors_allow_credentials": True,
        }
    )
    with TestClient(build_app(config=config)) as client:
        response = client.get("/api/v1/health", headers={"Origin": "https://dashboard.example"})
        assert response.headers["access-control-allow-origin"] == "https://dashboard.example"
        assert response.headers["access-control-allow-credentials"] == "true"


def test_absent_cors_configuration_keeps_the_same_origin_default() -> None:
    with TestClient(build_app()) as client:
        response = client.get("/api/v1/health", headers={"Origin": "https://dashboard.example"})
        assert response.status_code == 200
        assert "access-control-allow-origin" not in response.headers


# ---------------------------------------------------------------------------
# Regressions: exception-safe lifespan
# ---------------------------------------------------------------------------


async def test_startup_failure_releases_already_started_resources() -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None

    async def failing_start() -> None:
        raise RuntimeError("feed start exploded")

    services.feed.start = failing_start  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="feed start exploded"):
        async with app.router.lifespan_context(app):
            pytest.fail("startup should not have completed")

    assert services.event_bus.is_running is False
    assert owned_store.is_closed is True
    assert app.state.feed_task is None


def test_construction_failure_closes_the_owned_store(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[TelemetryStore] = []
    real_store = main.TelemetryStore

    def recording_store(*args: Any, **kwargs: Any) -> TelemetryStore:
        telemetry_store = real_store(*args, **kwargs)
        created.append(telemetry_store)
        return telemetry_store

    monkeypatch.setattr(main, "TelemetryStore", recording_store)

    def fail_after_store_opened(*args: Any, **kwargs: Any) -> None:
        raise RuntimeError("post-store wiring failed")

    monkeypatch.setattr(main, "_build_feed", fail_after_store_opened)

    with pytest.raises(RuntimeError, match="post-store wiring failed"):
        build_app(store=None, enable_store=True)

    assert len(created) == 1
    assert created[0].is_closed is True


async def test_failing_teardown_step_does_not_strand_other_resources() -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    real_stop = services.feed.stop

    async def failing_stop() -> None:
        await real_stop()
        raise RuntimeError("feed stop exploded")

    services.feed.stop = failing_stop  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="feed stop exploded"):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.02)

    assert services.event_bus.is_running is False
    assert owned_store.is_closed is True
    assert app.state.feed_task is None


async def test_cancelled_teardown_step_still_releases_everything_and_propagates() -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    real_stop = services.feed.stop

    async def cancelling_stop() -> None:
        await real_stop()
        raise asyncio.CancelledError

    services.feed.stop = cancelling_stop  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.02)

    assert services.event_bus.is_running is False
    assert owned_store.is_closed is True
    assert app.state.feed_task is None


async def test_interrupted_teardown_step_still_releases_everything() -> None:
    app = build_app(enable_feed=False, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    real_stop = services.event_bus.stop

    async def interrupting_stop() -> None:
        await real_stop()
        raise KeyboardInterrupt

    services.event_bus.stop = interrupting_stop  # type: ignore[method-assign]

    with pytest.raises(KeyboardInterrupt):
        async with app.router.lifespan_context(app):
            pass

    assert owned_store.is_closed is True


async def test_cancellation_wins_over_ordinary_teardown_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    real_feed_stop = services.feed.stop
    real_bus_stop = services.event_bus.stop

    async def failing_feed_stop() -> None:
        await real_feed_stop()
        raise RuntimeError("feed stop exploded")

    async def cancelling_bus_stop() -> None:
        await real_bus_stop()
        raise asyncio.CancelledError

    services.feed.stop = failing_feed_stop  # type: ignore[method-assign]
    services.event_bus.stop = cancelling_bus_stop  # type: ignore[method-assign]

    caplog.set_level(logging.ERROR, logger="mittelwerk")
    with pytest.raises(asyncio.CancelledError):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.02)

    assert owned_store.is_closed is True
    assert any("feed stop exploded" in record.getMessage() for record in caplog.records)


async def test_partially_started_feed_still_receives_a_stop() -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    feed = services.feed
    real_stop = feed.stop
    calls: list[str] = []

    async def half_start() -> None:
        feed._running = True
        calls.append("start")
        raise RuntimeError("half started")

    async def tracking_stop() -> None:
        calls.append("stop")
        await real_stop()

    feed.start = half_start  # type: ignore[method-assign]
    feed.stop = tracking_stop  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="half started"):
        async with app.router.lifespan_context(app):
            pytest.fail("startup should not have completed")

    assert calls == ["start", "stop"]
    assert feed.is_running is False
    assert services.event_bus.is_running is False
    assert owned_store.is_closed is True


async def test_partially_started_event_bus_still_receives_a_stop() -> None:
    app = build_app(enable_feed=False, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    event_bus = services.event_bus

    async def half_start() -> None:
        event_bus._running = True
        raise RuntimeError("bus half started")

    event_bus.start = half_start  # type: ignore[method-assign]

    with pytest.raises(RuntimeError, match="bus half started"):
        async with app.router.lifespan_context(app):
            pytest.fail("startup should not have completed")

    assert event_bus.is_running is False
    assert owned_store.is_closed is True


async def test_failing_feed_pump_is_supervised_and_surfaced(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None

    async def failing_readings() -> Any:
        raise RuntimeError("pump exploded")
        yield

    services.feed.generate_readings = failing_readings  # type: ignore[method-assign]

    caplog.set_level(logging.ERROR, logger="mittelwerk")
    with pytest.raises(RuntimeError, match="pump exploded"):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.05)
            assert any(main.FEED_TASK_NAME in record.getMessage() for record in caplog.records)

    assert services.event_bus.is_running is False
    assert owned_store.is_closed is True
    assert app.state.feed_task is None
    current = asyncio.current_task()
    assert [task for task in asyncio.all_tasks() if task is not current] == []


async def test_early_feed_completion_is_reported(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = build_app(enable_feed=True, enable_store=False)
    services = app.state.services

    async def finished_readings() -> Any:
        return
        yield

    services.feed.generate_readings = finished_readings  # type: ignore[method-assign]

    caplog.set_level(logging.ERROR, logger="mittelwerk")
    async with app.router.lifespan_context(app):
        await asyncio.sleep(0.05)
        assert any("finished before shutdown" in record.getMessage() for record in caplog.records)
    assert app.state.feed_task is None


async def test_body_failure_wins_over_cleanup_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    real_stop = services.feed.stop

    async def failing_stop() -> None:
        await real_stop()
        raise RuntimeError("cleanup boom")

    services.feed.stop = failing_stop  # type: ignore[method-assign]

    caplog.set_level(logging.ERROR, logger="mittelwerk")
    with pytest.raises(ValueError, match="body boom"):
        async with app.router.lifespan_context(app):
            raise ValueError("body boom")

    assert owned_store.is_closed is True
    assert services.event_bus.is_running is False
    assert any("cleanup boom" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# Regressions: assignment persistence and feed-driven marking
# ---------------------------------------------------------------------------


def test_executed_assignments_are_persisted_exactly_once(store: TelemetryStore) -> None:
    with TestClient(build_app(store=store, enable_store=True)) as client:
        maker = submit(
            client,
            ALICE,
            asset_id="CNC-01",
            side="OFFER",
            requested_hours="10",
            mode="RATE_CAPPED",
            max_hourly_rate="150.50",
        ).json()
        taker = submit(
            client,
            BOB,
            asset_id="CNC-01",
            side="REQUEST",
            requested_hours="4",
            mode="RATE_CAPPED",
            max_hourly_rate="151.00",
        ).json()

        assert taker["status"] == "ASSIGNED"
        assignment = taker["assignments"][0]

        rows = store.get_assignments("CNC-01")
        assert len(rows) == 1
        row = rows[0]
        assert row.assignment_id == assignment["assignment_id"]
        assert row.asset_id == "CNC-01"
        assert row.requester_work_order_id == taker["work_order_id"]
        assert row.provider_work_order_id == maker["work_order_id"]
        assert row.hourly_rate == Decimal("150.50")
        assert row.hours == Decimal("4")
        assert row.requester_organization_id == "bob"
        assert row.provider_organization_id == "alice"
        assert row.timestamp.utcoffset() == timedelta(0)
        assert row.timestamp == datetime.fromisoformat(assignment["timestamp"])

        submit(
            client,
            BOB,
            asset_id="CNC-01",
            side="REQUEST",
            requested_hours="6",
            mode="RATE_CAPPED",
            max_hourly_rate="151.00",
        )
        assert store.count_assignments("CNC-01") == 2

        submit(
            client,
            ALICE,
            asset_id="COMP-03",
            side="REQUEST",
            requested_hours="1",
            mode="RATE_CAPPED",
            max_hourly_rate="78.00",
        )
        assert store.count_assignments() == 2


def test_persistence_failure_reports_the_execution_honestly(
    store: TelemetryStore,
) -> None:
    def failing_insert(rows: Any) -> int:
        raise OperationalError(
            "INSERT INTO assignments ...", {}, Exception("sqlite:///secret/path.db is gone")
        )

    store.insert_assignments = failing_insert  # type: ignore[method-assign]

    app = build_app(store=store, enable_store=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        submit(
            client,
            ALICE,
            asset_id="PRESS-04",
            side="OFFER",
            requested_hours="10",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
        )
        response = submit(
            client,
            BOB,
            asset_id="PRESS-04",
            side="REQUEST",
            requested_hours="4",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
        )

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "assignment_persistence_failed"
        assert detail["status"] == "ASSIGNED"
        assert detail["assigned_hours"] == "4"
        assert len(detail["assignment_ids"]) == 1
        assert "do not resubmit" in detail["message"].lower()

        assert "secret/path.db" not in response.text
        assert "INSERT INTO" not in response.text

        work_orders = client.get("/api/v1/work-orders", headers=BOB).json()["work_orders"]
        assert [work_order["status"] for work_order in work_orders] == ["ASSIGNED"]
        assert client.get("/api/v1/workloads", headers=BOB).json()["count"] == 1


def test_persistence_is_optional_when_no_store_is_configured(
    client: TestClient,
) -> None:
    assert client.app.state.services.store is None
    submit(
        client,
        ALICE,
        asset_id="PRESS-04",
        side="OFFER",
        requested_hours="10",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    taker = submit(
        client,
        BOB,
        asset_id="PRESS-04",
        side="REQUEST",
        requested_hours="4",
        mode="RATE_CAPPED",
        max_hourly_rate="100.00",
    )
    assert taker.status_code == 201
    assert taker.json()["status"] == "ASSIGNED"


def test_closed_configured_store_is_a_persistence_failure(
    store: TelemetryStore,
) -> None:
    app = build_app(store=store, enable_store=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        submit(
            client,
            ALICE,
            asset_id="PRESS-04",
            side="OFFER",
            requested_hours="10",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
        )
        store.close()

        response = submit(
            client,
            BOB,
            asset_id="PRESS-04",
            side="REQUEST",
            requested_hours="4",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
        )
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "assignment_persistence_failed"
        assert detail["status"] == "ASSIGNED"
        assert detail["assigned_hours"] == "4"
        assert len(detail["assignment_ids"]) == 1

        assert client.get("/api/v1/workloads", headers=BOB).json()["count"] == 1


def test_long_client_work_order_ids_persist_intact(store: TelemetryStore) -> None:
    maker_id = "m" * 64
    taker_id = "t" * 64
    with TestClient(build_app(store=store, enable_store=True)) as client:
        submit(
            client,
            ALICE,
            asset_id="PRESS-04",
            side="OFFER",
            requested_hours="10",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
            work_order_id=maker_id,
        )
        taker = submit(
            client,
            BOB,
            asset_id="PRESS-04",
            side="REQUEST",
            requested_hours="4",
            mode="RATE_CAPPED",
            max_hourly_rate="100.00",
            work_order_id=taker_id,
        )
        assert taker.status_code == 201

    row = store.get_assignments("PRESS-04")[0]
    assert row.requester_work_order_id == taker_id
    assert row.provider_work_order_id == maker_id
    assert len(row.requester_work_order_id) == 64


async def test_feed_marks_engine_workloads_from_generated_readings() -> None:
    app = build_app(enable_feed=True, enable_store=False)
    engine = app.state.services.engine

    async with app.router.lifespan_context(app):
        await engine.submit_work_order(
            WorkOrder(
                organization_id="alice",
                asset_id="CNC-01",
                side=DispatchSide.OFFER,
                mode=WorkOrderMode.RATE_CAPPED,
                requested_hours=1,
                max_hourly_rate="85.00",
            )
        )
        await engine.submit_work_order(
            WorkOrder(
                organization_id="bob",
                asset_id="CNC-01",
                side=DispatchSide.REQUEST,
                mode=WorkOrderMode.RATE_CAPPED,
                requested_hours=1,
                max_hourly_rate="85.00",
            )
        )
        workload = engine.workload_manager.get_workloads("bob")["CNC-01"]
        assert workload.last_rate == Decimal("85.00")

        for _ in range(50):
            await asyncio.sleep(0.02)
            if workload.last_rate != Decimal("85.00"):
                break

        assert workload.last_rate != Decimal("85.00")
        assert (
            workload.unrealized_cost
            == (workload.last_rate - workload.average_service_rate) * workload.net_hours
        )
