"""Render workshop run cards and shared clocks from one stdlib-only definition."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFINITION = Path("workshop/journeys.json")
LOOP = "Understand/Plan -> Implement/Test -> Review -> Explain"
ROUTES = {"live", "local", "captured/offline"}
LAB_IDS = {"0", "1", "2", "3", "4", "5", "5A", "5B", "5C", "6", "7"}


def minute(clock: str) -> int:
    """Return a minute-of-day for a strict 24-hour clock."""
    if not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", clock):
        raise ValueError(f"Invalid clock: {clock!r}")
    hour, minutes = map(int, clock.split(":"))
    return hour * 60 + minutes


def clock(value: int) -> str:
    """Format a same-day minute as a 24-hour clock."""
    if not 0 <= value < 24 * 60:
        raise ValueError("Workshop clocks must stay within one day")
    return f"{value // 60:02}:{value % 60:02}"


def require(condition: bool, message: str) -> None:
    """Reject an invalid definition with an actionable error."""
    if not condition:
        raise ValueError(message)


def safe_path(value: Any, root: Path) -> Path:
    """Validate a relative repository path without traversing outside the root."""
    require(isinstance(value, str) and bool(value), "Expected a non-empty path")
    path = Path(value)
    require(not path.is_absolute() and ".." not in path.parts, f"Unsafe path: {value}")
    require(
        (root / path).resolve().is_relative_to(root.resolve()),
        f"Path leaves repository: {value}",
    )
    return path


def validate(data: dict[str, Any], root: Path = ROOT) -> None:
    """Check clocks, routes, navigation, evidence locations, and scenario links."""
    require(data.get("version") == 1, "Unsupported journey definition version")
    require(data.get("timezone") == "Europe/Berlin", "Use Europe/Berlin for presentation")
    require(data.get("loop") == LOOP, "The canonical learning loop must not change")
    blocks = data.get("blocks")
    labs = data.get("labs")
    if not isinstance(blocks, list) or not blocks:
        raise ValueError("Missing blocks")
    if not isinstance(labs, list) or not labs:
        raise ValueError("Missing labs")
    block_ids: set[str] = set()
    end = minute("09:00")
    slack = 0
    for block in blocks:
        require(isinstance(block, dict), "Each block must be an object")
        identifier = block.get("id")
        require(
            isinstance(identifier, str) and identifier not in block_ids,
            "Missing or duplicate block id",
        )
        block_ids.add(identifier)
        require(isinstance(block.get("start"), str), f"{identifier}: missing start")
        start = minute(block["start"])
        duration = block.get("minutes")
        require(type(duration) is int and duration > 0, f"{identifier}: invalid duration")
        require(start == end, f"{identifier}: schedule gap or overlap")
        end = start + duration
        clock(end)
        if identifier.startswith("slack-"):
            slack += duration
        if identifier.isdigit():
            phases = block.get("phases")
            require(isinstance(phases, list) and bool(phases), f"{identifier}: no phases")
            for phase in phases:
                require(
                    isinstance(phase, list)
                    and len(phase) == 2
                    and isinstance(phase[0], str)
                    and bool(phase[0])
                    and type(phase[1]) is int
                    and phase[1] > 0,
                    f"{identifier}: invalid phase",
                )
            require(
                sum(phase[1] for phase in phases) == duration,
                f"{identifier}: phases must fill the block",
            )
            cuts = block.get("cuts")
            require(isinstance(cuts, list) and bool(cuts), f"{identifier}: missing cuts")
            previous = -1
            for cut in cuts:
                require(
                    isinstance(cut, list)
                    and len(cut) == 2
                    and type(cut[0]) is int
                    and previous < cut[0] <= duration
                    and isinstance(cut[1], str)
                    and bool(cut[1]),
                    f"{identifier}: invalid or unordered cut",
                )
                previous = cut[0]
        else:
            require(isinstance(block.get("label"), str), f"{identifier}: missing label")
    require(end == minute("17:15") and slack == 60, "Protect 17:15 finish and 60m slack")
    require(
        next(block for block in blocks if block["id"] == "0")["cuts"][0][0] == 8,
        "Lab 0 repair stops at 09:08 / T+8",
    )
    ids: set[str] = set()
    docs: set[str] = set()
    scenarios: set[str] = set()
    for lab in labs:
        require(isinstance(lab, dict), "Each lab must be an object")
        identifier = lab.get("id")
        require(
            isinstance(identifier, str) and identifier not in ids,
            "Missing or duplicate lab id",
        )
        ids.add(identifier)
        require(lab.get("block") in block_ids, f"{identifier}: unknown block")
        for field in ("title", "outcome", "first", "workspace", "evidence", "lanes"):
            require(
                isinstance(lab.get(field), str) and bool(lab[field].strip()),
                f"{identifier}: missing {field}",
            )
            require(
                "|" not in lab[field] and "\n" not in lab[field],
                f"{identifier}: {field} must fit one Markdown table cell",
            )
        document = safe_path(lab.get("doc"), root)
        require((root / document).is_file(), f"{identifier}: missing lab document")
        require(str(document) not in docs, f"{identifier}: duplicate document")
        docs.add(str(document))
        if "hints" in lab:
            hints = safe_path(lab["hints"], root)
            require((root / hints).is_file(), f"{identifier}: missing hint document")
        routes = lab.get("routes")
        require(
            isinstance(routes, list)
            and bool(routes)
            and all(isinstance(route, str) and route in ROUTES for route in routes)
            and len(routes) == len(set(routes))
            and lab.get("default") in routes
            and any(route != "live" for route in routes),
            f"{identifier}: invalid routes or missing non-live route",
        )
        for link in ("next", "return"):
            require(
                lab.get(link) is None or lab[link] in LAB_IDS,
                f"{identifier}: unknown {link} lab",
            )
        evidence = safe_path(lab["evidence"], root)
        scenario = lab.get("scenario")
        if scenario is None:
            require(
                evidence.is_relative_to(".workshop-state/notes"),
                f"{identifier}: non-scenario evidence must be private ignored notes",
            )
        else:
            require(
                isinstance(scenario, str)
                and bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", scenario))
                and scenario not in scenarios,
                f"{identifier}: invalid or duplicate scenario",
            )
            scenarios.add(scenario)
            scenario_root = Path("workshop/scenarios") / scenario
            require((root / scenario_root).is_dir(), f"{identifier}: missing scenario")
            require(
                (root / "workshop/fallbacks" / scenario).is_dir(),
                f"{identifier}: missing fallback",
            )
            require(
                evidence.is_relative_to(scenario_root / "work"),
                f"{identifier}: evidence must be archived with scenario work",
            )
            require(
                lab["first"] == f"python scripts/workshop.py start {scenario}",
                f"{identifier}: start command disagrees with scenario",
            )
    require(ids == LAB_IDS, "Expected Labs 0-7 and all three elective branches")
    catalogue = json.loads((root / "workshop/scenarios/catalogue.json").read_text(encoding="utf-8"))
    require(
        scenarios == set(catalogue["scenarios"]),
        "Journey scenarios must match the scenario catalogue",
    )
    require(
        docs == {str(path.relative_to(root)) for path in (root / "challenges").glob("lab_*.md")},
        "Every lab_*.md needs exactly one journey",
    )
    by_id = {lab["id"]: lab for lab in labs}
    for identifier in sorted(LAB_IDS):
        expected_block = "5" if identifier in {"5A", "5B", "5C"} else identifier
        require(by_id[identifier]["block"] == expected_block, "Lab/block mapping changed")
        next_id = (
            "6"
            if identifier in {"5A", "5B", "5C"}
            else str(int(identifier) + 1)
            if identifier != "7"
            else None
        )
        return_id = (
            "5"
            if identifier in {"5A", "5B", "5C"}
            else str(int(identifier) - 1)
            if identifier != "0"
            else None
        )
        require(
            by_id[identifier]["next"] == next_id and by_id[identifier]["return"] == return_id,
            f"Lab {identifier}: Next/Return must follow the learning sequence",
        )


def link(source: Path, target: str) -> str:
    """Return the relative link between known repository documentation paths."""
    import os

    return Path(os.path.relpath(target, source.parent)).as_posix()


def run_card(lab: dict[str, Any], data: dict[str, Any]) -> str:
    """Render a compact participant card with elapsed and cohort clocks."""
    block = next(item for item in data["blocks"] if item["id"] == lab["block"])
    source = Path(lab["doc"])
    by_id = {item["id"]: item for item in data["labs"]}
    start = minute(block["start"])
    reference = link(source, "challenges/reference/scenario_tooling.md")
    solo = link(source, "challenges/README.md") + "#self-paced-route"
    first = f"`{lab['first']}`" if lab["first"].startswith("python ") else lab["first"]
    scenario = lab["scenario"]
    recovery = (
        f"`python scripts/workshop.py resync {scenario} --blocked-at <phase>`; "
        f"then verify and reset. [Recovery commands]({reference})."
        if scenario
        else "Keep the actual result in your private note; "
        "use the supplied capture or approved route."
    )
    lines = [
        "## Run card",
        "",
        "| Decision | This lab |",
        "|---|---|",
        f"| Outcome | {lab['outcome']} |",
        f"| First action | {first} |",
        f"| Edit boundary | {lab['workspace']} |",
        f"| Evidence | `{lab['evidence']}`; "
        + ("reset archives this work. |" if scenario else "private and Git-ignored. |"),
        f"| Lane boundary | {lab['lanes']} |",
        f"| Delivery | Default: **{lab['default']}**. Routes: {', '.join(lab['routes'])}. "
        "Mode does not raise or lower the lane; follow the acceptance checklist. |",
        f"| Clock | **{block['minutes']} elapsed minutes**; cohort "
        f"**{block['start']}-{clock(start + block['minutes'])} Europe/Berlin**. "
        f"[Self-paced route]({solo}): start at T+0, pause between phases, keep the same cuts. |",
        f"| Recovery | {recovery} |",
        "",
        "**Phase clock** (elapsed minutes; solo work uses the left column):",
        "",
        "| Elapsed | Cohort | Phase |",
        "|---|---|---|",
    ]
    elapsed = 0
    for label, duration in block["phases"]:
        end = elapsed + duration
        lines.append(
            f"| T+{elapsed}-{end} | {clock(start + elapsed)}-{clock(start + end)} | {label} |"
        )
        elapsed = end
    lines.extend(["", "**Cuts — move on with honest evidence:**"])
    for elapsed, action in block["cuts"]:
        lines.append(f"- **T+{elapsed} / {clock(start + elapsed)}:** {action}")
    navigation = []
    for field, label in (("return", "Return"), ("next", "Next")):
        if lab[field] is not None:
            target = by_id[lab[field]]
            navigation.append(f"[{label}: Lab {target['id']}]({link(source, target['doc'])})")
    navigation.append(f"[All labs]({link(source, 'challenges/README.md')})")
    navigation.append(f"[Terms]({link(source, 'challenges/README.md')}#terms-used-in-the-labs)")
    lines.extend(["", " · ".join(navigation)])
    return "\n".join(lines)


def agenda(data: dict[str, Any], source: Path) -> str:
    """Render the same complete agenda wherever the delivery clock appears."""
    by_id = {lab["id"]: lab for lab in data["labs"]}
    lines = ["| Time | Block | Duration |", "|---|---|---|"]
    for block in data["blocks"]:
        if block["id"] in by_id:
            lab = by_id[block["id"]]
            label = f"[Lab {lab['id']} - {lab['title']}]({link(source, lab['doc'])})"
        else:
            label = f"**{block['label']}**"
        end = clock(minute(block["start"]) + block["minutes"])
        lines.append(f"| {block['start']}-{end} | {label} | {block['minutes']} min |")
    return "\n".join(lines)


def cut_table(data: dict[str, Any]) -> str:
    """Render facilitator cut triggers from the participant clocks."""
    lines = ["| Lab | Elapsed / cohort | Action |", "|---|---|---|"]
    for block in data["blocks"]:
        for elapsed, action in block.get("cuts", []):
            time = clock(minute(block["start"]) + elapsed)
            lines.append(f"| {block['id']} | T+{elapsed} / {time} | {action} |")
    return "\n".join(lines)


def replace_block(text: str, key: str, content: str, *, insert: bool = False) -> str:
    """Replace exactly one generated region, leaving author-written text alone."""
    start = f"<!-- journeys:{key}:start -->"
    end = f"<!-- journeys:{key}:end -->"
    block = f"{start}\n{content}\n{end}"
    if start not in text and end not in text and insert:
        title, separator, remainder = text.partition("\n")
        require(bool(separator) and title.startswith("# "), "Lab needs a Markdown title")
        return f"{title}\n\n{block}\n{remainder}"
    require(text.count(start) == text.count(end) == 1, f"Missing/duplicate markers: {key}")
    before, tail = text.split(start)
    _, after = tail.split(end)
    return before + block + after


def rendered_files(data: dict[str, Any], root: Path = ROOT) -> dict[Path, str]:
    """Build updated documents without writing to disk."""
    result = {}
    for lab in data["labs"]:
        path = Path(lab["doc"])
        original = (root / path).read_text(encoding="utf-8")
        validate_written_clocks(original, lab, data)
        if "hints" in lab:
            validate_elapsed_clocks((root / lab["hints"]).read_text(encoding="utf-8"), lab, data)
        result[path] = replace_block(
            original,
            f"card:{lab['id']}",
            run_card(lab, data),
            insert=True,
        )
    for path in (
        Path("README.md"),
        Path("challenges/README.md"),
        Path("workshop/ops/FACILITATOR_GUIDE.md"),
    ):
        result[path] = replace_block(
            (root / path).read_text(encoding="utf-8"), "agenda", agenda(data, path)
        )
    facilitator = Path("workshop/ops/FACILITATOR_GUIDE.md")
    result[facilitator] = replace_block(result[facilitator], "cuts", cut_table(data))
    return result


def validate_written_clocks(text: str, lab: dict[str, Any], data: dict[str, Any]) -> None:
    """Check retained author-written timing tables against the shared phases."""
    block = next(item for item in data["blocks"] if item["id"] == lab["block"])
    text = re.sub(
        r"<!-- journeys:.*?:start -->.*?<!-- journeys:.*?:end -->",
        "",
        text,
        flags=re.DOTALL,
    )
    validate_elapsed_clocks(text, lab, data)
    rows = re.findall(r"^\| (\d{2}:\d{2})[-–](\d{2}:\d{2}) \|", text, re.MULTILINE)
    start = minute(block["start"])
    expected = []
    for _, duration in block["phases"]:
        expected.append((clock(start), clock(start + duration)))
        start += duration
    require(
        not rows or rows == expected,
        f"Lab {lab['id']}: author-written phase table differs from journeys.json",
    )
    header = re.search(r"\*\*Block:\*\* (\d{2}:\d{2})-(\d{2}:\d{2}) \((\d+) minutes\)", text)
    if header:
        require(
            header.groups() == (block["start"], clock(start), str(block["minutes"])),
            f"Lab {lab['id']}: block heading differs from journeys.json",
        )
    landing = re.search(
        r"\*\*Landing check on the day:\*\* (\d{2}:\d{2})-(\d{2}:\d{2}) \((\d+) minutes\)",
        text,
    )
    if landing:
        require(
            landing.groups() == (block["start"], clock(start), str(block["minutes"])),
            "Lab 0: landing heading differs from journeys.json",
        )


def validate_elapsed_clocks(text: str, lab: dict[str, Any], data: dict[str, Any]) -> None:
    """Keep paired elapsed/cohort clocks in prose and optional hints consistent."""
    block = next(item for item in data["blocks"] if item["id"] == lab["block"])
    for elapsed, cohort in re.findall(r"T\+(\d+) / (\d{2}:\d{2})", text):
        require(
            0 <= int(elapsed) <= block["minutes"]
            and minute(cohort) == minute(block["start"]) + int(elapsed),
            f"Lab {lab['id']}: T+{elapsed} / {cohort} differs from journeys.json",
        )


def main(argv: list[str] | None = None) -> int:
    """Check generated docs or update them after editing the journey definition."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="report drift without writing")
    args = parser.parse_args(argv)
    try:
        data = json.loads((ROOT / DEFINITION).read_text(encoding="utf-8"))
        require(isinstance(data, dict), "Journey definition must be an object")
        validate(data)
        rendered = rendered_files(data)
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as error:
        print(f"Journey check failed: {error}")
        return 1
    changed = [
        path
        for path, content in rendered.items()
        if (ROOT / path).read_text(encoding="utf-8") != content
    ]
    if args.check and changed:
        for path in changed:
            print(f"Journey drift: {path}")
        print("Run: python scripts/workshop_journeys.py")
        return 1
    if not args.check:
        for path in changed:
            (ROOT / path).write_text(rendered[path], encoding="utf-8")
    print(f"Journeys {'checked' if args.check else 'updated'}: {len(rendered)} documents")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
