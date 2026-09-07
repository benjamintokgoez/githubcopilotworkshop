"""Deterministic checks for the shared workshop clocks and participant run cards."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import workshop_journeys as journeys


@pytest.fixture
def definition() -> dict[str, Any]:
    """Load a fresh definition without generating files or scenario state."""
    return json.loads((journeys.ROOT / journeys.DEFINITION).read_text(encoding="utf-8"))


def test_definition_covers_labs_and_preserves_learning_loop(
    definition: dict[str, Any],
) -> None:
    journeys.validate(definition)
    assert definition["loop"] == journeys.LOOP
    assert len(definition["labs"]) == 11
    assert len({lab["scenario"] for lab in definition["labs"] if lab["scenario"]}) == 7


@pytest.mark.parametrize("value", ["9:00", "24:00", "09:60", "00:00:00", "-1:00"])
def test_clock_rejects_non_24_hour_values(value: str) -> None:
    with pytest.raises(ValueError, match="Invalid clock"):
        journeys.minute(value)


@pytest.mark.parametrize("value", [0, 8, 559, 1035, 1439])
def test_clock_round_trip(value: int) -> None:
    assert journeys.minute(journeys.clock(value)) == value


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("version", 2, "version"),
        ("timezone", "CET", "Europe/Berlin"),
        ("loop", "Plan -> Code", "canonical"),
    ],
)
def test_definition_rejects_changed_shared_contracts(
    definition: dict[str, Any], field: str, value: object, message: str
) -> None:
    definition[field] = value
    with pytest.raises(ValueError, match=message):
        journeys.validate(definition)


def test_landing_repair_cut_is_eight_minutes(definition: dict[str, Any]) -> None:
    block = definition["blocks"][0]
    assert block["cuts"][0][0] == 8
    assert journeys.clock(journeys.minute(block["start"]) + 8) == "09:08"
    block["cuts"][0][0] = 12
    with pytest.raises(ValueError, match="09:08"):
        journeys.validate(definition)


def test_phase_durations_must_fill_the_block(definition: dict[str, Any]) -> None:
    definition["blocks"][0]["phases"][0][1] += 1
    with pytest.raises(ValueError, match="phases must fill"):
        journeys.validate(definition)


def test_schedule_has_no_gap_or_overlap(definition: dict[str, Any]) -> None:
    definition["blocks"][1]["start"] = "09:21"
    with pytest.raises(ValueError, match="gap or overlap"):
        journeys.validate(definition)


def test_every_lab_retains_a_non_live_route(definition: dict[str, Any]) -> None:
    definition["labs"][0].update(routes=["live"], default="live")
    with pytest.raises(ValueError, match="non-live"):
        journeys.validate(definition)


def test_electives_share_one_clock_without_adding_labs(
    definition: dict[str, Any],
) -> None:
    for identifier in ("5", "5A", "5B", "5C"):
        lab = next(lab for lab in definition["labs"] if lab["id"] == identifier)
        assert lab["block"] == "5"
        card = journeys.run_card(lab, definition)
        assert "35 elapsed minutes" in card
        assert "T+18 / 15:18" in card
        assert "T+29 / 15:29" in card
        assert "[Next: Lab 6]" in card


@pytest.mark.parametrize("evidence", ["notes/lab-00.md", "../outside.md", "/outside.md"])
def test_non_scenario_notes_cannot_enter_tracked_or_external_paths(
    definition: dict[str, Any], evidence: str
) -> None:
    definition["labs"][0]["evidence"] = evidence
    with pytest.raises(ValueError, match="private ignored notes|Unsafe path"):
        journeys.validate(definition)


def test_scenario_evidence_stays_with_archived_work(
    definition: dict[str, Any],
) -> None:
    lab = next(lab for lab in definition["labs"] if lab["id"] == "2")
    lab["evidence"] = ".workshop-state/notes/incident.md"
    with pytest.raises(ValueError, match="archived with scenario"):
        journeys.validate(definition)


def test_duplicate_ids_and_broken_navigation_are_rejected(
    definition: dict[str, Any],
) -> None:
    duplicate = copy.deepcopy(definition)
    duplicate["labs"][1]["id"] = "0"
    with pytest.raises(ValueError, match="duplicate lab"):
        journeys.validate(duplicate)
    definition["labs"][0]["next"] = "missing"
    with pytest.raises(ValueError, match="unknown next"):
        journeys.validate(definition)


def test_generated_region_preserves_author_written_pedagogy() -> None:
    text = (
        "# Title\n\nAuthor before.\n\n<!-- journeys:x:start -->\n"
        "old\n<!-- journeys:x:end -->\n\nAuthor after.\n"
    )
    updated = journeys.replace_block(text, "x", "new")
    assert updated == text.replace("\nold\n", "\nnew\n")
    assert journeys.replace_block(updated, "x", "new") == updated


def test_missing_or_duplicate_markers_fail_explicitly() -> None:
    with pytest.raises(ValueError, match="markers"):
        journeys.replace_block("# Title\n", "agenda", "table")
    with pytest.raises(ValueError, match="markers"):
        journeys.replace_block(
            "<!-- journeys:x:start -->\n<!-- journeys:x:start -->\n<!-- journeys:x:end -->",
            "x",
            "new",
        )


def test_author_written_clock_drift_is_detected(definition: dict[str, Any]) -> None:
    lab = next(lab for lab in definition["labs"] if lab["id"] == "2")
    text = (journeys.ROOT / lab["doc"]).read_text(encoding="utf-8")
    journeys.validate_written_clocks(text, lab, definition)
    with pytest.raises(ValueError, match="phase table"):
        journeys.validate_written_clocks(
            text + "\n| 10:15-10:29 | stale phase |\n", lab, definition
        )


def test_hint_clocks_follow_the_same_elapsed_schedule(definition: dict[str, Any]) -> None:
    hints = [lab for lab in definition["labs"] if "hints" in lab]
    assert len(hints) == 6
    for lab in hints:
        text = (journeys.ROOT / lab["hints"]).read_text(encoding="utf-8")
        journeys.validate_elapsed_clocks(text, lab, definition)
    incident = next(lab for lab in hints if lab["id"] == "2")
    with pytest.raises(ValueError, match="differs from journeys.json"):
        journeys.validate_elapsed_clocks("T+35 / 10:46: stop implementation", incident, definition)


def test_all_rendered_documents_are_current_and_rendering_is_pure(
    definition: dict[str, Any],
) -> None:
    before = copy.deepcopy(definition)
    first = journeys.rendered_files(definition)
    assert first == journeys.rendered_files(definition)
    assert definition == before
    assert len(first) == 14
    for path, content in first.items():
        assert content == (journeys.ROOT / path).read_text(encoding="utf-8"), path


def test_check_never_writes_files(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def reject_write(*args: object, **kwargs: object) -> None:
        pytest.fail("--check must not write")

    monkeypatch.setattr(Path, "write_text", reject_write)
    assert journeys.main(["--check"]) == 0
    assert "Journeys checked: 14 documents" in capsys.readouterr().out


def test_check_returns_failure_and_repair_command_for_drift(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(journeys, "rendered_files", lambda data: {Path("README.md"): "drift"})
    assert journeys.main(["--check"]) == 1
    output = capsys.readouterr().out
    assert "Journey drift: README.md" in output
    assert "python scripts/workshop_journeys.py" in output
