"""QuantCore — application factory and CLI entry point.

QuantCore is an **educational, simulation-only** trading platform: the matching
engine, market data, and analytics all run against synthetic data and no order
ever reaches a real venue.

Everything an application needs is created per instance and stored on
``app.state`` — there are no module-level dependency globals, so several
applications can be built in one process (or one test session) without sharing
an engine, key manager, or database.  Startup and shutdown run through a
FastAPI ``lifespan`` context, so the event bus, the optional simulated feed
task, and storage are stopped deterministically and leave no stray tasks.

Configuration and instrument files are loaded strictly: a missing or malformed
file raises instead of silently degrading to defaults.
"""

from __future__ import annotations

import argparse
import asyncio
import inspect
import logging
import math
import os
import sys
from collections.abc import AsyncIterator, Callable, Mapping, Sequence
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from dataclasses import field as dataclass_field
from pathlib import Path
from typing import Any

import uvicorn
import yaml
from fastapi import FastAPI
from fastapi.responses import FileResponse

from qxm import __version__
from qxm.api.dependencies import AppServices
from qxm.api.middleware import (
    configure_middleware,
    validate_cors_credentials,
    validate_cors_origins,
)
from qxm.api.routes import router
from qxm.api.service import DEFAULT_DISPLAY_CURRENCY, TradingService
from qxm.auth.keys import KeyManager
from qxm.core.engine import MatchingEngine
from qxm.core.events import EventBus
from qxm.core.models import Instrument
from qxm.data.feed import MarketDataFeed
from qxm.data.store import TimeSeriesStore
from qxm.utils.serializer import from_json

logger = logging.getLogger("qxm")

BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = BASE_DIR / "settings.yaml"
DEFAULT_INSTRUMENTS_PATH = BASE_DIR / "instruments.json"
DASHBOARD_INDEX = BASE_DIR / "dashboard" / "index.html"

#: Environment variables used to bootstrap a local API key.  The raw key is
#: never logged and never returned by the API.
BOOTSTRAP_KEY_ENV = "QXM_API_KEY"
BOOTSTRAP_CLIENT_ENV = "QXM_API_CLIENT_ID"
DEFAULT_BOOTSTRAP_CLIENT = "local_operator"
DEFAULT_BOOTSTRAP_PERMISSIONS = ("read", "trade")

#: Name of the background task that drives the simulated market data feed.
FEED_TASK_NAME = "qxm-market-feed"

#: Supported ``feed.mode`` values.  The application implements the deterministic
#: simulator only; ``websocket`` is refused explicitly (see
#: :func:`resolve_feed_mode`) instead of being downgraded to simulated data.
FEED_MODE_SIMULATED = "simulated"
FEED_MODE_WEBSOCKET = "websocket"
FEED_MODES_DISABLED = frozenset({"disabled", "off", "none"})
DEFAULT_FEED_SEED = 7

# Unknown settings are errors rather than inert promises. The timezone section
# is a declarative cross-surface contract: Python stores UTC while the static
# dashboard presents Europe/Berlin.
SUPPORTED_CONFIG_KEYS: dict[str, frozenset[str]] = {
    "timezone": frozenset({"application", "presentation"}),
    "server": frozenset({"host", "port", "log_level", "cors_origins", "cors_allow_credentials"}),
    "risk": frozenset({"daily_volatility"}),
    "database": frozenset({"url", "echo"}),
    "feed": frozenset({"mode", "interval_ms", "seed"}),
    "dashboard": frozenset({"currency"}),
    "auth": frozenset({"key_ttl_seconds"}),
    "logging": frozenset({"level", "format"}),
}

APP_TITLE = "QuantCore Trading Simulator"
APP_DESCRIPTION = (
    "Educational, simulation-only order matching and risk analytics. "
    "All market data is synthetic and no order is routed to a real venue."
)


# ---------------------------------------------------------------------------
# Strict configuration loading
# ---------------------------------------------------------------------------


