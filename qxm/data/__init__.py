"""qxm.data — Market-data ingestion, storage, and transformation layer."""

from qxm.data.feed import GBMSimulator, MarketDataFeed, WebSocketFeedAdapter
from qxm.data.store import (
    InstrumentRow,
    OHLCRow,
    TickRow,
    TimeSeriesStore,
    TradeRow,
)
from qxm.data.transform import (
    compute_returns,
    compute_twap,
    compute_volatility,
    compute_vwap,
    exponential_moving_average,
    normalise_prices,
    rolling_mean,
    rolling_std,
    ticks_to_ohlc,
)

__all__ = [
    "GBMSimulator",
    "MarketDataFeed",
    "WebSocketFeedAdapter",
    "TimeSeriesStore",
    "TickRow",
    "OHLCRow",
    "TradeRow",
    "InstrumentRow",
    "ticks_to_ohlc",
    "compute_vwap",
    "compute_twap",
    "compute_returns",
    "compute_volatility",
    "normalise_prices",
    "rolling_mean",
    "rolling_std",
    "exponential_moving_average",
]
