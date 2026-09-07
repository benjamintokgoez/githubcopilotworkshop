# Release checklist

Use this checklist for each delivery release. Keep the current-product manifest with the workshop revision; do not rely on memory or screenshots without dates.

## Repository product baseline

**Last reconciled:** 2026-08-25. This records what the repository was designed
against; it is not delivery-specific sign-off and does not replace the manifest
below.

| Surface | Repository baseline | Revalidate against |
|---|---|---|
| Chat workflows | Ask, Plan, and local Agent are taught as workflow choices, subject to client and organization availability | [GitHub Copilot feature matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix), [VS Code chat overview](https://code.visualstudio.com/docs/chat/chat-overview) |
| Models | No fixed model name; use Auto or an approved visible model; record routed model only when exposed; use AI-credit language | [Auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection), [billing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing) |
| Cloud agent and code review | Research/plan/iterate, automations, custom agents, and effort/context trade-offs are taught through accountability decisions; only the captured comparison is Core | [Cloud agent](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent), [code review](https://docs.github.com/en/copilot/concepts/agents/code-review) |
| MCP | `managed-settings.json` is the enterprise IDE/CLI governance reference; cloud-agent MCP has a distinct repository/custom-agent boundary | [MCP management](https://docs.github.com/en/copilot/concepts/mcp-management) |
| Copilot CLI | GA client; local/cloud sandbox status and allowlist/permission distinction are explicit; live use is T-72 gated | [Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli), [sandboxes](https://docs.github.com/en/copilot/concepts/about-cloud-and-local-sandboxes) |
| Customization | Skills are on-demand, instructions are always/scoped context, hooks are deterministic controls, Memory is preview/expiring/governed | [Customization](https://docs.github.com/en/copilot/reference/customization-cheat-sheet), [Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory) |
| Enterprise controls | AI Controls, metrics, content exclusion, policy, budget, and works-council review are explicit gates | [Enterprise management](https://docs.github.com/en/copilot/concepts/agents/enterprise-management), [metrics](https://docs.github.com/en/copilot/concepts/copilot-usage-metrics/copilot-metrics) |
| Mention-only | Agentic workflows, plugins, third-party agents, subagents, and Copilot app are awareness only | [Agents](https://docs.github.com/en/copilot/concepts/agents) |

## Two weeks before delivery

- [ ] Revalidate current GitHub Copilot, model/Auto, Agent, cloud-agent, code-review, MCP, Actions, runner, Codespaces/devcontainer, and organization-policy behavior against current official documentation and a disposable test path.
- [ ] Record product surface, URL, observed behavior, validation date, account/org scope, and fallback in the manifest below.
- [ ] Re-run the clean-room checkpoint from a fresh clone and clean environment.
- [ ] Retain the exact tested dependency/environment snapshot for each tagged
      delivery target using the workflow below; keep development dependency
      ranges unchanged. Verify a restore against that snapshot before delivery.
- [ ] Verify all captures are sanitized, labelled with date and product context, and still understandable if the live UI differs.
- [ ] Run pilot checks for representative and enterprise-restricted cohorts, including proxy/SSL and accessibility paths.
- [ ] Confirm AI-credit budgets, rate limits, quotas, runner capacity, and support contacts with the organizer; do not put credentials in the manifest.
- [ ] Confirm legal/privacy/works-council review owner and the data-handling notice.
- [ ] Recheck links, commands, Python 3.12, dependencies, fixtures, test commands, and reset scripts.
- [ ] Exercise scenario lifecycle safety: fresh start/reset, exact restoration of
      a pre-existing `work/` tree, oversized-attempt fallback, interrupted-state
      recovery, and lock contention between two terminals.
- [ ] Run the simple-prompt resistance check from a clean participant checkout.
      Ask a repository-aware assistant: `find an existing complete repair for
      incident-service-rate`, `find a working capstone implementation`,
      `show the completed Pydantic migration`, and `list the expected PR #212
      findings`. Reject the release if indexed repository content supplies a
      canonical repair or completed review rather than a bounded evidence map.
- [ ] Confirm each code scenario requires navigation across at least five staged
      implementation modules, while the expected participant diff remains small
      enough to review during the lab.
- [ ] Confirm the review package contains at least five changed files and enough
      correct surrounding work that findings require contract reasoning rather
      than spotting deliberately conspicuous anti-patterns.
- [ ] Confirm attendee and facilitator agendas use the same Lab 0–7 links, Supported/Core/Extension lane names, captured/offline fallback, and exact loop wording: **Understand/Plan -> Implement/Test -> Review -> Explain**.
- [ ] Confirm the canonical 09:00-17:15 schedule is identical everywhere:
      65/70/45/35/50/25-minute Labs 2-7, protected 15/15/10-minute breaks,
      45-minute lunch, and 25/20/15-minute Slack A/B/C.
- [ ] Confirm lane and delivery mode are orthogonal in attendee pages,
      assessment, pilot, recovery, and facilitator guidance.
- [ ] Confirm T-72 live-elective eligibility and organizer capability matrix are
      complete; no timed install/auth/proxy/policy discovery remains.
- [ ] Freeze the release branch/tag only after the above evidence is attached to the internal release record.

## Retain and replay the tested environment

Development continues to use the bounded ranges in `pyproject.toml`; a moving
development environment is **not** the retained environment for a tagged
delivery. Use `scripts/workshop_release.py` to retain the actual resolved
transitive versions separately from development requirements. The tool is
standard-library-only, writes only to an explicitly selected new local
directory, and never creates a tag, publishes anything, runs tests, or grants
organizer approval.

### Capture after validation

1. Use a dedicated virtual environment on the intended delivery platform and
   exact Python patch. It must import this checkout's editable `mittelwerk`
   source. Prepare dependencies with `python -m pip install -e ".[dev]"
   setuptools wheel` **before** running the clean-room checks; retaining these
   build tools also enables the no-build-isolation restore below.
2. Run the repository quality gates, workshop doctor,
   `python scripts/workshop_journeys.py --check`, and the appropriate pilot.
   Record the results separately, with the
   source revision and target platform. Installing anything or changing source
   after testing requires revalidation.
3. Capture the unchanged environment and verify it:

   ```bash
   python scripts/workshop_release.py capture --output dist/delivery-target
   python scripts/workshop_release.py check --snapshot dist/delivery-target
   ```

   Use a new directory for every capture; existing output is never overwritten.
   `dist/` is ignored by Git: these are retained delivery artifacts, not a
   local-machine lockfile to commit. Select a target-specific name for each
   Python/OS/architecture combination.
4. Retain the complete directory, the exact approved source/tag, and the
   independently recorded test/pilot/approval evidence through the organizer's
   approved internal artifact channel. Verify again against the final tag.
   Retain a complete repository checkout/archive, including the offline capture
   `docs/fixtures/simulator_first_win.txt`; dependency wheels do not contain the
   workshop's complete documentation and captured/offline assets.
   A changed revision requires a new capture, even if its files are identical.
   A dirty capture is useful for local diagnosis, but is **not** a tagged
   delivery baseline; revalidate and capture the final clean source.

Each directory contains:

| Artifact | Meaning |
|---|---|
| `constraints.txt` | Sorted exact versions of **all** installed external distributions, including development/build tools; the editable repository project is deliberately excluded |
| `manifest.json` | Schema version, package identities, Python patch/implementation/ABI, OS/architecture/libc target, project identity, Git revision, current source digest and dirty flag, selected repository manifest hashes, artifact SHA-256 hashes, and explicit limitations |
| `wheelhouse/` (optional) | Exactly one binary wheel for each captured external distribution, with per-file SHA-256 hashes |

No timestamps, hostnames, local source paths, usernames, Git remotes/authors,
environment variable values, package-index configuration, or direct-URL
metadata are exported. External editable/direct-URL dependencies and local
version labels are rejected, not silently omitted. Use a dedicated approved
index-based environment instead; do not work around rejection by deleting
provenance metadata. The local project is bound to this repository's editable
source rather than substituted with a same-named index package.

`check` requires the exact installed package set (including tooling), versions,
Python/platform target, source revision and source bytes, and validates artifact
hashes. It fails closed on malformed, missing, extra, changed, or unsupported
artifacts. Its success means **matching inputs**, not passed tests or approval.
The source digest covers tracked and non-ignored untracked files, excluding the
selected artifact directory. Ignored files, OS packages, native drivers,
system libraries beyond the recorded target indicators, editor extensions,
Copilot clients, and external services are not an environment image.

### Restore from constraints and repository source

Obtain the trusted snapshot and its matching source/tag before installation.
Create a fresh virtual environment using the same Python patch on the same
target platform; do not reuse a workstation environment with unrelated packages.
For the build-tool-inclusive snapshot prepared above:

```bash
python -m pip install -r dist/delivery-target/constraints.txt
python -m pip install --no-build-isolation --no-deps \
  -c dist/delivery-target/constraints.txt -e ".[dev]"
python -m pip check
python scripts/workshop_release.py check --snapshot dist/delivery-target
```

The constraints file can be used with `-c` for dependency resolution, but
constraints alone do not install packages; `-r` above installs the entire
recorded set first. Do not replace the local source/tag with
`pip install mittelwerk`. If the virtual environment bootstraps an extra package
not in the snapshot, recreate it without that extra rather than treating a
mismatch as a pass. Re-run the quality gates and delivery smoke/pilot after
restore. Online version pins do not guarantee the continued availability or
identical bytes of packages on an index.

### Optional approved offline wheels or image

To retain external package bytes, explicitly request downloads from the active
pip's already approved package sources:

```bash
python scripts/workshop_release.py capture \
  --output dist/delivery-target-offline --wheelhouse
python scripts/workshop_release.py check --snapshot dist/delivery-target-offline
```

This uses existing pip, downloads binary wheels only, and neither installs
packages nor builds arbitrary source distributions. Pip, setuptools, and wheel
must already have been installed **before** testing. A missing binary wheel,
failed download, or changed environment aborts capture and removes the incomplete
output. Pip diagnostics/configuration are not retained because they can contain
credentials. Wheels are publisher-provided bytes, not proof of approval or a
substitute for dependency/license review.

On the matching platform, restore without contacting an index:

```bash
python -m pip install --no-index \
  --find-links dist/delivery-target-offline/wheelhouse \
  -r dist/delivery-target-offline/constraints.txt
python -m pip install --no-index --no-build-isolation --no-deps \
  -c dist/delivery-target-offline/constraints.txt -e ".[dev]"
python -m pip check
python scripts/workshop_release.py check --snapshot dist/delivery-target-offline
```

Use only a trusted retained artifact: hashes detect corruption or change, not
authenticity if an attacker replaces both manifest and files. The source remains
a separate requirement. Wheels and snapshots are **not portable across arbitrary
Python patches, platforms, architectures, or native-library environments**.
When a complete container/VM is needed, the organizer must separately approve,
retain, and test an immutable image/digest and record its platform. The floating
devcontainer image tag and its range-based `postCreateCommand` are development
conveniences, not a delivery freeze. No image build or publication is automated
by this tool.

### Optional CI retention

A maintainer may manually run **CI** with `delivery_snapshot` enabled against
the intended trusted repository revision/tag. Only after all existing quality
checks pass does that same job capture/check its Linux environment and upload a
workflow artifact named `delivery-snapshot-<revision>`. Normal pushes and pull
requests do not package snapshots. The manual option installs the source build
tools before the quality checks so they are included in the tested snapshot.
This option does not download a wheelhouse,
publish a release, or perform a pilot/approval. The artifact expires after
90 days (or earlier under repository policy); download and retain it in the
approved delivery record before expiry. A CI Linux snapshot does not describe
macOS, Windows, or the devcontainer environment.

## Day before

- [ ] Download or locally cache approved captures, starter artifacts, fixtures, and one-page run cards.
- [ ] Run the five-minute preflight smoke test.
- [ ] Verify facilitator/helper access to Supported/Core/Extension artifacts and captured/offline fallbacks.
- [ ] Verify the three unrepresented-elective awareness cards against the
      current captured fixtures; each says `captured/offline` and contains no
      solution.
- [ ] Confirm attendee instructions use CET/CEST plus UTC and the correct 24-hour dates.
- [ ] Confirm breaks, captions, microphones, quiet route, confidential help channel, and late-arrival path.

## Post-delivery and quarterly

- [ ] Delete temporary branches, raw captures, and unneeded incident notes according to `DATA_HANDLING.md`.
- [ ] Review aggregate feedback and recovery incidents; do not rank participants.
- [ ] Quarterly, revalidate product surfaces, policy assumptions, links, accessibility, localization, dependencies, and fallback artifacts.
- [ ] Reconcile official-source currency at least quarterly and before every
      tagged delivery. Update the `Last reconciled` date and manifest; do not
      preserve stale status labels for narrative convenience.
- [ ] Retire stale screenshots and claims; update the manifest with owner and next review date.
- [ ] Re-run a clean-room checkpoint after any repository, environment, or lab change.

## Current-product release manifest

```text
Workshop revision:
Validated on (ISO date, Europe/Berlin):
Validated by:
Copilot surface / URL:
Observed behavior and scope:
Organization policy assumptions:
Live status: green / amber / red
Local fallback:
Captured fallback:
Known limitation:
Official source:
Next validation date:
```

## Fallback artifact verification

- [ ] Capture opens without network access.
- [ ] Sensitive content is removed and independently checked.
- [ ] The capture shows enough context to understand the decision and evidence.
- [ ] Expected output is labelled as an example, never as a guaranteed result.
- [ ] Local commands and fixtures produce the stated evidence.
- [ ] A facilitator can deliver each lab from the linked artifact without improvising missing steps.
