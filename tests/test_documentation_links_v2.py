"""Repository-local Markdown links are part of the workshop's executable UX."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"!?\[[^\]]*]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
EXCLUDED_PARTS = {".git", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".workshop-state"}


def markdown_files() -> list[Path]:
    return sorted(
        path
        for path in REPO_ROOT.rglob("*.md")
        if not EXCLUDED_PARTS.intersection(path.relative_to(REPO_ROOT).parts)
        and not any(part.startswith(".venv") for part in path.relative_to(REPO_ROOT).parts)
    )


def github_heading_anchors(path: Path) -> set[str]:
    anchors: set[str] = set()
    occurrences: Counter[str] = Counter()
    fenced = False

    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.lstrip()
        if stripped.startswith(("```", "~~~")):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = HEADING_RE.match(line)
        if match is None:
            continue

        heading = re.sub(r"<[^>]+>", "", match.group(1))
        heading = re.sub(r"[^\w\s-]", "", heading.lower(), flags=re.UNICODE)
        base = re.sub(r"\s+", "-", heading.strip())
        suffix = occurrences[base]
        occurrences[base] += 1
        anchors.add(base if suffix == 0 else f"{base}-{suffix}")

    return anchors


def test_internal_markdown_links_and_anchors_resolve() -> None:
    failures: list[str] = []

    for source in markdown_files():
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8").splitlines(), start=1
        ):
            for raw_target in LINK_RE.findall(line):
                target = raw_target.strip().strip("<>")
                if not target or target.startswith(("http://", "https://", "mailto:")):
                    continue

                raw_path, separator, raw_fragment = target.partition("#")
                target_path = source if not raw_path else source.parent / unquote(raw_path)
                target_path = target_path.resolve()
                try:
                    target_path.relative_to(REPO_ROOT.resolve())
                except ValueError:
                    failures.append(
                        f"{source.relative_to(REPO_ROOT)}:{line_number}: "
                        f"target escapes repository: {target}"
                    )
                    continue

                if not target_path.exists():
                    failures.append(
                        f"{source.relative_to(REPO_ROOT)}:{line_number}: missing target: {target}"
                    )
                    continue

                if separator and raw_fragment:
                    if target_path.is_dir():
                        target_path = target_path / "README.md"
                    if target_path.suffix.lower() != ".md":
                        failures.append(
                            f"{source.relative_to(REPO_ROOT)}:{line_number}: "
                            f"anchor points to non-Markdown target: {target}"
                        )
                        continue
                    fragment = unquote(raw_fragment).lower()
                    if fragment not in github_heading_anchors(target_path):
                        failures.append(
                            f"{source.relative_to(REPO_ROOT)}:{line_number}: "
                            f"missing anchor: {target}"
                        )

    assert failures == [], "\n" + "\n".join(failures)
