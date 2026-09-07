#!/usr/bin/env python3
"""Capture/check local, platform-specific delivery inputs; never approve a release.

Uses only the standard library. Optional wheel downloads use the active Python's
existing pip and its configured package sources; nothing is published.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import sysconfig
import tomllib
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from urllib.request import url2pathname

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 1
NAME = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?")
VERSION = re.compile(
    r"(?:[0-9]+!)?[0-9]+(?:\.[0-9]+)*(?:(?:a|b|rc)[0-9]+)?"
    r"(?:\.post[0-9]+)?(?:\.dev[0-9]+)?"
)
HASH = re.compile(r"[0-9a-f]{64}")
MANIFEST_INPUTS = (
    "pyproject.toml",
    "requirements.txt",
    ".devcontainer/devcontainer.json",
    ".github/workflows/ci.yml",
)
LIMITATIONS = [
    "Capture is not evidence of passed tests, a pilot, or organizer approval.",
    "Requires the same Python patch, implementation, ABI, OS target, and architecture.",
    "The repository source is separate; revision and current source bytes must match.",
    "Ignored files, system libraries, editors, containers, and external services are not captured.",
    "Version pins alone do not preserve package bytes; optional wheels have integrity hashes.",
    "Hashes detect changes, not authenticity; retain through an approved trusted channel.",
]


class SnapshotError(Exception):
    """A safe, deliberately non-sensitive diagnostic."""


def _run(arguments: Sequence[str], cwd: Path, *, scratch: Path | None = None) -> bytes:
    """Do not echo subprocess output: pip/git diagnostics can contain credentials."""
    try:
        child_env = None
        if scratch is not None:
            child_env = dict(os.environ)
            child_env.update(dict.fromkeys(("TMPDIR", "TEMP", "TMP"), str(scratch.resolve())))
        result = subprocess.run(  # noqa: S603
            list(arguments), cwd=cwd, capture_output=True, check=False, env=child_env, timeout=600
        )
    except (OSError, subprocess.TimeoutExpired):
        raise SnapshotError("Required local command could not start or timed out.") from None
    if result.returncode:
        raise SnapshotError("Local command failed; no subprocess output retained.") from None
    return result.stdout


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json(data: object) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode()


def _name(value: str) -> str:
    if len(value) > 200 or not NAME.fullmatch(value):
        raise SnapshotError("Distribution name is not safe for an index requirement.")
    return re.sub(r"[-_.]+", "-", value).lower()


def _version(value: str) -> str:
    # Local version labels can contain private build identifiers. Do not export them.
    if len(value) > 100 or not VERSION.fullmatch(value):
        raise SnapshotError("Distribution version is not an accepted public index version.")
    return value


def _project(root: Path) -> dict[str, str]:
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    return {"name": _name(data["name"]), "version": _version(data["version"])}


def _local_project_url(raw: str, root: Path) -> None:
    try:
        data = json.loads(raw)
        url = urlsplit(data["url"])
        valid = (
            data.get("dir_info", {}).get("editable") is True
            and url.scheme == "file"
            and not url.netloc
            and not url.query
            and not url.fragment
            and Path(url2pathname(url.path)).resolve() == root.resolve()
        )
    except (ValueError, KeyError, TypeError, AttributeError):
        valid = False
    if not valid:
        raise SnapshotError("Installed project must be editable from this repository source.")


def installed_packages(
    root: Path, distributions: Iterable[importlib.metadata.Distribution] | None = None
) -> tuple[dict[str, str], list[dict[str, str]]]:
    """Allow only the repository itself to be editable; never serialize provenance."""
    project = _project(root)
    packages: dict[str, str] = {}
    project_seen = False
    source_seen = False
    for distribution in (
        importlib.metadata.distributions() if distributions is None else distributions
    ):
        name = _name(distribution.metadata.get("Name", ""))
        version = _version(distribution.version)
        direct = distribution.read_text("direct_url.json")
        if name == project["name"]:
            if version != project["version"]:
                raise SnapshotError("Installed project version differs from repository metadata.")
            project_seen = True
            if direct:
                _local_project_url(direct, root)
                source_seen = True
            continue
        if direct:
            raise SnapshotError(
                "External direct-URL or editable dependency cannot be captured. "
                "Use a dedicated environment with only approved index packages and this project."
            )
        if name in packages and packages[name] != version:
            raise SnapshotError("Conflicting installed distribution versions.")
        packages[name] = version
    if not project_seen:
        raise SnapshotError("Install this repository project with its dev extras before capture.")
    spec = importlib.util.find_spec("mittelwerk")
    if (
        not source_seen
        or spec is None
        or spec.origin is None
        or Path(spec.origin).resolve() != (root / "mittelwerk" / "__init__.py").resolve()
    ):
        raise SnapshotError("Current Python is not bound to this repository's editable source.")
    return project, [{"name": name, "version": packages[name]} for name in sorted(packages)]


def environment() -> dict[str, str]:
    """Avoid sys.version, platform.platform, hostname, executable, and environment."""
    libc_name, libc_version = platform.libc_ver()
    os_id, os_version = "", ""
    if sys.platform == "linux":
        try:
            os_release = platform.freedesktop_os_release()
        except OSError:
            raise SnapshotError("Linux target metadata is unavailable.") from None
        os_id = os_release.get("ID", "")
        os_version = os_release.get("VERSION_ID", "")
    elif sys.platform == "darwin":
        os_version = platform.mac_ver()[0]
    elif sys.platform == "win32":
        os_version = platform.win32_ver()[1]
    values = {
        "python": platform.python_version(),
        "implementation": sys.implementation.name,
        "system": platform.system(),
        "machine": platform.machine(),
        "abi": str(sysconfig.get_config_var("SOABI") or ""),
        "libc": libc_name,
        "libc_version": libc_version,
        "os_id": os_id,
        "os_version": os_version,
    }
    if any(not re.fullmatch(r"[A-Za-z0-9_.-]{0,100}", value) for value in values.values()):
        raise SnapshotError("Platform metadata is not safe to export.")
    return values


def source_snapshot(root: Path, output: Path) -> dict[str, Any]:
    """Hash names/content without exporting paths, file contents, remotes, or authors."""
    git = shutil.which("git")
    if git is None:
        raise SnapshotError("Git is required to bind a snapshot to repository source.")
    revision = _run([git, "rev-parse", "HEAD"], root).decode().strip()
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", revision):
        raise SnapshotError("Repository revision is invalid.")
    tracked = set(_run([git, "ls-files", "-z", "--cached"], root).split(b"\0")) - {b""}
    others = set(
        _run([git, "ls-files", "-z", "--others", "--exclude-standard"], root).split(b"\0")
    ) - {b""}
    digest = hashlib.sha256()
    untracked = False
    for name in sorted(tracked | others):
        path = root / os.fsdecode(name)
        component = root
        for part in Path(os.fsdecode(name)).parts:
            component /= part
            if component.is_symlink():
                raise SnapshotError("Source symlinks need a separately approved image.")
        if path.resolve().is_relative_to(output.resolve()):
            if name in tracked:
                raise SnapshotError("Snapshot directory must not contain repository inputs.")
            continue
        if path.exists() and not path.is_file():
            raise SnapshotError("Source symlinks and submodules need a separately approved image.")
        untracked |= name in others
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        if path.exists():
            digest.update(b"x" if path.stat().st_mode & stat.S_IXUSR else b"f")
            digest.update(hashlib.sha256(path.read_bytes()).digest())
        else:
            digest.update(b"deleted")
    changed = bool(_run([git, "diff", "HEAD", "--name-only", "-z"], root)) or untracked
    return {
        "revision": revision,
        "tree_sha256": digest.hexdigest(),
        "dirty": changed,
        "input_sha256": {
            name: _sha((root / name).read_bytes())
            for name in MANIFEST_INPUTS
            if (root / name).is_file()
        },
    }


def _constraints(packages: list[dict[str, str]]) -> bytes:
    return "".join(f"{item['name']}=={item['version']}\n" for item in packages).encode()


def _wheel_inventory(directory: Path, packages: list[dict[str, str]]) -> dict[str, str]:
    expected = {(item["name"], item["version"]) for item in packages}
    found: set[tuple[str, str]] = set()
    hashes: dict[str, str] = {}
    for path in sorted(directory.iterdir()):
        if (
            path.is_symlink()
            or not path.is_file()
            or not re.fullmatch(r"[A-Za-z0-9_.!+-]+\.whl", path.name)
        ):
            raise SnapshotError("Wheelhouse contains an unsupported entry.")
        parts = path.name[:-4].split("-")
        if len(parts) not in (5, 6):
            raise SnapshotError("Wheelhouse contains an invalid wheel filename.")
        package = (_name(parts[0]), _version(parts[1]))
        if package not in expected or package in found:
            raise SnapshotError("Wheelhouse does not contain exactly the captured dependencies.")
        found.add(package)
        hashes[f"wheelhouse/{path.name}"] = _sha(path.read_bytes())
    if found != expected:
        raise SnapshotError("Wheelhouse is incomplete for the captured dependencies.")
    return hashes


def capture(root: Path, output: Path, *, wheelhouse: bool = False) -> None:
    """Write a new local snapshot. No test or release approval is inferred."""
    if output.exists() or output.is_symlink():
        raise SnapshotError("Output already exists; select a new directory.")
    project, packages = installed_packages(root)
    source = source_snapshot(root, output)
    target = environment()
    constraints = _constraints(packages)
    output.mkdir(parents=True, exist_ok=False)
    try:
        (output / "constraints.txt").write_bytes(constraints)
        artifacts = {"constraints.txt": _sha(constraints)}
        if wheelhouse:
            if not {"pip", "setuptools", "wheel"} <= {item["name"] for item in packages}:
                raise SnapshotError(
                    "Offline packaging requires pip, setuptools, and wheel already installed "
                    "in the environment before testing and capture."
                )
            directory = output / "wheelhouse"
            directory.mkdir()
            scratch = output / ".pip-work"
            scratch.mkdir()
            # Existing approved pip configuration applies; never retain or print its logs.
            _run(
                [
                    sys.executable,
                    "-m",
                    "pip",
                    "--disable-pip-version-check",
                    "--no-cache-dir",
                    "download",
                    "--only-binary=:all:",
                    "--no-deps",
                    "--dest",
                    str(directory.resolve()),
                    "--requirement",
                    str((output / "constraints.txt").resolve()),
                ],
                root,
                scratch=scratch,
            )
            shutil.rmtree(scratch)
            artifacts.update(_wheel_inventory(directory, packages))
        current_project, current_packages = installed_packages(root)
        if (
            current_project != project
            or current_packages != packages
            or source_snapshot(root, output) != source
            or environment() != target
        ):
            raise SnapshotError("Source or environment changed during capture; retry when settled.")
        manifest = {
            "schema_version": SCHEMA_VERSION,
            "project": project,
            "environment": target,
            "source": source,
            "packages": packages,
            "artifacts": artifacts,
            "limitations": LIMITATIONS,
        }
        (output / "manifest.json").write_bytes(_json(manifest))
    except (SnapshotError, OSError, ValueError, KeyError, TypeError, AttributeError):
        # Only remove a directory created by this call, never an existing destination.
        shutil.rmtree(output)
        raise


def _unique_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise SnapshotError("Snapshot contains duplicate JSON fields.")
        result[name] = value
    return result


def _read_manifest(snapshot: Path) -> dict[str, Any]:
    path = snapshot / "manifest.json"
    if snapshot.is_symlink() or path.is_symlink() or path.stat().st_size > 2_000_000:
        raise SnapshotError("Snapshot manifest is invalid.")
    data: Any = json.loads(path.read_bytes(), object_pairs_hook=_unique_keys)
    if not isinstance(data, dict) or set(data) != {
        "schema_version",
        "project",
        "environment",
        "source",
        "packages",
        "artifacts",
        "limitations",
    }:
        raise SnapshotError("Snapshot manifest schema is invalid.")
    if type(data["schema_version"]) is not int or data["schema_version"] != SCHEMA_VERSION:
        raise SnapshotError("Snapshot schema version is unsupported.")
    if data["limitations"] != LIMITATIONS:
        raise SnapshotError("Snapshot limitations are invalid.")
    for key in ("project", "environment", "source", "artifacts"):
        if not isinstance(data[key], dict):
            raise SnapshotError("Snapshot manifest field is invalid.")
    if (
        set(data["project"]) != {"name", "version"}
        or set(data["environment"]) != set(environment())
        or set(data["source"]) != {"revision", "tree_sha256", "dirty", "input_sha256"}
        or type(data["source"]["dirty"]) is not bool
    ):
        raise SnapshotError("Snapshot identity is invalid.")
    if not isinstance(data["packages"], list):
        raise SnapshotError("Snapshot package list is invalid.")
    previous = ""
    for item in data["packages"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"name", "version"}
            or not isinstance(item["name"], str)
            or not isinstance(item["version"], str)
            or _name(item["name"]) != item["name"]
            or item["name"] <= previous
            or item["name"] == data["project"].get("name")
        ):
            raise SnapshotError("Snapshot package entry is invalid.")
        _version(item["version"])
        previous = item["name"]
    artifacts = data["artifacts"]
    if "constraints.txt" not in artifacts or any(
        not isinstance(name, str)
        or not re.fullmatch(r"constraints\.txt|wheelhouse/[A-Za-z0-9_.!+-]+\.whl", name)
        or not isinstance(value, str)
        or not HASH.fullmatch(value)
        for name, value in artifacts.items()
    ):
        raise SnapshotError("Snapshot artifact inventory is invalid.")
    return dict(data)


def check(root: Path, snapshot: Path) -> None:
    """Verify byte integrity, repository source, and exact active environment equality."""
    manifest = _read_manifest(snapshot)
    artifacts = manifest["artifacts"]
    expected_entries = {"manifest.json", "constraints.txt"}
    if len(artifacts) > 1:
        expected_entries.add("wheelhouse")
        if (snapshot / "wheelhouse").is_symlink():
            raise SnapshotError("Wheelhouse must not be a symlink.")
    if {path.name for path in snapshot.iterdir()} != expected_entries:
        raise SnapshotError("Snapshot contains missing or unexpected files.")
    for name, digest in artifacts.items():
        path = snapshot / name
        if path.is_symlink() or not path.is_file() or _sha(path.read_bytes()) != digest:
            raise SnapshotError("Snapshot artifact integrity mismatch.")
    if (snapshot / "constraints.txt").read_bytes() != _constraints(manifest["packages"]):
        raise SnapshotError("Constraints differ from manifest package pins.")
    if "wheelhouse" in expected_entries:
        directory = snapshot / "wheelhouse"
        if directory.is_symlink() or _wheel_inventory(directory, manifest["packages"]) != {
            name: digest for name, digest in artifacts.items() if name.startswith("wheelhouse/")
        }:
            raise SnapshotError("Wheelhouse integrity mismatch.")
    if environment() != manifest["environment"]:
        raise SnapshotError("Python/platform mismatch; use a snapshot for this exact target.")
    project, packages = installed_packages(root)
    if project != manifest["project"]:
        raise SnapshotError("Repository project metadata mismatch.")
    if packages != manifest["packages"]:
        raise SnapshotError("Installed dependency versions/set do not match the snapshot.")
    if source_snapshot(root, snapshot) != manifest["source"]:
        raise SnapshotError("Repository revision/current source differs from the snapshot.")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    capture_parser = commands.add_parser("capture", help="Record inputs, not release approval.")
    capture_parser.add_argument("--output", type=Path, required=True, help="New local directory.")
    capture_parser.add_argument(
        "--wheelhouse",
        action="store_true",
        help="Explicitly download binary wheels using existing approved pip configuration.",
    )
    check_parser = commands.add_parser(
        "check", help="Verify artifact and active source/environment."
    )
    check_parser.add_argument("--snapshot", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "capture":
            capture(REPO_ROOT, args.output, wheelhouse=args.wheelhouse)
            print(
                "Snapshot captured locally. Tests, pilot, and organizer approval are not asserted."
            )
        else:
            check(REPO_ROOT, args.snapshot)
            print("Snapshot integrity, source, and Python environment match. Not release approval.")
        return 0
    except SnapshotError as exc:
        print(f"Snapshot failed: {exc}", file=sys.stderr)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, RecursionError):
        print(
            "Snapshot failed: unreadable or malformed local inputs (details suppressed).",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