def load_config(path: Path | str | None = None) -> dict[str, Any]:
    """Load ``settings.yaml``.

    A missing file raises :class:`FileNotFoundError` and malformed YAML raises
    :class:`yaml.YAMLError`; neither is masked with defaults.
    """
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open(encoding="utf-8") as handle:
        loaded = yaml.safe_load(handle)
    if loaded is None:
        raise ValueError(f"Configuration file is empty: {config_path}")
    if not isinstance(loaded, dict):
        raise ValueError(f"Configuration file must contain a mapping, got {type(loaded).__name__}")
    return loaded


def load_instruments(path: Path | str | None = None) -> dict[str, Instrument]:
    """Load instrument reference data from JSON, validating every entry."""
    inst_path = Path(path) if path is not None else DEFAULT_INSTRUMENTS_PATH
    if not inst_path.is_file():
        raise FileNotFoundError(f"Instruments file not found: {inst_path}")
    data = from_json(inst_path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError(f"Instruments file must contain a JSON array, got {type(data).__name__}")
    instruments: dict[str, Instrument] = {}
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(
                f"Instrument entry {index} must be a JSON object, got {type(item).__name__}"
            )
        instrument = Instrument(**item)
        if instrument.symbol in instruments:
            raise ValueError(f"Duplicate instrument symbol: {instrument.symbol}")
        instruments[instrument.symbol] = instrument
    if not instruments:
        raise ValueError(f"Instruments file contains no instruments: {inst_path}")
    return instruments


def _section(config: Mapping[str, Any], name: str) -> dict[str, Any]:
    section = config.get(name)
    if section is None:
        if name in config:
            raise ValueError(f"Configuration section {name!r} must be a mapping")
        return {}
    if not isinstance(section, Mapping):
        raise ValueError(f"Configuration section {name!r} must be a mapping")
    return dict(section)


def validate_config_keys(config: Mapping[str, Any]) -> None:
    """Reject unknown configuration sections and keys.

    Silently ignored settings make operators believe a control is active when
    it is not. Every accepted key therefore has an implemented consumer or is
    part of the explicit UTC/Europe-Berlin presentation contract.
    """
    unknown_sections = sorted(
        (key for key in config if key not in SUPPORTED_CONFIG_KEYS),
        key=lambda key: str(key),
    )
    if unknown_sections:
        raise ValueError(
            "Unsupported configuration section(s): "
            f"{', '.join(map(str, unknown_sections))}; supported sections are "
            f"{', '.join(sorted(SUPPORTED_CONFIG_KEYS))}"
        )

    for section_name, supported_keys in SUPPORTED_CONFIG_KEYS.items():
        section = _section(config, section_name)
        unknown_keys = sorted(
            (key for key in section if key not in supported_keys),
            key=lambda key: str(key),
        )
        if unknown_keys:
            raise ValueError(
                f"Unsupported configuration key(s) in {section_name!r}: "
                f"{', '.join(map(str, unknown_keys))}; supported keys are "
                f"{', '.join(sorted(supported_keys))}"
            )


def _strict_bool(value: Any, name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{name} must be a boolean")
    return value


def _nonblank_string(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-blank string")
    return value.strip()


def validate_config_values(config: Mapping[str, Any]) -> None:
    """Validate configuration values independently of optional runtime paths."""
    timezone_cfg = _section(config, "timezone")
    if timezone_cfg.get("application", "UTC") != "UTC":
        raise ValueError("timezone.application must be 'UTC'")
    if timezone_cfg.get("presentation", "Europe/Berlin") != "Europe/Berlin":
        raise ValueError("timezone.presentation must be 'Europe/Berlin'")

    server_cfg = _section(config, "server")
    coerce_host(server_cfg.get("host", "127.0.0.1"))
    coerce_port(server_cfg.get("port", 8443))
    server_log_level = _nonblank_string(
        server_cfg.get("log_level", "info"), "server.log_level"
    ).lower()
    if server_log_level not in {"critical", "error", "warning", "info", "debug", "trace"}:
        raise ValueError("server.log_level must be critical, error, warning, info, debug, or trace")
    validate_cors_origins(server_cfg.get("cors_origins"))
    validate_cors_credentials(server_cfg.get("cors_allow_credentials", False))

    database_cfg = _section(config, "database")
    _nonblank_string(database_cfg.get("url", "sqlite:///quantcore.db"), "database.url")
    _strict_bool(database_cfg.get("echo", False), "database.echo")

    feed_cfg = _section(config, "feed")
    resolve_feed_mode(feed_cfg.get("mode", FEED_MODE_SIMULATED))
    _feed_interval_seconds(feed_cfg)
    _feed_seed(feed_cfg)

    auth_cfg = _section(config, "auth")
    ttl = auth_cfg.get("key_ttl_seconds")
    if ttl is not None and (isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0):
        raise ValueError("auth.key_ttl_seconds must be a positive integer or null")

    risk_cfg = _section(config, "risk")
    _optional_positive_float(risk_cfg.get("daily_volatility"), "risk.daily_volatility")

    dashboard_cfg = _section(config, "dashboard")
    currency = dashboard_cfg.get("currency", DEFAULT_DISPLAY_CURRENCY)
    if (
        not isinstance(currency, str)
        or len(currency.strip()) != 3
        or not currency.strip().isascii()
        or not currency.strip().isalpha()
    ):
        raise ValueError("dashboard.currency must be a 3-letter ASCII currency code")

    logging_cfg = _section(config, "logging")
    logging_level = _nonblank_string(logging_cfg.get("level", "INFO"), "logging.level").upper()
    if logging_level not in logging.getLevelNamesMapping():
        raise ValueError(f"Unsupported logging.level {logging_level!r}")
    _nonblank_string(
        logging_cfg.get("format", "%(asctime)s [%(name)s] %(levelname)s: %(message)s"),
        "logging.format",
    )


def coerce_port(value: Any) -> int:
    """Return a valid TCP port, accepting an int or a numeric string."""
    if isinstance(value, bool):
        raise TypeError("port must be an integer, not a bool")
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped.isdigit():
            raise ValueError(f"port must be a positive integer, got {value!r}")
        value = int(stripped)
    if not isinstance(value, int):
        raise TypeError(f"port must be an integer, got {type(value).__name__}")
    if not 1 <= value <= 65535:
        raise ValueError(f"port must be between 1 and 65535, got {value}")
    return value


def coerce_host(value: Any) -> str:
    """Return a non-blank bind host."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("host must be a non-blank string")
    return value.strip()


def _optional_positive_float(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a number")
    if value <= 0 or not math.isfinite(value):
        raise ValueError(f"{name} must be finite and positive")
    return float(value)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app(
    config: Mapping[str, Any] | None = None,
    *,
    instruments: Mapping[str, Instrument] | None = None,
    key_manager: KeyManager | None = None,
    store: TimeSeriesStore | None = None,
    enable_store: bool = True,
    enable_feed: bool | None = None,
    bootstrap_api_key: str | None = None,
    bootstrap_client_id: str | None = None,
    bootstrap_permissions: Sequence[str] | None = None,
) -> FastAPI:
    """Build a fully wired application instance.

    Every collaborator can be injected, which keeps tests deterministic:
    ``enable_feed=False`` and ``enable_store=False`` produce an application with
    no background task and no database, and ``bootstrap_api_key`` installs a
    known key so protected endpoints can be exercised.  Without a bootstrap key
    (argument or ``QXM_API_KEY``) the application starts with no valid keys and
    protected endpoints are honestly inaccessible.

    ``enable_feed`` only overrides whether the *simulated* feed runs; the
    configured ``feed.mode`` is validated either way, so an unsupported mode
    (``websocket``) or a typo raises instead of silently changing the data
    source or disabling market data.
    """
    cfg: dict[str, Any] = dict(config) if config is not None else load_config()
    validate_config_keys(cfg)
    validate_config_values(cfg)

    auth_cfg = _section(cfg, "auth")
    db_cfg = _section(cfg, "database")
    feed_cfg = _section(cfg, "feed")
    risk_cfg = _section(cfg, "risk")
    server_cfg = _section(cfg, "server")
    dashboard_cfg = _section(cfg, "dashboard")

    resolved_instruments = dict(instruments) if instruments is not None else load_instruments()
    if not resolved_instruments:
        raise ValueError("At least one simulated instrument is required")
    for key, instrument in resolved_instruments.items():
        if key != instrument.symbol:
            raise ValueError(
                f"Instrument mapping key {key!r} does not match symbol {instrument.symbol!r}"
            )

    event_bus = EventBus()
    engine = MatchingEngine(event_bus=event_bus, instruments=resolved_instruments)

    manager = key_manager or KeyManager(default_ttl_seconds=auth_cfg.get("key_ttl_seconds"))
    _install_bootstrap_key(
        manager,
        raw_key=bootstrap_api_key,
        client_id=bootstrap_client_id,
        permissions=bootstrap_permissions,
    )

    owns_store = False
    resolved_store = store
    if resolved_store is None and enable_store:
        database_url = _nonblank_string(db_cfg.get("url", "sqlite:///quantcore.db"), "database.url")
        resolved_store = TimeSeriesStore(
            database_url,
            echo=_strict_bool(db_cfg.get("echo", False), "database.echo"),
        )
        owns_store = True
    try:
        if resolved_store is not None:
            resolved_store.seed_instruments(resolved_instruments)

        trading = TradingService(
            engine,
            event_bus,
            display_currency=dashboard_cfg.get("currency", DEFAULT_DISPLAY_CURRENCY),
            daily_volatility=_optional_positive_float(
                risk_cfg.get("daily_volatility"), "risk.daily_volatility"
            ),
            store=resolved_store,
        )

        feed = _build_feed(feed_cfg, event_bus, resolved_instruments, enable_feed)
    except BaseException:
        # Wiring failed after the database engine was opened: dispose it here,
        # because no lifespan will ever run to do it.
        if owns_store and resolved_store is not None:
            resolved_store.close()
        raise

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        """Start and stop every runtime resource exactly once.

        Startup is tracked step by step, so a failure half-way through still
        releases what was already acquired, and every teardown step runs even
        when an earlier one fails.  Teardown failures are logged and re-raised
        (never swallowed) unless an error is already propagating, in which case
        that original error wins and the cleanup failures are logged alongside it.

        The tracking flags record *intent*, not success: they are set before the
        matching ``start`` is awaited, because a start that mutates state and
        then fails still needs its idempotent ``stop``.
        """
        bus_acquired = False
        feed_acquired = False
        feed_task: asyncio.Task[None] | None = None
        shutting_down = _ShutdownFlag()
        app.state.feed_task = None

        try:
            bus_acquired = True
            await event_bus.start()
            if feed is not None:
                feed_acquired = True
                await feed.start()
                feed_task = asyncio.create_task(_pump_feed(feed, engine), name=FEED_TASK_NAME)
                feed_task.add_done_callback(_feed_task_supervisor(shutting_down))
                app.state.feed_task = feed_task
            logger.info(
                "QuantCore v%s ready (simulation) - %d instruments, feed=%s, store=%s",
                __version__,
                len(resolved_instruments),
                "on" if feed is not None else "off",
                "on" if resolved_store is not None else "off",
            )
            yield
        finally:
            shutting_down.set()
            outcome = await _release_resources(
                feed=feed if feed_acquired else None,
                feed_task=feed_task,
                event_bus=event_bus if bus_acquired else None,
                store=resolved_store if owns_store else None,
            )
            app.state.feed_task = None
            logger.info("QuantCore shutdown complete")
            _report_shutdown_failures(outcome, sys.exc_info()[1])

    app = FastAPI(
        title=APP_TITLE,
        description=APP_DESCRIPTION,
        version=__version__,
        lifespan=lifespan,
    )

    app.state.services = AppServices(
        event_bus=event_bus,
        engine=engine,
        trading=trading,
        key_manager=manager,
        instruments=resolved_instruments,
        version=__version__,
        store=resolved_store,
        feed=feed,
    )
    app.state.feed_task = None

    configure_middleware(
        app,
        manager,
        cors_origins=server_cfg.get("cors_origins"),
        # Passed through unchanged: the middleware validates the shape and
        # rejects values such as the string "false" instead of coercing them.
        cors_allow_credentials=server_cfg.get("cors_allow_credentials", False),
    )
    app.include_router(router)
    _register_dashboard_route(app)
    return app


def _install_bootstrap_key(
    manager: KeyManager,
    *,
    raw_key: str | None,
    client_id: str | None,
    permissions: Sequence[str] | None,
) -> None:
    """Register a caller- or environment-supplied raw key, if one exists.

    The raw key is never logged; only the derived key id is.
    """
    key = raw_key if raw_key is not None else os.environ.get(BOOTSTRAP_KEY_ENV)
    if not key:
        logger.info(
            "No bootstrap API key configured (%s unset); protected endpoints "
            "require a key issued out of band",
            BOOTSTRAP_KEY_ENV,
        )
        return
    client = client_id or os.environ.get(BOOTSTRAP_CLIENT_ENV) or DEFAULT_BOOTSTRAP_CLIENT
    granted = tuple(permissions) if permissions is not None else DEFAULT_BOOTSTRAP_PERMISSIONS
    record = manager.register_key(key, client, permissions=granted)
    logger.info(
        "Bootstrap API key registered as %s for client %s",
        record.key_id,
        record.client_id,
    )


def resolve_feed_mode(mode: object) -> str:
    """Validate ``feed.mode`` and return it normalised.

    The application implements exactly one live data source — the deterministic
    simulator — plus an explicit off switch.  Anything else fails closed:

    * ``websocket`` is refused rather than silently downgraded.  The
      :class:`~qxm.data.feed.WebSocketFeedAdapter` is a reusable library surface,
      but no venue is wired into the application and a workshop must not depend
      on a live network.
    * A typo such as ``simulted`` is refused rather than quietly disabling market
      data, which used to look like a working configuration with a dead feed.
    """
    if not isinstance(mode, str):
        raise ValueError(
            "feed.mode must be a string, got "
            f"{type(mode).__name__}; expected one of {_feed_mode_list()}"
        )
    normalised = mode.strip().lower()
    if normalised == FEED_MODE_WEBSOCKET:
        raise ValueError(
            "feed.mode 'websocket' is not wired into this application: "
            "qxm.data.feed.WebSocketFeedAdapter is a library surface and no "
            "venue endpoint is configured. Use feed.mode 'simulated' for the "
            "deterministic simulator, or 'disabled' to run without market data."
        )
    if normalised == FEED_MODE_SIMULATED or normalised in FEED_MODES_DISABLED:
        return normalised
    raise ValueError(f"Unsupported feed.mode {mode!r}; expected one of {_feed_mode_list()}")


def _feed_mode_list() -> str:
    return ", ".join(repr(name) for name in [FEED_MODE_SIMULATED, *sorted(FEED_MODES_DISABLED)])


def _build_feed(
    feed_cfg: Mapping[str, Any],
    event_bus: EventBus,
    instruments: Mapping[str, Instrument],
    enable_feed: bool | None,
) -> MarketDataFeed | None:
    """Create the simulated feed when enabled by argument or configuration.

    ``feed.mode`` is always validated, even when ``enable_feed`` overrides it: a
    malformed or unsupported mode is a configuration error regardless of how this
    process happens to be started.  ``enable_feed`` then decides only *whether*
    the supported simulator runs — it never selects a different data source.
    """
    mode = resolve_feed_mode(feed_cfg.get("mode", FEED_MODE_SIMULATED))
    tick_interval = _feed_interval_seconds(feed_cfg)
    seed = _feed_seed(feed_cfg)
    if enable_feed is False:
        return None
    if enable_feed is None and mode in FEED_MODES_DISABLED:
        logger.info("Market data feed disabled by configuration (feed.mode=%r)", mode)
        return None
    return MarketDataFeed(
        event_bus=event_bus,
        symbols=list(instruments),
        tick_interval=tick_interval,
        seed=seed,
    )


def _feed_interval_seconds(feed_cfg: Mapping[str, Any]) -> float:
    interval_ms = feed_cfg.get("interval_ms", 100)
    if isinstance(interval_ms, bool) or not isinstance(interval_ms, (int, float)):
        raise TypeError("feed.interval_ms must be a number")
    if interval_ms <= 0 or not math.isfinite(interval_ms):
        raise ValueError("feed.interval_ms must be finite and positive")
    return float(interval_ms) / 1000.0


def _feed_seed(feed_cfg: Mapping[str, Any]) -> int:
    seed = feed_cfg.get("seed", DEFAULT_FEED_SEED)
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("feed.seed must be an integer")
    if not 0 <= seed <= 2**32 - 1:
        raise ValueError("feed.seed must be between 0 and 4294967295")
    return int(seed)


async def _pump_feed(feed: MarketDataFeed, engine: MatchingEngine) -> None:
    """Drive the simulated tick generator and mark open positions to market.

    Consuming the stream is what publishes ``MARKET_DATA_TICK`` events and keeps
    ``feed.get_latest_tick`` current.  Each tick's ``last`` price is also applied
    to the engine's open positions, so the dashboard's unrealised P&L actually
    follows the simulated feed instead of freezing at the last fill.  Individual
    ticks are not persisted: they are high-frequency, synthetic, and reproducible
    from the feed seed.
    """
    async for tick in feed.generate_ticks():
        engine.position_manager.mark_symbol(tick.symbol, tick.last)


class _ShutdownFlag:
    """Tiny mutable flag telling the feed supervisor that stopping is expected."""

    __slots__ = ("_set",)

    def __init__(self) -> None:
        self._set = False

    def set(self) -> None:
        self._set = True

    def __bool__(self) -> bool:
        return self._set


def _feed_task_supervisor(
    shutting_down: _ShutdownFlag,
) -> Callable[[asyncio.Task[None]], None]:
    """Build a done-callback that surfaces unexpected feed-task termination."""

    def _on_done(task: asyncio.Task[None]) -> None:
        if task.cancelled():
            if not shutting_down:
                logger.error(
                    "Market data feed task %s was cancelled while the "
                    "application was still running",
                    task.get_name(),
                )
            return
        error = task.exception()
        if error is not None:
            logger.error(
                "Market data feed task %s failed: %r",
                task.get_name(),
                error,
                exc_info=error,
            )
        elif not shutting_down:
            logger.error(
                "Market data feed task %s finished before shutdown; ticks have "
                "stopped and marks will no longer update",
                task.get_name(),
            )

    return _on_done


async def _stop_task(task: asyncio.Task[None], timeout: float = 5.0) -> None:
    """Await a stopping task, cancelling it if it overruns ``timeout``.

    An exception raised by the task propagates: a pump that died is a real
    failure and must not be discovered only by silence.
    """
    try:
        await asyncio.wait_for(asyncio.shield(task), timeout=timeout)
    except TimeoutError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task
    except asyncio.CancelledError:
        if not task.cancelled():
            raise


@dataclass
class ShutdownOutcome:
    """What happened while releasing runtime resources.

    ``failures`` are ordinary errors raised by individual teardown steps.
    ``controlling`` is the first :class:`BaseException` that is *not* an
    ``Exception`` — cancellation or an interrupt — which must keep its
    propagation semantics and therefore wins over everything else.
    """

    failures: list[Exception] = dataclass_field(default_factory=list)
    controlling: BaseException | None = None


async def _release_resources(
    *,
    feed: MarketDataFeed | None,
    feed_task: asyncio.Task[None] | None,
    event_bus: EventBus | None,
    store: TimeSeriesStore | None,
) -> ShutdownOutcome:
    """Run every teardown step, collecting rather than short-circuiting failures.

    Each step is attempted even when an earlier one failed, so one broken
    resource can never strand another (a feed that refuses to stop must not keep
    the event bus running or leak the database engine).  That holds for
    ``CancelledError`` and ``KeyboardInterrupt`` too: the remaining steps still
    run, and the caller re-raises the controlling exception afterwards so
    cancellation semantics are preserved rather than downgraded.
    """
    outcome = ShutdownOutcome()

    async def _run(description: str, step: Callable[[], Any]) -> None:
        try:
            result = step()
            if inspect.isawaitable(result):
                await result
        except Exception as exc:  # collected, logged, and re-raised by the caller
            logger.exception("Shutdown step failed: %s", description)
            outcome.failures.append(exc)
        except BaseException as exc:
            # Cancellation / interrupt: remember it, finish the remaining steps,
            # and let the caller re-raise it unchanged.
            logger.error("Shutdown step interrupted by %s: %s", type(exc).__name__, description)
            if outcome.controlling is None:
                outcome.controlling = exc

    if feed is not None:
        await _run("stopping the market data feed", feed.stop)
    if feed_task is not None:
        await _run("draining the market data feed task", lambda: _stop_task(feed_task))
    if event_bus is not None:
        await _run("stopping the event bus", event_bus.stop)
    if store is not None:
        await _run("closing the time-series store", store.close)
    return outcome


def _report_shutdown_failures(outcome: ShutdownOutcome, in_flight: BaseException | None) -> None:
    """Re-raise teardown problems with the right precedence.

    A cancellation or interrupt caught during teardown always wins — swallowing
    it would break the caller's cancellation contract.  Otherwise ordinary
    teardown failures are raised, unless a real error is already propagating, in
    which case that original error wins and the failures are logged.
    """
    failures = outcome.failures
    if outcome.controlling is not None:
        for failure in failures:
            logger.error(
                "Shutdown failure %r occurred while %r was propagating",
                failure,
                outcome.controlling,
            )
        raise outcome.controlling
    if not failures:
        return
    if in_flight is not None:
        for failure in failures:
            logger.error(
                "Shutdown failure %r occurred while %r was propagating",
                failure,
                in_flight,
            )
        return
    if len(failures) == 1:
        raise failures[0]
    raise ExceptionGroup("QuantCore shutdown failed", list(failures))


def _register_dashboard_route(app: FastAPI) -> None:
    """Serve the self-contained dashboard shell same-origin, without auth."""
    if not DASHBOARD_INDEX.is_file():
        logger.warning(
            "Dashboard file not found at %s; the '/' route is not registered",
            DASHBOARD_INDEX,
        )
        return

    @app.get("/", include_in_schema=False)
    async def dashboard_index() -> FileResponse:
        return FileResponse(DASHBOARD_INDEX, media_type="text/html")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="quantcore", description=APP_DESCRIPTION)
    parser.add_argument("--config", default=None, help="path to settings.yaml")
    parser.add_argument("--host", default=None, help="bind host (overrides config)")
    parser.add_argument("--port", default=None, help="bind port (overrides config)")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    """Run the QuantCore server."""
    args = _parse_args(argv)
    config = load_config(args.config)

    logging_cfg = _section(config, "logging")
    logging.basicConfig(
        level=str(logging_cfg.get("level", "INFO")).upper(),
        format=str(logging_cfg.get("format", "%(asctime)s [%(name)s] %(levelname)s: %(message)s")),
    )

    server_cfg = _section(config, "server")
    host = coerce_host(args.host if args.host is not None else server_cfg.get("host", "127.0.0.1"))
    port = coerce_port(args.port if args.port is not None else server_cfg.get("port", 8443))

    app = create_app(config)
    uvicorn.run(app, host=host, port=port, log_level=str(server_cfg.get("log_level", "info")))


__all__ = [
    "APP_TITLE",
    "APP_DESCRIPTION",
    "BOOTSTRAP_KEY_ENV",
    "BOOTSTRAP_CLIENT_ENV",
    "FEED_TASK_NAME",
    "FEED_MODE_SIMULATED",
    "FEED_MODE_WEBSOCKET",
    "FEED_MODES_DISABLED",
    "DEFAULT_FEED_SEED",
    "SUPPORTED_CONFIG_KEYS",
    "resolve_feed_mode",
    "validate_config_keys",
    "validate_config_values",
    "ShutdownOutcome",
    "create_app",
    "load_config",
    "load_instruments",
    "coerce_host",
    "coerce_port",
    "main",
]


if __name__ == "__main__":
    main()
