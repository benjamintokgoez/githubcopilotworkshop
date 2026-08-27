"""Focused tests for MittelWerk API keys, request signing, and telemetry storage.

Covers: key entropy and secrecy, permission/TTL validation, deterministic
expiry, revoke/rotate/register, signing timestamp edge cases, exact Decimal
round trips, aware-UTC normalisation, bounded queries, injection-safe search,
and close behaviour.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta, timezone
from decimal import Decimal

import pytest
from sqlalchemy.exc import IntegrityError

from mittelwerk.auth.keys import (
    DEFAULT_PERMISSIONS,
    KEY_ENTROPY_BYTES,
    KEY_PREFIX,
    SECRET_ENV_NAME,
    VALID_PERMISSIONS,
    APIKey,
    KeyManager,
)
from mittelwerk.auth.signing import canonical_request, sign_request, verify_signature
from mittelwerk.telemetry.store import (
    MAX_QUERY_LIMIT,
    MAX_SEARCH_QUERY_LENGTH,
    WORK_ORDER_ID_COLUMN_LENGTH,
    AssignmentRecord,
    TelemetryStore,
)

# Test-only key material; never used outside this module.
SECRET = "unit-test-secret-material"  # noqa: S105


class FrozenClock:
    """Deterministic, movable aware-UTC clock."""

    def __init__(self, start: datetime) -> None:
        self.now = start

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock(datetime(2026, 1, 1, 12, 0, tzinfo=UTC))


@pytest.fixture
def manager(clock: FrozenClock) -> KeyManager:
    return KeyManager(SECRET, clock=clock)


@pytest.fixture
def store() -> Iterator[TelemetryStore]:
    telemetry_store = TelemetryStore("sqlite://")
    try:
        yield telemetry_store
    finally:
        telemetry_store.close()


def _ts(hour: int = 12, minute: int = 0) -> datetime:
    return datetime(2026, 3, 1, hour, minute, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Key generation and secrecy
# ---------------------------------------------------------------------------


def test_exported_auth_constants_match_the_mittelwerk_contract() -> None:
    assert KEY_PREFIX == "mwk_"
    assert SECRET_ENV_NAME == "MITTELWERK_AUTH_SECRET_KEY"  # noqa: S105
    assert KEY_ENTROPY_BYTES == 32
    assert VALID_PERMISSIONS == frozenset({"read", "dispatch", "admin"})
    assert DEFAULT_PERMISSIONS == frozenset({"read"})


def test_generated_keys_are_prefixed_high_entropy_and_unique(manager: KeyManager) -> None:
    keys = {manager.generate_key(f"org-{i}") for i in range(64)}
    assert len(keys) == 64
    for key in keys:
        assert key.startswith(KEY_PREFIX)
        body = key[len(KEY_PREFIX) :]
        # 32 random bytes rendered url-safe base64 -> at least 40 characters.
        assert len(body) >= 40
        assert re.fullmatch(r"[A-Za-z0-9_-]+", body)


def test_raw_key_never_appears_in_metadata_repr_or_listing(manager: KeyManager) -> None:
    raw = manager.generate_key("mwk-west", permissions=["read", "dispatch"])
    record = manager.validate_key(raw)
    assert isinstance(record, APIKey)

    assert raw not in repr(record)
    assert raw not in repr(manager)
    assert raw not in repr(manager.list_keys())
    assert not hasattr(record, "hashed_key")
    assert not any(raw in str(value) for value in vars(record).values())


def test_repr_of_manager_reveals_only_key_count(manager: KeyManager) -> None:
    manager.generate_key("mwk-west")
    manager.generate_key("mwk-east")
    assert repr(manager) == "KeyManager(keys=2)"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_key_round_trip_and_rejects_unknown(manager: KeyManager) -> None:
    raw = manager.generate_key("mwk-west", permissions=["read", "dispatch"])
    record = manager.validate_key(raw)
    assert record is not None
    assert record.organization_id == "mwk-west"
    assert record.permissions == frozenset({"read", "dispatch"})
    assert record.has_permission("read")
    assert record.has_permission("dispatch")
    assert not record.has_permission("admin")

    assert manager.validate_key(raw + "x") is None
    assert manager.validate_key("") is None
    assert manager.validate_key(None) is None  # type: ignore[arg-type]


def test_keys_do_not_validate_across_key_stores(clock: FrozenClock) -> None:
    issuer = KeyManager(SECRET, clock=clock)
    raw = issuer.generate_key("mwk-west")

    peer = KeyManager(SECRET, clock=clock)
    assert peer.validate_key(raw) is None

    peer.register_key(raw, "mwk-west")
    assert peer.validate_key(raw) is not None


def test_secret_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV_NAME, "env-provided-secret")
    first = KeyManager()
    second = KeyManager()
    raw = "mwk_shared_bootstrap_key_value_x"
    first.register_key(raw, "mwk-west")
    second.register_key(raw, "mwk-west")
    # Same secret and same raw key produce the same keyed digest, so both
    # managers accept the bootstrap key.
    assert first.validate_key(raw) is not None
    assert second.validate_key(raw) is not None


def test_process_local_secret_is_generated_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(SECRET_ENV_NAME, raising=False)
    local_manager = KeyManager()
    raw = local_manager.generate_key("mwk-west")
    assert local_manager.validate_key(raw) is not None


def test_invalid_secret_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        KeyManager("")
    with pytest.raises(TypeError):
        KeyManager(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        KeyManager(SECRET, clock="not-callable")  # type: ignore[arg-type]


def test_clock_must_return_aware_datetime() -> None:
    naive_manager = KeyManager(SECRET, clock=lambda: datetime(2026, 1, 1, 12, 0))
    with pytest.raises(ValueError):
        naive_manager.generate_key("mwk-west")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("organization_id", ["", "   ", "\t"])
def test_blank_organization_ids_are_rejected(manager: KeyManager, organization_id: str) -> None:
    with pytest.raises(ValueError):
        manager.generate_key(organization_id)


def test_non_string_organization_id_is_rejected(manager: KeyManager) -> None:
    with pytest.raises(TypeError):
        manager.generate_key(42)  # type: ignore[arg-type]


def test_permission_inputs_are_validated(manager: KeyManager) -> None:
    with pytest.raises(TypeError):
        manager.generate_key("mwk-west", permissions="read")
    with pytest.raises(TypeError):
        manager.generate_key("mwk-west", permissions=[1])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        manager.generate_key("mwk-west", permissions=["superuser"])
    with pytest.raises(ValueError):
        manager.generate_key("mwk-west", permissions=[])


@pytest.mark.parametrize("ttl", [0, -1, -3600])
def test_non_positive_ttls_are_rejected(manager: KeyManager, ttl: int) -> None:
    with pytest.raises(ValueError):
        manager.generate_key("mwk-west", ttl_seconds=ttl)


@pytest.mark.parametrize("ttl", [True, False, 1.5, "3600"])
def test_non_integer_ttls_are_rejected(manager: KeyManager, ttl: object) -> None:
    with pytest.raises(TypeError):
        manager.generate_key("mwk-west", ttl_seconds=ttl)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Expiry, revocation, rotation, registration
# ---------------------------------------------------------------------------


def test_expiry_is_deterministic_against_injected_clock(
    manager: KeyManager, clock: FrozenClock
) -> None:
    raw = manager.generate_key("mwk-west", ttl_seconds=60)
    assert manager.validate_key(raw) is not None

    clock.advance(59)
    assert manager.validate_key(raw) is not None

    clock.advance(1)  # exactly at expiry
    assert manager.validate_key(raw) is None

    record = manager.list_keys("mwk-west")[0]
    assert record.is_expired(clock.now)
    assert not record.is_active(clock.now)


def test_default_ttl_applies_when_not_overridden(clock: FrozenClock) -> None:
    ttl_manager = KeyManager(SECRET, clock=clock, default_ttl_seconds=30)
    raw = ttl_manager.generate_key("mwk-west")
    clock.advance(31)
    assert ttl_manager.validate_key(raw) is None


def test_revoke_key_is_immediate_and_idempotent(manager: KeyManager) -> None:
    raw = manager.generate_key("mwk-west")
    record = manager.validate_key(raw)
    assert record is not None

    assert manager.revoke_key(record.key_id) is True
    assert manager.validate_key(raw) is None
    assert manager.revoke_key(record.key_id) is False
    assert manager.revoke_key("unknown-key-id") is False
    assert manager.list_keys("mwk-west")[0].is_revoked()


def test_rotate_key_revokes_old_and_preserves_grants(manager: KeyManager) -> None:
    old_raw = manager.generate_key("mwk-west", permissions=["read", "dispatch"])
    old = manager.validate_key(old_raw)
    assert old is not None

    new_raw = manager.rotate_key(old.key_id)
    assert new_raw is not None
    assert new_raw != old_raw
    assert manager.validate_key(old_raw) is None

    new = manager.validate_key(new_raw)
    assert new is not None
    assert new.organization_id == "mwk-west"
    assert new.permissions == frozenset({"read", "dispatch"})
    assert manager.rotate_key("unknown-key-id") is None


def test_register_key_supports_bootstrap_and_rejects_duplicates(
    manager: KeyManager,
) -> None:
    raw = "mwk_bootstrap_key_for_local_use"
    record = manager.register_key(raw, "operations", permissions=["read", "dispatch"])
    assert record.organization_id == "operations"
    assert manager.validate_key(raw) is not None

    with pytest.raises(ValueError):
        manager.register_key(raw, "operations")
    with pytest.raises(ValueError):
        manager.register_key("too-short", "operations")
    with pytest.raises(TypeError):
        manager.register_key(12345, "operations")  # type: ignore[arg-type]


def test_list_keys_filters_by_organization(manager: KeyManager) -> None:
    manager.generate_key("mwk-west")
    manager.generate_key("mwk-east")
    manager.generate_key("mwk-west")

    assert manager.key_count == 3
    assert len(manager.list_keys("mwk-west")) == 2
    assert len(manager.list_keys("mwk-east")) == 1
    assert manager.list_keys("nobody") == []
    with pytest.raises(ValueError):
        manager.list_keys("  ")


# ---------------------------------------------------------------------------
# Request signing
# ---------------------------------------------------------------------------


def test_canonical_request_is_parameter_order_independent() -> None:
    first = canonical_request(
        "get",
        "/api/v1/work-orders",
        {"b": "2", "a": "1"},
        "",
        1000,
    )
    second = canonical_request(
        "GET",
        "/api/v1/work-orders",
        {"a": "1", "b": "2"},
        "",
        1000,
    )
    assert first == second
    assert first.startswith("GET\n/api/v1/work-orders\na=1&b=2\n")
    assert first.endswith("\n1000")


def test_timestamp_zero_is_signed_literally_not_treated_as_missing() -> None:
    canon = canonical_request("GET", "/api/v1/work-orders", None, "", 0)
    assert canon.endswith("\n0")
    assert canon != canonical_request("GET", "/api/v1/work-orders", None, "", None)
    # A zero timestamp is ancient, so verification fails as stale rather than
    # silently resolving to "now".
    signature = sign_request(SECRET, "GET", "/api/v1/work-orders", None, "", 0)
    assert verify_signature(SECRET, signature, "GET", "/api/v1/work-orders", None, "", 0) is False


def test_sign_and_verify_round_trip_and_tamper_detection() -> None:
    now = int(datetime.now(UTC).timestamp())
    params = {"asset_id": "CNC-01"}
    body = '{"hours":"10"}'
    signature = sign_request(SECRET, "POST", "/api/v1/work-orders", params, body, now)

    assert verify_signature(SECRET, signature, "POST", "/api/v1/work-orders", params, body, now)
    assert not verify_signature(
        SECRET,
        signature,
        "POST",
        "/api/v1/work-orders",
        params,
        '{"hours":"11"}',
        now,
    )
    assert not verify_signature(
        SECRET,
        signature,
        "GET",
        "/api/v1/work-orders",
        params,
        body,
        now,
    )
    assert not verify_signature(
        SECRET,
        signature,
        "POST",
        "/api/v1/work-orders",
        {"asset_id": "FORK-07"},
        body,
        now,
    )
    assert not verify_signature(
        "other-secret",
        signature,
        "POST",
        "/api/v1/work-orders",
        params,
        body,
        now,
    )


def test_stale_and_future_requests_are_rejected() -> None:
    now = int(datetime.now(UTC).timestamp())
    for ts in (now - 400, now + 400):
        signature = sign_request(SECRET, "GET", "/api/v1/health", None, "", ts)
        assert (
            verify_signature(
                SECRET,
                signature,
                "GET",
                "/api/v1/health",
                None,
                "",
                ts,
                max_age_seconds=300,
            )
            is False
        )


def test_malformed_signature_and_configuration_inputs() -> None:
    now = int(datetime.now(UTC).timestamp())
    assert verify_signature(SECRET, "", "GET", "/x", None, "", now) is False
    assert verify_signature(SECRET, None, "GET", "/x", None, "", now) is False  # type: ignore[arg-type]
    assert verify_signature(SECRET, "zz", "GET", "/x", None, "", now) is False

    with pytest.raises(ValueError):
        verify_signature(SECRET, "abc", "GET", "/x", None, "", now, max_age_seconds=0)
    with pytest.raises(TypeError):
        verify_signature(SECRET, "abc", "GET", "/x", None, "", now, max_age_seconds=True)
    with pytest.raises(ValueError):
        sign_request("", "GET", "/x")
    with pytest.raises(ValueError):
        canonical_request("GET", "work-orders-without-leading-slash")
    with pytest.raises(ValueError):
        canonical_request("GET", "/x", None, "", -1)
    with pytest.raises(TypeError):
        canonical_request("GET", "/x", None, "", "1000")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        canonical_request("GET", "/x", {"a": 1})  # type: ignore[dict-item]


# ---------------------------------------------------------------------------
# Store — decimals
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value",
    ["0.1", "0.30000000000000004", "185.55", "0.00000001", "123456789.123456789"],
)
def test_decimal_values_round_trip_exactly(store: TelemetryStore, value: str) -> None:
    amount = Decimal(value)
    store.insert_reading("CNC-01", amount, amount, amount, 1, _ts())
    row = store.get_readings("CNC-01")[0]
    assert row.min_reading == amount
    # Identical value *and* precision: the canonical text form is preserved.
    assert str(row.min_reading) == str(amount)
    assert row.min_reading.as_tuple() == amount.as_tuple()
    assert row.max_reading == amount
    assert row.last_reading == amount


def test_binary_floats_are_rejected_for_decimal_columns(store: TelemetryStore) -> None:
    with pytest.raises(TypeError):
        store.insert_reading("CNC-01", 0.1, Decimal("1"), Decimal("1"), 1, _ts())
    with pytest.raises(TypeError):
        store.insert_assignment(
            "assign-float",
            "CNC-01",
            "req-1",
            "prov-1",
            1.5,
            Decimal("1"),
            "mwk-west",
            "mwk-east",
            _ts(),
        )


def test_interval_round_trip(store: TelemetryStore) -> None:
    store.insert_interval(
        "CNC-01",
        "1h",
        "185.10",
        "186.00",
        "184.99",
        "185.55",
        1_000,
        _ts(),
    )
    bar = store.get_intervals("CNC-01", "1h")[0]
    assert (bar.open_reading, bar.high_reading, bar.low_reading, bar.close_reading) == (
        Decimal("185.10"),
        Decimal("186.00"),
        Decimal("184.99"),
        Decimal("185.55"),
    )
    assert bar.sample_count == 1_000
    assert store.get_intervals("CNC-01", "4h") == []


# ---------------------------------------------------------------------------
# Store — timestamps
# ---------------------------------------------------------------------------


def test_naive_datetimes_are_rejected(store: TelemetryStore) -> None:
    naive = datetime(2026, 3, 1, 12, 0)
    with pytest.raises(ValueError):
        store.insert_reading("CNC-01", Decimal("1"), Decimal("1"), Decimal("1"), 1, naive)
    store.insert_reading("CNC-01", Decimal("1"), Decimal("1"), Decimal("1"), 1, _ts())
    with pytest.raises(ValueError):
        store.get_readings("CNC-01", start=naive)
    with pytest.raises(ValueError):
        store.get_readings("CNC-01", end=naive)


def test_offsets_are_normalised_to_utc_and_returned_aware(
    store: TelemetryStore,
) -> None:
    berlin_summer = timezone(timedelta(hours=2))
    stamp = datetime(2026, 7, 1, 14, 30, tzinfo=berlin_summer)
    store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), 5, stamp)

    row = store.get_readings("CNC-01")[0]
    assert row.timestamp.tzinfo is not None
    assert row.timestamp.utcoffset() == timedelta(0)
    assert row.timestamp == datetime(2026, 7, 1, 12, 30, tzinfo=UTC)


def test_range_boundaries_are_inclusive(store: TelemetryStore) -> None:
    stamps = [_ts(hour=hour) for hour in (10, 11, 12, 13)]
    for index, stamp in enumerate(stamps):
        store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), index, stamp)

    inclusive = store.get_readings("CNC-01", start=stamps[1], end=stamps[2])
    assert [row.timestamp for row in inclusive] == [stamps[2], stamps[1]]

    everything = store.get_readings("CNC-01")
    assert [row.timestamp for row in everything] == sorted(stamps, reverse=True)
    assert store.get_readings("CNC-01", limit=2) == everything[:2]


def test_query_limits_are_validated_and_capped(store: TelemetryStore) -> None:
    store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), 1, _ts())
    assert store.get_readings("CNC-01", limit=MAX_QUERY_LIMIT * 10) == store.get_readings("CNC-01")
    with pytest.raises(ValueError):
        store.get_readings("CNC-01", limit=0)
    with pytest.raises(TypeError):
        store.get_readings("CNC-01", limit=True)
    with pytest.raises(ValueError):
        store.get_readings("   ")


# ---------------------------------------------------------------------------
# Store — assignments and equipment
# ---------------------------------------------------------------------------


def test_assignment_ids_are_unique_and_integrity_errors_surface(
    store: TelemetryStore,
) -> None:
    store.insert_assignment(
        "assignment-1",
        "CNC-01",
        "req-1",
        "prov-1",
        "185.55",
        "10",
        "mwk-west",
        "mwk-east",
        _ts(),
    )
    with pytest.raises(IntegrityError):
        store.insert_assignment(
            "assignment-1",
            "CNC-01",
            "req-2",
            "prov-2",
            "185.55",
            "10",
            "mwk-west",
            "mwk-east",
            _ts(),
        )
    assert store.count_assignments("CNC-01") == 1
    assignment = store.get_assignments("CNC-01")[0]
    assert assignment.hourly_rate == Decimal("185.55")
    assert assignment.hours == Decimal("10")


def _assignment_payload(assignment_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "assignment_id": assignment_id,
        "asset_id": "CNC-01",
        "requester_work_order_id": "req-1",
        "provider_work_order_id": "prov-1",
        "hourly_rate": Decimal("150.55"),
        "hours": Decimal("0.25"),
        "requester_organization_id": "mwk-west",
        "provider_organization_id": "mwk-east",
        "timestamp": _ts(),
    }
    payload.update(overrides)
    return payload


def test_insert_assignments_batch_round_trips_exactly(store: TelemetryStore) -> None:
    berlin_summer = timezone(timedelta(hours=2))
    written = store.insert_assignments(
        [
            _assignment_payload("batch-1"),
            _assignment_payload(
                "batch-2",
                hourly_rate=Decimal("0.10"),
                hours=Decimal("2"),
                timestamp=datetime(2026, 3, 1, 14, 30, tzinfo=berlin_summer),
            ),
        ]
    )
    assert written == 2
    assert store.insert_assignments([]) == 0

    rows = {row.assignment_id: row for row in store.get_assignments("CNC-01")}
    assert rows["batch-1"].hourly_rate == Decimal("150.55")
    assert rows["batch-1"].hours == Decimal("0.25")
    assert str(rows["batch-2"].hourly_rate) == "0.10"
    assert rows["batch-2"].timestamp == datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
    assert rows["batch-2"].timestamp.utcoffset() == timedelta(0)


def test_insert_assignments_batch_is_atomic(store: TelemetryStore) -> None:
    store.insert_assignments([_assignment_payload("existing-1")])

    with pytest.raises(IntegrityError):
        store.insert_assignments(
            [_assignment_payload("fresh-1"), _assignment_payload("existing-1")]
        )
    assert store.count_assignments() == 1

    with pytest.raises(ValueError):
        store.insert_assignments([_assignment_payload("fresh-2"), _assignment_payload("  ")])
    assert store.count_assignments() == 1

    with pytest.raises(ValueError):
        store.insert_assignments([_assignment_payload("fresh-3", requester_organization_id="")])
    with pytest.raises(TypeError):
        store.insert_assignments([_assignment_payload("fresh-4", hourly_rate=1.5)])
    assert store.count_assignments() == 1
    assert store.insert_assignments([_assignment_payload("fresh-5")]) == 1


def test_assignment_work_order_id_columns_match_the_api_contract(
    store: TelemetryStore,
) -> None:
    """Work-order-id columns must hold a full-length client-supplied id."""
    assert WORK_ORDER_ID_COLUMN_LENGTH == 64
    columns = AssignmentRecord.__table__.c
    assert columns.requester_work_order_id.type.length == WORK_ORDER_ID_COLUMN_LENGTH
    assert columns.provider_work_order_id.type.length == WORK_ORDER_ID_COLUMN_LENGTH

    long_requester = "r" * WORK_ORDER_ID_COLUMN_LENGTH
    long_provider = "p" * WORK_ORDER_ID_COLUMN_LENGTH
    store.insert_assignments(
        [
            _assignment_payload(
                "long-ids",
                requester_work_order_id=long_requester,
                provider_work_order_id=long_provider,
            )
        ]
    )
    row = store.get_assignments("CNC-01")[0]
    assert row.requester_work_order_id == long_requester
    assert row.provider_work_order_id == long_provider


def _seed_equipment(store: TelemetryStore) -> None:
    store.upsert_equipments(
        [
            {
                "asset_id": "CNC-01",
                "name": "CNC Milling Center",
                "equipment_type": "MACHINE",
                "currency": "EUR",
                "site_code": "BER-01",
                "hourly_service_rate": "185.55",
                "rate_increment": "0.25",
                "hour_lot_size": "0.25",
            },
            {
                "asset_id": "LIFT-02",
                "name": "Warehouse Lift",
                "equipment_type": "LIFT",
                "currency": "EUR",
                "site_code": "HAM-02",
                "hourly_service_rate": "95.00",
                "rate_increment": "0.50",
                "hour_lot_size": "0.50",
            },
            {
                "asset_id": "DISC-01",
                "name": "100% Service Discount Rig",
                "equipment_type": "PROMO",
                "currency": "EUR",
                "site_code": "MUC-03",
                "hourly_service_rate": "1.00",
                "rate_increment": "0.25",
                "hour_lot_size": "1",
            },
        ]
    )


def test_upsert_equipment_updates_existing_rows(store: TelemetryStore) -> None:
    _seed_equipment(store)
    assert store.count_equipment() == 3
    store.upsert_equipments(
        [
            {
                "asset_id": "CNC-01",
                "name": "CNC Milling Center (renamed)",
                "equipment_type": "MACHINE",
                "currency": "EUR",
                "site_code": "BER-01",
                "hourly_service_rate": "190.00",
                "rate_increment": "0.50",
                "hour_lot_size": "0.25",
            }
        ]
    )
    assert store.count_equipment() == 3
    cnc = store.get_equipment("cnc-01")
    assert cnc is not None
    assert cnc.name == "CNC Milling Center (renamed)"
    assert cnc.hourly_service_rate == Decimal("190.00")
    assert cnc.rate_increment == Decimal("0.50")


@pytest.mark.parametrize(
    "payload",
    [
        "' OR 1=1 --",
        "'; DROP TABLE equipment; --",
        '" OR ""="',
        "CNC' UNION SELECT * FROM equipment --",
    ],
)
def test_sql_injection_payloads_are_inert(store: TelemetryStore, payload: str) -> None:
    _seed_equipment(store)
    assert store.search_equipment(payload) == []
    assert store.count_equipment() == 3


def test_like_wildcards_are_escaped_and_matched_literally(
    store: TelemetryStore,
) -> None:
    _seed_equipment(store)
    # '%' and '_' are matched literally instead of acting as LIKE wildcards:
    # only the equipment row whose name really contains '%' is returned.
    assert [row.asset_id for row in store.search_equipment("%")] == ["DISC-01"]
    assert store.search_equipment("_") == []
    assert [row.asset_id for row in store.search_equipment("100%")] == ["DISC-01"]
    assert [row.asset_id for row in store.search_equipment("cnc")] == ["CNC-01"]
    assert [row.asset_id for row in store.search_equipment("lift")] == ["LIFT-02"]


def test_search_bounds_are_enforced(store: TelemetryStore) -> None:
    _seed_equipment(store)
    assert len(store.search_equipment("i", limit=1)) <= 1
    with pytest.raises(ValueError):
        store.search_equipment("   ")
    with pytest.raises(ValueError):
        store.search_equipment("x" * (MAX_SEARCH_QUERY_LENGTH + 1))
    with pytest.raises(ValueError):
        store.search_equipment("cnc", limit=0)
    with pytest.raises(TypeError):
        store.search_equipment(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Store — lifecycle
# ---------------------------------------------------------------------------


def test_close_disposes_engine_and_blocks_further_use() -> None:
    telemetry_store = TelemetryStore("sqlite://")
    telemetry_store.insert_reading("CNC-01", Decimal("1"), Decimal("2"), Decimal("1.5"), 1, _ts())
    assert telemetry_store.count_readings("CNC-01") == 1

    telemetry_store.close()
    assert telemetry_store.is_closed is True
    telemetry_store.close()  # idempotent
    with pytest.raises(RuntimeError):
        telemetry_store.count_readings("CNC-01")
    with pytest.raises(RuntimeError):
        telemetry_store.get_readings("CNC-01")


def test_store_context_manager_closes() -> None:
    with TelemetryStore("sqlite://") as telemetry_store:
        assert telemetry_store.count_readings() == 0
    assert telemetry_store.is_closed is True


def test_failed_operation_rolls_back(store: TelemetryStore) -> None:
    store.insert_assignment(
        "assignment-rollback",
        "CNC-01",
        "req-1",
        "prov-1",
        "1.00",
        "1",
        "mwk-west",
        "mwk-east",
        _ts(),
    )
    with pytest.raises(IntegrityError):
        store.insert_assignment(
            "assignment-rollback",
            "CNC-01",
            "req-1",
            "prov-1",
            "1.00",
            "1",
            "mwk-west",
            "mwk-east",
            _ts(),
        )
    # The store is still usable after the rolled-back transaction.
    store.insert_assignment(
        "assignment-ok",
        "CNC-01",
        "req-2",
        "prov-2",
        "1.00",
        "1",
        "mwk-west",
        "mwk-east",
        _ts(),
    )
    assert store.count_assignments() == 2


def test_batch_insert_is_atomic_and_counted(store: TelemetryStore) -> None:
    readings: list[dict[str, object]] = [
        {
            "asset_id": "CNC-01",
            "min_reading": Decimal("1.01"),
            "max_reading": Decimal("1.02"),
            "last_reading": Decimal("1.015"),
            "sample_count": 10,
            "timestamp": _ts(hour=hour),
        }
        for hour in (9, 10, 11)
    ]
    assert store.insert_readings(readings) == 3
    assert store.insert_readings([]) == 0
    assert store.count_readings("CNC-01") == 3

    readings[1]["timestamp"] = datetime(2026, 3, 1, 10, 0)  # naive -> whole batch fails
    with pytest.raises(ValueError):
        store.insert_readings(readings)
    assert store.count_readings("CNC-01") == 3
