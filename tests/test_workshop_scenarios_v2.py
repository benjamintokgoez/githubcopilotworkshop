"""Tests for the workshop scenario runner (`scripts/workshop.py`).

Every test that mutates anything works in an isolated temporary copy of the
repository's `scripts/` and `workshop/` trees. Nothing here ever stages, resets,
or writes scenario state in the real working tree.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import shutil
import stat
import subprocess
import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
TOOL_PATH = REPO_ROOT / "scripts" / "workshop.py"
SCENARIO_ROOT = REPO_ROOT / "workshop" / "scenarios"
FALLBACK_ROOT = REPO_ROOT / "workshop" / "fallbacks"

CODE_SCENARIOS = ("incident-service-rate", "migration-legacy-models", "capstone-transfer")
EVIDENCE_SCENARIOS = (
    "review-pr",
    "elective-mcp",
    "elective-cli",
    "elective-customization",
)
ALL_SCENARIOS = (
    "incident-service-rate",
    "migration-legacy-models",
    "review-pr",
    "elective-mcp",
    "elective-cli",
    "elective-customization",
    "capstone-transfer",
)

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2
EXIT_ACCEPTANCE_FAILED = 3
EXIT_STATE_CONFLICT = 4
EXIT_INVALID_ARTIFACT = 5
EXIT_PREREQUISITE = 6

HAS_PYDANTIC = importlib.util.find_spec("pydantic") is not None
NEEDS_PYDANTIC = pytest.mark.skipif(
    not HAS_PYDANTIC, reason="scenario declares pydantic as a prerequisite"
)


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def cli() -> types.ModuleType:
    """The runner imported as a module, for unit-level checks."""
    spec = importlib.util.spec_from_file_location("workshop_cli_under_test", TOOL_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def repo_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """One pristine copy of the scenario system, cloned per test."""
    template = tmp_path_factory.mktemp("workshop-template")
    (template / "scripts").mkdir()
    shutil.copy2(TOOL_PATH, template / "scripts" / "workshop.py")
    shutil.copytree(REPO_ROOT / "workshop", template / "workshop")
    return template


@pytest.fixture
def sandbox(repo_template: Path, tmp_path: Path) -> Path:
    """An isolated repository root for one test."""
    root = tmp_path / "repo"
    shutil.copytree(repo_template, root)
    return root


def run(
    root: Path, *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    """Invoke the runner against ``root`` and capture its output."""
    argv = [
        sys.executable,
        str(root / "scripts" / "workshop.py"),
        "--repo-root",
        str(root),
        *args,
    ]
    process_env = dict(os.environ)
    process_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        process_env.update(env)
    return subprocess.run(  # noqa: S603 - fixed argv, no shell, test-owned paths
        argv,
        cwd=str(root),
        env=process_env,
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )


def tree_state(root: Path) -> dict[str, tuple[str, int]]:
    """Hash and mode of every file under ``root/workshop``."""
    state: dict[str, tuple[str, int]] = {}
    for path in sorted((root / "workshop").rglob("*")):
        if path.is_file() and not path.is_symlink():
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            state[path.relative_to(root).as_posix()] = (digest, path.stat().st_mode & 0o777)
    return state


def manifest_of(root: Path, scenario_id: str) -> dict[str, object]:
    path = root / "workshop" / "scenarios" / scenario_id / "manifest.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def targets_of(root: Path, scenario_id: str) -> list[str]:
    stage = manifest_of(root, scenario_id)["stage"]
    assert isinstance(stage, list)
    return [str(item["target"]) for item in stage]


def evidence_path_of(root: Path, scenario_id: str) -> Path:
    acceptance = manifest_of(root, scenario_id)["acceptance"]
    assert isinstance(acceptance, dict)
    evidence = acceptance["evidence"]
    assert isinstance(evidence, dict)
    return root / str(evidence["path"])


def state_json(root: Path) -> dict[str, object]:
    data = json.loads((root / ".workshop-state" / "state.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict)
    return data


def first_target_record(root: Path) -> dict[str, object]:
    targets = state_json(root)["targets"]
    assert isinstance(targets, list)
    record = targets[0]
    assert isinstance(record, dict)
    return record


def write_state(root: Path, state: dict[str, object]) -> None:
    (root / ".workshop-state" / "state.json").write_text(
        json.dumps(state, indent=2), encoding="utf-8"
    )


def archived_files(root: Path, scenario_id: str) -> dict[str, str]:
    """Every archived attempt file, keyed by its repository-relative path."""
    base = root / ".workshop-state" / "attempts" / scenario_id
    archived: dict[str, str] = {}
    if not base.is_dir():
        return archived
    for run_dir in sorted(base.iterdir()):
        for path in sorted(run_dir.rglob("*")):
            if path.is_file():
                archived[path.relative_to(run_dir).as_posix()] = path.read_text(
                    encoding="utf-8", errors="replace"
                )
    return archived


def write_custom_scenario(
    root: Path,
    scenario_id: str,
    manifest: dict[str, object],
    payloads: dict[str, str] | None = None,
) -> None:
    """Create an extra scenario inside a sandbox, for validation tests."""
    directory = root / "workshop" / "scenarios" / scenario_id
    (directory / "payloads").mkdir(parents=True, exist_ok=True)
    (directory / "acceptance.md").write_text("# acceptance\n", encoding="utf-8")
    (directory / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    for name, body in (payloads or {}).items():
        (directory / "payloads" / name).write_text(body, encoding="utf-8")
    fallback = root / "workshop" / "fallbacks" / scenario_id
    fallback.mkdir(parents=True, exist_ok=True)
    (fallback / "README.md").write_text("# offline fallback\n", encoding="utf-8")
    catalogue_path = root / "workshop" / "scenarios" / "catalogue.json"
    catalogue = json.loads(catalogue_path.read_text(encoding="utf-8"))
    catalogue["scenarios"].append(scenario_id)
    catalogue_path.write_text(json.dumps(catalogue, indent=2), encoding="utf-8")


def base_command_manifest(
    scenario_id: str, argv: list[str], timeout: int = 60
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "id": scenario_id,
        "title": "Sandbox scenario",
        "kind": "code",
        "lab": "Lab X",
        "summary": "Synthetic scenario used only by the test suite.",
        "fallback": f"workshop/fallbacks/{scenario_id}",
        "acceptance_doc": f"workshop/scenarios/{scenario_id}/acceptance.md",
        "stage": [
            {
                "payload": f"workshop/scenarios/{scenario_id}/payloads/probe.py.txt",
                "target": f"workshop/scenarios/{scenario_id}/work/probe.py",
                "description": "Sandbox payload.",
            }
        ],
        "acceptance": {
            "kind": "command",
            "commands": [{"label": "sandbox check", "argv": argv, "timeout_seconds": timeout}],
        },
    }


def iter_workshop_files(*roots: Path) -> Iterator[Path]:
    for root in roots:
        for path in sorted(root.rglob("*")):
            if path.is_file() and not path.is_symlink():
                yield path


# ---------------------------------------------------------------------------
# Repairs and evidence used to prove pass-after
# ---------------------------------------------------------------------------

CAPSTONE_IMPLEMENTATION = '''"""Daily export helper (test-local reference implementation)."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_UP, Decimal
from zoneinfo import ZoneInfo

EXPORT_PREFIX = "service_export"


def selection_window(business_date: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo("Europe/Berlin")
    start = datetime.combine(business_date, time(0, 0), tzinfo=tz)
    end = datetime.combine(business_date + timedelta(days=1), time(0, 0), tzinfo=tz)
    return start.astimezone(UTC), end.astimezone(UTC)


def records_in_window(
    records: Iterable[dict[str, str]], business_date: date
) -> list[dict[str, str]]:
    start, end = selection_window(business_date)
    selected: list[dict[str, str]] = []
    for record in records:
        moment = datetime.fromisoformat(record["recorded_at"].replace("Z", "+00:00"))
        if start <= moment.astimezone(UTC) < end:
            selected.append(record)
    return selected


def export_filename(business_date: date) -> str:
    return f"{EXPORT_PREFIX}_{business_date.isoformat()}.csv"


def display_total(amount: Decimal, currency: str = "EUR") -> str:
    quantised = amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    whole, _, fraction = f"{quantised:,.2f}".partition(".")
    return f"{whole.replace(',', '.')},{fraction} {currency}"


def total_of(records: Sequence[dict[str, str]]) -> Decimal:
    return sum((Decimal(record["amount"]) for record in records), Decimal("0"))
'''

MIGRATED_MODELS = '''"""MittelWerk model surface (test-local migrated implementation)."""

from datetime import UTC, datetime
from decimal import Decimal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_serializer,
    field_validator,
    model_validator,
)

SUPPORTED_CURRENCIES = ("EUR", "CHF")


class EquipmentRef(BaseModel):
    model_config = ConfigDict(populate_by_name=True, str_strip_whitespace=True)

    asset_code: str = Field(..., alias="asset", min_length=1, max_length=24)
    name: str = Field(..., min_length=1, max_length=80)
    currency: str = Field("EUR", min_length=3, max_length=3)
    standard_hourly_rate: Decimal = Field(..., gt=0)
    service_region: str | None = None

    @field_validator("asset_code")
    @classmethod
    def asset_code_is_upper_case(cls, value: str) -> str:
        upper = value.upper()
        if not upper.replace("-", "").isalnum():
            raise ValueError("asset code must be alphanumeric, optionally with '-'")
        return upper

    @field_validator("currency")
    @classmethod
    def currency_is_supported(cls, value: str) -> str:
        upper = value.upper()
        if upper not in SUPPORTED_CURRENCIES:
            raise ValueError(f"currency must be one of {', '.join(SUPPORTED_CURRENCIES)}")
        return upper


class ServiceRatePayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    asset_code: str = Field(..., alias="asset", min_length=1, max_length=24)
    standard_rate: Decimal = Field(..., ge=0)
    emergency_rate: Decimal = Field(..., ge=0)
    as_of: datetime
    service_region: str | None = None

    @field_validator("asset_code")
    @classmethod
    def asset_code_is_upper_case(cls, value: str) -> str:
        return value.upper()

    @field_validator("as_of")
    @classmethod
    def as_of_is_utc(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("as_of must be timezone-aware (INV-TIME-1)")
        return value.astimezone(UTC)

    @field_serializer("as_of", when_used="json")
    def serialise_as_of(self, value: datetime) -> str:
        return value.astimezone(UTC).isoformat()

    @model_validator(mode="after")
    def emergency_rate_is_not_lower(self) -> "ServiceRatePayload":
        if self.emergency_rate < self.standard_rate:
            raise ValueError("emergency rate must not be below standard rate")
        return self
'''

MIGRATED_SERVICE = '''"""Serialisation boundary (test-local migrated implementation)."""

from typing import Any

from legacy_models import EquipmentRef, ServiceRatePayload


class ContractError(ValueError):
    """Raised when input does not satisfy the published contract."""


def parse_equipment(raw: dict[str, Any]) -> EquipmentRef:
    try:
        return EquipmentRef.model_validate(raw)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc


def parse_service_rate(raw: dict[str, Any]) -> ServiceRatePayload:
    try:
        return ServiceRatePayload.model_validate(raw)
    except ValueError as exc:
        raise ContractError(str(exc)) from exc


def equipment_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return parse_equipment(raw).model_dump(by_alias=True)


def equipment_json(raw: dict[str, Any]) -> str:
    return parse_equipment(raw).model_dump_json(by_alias=True)


def service_rate_payload(raw: dict[str, Any]) -> dict[str, Any]:
    return parse_service_rate(raw).model_dump(by_alias=True)


def service_rate_json(raw: dict[str, Any]) -> str:
    return parse_service_rate(raw).model_dump_json(by_alias=True)
'''

REVIEW_NOTES = """# Review notes - PR #212

## 1. What I think the diff does

It makes overdue workload and service-cost values negative, renames published
summary fields, weakens analytics assertions, puts locale-formatted numbers into
machine JSON, and drops timezone awareness while swallowing storage failures.

## 2. Findings

### Finding 1 - overdue workload becomes negative

- Location: mittelwerk/analytics/sla.py, reporting helpers
- Severity: blocking
- Evidence: the issue requires non-negative operational magnitudes, but both
  helpers return minus the absolute value, so overdue hours and cost are negative.
- Requested change: return the absolute value and restore the exact analytics
  assertions that would fail for negative values.

### Finding 2 - response field names changed although the issue forbade it

- Location: mittelwerk/api/routes.py, get_operations_summary return value
- Severity: blocking
- Evidence: the issue puts the response shape explicitly out of scope, the diff
  renames the two published keys, and the session log records a dashboard
  consumer that was found and then not updated.
- Requested change: restore the original field names and raise a separate ticket
  with a deprecation window if the rename is still wanted.

### Finding 3 - test assertions were weakened to make the change pass

- Location: tests/test_analytics.py, both updated assertions
- Severity: blocking
- Evidence: the tolerance widened and the non-negative assertion became a
  non-zero assertion, so the suite no longer detects the reported defect.
- Requested change: restore the original assertions and let the implementation
  satisfy them instead.

## 3. Comparison with the captured automated review

- Found by the captured review, missed by me: the naive timestamp and swallowed
  storage failure, which I skipped while reading analytics first.
- Found by me, missed by the captured review: the renamed response keys that
  break the documented contract, because judging that needs the linked issue and
  the downstream consumer rather than the diff alone.
- Comment I would not forward to the author: converting Decimal rates to float,
  because that contradicts the exact money-boundary contract.

## 4. Decision

- Decision: request changes, with the conditions listed below
- Condition that would flip it: original field names restored, non-negative
  magnitudes returned, and strong assertions reinstated.

## 5. Uncertainty

I verified the sign convention and the field names against the issue. I assumed
the dashboard consumer is the only one. It could still be wrong if another
service parses the same response.
"""

MCP_INVENTORY = """# MCP permission inventory

## 1. What this server can reach

The default server exposes three read-only tools over standard input and output,
and the process itself runs unsandboxed in the workspace folder with whatever the
environment file hands it.

- Data that leaves this machine: nothing beyond the local process, but every
  response enters the model context, which is the part worth stating explicitly.

## 2. Tools offered, enabled, disabled

- Tools offered: list_equipment, get_dispatch_queue, calculate_service_risk
- Tools enabled: get_dispatch_queue, calculate_service_risk
- Tools disabled: list_equipment was deselected in the client; submit_work_order and
  cancel_work_order were never registered by this read-only server

The writing tools are absent because the task is read-only, and the equipment
listing is deselected because it returns the whole reference set when the
question concerned one asset.

- Where the control lives: the process confinement is mcp.json with sandboxEnabled
  and the top-level sandbox rules, tool selection and approval are client settings,
  and the argument bounds plus write registration are the server's own code.
- Approval boundary: I left the sandbox off for this session, so per-call
  confirmation is still the boundary; enabling it would auto-approve confirmations
  for this server and make the filesystem and network rules the only check.

## 3. Evidence the answer came from the tool

Captured evidence from the shipped tool-call log: the queue call returned three
offers and one request for PRESS-17 at 13:03 UTC, values the model could not have
produced without the call, and the reply quoted them exactly.

## 4. Negative case

- What I asked for outside the permission: submitting a work order for four
  hours, and then requesting queue depth far beyond the documented bound.
- Observed behaviour: the server answered unknown tool for the write, because it
  was never registered, and rejected the depth argument in its own validation, so
  the refusals came from the server rather than from the client.

## 5. What MCP configuration does not protect against

It does not protect against a permitted tool returning more than the task needs,
and it does not protect against instructions embedded in the data that a
permitted tool returns. The process sandbox is also macOS and Linux only, so on
Windows that layer is documentation rather than enforcement, and turning it on
elsewhere removes the per-call prompts rather than adding to them.

## 6. What I would ask my platform team for

A registry entry for the local server with reading tools only, an approval prompt
for anything that changes state, and tool-call logging retained long enough to
reconstruct a session the next morning.

- Approval owner: the platform security group that maintains the tool allowlist
"""

CLI_POLICY = """# Terminal agent permission policy

- Evidence source: captured transcript shipped with the scenario

## 1. Default posture

Deny by default and ask for anything not on the list, because this machine also
holds credentials for other systems and an unattended command cannot be reviewed
after the fact.

- Default posture: deny by default, ask for everything not explicitly allowed

## 2. Rules

### Rule 1

- Command: repository-scoped source search inside the working directory
- Verdict: allow
- Why: reading source inside the checkout is what the task needs and it changes
  nothing on disk or in the environment.
- Blast radius if wrong: a file inside the repository is read into the context,
  which is why the repository must not hold secrets.

### Rule 2

- Command: the test runner with an explicit path inside the repository
- Verdict: ask
- Why: running tests executes repository code, and arguments can widen the scope
  well beyond the directory the agent started in.
- Blast radius if wrong: arbitrary code execution with the developer's own
  environment and credentials.

### Rule 3

- Command: any version-control command that writes, and any network call
- Verdict: deny
- Why: writes to a remote or calls to the network are outside the task and cannot
  be reviewed afterwards.
- Blast radius if wrong: published changes, or data leaving the machine without
  anyone reading it first.

- Broadest entry I wrote: the test-runner entry, because a wildcard on arguments
  also grants paths outside the working directory.

## 3. Negative case

- What I asked for outside the policy: a network call to check whether a service
  was reachable from this machine.
- Observed behaviour: the request was surfaced for approval and denied, and the
  session continued without it.

## 4. What an allowlist does not protect against

It does not protect against a permitted command carrying hostile arguments, and
it does not protect against credentials already exported in the environment.

## 5. Shared machines and CI

On a shared runner I would remove the test-runner allowance entirely, require
approval for every command, and keep a retained log so that what ran overnight
can be reconstructed the next morning.
"""

CUSTOMIZATION_NOTES = """# Customization notes

## 1. The task I measured with

Write a unit test for a small helper that formats an amount for display, using
the repository conventions and nothing else, in a single file.

## 2. Before

The generated test asserted a formatted string with a dot decimal separator and
used a naive timestamp for the recorded field, which no reviewer here would
accept in a payload.

## 3. After

- Observable difference: the regenerated test used a decimal comma with the
  currency attached and a timezone-aware timestamp, without being reminded.

The same task also produced a test that fails before the fix rather than one that
asserts the behaviour that already exists.

## 4. Rules

### Rule 1

- Rule: store timestamps as timezone-aware UTC and convert to Europe/Berlin only
  at the presentation edge.
- How a reviewer checks it: search the diff for naive timestamp construction and
  for conversion outside the display layer.
- Belongs in: instruction plus a test for the round trip

### Rule 2

- Rule: use a dot decimal separator in code, configuration and payloads, and keep
  the comma for display only.
- How a reviewer checks it: read the serialised payload in the fixtures and
  confirm that no comma appears in a stored value.
- Belongs in: CI check on the serialised fixtures

### Rule 3

- Rule: a test must fail before the fix and pass after it, and the failing output
  belongs in the pull request.
- How a reviewer checks it: ask for the failing run, or revert the change locally
  and run the test again.
- Belongs in: review checklist

## 5. What I deleted or rewrote

- Rule I deleted or rewrote: always use the fastest available model for this
  repository.
- Why its effect was not observable: model availability differs per organisation,
  nothing in a diff shows whether it was followed, and the rule expires.

## 6. Contradiction test

- What I asked for that contradicts a rule: a helper that formats an amount with
  a comma and then stores that string in the payload.
- Observed behaviour: the first answer followed the rule and warned about it, and
  a second, more insistent request complied, which is why the rule needs a check.

## 7. What durable context cannot enforce

Nothing in an instruction file is guaranteed. The separator rule and the storage
rule both need a test or a lint rule, and only the review checklist item really
depends on a human reading it.
"""

EVIDENCE_FIXTURES: dict[str, str] = {
    "review-pr": REVIEW_NOTES,
    "elective-mcp": MCP_INVENTORY,
    "elective-cli": CLI_POLICY,
    "elective-customization": CUSTOMIZATION_NOTES,
}


def apply_repair(root: Path, scenario_id: str) -> None:
    """Simulate a correct participant repair for a code scenario."""
    work = root / "workshop" / "scenarios" / scenario_id / "work"
    if scenario_id == "incident-service-rate":
        module = work / "dispatch_engine.py"
        source = module.read_text(encoding="utf-8")
        assert "hourly_rate=request.maximum_hourly_rate," in source
        module.write_text(
            source.replace(
                "hourly_rate=request.maximum_hourly_rate,",
                "hourly_rate=offer.hourly_rate,",
            ),
            encoding="utf-8",
        )
    elif scenario_id == "capstone-transfer":
        (work / "daily_export.py").write_text(CAPSTONE_IMPLEMENTATION, encoding="utf-8")
    elif scenario_id == "migration-legacy-models":
        (work / "legacy_models.py").write_text(MIGRATED_MODELS, encoding="utf-8")
        (work / "legacy_service.py").write_text(MIGRATED_SERVICE, encoding="utf-8")
    else:  # pragma: no cover - guarded by the parametrisation
        raise AssertionError(f"no repair defined for {scenario_id}")


def apply_evidence(root: Path, scenario_id: str) -> None:
    """Write substantive evidence in place of the staged template."""
    evidence_path_of(root, scenario_id).write_text(EVIDENCE_FIXTURES[scenario_id], encoding="utf-8")


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


class TestCommandSurface:
    def test_help_lists_every_documented_command(self, sandbox: Path) -> None:
        result = run(sandbox, "--help")
        assert result.returncode == EXIT_OK
        for command in ("list", "start", "status", "resync", "verify", "reset", "fallback"):
            assert command in result.stdout

    def test_help_documents_exit_codes(self, sandbox: Path) -> None:
        result = run(sandbox, "--help")
        assert "acceptance failed" in result.stdout
        assert "state conflict" in result.stdout

    def test_version_is_reported(self, sandbox: Path) -> None:
        result = run(sandbox, "--version")
        assert result.returncode == EXIT_OK
        assert "workshop.py" in result.stdout

    def test_missing_command_is_a_usage_error(self, sandbox: Path) -> None:
        assert run(sandbox).returncode == EXIT_USAGE

    def test_unknown_command_is_a_usage_error(self, sandbox: Path) -> None:
        assert run(sandbox, "explode").returncode == EXIT_USAGE

    def test_repo_root_can_come_from_the_environment(self, sandbox: Path) -> None:
        argv = [sys.executable, str(sandbox / "scripts" / "workshop.py"), "list"]
        result = subprocess.run(  # noqa: S603 - fixed argv, no shell
            argv,
            cwd=str(sandbox),
            env={**os.environ, "MITTELWERK_WORKSHOP_REPO_ROOT": str(sandbox)},
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
        assert result.returncode == EXIT_OK
        assert "incident-service-rate" in result.stdout

    def test_a_root_without_a_catalogue_is_refused(self, tmp_path: Path, sandbox: Path) -> None:
        empty = tmp_path / "empty"
        empty.mkdir()
        result = run(sandbox, "--repo-root", str(empty), "list")
        assert result.returncode == EXIT_ERROR
        assert "catalogue" in result.stderr


class TestList:
    def test_lists_the_seven_scenarios_in_catalogue_order(self, sandbox: Path) -> None:
        result = run(sandbox, "list")
        assert result.returncode == EXIT_OK
        positions = [result.stdout.index(scenario_id) for scenario_id in ALL_SCENARIOS]
        assert positions == sorted(positions)

    def test_reports_kind_and_lab_for_each_scenario(self, sandbox: Path) -> None:
        result = run(sandbox, "list")
        for scenario_id in CODE_SCENARIOS:
            line = next(line for line in result.stdout.splitlines() if scenario_id in line)
            assert "code" in line
        for scenario_id in EVIDENCE_SCENARIOS:
            line = next(line for line in result.stdout.splitlines() if scenario_id in line)
            assert "evidence" in line

    def test_is_deterministic(self, sandbox: Path) -> None:
        assert run(sandbox, "list").stdout == run(sandbox, "list").stdout

    def test_marks_the_active_scenario(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        result = run(sandbox, "list")
        assert "Active scenario: review-pr" in result.stdout
        marked = next(line for line in result.stdout.splitlines() if "review-pr" in line)
        assert marked.strip().startswith("*")

    def test_invalid_json_manifest_is_reported_actionably(self, sandbox: Path) -> None:
        path = sandbox / "workshop" / "scenarios" / "review-pr" / "manifest.json"
        path.write_text("{ not json", encoding="utf-8")
        result = run(sandbox, "list")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "not valid JSON" in result.stderr

    def test_manifest_with_unknown_key_is_rejected(self, sandbox: Path) -> None:
        path = sandbox / "workshop" / "scenarios" / "review-pr" / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["surprise"] = True
        path.write_text(json.dumps(data), encoding="utf-8")
        result = run(sandbox, "list")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "unknown key" in result.stderr

    def test_manifest_id_must_match_its_directory(self, sandbox: Path) -> None:
        path = sandbox / "workshop" / "scenarios" / "review-pr" / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["id"] = "review-pr-2"
        path.write_text(json.dumps(data), encoding="utf-8")
        result = run(sandbox, "list")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "does not match its directory" in result.stderr

    def test_missing_required_artifact_is_reported(self, sandbox: Path) -> None:
        (sandbox / "workshop" / "scenarios" / "incident-service-rate" / "issue.md").unlink()
        result = run(sandbox, "list")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "required artifact is missing" in result.stderr

    def test_manifest_with_invalid_utf8_is_rejected(self, sandbox: Path) -> None:
        path = sandbox / "workshop" / "scenarios" / "elective-cli" / "manifest.json"
        path.write_bytes(b'{"id": "\xff\xfe"}')
        result = run(sandbox, "list")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "UTF-8" in result.stderr

    def test_duplicate_catalogue_entries_are_rejected(self, sandbox: Path) -> None:
        path = sandbox / "workshop" / "scenarios" / "catalogue.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["scenarios"].append("review-pr")
        path.write_text(json.dumps(data), encoding="utf-8")
        result = run(sandbox, "list")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "duplicate" in result.stderr


# ---------------------------------------------------------------------------
# Manifest and path validation
# ---------------------------------------------------------------------------


class TestPathValidation:
    @pytest.mark.parametrize(
        "candidate",
        [
            "/etc/passwd",
            "../outside.txt",
            "workshop/../../escape.txt",
            "workshop\\scenarios\\x.txt",
            "C:/windows/system32",
            "workshop/scenarios/./x.txt",
            "workshop/scenarios/x .txt",
            "workshop/scenarios/x$.txt",
            "",
        ],
    )
    def test_unsafe_paths_are_rejected(self, cli: types.ModuleType, candidate: str) -> None:
        with pytest.raises(cli.ArtifactError):
            cli.check_relpath(candidate, what="test")

    def test_normal_paths_are_accepted(self, cli: types.ModuleType) -> None:
        parsed = cli.check_relpath("workshop/scenarios/review-pr/work/review_notes.md", what="test")
        assert parsed.name == "review_notes.md"

    def test_symlinked_component_is_refused(self, cli: types.ModuleType, tmp_path: Path) -> None:
        (tmp_path / "real").mkdir()
        (tmp_path / "link").symlink_to(tmp_path / "real", target_is_directory=True)
        with pytest.raises(cli.ArtifactError):
            cli.resolve_under_root(
                tmp_path, cli.check_relpath("link/file.txt", what="t"), what="target"
            )

    def test_symlinked_target_is_refused_by_start(self, sandbox: Path) -> None:
        work = sandbox / "workshop" / "scenarios" / "review-pr" / "work"
        work.mkdir(parents=True)
        outside = sandbox.parent / "outside.md"
        outside.write_text("do not touch\n", encoding="utf-8")
        (work / "review_notes.md").symlink_to(outside)
        result = run(sandbox, "start", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "symlink" in result.stderr
        assert outside.read_text(encoding="utf-8") == "do not touch\n"
        assert not (sandbox / ".workshop-state" / "state.json").exists()


class TestManifestValidation:
    def _parse(self, cli: types.ModuleType, data: dict[str, object]) -> object:
        return cli.parse_manifest(data, expected_id="sandbox-x", where="test")

    def test_valid_manifest_parses(self, cli: types.ModuleType) -> None:
        manifest = self._parse(cli, base_command_manifest("sandbox-x", ["{python}", "-c", "pass"]))
        assert manifest.kind == "code"
        assert manifest.commands[0].timeout_seconds == 60

    def test_duplicate_targets_are_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        stage = data["stage"]
        assert isinstance(stage, list)
        stage.append(dict(stage[0]))
        with pytest.raises(cli.ArtifactError, match="duplicate target"):
            self._parse(cli, data)

    def test_target_outside_the_scenario_directory_is_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        stage = data["stage"]
        assert isinstance(stage, list)
        stage[0]["target"] = "outside/core/engine.py"
        with pytest.raises(cli.ArtifactError, match="must live under"):
            self._parse(cli, data)

    def test_absolute_payload_is_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        stage = data["stage"]
        assert isinstance(stage, list)
        stage[0]["payload"] = "/etc/passwd"
        with pytest.raises(cli.ArtifactError):
            self._parse(cli, data)

    def test_traversing_payload_is_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        stage = data["stage"]
        assert isinstance(stage, list)
        stage[0]["payload"] = "workshop/scenarios/sandbox-x/../../../etc/hosts"
        with pytest.raises(cli.ArtifactError):
            self._parse(cli, data)

    def test_unsupported_mode_is_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        stage = data["stage"]
        assert isinstance(stage, list)
        stage[0]["mode"] = "0777"
        with pytest.raises(cli.ArtifactError, match="mode"):
            self._parse(cli, data)

    def test_unknown_substitution_token_is_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{shell}", "-c", "pass"])
        with pytest.raises(cli.ArtifactError, match="substitution token"):
            self._parse(cli, data)

    def test_control_characters_in_argv_are_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "print(1)\nimport os"])
        with pytest.raises(cli.ArtifactError, match="control character"):
            self._parse(cli, data)

    def test_timeout_bounds_are_enforced(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"], timeout=100000)
        with pytest.raises(cli.ArtifactError, match="between"):
            self._parse(cli, data)

    def test_kind_and_acceptance_kind_must_agree(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        data["kind"] = "evidence"
        with pytest.raises(cli.ArtifactError, match="requires scenario kind"):
            self._parse(cli, data)

    def test_unknown_kind_is_rejected(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        data["kind"] = "quiz"
        with pytest.raises(cli.ArtifactError, match="kind must be one of"):
            self._parse(cli, data)

    def test_evidence_headings_must_be_headings(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        data["kind"] = "evidence"
        data["acceptance"] = {
            "kind": "evidence",
            "evidence": {
                "path": "workshop/scenarios/sandbox-x/work/notes.md",
                "required_headings": ["Findings"],
            },
        }
        with pytest.raises(cli.ArtifactError, match="must start with"):
            self._parse(cli, data)

    def test_fallback_path_is_pinned_to_the_scenario_id(self, cli: types.ModuleType) -> None:
        data = base_command_manifest("sandbox-x", ["{python}", "-c", "pass"])
        data["fallback"] = "workshop/fallbacks/other"
        with pytest.raises(cli.ArtifactError, match="fallback must be"):
            self._parse(cli, data)

    def test_every_shipped_manifest_is_valid(self, cli: types.ModuleType) -> None:
        catalogue = cli.load_catalogue(REPO_ROOT)
        assert catalogue.scenario_ids == ALL_SCENARIOS
        for scenario_id in ALL_SCENARIOS:
            manifest = catalogue.manifests[scenario_id]
            assert manifest.scenario_id == scenario_id
            assert manifest.kind in ("code", "evidence")
            cli.validate_scenario_artifacts(REPO_ROOT, manifest)


# ---------------------------------------------------------------------------
# start / status / verify / reset for every scenario
# ---------------------------------------------------------------------------


def skip_without_prerequisites(scenario_id: str) -> None:
    if scenario_id == "migration-legacy-models" and not HAS_PYDANTIC:
        pytest.skip("scenario declares pydantic as a prerequisite")


@pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
class TestScenarioLifecycle:
    def test_start_stages_every_declared_target(self, sandbox: Path, scenario_id: str) -> None:
        skip_without_prerequisites(scenario_id)
        result = run(sandbox, "start", scenario_id)
        assert result.returncode == EXIT_OK, result.stderr
        for target in targets_of(sandbox, scenario_id):
            path = sandbox / target
            assert path.is_file()
            assert stat.S_IMODE(path.stat().st_mode) == 0o644
            assert target in result.stdout
        state = state_json(sandbox)
        assert state["scenario_id"] == scenario_id
        assert state["phase"] == "active"
        assert str(state["started_at"]).endswith("+00:00")

    def test_start_prints_the_acceptance_route(self, sandbox: Path, scenario_id: str) -> None:
        skip_without_prerequisites(scenario_id)
        result = run(sandbox, "start", scenario_id)
        assert f"verify {scenario_id}" in result.stdout
        assert f"reset {scenario_id}" in result.stdout
        assert "expected to FAIL" in result.stdout

    def test_status_reports_the_active_scenario(self, sandbox: Path, scenario_id: str) -> None:
        skip_without_prerequisites(scenario_id)
        run(sandbox, "start", scenario_id)
        result = run(sandbox, "status")
        assert result.returncode == EXIT_OK
        assert f"Active scenario: {scenario_id}" in result.stdout
        assert "[unchanged]" in result.stdout
        assert f"verify {scenario_id}" in result.stdout

    def test_status_detects_participant_changes_and_deletions(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        skip_without_prerequisites(scenario_id)
        run(sandbox, "start", scenario_id)
        target = sandbox / targets_of(sandbox, scenario_id)[0]
        target.write_text("participant edit\n", encoding="utf-8")
        assert "[participant-modified]" in run(sandbox, "status").stdout
        target.unlink()
        assert "[missing]" in run(sandbox, "status").stdout

    def test_verify_fails_before_the_work_is_done(self, sandbox: Path, scenario_id: str) -> None:
        skip_without_prerequisites(scenario_id)
        run(sandbox, "start", scenario_id)
        result = run(sandbox, "verify", scenario_id)
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "acceptance checks passed" in result.stdout
        assert "fail-before evidence" in result.stdout

    def test_reset_restores_the_pre_start_tree_exactly(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        skip_without_prerequisites(scenario_id)
        before = tree_state(sandbox)
        run(sandbox, "start", scenario_id)
        targets = targets_of(sandbox, scenario_id)
        (sandbox / targets[0]).write_text("participant work in progress\n", encoding="utf-8")
        result = run(sandbox, "reset", scenario_id)
        assert result.returncode == EXIT_OK, result.stderr
        assert tree_state(sandbox) == before
        assert not (sandbox / ".workshop-state" / "state.json").exists()
        for target in targets:
            assert not (sandbox / target).exists()

    def test_reset_archives_participant_work(self, sandbox: Path, scenario_id: str) -> None:
        skip_without_prerequisites(scenario_id)
        run(sandbox, "start", scenario_id)
        target = targets_of(sandbox, scenario_id)[0]
        (sandbox / target).write_text("my attempt, worth keeping\n", encoding="utf-8")
        result = run(sandbox, "reset", scenario_id)
        assert "Archived your work" in result.stdout
        archive_root = sandbox / ".workshop-state" / "attempts" / scenario_id
        contents = [
            path.read_text(encoding="utf-8") for path in archive_root.rglob("*") if path.is_file()
        ]
        assert "my attempt, worth keeping\n" in contents

    def test_fallback_is_available_without_an_active_scenario(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        result = run(sandbox, "fallback", scenario_id)
        assert result.returncode == EXIT_OK
        assert f"workshop/fallbacks/{scenario_id}" in result.stdout
        assert "README.md" in result.stdout
        assert "Inventory" in result.stdout

    @pytest.mark.parametrize(
        ("blocked_at", "expected"),
        [
            ("tooling", "captured route"),
            ("understand-plan", "smallest testable claim"),
            ("implement-test", "incomplete attempt"),
            ("review", "six checks"),
            ("explain", "what you verified"),
        ],
    )
    def test_resync_prints_an_answer_neutral_route_without_changing_state(
        self, sandbox: Path, scenario_id: str, blocked_at: str, expected: str
    ) -> None:
        skip_without_prerequisites(scenario_id)
        run(sandbox, "start", scenario_id)
        before = tree_state(sandbox)
        state_before = state_json(sandbox)
        result = run(sandbox, "resync", scenario_id, "--blocked-at", blocked_at)
        assert result.returncode == EXIT_OK, result.stderr
        assert expected in result.stdout
        assert "does not solve the task" in result.stdout
        assert f"reset {scenario_id}" in result.stdout
        assert tree_state(sandbox) == before
        assert state_json(sandbox) == state_before


# ---------------------------------------------------------------------------
# Fail-before / pass-after
# ---------------------------------------------------------------------------


class TestCodeScenarios:
    @pytest.mark.parametrize("scenario_id", CODE_SCENARIOS)
    def test_repair_turns_the_acceptance_check_green(self, sandbox: Path, scenario_id: str) -> None:
        skip_without_prerequisites(scenario_id)
        assert run(sandbox, "start", scenario_id).returncode == EXIT_OK
        assert run(sandbox, "verify", scenario_id).returncode == EXIT_ACCEPTANCE_FAILED
        apply_repair(sandbox, scenario_id)
        after = run(sandbox, "verify", scenario_id)
        assert after.returncode == EXIT_OK, after.stdout + after.stderr
        assert "Summary: 1/1 acceptance checks passed" in after.stdout

    @pytest.mark.parametrize("scenario_id", CODE_SCENARIOS)
    def test_reset_after_a_repair_returns_to_the_original_bytes(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        skip_without_prerequisites(scenario_id)
        before = tree_state(sandbox)
        run(sandbox, "start", scenario_id)
        apply_repair(sandbox, scenario_id)
        run(sandbox, "verify", scenario_id)
        assert run(sandbox, "reset", scenario_id).returncode == EXIT_OK
        assert tree_state(sandbox) == before

    def test_the_incident_check_asserts_the_invariant_not_one_literal(self, sandbox: Path) -> None:
        run(sandbox, "start", "incident-service-rate")
        module = sandbox / "workshop/scenarios/incident-service-rate/work/dispatch_engine.py"
        source = module.read_text(encoding="utf-8")
        module.write_text(
            source.replace(
                "hourly_rate=request.maximum_hourly_rate,",
                'hourly_rate=Decimal("110.00"),',
            ),
            encoding="utf-8",
        )
        assert run(sandbox, "verify", "incident-service-rate").returncode == EXIT_ACCEPTANCE_FAILED

    @NEEDS_PYDANTIC
    def test_the_migration_contract_checks_pass_before_the_migration(self, sandbox: Path) -> None:
        run(sandbox, "start", "migration-legacy-models")
        result = run(sandbox, "verify", "migration-legacy-models")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "compatibility shim" in result.stdout

    @NEEDS_PYDANTIC
    def test_a_migration_that_breaks_the_contract_is_caught(self, sandbox: Path) -> None:
        run(sandbox, "start", "migration-legacy-models")
        apply_repair(sandbox, "migration-legacy-models")
        models = sandbox / "workshop/scenarios/migration-legacy-models/work/legacy_models.py"
        source = models.read_text(encoding="utf-8")
        models.write_text(
            source.replace('alias="asset"', 'alias="equipment_code"'),
            encoding="utf-8",
        )
        assert (
            run(sandbox, "verify", "migration-legacy-models").returncode == EXIT_ACCEPTANCE_FAILED
        )


class TestEvidenceScenarios:
    @pytest.mark.parametrize("scenario_id", EVIDENCE_SCENARIOS)
    def test_template_fails_and_substantive_evidence_passes(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        assert run(sandbox, "start", scenario_id).returncode == EXIT_OK
        before = run(sandbox, "verify", scenario_id)
        assert before.returncode == EXIT_ACCEPTANCE_FAILED
        assert "placeholder" in before.stdout
        apply_evidence(sandbox, scenario_id)
        after = run(sandbox, "verify", scenario_id)
        assert after.returncode == EXIT_OK, after.stdout
        assert "FAIL" not in after.stdout

    @pytest.mark.parametrize("scenario_id", EVIDENCE_SCENARIOS)
    def test_a_missing_evidence_file_is_reported(self, sandbox: Path, scenario_id: str) -> None:
        run(sandbox, "start", scenario_id)
        evidence_path_of(sandbox, scenario_id).unlink()
        result = run(sandbox, "verify", scenario_id)
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "file not found" in result.stdout

    def test_an_evidence_file_replaced_by_a_symlink_is_never_read(self, sandbox: Path) -> None:
        secret = sandbox.parent / "outside_evidence.md"
        secret.write_text(
            "## 1. What I think the diff does\n\nnot yours to read\n", encoding="utf-8"
        )
        run(sandbox, "start", "review-pr")
        evidence = evidence_path_of(sandbox, "review-pr")
        evidence.unlink()
        evidence.symlink_to(secret)
        result = run(sandbox, "verify", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "symlink" in result.stderr
        assert "not yours to read" not in result.stdout

    def test_a_truncated_review_note_still_fails(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        trimmed = REVIEW_NOTES.split("### Finding 2")[0]
        evidence_path_of(sandbox, "review-pr").write_text(trimmed, encoding="utf-8")
        result = run(sandbox, "verify", "review-pr")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "### Finding" in result.stdout

    def test_a_decision_without_a_verdict_fails(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        evidence_path_of(sandbox, "review-pr").write_text(
            REVIEW_NOTES.replace(
                "- Decision: request changes, with the conditions listed below",
                "- Decision: I have mixed feelings about this one",
            ),
            encoding="utf-8",
        )
        result = run(sandbox, "verify", "review-pr")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "must mention one of" in result.stdout

    def test_a_finding_without_evidence_fails(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        weakened = REVIEW_NOTES.replace(
            "- Evidence: the issue requires non-negative operational magnitudes, but both\n"
            "  helpers return minus the absolute value, so overdue hours and cost are negative.",
            "- Evidence: looks wrong",
        )
        evidence_path_of(sandbox, "review-pr").write_text(weakened, encoding="utf-8")
        result = run(sandbox, "verify", "review-pr")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "characters of content" in result.stdout

    @pytest.mark.parametrize("scenario_id", EVIDENCE_SCENARIOS)
    def test_a_placeholder_outside_a_checked_section_still_fails(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        run(sandbox, "start", scenario_id)
        evidence_path_of(sandbox, scenario_id).write_text(
            EVIDENCE_FIXTURES[scenario_id] + "\n## Scratch\n\nTODO: tidy this up later.\n",
            encoding="utf-8",
        )
        result = run(sandbox, "verify", scenario_id)
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "no template placeholder is left anywhere in the file" in result.stdout

    @pytest.mark.parametrize("scenario_id", EVIDENCE_SCENARIOS)
    def test_a_placeholder_in_the_preamble_still_fails(
        self, sandbox: Path, scenario_id: str
    ) -> None:
        run(sandbox, "start", scenario_id)
        fixture = EVIDENCE_FIXTURES[scenario_id]
        title, _, rest = fixture.partition("\n")
        evidence_path_of(sandbox, scenario_id).write_text(
            f"{title}\n\nReviewer: <fill in>\n{rest}", encoding="utf-8"
        )
        result = run(sandbox, "verify", scenario_id)
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "no template placeholder is left anywhere in the file" in result.stdout


# ---------------------------------------------------------------------------
# State conflicts and wrong identifiers
# ---------------------------------------------------------------------------


class TestStateConflicts:
    def test_only_one_scenario_can_be_active(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        result = run(sandbox, "start", "elective-cli")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert "already active" in result.stderr
        assert not (sandbox / "workshop/scenarios/elective-cli/work").exists()

    def test_verify_refuses_a_scenario_that_is_not_active(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        result = run(sandbox, "verify", "elective-cli")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert "not the active scenario" in result.stderr

    def test_reset_refuses_a_scenario_that_is_not_active(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        result = run(sandbox, "reset", "elective-cli")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert (sandbox / "workshop/scenarios/review-pr/work/review_notes.md").is_file()

    def test_verify_without_an_active_scenario(self, sandbox: Path) -> None:
        result = run(sandbox, "verify", "review-pr")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert "not active" in result.stderr

    def test_reset_without_an_active_scenario(self, sandbox: Path) -> None:
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert "nothing to reset" in result.stderr

    def test_resync_without_an_active_scenario(self, sandbox: Path) -> None:
        result = run(sandbox, "resync", "review-pr", "--blocked-at", "implement-test")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert "not active" in result.stderr

    def test_status_without_an_active_scenario(self, sandbox: Path) -> None:
        result = run(sandbox, "status")
        assert result.returncode == EXIT_OK
        assert "Active scenario: none" in result.stdout

    @pytest.mark.parametrize("command", ["start", "verify", "reset", "fallback"])
    def test_unknown_scenario_id_is_refused(self, sandbox: Path, command: str) -> None:
        result = run(sandbox, command, "does-not-exist")
        assert result.returncode == EXIT_ERROR
        assert "unknown scenario id" in result.stderr
        assert "incident-service-rate" in result.stderr

    def test_resync_refuses_a_scenario_that_is_not_active(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        result = run(sandbox, "resync", "elective-cli", "--blocked-at", "review")
        assert result.returncode == EXIT_STATE_CONFLICT
        assert "not the active scenario" in result.stderr

    def test_corrupt_state_is_reported_with_recovery_advice(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        (sandbox / ".workshop-state" / "state.json").write_text("{ broken", encoding="utf-8")
        result = run(sandbox, "status")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert ".workshop-state" in result.stderr

    def test_state_with_an_unknown_schema_is_refused(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        path = sandbox / ".workshop-state" / "state.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["schema_version"] = 99
        path.write_text(json.dumps(data), encoding="utf-8")
        assert run(sandbox, "status").returncode == EXIT_INVALID_ARTIFACT

    def test_interrupted_staging_is_recoverable(self, sandbox: Path) -> None:
        before = tree_state(sandbox)
        run(sandbox, "start", "review-pr")
        path = sandbox / ".workshop-state" / "state.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["phase"] = "staging"
        path.write_text(json.dumps(data), encoding="utf-8")

        assert "INTERRUPTED" in run(sandbox, "status").stdout

        blocked = run(sandbox, "start", "elective-cli")
        assert blocked.returncode == EXIT_STATE_CONFLICT
        assert "interrupted" in blocked.stderr

        assert run(sandbox, "verify", "review-pr").returncode == EXIT_STATE_CONFLICT

        recovered = run(sandbox, "reset", "review-pr")
        assert recovered.returncode == EXIT_OK
        assert tree_state(sandbox) == before
        assert not path.exists()

    def test_state_file_is_not_world_readable(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        mode = stat.S_IMODE((sandbox / ".workshop-state" / "state.json").stat().st_mode)
        assert mode == 0o600

    def test_state_records_repository_identity_and_no_secrets(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        assert state["repo_root"] == str(sandbox)
        assert "git" in state
        raw = (sandbox / ".workshop-state" / "state.json").read_text(encoding="utf-8")
        for marker in ("token", "password", "secret", "Bearer"):
            assert marker not in raw


# ---------------------------------------------------------------------------
# Pre-existing targets, backups, and transactional staging
# ---------------------------------------------------------------------------


class TestTransactionalStaging:
    def test_pre_existing_target_is_backed_up_and_restored_byte_for_byte(
        self, sandbox: Path
    ) -> None:
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.parent.mkdir(parents=True)
        original = "# my own notes from an earlier run\n\nkeep me exactly\n"
        target.write_text(original, encoding="utf-8")
        target.chmod(0o640)
        original_mode = stat.S_IMODE(target.stat().st_mode)

        assert run(sandbox, "start", "review-pr").returncode == EXIT_OK
        assert target.read_text(encoding="utf-8") != original
        record = first_target_record(sandbox)
        assert record["existed_before"] is True
        assert record["pre_mode"] == f"{original_mode:04o}"
        backup = sandbox / str(record["backup"])
        assert backup.read_text(encoding="utf-8") == original

        assert run(sandbox, "reset", "review-pr").returncode == EXIT_OK
        assert target.read_text(encoding="utf-8") == original
        assert stat.S_IMODE(target.stat().st_mode) == original_mode

    def test_staging_failure_rolls_back_completely(self, sandbox: Path) -> None:
        blocker = sandbox / "workshop/scenarios/incident-service-rate/work"
        blocker.write_text("not a directory\n", encoding="utf-8")
        before = tree_state(sandbox)
        result = run(sandbox, "start", "incident-service-rate")
        assert result.returncode == EXIT_ERROR
        assert "rolled back" in result.stderr
        assert tree_state(sandbox) == before
        assert not (sandbox / ".workshop-state" / "state.json").exists()

    def test_a_directory_where_a_target_belongs_is_refused_before_mutation(
        self, sandbox: Path
    ) -> None:
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.mkdir(parents=True)
        result = run(sandbox, "start", "review-pr")
        assert result.returncode == EXIT_ERROR
        assert "directory" in result.stderr
        assert not (sandbox / ".workshop-state" / "state.json").exists()

    def test_backups_are_removed_after_a_successful_reset(self, sandbox: Path) -> None:
        run(sandbox, "start", "elective-mcp")
        run(sandbox, "reset", "elective-mcp")
        assert not (sandbox / ".workshop-state" / "backups" / "elective-mcp").exists()

    def test_reset_refuses_a_tampered_backup(self, sandbox: Path) -> None:
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.parent.mkdir(parents=True)
        target.write_text("original\n", encoding="utf-8")
        run(sandbox, "start", "review-pr")
        backup = sandbox / str(first_target_record(sandbox)["backup"])
        backup.write_text("tampered\n", encoding="utf-8")
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_ERROR
        assert "does not match its recorded hash" in result.stderr

    def test_reset_archives_extra_files_and_restores_the_tree_exactly(self, sandbox: Path) -> None:
        before = tree_state(sandbox)
        run(sandbox, "start", "review-pr")
        work = sandbox / "workshop/scenarios/review-pr/work"
        (work / "scratch_notes.md").write_text("thinking out loud\n", encoding="utf-8")
        (work / "deeper").mkdir()
        (work / "deeper" / "draft.md").write_text("a second thought\n", encoding="utf-8")
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_OK, result.stderr
        assert not work.exists()
        assert tree_state(sandbox) == before
        archived = archived_files(sandbox, "review-pr")
        assert "workshop/scenarios/review-pr/work/scratch_notes.md" in archived
        assert "workshop/scenarios/review-pr/work/deeper/draft.md" in archived
        assert archived["workshop/scenarios/review-pr/work/scratch_notes.md"] == (
            "thinking out loud\n"
        )

    def test_reset_archives_a_mode_only_change(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.chmod(0o600)
        assert "[mode-changed]" in run(sandbox, "status").stdout
        assert run(sandbox, "reset", "review-pr").returncode == EXIT_OK
        assert "workshop/scenarios/review-pr/work/review_notes.md" in archived_files(
            sandbox, "review-pr"
        )

    def test_archives_from_the_same_second_do_not_collide(self, sandbox: Path) -> None:
        for content in ("first attempt\n", "second attempt\n"):
            run(sandbox, "start", "review-pr")
            evidence_path_of(sandbox, "review-pr").write_text(content, encoding="utf-8")
            assert run(sandbox, "reset", "review-pr").returncode == EXIT_OK
        archives = sorted(
            path.name for path in (sandbox / ".workshop-state" / "attempts" / "review-pr").iterdir()
        )
        assert len(archives) == 2
        assert len(set(archives)) == 2

    def test_an_oversized_attempt_file_is_refused_with_state_intact(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        big = sandbox / "workshop/scenarios/review-pr/work/huge.bin"
        big.write_bytes(b"x" * (3 * 1024 * 1024))
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_ERROR
        assert "refusing to archive" in result.stderr
        assert big.is_file()
        assert (sandbox / ".workshop-state" / "state.json").is_file()
        assert "Active scenario: review-pr" in run(sandbox, "status").stdout

    def test_a_target_replaced_by_a_directory_is_reported_not_crashed(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.unlink()
        target.mkdir()
        status = run(sandbox, "status")
        assert status.returncode == EXIT_OK
        assert "[replaced-by-directory]" in status.stdout
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_ERROR
        assert "directory" in result.stderr
        assert "Traceback" not in result.stderr
        assert (sandbox / ".workshop-state" / "state.json").is_file()

    def test_an_unwritable_state_directory_fails_actionably(self, sandbox: Path) -> None:
        state_dir = sandbox / ".workshop-state"
        state_dir.mkdir()
        state_dir.chmod(0o500)
        try:
            result = run(sandbox, "start", "review-pr")
            assert result.returncode == EXIT_ERROR
            assert "cannot write" in result.stderr
            assert "Traceback" not in result.stderr
            assert not (sandbox / "workshop/scenarios/review-pr/work").exists()
        finally:
            state_dir.chmod(0o700)


# ---------------------------------------------------------------------------
# Acceptance command execution
# ---------------------------------------------------------------------------


class TestAcceptanceExecution:
    def _probe(self, sandbox: Path, script: str, timeout: int = 60) -> None:
        write_custom_scenario(
            sandbox,
            "sandbox-probe",
            base_command_manifest(
                "sandbox-probe",
                ["{python}", "workshop/scenarios/sandbox-probe/work/probe.py"],
                timeout=timeout,
            ),
            {"probe.py.txt": script},
        )

    def test_timeout_is_enforced_and_reported(self, sandbox: Path) -> None:
        self._probe(sandbox, "import time\ntime.sleep(30)\n", timeout=2)
        run(sandbox, "start", "sandbox-probe")
        result = run(sandbox, "verify", "sandbox-probe")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "TIMEOUT" in result.stdout

    def test_output_is_sanitised_and_truncated(self, sandbox: Path) -> None:
        script = (
            "import sys\n"
            "print('token ' + 'ghp_' + 'A' * 30)\n"
            "print('cwd ' + __file__)\n"
            "for index in range(200):\n"
            "    print('line', index)\n"
            "sys.exit(1)\n"
        )
        self._probe(sandbox, script)
        run(sandbox, "start", "sandbox-probe")
        result = run(sandbox, "verify", "sandbox-probe")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "ghp_" not in result.stdout
        assert "<redacted>" in result.stdout
        assert str(sandbox) not in result.stdout
        assert "truncated" in result.stdout
        assert "line 199" not in result.stdout

    def test_a_passing_command_reports_success(self, sandbox: Path) -> None:
        self._probe(sandbox, "print('all good')\n")
        run(sandbox, "start", "sandbox-probe")
        result = run(sandbox, "verify", "sandbox-probe")
        assert result.returncode == EXIT_OK
        assert "Summary: 1/1 acceptance checks passed" in result.stdout

    def test_commands_run_from_the_repository_root(self, sandbox: Path) -> None:
        script = (
            "import pathlib, sys\n"
            "target = pathlib.Path('workshop/scenarios/catalogue.json')\n"
            "sys.exit(0 if target.is_file() else 1)\n"
        )
        self._probe(sandbox, script)
        run(sandbox, "start", "sandbox-probe")
        assert run(sandbox, "verify", "sandbox-probe").returncode == EXIT_OK

    def test_missing_prerequisite_is_reported_before_staging(self, sandbox: Path) -> None:
        path = sandbox / "workshop" / "scenarios" / "capstone-transfer" / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["required_imports"] = ["a_module_that_is_not_installed"]
        path.write_text(json.dumps(data), encoding="utf-8")
        result = run(sandbox, "start", "capstone-transfer")
        assert result.returncode == EXIT_PREREQUISITE
        assert "a_module_that_is_not_installed" in result.stderr
        assert not (sandbox / "workshop/scenarios/capstone-transfer/work").exists()

    def test_acceptance_commands_do_not_inherit_caller_secrets(self, sandbox: Path) -> None:
        script = (
            "import os, sys\n"
            "leaked = [name for name in ('GITHUB_TOKEN', 'AWS_SECRET_ACCESS_KEY',\n"
            "         'LEGACY_API_TOKEN', 'NPM_TOKEN') if name in os.environ]\n"
            "print('leaked:', leaked)\n"
            "for name, value in sorted(os.environ.items()):\n"
            "    print(name, '=', value)\n"
            "sys.exit(1)\n"
        )
        self._probe(sandbox, script)
        secrets = {
            "GITHUB_TOKEN": "ghp_" + "s" * 30,
            "AWS_SECRET_ACCESS_KEY": "AKIA" + "Z" * 16,
            "LEGACY_API_TOKEN": "legacy-super-secret-value-42",
            "NPM_TOKEN": "npm-secret-value-42",
        }
        run(sandbox, "start", "sandbox-probe", env=secrets)
        result = run(sandbox, "verify", "sandbox-probe", env=secrets)
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        assert "leaked: []" in result.stdout
        for value in secrets.values():
            assert value not in result.stdout
            assert value not in result.stderr

    def test_the_minimal_environment_still_runs_python_and_unittest(self, sandbox: Path) -> None:
        script = (
            "import subprocess, sys\n"
            "done = subprocess.run([sys.executable, '-c', 'import unittest, json, pathlib'],\n"
            "                      check=False)\n"
            "sys.exit(done.returncode)\n"
        )
        self._probe(sandbox, script)
        run(sandbox, "start", "sandbox-probe")
        assert run(sandbox, "verify", "sandbox-probe").returncode == EXIT_OK

    def test_embedded_and_assigned_credentials_are_redacted(self, sandbox: Path) -> None:
        script = (
            "import sys\n"
            "print('TOKEN=' + 'ghp_' + 'A' * 30)\n"
            "print('Authorization: Bearer ' + 'B' * 40)\n"
            "print('api_key=' + 'plain-looking-value-123456')\n"
            "print('password: ' + 'hunter2-hunter2')\n"
            "print('config: client_secret=' + 'C' * 24 + ' rest of line')\n"
            "print('url=https://example.invalid/x?access_token=' + 'D' * 24)\n"
            "sys.exit(1)\n"
        )
        self._probe(sandbox, script)
        run(sandbox, "start", "sandbox-probe")
        result = run(sandbox, "verify", "sandbox-probe")
        assert result.returncode == EXIT_ACCEPTANCE_FAILED
        for leaked in (
            "ghp_" + "A" * 30,
            "B" * 40,
            "plain-looking-value-123456",
            "hunter2-hunter2",
            "C" * 24,
            "D" * 24,
        ):
            assert leaked not in result.stdout
        assert result.stdout.count("<redacted>") >= 6


# ---------------------------------------------------------------------------
# The state file is untrusted input
# ---------------------------------------------------------------------------


class TestUntrustedState:
    def _secret_outside(self, sandbox: Path) -> Path:
        secret = sandbox.parent / "outside_secret.txt"
        secret.write_text("not yours to read\n", encoding="utf-8")
        return secret

    def test_state_file_replaced_by_directory_is_actionable(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        state_path = sandbox / ".workshop-state" / "state.json"
        state_path.unlink()
        state_path.mkdir()

        result = run(sandbox, "reset", "review-pr")

        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "not a regular file" in result.stderr
        assert "Traceback" not in result.stderr

    @pytest.mark.parametrize(
        "bad_path",
        [
            "/etc/passwd",
            "../../../../etc/passwd",
            "workshop/scenarios/review-pr/manifest.json",
            "workshop/scenarios/other/work/notes.md",
            "outside/core/engine.py",
        ],
    )
    def test_a_tampered_target_path_is_refused(self, sandbox: Path, bad_path: str) -> None:
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        targets = state["targets"]
        assert isinstance(targets, list)
        targets[0]["path"] = bad_path
        write_state(sandbox, state)
        for command in (["status"], ["reset", "review-pr"], ["verify", "review-pr"]):
            result = run(sandbox, *command)
            assert result.returncode == EXIT_INVALID_ARTIFACT, command
            assert "Traceback" not in result.stderr
        assert (sandbox / "workshop/scenarios/review-pr/manifest.json").is_file()

    def test_a_tampered_backup_path_cannot_read_outside_the_repository(self, sandbox: Path) -> None:
        secret = self._secret_outside(sandbox)
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.parent.mkdir(parents=True)
        target.write_text("mine\n", encoding="utf-8")
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        targets = state["targets"]
        assert isinstance(targets, list)
        targets[0]["backup"] = "../outside_secret.txt"
        write_state(sandbox, state)
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "not yours to read" not in result.stdout
        assert secret.read_text(encoding="utf-8") == "not yours to read\n"

    def test_a_tampered_created_dir_cannot_delete_the_scenario(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        state["created_dirs"] = ["workshop/scenarios/review-pr"]
        write_state(sandbox, state)
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert (sandbox / "workshop/scenarios/review-pr/manifest.json").is_file()
        assert (sandbox / "workshop/scenarios/review-pr/brief.md").is_file()

    def test_state_from_another_checkout_is_refused(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        state["repo_root"] = "/somewhere/else"
        write_state(sandbox, state)
        result = run(sandbox, "status")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "different checkout" in result.stderr
        assert "reset" in result.stderr

    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("scenario_id", "../../etc"),
            ("started_at", "yesterday"),
            ("catalogue_sha256", "nothex"),
            ("manifest_sha256", ""),
        ],
    )
    def test_malformed_state_scalars_are_refused(self, sandbox: Path, key: str, value: str) -> None:
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        state[key] = value
        write_state(sandbox, state)
        result = run(sandbox, "status")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "Traceback" not in result.stderr

    @pytest.mark.parametrize("field_name", ["pre_sha256", "pre_mode", "staged_mode"])
    def test_malformed_target_scalars_are_refused(self, sandbox: Path, field_name: str) -> None:
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.parent.mkdir(parents=True)
        target.write_text("mine\n", encoding="utf-8")
        run(sandbox, "start", "review-pr")
        state = state_json(sandbox)
        targets = state["targets"]
        assert isinstance(targets, list)
        targets[0][field_name] = "0999"
        write_state(sandbox, state)
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert target.read_text(encoding="utf-8") != "mine\n"

    def test_a_symlinked_state_directory_is_refused(self, sandbox: Path) -> None:
        elsewhere = sandbox.parent / "state-elsewhere"
        elsewhere.mkdir()
        (sandbox / ".workshop-state").symlink_to(elsewhere, target_is_directory=True)
        result = run(sandbox, "start", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "symlink" in result.stderr
        assert not any(elsewhere.iterdir())

    def test_a_symlinked_backup_is_not_restored_through(self, sandbox: Path) -> None:
        secret = self._secret_outside(sandbox)
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.parent.mkdir(parents=True)
        target.write_text("mine\n", encoding="utf-8")
        run(sandbox, "start", "review-pr")
        backup = sandbox / str(first_target_record(sandbox)["backup"])
        backup.unlink()
        backup.symlink_to(secret)
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "symlink" in result.stderr
        assert "not yours to read" not in target.read_text(encoding="utf-8")
        assert secret.read_text(encoding="utf-8") == "not yours to read\n"
        assert (sandbox / ".workshop-state" / "state.json").is_file()

    def test_a_target_replaced_by_a_symlink_is_never_followed(self, sandbox: Path) -> None:
        secret = self._secret_outside(sandbox)
        run(sandbox, "start", "review-pr")
        target = sandbox / "workshop/scenarios/review-pr/work/review_notes.md"
        target.unlink()
        target.symlink_to(secret)
        status = run(sandbox, "status")
        assert status.returncode == EXIT_OK
        assert "[replaced-by-symlink]" in status.stdout
        assert "not yours to read" not in status.stdout
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "symlink" in result.stderr
        assert secret.is_file()
        assert secret.read_text(encoding="utf-8") == "not yours to read\n"
        assert not archived_files(sandbox, "review-pr")


# ---------------------------------------------------------------------------
# Multi-target staging and interrupted starts
# ---------------------------------------------------------------------------


class TestMultiTargetStaging:
    """elective-customization stages two files; capstone-transfer stages three."""

    def _two_target_scenario(self, sandbox: Path) -> None:
        """A sandbox scenario whose second target lives in a nested directory."""
        scenario_id = "sandbox-pair"
        manifest = base_command_manifest(scenario_id, ["{python}", "-c", "pass"])
        manifest["stage"] = [
            {
                "payload": f"workshop/scenarios/{scenario_id}/payloads/first.py.txt",
                "target": f"workshop/scenarios/{scenario_id}/work/first.py",
                "description": "First target.",
            },
            {
                "payload": f"workshop/scenarios/{scenario_id}/payloads/second.py.txt",
                "target": f"workshop/scenarios/{scenario_id}/work/nested/second.py",
                "description": "Second target, one directory deeper.",
            },
        ]
        write_custom_scenario(
            sandbox,
            scenario_id,
            manifest,
            {"first.py.txt": "# staged first\n", "second.py.txt": "# staged second\n"},
        )

    def test_failure_on_a_later_target_restores_an_earlier_pre_existing_one(
        self, sandbox: Path
    ) -> None:
        self._two_target_scenario(sandbox)
        work = sandbox / "workshop/scenarios/sandbox-pair/work"
        nested = work / "nested"
        nested.mkdir(parents=True)
        first = work / "first.py"
        original = "# my earlier draft\n"
        first.write_text(original, encoding="utf-8")
        first.chmod(0o640)
        before = tree_state(sandbox)
        nested.chmod(0o500)
        try:
            result = run(sandbox, "start", "sandbox-pair")
        finally:
            nested.chmod(0o700)
        assert result.returncode == EXIT_ERROR
        assert "rolled back" in result.stderr
        assert "Traceback" not in result.stderr
        assert first.read_text(encoding="utf-8") == original
        assert stat.S_IMODE(first.stat().st_mode) == 0o640
        assert not (nested / "second.py").exists()
        assert not (sandbox / ".workshop-state" / "state.json").exists()
        assert tree_state(sandbox) == before

    def test_an_unreadable_payload_fails_before_anything_is_staged(self, sandbox: Path) -> None:
        blocked = (
            sandbox
            / "workshop/scenarios/elective-customization/payloads/customization_notes.md.txt"
        )
        blocked.chmod(0o000)
        try:
            result = run(sandbox, "start", "elective-customization")
        finally:
            blocked.chmod(0o644)
        assert result.returncode == EXIT_ERROR
        assert "cannot read" in result.stderr
        assert "Traceback" not in result.stderr
        assert not (sandbox / "workshop/scenarios/elective-customization/work").exists()
        assert not (sandbox / ".workshop-state" / "state.json").exists()

    def test_backups_for_every_target_exist_before_any_payload_is_written(
        self, sandbox: Path
    ) -> None:
        work = sandbox / "workshop/scenarios/capstone-transfer/work"
        work.mkdir(parents=True)
        contents = {
            "daily_export.py": "# mine 1\n",
            "test_daily_export.py": "# mine 2\n",
            "NOTES.md": "# mine 3\n",
        }
        for name, body in contents.items():
            (work / name).write_text(body, encoding="utf-8")
        assert run(sandbox, "start", "capstone-transfer").returncode == EXIT_OK
        backups = sandbox / ".workshop-state" / "backups" / "capstone-transfer"
        archived = sorted(path.read_text(encoding="utf-8") for path in backups.iterdir())
        assert archived == sorted(contents.values())
        assert run(sandbox, "reset", "capstone-transfer").returncode == EXIT_OK
        for name, body in contents.items():
            assert (work / name).read_text(encoding="utf-8") == body

    def test_a_crash_before_the_payload_was_written_still_restores(self, sandbox: Path) -> None:
        target = sandbox / "workshop/scenarios/elective-cli/work/permission_policy.md"
        target.parent.mkdir(parents=True)
        original = "# pre-existing policy\n"
        target.write_text(original, encoding="utf-8")
        run(sandbox, "start", "elective-cli")
        # Reconstruct the on-disk situation of a crash between the backup and the
        # payload write: state still says 'staging', the target is untouched.
        target.write_text(original, encoding="utf-8")
        state = state_json(sandbox)
        state["phase"] = "staging"
        write_state(sandbox, state)
        result = run(sandbox, "reset", "elective-cli")
        assert result.returncode == EXIT_OK, result.stderr
        assert target.read_text(encoding="utf-8") == original
        assert not (sandbox / ".workshop-state" / "state.json").exists()

    def test_a_crash_before_the_backup_was_written_still_restores(self, sandbox: Path) -> None:
        target = sandbox / "workshop/scenarios/elective-cli/work/permission_policy.md"
        target.parent.mkdir(parents=True)
        original = "# pre-existing policy\n"
        target.write_text(original, encoding="utf-8")
        run(sandbox, "start", "elective-cli")
        backup = sandbox / str(first_target_record(sandbox)["backup"])
        backup.unlink()
        target.write_text(original, encoding="utf-8")
        state = state_json(sandbox)
        state["phase"] = "staging"
        write_state(sandbox, state)
        result = run(sandbox, "reset", "elective-cli")
        assert result.returncode == EXIT_OK, result.stderr
        assert target.read_text(encoding="utf-8") == original

    def test_a_missing_backup_with_a_changed_target_refuses_to_guess(self, sandbox: Path) -> None:
        target = sandbox / "workshop/scenarios/elective-cli/work/permission_policy.md"
        target.parent.mkdir(parents=True)
        target.write_text("# pre-existing policy\n", encoding="utf-8")
        run(sandbox, "start", "elective-cli")
        backup = sandbox / str(first_target_record(sandbox)["backup"])
        backup.unlink()
        result = run(sandbox, "reset", "elective-cli")
        assert result.returncode == EXIT_ERROR
        assert "backup for" in result.stderr
        assert (sandbox / ".workshop-state" / "state.json").is_file()


# ---------------------------------------------------------------------------
# Reset is the unconditional recovery route
# ---------------------------------------------------------------------------


class TestRecoveryWithoutTheCatalogue:
    def test_reset_works_after_the_manifest_is_deleted(self, sandbox: Path) -> None:
        before = tree_state(sandbox)
        run(sandbox, "start", "capstone-transfer")
        (sandbox / "workshop/scenarios/capstone-transfer/manifest.json").unlink()
        result = run(sandbox, "reset", "capstone-transfer")
        assert result.returncode == EXIT_OK, result.stderr
        assert not (sandbox / "workshop/scenarios/capstone-transfer/work").exists()
        assert not (sandbox / ".workshop-state" / "state.json").exists()
        restored = tree_state(sandbox)
        missing = set(before) - set(restored)
        assert missing == {"workshop/scenarios/capstone-transfer/manifest.json"}

    def test_reset_works_after_the_catalogue_is_corrupted(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        (sandbox / "workshop/scenarios/catalogue.json").write_text("{ broken", encoding="utf-8")
        result = run(sandbox, "reset", "review-pr")
        assert result.returncode == EXIT_OK, result.stderr
        assert not (sandbox / "workshop/scenarios/review-pr/work").exists()

    def test_reset_works_after_the_manifest_is_corrupted(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        (sandbox / "workshop/scenarios/review-pr/manifest.json").write_text(
            "{ not json at all", encoding="utf-8"
        )
        assert run(sandbox, "reset", "review-pr").returncode == EXIT_OK

    def test_status_stays_useful_when_the_catalogue_is_broken(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        (sandbox / "workshop/scenarios/catalogue.json").write_text("{ broken", encoding="utf-8")
        result = run(sandbox, "status")
        assert result.returncode == EXIT_OK
        assert "Active scenario: review-pr" in result.stdout
        assert "unavailable" in result.stdout
        assert "[unchanged]" in result.stdout

    def test_verify_refuses_a_manifest_edited_after_start(self, sandbox: Path) -> None:
        run(sandbox, "start", "capstone-transfer")
        path = sandbox / "workshop/scenarios/capstone-transfer/manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["acceptance"]["commands"][0]["argv"] = ["{python}", "-c", "pass"]
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = run(sandbox, "verify", "capstone-transfer")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "definition changed after start" in result.stderr

    def test_verify_refuses_a_catalogue_edited_after_start(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        path = sandbox / "workshop/scenarios/catalogue.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["description"] = "edited after start"
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        result = run(sandbox, "verify", "review-pr")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "definition changed after start" in result.stderr

    def test_an_unedited_definition_still_verifies(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        apply_evidence(sandbox, "review-pr")
        assert run(sandbox, "verify", "review-pr").returncode == EXIT_OK


# ---------------------------------------------------------------------------
# Fallbacks
# ---------------------------------------------------------------------------


class TestFallbacks:
    def test_fallback_works_while_another_scenario_is_active(self, sandbox: Path) -> None:
        run(sandbox, "start", "review-pr")
        result = run(sandbox, "fallback", "capstone-transfer")
        assert result.returncode == EXIT_OK
        assert "capstone-transfer" in result.stdout

    def test_fallback_output_is_deterministic(self, sandbox: Path) -> None:
        first = run(sandbox, "fallback", "elective-mcp").stdout
        second = run(sandbox, "fallback", "elective-mcp").stdout
        assert first == second

    def test_missing_fallback_directory_is_reported(self, sandbox: Path) -> None:
        shutil.rmtree(sandbox / "workshop" / "fallbacks" / "elective-cli")
        result = run(sandbox, "fallback", "elective-cli")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "fallback directory is missing" in result.stderr

    def test_missing_fallback_readme_is_reported(self, sandbox: Path) -> None:
        (sandbox / "workshop" / "fallbacks" / "elective-cli" / "README.md").unlink()
        result = run(sandbox, "fallback", "elective-cli")
        assert result.returncode == EXIT_INVALID_ARTIFACT
        assert "inventory is missing" in result.stderr

    @pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
    def test_every_fallback_has_a_readme_and_content(self, scenario_id: str) -> None:
        directory = FALLBACK_ROOT / scenario_id
        assert (directory / "README.md").is_file()
        files = [path for path in directory.rglob("*") if path.is_file()]
        assert len(files) >= 3

    @pytest.mark.parametrize("scenario_id", ALL_SCENARIOS)
    def test_staged_copies_match_the_payloads_byte_for_byte(self, scenario_id: str) -> None:
        payloads = sorted((SCENARIO_ROOT / scenario_id / "payloads").glob("*.txt"))
        assert payloads
        for payload in payloads:
            copy = FALLBACK_ROOT / scenario_id / "staged_copy" / payload.name
            assert copy.is_file(), f"missing offline copy for {payload.name}"
            assert copy.read_bytes() == payload.read_bytes()

    def test_review_package_is_complete_and_offline(self) -> None:
        directory = FALLBACK_ROOT / "review-pr"
        for name in (
            "issue.md",
            "pr_description.md",
            "pr_diff.patch",
            "session_transcript.md",
            "review_thread.md",
            "captured_code_review.md",
        ):
            assert (directory / name).is_file()

    def test_captured_review_misses_a_human_context_finding(self) -> None:
        captured = (FALLBACK_ROOT / "review-pr" / "captured_code_review.md").read_text(
            encoding="utf-8"
        )
        assert "value_at_risk" not in captured
        assert "response shape" not in captured
        assert "No blocking issues found in" in captured

    def test_captured_review_contains_a_comment_worth_suppressing(self) -> None:
        captured = (FALLBACK_ROOT / "review-pr" / "captured_code_review.md").read_text(
            encoding="utf-8"
        )
        assert "float" in captured

    def test_captured_acceptance_output_ships_for_every_scenario(self) -> None:
        for scenario_id in ALL_SCENARIOS:
            captured = FALLBACK_ROOT / scenario_id / "captured_acceptance_output.txt"
            assert captured.is_file()
            assert "acceptance checks passed" in captured.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Content hygiene of the shipped artifacts
# ---------------------------------------------------------------------------

SECRET_MARKERS = (
    "ghp_",
    "gho_",
    "github_pat_",
    "AKIA",
    "-----BEGIN",
    "xoxb-",
    "password=",
    "passwd=",
    "secret=",
    "api_key=",
    "Authorization: Bearer ",
)

ALLOWED_URL_HOSTS = (
    "docs.github.com",
    "code.visualstudio.com",
    "example.invalid",
)

ALLOWED_URL_PREFIXES = (
    "https://github.blog/changelog/",
    "https://github.com/github/github-mcp-server",
)


class TestContentHygiene:
    def test_no_file_is_named_like_an_answer_key(self) -> None:
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            lowered = path.name.lower()
            assert "answer" not in lowered
            assert "solution" not in lowered
            assert "bug" not in lowered

    def test_no_secret_markers_in_workshop_content(self) -> None:
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            text = path.read_text(encoding="utf-8")
            for marker in SECRET_MARKERS:
                assert marker not in text, f"{path} contains {marker!r}"

    def test_urls_are_limited_to_public_documentation(self) -> None:
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            for line in path.read_text(encoding="utf-8").splitlines():
                for scheme in ("http://", "https://"):
                    index = line.find(scheme)
                    while index != -1:
                        rest = line[index + len(scheme) :]
                        host = rest.split("/")[0].strip("<>()[], ")
                        allowed_prefix = any(
                            line[index:].startswith(prefix) for prefix in ALLOWED_URL_PREFIXES
                        )
                        assert host in ALLOWED_URL_HOSTS or allowed_prefix, (
                            f"{path}: unexpected host {host}"
                        )
                        index = line.find(scheme, index + 1)

    def test_no_email_addresses_in_workshop_content(self) -> None:
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            for token in path.read_text(encoding="utf-8").split():
                cleaned = token.strip("<>(),.;:\"'`")
                if "@" in cleaned and "." in cleaned.split("@")[-1]:
                    raise AssertionError(f"{path} may contain an address: {cleaned}")

    def test_workshop_content_and_tool_are_ascii(self) -> None:
        for path in [TOOL_PATH, *iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT)]:
            data = path.read_bytes()
            assert all(byte <= 0x7F for byte in data), f"{path} contains non-ASCII bytes"

    def test_every_scenario_directory_is_in_the_catalogue(self) -> None:
        catalogue = json.loads((SCENARIO_ROOT / "catalogue.json").read_text(encoding="utf-8"))
        listed = catalogue["scenarios"]
        on_disk = sorted(
            path.name
            for path in SCENARIO_ROOT.iterdir()
            if path.is_dir() and path.name != "__pycache__"
        )
        assert sorted(listed) == on_disk
        assert listed == list(ALL_SCENARIOS)

    def test_no_staged_work_directory_is_committed(self) -> None:
        for scenario_id in ALL_SCENARIOS:
            assert not (SCENARIO_ROOT / scenario_id / "work").exists()

    def test_state_directory_is_ignored_by_git(self) -> None:
        gitignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        assert ".workshop-state/" in gitignore

    def test_payload_sources_are_inert_text_files(self) -> None:
        for scenario_id in ALL_SCENARIOS:
            for payload in (SCENARIO_ROOT / scenario_id / "payloads").iterdir():
                assert payload.suffix == ".txt", f"{payload} would be linted or collected"

    def test_no_python_module_is_shipped_under_workshop(self) -> None:
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            assert path.suffix != ".py", f"{path} would be linted or collected"

    def test_the_tool_never_uses_a_shell_or_dynamic_evaluation(self) -> None:
        source = TOOL_PATH.read_text(encoding="utf-8")
        assert "shell=True" not in source
        assert "os.system" not in source
        assert "eval(" not in source
        assert "exec(" not in source

    def test_scenario_briefs_do_not_leak_a_solution(self) -> None:
        forbidden = (
            "the fix is to",
            "the answer is",
            "the defect is in",
            "the bug is in",
            "root cause:",
            "correct implementation:",
        )
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            lowered = path.read_text(encoding="utf-8").lower()
            for phrase in forbidden:
                assert phrase not in lowered, f"{path} contains {phrase!r}"


# ---------------------------------------------------------------------------
# The MCP elective must describe the server this repository actually ships
# ---------------------------------------------------------------------------

MCP_SERVER_SOURCE = REPO_ROOT / "mittelwerk" / "mcp_server" / "server.py"
DOCUMENTED_READ_TOOLS = (
    "list_equipment",
    "get_dispatch_queue",
    "calculate_service_risk",
)
DOCUMENTED_WRITE_TOOLS = ("submit_work_order", "cancel_work_order")
VSCODE_SERVER_KEYS = {
    "type",
    "command",
    "args",
    "cwd",
    "env",
    "envFile",
    "dev",
    "sandboxEnabled",
}


def registered_tool_names() -> set[str]:
    """Tool names the shipped MCP server registers, read from its source."""
    source = MCP_SERVER_SOURCE.read_text(encoding="utf-8").splitlines()
    names: set[str] = set()
    pending = False
    for line in source:
        stripped = line.strip()
        if stripped.startswith("@mcp.tool("):
            pending = True
            continue
        if pending and (stripped.startswith("def ") or stripped.startswith("async def ")):
            names.add(stripped.split("def ", 1)[1].split("(", 1)[0].strip())
            pending = False
    return names


def flatten_markdown(path: Path) -> str:
    """Markdown text as one line, without quote markers or code ticks."""
    lines = []
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            stripped = stripped[1:].strip()
        lines.append(stripped.replace("`", ""))
    return " ".join(" ".join(lines).split())


class TestMcpElectiveMatchesTheServer:
    def _artifacts(self) -> list[Path]:
        return [
            SCENARIO_ROOT / "elective-mcp" / "fixtures" / "tool_inventory.md",
            SCENARIO_ROOT / "elective-mcp" / "fixtures" / "tool_call_log.md",
            SCENARIO_ROOT / "elective-mcp" / "brief.md",
            FALLBACK_ROOT / "elective-mcp" / "fixtures" / "tool_inventory.md",
            FALLBACK_ROOT / "elective-mcp" / "fixtures" / "tool_call_log.md",
        ]

    def test_the_source_registers_exactly_the_documented_tools(self) -> None:
        assert registered_tool_names() == set(DOCUMENTED_READ_TOOLS) | set(DOCUMENTED_WRITE_TOOLS)

    def test_the_inventory_lists_every_registered_tool(self) -> None:
        inventory = (SCENARIO_ROOT / "elective-mcp" / "fixtures" / "tool_inventory.md").read_text(
            encoding="utf-8"
        )
        for name in DOCUMENTED_READ_TOOLS + DOCUMENTED_WRITE_TOOLS:
            assert f"`{name}`" in inventory, f"{name} is missing from the tool inventory"

    def test_the_inventory_separates_capability_from_configuration(self) -> None:
        inventory = flatten_markdown(
            SCENARIO_ROOT / "elective-mcp" / "fixtures" / "tool_inventory.md"
        )
        assert "not registered at all" in inventory
        assert "not authorization" in inventory
        assert "sandboxEnabled" in inventory

    @pytest.mark.parametrize(
        "relative",
        [
            "workshop/scenarios/elective-mcp/fixtures/mcp_config_sample.json",
            "workshop/scenarios/elective-mcp/payloads/mcp_config_reduced.json.txt",
            "workshop/fallbacks/elective-mcp/fixtures/mcp_config_sample.json",
            "workshop/fallbacks/elective-mcp/staged_copy/mcp_config_reduced.json.txt",
        ],
    )
    def test_configurations_use_only_documented_vs_code_keys(self, relative: str) -> None:
        data = json.loads((REPO_ROOT / relative).read_text(encoding="utf-8"))
        assert set(data) <= {"servers", "inputs", "sandbox"}
        servers = data["servers"]
        assert isinstance(servers, dict)
        for name, server in servers.items():
            assert isinstance(server, dict), name
            unknown = set(server) - VSCODE_SERVER_KEYS
            assert not unknown, f"{relative}: {name} uses undocumented keys {sorted(unknown)}"
            assert server["type"] == "stdio"

    def test_the_config_notes_document_the_real_sandbox_keys(self) -> None:
        notes = (SCENARIO_ROOT / "elective-mcp" / "fixtures" / "config_notes.md").read_text(
            encoding="utf-8"
        )
        for key in (
            "filesystem.allowWrite",
            "filesystem.denyRead",
            "filesystem.denyWrite",
            "network.allowedDomains",
            "network.deniedDomains",
            "sandboxEnabled",
        ):
            assert key in notes
        assert "macOS and Linux only" in notes

    def test_the_sandbox_auto_approval_trade_off_is_explicit(self) -> None:
        for relative in (
            "workshop/scenarios/elective-mcp/fixtures/config_notes.md",
            "workshop/scenarios/elective-mcp/fixtures/tool_inventory.md",
            "workshop/scenarios/elective-mcp/brief.md",
            "workshop/fallbacks/elective-mcp/fixtures/config_notes.md",
            "workshop/fallbacks/elective-mcp/brief.md",
        ):
            text = flatten_markdown(REPO_ROOT / relative)
            assert "auto-approve" in text.lower(), f"{relative} omits the auto-approval trade"
            assert "sandboxEnabled" in text, relative

    def test_the_config_notes_quote_the_official_sandbox_wording(self) -> None:
        notes = flatten_markdown(SCENARIO_ROOT / "elective-mcp" / "fixtures" / "config_notes.md")
        assert (
            "tool confirmations are auto-approved because the server runs in a "
            "controlled environment" in notes
        )
        assert "code.visualstudio.com/docs/agents/reference/mcp-configuration" in notes

    def test_no_artifact_claims_sandboxed_calls_still_prompt(self) -> None:
        """The trade is confinement instead of confirmation, not both."""
        for path in iter_workshop_files(
            SCENARIO_ROOT / "elective-mcp", FALLBACK_ROOT / "elective-mcp"
        ):
            text = flatten_markdown(path).lower()
            for claim in (
                "sandbox and still be prompted",
                "sandboxed calls still prompt",
                "sandboxing adds a prompt",
                "prompts remain when sandboxed",
            ):
                assert claim not in text, f"{path} implies {claim!r}"

    def test_the_captured_log_states_what_would_change_under_a_sandbox(self) -> None:
        log = flatten_markdown(SCENARIO_ROOT / "elective-mcp" / "fixtures" / "tool_call_log.md")
        assert "sandboxEnabled=false" in log
        assert "no approval=prompted line at all" in log

    def test_the_inventory_template_asks_for_the_approval_boundary(self) -> None:
        template = (
            SCENARIO_ROOT / "elective-mcp" / "payloads" / "permission_inventory.md.txt"
        ).read_text(encoding="utf-8")
        assert "- Approval boundary:" in template
        manifest = json.loads(
            (SCENARIO_ROOT / "elective-mcp" / "manifest.json").read_text(encoding="utf-8")
        )
        labels = [field["label"] for field in manifest["acceptance"]["evidence"]["fields"]]
        assert "- Approval boundary:" in labels

    def test_no_invented_configuration_keys_survive_anywhere(self) -> None:
        invented = (
            "autoApprove",
            "readOnly",
            "maxResponseBytes",
            "allowedWorkspacePaths",
            "networkAccess",
        )
        for path in iter_workshop_files(SCENARIO_ROOT, FALLBACK_ROOT):
            text = path.read_text(encoding="utf-8")
            for key in invented:
                # Quoted form: the configuration key, not prose about annotations
                # such as readOnlyHint, which is a real piece of server metadata.
                assert f'"{key}"' not in text, f"{path} still teaches {key!r}"
                assert f"`{key}`" not in text, f"{path} still teaches {key!r}"

    def test_the_mcp_elective_ships_no_api_token(self) -> None:
        for path in iter_workshop_files(
            SCENARIO_ROOT / "elective-mcp", FALLBACK_ROOT / "elective-mcp"
        ):
            assert "QXM_API_TOKEN" not in path.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Baseline safety
# ---------------------------------------------------------------------------


class TestBaselineSafety:
    def test_start_verify_reset_cycles_leave_the_tree_untouched(self, sandbox: Path) -> None:
        before = tree_state(sandbox)
        for scenario_id in ("incident-service-rate", "review-pr", "capstone-transfer"):
            run(sandbox, "start", scenario_id)
            run(sandbox, "verify", scenario_id)
            run(sandbox, "reset", scenario_id)
        assert tree_state(sandbox) == before

    def test_nothing_outside_the_scenario_tree_is_touched(self, sandbox: Path) -> None:
        runtime = sandbox / "mittelwerk"
        runtime.mkdir()
        marker = runtime / "engine.py"
        marker.write_text("# baseline runtime\n", encoding="utf-8")
        run(sandbox, "start", "incident-service-rate")
        run(sandbox, "reset", "incident-service-rate")
        assert marker.read_text(encoding="utf-8") == "# baseline runtime\n"

    def test_no_scenario_stages_outside_its_own_work_directory(self, cli: types.ModuleType) -> None:
        catalogue = cli.load_catalogue(REPO_ROOT)
        for scenario_id, manifest in catalogue.manifests.items():
            for item in manifest.stage:
                assert item.target.as_posix().startswith(f"workshop/scenarios/{scenario_id}/work/")

    def test_the_repository_has_no_active_scenario_state(self) -> None:
        assert not (REPO_ROOT / ".workshop-state" / "state.json").exists()
