# Release checklist

Use this checklist for each delivery release. Keep the current-product manifest with the workshop revision; do not rely on memory or screenshots without dates.

## Repository product baseline

**Last reconciled:** 2026-08-19. This records what the repository was designed
against; it is not delivery-specific sign-off and does not replace the manifest
below.

| Surface | Repository baseline | Revalidate against |
|---|---|---|
| Chat workflows | Ask, Plan, and local Agent are taught as workflow choices, subject to client and organization availability | [GitHub Copilot feature matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix), [VS Code chat overview](https://code.visualstudio.com/docs/chat/chat-overview) |
| Models | No fixed model name; use Auto or an organization-approved available model | [Auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection), [supported models](https://docs.github.com/en/copilot/reference/ai-models/supported-models) |
| Cloud agent and code review | Optional observation/comparison only; captured local evidence preserves every learning outcome | [Copilot agents](https://docs.github.com/en/copilot/concepts/agents), [Copilot code review](https://docs.github.com/en/copilot/concepts/agents/code-review) |
| MCP | QuantCore uses the official Python SDK v2; VS Code host configuration is isolated to the elective and writes are opt-in | [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk), [VS Code MCP servers](https://code.visualstudio.com/docs/agent-customization/mcp-servers) |
| Copilot CLI | Optional elective with deny/ask/allow analysis and a captured session fallback | [About Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli), [allowing tools](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools) |
| Enterprise controls | Entitlement, policy, budget, content exclusion, network, and works-council review are explicit gates | [Copilot policies](https://docs.github.com/en/copilot/concepts/policies), [policy surfaces](https://docs.github.com/en/copilot/reference/supported-surfaces-for-policies) |

## Two weeks before delivery

- [ ] Revalidate current GitHub Copilot, model/Auto, Agent, cloud-agent, code-review, MCP, Actions, runner, Codespaces/devcontainer, and organization-policy behavior against current official documentation and a disposable test path.
- [ ] Record product surface, URL, observed behavior, validation date, account/org scope, and fallback in the manifest below.
- [ ] Re-run the clean-room checkpoint from a fresh clone and clean environment.
- [ ] Verify all captures are sanitized, labelled with date and product context, and still understandable if the live UI differs.
- [ ] Run pilot checks for representative and enterprise-restricted cohorts, including proxy/SSL and accessibility paths.
- [ ] Confirm AI-credit budgets, rate limits, quotas, runner capacity, and support contacts with the organizer; do not put credentials in the manifest.
- [ ] Confirm legal/privacy/works-council review owner and the data-handling notice.
- [ ] Recheck links, commands, Python 3.12, dependencies, fixtures, test commands, and reset scripts.
- [ ] Confirm attendee and facilitator agendas use the same Lab 0–7 links, Supported/Core/Extension lane names, captured/offline fallback, and exact loop wording: **Understand/Plan -> Implement/Test -> Review -> Explain**.
- [ ] Freeze the release branch/tag only after the above evidence is attached to the internal release record.

## Day before

- [ ] Download or locally cache approved captures, starter artifacts, fixtures, and one-page run cards.
- [ ] Run the five-minute preflight smoke test.
- [ ] Verify facilitator/helper access to Supported/Core/Extension artifacts and captured/offline fallbacks.
- [ ] Confirm attendee instructions use CET/CEST plus UTC and the correct 24-hour dates.
- [ ] Confirm breaks, captions, microphones, quiet route, confidential help channel, and late-arrival path.

## Post-delivery and quarterly

- [ ] Delete temporary branches, raw captures, and unneeded incident notes according to `DATA_HANDLING.md`.
- [ ] Review aggregate feedback and recovery incidents; do not rank participants.
- [ ] Quarterly, revalidate product surfaces, policy assumptions, links, accessibility, localization, dependencies, and fallback artifacts.
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
