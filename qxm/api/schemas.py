"""Pydantic v2 request/response models for the QuantCore REST surface.

Requests carry JSON bodies (not loose query strings) and use the canonical core
enumerations, so ``Side``/``OrderType``/``TimeInForce`` are validated by the
domain model rather than re-implemented here.  Quantities and prices are
``Decimal`` end-to-end — fractional lots such as ``0.001`` BTC survive intact.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from qxm.core.models import Order, OrderStatus, OrderType, Side, TimeInForce

#: Character set accepted for a client-supplied ``order_id``.
#:
#: Every id must survive a round trip through ``/api/v1/orders/{order_id}``
#: unescaped, so the set is restricted to URL-path-segment-safe characters.
#: An id must additionally start and end alphanumeric: that keeps single
#: character ids usable while excluding the dot-segments ``.`` and ``..``,
#: which URL normalisation rewrites and which would therefore be just as
#: unaddressable as a segment containing ``/``.  UUID4 values (hex digits plus
#: ``-``) are covered.
ORDER_ID_PATTERN = r"^[A-Za-z0-9](?:[A-Za-z0-9._:-]*[A-Za-z0-9])?$"
#: Maximum length of a client-supplied ``order_id``.
ORDER_ID_MAX_LENGTH = 64


def _coerce_decimal(value: object) -> object:
    """Coerce numeric input to ``Decimal`` via text, avoiding float artefacts."""
    if value is None or isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("boolean is not a valid numeric value")
    if isinstance(value, (int, float, str)):
        try:
            return Decimal(str(value))
        except InvalidOperation as exc:
            raise ValueError(f"{value!r} is not a valid decimal") from exc
    return value


class OrderRequest(BaseModel):
    """Body of ``POST /api/v1/orders``.

    ``client_id`` is intentionally absent: the identity is derived from the
    validated API key, so a caller can never trade as somebody else.
    ``order_id`` may be supplied by the client for idempotency testing; a
    repeated id is a conflict (HTTP 409).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, max_length=32)
    side: Side
    quantity: Decimal = Field(..., gt=0)
    order_type: OrderType = OrderType.LIMIT
    price: Decimal | None = Field(default=None, gt=0)
    stop_price: Decimal | None = Field(default=None, gt=0)
    time_in_force: TimeInForce = TimeInForce.GTC
    order_id: str | None = Field(
        default=None,
        min_length=1,
        max_length=ORDER_ID_MAX_LENGTH,
        pattern=ORDER_ID_PATTERN,
        description=(
            "Optional client-supplied id. Must be URL-path-segment safe: "
            "letters and digits, optionally separated by . _ : - , and it must "
            "start and end with a letter or digit."
        ),
    )

    @field_validator("quantity", "price", "stop_price", mode="before")
    @classmethod
    def _decimalise(cls, value: object) -> object:
        return _coerce_decimal(value)

    def to_order(self, client_id: str) -> Order:
        """Build the canonical core order for this request.

        Domain invariants (e.g. a LIMIT order needs a price) are enforced by
        :class:`~qxm.core.models.Order`; the resulting ``ValidationError`` is
        translated to a 4xx by the route.
        """
        payload: dict[str, Any] = {
            "client_id": client_id,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "quantity": self.quantity,
            "price": self.price,
            "stop_price": self.stop_price,
            "time_in_force": self.time_in_force,
        }
        if self.order_id is not None:
            payload["order_id"] = self.order_id
        return Order(**payload)


class OrderSubmissionResponse(BaseModel):
    """Result of an accepted submission, including any immediate executions."""

    accepted: bool
    order_id: str
    status: OrderStatus
    filled_quantity: Decimal
    order: dict[str, Any]
    trades: list[dict[str, Any]]


class OrderListResponse(BaseModel):
    orders: list[dict[str, Any]]
    count: int


class CancelResponse(BaseModel):
    order_id: str
    status: OrderStatus
    order: dict[str, Any]


class PositionListResponse(BaseModel):
    client_id: str
    positions: list[dict[str, Any]]
    count: int


class InstrumentSearchResponse(BaseModel):
    query: str
    results: list[dict[str, str]]
    count: int


class StrategyListResponse(BaseModel):
    strategies: list[str]


class HealthResponse(BaseModel):
    """Public liveness payload.

    ``status`` is ``healthy`` only while every configured component is doing its
    job; a configured market data feed that has stopped makes it ``degraded``.
    ``feed`` names that component's state (``off``/``running``/``stopped``)
    without revealing why it stopped — the reason belongs in the server log, not
    in an unauthenticated response.
    """

    status: str
    version: str
    timestamp: datetime
    mode: str
    feed: str


class DashboardResponse(BaseModel):
    """Exact payload contract consumed by ``dashboard/index.html``."""

    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    currency: str
    kpis: dict[str, Any]
    positions: list[dict[str, Any]]
    pnl_history: list[dict[str, Any]]
    risk: dict[str, Any]
    order_books: dict[str, dict[str, list[dict[str, Any]]]]


__all__ = [
    "ORDER_ID_PATTERN",
    "ORDER_ID_MAX_LENGTH",
    "OrderRequest",
    "OrderSubmissionResponse",
    "OrderListResponse",
    "CancelResponse",
    "PositionListResponse",
    "InstrumentSearchResponse",
    "StrategyListResponse",
    "HealthResponse",
    "DashboardResponse",
]
