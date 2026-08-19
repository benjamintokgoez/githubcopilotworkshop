#!/usr/bin/env python3
"""Workshop Doctor - deterministic preflight/health check for the QuantCore
workshop platform baseline.

Verifies the local (or CI) environment is set up correctly: Python version,
repository revision, presence of expected baseline files, importability of
key runtime dependencies, structural validity of `settings.yaml` and
`instruments.json`, and a handful of Copilot/CI-relevant environment hints.

This script never prints secret values - only whether a variable is set.
It is cross-platform (Windows/macOS/Linux) and uses only the Python
standard library, so it can run even before project dependencies are
installed.

Usage:
    python scripts/workshop_doctor.py [--json] [--strict]

Exit codes:
    0  overall status is PASS or WARN
    1  overall status is FAIL (or WARN when combined with --strict)
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

STATUS_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}

# Exact, single canonical statement of the workshop's Python baseline. Kept
# in sync with pyproject.toml requires-python, .github/workflows/ci.yml
# PYTHON_VERSION, and .devcontainer/devcontainer.json's image comment.
PYTHON_BASELINE = "3.12.14"

# Mirrors qxm.core.models.InstrumentType exactly. Options are a single
# "OPTION" instrument_type with a separate option_type: CALL|PUT field --
# there is no OPTION_CALL/OPTION_PUT instrument_type in the live contract.
ALLOWED_INSTRUMENT_TYPES = {"EQUITY", "ETF", "OPTION", "FUTURE", "FX", "CRYPTO"}
ALLOWED_OPTION_TYPES = {"CALL", "PUT"}
SYMBOL_RE = re.compile(r"^[A-Z0-9][A-Z0-9._/\-]*$")

# Runtime packages the application depends on; import failures here are a
# WARN (not FAIL) because this doctor is designed to run even *before*
# `pip install` has been done, e.g. as a first setup diagnostic.
RUNTIME_IMPORTS = [
    "pydantic",
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "yaml",
    "numpy",
    "scipy",
    "sortedcontainers",
    "websockets",
    "mcp",
]

EXPECTED_FILES = [
    "pyproject.toml",
    "requirements.txt",
    "settings.yaml",
    "instruments.json",
    ".env.example",
    ".github/workflows/ci.yml",
    ".devcontainer/devcontainer.json",
    "dashboard/index.html",
    "ARCHITECTURE.md",
    "docs/API_REFERENCE.md",
    "docs/DOMAIN_GLOSSARY.md",
    "challenges/README.md",
    "workshop/ops/FACILITATOR_GUIDE.md",
    "workshop/ops/RELEASE_CHECKLIST.md",
    "workshop/scenarios/catalogue.json",
    "scripts/workshop.py",
    "scripts/workshop_doctor.py",
]

SCENARIO_IDS = (
    "incident-fill-price",
    "migration-legacy-models",
    "review-pr",
    "elective-mcp",
    "elective-cli",
    "elective-customization",
    "capstone-transfer",
)

SUPPORTED_SETTINGS_KEYS = {
    "timezone": {"application", "presentation"},
    "server": {
        "host",
        "port",
        "log_level",
        "cors_origins",
        "cors_allow_credentials",
    },
    "risk": {"daily_volatility"},
    "database": {"url", "echo"},
    "feed": {"mode", "interval_ms", "seed"},
    "dashboard": {"currency"},
    "auth": {"key_ttl_seconds"},
    "logging": {"level", "format"},
}


@dataclass
class CheckResult:
    name: str
    status: str  # PASS | WARN | FAIL
    detail: str = ""


@dataclass
class Report:
    results: list[CheckResult] = field(default_factory=list)

    def add(self, name: str, status: str, detail: str = "") -> None:
        if status not in STATUS_ORDER:
            raise ValueError(f"invalid status: {status!r}")
        self.results.append(CheckResult(name=name, status=status, detail=detail))

    @property
    def overall(self) -> str:
        if not self.results:
            return "WARN"
        worst = max(self.results, key=lambda r: STATUS_ORDER[r.status])
        return worst.status


def _parse_requires_python(pyproject_text: str) -> str | None:
    """Extract the `requires-python` value from pyproject.toml text without
    requiring a TOML parser (kept dependency-free for maximum portability)."""
    match = re.search(r'^requires-python\s*=\s*"([^"]+)"', pyproject_text, re.MULTILINE)
    return match.group(1) if match else None


def _python_satisfies(version_info: tuple[int, int], spec: str) -> bool:
    """Evaluate a simple comma-separated PEP 440-style version spec such as
    '>=3.12,<3.14' against a (major, minor) tuple. Supports >=, <, ==, >, <=."""
    ok = True
    for clause in spec.split(","):
        clause = clause.strip()
        m = re.match(r"(>=|<=|==|>|<)\s*(\d+)(?:\.(\d+))?", clause)
        if not m:
            continue
        op, major, minor = m.group(1), int(m.group(2)), int(m.group(3) or 0)
        target = (major, minor)
        if op == ">=":
            ok &= version_info >= target
        elif op == "<=":
            ok &= version_info <= target
        elif op == "==":
            ok &= version_info == target
        elif op == ">":
            ok &= version_info > target
        elif op == "<":
            ok &= version_info < target
    return ok


# Curriculum delivery requires exactly this (major, minor); pyproject's
# `requires-python` is intentionally broader (also allows 3.13) for package
# compatibility, but the workshop doctor enforces the stricter delivery
# baseline regardless of what the package bounds permit.
WORKSHOP_PYTHON_MINOR = (3, 12)


def check_python_version(report: Report) -> None:
    current = sys.version_info[:2]
    running = sys.version.split()[0]
    detail = f"running {running} ({sys.executable}); workshop baseline is Python {PYTHON_BASELINE}"
    pyproject_path = REPO_ROOT / "pyproject.toml"

    # Package-compatibility note (informational only): does the running
    # interpreter satisfy pyproject's broader `requires-python` bound?
    package_note = ""
    if pyproject_path.exists():
        text = pyproject_path.read_text(encoding="utf-8")
        spec = _parse_requires_python(text)
        if spec is not None:
            satisfied = "is satisfied" if _python_satisfies(current, spec) else "is NOT satisfied"
            package_note = f"; package requires-python {spec} {satisfied}"
    else:
        package_note = "; pyproject.toml not found to verify package bounds"

    if current != WORKSHOP_PYTHON_MINOR:
        report.add(
            "python_version",
            "FAIL",
            f"{detail}{package_note}; curriculum delivery requires exactly Python "
            f"{WORKSHOP_PYTHON_MINOR[0]}.{WORKSHOP_PYTHON_MINOR[1]}.x, found "
            f"{current[0]}.{current[1]}",
        )
        return

    if running == PYTHON_BASELINE:
        note = " (matches the exact verified 3.12.14 baseline pin)"
    else:
        note = (
            " (a different 3.12.x patch than the verified 3.12.14 baseline; "
            "still workshop-compatible)"
        )
    report.add("python_version", "PASS", f"{detail}{package_note}{note}")


def check_git_revision(report: Report) -> None:
    git = shutil.which("git")
    if git is None:
        report.add("git_revision", "WARN", "git executable not found on PATH")
        return
    try:
        # git path is resolved via shutil.which and argv is fully hardcoded
        # below, so there is no untrusted-input injection risk here.
        result = subprocess.run(  # noqa: S603
            [git, "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        report.add("git_revision", "WARN", f"could not determine revision: {exc}")
        return
    if result.returncode == 0 and result.stdout.strip():
        report.add("git_revision", "PASS", f"HEAD is {result.stdout.strip()}")
    else:
        report.add("git_revision", "WARN", "not a git repository or no commits yet")


def check_expected_files(report: Report) -> None:
    missing = [p for p in EXPECTED_FILES if not (REPO_ROOT / p).exists()]
    if missing:
        report.add("expected_files", "FAIL", f"missing: {', '.join(missing)}")
    else:
        report.add(
            "expected_files", "PASS", f"all {len(EXPECTED_FILES)} expected baseline files present"
        )


def _manifest_path(value: Any, *, label: str) -> tuple[Path | None, str | None]:
    if not isinstance(value, str) or not value:
        return None, f"{label} must be a non-empty repository-relative path"
    relative = PurePosixPath(value)
    if relative.is_absolute() or ".." in relative.parts or str(relative) != value:
        return None, f"{label} is not a normalized repository-relative path"
    current = REPO_ROOT
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            return None, f"{label} traverses symlink {relative}"
    return current, None


def check_scenario_catalogue(report: Report) -> None:
    """Validate the exact seven-scenario inventory and its local fallbacks."""
    catalogue_path = REPO_ROOT / "workshop" / "scenarios" / "catalogue.json"
    try:
        catalogue = json.loads(
            catalogue_path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        report.add("scenario_catalogue", "FAIL", f"cannot read catalogue: {exc}")
        return

    errors: list[str] = []
    if not isinstance(catalogue, dict):
        errors.append("catalogue must be a JSON object")
        scenarios: Any = None
    else:
        scenarios = catalogue.get("scenarios")
        if catalogue.get("schema_version") != 1:
            errors.append("catalogue schema_version must be 1")
    if scenarios != list(SCENARIO_IDS):
        errors.append("catalogue scenarios must be the exact seven IDs in canonical lab order")

    scenario_root = REPO_ROOT / "workshop" / "scenarios"
    fallback_root = REPO_ROOT / "workshop" / "fallbacks"
    if not scenario_root.is_dir() or scenario_root.is_symlink():
        errors.append("workshop/scenarios must be a real directory")
        actual_scenarios: list[str] = []
    else:
        actual_scenarios = sorted(path.name for path in scenario_root.iterdir() if path.is_dir())
    if not fallback_root.is_dir() or fallback_root.is_symlink():
        errors.append("workshop/fallbacks must be a real directory")
        actual_fallbacks: list[str] = []
    else:
        actual_fallbacks = sorted(path.name for path in fallback_root.iterdir() if path.is_dir())
    expected_sorted = sorted(SCENARIO_IDS)
    if actual_scenarios != expected_sorted:
        errors.append("scenario directories do not match the canonical seven IDs")
    if actual_fallbacks != expected_sorted:
        errors.append("fallback directories do not match the canonical seven IDs")

    for scenario_id in SCENARIO_IDS:
        if (scenario_root / scenario_id).is_symlink():
            errors.append(f"{scenario_id}: scenario directory must not be a symlink")
        if (fallback_root / scenario_id).is_symlink():
            errors.append(f"{scenario_id}: fallback directory must not be a symlink")
        manifest_path = scenario_root / scenario_id / "manifest.json"
        try:
            manifest = json.loads(
                manifest_path.read_text(encoding="utf-8"),
                parse_constant=_reject_json_constant,
            )
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            errors.append(f"{scenario_id}: cannot read manifest ({exc})")
            continue
        if not isinstance(manifest, dict):
            errors.append(f"{scenario_id}: manifest must be a JSON object")
            continue
        if manifest.get("id") != scenario_id:
            errors.append(f"{scenario_id}: manifest id does not match directory")
        expected_fallback = f"workshop/fallbacks/{scenario_id}"
        if manifest.get("fallback") != expected_fallback:
            errors.append(f"{scenario_id}: fallback must be {expected_fallback}")

        path_fields: list[tuple[str, Any]] = [
            ("acceptance_doc", manifest.get("acceptance_doc")),
        ]
        required = manifest.get("required_artifacts", [])
        if not isinstance(required, list):
            errors.append(f"{scenario_id}: required_artifacts must be a list")
            required = []
        path_fields.extend(("required_artifacts", value) for value in required)
        stage = manifest.get("stage")
        if not isinstance(stage, list) or not stage:
            errors.append(f"{scenario_id}: stage must be a non-empty list")
            stage = []
        for index, item in enumerate(stage):
            if not isinstance(item, dict):
                errors.append(f"{scenario_id}: stage[{index}] must be an object")
                continue
            path_fields.append((f"stage[{index}].payload", item.get("payload")))

        for label, value in path_fields:
            path, error = _manifest_path(value, label=f"{scenario_id}.{label}")
            if error is not None:
                errors.append(error)
            elif path is not None and not path.is_file():
                errors.append(f"{scenario_id}.{label} does not exist")

        for fallback_name in ("README.md", "acceptance.md"):
            if not (fallback_root / scenario_id / fallback_name).is_file():
                errors.append(f"{scenario_id}: fallback missing {fallback_name}")

    if errors:
        report.add("scenario_catalogue", "FAIL", "; ".join(errors))
    else:
        report.add(
            "scenario_catalogue",
            "PASS",
            "exact seven scenario manifests, payloads, and fallbacks are present",
        )


def check_runtime_imports(report: Report) -> None:
    missing = []
    for module_name in RUNTIME_IMPORTS:
        try:
            __import__(module_name)
        except ImportError:
            missing.append(module_name)
    if not missing:
        report.add(
            "runtime_imports", "PASS", f"all {len(RUNTIME_IMPORTS)} runtime packages import cleanly"
        )
    elif len(missing) == len(RUNTIME_IMPORTS):
        report.add(
            "runtime_imports",
            "WARN",
            'no runtime dependencies installed yet - run: pip install -e ".[dev]"',
        )
    else:
        report.add(
            "runtime_imports",
            "WARN",
            f'missing packages: {", ".join(missing)} - run: pip install -e ".[dev]"',
        )


def check_settings_yaml(report: Report) -> None:
    settings_path = REPO_ROOT / "settings.yaml"
    if not settings_path.exists():
        report.add("settings_yaml", "FAIL", "settings.yaml not found")
        return
    try:
        import yaml
    except ImportError:
        report.add("settings_yaml", "WARN", "PyYAML not installed - skipped structural validation")
        return

    try:
        data = yaml.safe_load(settings_path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        report.add("settings_yaml", "FAIL", f"invalid YAML: {exc}")
        return

    if not isinstance(data, dict):
        report.add("settings_yaml", "FAIL", "top-level document is not a mapping")
        return

    problems: list[str] = []
    unknown_sections = sorted(
        (key for key in data if key not in SUPPORTED_SETTINGS_KEYS),
        key=lambda key: str(key),
    )
    if unknown_sections:
        problems.append(f"unsupported settings section(s): {', '.join(map(str, unknown_sections))}")
    sections: dict[str, dict[str, Any]] = {}
    for section_name, supported_keys in SUPPORTED_SETTINGS_KEYS.items():
        section = data.get(section_name, {})
        if not isinstance(section, dict):
            problems.append(f"{section_name} must be a mapping")
            sections[section_name] = {}
            continue
        sections[section_name] = section
        unknown_keys = sorted(
            (key for key in section if key not in supported_keys),
            key=lambda key: str(key),
        )
        if unknown_keys:
            problems.append(
                f"unsupported {section_name} key(s): {', '.join(map(str, unknown_keys))}"
            )

    server = sections["server"]
    port = server.get("port")
    if isinstance(port, bool) or not isinstance(port, int) or not 1 <= port <= 65535:
        problems.append("server.port must be an int (found quoted/non-int value)")
    if not isinstance(server.get("host"), str) or not server["host"].strip():
        problems.append("server.host must be a non-blank string")
    if str(server.get("log_level", "")).lower() not in {
        "critical",
        "error",
        "warning",
        "info",
        "debug",
        "trace",
    }:
        problems.append("server.log_level is unsupported")
    cors_origins = server.get("cors_origins")
    if not isinstance(cors_origins, list) or not all(
        isinstance(origin, str) and origin.strip() for origin in cors_origins
    ):
        problems.append("server.cors_origins must be a list of non-blank strings")
    if not isinstance(server.get("cors_allow_credentials"), bool):
        problems.append("server.cors_allow_credentials must be a boolean")

    tz = sections["timezone"]
    if tz.get("application") != "UTC":
        problems.append("timezone.application must be 'UTC'")
    if tz.get("presentation") != "Europe/Berlin":
        problems.append("timezone.presentation must be 'Europe/Berlin'")

    database = sections["database"]
    if not isinstance(database.get("url"), str) or not database["url"].strip():
        problems.append("database.url must be a non-empty string")
    if not isinstance(database.get("echo"), bool):
        problems.append("database.echo must be a boolean")

    feed = sections["feed"]
    interval_ms = feed.get("interval_ms")
    if (
        isinstance(interval_ms, bool)
        or not isinstance(interval_ms, (int, float))
        or interval_ms <= 0
        or not math.isfinite(interval_ms)
    ):
        problems.append("feed.interval_ms must be a positive number")
    if feed.get("mode") not in {"simulated", "disabled", "off", "none"}:
        problems.append("feed.mode must be simulated, disabled, off, or none")
    seed = feed.get("seed")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2**32 - 1:
        problems.append("feed.seed must be an integer between 0 and 4294967295")

    auth = sections["auth"]
    ttl = auth.get("key_ttl_seconds")
    if ttl is not None and (isinstance(ttl, bool) or not isinstance(ttl, int) or ttl <= 0):
        problems.append("auth.key_ttl_seconds must be a positive int or null")

    risk = sections["risk"]
    daily_volatility = risk.get("daily_volatility")
    if daily_volatility is not None and (
        isinstance(daily_volatility, bool)
        or not isinstance(daily_volatility, (int, float))
        or daily_volatility <= 0
        or not math.isfinite(daily_volatility)
    ):
        problems.append("risk.daily_volatility must be finite and positive or null")

    dashboard = sections["dashboard"]
    currency = dashboard.get("currency")
    if (
        not isinstance(currency, str)
        or len(currency) != 3
        or currency != currency.upper()
        or not currency.isascii()
        or not currency.isalpha()
    ):
        problems.append("dashboard.currency must be a 3-letter uppercase ASCII code")

    logging_config = sections["logging"]
    if str(logging_config.get("level", "")).upper() not in {
        "CRITICAL",
        "FATAL",
        "ERROR",
        "WARN",
        "WARNING",
        "INFO",
        "DEBUG",
        "NOTSET",
    }:
        problems.append("logging.level is unsupported")
    if not isinstance(logging_config.get("format"), str) or not logging_config["format"].strip():
        problems.append("logging.format must be a non-blank string")

    # No secrets belong in settings.yaml. Only scan leaf *values* (never the
    # key names themselves, which may legitimately describe credentials).
    secret_markers = ("secret", "password", "token", "private_key", "-----begin", "bearer ")
    leaf_values = "\n".join(str(v).lower() for v in _iter_leaf_values(data))
    if any(marker in leaf_values for marker in secret_markers):
        problems.append("settings.yaml appears to contain a hardcoded secret-like value")

    if problems:
        report.add("settings_yaml", "FAIL", "; ".join(problems))
    else:
        report.add("settings_yaml", "PASS", "structure, types, and timezone settings look correct")


def _parse_finite_decimal(value: Any) -> Decimal | None:
    """Parse `value` into a finite Decimal, or return `None` if it isn't
    Decimal-compatible or isn't finite.

    Booleans are rejected even though `bool` is an `int` subclass (mirrors
    the live model's own coercion). Non-finite values (Infinity, -Infinity,
    NaN) are rejected: real tick/lot/strike values must be finite.

    Callers must compare the returned Decimal directly (e.g. `dec > 0`)
    rather than converting to float: a tiny finite Decimal such as
    `1e-10000` underflows to `0.0` under `float()`, and a huge one can
    overflow to `inf`, both of which would corrupt a positivity check.
    Also note `Decimal("0")` is falsy, so callers must check `is None`
    explicitly rather than `if not parsed`.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        return None
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return parsed if parsed.is_finite() else None


