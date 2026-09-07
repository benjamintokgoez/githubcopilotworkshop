"""Release inputs are exact, source-bound, private, and never release approval."""

from __future__ import annotations

import importlib.metadata
import importlib.util
import json
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any, cast

import pytest

from scripts import workshop_release as release


def distribution(
    name: str, version: str = "1.0.0", direct: str | None = None
) -> importlib.metadata.Distribution:
    return cast(
        importlib.metadata.Distribution,
        SimpleNamespace(
            metadata={"Name": name},
            version=version,
            read_text=lambda filename: direct if filename == "direct_url.json" else None,
        ),
    )


@pytest.fixture
def repository(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "repository"
    root.mkdir()
    (root / "pyproject.toml").write_text('[project]\nname="mittelwerk"\nversion="1.0.0"\n')
    (root / "mittelwerk").mkdir()
    (root / "mittelwerk" / "__init__.py").write_text('"""Synthetic fixture."""\n')
    git = shutil.which("git")
    assert git is not None
    for args in (
        ["init", "--quiet"],
        ["add", "."],
        [
            "-c",
            "user.name=Workshop Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "--quiet",
            "-m",
            "Synthetic fixture",
        ],
    ):
        subprocess.run([git, *args], cwd=root, check=True, capture_output=True)  # noqa: S603
    monkeypatch.setattr(release, "REPO_ROOT", root)
    monkeypatch.setattr(
        importlib.util,
        "find_spec",
        lambda name: SimpleNamespace(origin=str(root / "mittelwerk" / "__init__.py")),
    )
    return root


@pytest.fixture
def installed(
    repository: Path, monkeypatch: pytest.MonkeyPatch
) -> list[importlib.metadata.Distribution]:
    packages = [
        distribution("Zebra_Package", "2.0rc1"),
        distribution("pip", "25.1"),
        distribution(
            "mittelwerk",
            direct=json.dumps({"url": repository.as_uri(), "dir_info": {"editable": True}}),
        ),
        distribution("Alpha.Package", "1.2.3"),
        # Source .egg-info and editable dist-info can both be visible in a real checkout.
        distribution("mittelwerk"),
    ]
    monkeypatch.setattr(importlib.metadata, "distributions", lambda: iter(packages))
    return packages


def manifest(path: Path) -> dict[str, Any]:
    return cast(dict[str, Any], json.loads((path / "manifest.json").read_text()))


def test_capture_check_and_deterministic_bytes(
    repository: Path, installed: list[importlib.metadata.Distribution], tmp_path: Path
) -> None:
    first, second = tmp_path / "first", tmp_path / "second"
    release.capture(repository, first)
    installed.reverse()
    release.capture(repository, second)
    for name in ("constraints.txt", "manifest.json"):
        assert (first / name).read_bytes() == (second / name).read_bytes()
    assert (first / "constraints.txt").read_text() == (
        "alpha-package==1.2.3\npip==25.1\nzebra-package==2.0rc1\n"
    )
    assert manifest(first)["source"]["dirty"] is False
    release.check(repository, first)


def test_snapshot_inside_repository_does_not_change_source_identity(
    repository: Path, installed: list[importlib.metadata.Distribution]
) -> None:
    snapshot = repository / "delivery"
    release.capture(repository, snapshot)
    release.check(repository, snapshot)
    assert manifest(snapshot)["source"]["dirty"] is False


def test_capture_never_overwrites(
    repository: Path, installed: list[importlib.metadata.Distribution], tmp_path: Path
) -> None:
    output = tmp_path / "existing"
    output.mkdir()
    (output / "keep").write_text("preserve")
    with pytest.raises(release.SnapshotError, match="already exists"):
        release.capture(repository, output)
    assert (output / "keep").read_text() == "preserve"


@pytest.mark.parametrize("change", ["version", "extra", "missing", "python", "architecture"])
def test_environment_mismatch(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    output = tmp_path / "snapshot"
    release.capture(repository, output)
    if change == "version":
        installed[0] = distribution("Zebra_Package", "2.1")
    elif change == "extra":
        installed.append(distribution("extra"))
    elif change == "missing":
        installed.pop(0)
    else:
        target = release.environment()
        target["python" if change == "python" else "machine"] = "different"
        monkeypatch.setattr(release, "environment", lambda: target)
    with pytest.raises(release.SnapshotError, match="mismatch|do not match"):
        release.check(repository, output)


@pytest.mark.parametrize("change", ["tracked", "untracked", "project", "revision"])
def test_current_source_is_bound(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    change: str,
) -> None:
    output = tmp_path / "snapshot"
    release.capture(repository, output)
    if change == "tracked":
        (repository / "mittelwerk" / "__init__.py").write_text("value = 1\n")
    elif change == "untracked":
        (repository / "new_module.py").write_text("value = 2\n")
    elif change == "project":
        (repository / "pyproject.toml").write_text('[project]\nname="mittelwerk"\nversion="2.0"\n')
    else:
        git = shutil.which("git")
        assert git is not None
        release._run(
            [
                git,
                "-c",
                "user.name=Workshop Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgsign=false",
                "commit",
                "--allow-empty",
                "-m",
                "Another revision",
            ],
            repository,
        )
    with pytest.raises(release.SnapshotError, match="source differs|project version differs"):
        release.check(repository, output)


def test_dirty_capture_is_identified_not_approved(
    repository: Path, installed: list[importlib.metadata.Distribution], tmp_path: Path
) -> None:
    (repository / "source_change.py").write_text("value = 1\n")
    output = tmp_path / "snapshot"
    release.capture(repository, output)
    data = manifest(output)
    assert data["source"]["dirty"] is True
    assert "not evidence of passed tests" in data["limitations"][0]
    assert "approved" not in data
    release.check(repository, output)


@pytest.mark.parametrize("kind", ["ancestor", "points-into-output"])
def test_source_links_are_rejected_before_output_exclusion(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    kind: str,
) -> None:
    output = tmp_path / "snapshot"
    if kind == "ancestor":
        directory = repository / "mittelwerk"
        external = tmp_path / "outside-source"
        directory.rename(external)
        directory.symlink_to(external, target_is_directory=True)
    else:
        (repository / "linked.py").symlink_to(output / "constraints.txt")
    with pytest.raises(release.SnapshotError, match="Source symlinks"):
        release.capture(repository, output)
    assert not output.exists()


@pytest.mark.parametrize(
    "direct",
    [
        '{"url":"https://private-user:secret@example.invalid/private/pkg.whl"}',
        '{"url":"file:///Users/private-user/project","dir_info":{"editable":true}}',
        '{"url":"git+https://secret@example.invalid/repo","vcs_info":{"commit_id":"abc"}}',
        "malformed",
    ],
)
def test_external_provenance_is_rejected_without_leaks(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    direct: str,
) -> None:
    installed.append(distribution("external", direct=direct))
    output = tmp_path / "snapshot"
    assert release.main(["capture", "--output", str(output)]) == 1
    text = capsys.readouterr().err
    assert "secret" not in text
    assert "private-user" not in text
    assert "example.invalid" not in text
    assert not output.exists()


@pytest.mark.parametrize("change", ["wrong-url", "not-editable", "wrong-import", "absent"])
def test_repository_editable_binding_is_required(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    if change == "wrong-url":
        installed[2] = distribution(
            "mittelwerk",
            direct='{"url":"file:///other/source","dir_info":{"editable":true}}',
        )
    elif change == "not-editable":
        installed[2] = distribution(
            "mittelwerk", direct=json.dumps({"url": repository.as_uri(), "dir_info": {}})
        )
    elif change == "wrong-import":
        monkeypatch.setattr(
            importlib.util, "find_spec", lambda name: SimpleNamespace(origin="/other/source.py")
        )
    else:
        installed[:] = [item for item in installed if item.metadata["Name"] != "mittelwerk"]
    with pytest.raises(release.SnapshotError, match="editable|dev extras"):
        release.capture(repository, tmp_path / "snapshot")


def test_artifacts_do_not_export_sensitive_metadata(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PIP_INDEX_URL", "https://private-user:secret@private-index.invalid")
    monkeypatch.setenv("PRIVATE_TOKEN", "super-secret")
    (repository / "private-user-filename.py").write_text("TOKEN = 'super-secret'\n")
    output = tmp_path / "snapshot"
    release.capture(repository, output)
    text = "".join(path.read_text() for path in output.iterdir())
    for value in (str(repository), "private-user", "secret", "private-index", "PRIVATE_TOKEN"):
        assert value not in text
    assert "direct_url" not in text
    assert "file://" not in text


@pytest.mark.parametrize(
    "kind",
    [
        "json",
        "recursive-json",
        "duplicate-json",
        "schema",
        "pins",
        "path",
        "hash",
        "field",
        "extra",
    ],
)
def test_malformed_snapshot_is_a_safe_failure(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    kind: str,
) -> None:
    output = tmp_path / "snapshot"
    release.capture(repository, output)
    data = manifest(output)
    if kind == "json":
        (output / "manifest.json").write_text("{secret-not-json")
    elif kind == "recursive-json":
        (output / "manifest.json").write_text("[" * 1500 + "0" + "]" * 1500)
    elif kind == "duplicate-json":
        (output / "manifest.json").write_text('{"schema_version":1,"schema_version":1}')
    elif kind == "pins":
        (output / "constraints.txt").write_text("secret@private.invalid\n")
    elif kind == "extra":
        (output / "private-secret").write_text("secret")
    else:
        if kind == "schema":
            data["schema_version"] = 999
        elif kind == "path":
            data["artifacts"]["../../secret"] = "a" * 64
        elif kind == "hash":
            data["artifacts"]["constraints.txt"] = "not-a-hash"
        elif kind == "field":
            data["packages"] = [{"name": [], "version": None}]
        (output / "manifest.json").write_text(json.dumps(data))
    assert release.main(["check", "--snapshot", str(output)]) == 1
    assert "secret" not in capsys.readouterr().err


@pytest.mark.parametrize("name,version", [("bad@private", "1.0"), ("safe", "1.0+private")])
def test_unsafe_requirement_metadata_rejected(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    name: str,
    version: str,
) -> None:
    installed.append(distribution(name, version))
    with pytest.raises(release.SnapshotError, match="index"):
        release.capture(repository, tmp_path / "snapshot")


def test_explicit_wheelhouse_and_tamper_check(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed.extend([distribution("setuptools", "80.0"), distribution("wheel", "0.45")])
    output = tmp_path / "snapshot"
    original = release._run
    calls: list[list[str]] = []

    def run(args: list[str], cwd: Path, *, scratch: Path | None = None) -> bytes:
        if "download" not in args:
            return original(args, cwd)
        calls.append(args)
        assert scratch == output / ".pip-work"
        assert scratch.is_dir()
        directory = Path(args[args.index("--dest") + 1])
        _, packages = release.installed_packages(repository)
        for item in packages:
            name = item["name"].replace("-", "_")
            (directory / f"{name}-{item['version']}-py3-none-any.whl").write_bytes(b"wheel fixture")
        return b"never publish pip output"

    monkeypatch.setattr(release, "_run", run)
    release.capture(repository, output, wheelhouse=True)
    assert len(calls) == 1
    assert "--only-binary=:all:" in calls[0] and "--no-deps" in calls[0]
    assert not (output / ".pip-work").exists()
    release.check(repository, output)
    wheel = next((output / "wheelhouse").iterdir())
    wheel.write_bytes(b"changed")
    with pytest.raises(release.SnapshotError, match="integrity"):
        release.check(repository, output)


def test_failed_wheel_download_leaves_no_partial_snapshot(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    installed.extend([distribution("setuptools"), distribution("wheel")])
    original = release._run

    def run(args: list[str], cwd: Path, *, scratch: Path | None = None) -> bytes:
        if "download" in args:
            raise release.SnapshotError("Local command failed; no subprocess output retained.")
        return original(args, cwd)

    monkeypatch.setattr(release, "_run", run)
    output = tmp_path / "snapshot"
    with pytest.raises(release.SnapshotError, match="command failed"):
        release.capture(repository, output, wheelhouse=True)
    assert not output.exists()


def test_subprocess_failures_suppress_sensitive_diagnostics(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diagnostic = "https://private-user:secret@internal-index.invalid/private"

    def fail(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        return subprocess.CompletedProcess(["pip"], 1, diagnostic.encode(), diagnostic.encode())

    monkeypatch.setattr(subprocess, "run", fail)
    with pytest.raises(release.SnapshotError) as error:
        release._run(["pip"], tmp_path)
    assert "secret" not in str(error.value)
    assert "private-user" not in str(error.value)
    assert "internal-index" not in str(error.value)


def test_wheelhouse_needs_captured_build_tools(
    repository: Path, installed: list[importlib.metadata.Distribution], tmp_path: Path
) -> None:
    output = tmp_path / "snapshot"
    with pytest.raises(release.SnapshotError, match="already installed"):
        release.capture(repository, output, wheelhouse=True)
    assert not output.exists()


def test_binary_download_requires_complete_package_set(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
) -> None:
    directory = tmp_path / "wheelhouse"
    directory.mkdir()
    (directory / "pip-25.1-py3-none-any.whl").write_bytes(b"fixture")
    _, packages = release.installed_packages(repository)
    with pytest.raises(release.SnapshotError, match="incomplete"):
        release._wheel_inventory(directory, packages)


def test_symlink_artifact_is_rejected(
    repository: Path, installed: list[importlib.metadata.Distribution], tmp_path: Path
) -> None:
    output = tmp_path / "snapshot"
    release.capture(repository, output)
    original = tmp_path / "original-constraints.txt"
    constraints = output / "constraints.txt"
    constraints.rename(original)
    constraints.symlink_to(original)
    with pytest.raises(release.SnapshotError, match="integrity"):
        release.check(repository, output)


def test_capture_detects_midflight_source_changes(
    repository: Path,
    installed: list[importlib.metadata.Distribution],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original: Callable[..., Any] = release.installed_packages
    count = 0

    def packages(root: Path) -> Any:
        nonlocal count
        count += 1
        if count == 2:
            (root / "concurrent.py").write_text("changed = True\n")
        return original(root)

    monkeypatch.setattr(release, "installed_packages", packages)
    output = tmp_path / "snapshot"
    with pytest.raises(release.SnapshotError, match="changed during capture"):
        release.capture(repository, output)
    assert not output.exists()
