"""Focused tests for the QuantCore application factory and REST surface.

Covers: lifespan and app-instance isolation, public vs protected routes,
401/403 and least-privilege permission checks, explicit CORS, the authenticated
order lifecycle (maker/taker, fractional lots, rejections, duplicates, cancel,
ownership), client-scoped positions and risk, the dashboard payload contract,
parameterised instrument search, trade persistence, feed-driven marking, and
exception-safe startup/shutdown without leaked tasks.
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
from qxm.api.dependencies import API_KEY_HEADER
from qxm.api.service import TradingService
from qxm.auth.keys import KeyManager
from qxm.core.engine import MatchingEngine
from qxm.core.events import EventBus
from qxm.core.models import Instrument, InstrumentType, Order, OrderType, Side
from qxm.data.store import TimeSeriesStore

ALICE_KEY = "qxm_test_alice_key_0123456789abc"
BOB_KEY = "qxm_test_bob_key_0123456789abcde"
READER_KEY = "qxm_test_reader_key_0123456789ab"
TRADER_ONLY_KEY = "qxm_test_traderonly_key_01234567"

ALICE = {API_KEY_HEADER: ALICE_KEY}
BOB = {API_KEY_HEADER: BOB_KEY}
READER = {API_KEY_HEADER: READER_KEY}
TRADER_ONLY = {API_KEY_HEADER: TRADER_ONLY_KEY}

DASHBOARD_KEYS = {
    "as_of",
    "currency",
    "kpis",
    "positions",
    "pnl_history",
    "risk",
    "order_books",
}


def build_instruments() -> dict[str, Instrument]:
    return {
        "AAPL": Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size="0.01",
            lot_size="1",
            currency="USD",
            exchange="NASDAQ",
        ),
        "SAP": Instrument(
            symbol="SAP",
            name="SAP SE",
            instrument_type=InstrumentType.EQUITY,
            tick_size="0.01",
            lot_size="1",
            currency="EUR",
            exchange="XETRA",
        ),
        "BTC-USD": Instrument(
            symbol="BTC-USD",
            name="Bitcoin / US Dollar",
            instrument_type=InstrumentType.CRYPTO,
            tick_size="0.01",
            lot_size="0.001",
            currency="USD",
            exchange="QUANTCORE",
        ),
    }


def build_config(**overrides: Any) -> dict[str, Any]:
    config: dict[str, Any] = {
        "server": {"host": "127.0.0.1", "port": 8443},
        "database": {"url": "sqlite://"},
        "feed": {"mode": "simulated", "interval_ms": 10, "seed": 7},
        "auth": {"key_ttl_seconds": 86400},
        "risk": {},
        "logging": {"level": "INFO"},
    }
    config.update(overrides)
    return config


def build_key_manager() -> KeyManager:
    manager = KeyManager("api-test-secret")
    manager.register_key(ALICE_KEY, "alice", permissions=["read", "trade"])
    manager.register_key(BOB_KEY, "bob", permissions=["read", "trade"])
    manager.register_key(READER_KEY, "reader", permissions=["read"])
    manager.register_key(TRADER_ONLY_KEY, "trader_only", permissions=["trade"])
    return manager


def build_app(**kwargs: Any) -> Any:
    kwargs.setdefault("config", build_config())
    kwargs.setdefault("instruments", build_instruments())
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
def store() -> Iterator[TimeSeriesStore]:
    store = TimeSeriesStore("sqlite://")
    try:
        yield store
    finally:
        store.close()


def submit(client: TestClient, headers: dict[str, str], **payload: Any) -> Any:
    return client.post("/api/v1/orders", headers=headers, json=payload)


# ---------------------------------------------------------------------------
# Factory, lifespan, isolation
# ---------------------------------------------------------------------------


def test_app_metadata_describes_an_educational_simulator() -> None:
    app = build_app()
    assert app.version == "0.5.0"
    assert "Simulator" in app.title
    description = app.description.lower()
    assert "simulation-only" in description
    assert "high-performance" not in description
    assert "production" not in description


def test_lifespan_starts_and_stops_event_bus(client: TestClient) -> None:
    services = client.app.state.services
    assert services.event_bus.is_running is True
    assert client.app.state.feed_task is None
    assert client.get("/api/v1/health").status_code == 200


def test_app_instances_are_isolated() -> None:
    first = build_app()
    second_manager = KeyManager("other-secret")
    second_manager.register_key(BOB_KEY, "bob", permissions=["read", "trade"])
    second = build_app(key_manager=second_manager)

    assert first.state.services.engine is not second.state.services.engine
    assert first.state.services.trading is not second.state.services.trading

    with TestClient(first) as first_client, TestClient(second) as second_client:
        created = submit(
            first_client, ALICE, symbol="AAPL", side="BUY", quantity="5", price="150.00"
        )
        assert created.status_code == 201

        # The second application knows neither alice's key nor her order.
        assert first_client.get("/api/v1/orders", headers=ALICE).json()["count"] == 1
        assert second_client.get("/api/v1/orders", headers=ALICE).status_code == 403
        assert second_client.get("/api/v1/orders", headers=BOB).json()["count"] == 0


def test_missing_config_and_instrument_files_raise(tmp_path: Any) -> None:
    with pytest.raises(FileNotFoundError):
        main.load_config(tmp_path / "absent.yaml")
    with pytest.raises(FileNotFoundError):
        main.load_instruments(tmp_path / "absent.json")

    malformed = tmp_path / "instruments.json"
    malformed.write_text('{"symbol": "AAPL"}', encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_instruments(malformed)

    broken_yaml = tmp_path / "settings.yaml"
    broken_yaml.write_text("server: [unclosed\n", encoding="utf-8")
    with pytest.raises(yaml.YAMLError):
        main.load_config(broken_yaml)

    empty_yaml = tmp_path / "empty.yaml"
    empty_yaml.write_text("", encoding="utf-8")
    with pytest.raises(ValueError):
        main.load_config(empty_yaml)


def test_repository_config_and_instruments_load() -> None:
    config = main.load_config()
    assert main.coerce_port(config["server"]["port"]) == 8443
    assert config["server"]["host"] == "127.0.0.1"
    assert config["dashboard"]["currency"] == "EUR"
    assert config["feed"]["seed"] == 7
    main.validate_config_keys(config)
    instruments = main.load_instruments()
    assert "SAP" in instruments
    assert instruments["BTC-USD"].lot_size == Decimal("0.001")


def test_app_requires_a_nonempty_consistent_instrument_mapping() -> None:
    with pytest.raises(ValueError, match="At least one simulated instrument"):
        build_app(instruments={})

    instruments = build_instruments()
    with pytest.raises(ValueError, match="does not match symbol"):
        build_app(instruments={"WRONG": instruments["SAP"]})


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
    assert body["version"] == "0.5.0"
    assert body["mode"] == "simulation"
    # This application runs without a feed, so nothing is missing.
    assert body["feed"] == "off"

    stamp = datetime.fromisoformat(body["timestamp"])
    assert stamp.tzinfo is not None
    assert stamp.utcoffset() == timedelta(0)


def test_dashboard_shell_is_served_same_origin_without_auth(client: TestClient) -> None:
    response = client.get("/")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/html")
    assert "QuantCore" in response.text


@pytest.mark.parametrize(
    "path",
    [
        "/api/v1/orders",
        "/api/v1/positions",
        "/api/v1/portfolio/snapshot",
        "/api/v1/portfolio/risk",
        "/api/v1/dashboard",
        "/api/v1/metrics",
        "/api/v1/strategies",
    ],
)
def test_protected_endpoints_require_a_key(client: TestClient, path: str) -> None:
    missing = client.get(path)
    assert missing.status_code == 401
    assert API_KEY_HEADER in missing.json()["detail"]

    invalid = client.get(path, headers={API_KEY_HEADER: "qxm_not_a_real_key"})
    assert invalid.status_code == 403


def test_expired_and_revoked_keys_are_forbidden() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    clock = {"now": now}
    manager = KeyManager("api-test-secret", clock=lambda: clock["now"])
    manager.register_key(ALICE_KEY, "alice", permissions=["read"], ttl_seconds=60)
    revoked = manager.register_key(BOB_KEY, "bob", permissions=["read"])

    with TestClient(build_app(key_manager=manager)) as client:
        assert client.get("/api/v1/positions", headers=ALICE).status_code == 200

        manager.revoke_key(revoked.key_id)
        assert client.get("/api/v1/positions", headers=BOB).status_code == 403

        clock["now"] = now + timedelta(seconds=61)
        assert client.get("/api/v1/positions", headers=ALICE).status_code == 403


def test_permissions_are_least_privilege(client: TestClient) -> None:
    read_only = submit(client, READER, symbol="AAPL", side="BUY", quantity="1", price="150.00")
    assert read_only.status_code == 403
    assert "trade" in read_only.json()["detail"]

    trade_only = client.get("/api/v1/orders", headers=TRADER_ONLY)
    assert trade_only.status_code == 403
    assert "read" in trade_only.json()["detail"]

    assert client.get("/api/v1/positions", headers=READER).status_code == 200


def test_client_identity_cannot_be_supplied_by_the_caller(client: TestClient) -> None:
    response = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.00",
        client_id="bob",
    )
    assert response.status_code == 422

    accepted = submit(client, ALICE, symbol="AAPL", side="BUY", quantity="1", price="150.00")
    assert accepted.json()["order"]["client_id"] == "alice"


def test_no_bootstrap_key_leaves_protected_endpoints_inaccessible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(main.BOOTSTRAP_KEY_ENV, raising=False)
    manager = KeyManager("api-test-secret")
    app = build_app(key_manager=manager)
    assert manager.key_count == 0

    with TestClient(app) as client:
        assert client.get("/api/v1/health").status_code == 200
        assert client.get("/api/v1/dashboard").status_code == 401
        assert client.get("/api/v1/dashboard", headers=ALICE).status_code == 403


def test_bootstrap_key_can_be_injected_for_local_use() -> None:
    raw = "qxm_injected_bootstrap_key_00001"
    app = build_app(
        key_manager=KeyManager("api-test-secret"),
        bootstrap_api_key=raw,
        bootstrap_client_id="operator",
    )
    with TestClient(app) as client:
        response = client.get("/api/v1/dashboard", headers={API_KEY_HEADER: raw})
        assert response.status_code == 200
        # The raw key is never echoed back by the API.
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
# Order lifecycle
# ---------------------------------------------------------------------------


def test_maker_taker_match_executes_at_the_resting_price(client: TestClient) -> None:
    maker = submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="150.00")
    assert maker.status_code == 201
    assert maker.json()["status"] == "ACCEPTED"
    assert maker.json()["trades"] == []

    taker = submit(client, BOB, symbol="SAP", side="BUY", quantity="4", price="151.00")
    body = taker.json()
    assert taker.status_code == 201
    assert body["status"] == "FILLED"
    assert body["filled_quantity"] == "4"
    assert [trade["price"] for trade in body["trades"]] == ["150.00"]
    assert body["trades"][0]["aggressor_side"] == "BUY"

    # The maker order object reflects its partial fill through the live registry.
    maker_state = client.get(f"/api/v1/orders/{maker.json()['order_id']}", headers=ALICE).json()
    assert maker_state["status"] == "PARTIALLY_FILLED"
    assert maker_state["filled_quantity"] == "4"


def test_fractional_quantities_are_supported(client: TestClient) -> None:
    submit(client, ALICE, symbol="BTC-USD", side="SELL", quantity="0.005", price="60000.00")
    taker = submit(client, BOB, symbol="BTC-USD", side="BUY", quantity="0.003", price="60000.00")
    assert taker.status_code == 201
    assert taker.json()["filled_quantity"] == "0.003"
    assert taker.json()["trades"][0]["quantity"] == "0.003"


@pytest.mark.parametrize(
    ("payload", "expected_fragment"),
    [
        (
            {"symbol": "NOPE", "side": "BUY", "quantity": "1", "price": "10.00"},
            "Unknown instrument",
        ),
        ({"symbol": "AAPL", "side": "BUY", "quantity": "1", "price": "150.005"}, "tick size"),
        (
            {"symbol": "BTC-USD", "side": "BUY", "quantity": "0.0005", "price": "100.00"},
            "lot size",
        ),
        (
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": "1",
                "price": "150.00",
                "time_in_force": "DAY",
            },
            "DAY time-in-force is not supported",
        ),
        (
            {
                "symbol": "AAPL",
                "side": "BUY",
                "quantity": "1",
                "order_type": "STOP",
                "stop_price": "150.00",
            },
            "STOP orders are not supported",
        ),
    ],
)
def test_domain_rejections_use_a_stable_contract(
    client: TestClient, payload: dict[str, Any], expected_fragment: str
) -> None:
    response = submit(client, ALICE, **payload)
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "order_rejected"
    assert detail["status"] == "REJECTED"
    assert expected_fragment in detail["reason"]
    assert client.get("/api/v1/orders", headers=ALICE).json()["count"] == 1


def test_schema_valid_but_domain_invalid_orders_are_reported(client: TestClient) -> None:
    response = submit(client, ALICE, symbol="AAPL", side="BUY", quantity="1")
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "invalid_order"
    assert "price" in detail["reason"].lower()


@pytest.mark.parametrize(
    "payload",
    [
        {"symbol": "AAPL", "side": "SIDEWAYS", "quantity": "1", "price": "10.00"},
        {"symbol": "AAPL", "side": "BUY", "quantity": "0", "price": "10.00"},
        {"symbol": "AAPL", "side": "BUY", "quantity": "-5", "price": "10.00"},
        {"symbol": "AAPL", "side": "BUY", "quantity": "1", "price": "-10.00"},
        {"side": "BUY", "quantity": "1", "price": "10.00"},
    ],
)
def test_schema_violations_are_rejected_before_the_engine(
    client: TestClient, payload: dict[str, Any]
) -> None:
    assert submit(client, ALICE, **payload).status_code == 422


def test_duplicate_order_id_conflicts_without_mutating_either_order(
    client: TestClient,
) -> None:
    first = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="10",
        price="150.00",
        order_id="idem-1",
    )
    assert first.status_code == 201
    original = client.get("/api/v1/orders/idem-1", headers=ALICE).json()

    duplicate = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="SELL",
        quantity="99",
        price="1.00",
        order_id="idem-1",
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == {
        "error": "duplicate_order_id",
        "order_id": "idem-1",
    }

    unchanged = client.get("/api/v1/orders/idem-1", headers=ALICE).json()
    assert unchanged == original
    assert client.get("/api/v1/orders", headers=ALICE).json()["count"] == 1


async def test_service_rejection_reason_does_not_depend_on_event_replay() -> None:
    event_bus = EventBus(persist=False)
    engine = MatchingEngine(event_bus, build_instruments())
    service = TradingService(engine, event_bus)
    order = Order(
        order_id="direct-rejection-reason",
        client_id="alice",
        symbol="AAPL",
        side=Side.BUY,
        order_type=OrderType.LIMIT,
        quantity=Decimal("1.5"),
        price=Decimal("90"),
    )

    result = await service.submit_order("alice", order)

    assert event_bus.event_log is None
    assert result.accepted is False
    assert result.rejection_reason == "Quantity 1.5 is not a multiple of lot size 1"


def test_order_ids_are_never_reusable_even_after_rejection(client: TestClient) -> None:
    rejected = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.005",
        order_id="reserved-1",
    )
    assert rejected.status_code == 400

    retry = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.00",
        order_id="reserved-1",
    )
    assert retry.status_code == 409


def test_order_listing_is_scoped_to_the_authenticated_client(client: TestClient) -> None:
    alice_order = submit(
        client, ALICE, symbol="AAPL", side="BUY", quantity="1", price="150.00"
    ).json()["order_id"]
    submit(client, BOB, symbol="AAPL", side="BUY", quantity="2", price="149.00")

    alice_orders = client.get("/api/v1/orders", headers=ALICE).json()
    assert alice_orders["count"] == 1
    assert alice_orders["orders"][0]["order_id"] == alice_order
    assert all(order["client_id"] == "alice" for order in alice_orders["orders"])

    assert client.get("/api/v1/orders", headers=BOB).json()["count"] == 1
    assert client.get("/api/v1/orders", headers=READER).json()["count"] == 0
    # Another client's order id is indistinguishable from an unknown one.
    assert client.get(f"/api/v1/orders/{alice_order}", headers=BOB).status_code == 404


def test_cancel_enforces_ownership_and_reports_terminal_orders(
    client: TestClient,
) -> None:
    order_id = submit(
        client, ALICE, symbol="AAPL", side="BUY", quantity="10", price="150.00"
    ).json()["order_id"]

    assert client.delete(f"/api/v1/orders/{order_id}", headers=BOB).status_code == 404
    assert client.delete(f"/api/v1/orders/{order_id}", headers=READER).status_code == 403

    cancelled = client.delete(f"/api/v1/orders/{order_id}", headers=ALICE)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert cancelled.json()["order"]["order_id"] == order_id

    repeat = client.delete(f"/api/v1/orders/{order_id}", headers=ALICE)
    assert repeat.status_code == 409
    assert repeat.json()["detail"]["error"] == "order_not_resting"
    assert repeat.json()["detail"]["status"] == "CANCELLED"

    assert client.delete("/api/v1/orders/does-not-exist", headers=ALICE).status_code == 404


# ---------------------------------------------------------------------------
# Positions, portfolio, risk
# ---------------------------------------------------------------------------


def test_positions_and_portfolio_are_client_scoped(client: TestClient) -> None:
    submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="100.00")
    submit(client, BOB, symbol="SAP", side="BUY", quantity="10", price="100.00")

    alice = client.get("/api/v1/positions", headers=ALICE).json()
    bob = client.get("/api/v1/positions", headers=BOB).json()
    assert alice["client_id"] == "alice"
    assert alice["positions"][0]["quantity"] == "-10"
    assert bob["positions"][0]["quantity"] == "10"
    assert all(p["client_id"] == "alice" for p in alice["positions"])

    # Counterparties must not net each other out in a shared portfolio.
    alice_snapshot = client.get("/api/v1/portfolio/snapshot", headers=ALICE).json()
    bob_snapshot = client.get("/api/v1/portfolio/snapshot", headers=BOB).json()
    assert alice_snapshot["client_id"] == "alice"
    assert Decimal(alice_snapshot["total_market_value"]) == Decimal("-1000.00")
    assert Decimal(bob_snapshot["total_market_value"]) == Decimal("1000.00")

    assert client.get("/api/v1/positions", headers=READER).json()["positions"] == []


def test_risk_payload_is_honest_without_a_volatility_assumption(
    client: TestClient,
) -> None:
    risk = client.get("/api/v1/portfolio/risk", headers=ALICE).json()
    assert risk["var_95"] is None
    assert risk["var_99"] is None
    assert risk["sharpe_ratio"] is None
    assert risk["max_drawdown"] is None
    assert Decimal(risk["gross_exposure"]) == Decimal("0")


def test_var_is_computed_when_a_volatility_assumption_is_configured() -> None:
    config = build_config(risk={"daily_volatility": 0.02})
    with TestClient(build_app(config=config)) as client:
        submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="100.00")
        submit(client, BOB, symbol="SAP", side="BUY", quantity="10", price="100.00")
        risk = client.get("/api/v1/portfolio/risk", headers=ALICE).json()
        assert Decimal(risk["var_95"]) > 0
        assert Decimal(risk["var_99"]) > Decimal(risk["var_95"])


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
    assert body["positions"] == []
    assert body["pnl_history"] == []
    assert body["order_books"] == {}
    assert set(body["kpis"]) >= {
        "portfolio_value",
        "realized_pnl",
        "unrealized_pnl",
        "var_95",
        "active_orders",
    }
    assert body["kpis"]["active_orders"] == 0


def test_dashboard_populated_state_exposes_positions_orders_and_books(
    client: TestClient,
) -> None:
    submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="100.00")
    submit(client, BOB, symbol="SAP", side="BUY", quantity="4", price="100.00")
    submit(client, BOB, symbol="AAPL", side="BUY", quantity="3", price="149.00")

    body = client.get("/api/v1/dashboard", headers=BOB).json()
    assert set(body) == DASHBOARD_KEYS

    position = body["positions"][0]
    assert position["symbol"] == "SAP"
    assert position["currency"] == "EUR"
    assert Decimal(position["quantity"]) == Decimal("4")
    assert Decimal(position["average_entry_price"]) == Decimal("100.00")
    assert Decimal(position["market_price"]) == Decimal("100.00")
    assert Decimal(position["total_pnl"]) == Decimal(position["realized_pnl"]) + Decimal(
        position["unrealized_pnl"]
    )

    assert body["kpis"]["active_orders"] == 1
    assert Decimal(body["kpis"]["portfolio_value"]) == Decimal("400.00")

    books = body["order_books"]
    assert set(books) == {"AAPL", "SAP"}
    assert books["AAPL"]["bids"][0]["price"] == "149.00"
    assert books["AAPL"]["bids"][0]["quantity"] == "3"
    assert books["AAPL"]["bids"][0]["orders"] == 1
    assert books["AAPL"]["asks"] == []

    history = body["pnl_history"]
    assert len(history) == 1
    stamp = datetime.fromisoformat(history[0]["timestamp"])
    assert stamp.utcoffset() == timedelta(0)
    assert Decimal(history[0]["value"]) == Decimal("0.00")

    # The dashboard view of another client is that client's own data only.
    alice_body = client.get("/api/v1/dashboard", headers=ALICE).json()
    assert Decimal(alice_body["positions"][0]["quantity"]) == Decimal("-4")


def test_position_payloads_carry_each_instruments_own_currency(
    client: TestClient,
) -> None:
    submit(client, ALICE, symbol="SAP", side="SELL", quantity="1", price="100.00")
    submit(client, BOB, symbol="SAP", side="BUY", quantity="1", price="100.00")
    submit(client, ALICE, symbol="AAPL", side="SELL", quantity="1", price="150.00")
    submit(client, BOB, symbol="AAPL", side="BUY", quantity="1", price="150.00")

    positions = client.get("/api/v1/positions", headers=BOB).json()["positions"]
    assert {position["symbol"]: position["currency"] for position in positions} == {
        "AAPL": "USD",
        "SAP": "EUR",
    }

    dashboard_positions = client.get("/api/v1/dashboard", headers=BOB).json()["positions"]
    assert {position["symbol"]: position["currency"] for position in dashboard_positions} == {
        "AAPL": "USD",
        "SAP": "EUR",
    }


# ---------------------------------------------------------------------------
# Instrument search
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    ["' OR 1=1 --", "'; DROP TABLE instruments; --", "%", "_"],
)
def test_instrument_search_injection_payloads_are_inert(
    store: TimeSeriesStore, payload: str
) -> None:
    app = build_app(store=store, enable_store=True)
    with TestClient(app) as client:
        response = client.get("/api/v1/instruments/search", headers=READER, params={"q": payload})
        assert response.status_code == 200
        assert response.json()["results"] == []
        # Reference data survives every payload.
        assert store.count_instruments() == 3


def test_instrument_search_is_seeded_bounded_and_authenticated(
    store: TimeSeriesStore,
) -> None:
    app = build_app(store=store, enable_store=True)
    with TestClient(app) as client:
        assert client.get("/api/v1/instruments/search", params={"q": "sap"}).status_code == 401

        found = client.get("/api/v1/instruments/search", headers=READER, params={"q": "sap"}).json()
        assert found["count"] == 1
        assert found["results"][0]["symbol"] == "SAP"
        assert found["results"][0]["currency"] == "EUR"

        limited = client.get(
            "/api/v1/instruments/search", headers=READER, params={"q": "a", "limit": 1}
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
                client.get("/api/v1/instruments/search", headers=READER, params=params).status_code
                == 422
            )


def test_instrument_search_falls_back_to_in_memory_reference_data(
    client: TestClient,
) -> None:
    response = client.get("/api/v1/instruments/search", headers=READER, params={"q": "bitcoin"})
    assert response.status_code == 200
    assert [row["symbol"] for row in response.json()["results"]] == ["BTC-USD"]
    assert (
        client.get(
            "/api/v1/instruments/search", headers=READER, params={"q": "' OR 1=1 --"}
        ).json()["results"]
        == []
    )


def test_strategies_and_metrics_require_read_permission(client: TestClient) -> None:
    strategies = client.get("/api/v1/strategies", headers=READER)
    assert strategies.status_code == 200
    assert "MomentumBreakout" in strategies.json()["strategies"]

    metrics = client.get("/api/v1/metrics", headers=READER)
    assert metrics.status_code == 200
    assert isinstance(metrics.json(), dict)

    assert client.get("/api/v1/strategies", headers=TRADER_ONLY).status_code == 403
    assert client.get("/api/v1/metrics", headers=TRADER_ONLY).status_code == 403


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
        assert app.state.feed_task.get_name() == "qxm-market-feed"

    assert app.state.feed_task is None
    assert app.state.services.feed.is_running is False
    assert app.state.services.event_bus.is_running is False

    current = asyncio.current_task()
    leaked = [task for task in asyncio.all_tasks() if task is not current]
    assert leaked == []


async def test_owned_store_is_closed_on_shutdown_and_injected_store_is_not(
    store: TimeSeriesStore,
) -> None:
    owned_app = main.create_app(
        build_config(database={"url": "sqlite://"}),
        instruments=build_instruments(),
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
    """An advertised-but-unwired mode must never be silently downgraded."""
    with pytest.raises(ValueError, match="websocket") as excinfo:
        feed_app("websocket", enable_feed=enable_feed)
    message = str(excinfo.value)
    assert "WebSocketFeedAdapter" in message
    assert "simulated" in message
    assert "disabled" in message


@pytest.mark.parametrize("mode", ["simulted", "live", "real", "", "  "])
def test_unknown_feed_modes_are_rejected_instead_of_disabling_market_data(
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
    # Argument off beats a config that asks for the simulator.
    assert feed_app("simulated", enable_feed=False).state.services.feed is None
    # Argument on beats an explicitly disabled config, still simulated.
    turned_on = feed_app("disabled", enable_feed=True).state.services.feed
    assert turned_on is not None
    assert type(turned_on).__name__ == "MarketDataFeed"


def test_feed_mode_is_validated_even_when_the_argument_disables_the_feed() -> None:
    """A broken config is a config error however this process was started."""
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
    real_feed = main.MarketDataFeed

    def recording_feed(*args: Any, **kwargs: Any) -> Any:
        captured.update(kwargs)
        return real_feed(*args, **kwargs)

    monkeypatch.setattr(main, "MarketDataFeed", recording_feed)
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
def test_daily_volatility_must_be_finite_and_positive(volatility: Any) -> None:
    config = build_config(risk={"daily_volatility": volatility})
    with pytest.raises((TypeError, ValueError)):
        build_app(config=config)


# ---------------------------------------------------------------------------
# Regressions: liveness tells the truth about the feed
# ---------------------------------------------------------------------------


async def get_health(app: Any) -> dict[str, Any]:
    """Call the public health endpoint on the running application."""
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

    async def failing_ticks() -> Any:
        raise RuntimeError("pump exploded with secret detail")
        yield  # pragma: no cover - generator marker

    services.feed.generate_ticks = failing_ticks  # type: ignore[method-assign]

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
            # The public probe never explains the failure.
            assert "pump exploded" not in response.text
            assert "secret detail" not in response.text
            assert "RuntimeError" not in response.text
            assert set(body) == {"status", "version", "timestamp", "mode", "feed"}


async def test_early_feed_completion_degrades_liveness() -> None:
    app = build_app(enable_feed=True)
    services = app.state.services

    async def finished_ticks() -> Any:
        return
        yield  # pragma: no cover - generator marker

    services.feed.generate_ticks = finished_ticks  # type: ignore[method-assign]

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
def store_client(store: TimeSeriesStore) -> Iterator[TestClient]:
    """Client for an application backed by a seeded in-memory store."""
    with TestClient(build_app(store=store, enable_store=True)) as test_client:
        yield test_client


@pytest.mark.parametrize("raw_query", ["q=%20", "q=%09", "q=%20%09%20", "q=+"])
def test_blank_search_terms_are_rejected_identically_by_both_backends(
    client: TestClient, store_client: TestClient, raw_query: str
) -> None:
    """Whitespace-only input is a client error, never a 500 or a full listing."""
    for backend in (client, store_client):
        response = backend.get(f"/api/v1/instruments/search?{raw_query}", headers=READER)
        assert response.status_code == 422
        assert response.json()["detail"][0]["loc"][-1] == "q"


def test_search_terms_are_trimmed_before_reaching_either_backend(
    client: TestClient, store_client: TestClient
) -> None:
    for backend in (client, store_client):
        body = backend.get(
            "/api/v1/instruments/search", headers=READER, params={"q": "  sap  "}
        ).json()
        assert body["query"] == "sap"
        assert [row["symbol"] for row in body["results"]] == ["SAP"]


def test_in_memory_search_never_returns_everything_for_padded_input(
    client: TestClient,
) -> None:
    total = len(build_instruments())
    padded = client.get("/api/v1/instruments/search", headers=READER, params={"q": " s "}).json()
    assert 0 < padded["count"] < total


# ---------------------------------------------------------------------------
# Regressions: order ids must stay addressable through the URL
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "order_id",
    ["a/b", "../escape", "a b", "a?b", "a#b", "a%2Fb", "a\\b", "x" * 65, "ümlaut"],
)
def test_unsafe_client_order_ids_are_rejected_before_the_engine(
    client: TestClient, order_id: str
) -> None:
    response = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.00",
        order_id=order_id,
    )
    assert response.status_code == 422
    # Nothing reached the matching engine, so no id was reserved and no order
    # was registered.
    assert client.app.state.services.engine.order_count == 0
    assert client.get("/api/v1/orders", headers=ALICE).json()["count"] == 0


@pytest.mark.parametrize(
    "order_id",
    [".", "..", "...", ".hidden", "trailing.", "-leading", "trailing-", ":x", "x:"],
)
def test_dot_segment_and_edge_punctuation_ids_are_rejected(
    client: TestClient, order_id: str
) -> None:
    """``.`` and ``..`` are normalised path segments, not addressable ids."""
    response = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.00",
        order_id=order_id,
    )
    assert response.status_code == 422
    # Rejected before the engine, so the id is never reserved and can still be
    # used once the client sends a well-formed one.
    assert client.app.state.services.engine.order_count == 0
    assert client.get("/api/v1/orders", headers=ALICE).json()["count"] == 0


@pytest.mark.parametrize("order_id", ["a", "9", "a.b", "a:b-c_d", "x" * 64])
def test_boundary_safe_ids_are_accepted_and_addressable(client: TestClient, order_id: str) -> None:
    created = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.00",
        order_id=order_id,
    )
    assert created.status_code == 201
    assert client.get(f"/api/v1/orders/{order_id}", headers=ALICE).status_code == 200
    assert client.delete(f"/api/v1/orders/{order_id}", headers=ALICE).status_code == 200


@pytest.mark.parametrize("order_id", ["plain-1", "ok_id.2:3", "A1-b2_c3.d4:e5"])
def test_safe_client_order_ids_round_trip_through_the_url(
    client: TestClient, order_id: str
) -> None:
    created = submit(
        client,
        ALICE,
        symbol="AAPL",
        side="BUY",
        quantity="1",
        price="150.00",
        order_id=order_id,
    )
    assert created.status_code == 201
    assert created.json()["order_id"] == order_id

    fetched = client.get(f"/api/v1/orders/{order_id}", headers=ALICE)
    assert fetched.status_code == 200
    assert fetched.json()["order_id"] == order_id

    cancelled = client.delete(f"/api/v1/orders/{order_id}", headers=ALICE)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"


def test_engine_generated_uuid_ids_remain_addressable(client: TestClient) -> None:
    order_id = submit(
        client, ALICE, symbol="AAPL", side="BUY", quantity="1", price="150.00"
    ).json()["order_id"]
    assert client.get(f"/api/v1/orders/{order_id}", headers=ALICE).status_code == 200
    assert client.delete(f"/api/v1/orders/{order_id}", headers=ALICE).status_code == 200


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
    [
        ({}, 401),
        ({API_KEY_HEADER: "qxm_not_a_real_key"}, 403),
        (ALICE, 200),
    ],
)
def test_cors_headers_are_present_on_auth_failures_too(
    headers: dict[str, str], expected_status: int
) -> None:
    origin = "https://dashboard.example"
    with TestClient(build_cors_app(origin)) as client:
        response = client.get("/api/v1/dashboard", headers={"Origin": origin, **headers})
        assert response.status_code == expected_status
        # Without this header the browser dashboard cannot read the status at
        # all and reports an opaque network error instead of "invalid key".
        assert response.headers["access-control-allow-origin"] == origin


def test_cors_preflight_is_answered_without_a_key() -> None:
    origin = "https://dashboard.example"
    with TestClient(build_cors_app(origin)) as client:
        response = client.options(
            "/api/v1/orders",
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
        assert response.headers["access-control-allow-origin"] == ("https://dashboard.example")
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
    """A wiring error after the engine is opened must not leak it."""
    created: list[TimeSeriesStore] = []
    real_store = main.TimeSeriesStore

    def recording_store(*args: Any, **kwargs: Any) -> TimeSeriesStore:
        store = real_store(*args, **kwargs)
        created.append(store)
        return store

    monkeypatch.setattr(main, "TimeSeriesStore", recording_store)

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

    # Every remaining step still ran despite the failure above.
    assert services.event_bus.is_running is False
    assert owned_store.is_closed is True
    assert app.state.feed_task is None


async def test_cancelled_teardown_step_still_releases_everything_and_propagates() -> None:
    """Cancellation must keep its semantics without stranding other resources."""
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

    # The store still got closed even though the interrupt came first.
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

    caplog.set_level(logging.ERROR, logger="qxm")
    with pytest.raises(asyncio.CancelledError):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.02)

    assert owned_store.is_closed is True
    assert any("feed stop exploded" in record.getMessage() for record in caplog.records)


async def test_partially_started_feed_still_receives_a_stop() -> None:
    """A start that mutates state before failing must still be stopped."""
    app = build_app(enable_feed=True, enable_store=True)
    services = app.state.services
    owned_store = services.store
    assert owned_store is not None
    feed = services.feed
    real_stop = feed.stop
    calls: list[str] = []

    async def half_start() -> None:
        feed._running = True  # partial acquisition, then failure
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

    async def failing_ticks() -> Any:
        raise RuntimeError("pump exploded")
        yield  # pragma: no cover - generator marker

    services.feed.generate_ticks = failing_ticks  # type: ignore[method-assign]

    caplog.set_level(logging.ERROR, logger="qxm")
    with pytest.raises(RuntimeError, match="pump exploded"):
        async with app.router.lifespan_context(app):
            await asyncio.sleep(0.05)
            # The supervisor reports the dead pump immediately, not only at
            # shutdown.
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

    async def finished_ticks() -> Any:
        return
        yield  # pragma: no cover - generator marker

    services.feed.generate_ticks = finished_ticks  # type: ignore[method-assign]

    caplog.set_level(logging.ERROR, logger="qxm")
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

    caplog.set_level(logging.ERROR, logger="qxm")
    with pytest.raises(ValueError, match="body boom"):
        async with app.router.lifespan_context(app):
            raise ValueError("body boom")

    assert owned_store.is_closed is True
    assert services.event_bus.is_running is False
    assert any("cleanup boom" in record.getMessage() for record in caplog.records)


# ---------------------------------------------------------------------------
# Regressions: order-flow persistence and feed-driven marking
# ---------------------------------------------------------------------------


def test_executed_trades_are_persisted_exactly_once(store: TimeSeriesStore) -> None:
    with TestClient(build_app(store=store, enable_store=True)) as client:
        maker = submit(
            client, ALICE, symbol="SAP", side="SELL", quantity="10", price="150.55"
        ).json()
        taker = submit(client, BOB, symbol="SAP", side="BUY", quantity="4", price="151.00").json()

        assert taker["status"] == "FILLED"
        trade = taker["trades"][0]

        rows = store.get_trades("SAP")
        assert len(rows) == 1
        row = rows[0]
        assert row.trade_id == trade["trade_id"]
        assert row.symbol == "SAP"
        assert row.buy_order_id == taker["order_id"]
        assert row.sell_order_id == maker["order_id"]
        assert row.price == Decimal("150.55")
        assert row.quantity == Decimal("4")
        assert row.buyer_client_id == "bob"
        assert row.seller_client_id == "alice"
        assert row.timestamp.utcoffset() == timedelta(0)
        assert row.timestamp == datetime.fromisoformat(trade["timestamp"])

        # A second execution appends exactly one more row.
        submit(client, BOB, symbol="SAP", side="BUY", quantity="6", price="151.00")
        assert store.count_trades("SAP") == 2

        # Resting-only orders produce no trades and therefore no rows.
        submit(client, ALICE, symbol="AAPL", side="BUY", quantity="1", price="150.00")
        assert store.count_trades() == 2


def test_persistence_failure_reports_the_execution_honestly(
    store: TimeSeriesStore,
) -> None:
    def failing_insert(rows: Any) -> int:
        raise OperationalError(
            "INSERT INTO trades ...", {}, Exception("sqlite:///secret/path.db is gone")
        )

    store.insert_trades = failing_insert  # type: ignore[method-assign]

    app = build_app(store=store, enable_store=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="100.00")
        response = submit(client, BOB, symbol="SAP", side="BUY", quantity="4", price="100.00")

        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "trade_persistence_failed"
        assert detail["status"] == "FILLED"
        assert detail["filled_quantity"] == "4"
        assert len(detail["trade_ids"]) == 1
        assert "do not resubmit" in detail["message"].lower()

        # No store internals or credentials leak into the response.
        assert "secret/path.db" not in response.text
        assert "INSERT INTO" not in response.text

        # The execution is not disowned: the engine state stands.
        orders = client.get("/api/v1/orders", headers=BOB).json()["orders"]
        assert [order["status"] for order in orders] == ["FILLED"]
        assert client.get("/api/v1/positions", headers=BOB).json()["count"] == 1


def test_persistence_is_optional_when_no_store_is_configured(
    client: TestClient,
) -> None:
    assert client.app.state.services.store is None
    submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="100.00")
    taker = submit(client, BOB, symbol="SAP", side="BUY", quantity="4", price="100.00")
    assert taker.status_code == 201
    assert taker.json()["status"] == "FILLED"


def test_closed_configured_store_is_a_persistence_failure(
    store: TimeSeriesStore,
) -> None:
    """A configured store that is closed is a malfunction, not "no persistence"."""
    app = build_app(store=store, enable_store=True)
    with TestClient(app, raise_server_exceptions=False) as client:
        submit(client, ALICE, symbol="SAP", side="SELL", quantity="10", price="100.00")
        store.close()

        response = submit(client, BOB, symbol="SAP", side="BUY", quantity="4", price="100.00")
        assert response.status_code == 500
        detail = response.json()["detail"]
        assert detail["error"] == "trade_persistence_failed"
        assert detail["status"] == "FILLED"
        assert detail["filled_quantity"] == "4"
        assert len(detail["trade_ids"]) == 1

        # The execution still stands and is reported honestly.
        assert client.get("/api/v1/positions", headers=BOB).json()["count"] == 1


def test_long_client_order_ids_persist_intact(store: TimeSeriesStore) -> None:
    """The trade columns match the API's 64-character order-id contract."""
    maker_id = "m" * 64
    taker_id = "t" * 64
    with TestClient(build_app(store=store, enable_store=True)) as client:
        submit(
            client,
            ALICE,
            symbol="SAP",
            side="SELL",
            quantity="10",
            price="100.00",
            order_id=maker_id,
        )
        taker = submit(
            client,
            BOB,
            symbol="SAP",
            side="BUY",
            quantity="4",
            price="100.00",
            order_id=taker_id,
        )
        assert taker.status_code == 201

    row = store.get_trades("SAP")[0]
    assert row.buy_order_id == taker_id
    assert row.sell_order_id == maker_id
    assert len(row.buy_order_id) == 64


async def test_feed_marks_engine_positions_from_generated_ticks() -> None:
    app = build_app(enable_feed=True, enable_store=False)
    engine = app.state.services.engine

    async with app.router.lifespan_context(app):
        await engine.submit_order(
            Order(
                client_id="alice",
                symbol="AAPL",
                side=Side.SELL,
                order_type=OrderType.LIMIT,
                quantity=1,
                price="185.00",
            )
        )
        await engine.submit_order(
            Order(
                client_id="bob",
                symbol="AAPL",
                side=Side.BUY,
                order_type=OrderType.LIMIT,
                quantity=1,
                price="185.00",
            )
        )
        position = engine.position_manager.get_position("bob", "AAPL")
        assert position.last_price == Decimal("185.00")

        for _ in range(50):
            await asyncio.sleep(0.02)
            if position.last_price != Decimal("185.00"):
                break

        assert position.last_price != Decimal("185.00")
        assert (
            position.unrealized_pnl
            == (position.last_price - position.average_entry_price) * position.quantity
        )
