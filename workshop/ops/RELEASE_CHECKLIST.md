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
- [ ] Verify all captures are sanitized, labelled with date and product context, and still understandable if the live UI differs.
- [ ] Run pilot checks for representative and enterprise-restricted cohorts, including proxy/SSL and accessibility paths.
- [ ] Confirm AI-credit budgets, rate limits, quotas, runner capacity, and support contacts with the organizer; do not put credentials in the manifest.
- [ ] Confirm legal/privacy/works-council review owner and the data-handling notice.
- [ ] Recheck links, commands, Python 3.12, dependencies, fixtures, test commands, and reset scripts.
- [ ] Exercise scenario lifecycle safety: fresh start/reset, exact restoration of
      a pre-existing `work/` tree, oversized-attempt fallback, interrupted-state
      recovery, and lock contention between two terminals.
- [ ] Confirm attendee and facilitator agendas use the same Lab 0–7 links, Supported/Core/Extension lane names, captured/offline fallback, and exact loop wording: **Understand/Plan -> Implement/Test -> Review -> Explain**.
- [ ] Confirm the canonical 09:00-17:15 schedule is identical everywhere:
      65/70/45/35/50/25-minute Labs 2-7, protected 15/15/10-minute breaks,
      45-minute lunch, and 25/20/15-minute Slack A/B/C.
- [ ] Confirm lane and delivery mode are orthogonal in attendee pages,
      assessment, pilot, recovery, and facilitator guidance.
- [ ] Confirm T-72 live-elective eligibility and organizer capability matrix are
      complete; no timed install/auth/proxy/policy discovery remains.
- [ ] Freeze the release branch/tag only after the above evidence is attached to the internal release record.

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
