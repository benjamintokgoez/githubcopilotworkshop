"""Shared test fixtures for QuantCore."""

from __future__ import annotations

import pytest

from qxm.core.models import (
    Instrument,
    InstrumentType,
)


@pytest.fixture
def instruments() -> dict[str, Instrument]:
    return {
        "AAPL": Instrument(
            symbol="AAPL",
            name="Apple Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        ),
        "GOOGL": Instrument(
            symbol="GOOGL",
            name="Alphabet Inc.",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        ),
        "MSFT": Instrument(
            symbol="MSFT",
            name="Microsoft Corporation",
            instrument_type=InstrumentType.EQUITY,
            tick_size=0.01,
            lot_size=1,
        ),
    }
