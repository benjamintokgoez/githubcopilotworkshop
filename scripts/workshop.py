#!/usr/bin/env python3
"""Workshop scenario runner for the QuantCore workshop.

Stages, verifies, and restores the deterministic lab scenarios that the
curriculum refers to.  A clean checkout is green: nothing in this repository
is broken at rest.  ``start`` is the only command that stages a failing or
questionable state, and ``reset`` restores the exact pre-start bytes.

Usage:
    python scripts/workshop.py list
    python scripts/workshop.py start <scenario-id>
    python scripts/workshop.py status
    python scripts/workshop.py resync <scenario-id> --blocked-at <phase>
    python scripts/workshop.py verify <scenario-id>
    python scripts/workshop.py reset <scenario-id>
    python scripts/workshop.py fallback <scenario-id>

Exit codes:
    0  success
    1  runtime error (actionable message on stderr)
    2  command-line usage error
    3  acceptance check failed (fail-before / not-yet-repaired)
    4  scenario state conflict (another scenario active, wrong id, no active)
    5  catalogue, manifest, or artifact is invalid
    6  a declared prerequisite is missing from this environment

The runner uses only the Python standard library so it works before project
dependencies are installed.  It performs no network access and no telemetry,
never uses a shell, and never writes credentials into its own state files.

Security note: the shipped acceptance checks are offline and bounded, and
acceptance commands run with a minimal environment rather than the caller's.
That is defence in depth, not a sandbox: an acceptance command still executes
participant-authored Python with the participant's own privileges.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import shutil
import stat
import subprocess  # noqa: S404 - only fixed argv lists from validated manifests
import sys
import tempfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any, Final
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TOOL_NAME: Final = "workshop.py"
TOOL_VERSION: Final = "1.1.0"
STATE_SCHEMA_VERSION: Final = 1
MANIFEST_SCHEMA_VERSION: Final = 1

STATE_DIR_NAME: Final = ".workshop-state"
STATE_FILE_NAME: Final = "state.json"
BACKUP_DIR_NAME: Final = "backups"
ATTEMPT_DIR_NAME: Final = "attempts"

SCENARIO_ROOT: Final = PurePosixPath("workshop/scenarios")
FALLBACK_ROOT: Final = PurePosixPath("workshop/fallbacks")
CATALOGUE_PATH: Final = SCENARIO_ROOT / "catalogue.json"
MANIFEST_NAME: Final = "manifest.json"

MAX_PAYLOAD_BYTES: Final = 256 * 1024
MAX_EVIDENCE_BYTES: Final = 512 * 1024
MAX_MANIFEST_BYTES: Final = 128 * 1024
MAX_STATE_BYTES: Final = 256 * 1024
MAX_ARCHIVE_FILE_BYTES: Final = 2 * 1024 * 1024
MAX_ARCHIVE_TOTAL_BYTES: Final = 20 * 1024 * 1024
MAX_ARCHIVE_FILES: Final = 200
MAX_OUTPUT_LINES: Final = 40
MAX_OUTPUT_CHARS: Final = 4000
MIN_TIMEOUT_SECONDS: Final = 1
MAX_TIMEOUT_SECONDS: Final = 900
DEFAULT_TIMEOUT_SECONDS: Final = 120

PYTHON_PLACEHOLDER: Final = "{python}"
SAFE_PATH_CHARS: Final = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-/"
)
SCENARIO_ID_CHARS: Final = frozenset("abcdefghijklmnopqrstuvwxyz0123456789-")
HEX_CHARS: Final = frozenset("0123456789abcdef")

# Credential shapes that must never be echoed back from captured command
# output.  The runner reads no secrets itself, but an acceptance command runs
# participant code that might print one.  Patterns are fixed and local; none of
# them is ever built from manifest or state data.
REDACT_PATTERNS: Final = (
    # Bearer values first: otherwise a key/value match would treat the word
    # "Bearer" as the secret and leave the token itself in the output.
    re.compile(r"(?i)\bbearer\s+(?P<value>[A-Za-z0-9._\-]{6,})"),
    re.compile(
        r"(?i)\b(?P<key>authorization|token|access[_-]?token|api[_-]?key|apikey|"
        r"access[_-]?key|secret[_-]?key|client[_-]?secret|secret|password|passwd|pwd)\b"
        r"(?P<sep>\s*[:=]\s*)(?P<value>[^\s,;'\"]+)"
    ),
    re.compile(
        r"(?P<value>(?:ghp_|gho_|ghu_|ghs_|ghr_|github_pat_|xox[bpasr]-|sk-|"
        r"AKIA|ASIA)[A-Za-z0-9_\-]{6,})"
    ),
    re.compile(r"(?P<value>-----BEGIN [A-Z ]*PRIVATE KEY-----)"),
)
REDACTED: Final = "<redacted>"

# Environment variables an acceptance command may inherit.  Everything else -
# including any credential the caller happens to have exported - is dropped.
INHERITED_ENV_KEYS: Final = (
    "SYSTEMROOT",
    "SystemRoot",
    "COMSPEC",
    "ComSpec",
    "PATHEXT",
    "WINDIR",
    "NUMBER_OF_PROCESSORS",
    "PROCESSOR_ARCHITECTURE",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
)

EXIT_OK: Final = 0
EXIT_ERROR: Final = 1
EXIT_USAGE: Final = 2
EXIT_ACCEPTANCE_FAILED: Final = 3
EXIT_STATE_CONFLICT: Final = 4
EXIT_INVALID_ARTIFACT: Final = 5
EXIT_PREREQUISITE: Final = 6

KIND_CODE: Final = "code"
KIND_EVIDENCE: Final = "evidence"
VALID_KINDS: Final = (KIND_CODE, KIND_EVIDENCE)

PHASE_STAGING: Final = "staging"
PHASE_ACTIVE: Final = "active"

BLOCKED_TOOLING: Final = "tooling"
BLOCKED_UNDERSTAND_PLAN: Final = "understand-plan"
BLOCKED_IMPLEMENT_TEST: Final = "implement-test"
BLOCKED_REVIEW: Final = "review"
BLOCKED_EXPLAIN: Final = "explain"
RESYNC_PHASES: Final = (
    BLOCKED_TOOLING,
    BLOCKED_UNDERSTAND_PLAN,
    BLOCKED_IMPLEMENT_TEST,
    BLOCKED_REVIEW,
    BLOCKED_EXPLAIN,
)


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class WorkshopError(Exception):
    """Base class for actionable, non-traceback failures."""

    exit_code: int = EXIT_ERROR

    def __init__(self, message: str, *, hint: str | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint


class ArtifactError(WorkshopError):
    """Catalogue, manifest, payload, or fallback artifact is invalid."""

    exit_code = EXIT_INVALID_ARTIFACT


class StateConflictError(WorkshopError):
    """Requested operation conflicts with the recorded scenario state."""

    exit_code = EXIT_STATE_CONFLICT


class PrerequisiteError(WorkshopError):
    """A declared prerequisite is not available in this environment."""

    exit_code = EXIT_PREREQUISITE


class AcceptanceFailed(WorkshopError):
    """Acceptance checks ran and did not pass."""

    exit_code = EXIT_ACCEPTANCE_FAILED


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def utc_now_iso() -> str:
    """Timezone-aware UTC timestamp for machine artifacts (INV-TIME-1)."""
    return datetime.now(UTC).isoformat(timespec="seconds")


def utc_compact_stamp() -> str:
    """Sortable UTC stamp usable inside a directory name (INV-FMT-4)."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def local_display(iso_utc: str) -> str:
    """Render a stored UTC timestamp for a Europe/Berlin reader (INV-TIME-2).

    Falls back to the stored UTC value when tz data is unavailable, because
    presentation must never become a hard dependency of the tooling.
    """
    try:
        moment = datetime.fromisoformat(iso_utc).astimezone(ZoneInfo("Europe/Berlin"))
    except (ValueError, KeyError, ZoneInfoNotFoundError):
        return f"{iso_utc} (UTC)"
    return f"{iso_utc} (= {moment.strftime('%d.%m.%Y %H:%M')} Europe/Berlin)"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
    except OSError as exc:
        raise WorkshopError(f"cannot read {path.name}: {exc.strerror or exc}") from exc
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_mode(path: Path) -> int:
    try:
        return path.stat().st_mode & 0o777
    except OSError as exc:
        raise WorkshopError(f"cannot stat {path.name}: {exc.strerror or exc}") from exc


def read_bytes_checked(path: Path, *, what: str) -> bytes:
    """Read a file, turning I/O failures into actionable errors."""
    try:
        return path.read_bytes()
    except OSError as exc:
        raise WorkshopError(f"cannot read {what}: {exc.strerror or exc}") from exc


def atomic_write_bytes(path: Path, data: bytes, mode: int) -> None:
    """Write ``data`` to ``path`` atomically and durably."""
    parent = path.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
        handle = tempfile.NamedTemporaryFile(
            mode="wb", dir=str(parent), prefix=".workshop-tmp-", delete=False
        )
    except OSError as exc:
        raise WorkshopError(f"cannot write {path.name}: {exc.strerror or exc}") from exc
    tmp_path = Path(handle.name)
    try:
        with handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(tmp_path, mode)
        os.replace(tmp_path, path)
    except OSError as exc:
        tmp_path.unlink(missing_ok=True)
        raise WorkshopError(f"cannot write {path.name}: {exc.strerror or exc}") from exc
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise
    _fsync_dir(parent)