def _non_blank_str(value: Any) -> bool:
    """True if `value` is a string containing at least one non-whitespace
    character. Whitespace-only strings (e.g. `"   "`) are not a meaningful
    name/exchange even though they pass a plain truthiness check."""
    return isinstance(value, str) and value.strip() != ""


def _reject_json_constant(token: str) -> Any:
    """Passed as `json.loads(parse_constant=...)` so the non-standard JSON
    extension tokens `Infinity`/`-Infinity`/`NaN` (accepted by Python's
    json module by default) are treated as parse errors instead of being
    silently turned into float('inf')/float('nan')."""
    raise ValueError(f"non-standard JSON constant {token!r} is not allowed")


def _iter_leaf_values(node: Any) -> Iterator[Any]:
    """Yield every scalar leaf value in a nested dict/list structure,
    deliberately skipping dict keys so that descriptive field names (e.g.
    'api_key_header') are never mistaken for secret values."""
    if isinstance(node, dict):
        for value in node.values():
            yield from _iter_leaf_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_leaf_values(item)
    else:
        yield node


def check_instruments_json(report: Report) -> None:
    instruments_path = REPO_ROOT / "instruments.json"
    if not instruments_path.exists():
        report.add("instruments_json", "FAIL", "instruments.json not found")
        return

    try:
        data = json.loads(
            instruments_path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (json.JSONDecodeError, ValueError) as exc:
        report.add("instruments_json", "FAIL", f"invalid JSON: {exc}")
        return

    if not isinstance(data, list) or not data:
        report.add("instruments_json", "FAIL", "expected a non-empty JSON array of instruments")
        return

    errors: list[str] = []
    seen_symbols: set[str] = set()

    common_fields = {
        "symbol",
        "name",
        "instrument_type",
        "tick_size",
        "lot_size",
        "currency",
        "exchange",
    }
    option_fields = common_fields | {"underlying", "strike", "expiry", "option_type"}

    for idx, item in enumerate(data):
        if not isinstance(item, dict):
            errors.append(f"<item {idx}>: not an object")
            continue
        label = item.get("symbol", f"<item {idx}>")

        symbol = item.get("symbol")
        if not isinstance(symbol, str) or not (1 <= len(symbol) <= 32):
            errors.append(f"{label}: symbol must be a string of length 1-32")
        elif not SYMBOL_RE.match(symbol):
            errors.append(f"{label}: symbol must be uppercase alphanumeric with . _ / - separators")
        elif symbol in seen_symbols:
            errors.append(f"{label}: duplicate symbol")
        else:
            seen_symbols.add(symbol)

        name = item.get("name")
        if not _non_blank_str(name):
            errors.append(f"{label}: name must be a non-empty (non-whitespace) string")

        exchange = item.get("exchange")
        if not _non_blank_str(exchange):
            errors.append(f"{label}: exchange must be a non-empty (non-whitespace) string")

        itype = item.get("instrument_type")
        if itype not in ALLOWED_INSTRUMENT_TYPES:
            errors.append(
                f"{label}: instrument_type must be one of {sorted(ALLOWED_INSTRUMENT_TYPES)}"
            )

        currency = item.get("currency")
        if not isinstance(currency, str) or len(currency) != 3:
            errors.append(f"{label}: currency must be a 3-letter code")

        tick_size = _parse_finite_decimal(item.get("tick_size"))
        if tick_size is None:
            errors.append(f"{label}: tick_size must be Decimal-compatible and finite")
        elif tick_size <= 0:
            errors.append(f"{label}: tick_size must be positive")

        lot_size = _parse_finite_decimal(item.get("lot_size"))
        if lot_size is None:
            errors.append(
                f"{label}: lot_size must be Decimal-compatible and finite (fractional allowed)"
            )
        elif lot_size <= 0:
            errors.append(f"{label}: lot_size must be positive")

        if itype == "OPTION":
            option_type = item.get("option_type")
            underlying = item.get("underlying")
            strike = item.get("strike")
            expiry = item.get("expiry")
            if option_type not in ALLOWED_OPTION_TYPES:
                errors.append(
                    f"{label}: option requires option_type in {sorted(ALLOWED_OPTION_TYPES)}"
                )
            if not isinstance(underlying, str) or not underlying:
                errors.append(f"{label}: option requires non-empty 'underlying'")
            strike_dec = _parse_finite_decimal(strike)
            if strike_dec is None or strike_dec <= 0:
                errors.append(f"{label}: option requires a positive 'strike'")
            if not isinstance(expiry, str):
                errors.append(f"{label}: option requires an 'expiry' date string")
            else:
                # Fixtures are dated scenarios (e.g. a 2027 option chain),
                # not live market data, so a past expiry is not an error -
                # only the ISO `date` format itself is validated here.
                try:
                    date.fromisoformat(expiry)
                except ValueError:
                    errors.append(f"{label}: expiry is not a valid ISO date (YYYY-MM-DD)")
            extra_keys = set(item) - option_fields
        else:
            extra_keys = set(item) - common_fields
        if extra_keys:
            errors.append(f"{label}: unsupported extra field(s) {sorted(extra_keys)}")

    if errors:
        report.add("instruments_json", "FAIL", "; ".join(errors))
    else:
        report.add(
            "instruments_json",
            "PASS",
            f"{len(data)} instrument(s) valid against the canonical schema "
            f"(types: {sorted(ALLOWED_INSTRUMENT_TYPES)})",
        )

    _crosscheck_live_model(report, data)


def _crosscheck_live_model(report: Report, data: list[dict[str, Any]]) -> None:
    """Best-effort live cross-check against the actual domain model. This is
    informational only (WARN, never FAIL) so the dependency-free doctor remains
    useful before the project has been installed."""
    try:
        from qxm.core.models import Instrument
    except ImportError as exc:
        report.add(
            "instruments_live_model_crosscheck",
            "WARN",
            f"qxm.core.models not importable yet, skipped live validation ({exc})",
        )
        return

    live_errors = []
    for item in data:
        try:
            Instrument(**item)
        except (ValueError, TypeError) as exc:
            live_errors.append(f"{item.get('symbol')}: {exc.__class__.__name__}")
    if live_errors:
        report.add(
            "instruments_live_model_crosscheck",
            "WARN",
            f"{len(live_errors)} instrument(s) do not validate against the live "
            f"qxm.core.models.Instrument: {'; '.join(live_errors)}",
        )
    else:
        report.add(
            "instruments_live_model_crosscheck",
            "PASS",
            "all instruments also validate against the live qxm.core.models.Instrument",
        )


def check_copilot_environment(report: Report) -> None:
    hints = []

    for tool_name in ("git", "gh"):
        path = shutil.which(tool_name)
        hints.append(f"{tool_name}={'found' if path else 'missing'}")

    # Presence-only checks: never print the value of anything secret-like.
    for var in ("GITHUB_TOKEN", "GH_TOKEN", "QXM_AUTH_SECRET_KEY"):
        hints.append(f"{var}={'set' if os.environ.get(var) else 'unset'}")

    # Non-secret environment hints - safe to show the actual value.
    hints.append(f"CODESPACES={'yes' if os.environ.get('CODESPACES') else 'no'}")
    hints.append(f"REMOTE_CONTAINERS={'yes' if os.environ.get('REMOTE_CONTAINERS') else 'no'}")
    hints.append(f"TZ={os.environ.get('TZ', 'unset')}")

    copilot_instructions = REPO_ROOT / ".github" / "copilot-instructions.md"
    present = "present" if copilot_instructions.exists() else "absent"
    hints.append(f"copilot-instructions.md={present}")

    missing_recommended = [t for t in ("git", "gh") if shutil.which(t) is None]
    status = "WARN" if missing_recommended else "PASS"
    report.add("copilot_environment_hints", status, "; ".join(hints))


CHECKS = [
    check_python_version,
    check_git_revision,
    check_expected_files,
    check_scenario_catalogue,
    check_runtime_imports,
    check_settings_yaml,
    check_instruments_json,
    check_copilot_environment,
]


def run_all_checks() -> Report:
    report = Report()
    for check in CHECKS:
        check(report)
    return report


def render_text_report(report: Report) -> str:
    lines = ["QuantCore Workshop Doctor", "=" * 32, ""]
    for result in report.results:
        lines.append(f"[{result.status:<4}] {result.name}")
        if result.detail:
            lines.append(f"         {result.detail}")
    lines.append("")
    lines.append(f"OVERALL: {report.overall}")
    return "\n".join(lines)


def render_json_report(report: Report) -> str:
    payload = {
        "overall": report.overall,
        "checks": [
            {"name": r.name, "status": r.status, "detail": r.detail} for r in report.results
        ],
    }
    return json.dumps(payload, indent=2)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON output")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="treat WARN as FAIL for the purposes of the exit code",
    )
    args = parser.parse_args(argv)

    report = run_all_checks()
    print(render_json_report(report) if args.json else render_text_report(report))

    if report.overall == "FAIL":
        return 1
    if report.overall == "WARN" and args.strict:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
