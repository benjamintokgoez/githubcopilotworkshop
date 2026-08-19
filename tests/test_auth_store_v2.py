"""Focused tests for the API key manager, request signing, and the store.

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

from qxm.auth.keys import KEY_PREFIX, SECRET_ENV_NAME, APIKey, KeyManager
from qxm.auth.signing import canonical_request, sign_request, verify_signature
from qxm.data.store import (
    MAX_QUERY_LIMIT,
    MAX_SEARCH_QUERY_LENGTH,
    ORDER_ID_COLUMN_LENGTH,
    TimeSeriesStore,
    TradeRecord,
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
def store() -> Iterator[TimeSeriesStore]:
    store = TimeSeriesStore("sqlite://")
    try:
        yield store
    finally:
        store.close()


def _ts(hour: int = 12, minute: int = 0) -> datetime:
    return datetime(2026, 3, 1, hour, minute, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Key generation and secrecy
# ---------------------------------------------------------------------------


def test_generated_keys_are_prefixed_high_entropy_and_unique(manager: KeyManager) -> None:
    keys = {manager.generate_key(f"client-{i}") for i in range(64)}
    assert len(keys) == 64
    for key in keys:
        assert key.startswith(KEY_PREFIX)
        body = key[len(KEY_PREFIX) :]
        # 32 random bytes rendered url-safe base64 -> at least 40 characters.
        assert len(body) >= 40
        assert re.fullmatch(r"[A-Za-z0-9_-]+", body)


def test_raw_key_never_appears_in_metadata_repr_or_listing(manager: KeyManager) -> None:
    raw = manager.generate_key("alice", permissions=["read", "trade"])
    record = manager.validate_key(raw)
    assert isinstance(record, APIKey)

    assert raw not in repr(record)
    assert raw not in repr(manager)
    assert raw not in repr(manager.list_keys())
    assert not hasattr(record, "hashed_key")
    assert not any(raw in str(value) for value in vars(record).values())


def test_repr_of_manager_reveals_only_key_count(manager: KeyManager) -> None:
    manager.generate_key("alice")
    manager.generate_key("bob")
    assert repr(manager) == "KeyManager(keys=2)"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validate_key_round_trip_and_rejects_unknown(manager: KeyManager) -> None:
    raw = manager.generate_key("alice", permissions=["read"])
    record = manager.validate_key(raw)
    assert record is not None
    assert record.client_id == "alice"
    assert record.permissions == frozenset({"read"})
    assert record.has_permission("read")
    assert not record.has_permission("trade")

    assert manager.validate_key(raw + "x") is None
    assert manager.validate_key("") is None
    assert manager.validate_key(None) is None  # type: ignore[arg-type]


def test_keys_do_not_validate_across_key_stores(clock: FrozenClock) -> None:
    issuer = KeyManager(SECRET, clock=clock)
    raw = issuer.generate_key("alice")

    peer = KeyManager(SECRET, clock=clock)
    assert peer.validate_key(raw) is None

    peer.register_key(raw, "alice")
    assert peer.validate_key(raw) is not None


def test_secret_is_read_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(SECRET_ENV_NAME, "env-provided-secret")
    first = KeyManager()
    second = KeyManager()
    raw = "qxm_shared_bootstrap_key_value_x"
    first.register_key(raw, "alice")
    second.register_key(raw, "alice")
    # Same secret and same raw key produce the same keyed digest, so both
    # managers accept the bootstrap key.
    assert first.validate_key(raw) is not None
    assert second.validate_key(raw) is not None


def test_process_local_secret_is_generated_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(SECRET_ENV_NAME, raising=False)
    manager = KeyManager()
    raw = manager.generate_key("alice")
    assert manager.validate_key(raw) is not None


def test_invalid_secret_inputs_are_rejected() -> None:
    with pytest.raises(ValueError):
        KeyManager("")
    with pytest.raises(TypeError):
        KeyManager(123)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        KeyManager(SECRET, clock="not-callable")  # type: ignore[arg-type]


def test_clock_must_return_aware_datetime() -> None:
    naive = KeyManager(SECRET, clock=lambda: datetime(2026, 1, 1, 12, 0))
    with pytest.raises(ValueError):
        naive.generate_key("alice")


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("client_id", ["", "   ", "\t"])
def test_blank_client_ids_are_rejected(manager: KeyManager, client_id: str) -> None:
    with pytest.raises(ValueError):
        manager.generate_key(client_id)


def test_non_string_client_id_is_rejected(manager: KeyManager) -> None:
    with pytest.raises(TypeError):
        manager.generate_key(42)  # type: ignore[arg-type]


def test_permission_inputs_are_validated(manager: KeyManager) -> None:
    with pytest.raises(TypeError):
        manager.generate_key("alice", permissions="read")
    with pytest.raises(TypeError):
        manager.generate_key("alice", permissions=[1])  # type: ignore[list-item]
    with pytest.raises(ValueError):
        manager.generate_key("alice", permissions=["superuser"])
    with pytest.raises(ValueError):
        manager.generate_key("alice", permissions=[])


@pytest.mark.parametrize("ttl", [0, -1, -3600])
def test_non_positive_ttls_are_rejected(manager: KeyManager, ttl: int) -> None:
    with pytest.raises(ValueError):
        manager.generate_key("alice", ttl_seconds=ttl)


@pytest.mark.parametrize("ttl", [True, False, 1.5, "3600"])
def test_non_integer_ttls_are_rejected(manager: KeyManager, ttl: object) -> None:
    with pytest.raises(TypeError):
        manager.generate_key("alice", ttl_seconds=ttl)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Expiry, revocation, rotation, registration
# ---------------------------------------------------------------------------


def test_expiry_is_deterministic_against_injected_clock(
    manager: KeyManager, clock: FrozenClock
) -> None:
    raw = manager.generate_key("alice", ttl_seconds=60)
    assert manager.validate_key(raw) is not None

    clock.advance(59)
    assert manager.validate_key(raw) is not None

    clock.advance(1)  # exactly at expiry
    assert manager.validate_key(raw) is None

    record = manager.list_keys("alice")[0]
    assert record.is_expired(clock.now)
    assert not record.is_active(clock.now)


def test_default_ttl_applies_when_not_overridden(clock: FrozenClock) -> None:
    manager = KeyManager(SECRET, clock=clock, default_ttl_seconds=30)
    raw = manager.generate_key("alice")
    clock.advance(31)
    assert manager.validate_key(raw) is None


def test_revoke_key_is_immediate_and_idempotent(manager: KeyManager) -> None:
    raw = manager.generate_key("alice")
    record = manager.validate_key(raw)
    assert record is not None

    assert manager.revoke_key(record.key_id) is True
    assert manager.validate_key(raw) is None
    assert manager.revoke_key(record.key_id) is False
    assert manager.revoke_key("unknown-key-id") is False
    assert manager.list_keys("alice")[0].is_revoked()


def test_rotate_key_revokes_old_and_preserves_grants(manager: KeyManager) -> None:
    old_raw = manager.generate_key("alice", permissions=["read", "trade"])
    old = manager.validate_key(old_raw)
    assert old is not None

    new_raw = manager.rotate_key(old.key_id)
    assert new_raw is not None
    assert new_raw != old_raw
    assert manager.validate_key(old_raw) is None

    new = manager.validate_key(new_raw)
    assert new is not None
    assert new.client_id == "alice"
    assert new.permissions == frozenset({"read", "trade"})
    assert manager.rotate_key("unknown-key-id") is None


def test_register_key_supports_bootstrap_and_rejects_duplicates(
    manager: KeyManager,
) -> None:
    raw = "qxm_bootstrap_key_for_local_use"
    record = manager.register_key(raw, "operator", permissions=["read", "trade"])
    assert record.client_id == "operator"
    assert manager.validate_key(raw) is not None

    with pytest.raises(ValueError):
        manager.register_key(raw, "operator")
    with pytest.raises(ValueError):
        manager.register_key("too-short", "operator")
    with pytest.raises(TypeError):
        manager.register_key(12345, "operator")  # type: ignore[arg-type]


def test_list_keys_filters_by_client(manager: KeyManager) -> None:
    manager.generate_key("alice")
    manager.generate_key("bob")
    manager.generate_key("alice")

    assert manager.key_count == 3
    assert len(manager.list_keys("alice")) == 2
    assert len(manager.list_keys("bob")) == 1
    assert manager.list_keys("nobody") == []
    with pytest.raises(ValueError):
        manager.list_keys("  ")


# ---------------------------------------------------------------------------
# Request signing
# ---------------------------------------------------------------------------


def test_canonical_request_is_parameter_order_independent() -> None:
    first = canonical_request("get", "/api/v1/orders", {"b": "2", "a": "1"}, "", 1000)
    second = canonical_request("GET", "/api/v1/orders", {"a": "1", "b": "2"}, "", 1000)
    assert first == second
    assert first.startswith("GET\n/api/v1/orders\na=1&b=2\n")
    assert first.endswith("\n1000")


def test_timestamp_zero_is_signed_literally_not_treated_as_missing() -> None:
    canon = canonical_request("GET", "/api/v1/orders", None, "", 0)
    assert canon.endswith("\n0")
    assert canon != canonical_request("GET", "/api/v1/orders", None, "", None)
    # A zero timestamp is ancient, so verification fails as stale rather than
    # silently resolving to "now".
    signature = sign_request(SECRET, "GET", "/api/v1/orders", None, "", 0)
    assert verify_signature(SECRET, signature, "GET", "/api/v1/orders", None, "", 0) is False


def test_sign_and_verify_round_trip_and_tamper_detection() -> None:
    now = int(datetime.now(UTC).timestamp())
    params = {"symbol": "AAPL"}
    body = '{"quantity":"10"}'
    signature = sign_request(SECRET, "POST", "/api/v1/orders", params, body, now)

    assert verify_signature(SECRET, signature, "POST", "/api/v1/orders", params, body, now)
    assert not verify_signature(
        SECRET, signature, "POST", "/api/v1/orders", params, '{"quantity":"11"}', now
    )
    assert not verify_signature(SECRET, signature, "GET", "/api/v1/orders", params, body, now)
    assert not verify_signature(
        SECRET, signature, "POST", "/api/v1/orders", {"symbol": "MSFT"}, body, now
    )
    assert not verify_signature(
        "other-secret", signature, "POST", "/api/v1/orders", params, body, now
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
        canonical_request("GET", "orders-without-leading-slash")
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
def test_decimal_values_round_trip_exactly(store: TimeSeriesStore, value: str) -> None:
    amount = Decimal(value)
    store.insert_tick("AAPL", amount, amount, amount, 1, _ts())
    row = store.get_ticks("AAPL")[0]
    assert row.bid == amount
    # Identical value *and* precision: the canonical text form is preserved.
    assert str(row.bid) == str(amount)
    assert row.bid.as_tuple() == amount.as_tuple()
    assert row.ask == amount
    assert row.last == amount


def test_binary_floats_are_rejected_for_money_columns(store: TimeSeriesStore) -> None:
    with pytest.raises(TypeError):
        store.insert_tick("AAPL", 0.1, Decimal("1"), Decimal("1"), 1, _ts())
    with pytest.raises(TypeError):
        store.insert_trade("t-float", "AAPL", "b", "s", 1.5, Decimal("1"), "buyer", "seller", _ts())


def test_ohlc_round_trip(store: TimeSeriesStore) -> None:
    store.insert_ohlc("AAPL", "1m", "185.10", "186.00", "184.99", "185.55", 1_000, _ts())
    bar = store.get_ohlc("AAPL", "1m")[0]
    assert (bar.open, bar.high, bar.low, bar.close) == (
        Decimal("185.10"),
        Decimal("186.00"),
        Decimal("184.99"),
        Decimal("185.55"),
    )
    assert bar.volume == 1_000
    assert store.get_ohlc("AAPL", "5m") == []


# ---------------------------------------------------------------------------
# Store — timestamps
# ---------------------------------------------------------------------------


def test_naive_datetimes_are_rejected(store: TimeSeriesStore) -> None:
    naive = datetime(2026, 3, 1, 12, 0)
    with pytest.raises(ValueError):
        store.insert_tick("AAPL", Decimal("1"), Decimal("1"), Decimal("1"), 1, naive)
    store.insert_tick("AAPL", Decimal("1"), Decimal("1"), Decimal("1"), 1, _ts())
    with pytest.raises(ValueError):
        store.get_ticks("AAPL", start=naive)
    with pytest.raises(ValueError):
        store.get_ticks("AAPL", end=naive)


def test_offsets_are_normalised_to_utc_and_returned_aware(
    store: TimeSeriesStore,
) -> None:
    berlin_summer = timezone(timedelta(hours=2))
    stamp = datetime(2026, 7, 1, 14, 30, tzinfo=berlin_summer)
    store.insert_tick("SAP", Decimal("1"), Decimal("2"), Decimal("1.5"), 5, stamp)

    row = store.get_ticks("SAP")[0]
    assert row.timestamp.tzinfo is not None
    assert row.timestamp.utcoffset() == timedelta(0)
    assert row.timestamp == datetime(2026, 7, 1, 12, 30, tzinfo=UTC)


def test_range_boundaries_are_inclusive(store: TimeSeriesStore) -> None:
    stamps = [_ts(hour=hour) for hour in (10, 11, 12, 13)]
    for index, stamp in enumerate(stamps):
        store.insert_tick("AAPL", Decimal("1"), Decimal("2"), Decimal("1.5"), index, stamp)

    inclusive = store.get_ticks("AAPL", start=stamps[1], end=stamps[2])
    assert [row.timestamp for row in inclusive] == [stamps[2], stamps[1]]

    everything = store.get_ticks("AAPL")
    assert [row.timestamp for row in everything] == sorted(stamps, reverse=True)
    assert store.get_ticks("AAPL", limit=2) == everything[:2]


def test_query_limits_are_validated_and_capped(store: TimeSeriesStore) -> None:
    store.insert_tick("AAPL", Decimal("1"), Decimal("2"), Decimal("1.5"), 1, _ts())
    assert store.get_ticks("AAPL", limit=MAX_QUERY_LIMIT * 10) == store.get_ticks("AAPL")
    with pytest.raises(ValueError):
        store.get_ticks("AAPL", limit=0)
    with pytest.raises(TypeError):
        store.get_ticks("AAPL", limit=True)
    with pytest.raises(ValueError):
        store.get_ticks("   ")


# ---------------------------------------------------------------------------
# Store — trades and instruments
# ---------------------------------------------------------------------------


def test_trade_ids_are_unique_and_integrity_errors_surface(
    store: TimeSeriesStore,
) -> None:
    store.insert_trade("trade-1", "AAPL", "buy-1", "sell-1", "185.55", "10", "alice", "bob", _ts())
    with pytest.raises(IntegrityError):
        store.insert_trade(
            "trade-1", "AAPL", "buy-2", "sell-2", "185.55", "10", "alice", "bob", _ts()
        )
    assert store.count_trades("AAPL") == 1
    trade = store.get_trades("AAPL")[0]
    assert trade.price == Decimal("185.55")
    assert trade.quantity == Decimal("10")


def _trade_payload(trade_id: str, **overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "trade_id": trade_id,
        "symbol": "SAP",
        "buy_order_id": "buy-1",
        "sell_order_id": "sell-1",
        "price": Decimal("150.55"),
        "quantity": Decimal("0.001"),
        "buyer_client_id": "bob",
        "seller_client_id": "alice",
        "timestamp": _ts(),
    }
    payload.update(overrides)
    return payload


def test_insert_trades_batch_round_trips_exactly(store: TimeSeriesStore) -> None:
    berlin_summer = timezone(timedelta(hours=2))
    written = store.insert_trades(
        [
            _trade_payload("batch-1"),
            _trade_payload(
                "batch-2",
                price=Decimal("0.10"),
                quantity=Decimal("2"),
                timestamp=datetime(2026, 3, 1, 14, 30, tzinfo=berlin_summer),
            ),
        ]
    )
    assert written == 2
    assert store.insert_trades([]) == 0

    rows = {row.trade_id: row for row in store.get_trades("SAP")}
    assert rows["batch-1"].price == Decimal("150.55")
    assert rows["batch-1"].quantity == Decimal("0.001")
    assert str(rows["batch-2"].price) == "0.10"
    assert rows["batch-2"].timestamp == datetime(2026, 3, 1, 12, 30, tzinfo=UTC)
    assert rows["batch-2"].timestamp.utcoffset() == timedelta(0)


def test_insert_trades_batch_is_atomic(store: TimeSeriesStore) -> None:
    store.insert_trades([_trade_payload("existing-1")])

    with pytest.raises(IntegrityError):
        store.insert_trades([_trade_payload("fresh-1"), _trade_payload("existing-1")])
    assert store.count_trades() == 1

    with pytest.raises(ValueError):
        store.insert_trades([_trade_payload("fresh-2"), _trade_payload("  ")])
    assert store.count_trades() == 1

    with pytest.raises(ValueError):
        store.insert_trades([_trade_payload("fresh-3", buyer_client_id="")])
    with pytest.raises(TypeError):
        store.insert_trades([_trade_payload("fresh-4", price=1.5)])
    assert store.count_trades() == 1
    assert store.insert_trades([_trade_payload("fresh-5")]) == 1


def test_trade_order_id_columns_match_the_api_contract(store: TimeSeriesStore) -> None:
    """Order-id columns must hold a full-length client-supplied id, not just a UUID."""
    assert ORDER_ID_COLUMN_LENGTH == 64
    columns = TradeRecord.__table__.c
    assert columns.buy_order_id.type.length == ORDER_ID_COLUMN_LENGTH
    assert columns.sell_order_id.type.length == ORDER_ID_COLUMN_LENGTH

    long_buy = "b" * ORDER_ID_COLUMN_LENGTH
    long_sell = "s" * ORDER_ID_COLUMN_LENGTH
    store.insert_trades(
        [_trade_payload("long-ids", buy_order_id=long_buy, sell_order_id=long_sell)]
    )
    row = store.get_trades("SAP")[0]
    assert row.buy_order_id == long_buy
    assert row.sell_order_id == long_sell


def _seed(store: TimeSeriesStore) -> None:
    store.seed_instruments(
        [
            {
                "symbol": "SAP",
                "name": "SAP SE",
                "instrument_type": "EQUITY",
                "currency": "EUR",
                "exchange": "XETRA",
                "tick_size": "0.01",
                "lot_size": "1",
            },
            {
                "symbol": "BTC-USD",
                "name": "Bitcoin / US Dollar",
                "instrument_type": "CRYPTO",
                "currency": "USD",
                "exchange": "QUANTCORE",
                "tick_size": "0.01",
                "lot_size": "0.001",
            },
            {
                "symbol": "PCT",
                "name": "100% Discount Retail AG",
                "instrument_type": "EQUITY",
                "currency": "EUR",
                "exchange": "XETRA",
                "tick_size": "0.01",
                "lot_size": "1",
            },
        ]
    )


def test_seed_instruments_upserts(store: TimeSeriesStore) -> None:
    _seed(store)
    assert store.count_instruments() == 3
    store.seed_instruments(
        [
            {
                "symbol": "SAP",
                "name": "SAP SE (renamed)",
                "instrument_type": "EQUITY",
                "currency": "EUR",
                "exchange": "XETRA",
                "tick_size": "0.05",
                "lot_size": "1",
            }
        ]
    )
    assert store.count_instruments() == 3
    sap = store.get_instrument("sap")
    assert sap is not None
    assert sap.name == "SAP SE (renamed)"
    assert sap.tick_size == Decimal("0.05")


@pytest.mark.parametrize(
    "payload",
    [
        "' OR 1=1 --",
        "'; DROP TABLE instruments; --",
        '" OR ""="',
        "SAP' UNION SELECT * FROM instruments --",
    ],
)
def test_sql_injection_payloads_are_inert(store: TimeSeriesStore, payload: str) -> None:
    _seed(store)
    assert store.search_instruments(payload) == []
    assert store.count_instruments() == 3


def test_like_wildcards_are_escaped_and_matched_literally(
    store: TimeSeriesStore,
) -> None:
    _seed(store)
    # '%' and '_' are matched literally instead of acting as LIKE wildcards:
    # only the instrument whose name really contains '%' is returned.
    assert [row.symbol for row in store.search_instruments("%")] == ["PCT"]
    assert store.search_instruments("_") == []
    assert [row.symbol for row in store.search_instruments("100%")] == ["PCT"]
    assert [row.symbol for row in store.search_instruments("btc")] == ["BTC-USD"]
    assert [row.symbol for row in store.search_instruments("SE")] == ["SAP"]


def test_search_bounds_are_enforced(store: TimeSeriesStore) -> None:
    _seed(store)
    assert len(store.search_instruments("a", limit=1)) <= 1
    with pytest.raises(ValueError):
        store.search_instruments("   ")
    with pytest.raises(ValueError):
        store.search_instruments("x" * (MAX_SEARCH_QUERY_LENGTH + 1))
    with pytest.raises(ValueError):
        store.search_instruments("sap", limit=0)
    with pytest.raises(TypeError):
        store.search_instruments(123)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Store — lifecycle
# ---------------------------------------------------------------------------


def test_close_disposes_engine_and_blocks_further_use() -> None:
    store = TimeSeriesStore("sqlite://")
    store.insert_tick("AAPL", Decimal("1"), Decimal("2"), Decimal("1.5"), 1, _ts())
    assert store.count_ticks("AAPL") == 1

    store.close()
    assert store.is_closed is True
    store.close()  # idempotent
    with pytest.raises(RuntimeError):
        store.count_ticks("AAPL")
    with pytest.raises(RuntimeError):
        store.get_ticks("AAPL")


def test_store_context_manager_closes() -> None:
    with TimeSeriesStore("sqlite://") as store:
        assert store.count_ticks() == 0
    assert store.is_closed is True


def test_failed_operation_rolls_back(store: TimeSeriesStore) -> None:
    store.insert_trade("trade-rollback", "AAPL", "b", "s", "1.00", "1", "alice", "bob", _ts())
    with pytest.raises(IntegrityError):
        store.insert_trade("trade-rollback", "AAPL", "b", "s", "1.00", "1", "alice", "bob", _ts())
    # The store is still usable after the rolled-back transaction.
    store.insert_trade("trade-ok", "AAPL", "b", "s", "1.00", "1", "alice", "bob", _ts())
    assert store.count_trades() == 2


def test_batch_insert_is_atomic_and_counted(store: TimeSeriesStore) -> None:
    ticks: list[dict[str, object]] = [
        {
            "symbol": "AAPL",
            "bid": Decimal("1.01"),
            "ask": Decimal("1.02"),
            "last": Decimal("1.015"),
            "volume": 10,
            "timestamp": _ts(hour=hour),
        }
        for hour in (9, 10, 11)
    ]
    assert store.insert_ticks_batch(ticks) == 3
    assert store.insert_ticks_batch([]) == 0
    assert store.count_ticks("AAPL") == 3

    ticks[1]["timestamp"] = datetime(2026, 3, 1, 10, 0)  # naive -> whole batch fails
    with pytest.raises(ValueError):
        store.insert_ticks_batch(ticks)
    assert store.count_ticks("AAPL") == 3
