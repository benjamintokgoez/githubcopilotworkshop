"""Static safety, theming, localization, and accessibility contracts."""

from __future__ import annotations

import re
from pathlib import Path

DASHBOARD = Path(__file__).resolve().parents[1] / "dashboard" / "index.html"


def dashboard_html() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


def test_theme_is_selected_before_styles_and_uses_clawpilot_tokens() -> None:
    html = dashboard_html()

    assert html.index("<script>") < html.index("<style>")
    assert 'new URLSearchParams(window.location.search).get("scoutTheme")' in html
    assert 'document.documentElement.setAttribute("data-theme", theme)' in html
    for token in (
        "--cp-bg:",
        "--cp-surface:",
        "--cp-border:",
        "--cp-text:",
        "--cp-accent:",
        "--cp-success:",
        "--cp-danger:",
        "--cp-warning:",
    ):
        assert token in html
    assert '"Segoe UI", Aptos, Calibri' in html


def test_dashboard_is_self_contained_and_avoids_dynamic_html_sinks() -> None:
    html = dashboard_html()

    assert (
        re.search(
            r"""(?:src|href)=["'](?:https?:)?//|url\(["']?https?://""",
            html,
            flags=re.IGNORECASE,
        )
        is None
    )
    for unsafe_sink in ("innerHTML", "outerHTML", "insertAdjacentHTML", "eval("):
        assert unsafe_sink not in html
    assert "localStorage" not in html
    assert "sessionStorage" in html


def test_dashboard_exposes_localization_and_accessibility_contracts() -> None:
    html = dashboard_html()

    for contract in (
        'lang="en"',
        "de-DE",
        "en-GB",
        "Europe/Berlin",
        "prefers-reduced-motion",
        "aria-live=",
        "aria-label=",
        "skip-link",
    ):
        assert contract in html
