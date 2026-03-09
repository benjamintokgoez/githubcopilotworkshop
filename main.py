"""QuantCore — Main entry point.

Initialises the trading engine, loads instruments, starts the market
data feed, and runs the FastAPI server.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Dict

import uvicorn
import yaml
from fastapi import FastAPI

# NOTE: We import submodules directly (not the top-level qxm package)
# to avoid the planted ImportError in qxm/__init__.py.  During the
# workshop, attendees fix qxm/__init__.py in Challenge 2.
from qxm.api.middleware import configure_middleware
from qxm.api.routes import router, set_engine, set_portfolio
from qxm.auth.keys import KeyManager
from qxm.core.engine import MatchingEngine
from qxm.core.events import EventBus
from qxm.core.models import Instrument, InstrumentType
from qxm.data.feed import MarketDataFeed
from qxm.data.store import TimeSeriesStore
from qxm.risk.portfolio import PortfolioAnalytics
from qxm.utils.serializer import to_json

logger = logging.getLogger("qxm")

BASE_DIR = Path(__file__).resolve().parent


# ---------------------------------------------------------------------------
# Configuration loader
# ---------------------------------------------------------------------------

def load_config(path: Path | None = None) -> Dict:
    """Load settings.yaml configuration."""
    config_path = path or BASE_DIR / "settings.yaml"
    if not config_path.exists():
        logger.warning("Config not found at %s — using defaults", config_path)
        return {"server": {"host": "0.0.0.0", "port": 8000}, "engine": {}}
    with open(config_path) as f:
        return yaml.safe_load(f)


def load_instruments(path: Path | None = None) -> Dict[str, Instrument]:
    """Load instrument definitions from JSON."""
    inst_path = path or BASE_DIR / "instruments.json"
    if not inst_path.exists():
        logger.warning("Instruments file not found — using defaults")
        return _default_instruments()
    with open(inst_path) as f:
        data = json.load(f)
    instruments = {}
    for item in data:
        inst = Instrument(**item)
        instruments[inst.symbol] = inst
    return instruments


def _default_instruments() -> Dict[str, Instrument]:
    """Fallback instrument set."""
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
    }


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------

def create_app(config: Dict | None = None) -> FastAPI:
    """Build the FastAPI application with all components wired up."""
    cfg = config or load_config()

    app = FastAPI(
        title="QuantCore Trading Platform",
        description="High-performance order matching and risk analytics",
        version="0.4.0",
    )

    # -- Core components
    event_bus = EventBus()
    instruments = load_instruments()
    engine = MatchingEngine(event_bus=event_bus, instruments=instruments)
    portfolio = PortfolioAnalytics(instruments=instruments)

    # -- Auth
    key_manager = KeyManager()
    demo_key = key_manager.generate_key("demo_client", permissions=["read", "write", "trade"])
    logger.info("Demo API key: %s", demo_key)

    # -- Wire dependencies
    set_engine(engine)
    set_portfolio(portfolio)

    # -- Store app state for access in routes
    app.state.engine = engine
    app.state.portfolio = portfolio
    app.state.event_bus = event_bus
    app.state.instruments = instruments
    app.state.key_manager = key_manager

    # -- Database
    store = TimeSeriesStore("sqlite:///quantcore.db")
    app.state.db_session = store.Session()

    # -- Middleware & routes
    configure_middleware(app, key_manager)
    app.include_router(router)

    @app.on_event("startup")
    async def startup():
        logger.info("QuantCore v0.4.0 starting — %d instruments loaded", len(instruments))
        logger.info("Instruments: %s", list(instruments.keys()))

    @app.on_event("shutdown")
    async def shutdown():
        logger.info("QuantCore shutting down")
        if hasattr(app.state, "db_session"):
            app.state.db_session.close()

    return app


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """Run the QuantCore server."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    config = load_config()
    server_cfg = config.get("server", {})

    # BUG (Challenge 2): port is loaded as string "8443" from settings.yaml
    # because YAML doesn't auto-infer types when quoted.  This causes
    # uvicorn to fail or behave unexpectedly.
    host = server_cfg.get("host", "0.0.0.0")
    port = server_cfg.get("port", 8000)

    app = create_app(config)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