def _fsync_dir(path: Path) -> None:
    try:
        fd = os.open(str(path), os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(fd)
    except OSError:
        pass
    finally:
        os.close(fd)


def read_json(path: Path, *, max_bytes: int, what: str) -> dict[str, Any]:
    if not path.is_file():
        raise ArtifactError(
            f"{what} is missing: {path}",
            hint="Re-checkout the repository or report a corrupt workshop package.",
        )
    size = path.stat().st_size
    if size > max_bytes:
        raise ArtifactError(f"{what} is larger than the {max_bytes} byte limit: {path}")
    try:
        raw = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ArtifactError(f"{what} is not valid UTF-8: {path} ({exc.reason})") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ArtifactError(f"{what} is not valid JSON: {path} (line {exc.lineno})") from exc
    if not isinstance(parsed, dict):
        raise ArtifactError(f"{what} must be a JSON object: {path}")
    return parsed


# ---------------------------------------------------------------------------
# Schema validation primitives
# ---------------------------------------------------------------------------


def _check_keys(
    obj: dict[str, Any], *, required: Sequence[str], optional: Sequence[str], where: str
) -> None:
    keys = set(obj)
    missing = sorted(set(required) - keys)
    if missing:
        raise ArtifactError(f"{where}: missing required key(s): {', '.join(missing)}")
    unknown = sorted(keys - set(required) - set(optional))
    if unknown:
        raise ArtifactError(f"{where}: unknown key(s): {', '.join(unknown)}")


def _as_str(obj: dict[str, Any], key: str, where: str, *, default: str | None = None) -> str:
    if key not in obj:
        if default is None:
            raise ArtifactError(f"{where}: missing string key {key!r}")
        return default
    value = obj[key]
    if not isinstance(value, str) or not value.strip():
        raise ArtifactError(f"{where}: key {key!r} must be a non-empty string")
    return value


def _as_int(obj: dict[str, Any], key: str, where: str, *, default: int, low: int, high: int) -> int:
    if key not in obj:
        return default
    value = obj[key]
    if isinstance(value, bool) or not isinstance(value, int):
        raise ArtifactError(f"{where}: key {key!r} must be an integer")
    if not low <= value <= high:
        raise ArtifactError(f"{where}: key {key!r} must be between {low} and {high}")
    return int(value)


def _as_str_list(
    obj: dict[str, Any], key: str, where: str, *, default: tuple[str, ...] = ()
) -> tuple[str, ...]:
    if key not in obj:
        return default
    value = obj[key]
    if not isinstance(value, list):
        raise ArtifactError(f"{where}: key {key!r} must be a list of strings")
    out: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item:
            raise ArtifactError(f"{where}: {key}[{index}] must be a non-empty string")
        out.append(item)
    return tuple(out)


def _as_dict_list(obj: dict[str, Any], key: str, where: str) -> list[dict[str, Any]]:
    value = obj.get(key)
    if not isinstance(value, list) or not value:
        raise ArtifactError(f"{where}: key {key!r} must be a non-empty list of objects")
    out: list[dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict):
            raise ArtifactError(f"{where}: {key}[{index}] must be an object")
        out.append(item)
    return out


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------


def check_relpath(rel: str, *, what: str) -> PurePosixPath:
    """Validate a manifest-declared repo-relative POSIX path.

    Rejects absolute paths, drive letters, backslashes, ``..``/``.`` segments,
    and anything outside a conservative ASCII character set.
    """
    if not rel or rel != rel.strip():
        raise ArtifactError(f"{what}: path must be a non-empty, untrimmed-free string")
    if "\\" in rel:
        raise ArtifactError(f"{what}: backslashes are not allowed in {rel!r}")
    if rel.startswith("/") or (len(rel) > 1 and rel[1] == ":"):
        raise ArtifactError(f"{what}: absolute paths are not allowed ({rel!r})")
    bad = sorted(set(rel) - SAFE_PATH_CHARS)
    if bad:
        raise ArtifactError(f"{what}: unsupported character(s) {bad!r} in {rel!r}")
    pure = PurePosixPath(rel)
    for part in pure.parts:
        if part in {"..", "."}:
            raise ArtifactError(f"{what}: relative traversal is not allowed ({rel!r})")
    if str(pure) != rel.rstrip("/"):
        raise ArtifactError(f"{what}: path must be normalised ({rel!r})")
    return pure


def resolve_under_root(root: Path, rel: PurePosixPath, *, what: str) -> Path:
    """Resolve ``rel`` under ``root`` refusing symlinked components and escapes."""
    try:
        current = root
        for part in rel.parts:
            current = current / part
            if _is_symlink(current):
                raise ArtifactError(
                    f"{what}: refusing to follow symlink {current.relative_to(root)}",
                    hint="Remove the symlink or restore a clean checkout.",
                )
        resolved_root = root.resolve()
        resolved = (root / rel).resolve()
    except (OSError, RuntimeError) as exc:
        raise ArtifactError(
            f"{what}: cannot safely resolve {rel}: {exc}",
            hint="Check the path permissions and remove any broken or looping symlink.",
        ) from exc
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ArtifactError(f"{what}: resolved path escapes the repository root ({rel})")
    return root / rel


def rel_to_root(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _is_symlink(path: Path) -> bool:
    try:
        return path.is_symlink()
    except OSError:
        return False


def check_scenario_id(value: str, *, what: str) -> str:
    """Validate a scenario identifier before it reaches any filesystem path."""
    if not value or len(value) > 64:
        raise ArtifactError(f"{what}: scenario id must be 1-64 characters")
    if set(value) - SCENARIO_ID_CHARS:
        raise ArtifactError(f"{what}: scenario id {value!r} may only use a-z, 0-9 and '-'")
    if value.startswith("-") or value.endswith("-"):
        raise ArtifactError(f"{what}: scenario id {value!r} must not start or end with '-'")
    return value


def work_dir_rel(scenario_id: str) -> PurePosixPath:
    """The only directory a scenario may ever stage into."""
    return SCENARIO_ROOT / scenario_id / "work"


def backup_dir_rel(scenario_id: str) -> PurePosixPath:
    return PurePosixPath(STATE_DIR_NAME) / BACKUP_DIR_NAME / scenario_id


def attempt_dir_rel(scenario_id: str) -> PurePosixPath:
    return PurePosixPath(STATE_DIR_NAME) / ATTEMPT_DIR_NAME / scenario_id


def check_confined(
    rel: str, *, parent: PurePosixPath, what: str, allow_parent_itself: bool = False
) -> PurePosixPath:
    """Validate ``rel`` and require it to sit under ``parent``."""
    parsed = check_relpath(rel, what=what)
    if parsed == parent:
        if allow_parent_itself:
            return parsed
        raise ArtifactError(f"{what}: {rel!r} must be inside {parent}, not the directory itself")
    if parent not in parsed.parents:
        raise ArtifactError(f"{what}: {rel!r} must be inside {parent}")
    return parsed


def check_sha256(value: str, *, what: str) -> str:
    lowered = value.lower()
    if len(lowered) != 64 or set(lowered) - HEX_CHARS:
        raise ArtifactError(f"{what}: {value!r} is not a sha256 digest")
    return lowered


def check_mode_string(value: str, *, what: str) -> str:
    if len(value) != 4 or not value.startswith("0"):
        raise ArtifactError(f"{what}: mode {value!r} must be a 4-character octal string")
    try:
        parsed = int(value, 8)
    except ValueError as exc:
        raise ArtifactError(f"{what}: mode {value!r} is not octal") from exc
    if not 0 <= parsed <= 0o777:
        raise ArtifactError(f"{what}: mode {value!r} is out of range")
    return value


def check_utc_timestamp(value: str, *, what: str) -> str:
    try:
        moment = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ArtifactError(f"{what}: {value!r} is not an ISO 8601 timestamp") from exc
    if moment.tzinfo is None:
        raise ArtifactError(f"{what}: {value!r} must be timezone-aware (INV-TIME-1)")
    return value


# ---------------------------------------------------------------------------
# Manifest model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StageItem:
    payload: PurePosixPath
    target: PurePosixPath
    mode: int
    description: str


@dataclass(frozen=True)
class AcceptanceCommand:
    label: str
    argv: tuple[str, ...]
    timeout_seconds: int

    def display(self) -> str:
        """The command as an attendee would type it in a shell."""
        tokens = ["python" if token == PYTHON_PLACEHOLDER else token for token in self.argv]
        return " ".join(shlex.quote(token) for token in tokens)


@dataclass(frozen=True)
class EvidenceField:
    label: str
    min_chars: int
    must_contain_any: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceBlock:
    heading_prefix: str
    min_count: int
    fields: tuple[EvidenceField, ...]


@dataclass(frozen=True)
class EvidenceCheck:
    path: PurePosixPath
    required_headings: tuple[str, ...]
    min_words_per_section: int
    placeholders: tuple[str, ...]
    fields: tuple[EvidenceField, ...]
    blocks: tuple[EvidenceBlock, ...]


@dataclass(frozen=True)
class Manifest:
    scenario_id: str
    title: str
    kind: str
    lab: str
    summary: str
    directory: PurePosixPath
    fallback: PurePosixPath
    required_artifacts: tuple[PurePosixPath, ...]
    required_imports: tuple[str, ...]
    stage: tuple[StageItem, ...]
    commands: tuple[AcceptanceCommand, ...]
    evidence: EvidenceCheck | None
    acceptance_doc: PurePosixPath
    briefing: tuple[str, ...]


_MANIFEST_KEYS_REQUIRED: Final = (
    "schema_version",
    "id",
    "title",
    "kind",
    "lab",
    "summary",
    "fallback",
    "acceptance_doc",
    "stage",
    "acceptance",
)
_MANIFEST_KEYS_OPTIONAL: Final = (
    "required_artifacts",
    "required_imports",
    "briefing",
)


def parse_manifest(data: dict[str, Any], *, expected_id: str, where: str) -> Manifest:
    _check_keys(
        data,
        required=_MANIFEST_KEYS_REQUIRED,
        optional=_MANIFEST_KEYS_OPTIONAL,
        where=where,
    )
    version = _as_int(
        data,
        "schema_version",
        where,
        default=0,
        low=MANIFEST_SCHEMA_VERSION,
        high=MANIFEST_SCHEMA_VERSION,
    )
    if version != MANIFEST_SCHEMA_VERSION:
        raise ArtifactError(f"{where}: unsupported schema_version {version}")

    scenario_id = _as_str(data, "id", where)
    if scenario_id != expected_id:
        raise ArtifactError(
            f"{where}: manifest id {scenario_id!r} does not match its directory {expected_id!r}"
        )
    kind = _as_str(data, "kind", where)
    if kind not in VALID_KINDS:
        raise ArtifactError(f"{where}: kind must be one of {', '.join(VALID_KINDS)}")

    directory = SCENARIO_ROOT / scenario_id
    fallback = check_relpath(_as_str(data, "fallback", where), what=f"{where}.fallback")
    expected_fallback = FALLBACK_ROOT / scenario_id
    if fallback != expected_fallback:
        raise ArtifactError(f"{where}: fallback must be {expected_fallback}")

    acceptance_doc = check_relpath(
        _as_str(data, "acceptance_doc", where), what=f"{where}.acceptance_doc"
    )
    required_artifacts = tuple(
        check_relpath(item, what=f"{where}.required_artifacts")
        for item in _as_str_list(data, "required_artifacts", where)
    )
    required_imports = _as_str_list(data, "required_imports", where)
    for module in required_imports:
        if not module.replace("_", "").replace(".", "").isalnum():
            raise ArtifactError(f"{where}: required_imports entry {module!r} is not a module name")

    stage = _parse_stage(data, scenario_id=scenario_id, where=where)
    commands, evidence = _parse_acceptance(
        data["acceptance"], kind=kind, where=f"{where}.acceptance"
    )
    return Manifest(
        scenario_id=scenario_id,
        title=_as_str(data, "title", where),
        kind=kind,
        lab=_as_str(data, "lab", where),
        summary=_as_str(data, "summary", where),
        directory=directory,
        fallback=fallback,
        required_artifacts=required_artifacts,
        required_imports=required_imports,
        stage=stage,
        commands=commands,
        evidence=evidence,
        acceptance_doc=acceptance_doc,
        briefing=_as_str_list(data, "briefing", where),
    )


def _parse_stage(data: dict[str, Any], *, scenario_id: str, where: str) -> tuple[StageItem, ...]:
    items: list[StageItem] = []
    seen_targets: set[PurePosixPath] = set()
    scenario_dir = SCENARIO_ROOT / scenario_id
    for index, raw in enumerate(_as_dict_list(data, "stage", where)):
        item_where = f"{where}.stage[{index}]"
        _check_keys(
            raw,
            required=("payload", "target", "description"),
            optional=("mode",),
            where=item_where,
        )
        payload = check_relpath(_as_str(raw, "payload", item_where), what=f"{item_where}.payload")
        target = check_relpath(_as_str(raw, "target", item_where), what=f"{item_where}.target")
        if not _is_relative_to(payload, scenario_dir):
            raise ArtifactError(f"{item_where}: payload must live under {scenario_dir}")
        if not _is_relative_to(target, scenario_dir):
            raise ArtifactError(f"{item_where}: target must live under {scenario_dir}")
        if target in seen_targets:
            raise ArtifactError(f"{item_where}: duplicate target {target}")
        seen_targets.add(target)
        mode_raw = raw.get("mode", "0644")
        if not isinstance(mode_raw, str) or len(mode_raw) != 4 or not mode_raw.startswith("0"):
            raise ArtifactError(
                f"{item_where}: mode must be a 4-character octal string like '0644'"
            )
        try:
            mode = int(mode_raw, 8)
        except ValueError as exc:
            raise ArtifactError(f"{item_where}: mode {mode_raw!r} is not octal") from exc
        if mode not in (0o644, 0o600, 0o755):
            raise ArtifactError(f"{item_where}: mode must be 0644, 0600, or 0755")
        items.append(
            StageItem(
                payload=payload,
                target=target,
                mode=mode,
                description=_as_str(raw, "description", item_where),
            )
        )
    return tuple(items)


def _is_relative_to(path: PurePosixPath, parent: PurePosixPath) -> bool:
    return path == parent or parent in path.parents


def _parse_acceptance(
    raw: Any, *, kind: str, where: str
) -> tuple[tuple[AcceptanceCommand, ...], EvidenceCheck | None]:
    if not isinstance(raw, dict):
        raise ArtifactError(f"{where}: must be an object")
    acceptance_kind = _as_str(raw, "kind", where)
    if acceptance_kind == "command":
        if kind != KIND_CODE:
            raise ArtifactError(f"{where}: command acceptance requires scenario kind 'code'")
        _check_keys(raw, required=("kind", "commands"), optional=(), where=where)
        return _parse_commands(raw, where=where), None
    if acceptance_kind == "evidence":
        if kind != KIND_EVIDENCE:
            raise ArtifactError(f"{where}: evidence acceptance requires scenario kind 'evidence'")
        _check_keys(raw, required=("kind", "evidence"), optional=(), where=where)
        return (), _parse_evidence(raw["evidence"], where=f"{where}.evidence")
    raise ArtifactError(f"{where}: kind must be 'command' or 'evidence'")


def _parse_commands(raw: dict[str, Any], *, where: str) -> tuple[AcceptanceCommand, ...]:
    commands: list[AcceptanceCommand] = []
    for index, item in enumerate(_as_dict_list(raw, "commands", where)):
        item_where = f"{where}.commands[{index}]"
        _check_keys(
            item,
            required=("label", "argv"),
            optional=("timeout_seconds",),
            where=item_where,
        )
        argv = _as_str_list(item, "argv", item_where)
        if not argv:
            raise ArtifactError(f"{item_where}: argv must not be empty")
        for token in argv:
            if token.startswith("{") and token != PYTHON_PLACEHOLDER:
                raise ArtifactError(
                    f"{item_where}: unsupported substitution token {token!r} "
                    f"(only {PYTHON_PLACEHOLDER} is allowed)"
                )
            if any(char in token for char in ("\n", "\r", "\x00")):
                raise ArtifactError(f"{item_where}: argv token contains a control character")
        commands.append(
            AcceptanceCommand(
                label=_as_str(item, "label", item_where),
                argv=argv,
                timeout_seconds=_as_int(
                    item,
                    "timeout_seconds",
                    item_where,
                    default=DEFAULT_TIMEOUT_SECONDS,
                    low=MIN_TIMEOUT_SECONDS,
                    high=MAX_TIMEOUT_SECONDS,
                ),
            )
        )
    return tuple(commands)


def _parse_evidence(raw: Any, *, where: str) -> EvidenceCheck:
    if not isinstance(raw, dict):
        raise ArtifactError(f"{where}: must be an object")
    _check_keys(
        raw,
        required=("path", "required_headings"),
        optional=("min_words_per_section", "placeholders", "fields", "blocks"),
        where=where,
    )
    path = check_relpath(_as_str(raw, "path", where), what=f"{where}.path")
    headings = _as_str_list(raw, "required_headings", where)
    if not headings:
        raise ArtifactError(f"{where}: required_headings must not be empty")
    for heading in headings:
        if not heading.startswith("#"):
            raise ArtifactError(f"{where}: heading {heading!r} must start with '#'")
    blocks: list[EvidenceBlock] = []
    for index, block_raw in enumerate(raw.get("blocks", []) or []):
        block_where = f"{where}.blocks[{index}]"
        if not isinstance(block_raw, dict):
            raise ArtifactError(f"{block_where}: must be an object")
        _check_keys(
            block_raw,
            required=("heading_prefix", "min_count"),
            optional=("fields",),
            where=block_where,
        )
        blocks.append(
            EvidenceBlock(
                heading_prefix=_as_str(block_raw, "heading_prefix", block_where),
                min_count=_as_int(block_raw, "min_count", block_where, default=1, low=1, high=20),
                fields=_parse_fields(block_raw, where=block_where),
            )
        )
    return EvidenceCheck(
        path=path,
        required_headings=headings,
        min_words_per_section=_as_int(
            raw, "min_words_per_section", where, default=12, low=1, high=500
        ),
        placeholders=_as_str_list(
            raw, "placeholders", where, default=("TODO", "TBD", "<fill in>", "PLACEHOLDER")
        ),
        fields=_parse_fields(raw, where=where),
        blocks=tuple(blocks),
    )


def _parse_fields(raw: dict[str, Any], *, where: str) -> tuple[EvidenceField, ...]:
    fields: list[EvidenceField] = []
    for index, item in enumerate(raw.get("fields", []) or []):
        field_where = f"{where}.fields[{index}]"
        if not isinstance(item, dict):
            raise ArtifactError(f"{field_where}: must be an object")
        _check_keys(
            item,
            required=("label",),
            optional=("min_chars", "must_contain_any"),
            where=field_where,
        )
        fields.append(
            EvidenceField(
                label=_as_str(item, "label", field_where),
                min_chars=_as_int(item, "min_chars", field_where, default=10, low=1, high=2000),
                must_contain_any=_as_str_list(item, "must_contain_any", field_where),
            )
        )
    return tuple(fields)


# ---------------------------------------------------------------------------
# Catalogue
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Catalogue:
    scenario_ids: tuple[str, ...]
    manifests: dict[str, Manifest]

    def require(self, scenario_id: str) -> Manifest:
        manifest = self.manifests.get(scenario_id)
        if manifest is None:
            known = ", ".join(self.scenario_ids)
            raise WorkshopError(
                f"unknown scenario id {scenario_id!r}",
                hint=f"Known scenarios: {known}",
            )
        return manifest


def load_catalogue(root: Path) -> Catalogue:
    data = read_json(root / CATALOGUE_PATH, max_bytes=MAX_MANIFEST_BYTES, what="scenario catalogue")
    where = str(CATALOGUE_PATH)
    _check_keys(
        data,
        required=("schema_version", "scenarios"),
        optional=("description",),
        where=where,
    )
    version = _as_int(
        data,
        "schema_version",
        where,
        default=0,
        low=MANIFEST_SCHEMA_VERSION,
        high=MANIFEST_SCHEMA_VERSION,
    )
    if version != MANIFEST_SCHEMA_VERSION:
        raise ArtifactError(f"{where}: unsupported schema_version {version}")
    scenario_ids = _as_str_list(data, "scenarios", where)
    if not scenario_ids:
        raise ArtifactError(f"{where}: scenarios must not be empty")
    if len(set(scenario_ids)) != len(scenario_ids):
        raise ArtifactError(f"{where}: duplicate scenario ids in catalogue")
    manifests: dict[str, Manifest] = {}
    for scenario_id in scenario_ids:
        check_relpath(scenario_id, what=f"{where}.scenarios")
        if "/" in scenario_id:
            raise ArtifactError(f"{where}: scenario id {scenario_id!r} must not contain '/'")
        manifest_rel = SCENARIO_ROOT / scenario_id / MANIFEST_NAME
        manifest_path = resolve_under_root(root, manifest_rel, what=f"manifest for {scenario_id}")
        raw = read_json(
            manifest_path, max_bytes=MAX_MANIFEST_BYTES, what=f"manifest for {scenario_id}"
        )
        manifests[scenario_id] = parse_manifest(
            raw, expected_id=scenario_id, where=str(manifest_rel)
        )
    return Catalogue(scenario_ids=scenario_ids, manifests=manifests)


def validate_scenario_artifacts(root: Path, manifest: Manifest) -> None:
    """Check every declared artifact exists before anything is mutated."""
    scenario_dir = resolve_under_root(
        root, manifest.directory, what=f"scenario directory for {manifest.scenario_id}"
    )
    if not scenario_dir.is_dir():
        raise ArtifactError(f"scenario directory is missing: {manifest.directory}")
    checks: list[PurePosixPath] = [manifest.acceptance_doc, *manifest.required_artifacts]
    for rel in checks:
        path = resolve_under_root(root, rel, what=f"required artifact {rel}")
        if not path.exists():
            raise ArtifactError(
                f"required artifact is missing: {rel}",
                hint="Restore a clean checkout of workshop/ and try again.",
            )
    for item in manifest.stage:
        payload = resolve_under_root(root, item.payload, what=f"payload {item.payload}")
        if not payload.is_file():
            raise ArtifactError(f"staged payload is missing: {item.payload}")
        size = payload.stat().st_size
        if size > MAX_PAYLOAD_BYTES:
            raise ArtifactError(
                f"staged payload exceeds the {MAX_PAYLOAD_BYTES} byte limit: {item.payload}"
            )
        try:
            read_bytes_checked(payload, what=item.payload.as_posix()).decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ArtifactError(
                f"staged payload is not valid UTF-8: {item.payload} ({exc.reason})"
            ) from exc
    fallback_dir = resolve_under_root(
        root, manifest.fallback, what=f"fallback for {manifest.scenario_id}"
    )
    if not fallback_dir.is_dir():
        raise ArtifactError(f"fallback directory is missing: {manifest.fallback}")


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class TargetRecord:
    path: str
    existed_before: bool
    pre_sha256: str | None
    pre_mode: str | None
    backup: str | None
    staged_sha256: str | None = None
    staged_mode: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "existed_before": self.existed_before,
            "pre_sha256": self.pre_sha256,
            "pre_mode": self.pre_mode,
            "backup": self.backup,
            "staged_sha256": self.staged_sha256,
            "staged_mode": self.staged_mode,
        }

    @staticmethod
    def from_json(raw: Any, where: str, scenario_id: str) -> TargetRecord:
        if not isinstance(raw, dict):
            raise ArtifactError(f"{where}: target record must be an object")
        _check_keys(
            raw,
            required=("path", "existed_before", "pre_sha256", "pre_mode", "backup"),
            optional=("staged_sha256", "staged_mode"),
            where=where,
        )
        existed = raw["existed_before"]
        if not isinstance(existed, bool):
            raise ArtifactError(f"{where}: existed_before must be a boolean")
        path = _as_str(raw, "path", where)
        check_confined(path, parent=work_dir_rel(scenario_id), what=f"{where}.path")
        backup = _opt_str(raw, "backup", where)
        if backup is not None:
            check_confined(backup, parent=backup_dir_rel(scenario_id), what=f"{where}.backup")
        pre_sha256 = _opt_str(raw, "pre_sha256", where)
        pre_mode = _opt_str(raw, "pre_mode", where)
        staged_sha256 = _opt_str(raw, "staged_sha256", where)
        staged_mode = _opt_str(raw, "staged_mode", where)
        for value, label in ((pre_sha256, "pre_sha256"), (staged_sha256, "staged_sha256")):
            if value is not None:
                check_sha256(value, what=f"{where}.{label}")
        for value, label in ((pre_mode, "pre_mode"), (staged_mode, "staged_mode")):
            if value is not None:
                check_mode_string(value, what=f"{where}.{label}")
        if existed and (backup is None or pre_sha256 is None or pre_mode is None):
            raise ArtifactError(
                f"{where}: a target that existed before start needs a backup, hash, and mode"
            )
        if not existed and (backup is not None or pre_sha256 is not None or pre_mode is not None):
            raise ArtifactError(
                f"{where}: a target created by start must not carry pre-start details"
            )
        return TargetRecord(
            path=path,
            existed_before=existed,
            pre_sha256=pre_sha256,
            pre_mode=pre_mode,
            backup=backup,
            staged_sha256=staged_sha256,
            staged_mode=staged_mode,
        )


def _opt_str(raw: dict[str, Any], key: str, where: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ArtifactError(f"{where}: key {key!r} must be a non-empty string or null")
    return value


@dataclass
class ScenarioState:
    scenario_id: str
    phase: str
    started_at: str
    repo_root: str
    git: dict[str, str] | None
    catalogue_sha256: str
    manifest_sha256: str
    targets: list[TargetRecord] = field(default_factory=list)
    created_dirs: list[str] = field(default_factory=list)

    def to_json(self) -> dict[str, Any]:
        return {
            "schema_version": STATE_SCHEMA_VERSION,
            "tool_version": TOOL_VERSION,
            "scenario_id": self.scenario_id,
            "phase": self.phase,
            "started_at": self.started_at,
            "repo_root": self.repo_root,
            "git": self.git,
            "catalogue_sha256": self.catalogue_sha256,
            "manifest_sha256": self.manifest_sha256,
            "targets": [target.to_json() for target in self.targets],
            "created_dirs": list(self.created_dirs),
        }

    @staticmethod
    def from_json(raw: dict[str, Any], where: str) -> ScenarioState:
        _check_keys(
            raw,
            required=(
                "schema_version",
                "tool_version",
                "scenario_id",
                "phase",
                "started_at",
                "repo_root",
                "git",
                "catalogue_sha256",
                "manifest_sha256",
                "targets",
                "created_dirs",
            ),
            optional=(),
            where=where,
        )
        version = _as_int(
            raw,
            "schema_version",
            where,
            default=0,
            low=STATE_SCHEMA_VERSION,
            high=STATE_SCHEMA_VERSION,
        )
        if version != STATE_SCHEMA_VERSION:
            raise ArtifactError(f"{where}: unsupported state schema_version {version}")
        _as_str(raw, "tool_version", where)
        scenario_id = check_scenario_id(
            _as_str(raw, "scenario_id", where), what=f"{where}.scenario_id"
        )
        phase = _as_str(raw, "phase", where)
        if phase not in (PHASE_STAGING, PHASE_ACTIVE):
            raise ArtifactError(f"{where}: phase must be 'staging' or 'active'")
        git_raw = raw.get("git")
        git: dict[str, str] | None = None
        if isinstance(git_raw, dict):
            git = {
                str(key)[:32]: str(value)[:128]
                for key, value in git_raw.items()
                if isinstance(value, str) and key in ("commit", "branch")
            }
        elif git_raw is not None:
            raise ArtifactError(f"{where}: git must be an object or null")
        targets_raw = raw.get("targets")
        if not isinstance(targets_raw, list):
            raise ArtifactError(f"{where}: targets must be a list")
        created_raw = raw.get("created_dirs")
        if not isinstance(created_raw, list) or any(
            not isinstance(item, str) for item in created_raw
        ):
            raise ArtifactError(f"{where}: created_dirs must be a list of strings")
        work_dir = work_dir_rel(scenario_id)
        created_dirs: list[str] = []
        for index, item in enumerate(created_raw):
            check_confined(
                str(item),
                parent=work_dir,
                what=f"{where}.created_dirs[{index}]",
                allow_parent_itself=True,
            )
            if str(item) in created_dirs:
                raise ArtifactError(f"{where}.created_dirs[{index}]: duplicate entry")
            created_dirs.append(str(item))
        targets = [
            TargetRecord.from_json(item, f"{where}.targets[{index}]", scenario_id)
            for index, item in enumerate(targets_raw)
        ]
        seen_paths: set[str] = set()
        seen_backups: set[str] = set()
        for record in targets:
            if record.path in seen_paths:
                raise ArtifactError(f"{where}: duplicate target path {record.path}")
            seen_paths.add(record.path)
            if record.backup is not None:
                if record.backup in seen_backups:
                    raise ArtifactError(f"{where}: duplicate backup path {record.backup}")
                seen_backups.add(record.backup)
        return ScenarioState(
            scenario_id=scenario_id,
            phase=phase,
            started_at=check_utc_timestamp(
                _as_str(raw, "started_at", where), what=f"{where}.started_at"
            ),
            repo_root=_as_str(raw, "repo_root", where),
            git=git,
            catalogue_sha256=check_sha256(
                _as_str(raw, "catalogue_sha256", where), what=f"{where}.catalogue_sha256"
            ),
            manifest_sha256=check_sha256(
                _as_str(raw, "manifest_sha256", where), what=f"{where}.manifest_sha256"
            ),
            targets=targets,
            created_dirs=created_dirs,
        )


def state_dir(root: Path) -> Path:
    """The runtime state directory, refusing a symlinked or replaced path."""
    return resolve_under_root(root, PurePosixPath(STATE_DIR_NAME), what="state directory")


def state_file(root: Path) -> Path:
    return resolve_under_root(
        root, PurePosixPath(STATE_DIR_NAME) / STATE_FILE_NAME, what="state file"
    )


def load_state(root: Path) -> ScenarioState | None:
    path = state_file(root)
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise ArtifactError(
            f"cannot inspect the scenario state file: {exc.strerror or exc}",
            hint=f"Check permissions on {STATE_DIR_NAME}/ before trying again.",
        ) from exc
    if not stat.S_ISREG(mode):
        raise ArtifactError(
            f"{STATE_DIR_NAME}/{STATE_FILE_NAME} is not a regular file",
            hint=(
                f"Inspect {STATE_DIR_NAME}/{BACKUP_DIR_NAME}/ for your pre-start files, "
                "then replace the state path with the original state file."
            ),
        )
    try:
        raw = read_json(path, max_bytes=MAX_STATE_BYTES, what="scenario state")
    except ArtifactError as exc:
        raise ArtifactError(
            f"{exc.message}",
            hint=(
                f"The state file {STATE_DIR_NAME}/{STATE_FILE_NAME} is unreadable. "
                f"Inspect {STATE_DIR_NAME}/{BACKUP_DIR_NAME}/ for your pre-start files, "
                "then remove the state directory once you have restored them."
            ),
        ) from exc
    state = ScenarioState.from_json(raw, where="scenario state")
    if state.repo_root != str(root):
        raise ArtifactError(
            "scenario state belongs to a different checkout: "
            f"recorded {state.repo_root!r}, current {str(root)!r}",
            hint=(
                "Run reset in the checkout the scenario was started in. If that checkout "
                f"is gone, restore your files from {STATE_DIR_NAME}/{BACKUP_DIR_NAME}/ by "
                f"hand and then delete {STATE_DIR_NAME}/."
            ),
        )
    return state


def save_state(root: Path, state: ScenarioState) -> None:
    payload = json.dumps(state.to_json(), indent=2, sort_keys=True).encode("utf-8") + b"\n"
    atomic_write_bytes(state_file(root), payload, 0o600)


def clear_state(root: Path) -> None:
    path = state_file(root)
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        raise WorkshopError(
            f"cannot clear the scenario state file: {exc.strerror or exc}",
            hint=f"Delete {STATE_DIR_NAME}/{STATE_FILE_NAME} by hand once the cause is fixed.",
        ) from exc
    if path.parent.is_dir():
        _fsync_dir(path.parent)


def git_identity(root: Path) -> dict[str, str] | None:
    """Best-effort repository identity; absent git is not an error."""
    git_exe = shutil.which("git")
    if git_exe is None or not (root / ".git").exists():
        return None
    identity: dict[str, str] = {}
    queries = (
        ("commit", ["rev-parse", "HEAD"]),
        ("branch", ["rev-parse", "--abbrev-ref", "HEAD"]),
    )
    for key, args in queries:
        try:
            completed = subprocess.run(  # noqa: S603 - fixed argv, no shell
                [git_exe, "-C", str(root), *args],
                capture_output=True,
                text=True,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return identity or None
        if completed.returncode == 0:
            identity[key] = completed.stdout.strip()
    return identity or None


# ---------------------------------------------------------------------------
# Staging / restoring
# ---------------------------------------------------------------------------


def _backup_rel(scenario_id: str, index: int, target: PurePosixPath) -> str:
    flat = target.name
    return f"{backup_dir_rel(scenario_id).as_posix()}/{index:02d}__{flat}"


def target_path_of(root: Path, record: TargetRecord, scenario_id: str) -> Path:
    """Resolve a recorded target, re-validating its confinement every time."""
    rel = check_confined(
        record.path, parent=work_dir_rel(scenario_id), what=f"state target {record.path}"
    )
    return resolve_under_root(root, rel, what=f"state target {record.path}")


def backup_path_of(root: Path, record: TargetRecord, scenario_id: str) -> Path:
    if record.backup is None:  # pragma: no cover - guarded by state validation
        raise WorkshopError(f"state for {record.path} is missing its backup location")
    rel = check_confined(
        record.backup, parent=backup_dir_rel(scenario_id), what=f"state backup {record.backup}"
    )
    return resolve_under_root(root, rel, what=f"state backup {record.backup}")


def created_dir_path_of(root: Path, rel: str, scenario_id: str) -> Path:
    parsed = check_confined(
        rel,
        parent=work_dir_rel(scenario_id),
        what=f"state created_dir {rel}",
        allow_parent_itself=True,
    )
    return resolve_under_root(root, parsed, what=f"state created_dir {rel}")


def _require_regular_file(path: Path, rel: str) -> None:
    """Refuse to treat a symlink or directory as a staged file."""
    if _is_symlink(path):
        raise WorkshopError(
            f"{rel} is a symlink; refusing to read, copy, or remove it",
            hint="Remove or replace it by hand after checking where it points.",
        )
    if path.is_dir():
        raise WorkshopError(
            f"{rel} is a directory where a file is expected",
            hint="Move it aside by hand, then run the command again.",
        )


def plan_targets(root: Path, manifest: Manifest) -> tuple[list[TargetRecord], list[str]]:
    records: list[TargetRecord] = []
    created_dirs: list[str] = []
    work_dir = work_dir_rel(manifest.scenario_id)
    for index, item in enumerate(manifest.stage):
        target_path = resolve_under_root(root, item.target, what=f"target {item.target}")
        _require_regular_file(target_path, item.target.as_posix())
        existed = target_path.is_file()
        record = TargetRecord(
            path=item.target.as_posix(),
            existed_before=existed,
            pre_sha256=sha256_file(target_path) if existed else None,
            pre_mode=f"{file_mode(target_path):04o}" if existed else None,
            backup=_backup_rel(manifest.scenario_id, index, item.target) if existed else None,
        )
        records.append(record)
        for parent in _missing_parents(root, item.target, work_dir):
            if parent not in created_dirs:
                created_dirs.append(parent)
    return records, created_dirs


def _missing_parents(root: Path, target: PurePosixPath, work_dir: PurePosixPath) -> list[str]:
    """Directories start would have to create, confined to the scenario work dir."""
    missing: list[str] = []
    current = PurePosixPath(target.parent)
    while current == work_dir or work_dir in current.parents:
        if not (root / current).exists():
            missing.append(current.as_posix())
        current = current.parent
    return list(reversed(missing))


def prepare_backups(root: Path, state: ScenarioState) -> None:
    """Back up and verify every pre-existing target before anything is mutated."""
    for record in state.targets:
        if not record.existed_before or record.pre_sha256 is None:
            continue
        target_path = target_path_of(root, record, state.scenario_id)
        _require_regular_file(target_path, record.path)
        backup_path = backup_path_of(root, record, state.scenario_id)
        data = read_bytes_checked(target_path, what=record.path)
        if sha256_bytes(data) != record.pre_sha256:
            raise WorkshopError(
                f"{record.path} changed while start was preparing; nothing was staged",
                hint="Re-run start once the file is stable.",
            )
        atomic_write_bytes(backup_path, data, 0o600)
        if sha256_file(backup_path) != record.pre_sha256:
            raise WorkshopError(f"backup verification failed for {record.path}")


def apply_payloads(root: Path, manifest: Manifest, state: ScenarioState) -> None:
    """Write the staged payloads.  Backups must already exist and be verified."""
    for item, record in zip(manifest.stage, state.targets, strict=True):
        target_path = target_path_of(root, record, state.scenario_id)
        payload_path = resolve_under_root(root, item.payload, what=f"payload {item.payload}")
        data = read_bytes_checked(payload_path, what=item.payload.as_posix())
        atomic_write_bytes(target_path, data, item.mode)
        record.staged_sha256 = sha256_bytes(data)
        record.staged_mode = f"{item.mode:04o}"


def restore_targets(root: Path, state: ScenarioState) -> list[str]:
    """Restore exact pre-start bytes and modes.  Returns human-readable notes."""
    notes: list[str] = []
    for record in state.targets:
        target_path = target_path_of(root, record, state.scenario_id)
        if _is_symlink(target_path):
            raise WorkshopError(
                f"{record.path} is now a symlink; refusing to restore through it",
                hint="Remove it by hand after checking where it points, then reset again.",
            )
        if target_path.is_dir():
            raise WorkshopError(
                f"{record.path} is now a directory; refusing to restore over it",
                hint="Move it aside by hand, then reset again. Your state is untouched.",
            )
        if record.existed_before:
            notes.append(_restore_existing(root, state, record, target_path))
        else:
            if target_path.exists():
                _unlink_checked(target_path, record.path)
            notes.append(f"removed   {record.path}")
    notes.extend(_remove_created_dirs(root, state))
    _discard_backups(root, state)
    return notes


def _restore_existing(
    root: Path, state: ScenarioState, record: TargetRecord, target_path: Path
) -> str:
    if record.pre_sha256 is None or record.pre_mode is None:  # pragma: no cover - validated
        raise WorkshopError(f"state for {record.path} is incomplete; cannot restore safely")
    backup_path = backup_path_of(root, record, state.scenario_id)
    if backup_path.is_file() and not _is_symlink(backup_path):
        data = read_bytes_checked(backup_path, what=record.backup or record.path)
        if sha256_bytes(data) != record.pre_sha256:
            raise WorkshopError(
                f"backup for {record.path} does not match its recorded hash",
                hint="Refusing to restore a modified backup; restore from version control.",
            )
    elif target_path.is_file() and sha256_file(target_path) == record.pre_sha256:
        # Nothing was staged over this target (an interrupted start), so the
        # file on disk is already the pre-start content.
        data = read_bytes_checked(target_path, what=record.path)
    else:
        raise WorkshopError(
            f"backup for {record.path} is missing: {record.backup}",
            hint="Restore the file from version control; the scenario state was left in place.",
        )
    atomic_write_bytes(target_path, data, int(record.pre_mode, 8))
    if sha256_file(target_path) != record.pre_sha256:
        raise WorkshopError(f"restore verification failed for {record.path}")
    return f"restored  {record.path}"


def _unlink_checked(path: Path, rel: str) -> None:
    try:
        path.unlink()
    except OSError as exc:
        raise WorkshopError(
            f"cannot remove {rel}: {exc.strerror or exc}",
            hint="Remove it by hand, then reset again. The scenario state was left in place.",
        ) from exc


def _remove_created_dirs(root: Path, state: ScenarioState) -> list[str]:
    """Remove exactly the directories start created, and nothing else."""
    notes: list[str] = []
    for rel in sorted(state.created_dirs, key=len, reverse=True):
        directory = created_dir_path_of(root, rel, state.scenario_id)
        if _is_symlink(directory):
            raise WorkshopError(
                f"{rel} is a symlink; refusing to remove it",
                hint="Remove it by hand after checking where it points.",
            )
        if not directory.is_dir():
            continue
        try:
            shutil.rmtree(directory)
        except OSError as exc:
            raise WorkshopError(
                f"cannot remove {rel}/: {exc.strerror or exc}",
                hint="Remove it by hand, then reset again. Your archive is already written.",
            ) from exc
        notes.append(f"removed   {rel}/")
    return notes


def _discard_backups(root: Path, state: ScenarioState) -> None:
    backups = resolve_under_root(root, backup_dir_rel(state.scenario_id), what="backup directory")
    if not backups.is_dir() or _is_symlink(backups):
        return
    try:
        shutil.rmtree(backups)
    except OSError as exc:
        raise WorkshopError(
            f"cannot clear the backup directory: {exc.strerror or exc}",
            hint=f"Delete {backup_dir_rel(state.scenario_id)}/ by hand.",
        ) from exc


def collect_attempt_files(root: Path, state: ScenarioState) -> list[PurePosixPath]:
    """Everything under the scenario's created directories plus changed targets.

    Files that are still byte-identical to what ``start`` staged are skipped:
    the pristine payload is already in the repository.
    """
    staged_state = {
        record.path: target_status(root, record, state.scenario_id) for record in state.targets
    }
    selected: list[PurePosixPath] = []
    for rel in state.created_dirs:
        directory = created_dir_path_of(root, rel, state.scenario_id)
        if not directory.is_dir() or _is_symlink(directory):
            continue
        for path in sorted(directory.rglob("*")):
            if _is_symlink(path) or not path.is_file():
                continue
            relative = PurePosixPath(path.relative_to(root).as_posix())
            if staged_state.get(relative.as_posix()) == "unchanged":
                continue
            selected.append(relative)
    known = {item.as_posix() for item in selected}
    for record in state.targets:
        if staged_state.get(record.path) not in ("participant-modified", "mode-changed"):
            continue
        if record.path in known:
            continue
        target_path = target_path_of(root, record, state.scenario_id)
        if target_path.is_file() and not _is_symlink(target_path):
            selected.append(PurePosixPath(record.path))
    return sorted(selected, key=lambda item: item.as_posix())


def archive_attempt(root: Path, state: ScenarioState) -> str | None:
    """Copy participant work into an ignored, timestamped archive."""
    files = collect_attempt_files(root, state)
    if not files:
        return None
    if len(files) > MAX_ARCHIVE_FILES:
        raise WorkshopError(
            f"refusing to archive {len(files)} files (limit {MAX_ARCHIVE_FILES})",
            hint=(
                "Move what you want to keep out of the scenario work directory, delete the "
                "rest, then reset again. Nothing has been changed."
            ),
        )
    total = 0
    for rel in files:
        path = resolve_under_root(root, rel, what=f"attempt file {rel}")
        size = path.stat().st_size
        if size > MAX_ARCHIVE_FILE_BYTES:
            raise WorkshopError(
                f"refusing to archive {rel}: {size} bytes exceeds the "
                f"{MAX_ARCHIVE_FILE_BYTES} byte per-file limit",
                hint="Move that file out of the work directory, then reset again.",
            )
        total += size
    if total > MAX_ARCHIVE_TOTAL_BYTES:
        raise WorkshopError(
            f"refusing to archive {total} bytes (limit {MAX_ARCHIVE_TOTAL_BYTES})",
            hint="Move the large files out of the work directory, then reset again.",
        )
    archive_dir, archive_rel = _new_archive_dir(root, state.scenario_id)
    for rel in files:
        source = resolve_under_root(root, rel, what=f"attempt file {rel}")
        destination = archive_dir / Path(*rel.parts)
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        except OSError as exc:
            raise WorkshopError(
                f"cannot archive {rel}: {exc.strerror or exc}",
                hint="Nothing was restored; fix the cause and reset again.",
            ) from exc
    return archive_rel


def _new_archive_dir(root: Path, scenario_id: str) -> tuple[Path, str]:
    """Create a fresh archive directory, tolerating same-second resets."""
    base = resolve_under_root(root, attempt_dir_rel(scenario_id), what="attempt archive")
    stamp = utc_compact_stamp()
    for attempt in range(1, 100):
        candidate = base / f"{stamp}-{attempt:02d}"
        try:
            candidate.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        except OSError as exc:
            raise WorkshopError(
                f"cannot create the attempt archive: {exc.strerror or exc}"
            ) from exc
        return candidate, f"{attempt_dir_rel(scenario_id).as_posix()}/{stamp}-{attempt:02d}"
    raise WorkshopError(
        "cannot create the attempt archive: too many archives in the same second",
        hint=f"Clean up {attempt_dir_rel(scenario_id)}/ and reset again.",
    )


def target_status(root: Path, record: TargetRecord, scenario_id: str) -> str:
    try:
        path = target_path_of(root, record, scenario_id)
    except ArtifactError:
        # Reporting only: never read or write through an unsafe path.
        raw = root / PurePosixPath(record.path)
        return "replaced-by-symlink" if _is_symlink(raw) else "unsafe-path"
    if path.is_dir():
        return "replaced-by-directory"
    if not path.is_file():
        return "missing"
    if record.staged_sha256 is None:
        return "unknown"
    if sha256_file(path) != record.staged_sha256:
        return "participant-modified"
    if record.staged_mode is not None and f"{file_mode(path):04o}" != record.staged_mode:
        return "mode-changed"
    return "unchanged"


# ---------------------------------------------------------------------------
# Output sanitising
# ---------------------------------------------------------------------------


def sanitize_output(text: str, root: Path) -> str:
    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = cleaned.replace(str(root.resolve()), "<repo>").replace(str(root), "<repo>")
    home = str(Path.home())
    if home and home != "/":
        cleaned = cleaned.replace(home, "<home>")
    out_lines: list[str] = []
    for line in cleaned.split("\n"):
        out_lines.append(_redact_line(_strip_escapes(line)))
    return "\n".join(out_lines)


def _strip_escapes(line: str) -> str:
    return "".join(char for char in line if char == "\t" or char >= " ")


def _redact_line(line: str) -> str:
    """Redact credential shapes anywhere in a line, not only whole tokens."""
    redacted = line
    for pattern in REDACT_PATTERNS:
        redacted = pattern.sub(_replace_secret, redacted)
    return redacted


def _replace_secret(match: re.Match[str]) -> str:
    groups = match.groupdict()
    key = groups.get("key")
    if key is None:
        return REDACTED
    return f"{key}{groups.get('sep', '=')}{REDACTED}"


def truncate_output(text: str) -> tuple[str, bool]:
    lines = [line for line in text.split("\n")]
    truncated = False
    if len(lines) > MAX_OUTPUT_LINES:
        lines = lines[:MAX_OUTPUT_LINES]
        truncated = True
    joined = "\n".join(lines)
    if len(joined) > MAX_OUTPUT_CHARS:
        joined = joined[:MAX_OUTPUT_CHARS]
        truncated = True
    return joined, truncated


# ---------------------------------------------------------------------------
# Evidence checking
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CheckResult:
    label: str
    passed: bool
    detail: str


def run_evidence_check(root: Path, check: EvidenceCheck) -> list[CheckResult]:
    results: list[CheckResult] = []
    path = resolve_under_root(root, check.path, what=f"evidence file {check.path}")
    if not path.is_file():
        return [
            CheckResult(
                label=f"evidence file {check.path} exists",
                passed=False,
                detail="file not found - run start again or create it from the template",
            )
        ]
    size = path.stat().st_size
    if size > MAX_EVIDENCE_BYTES:
        return [
            CheckResult(
                label=f"evidence file {check.path} is within size limits",
                passed=False,
                detail=f"file is {size} bytes; limit is {MAX_EVIDENCE_BYTES}",
            )
        ]
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        return [
            CheckResult(
                label=f"evidence file {check.path} is valid UTF-8",
                passed=False,
                detail=f"invalid UTF-8 at byte {exc.start}",
            )
        ]
    lines = text.split("\n")
    results.append(
        CheckResult(label=f"evidence file {check.path} is readable", passed=True, detail="ok")
    )
    results.append(_judge_document_placeholders(text, check))
    for heading in check.required_headings:
        body = _section_body(lines, heading)
        if body is None:
            results.append(
                CheckResult(label=f"section {heading!r}", passed=False, detail="heading not found")
            )
            continue
        results.append(_judge_body(heading, body, check))
    for spec in check.fields:
        results.append(_judge_field(lines, spec, check.placeholders))
    for block in check.blocks:
        results.extend(_judge_blocks(lines, block, check))
    return results


def _judge_document_placeholders(text: str, check: EvidenceCheck) -> CheckResult:
    """One whole-document sweep, so a placeholder outside a checked section fails too."""
    lowered = text.lower()
    found = [placeholder for placeholder in check.placeholders if placeholder.lower() in lowered]
    if found:
        return CheckResult(
            label="no template placeholder is left anywhere in the file",
            passed=False,
            detail=f"still contains {', '.join(repr(item) for item in found)}",
        )
    return CheckResult(
        label="no template placeholder is left anywhere in the file",
        passed=True,
        detail="none found",
    )


def _heading_level(line: str) -> int:
    stripped = line.lstrip()
    level = 0
    while level < len(stripped) and stripped[level] == "#":
        level += 1
    return level if level and stripped[level : level + 1] == " " else 0


def _section_body(lines: Sequence[str], heading: str) -> list[str] | None:
    target_level = _heading_level(heading)
    wanted = heading.strip()
    for index, line in enumerate(lines):
        if line.strip() != wanted:
            continue
        body: list[str] = []
        for follower in lines[index + 1 :]:
            level = _heading_level(follower)
            if level and level <= target_level:
                break
            body.append(follower)
        return body
    return None


def _judge_body(heading: str, body: Sequence[str], check: EvidenceCheck) -> CheckResult:
    text = "\n".join(body)
    lowered = text.lower()
    for placeholder in check.placeholders:
        if placeholder.lower() in lowered:
            return CheckResult(
                label=f"section {heading!r}",
                passed=False,
                detail=f"still contains the template placeholder {placeholder!r}",
            )
    words = len([word for word in text.split() if any(ch.isalnum() for ch in word)])
    if words < check.min_words_per_section:
        return CheckResult(
            label=f"section {heading!r}",
            passed=False,
            detail=f"{words} words; at least {check.min_words_per_section} required",
        )
    return CheckResult(label=f"section {heading!r}", passed=True, detail=f"{words} words")


def _field_lines(lines: Sequence[str], label: str) -> list[str]:
    found: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith(label):
            found.append(stripped[len(label) :].strip())
    return found


def _judge_field(
    lines: Sequence[str], spec: EvidenceField, placeholders: Sequence[str] = ()
) -> CheckResult:
    values = _field_lines(lines, spec.label)
    if not values:
        return CheckResult(label=f"field {spec.label!r}", passed=False, detail="line not found")
    best = max(values, key=len)
    lowered_best = best.lower()
    for placeholder in placeholders:
        if placeholder.lower() in lowered_best:
            return CheckResult(
                label=f"field {spec.label!r}",
                passed=False,
                detail=f"still contains the template placeholder {placeholder!r}",
            )
    if len(best) < spec.min_chars:
        return CheckResult(
            label=f"field {spec.label!r}",
            passed=False,
            detail=f"{len(best)} characters of content; at least {spec.min_chars} required",
        )
    if spec.must_contain_any:
        lowered = best.lower()
        if not any(option.lower() in lowered for option in spec.must_contain_any):
            return CheckResult(
                label=f"field {spec.label!r}",
                passed=False,
                detail=f"must mention one of: {', '.join(spec.must_contain_any)}",
            )
    return CheckResult(label=f"field {spec.label!r}", passed=True, detail="present")


def _judge_blocks(
    lines: Sequence[str], block: EvidenceBlock, check: EvidenceCheck
) -> list[CheckResult]:
    starts = [
        index for index, line in enumerate(lines) if line.strip().startswith(block.heading_prefix)
    ]
    label = f"blocks starting with {block.heading_prefix!r}"
    if len(starts) < block.min_count:
        return [
            CheckResult(
                label=label,
                passed=False,
                detail=f"found {len(starts)}; at least {block.min_count} required",
            )
        ]
    results = [CheckResult(label=label, passed=True, detail=f"found {len(starts)}")]
    level = _heading_level(block.heading_prefix)
    for order, start in enumerate(starts, start=1):
        body: list[str] = []
        for follower in lines[start + 1 :]:
            follower_level = _heading_level(follower)
            if follower_level and follower_level <= level:
                break
            body.append(follower)
        heading_text = lines[start].strip()
        results.append(_judge_body(f"{heading_text} (block {order})", body, check))
        for spec in block.fields:
            result = _judge_field(body, spec, check.placeholders)
            results.append(
                CheckResult(
                    label=f"block {order}: {result.label}",
                    passed=result.passed,
                    detail=result.detail,
                )
            )
    return results


# ---------------------------------------------------------------------------
# Acceptance commands
# ---------------------------------------------------------------------------


def build_argv(command: AcceptanceCommand) -> list[str]:
    return [sys.executable if token == PYTHON_PLACEHOLDER else token for token in command.argv]


def acceptance_environment() -> dict[str, str]:
    """A minimal environment for acceptance commands.

    The caller's environment is deliberately not inherited: it routinely holds
    tokens and cloud credentials, and an acceptance command runs participant
    code. Only what an interpreter and a test runner need is passed through.
    """
    env: dict[str, str] = {key: os.environ[key] for key in INHERITED_ENV_KEYS if key in os.environ}
    path_parts: list[str] = [str(Path(sys.executable).resolve().parent)]
    if os.name == "nt":
        system_root = os.environ.get("SystemRoot") or os.environ.get("SYSTEMROOT")
        if system_root:
            path_parts.extend([f"{system_root}\\System32", f"{system_root}\\System32\\Wbem"])
    for part in os.defpath.split(os.pathsep):
        if part:
            path_parts.append(part)
    ordered: list[str] = []
    for part in path_parts:
        if part not in ordered:
            ordered.append(part)
    env["PATH"] = os.pathsep.join(ordered)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONNOUSERSITE"] = "1"
    return env


def run_acceptance_command(root: Path, command: AcceptanceCommand) -> tuple[CheckResult, str]:
    argv = build_argv(command)
    env = acceptance_environment()
    try:
        completed = subprocess.run(  # noqa: S603 - validated argv list, shell is never used
            argv,
            cwd=str(root),
            env=env,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=command.timeout_seconds,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (
            CheckResult(
                label=command.label,
                passed=False,
                detail=f"TIMEOUT after {command.timeout_seconds}s",
            ),
            "",
        )
    except FileNotFoundError as exc:
        raise PrerequisiteError(
            f"acceptance command executable not found: {argv[0]}",
            hint=f"Install the missing tool, then re-run: {command.display()} ({exc.strerror})",
        ) from exc
    except OSError as exc:
        raise WorkshopError(f"failed to run acceptance command: {exc}") from exc
    output = sanitize_output(f"{completed.stdout}{completed.stderr}", root)
    passed = completed.returncode == 0
    detail = "exit 0" if passed else f"exit {completed.returncode}"
    return CheckResult(label=command.label, passed=passed, detail=detail), output


# ---------------------------------------------------------------------------
# Printing helpers
# ---------------------------------------------------------------------------


def out(message: str = "") -> None:
    print(message)


def print_block(text: str) -> None:
    body, truncated = truncate_output(text.rstrip("\n"))
    if not body.strip():
        out("  | (no output)")
        return
    for line in body.split("\n"):
        out(f"  | {line}")
    if truncated:
        out(f"  | ... output truncated at {MAX_OUTPUT_LINES} lines / {MAX_OUTPUT_CHARS} chars")


def command_hint(*parts: str) -> str:
    return " ".join(["python", "scripts/workshop.py", *parts])


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_list(root: Path, _args: argparse.Namespace) -> int:
    catalogue = load_catalogue(root)
    state = load_state(root)
    active = state.scenario_id if state else None
    for scenario_id in catalogue.scenario_ids:
        validate_scenario_artifacts(root, catalogue.manifests[scenario_id])
    out(f"QuantCore workshop scenarios ({len(catalogue.scenario_ids)}):")
    out("")
    id_width = max(len(scenario_id) for scenario_id in catalogue.scenario_ids)
    for scenario_id in catalogue.scenario_ids:
        manifest = catalogue.manifests[scenario_id]
        marker = "*" if scenario_id == active else " "
        out(
            f" {marker} {scenario_id.ljust(id_width)}  "
            f"{manifest.kind.ljust(8)}  {manifest.lab.ljust(7)}  {manifest.title}"
        )
    out("")
    if active is None:
        out("Active scenario: none")
        out(f"Next: {command_hint('start', catalogue.scenario_ids[0])}")
    else:
        out(f"Active scenario: {active} (marked with *)")
        out(f"Next: {command_hint('status')}")
    return EXIT_OK


def cmd_start(root: Path, args: argparse.Namespace) -> int:
    scenario_id = str(args.scenario_id)
    catalogue = load_catalogue(root)
    manifest = catalogue.require(scenario_id)
    existing = load_state(root)
    if existing is not None:
        if existing.phase == PHASE_STAGING:
            raise StateConflictError(
                f"a previous start of {existing.scenario_id!r} was interrupted while staging",
                hint=f"Run {command_hint('reset', existing.scenario_id)} to roll it back first.",
            )
        raise StateConflictError(
            f"scenario {existing.scenario_id!r} is already active",
            hint=(
                f"One scenario runs at a time. Finish it, or run "
                f"{command_hint('reset', existing.scenario_id)} first."
            ),
        )
    validate_scenario_artifacts(root, manifest)
    _check_required_imports(manifest)

    records, created_dirs = plan_targets(root, manifest)
    catalogue_hash, manifest_hash = definition_hashes(root, manifest.scenario_id)
    state = ScenarioState(
        scenario_id=manifest.scenario_id,
        phase=PHASE_STAGING,
        started_at=utc_now_iso(),
        repo_root=str(root),
        git=git_identity(root),
        catalogue_sha256=catalogue_hash,
        manifest_sha256=manifest_hash,
        targets=records,
        created_dirs=created_dirs,
    )
    # Recovery state is durable before the first byte is written or copied.
    save_state(root, state)
    try:
        prepare_backups(root, state)
        apply_payloads(root, manifest, state)
    except BaseException as exc:
        try:
            _rollback(root, state)
        except WorkshopError as rollback_error:
            raise WorkshopError(
                f"staging {scenario_id} failed and the rollback did not complete: "
                f"{rollback_error.message}",
                hint=(
                    f"Your pre-start files are in "
                    f"{STATE_DIR_NAME}/{BACKUP_DIR_NAME}/{scenario_id}/. Restore them by "
                    f"hand, then delete {STATE_DIR_NAME}/ before starting another scenario."
                ),
            ) from exc
        raise WorkshopError(
            f"staging {scenario_id} failed and was rolled back: {exc}",
            hint="Your working tree is unchanged. Re-run start once the cause is fixed.",
        ) from exc
    state.phase = PHASE_ACTIVE
    save_state(root, state)

    out(f"Started scenario: {manifest.scenario_id}")
    out(f"Title:            {manifest.title}")
    out(f"Kind:             {manifest.kind} ({manifest.lab})")
    out(f"Started at:       {local_display(state.started_at)}")
    out("")
    out("Staged into your working tree:")
    for item, record in zip(manifest.stage, state.targets, strict=True):
        marker = "modified" if record.existed_before else "created "
        out(f"  {marker}  {record.path}")
        out(f"            {item.description}")
    out("")
    out("Read first:")
    out(f"  {manifest.acceptance_doc}")
    for artifact in manifest.briefing:
        out(f"  {artifact}")
    out("")
    if manifest.kind == KIND_CODE:
        out("Acceptance check (expected to FAIL until you repair it - that is your")
        out("fail-before evidence; capture the output now):")
        for command in manifest.commands:
            out(f"  {command.display()}")
    else:
        evidence = manifest.evidence
        if evidence is not None:
            out("Acceptance evidence file (expected to FAIL until you complete it):")
            out(f"  {evidence.path}")
    out("")
    out(f"Verify: {command_hint('verify', manifest.scenario_id)}")
    out(f"Reset:  {command_hint('reset', manifest.scenario_id)}")
    return EXIT_OK


def _check_required_imports(manifest: Manifest) -> None:
    missing: list[str] = []
    for module in manifest.required_imports:
        try:
            if importlib.util.find_spec(module) is None:
                missing.append(module)
        except (ImportError, ValueError):
            missing.append(module)
    if missing:
        raise PrerequisiteError(
            f"scenario {manifest.scenario_id} needs missing module(s): {', '.join(missing)}",
            hint="Install project dependencies first: python -m pip install -r requirements.txt",
        )


def definition_hashes(root: Path, scenario_id: str) -> tuple[str, str]:
    """Hashes of the catalogue and the scenario manifest, bound into state."""
    catalogue_path = resolve_under_root(root, CATALOGUE_PATH, what="scenario catalogue")
    manifest_path = resolve_under_root(
        root, SCENARIO_ROOT / scenario_id / MANIFEST_NAME, what=f"manifest for {scenario_id}"
    )
    return sha256_file(catalogue_path), sha256_file(manifest_path)


def _check_definition_unchanged(root: Path, state: ScenarioState) -> None:
    """Refuse to run acceptance from a definition edited since ``start``."""
    catalogue_hash, manifest_hash = definition_hashes(root, state.scenario_id)
    changed = []
    if catalogue_hash != state.catalogue_sha256:
        changed.append(str(CATALOGUE_PATH))
    if manifest_hash != state.manifest_sha256:
        changed.append(str(SCENARIO_ROOT / state.scenario_id / MANIFEST_NAME))
    if changed:
        raise ArtifactError(
            f"the scenario definition changed after start: {', '.join(changed)}",
            hint=(
                f"Acceptance must run the checks you started with. Run "
                f"{command_hint('reset', state.scenario_id)} and start again, or restore the "
                "definition from version control."
            ),
        )


def _rollback(root: Path, state: ScenarioState) -> None:
    """Undo a partially staged scenario.  Leaves state in place if it fails."""
    restore_targets(root, state)
    clear_state(root)


def cmd_status(root: Path, _args: argparse.Namespace) -> int:
    state = load_state(root)
    if state is None:
        out("Active scenario: none")
        out("Your checkout is in its baseline state; nothing is staged.")
        out(f"Next: {command_hint('list')}")
        return EXIT_OK
    # Status must survive a broken catalogue: the title is a nicety, the staged
    # file state is the thing a stuck participant actually needs.
    manifest: Manifest | None = None
    catalogue_note: str | None = None
    try:
        manifest = load_catalogue(root).manifests.get(state.scenario_id)
    except WorkshopError as exc:
        catalogue_note = exc.message
    out(f"Active scenario: {state.scenario_id}")
    if manifest is not None:
        out(f"Title:           {manifest.title}")
        out(f"Kind:            {manifest.kind} ({manifest.lab})")
    elif catalogue_note is not None:
        out(f"Title:           unavailable ({catalogue_note})")
    out(f"Started at:      {local_display(state.started_at)}")
    if state.git:
        commit = state.git.get("commit", "unknown")
        branch = state.git.get("branch", "unknown")
        out(f"Repository:      {branch} @ {commit[:12]}")
    if state.phase == PHASE_STAGING:
        out("")
        out("State:           INTERRUPTED while staging.")
        out(f"Next: {command_hint('reset', state.scenario_id)} to roll back safely.")
        return EXIT_OK
    out("")
    out("Staged targets:")
    modified = 0
    missing = 0
    for record in state.targets:
        status = target_status(root, record, state.scenario_id)
        if status in ("participant-modified", "mode-changed"):
            modified += 1
        elif status != "unchanged":
            missing += 1
        out(f"  [{status}] {record.path}")
    out("")
    out(
        f"Summary:         {len(state.targets)} staged, "
        f"{modified} modified by you, {missing} missing or replaced"
    )
    out(f"Next: {command_hint('verify', state.scenario_id)}")
    out(f"Reset: {command_hint('reset', state.scenario_id)}")
    return EXIT_OK


def cmd_resync(root: Path, args: argparse.Namespace) -> int:
    """Print an answer-neutral route around a blocked lab phase."""
    scenario_id = str(args.scenario_id)
    blocked_at = str(args.blocked_at)
    catalogue = load_catalogue(root)
    manifest = catalogue.require(scenario_id)
    state = load_state(root)
    if state is None:
        raise StateConflictError(
            f"scenario {scenario_id!r} is not active",
            hint=f"Start it first: {command_hint('start', scenario_id)}",
        )
    if state.scenario_id != scenario_id:
        raise StateConflictError(
            f"scenario {scenario_id!r} is not the active scenario ({state.scenario_id!r})",
            hint=(
                f"Resync the active one: "
                f"{command_hint('resync', state.scenario_id, '--blocked-at', blocked_at)}"
            ),
        )
    if state.phase != PHASE_ACTIVE:
        raise StateConflictError(
            f"scenario {scenario_id!r} is not fully staged (phase: {state.phase})",
            hint=f"Run {command_hint('reset', scenario_id)} and start again.",
        )

    routes: dict[str, tuple[str, ...]] = {
        BLOCKED_TOOLING: (
            "Stop after two retries or five minutes; do not repair the machine during lab time.",
            f"Open the captured route: {command_hint('fallback', scenario_id)}",
            "Continue with the same evidence question as reader, navigator, or reviewer.",
        ),
        BLOCKED_UNDERSTAND_PLAN: (
            "Write only the observable symptom, the invariant, and one unknown.",
            "Take the next hint level or ask a helper for a five-minute orientation reset.",
            "Choose the Supported lane and continue with the smallest testable claim.",
        ),
        BLOCKED_IMPLEMENT_TEST: (
            "Stop changing code. Keep the incomplete attempt; it is still reviewable evidence.",
            f"Run {command_hint('verify', scenario_id)} once and record the honest result.",
            "Continue to Review and Explain: identify scope, risk, what failed, "
            "and the next safe action.",
        ),
        BLOCKED_REVIEW: (
            "Use the six checks in challenges/reference/evidence.md: scope, invariant, tests, "
            "contracts, non-functional concerns, and explanation.",
            "Document one high-confidence finding with location, evidence, and requested action.",
            "Continue to Explain even if the implementation remains incomplete.",
        ),
        BLOCKED_EXPLAIN: (
            "Use three sentences: what you verified, what you assumed, and what "
            "could still be wrong.",
            "State whether acceptance passed; do not turn an incomplete result "
            "into a success claim.",
            "Name the next safe action and the rollback or reset route.",
        ),
    }

    out(f"Resync route: {scenario_id} ({manifest.lab})")
    out(f"Blocked at:    {blocked_at}")
    out("")
    out("This command does not solve the task, edit files, or weaken acceptance.")
    out("It preserves the remaining learning steps without pretending the blocked step passed.")
    out("")
    for index, instruction in enumerate(routes[blocked_at], start=1):
        out(f"{index}. {instruction}")
    out("")
    out("At the room checkpoint:")
    out(f"  Verify once: {command_hint('verify', scenario_id)}")
    out(f"  Archive and restore: {command_hint('reset', scenario_id)}")
    out("A failing verifier is an honest outcome. Reset archives the attempt before")
    out("restoring the pre-start state, so you can rejoin the next lab on time.")
    return EXIT_OK


def cmd_verify(root: Path, args: argparse.Namespace) -> int:
    scenario_id = str(args.scenario_id)
    catalogue = load_catalogue(root)
    manifest = catalogue.require(scenario_id)
    state = load_state(root)
    if state is None:
        raise StateConflictError(
            f"scenario {scenario_id!r} is not active",
            hint=f"Start it first: {command_hint('start', scenario_id)}",
        )
    if state.scenario_id != scenario_id:
        raise StateConflictError(
            f"scenario {scenario_id!r} is not the active scenario ({state.scenario_id!r})",
            hint=f"Verify the active one: {command_hint('verify', state.scenario_id)}",
        )
    if state.phase != PHASE_ACTIVE:
        raise StateConflictError(
            f"scenario {scenario_id!r} is not fully staged (phase: {state.phase})",
            hint=f"Run {command_hint('reset', scenario_id)} and start again.",
        )
    _check_definition_unchanged(root, state)
    out(f"Verifying scenario: {scenario_id}")
    out(f"Acceptance contract: {manifest.acceptance_doc}")
    out("")
    results: list[CheckResult] = []
    if manifest.kind == KIND_CODE:
        _check_required_imports(manifest)
        for index, command in enumerate(manifest.commands, start=1):
            out(f"Check {index}/{len(manifest.commands)}: {command.label}")
            out(f"  command: {command.display()}")
            result, output = run_acceptance_command(root, command)
            out(f"  result:  {'PASS' if result.passed else 'FAIL'} ({result.detail})")
            if not result.passed:
                print_block(output)
            results.append(result)
            out("")
    else:
        evidence = manifest.evidence
        if evidence is None:  # pragma: no cover - guarded by manifest validation
            raise ArtifactError(f"{scenario_id}: evidence scenario without an evidence check")
        out(f"Evidence file: {evidence.path}")
        results = run_evidence_check(root, evidence)
        for result in results:
            out(f"  {'PASS' if result.passed else 'FAIL'}  {result.label}: {result.detail}")
        out("")
    passed = sum(1 for result in results if result.passed)
    total = len(results)
    out(f"Summary: {passed}/{total} acceptance checks passed")
    if passed != total:
        out("")
        out("This is the expected result before your change is complete.")
        out("Keep this output: it is your fail-before evidence.")
        raise AcceptanceFailed(f"acceptance not met for {scenario_id}")
    out("Acceptance evidence is present. Record the command and this output in your")
    out("evidence note, then write your handover.")
    return EXIT_OK


def cmd_reset(root: Path, args: argparse.Namespace) -> int:
    scenario_id = str(args.scenario_id)
    # Reset is the unconditional recovery route, so it reads the state first and
    # never depends on the catalogue or the manifest being readable.
    state = load_state(root)
    if state is None:
        _explain_unknown_scenario(root, scenario_id)
        raise StateConflictError(
            f"scenario {scenario_id!r} is not active; nothing to reset",
            hint=f"See what is available: {command_hint('list')}",
        )
    if state.scenario_id != scenario_id:
        _explain_unknown_scenario(root, scenario_id)
        raise StateConflictError(
            f"scenario {scenario_id!r} is not the active scenario ({state.scenario_id!r})",
            hint=f"Reset the active one: {command_hint('reset', state.scenario_id)}",
        )
    archive = archive_attempt(root, state)
    notes = restore_targets(root, state)
    clear_state(root)
    out(f"Reset scenario: {scenario_id}")
    if archive is not None:
        out(f"Archived your work: {archive}")
        out("Nothing you wrote was deleted; it was copied there before restoring.")
        out("Treat that archive the way you treat your own notes: it holds whatever you")
        out("wrote, so delete it under the workshop's data-handling rules when you are done.")
    for note in notes:
        out(f"  {note}")
    out("")
    out("Your checkout is back at the pre-start state. The baseline should be green:")
    out("  python -m pytest tests/ -q")
    out(f"Next: {command_hint('list')}")
    return EXIT_OK


def _explain_unknown_scenario(root: Path, scenario_id: str) -> None:
    """Raise the friendlier 'unknown id' error when the catalogue is readable."""
    try:
        load_catalogue(root).require(scenario_id)
    except ArtifactError:
        return


def cmd_fallback(root: Path, args: argparse.Namespace) -> int:
    scenario_id = str(args.scenario_id)
    catalogue = load_catalogue(root)
    manifest = catalogue.require(scenario_id)
    fallback_dir = resolve_under_root(root, manifest.fallback, what=f"fallback for {scenario_id}")
    if not fallback_dir.is_dir():
        raise ArtifactError(
            f"fallback directory is missing: {manifest.fallback}",
            hint="Restore a clean checkout of workshop/fallbacks/.",
        )
    readme = fallback_dir / "README.md"
    if not readme.is_file():
        raise ArtifactError(f"fallback inventory is missing: {manifest.fallback}/README.md")
    entries = sorted(_iter_files(fallback_dir), key=lambda path: rel_to_root(fallback_dir, path))
    out(f"Offline fallback for {scenario_id} ({manifest.lab}):")
    out(f"  {manifest.fallback}")
    out("")
    out("These artifacts are captured, not live. They need no network, no cloud")
    out("agent, and no active scenario. Read them directly if staging is unavailable.")
    out("")
    out(f"Inventory ({len(entries)} files):")
    for path in entries:
        out(f"  {rel_to_root(fallback_dir, path).ljust(46)} {path.stat().st_size:>7} bytes")
    out("")
    out(f"Start here: {manifest.fallback}/README.md")
    return EXIT_OK


def _iter_files(directory: Path) -> Iterator[Path]:
    for path in sorted(directory.rglob("*")):
        if path.is_symlink():
            continue
        if path.is_file():
            yield path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python scripts/workshop.py",
        description=(
            "Stage, verify, and restore QuantCore workshop scenarios. "
            "A clean checkout is green; only 'start' stages a failing state, "
            "and 'reset' restores it exactly."
        ),
        epilog=(
            "Exit codes: 0 ok, 1 error, 2 usage, 3 acceptance failed, "
            "4 state conflict, 5 invalid artifact, 6 missing prerequisite."
        ),
    )
    parser.add_argument("--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}")
    # Test-only escape hatch so the suite never mutates the real worktree.
    parser.add_argument("--repo-root", help=argparse.SUPPRESS, default=None)
    subparsers = parser.add_subparsers(dest="command", required=True, metavar="<command>")

    subparsers.add_parser("list", help="List scenarios and show which one is active")
    subparsers.add_parser("status", help="Show the active scenario and staged-file state")

    for name, help_text in (
        ("start", "Stage a scenario into your working tree"),
        ("verify", "Run the scenario's acceptance checks"),
        ("reset", "Restore the pre-start state of a scenario"),
        ("fallback", "Print the offline fallback directory and its inventory"),
    ):
        sub = subparsers.add_parser(name, help=help_text)
        sub.add_argument("scenario_id", metavar="<scenario-id>", help="Scenario identifier")

    resync = subparsers.add_parser("resync", help="Continue learning when one lab phase is blocked")
    resync.add_argument("scenario_id", metavar="<scenario-id>", help="Scenario identifier")
    resync.add_argument(
        "--blocked-at",
        required=True,
        choices=RESYNC_PHASES,
        help="Phase that cannot be completed in the available time",
    )
    return parser


HANDLERS: Final[dict[str, Any]] = {
    "list": cmd_list,
    "start": cmd_start,
    "status": cmd_status,
    "resync": cmd_resync,
    "verify": cmd_verify,
    "reset": cmd_reset,
    "fallback": cmd_fallback,
}


def resolve_root(explicit: str | None) -> Path:
    candidate = explicit or os.environ.get("QXM_WORKSHOP_REPO_ROOT")
    if candidate:
        root = Path(candidate).expanduser()
        if not root.is_dir():
            raise WorkshopError(f"repository root is not a directory: {candidate}")
        root = root.resolve()
    else:
        root = Path(__file__).resolve().parent.parent
    if not (root / CATALOGUE_PATH).is_file():
        raise WorkshopError(
            f"no scenario catalogue found under {root}",
            hint=f"Expected {CATALOGUE_PATH}. Run this from a QuantCore checkout.",
        )
    return root


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        root = resolve_root(args.repo_root)
        handler = HANDLERS[str(args.command)]
        result = handler(root, args)
    except WorkshopError as exc:
        print(f"error: {exc.message}", file=sys.stderr)
        if exc.hint:
            print(f"hint: {exc.hint}", file=sys.stderr)
        return exc.exit_code
    except KeyboardInterrupt:  # pragma: no cover - interactive path
        print("error: interrupted", file=sys.stderr)
        return EXIT_ERROR
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
