"""Time-series storage layer using SQLAlchemy with SQLite.

Persists tick data, OHLC bars, and trade history for backtesting,
analytics, and regulatory record-keeping.
"""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    desc,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


# ---------------------------------------------------------------------------
# ORM models
# ---------------------------------------------------------------------------

class TickRecord(Base):
    __tablename__ = "ticks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), index=True, nullable=False)
    bid = Column(Float, nullable=False)
    ask = Column(Float, nullable=False)
    last = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)


class OHLCRecord(Base):
    __tablename__ = "ohlc"

    id = Column(Integer, primary_key=True, autoincrement=True)
    symbol = Column(String(12), index=True, nullable=False)
    interval = Column(String(10), nullable=False)  # e.g. "1m", "5m", "1h", "1d"
    open = Column(Float, nullable=False)
    high = Column(Float, nullable=False)
    low = Column(Float, nullable=False)
    close = Column(Float, nullable=False)
    volume = Column(Integer, nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)


class TradeRecord(Base):
    __tablename__ = "trades"

    id = Column(Integer, primary_key=True, autoincrement=True)
    trade_id = Column(String(36), unique=True, nullable=False)
    symbol = Column(String(12), index=True, nullable=False)
    buy_order_id = Column(String(36), nullable=False)
    sell_order_id = Column(String(36), nullable=False)
    price = Column(Float, nullable=False)
    quantity = Column(Float, nullable=False)
    buyer_client_id = Column(String(64), nullable=False)
    seller_client_id = Column(String(64), nullable=False)
    timestamp = Column(DateTime, index=True, nullable=False)


# ---------------------------------------------------------------------------
# Time-series store
# ---------------------------------------------------------------------------

class TimeSeriesStore:
    """SQLAlchemy-based persistence layer for market data and trades.

    Uses SQLite for workshop portability — no external database required.
    """

    def __init__(self, db_url: str = "sqlite:///data/sample.db") -> None:
        self._engine = create_engine(db_url, echo=False)
        self._session_factory = sessionmaker(bind=self._engine)
        Base.metadata.create_all(self._engine)

    def _session(self) -> Session:
        return self._session_factory()

    # -- Tick persistence ------------------------------------------------

    def insert_tick(
        self,
        symbol: str,
        bid: float,
        ask: float,
        last: float,
        volume: int,
        timestamp: datetime,
    ) -> None:
        with self._session() as session:
            record = TickRecord(
                symbol=symbol, bid=bid, ask=ask, last=last,
                volume=volume, timestamp=timestamp,
            )
            session.add(record)
            session.commit()

    def insert_ticks_batch(self, ticks: List[Dict[str, Any]]) -> None:
        with self._session() as session:
            for t in ticks:
                session.add(TickRecord(**t))
            session.commit()

    def get_ticks(
        self,
        symbol: str,
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        limit: int = 1000,
    ) -> List[TickRecord]:
        with self._session() as session:
            query = session.query(TickRecord).filter(TickRecord.symbol == symbol)
            if start:
                query = query.filter(TickRecord.timestamp >= start)
            if end:
                query = query.filter(TickRecord.timestamp <= end)
            return query.order_by(desc(TickRecord.timestamp)).limit(limit).all()

    # -- OHLC persistence -----------------------------------------------

    def insert_ohlc(
        self,
        symbol: str,
        interval: str,
        open_: float,
        high: float,
        low: float,
        close: float,
        volume: int,
        timestamp: datetime,
    ) -> None:
        with self._session() as session:
            record = OHLCRecord(
                symbol=symbol, interval=interval, open=open_,
                high=high, low=low, close=close,
                volume=volume, timestamp=timestamp,
            )
            session.add(record)
            session.commit()

    def get_ohlc(
        self,
        symbol: str,
        interval: str = "1m",
        limit: int = 500,
    ) -> List[OHLCRecord]:
        with self._session() as session:
            return (
                session.query(OHLCRecord)
                .filter(OHLCRecord.symbol == symbol, OHLCRecord.interval == interval)
                .order_by(desc(OHLCRecord.timestamp))
                .limit(limit)
                .all()
            )

    # -- Trade persistence -----------------------------------------------

    def insert_trade(
        self,
        trade_id: str,
        symbol: str,
        buy_order_id: str,
        sell_order_id: str,
        price: float,
        quantity: float,
        buyer_client_id: str,
        seller_client_id: str,
        timestamp: datetime,
    ) -> None:
        with self._session() as session:
            record = TradeRecord(
                trade_id=trade_id, symbol=symbol,
                buy_order_id=buy_order_id, sell_order_id=sell_order_id,
                price=price, quantity=quantity,
                buyer_client_id=buyer_client_id,
                seller_client_id=seller_client_id,
                timestamp=timestamp,
            )
            session.add(record)
            session.commit()

    def get_trades(
        self,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[TradeRecord]:
        with self._session() as session:
            query = session.query(TradeRecord)
            if symbol:
                query = query.filter(TradeRecord.symbol == symbol)
            return query.order_by(desc(TradeRecord.timestamp)).limit(limit).all()

    # -- Utility ---------------------------------------------------------

    def count_ticks(self, symbol: Optional[str] = None) -> int:
        with self._session() as session:
            query = session.query(TickRecord)
            if symbol:
                query = query.filter(TickRecord.symbol == symbol)
            return query.count()

    def count_trades(self, symbol: Optional[str] = None) -> int:
        with self._session() as session:
            query = session.query(TradeRecord)
            if symbol:
                query = query.filter(TradeRecord.symbol == symbol)
            return query.count()
