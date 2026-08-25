# Preflight checklist

Use this checklist at **72 hours** and again **day-of**. It tests the delivery path, not a participant’s personal identity. Never request passwords, personal access tokens, API keys, recovery codes, or screenshots of credentials. Use organization-approved support channels for access issues.

## Status and routing

| Status | Meaning | Action |
| --- | --- | --- |
| **Green** | The path is tested with a disposable account/repository and policy-safe fixture | Use the selected Supported/Core/Extension lane |
| **Amber** | It works for some users or is policy/network dependent | Do not make it critical-path; provide the captured/offline fallback and label the limitation |
| **Red** | It is unavailable, unsafe, or not authorized | Stop retrying; route to the captured/offline fallback and open an organizer support ticket |

Record only: check, status, owner, timestamp, fallback lane, and ticket reference. Do not record credentials, full prompts, production code, or personal data.

## T-72 hours: owner sign-off

- [ ] **Objectives and artifacts:** facilitator guide, starter repository, lab branches, fixtures, expected evidence, rubric, feedback form, and all short links are versioned and locally available.
- [ ] **Python:** Python 3.12 is installed or the approved devcontainer is ready; `python --version`; virtual environment creation; dependency install from the declared bounded requirements; focused tests pass.
- [ ] **Repository:** each participant gets an isolated training repository/branch; write permissions and default branch protections are tested with a non-production identity; clean-room clone and reset procedure are verified.
- [ ] **IDE/editor:** approved editor opens the repository, terminal runs, tests discover, keyboard-only navigation works, zoom is usable, and extensions are not required for the offline fallback.
- [ ] **Copilot login and entitlement:** participant-facing sign-in route and organization policy are documented; verify with a test identity or organizer account without asking attendees to share credentials.
- [ ] **Models / Auto:** check the currently offered model selector and Auto behavior in the target client. Capture the screen and note the validation date; do not promise a model name or availability.
- [ ] **Agent mode:** test an isolated toy change, approval prompts, diff review, cancellation, and local verification. Confirm the lab can continue without it.
- [ ] **Cloud agent:** test repository policy, branch creation, timeout behavior, and bad-result recovery. Prepare a captured successful run and a deliberately safe timeout example.
- [ ] **Code review:** verify the current entry point, permissions, output location, and review limits. Pre-create a review capture; never use a live production pull request.
- [ ] **MCP:** test one approved, read-only training server and its permission boundary. Prepare a captured/offline fallback; do not connect arbitrary servers or expose tokens.
- [ ] **Actions runners:** test the workflow on the organization’s permitted runner type, queue time, permissions, network access, and artifact download. Keep a captured run and offline equivalent.
- [ ] **Organization policies:** confirm Copilot, Actions, third-party action, repository, SSO, IP allowlist, proxy, and retention settings with the organizer. The facilitator must not bypass policy.
- [ ] **AI credits / budgets / rate limits:** ask the organization owner to confirm applicable budgets, quotas, concurrency, and reset windows. Set a stop rule and do not ask for billing or credential details.
- [ ] **Network/proxy/SSL:** test DNS, GitHub endpoints, package indexes, certificate chain, WebSockets if needed, and proxy authentication flow. Provide approved CA/proxy instructions only; never disable certificate validation.
- [ ] **Devcontainer/Codespaces:** build and reopen from a clean state; check forwarded ports, extensions, storage, timeout, and offline behavior. Keep an offline environment and prebuilt artifact as fallbacks.
- [ ] **Privacy:** remove production/customer data and secrets from fixtures; inspect logs, screenshots, artifacts, and issue text; confirm recording/caption policy and the confidential help channel.
- [ ] **Accessibility:** test captions, microphone, contrast, keyboard operation, screen-reader labels where applicable, document structure, quiet seat, and solo alternative.
- [ ] **People and timing:** confirm one helper per six participants for pilots,
      or a floating technical producer; use 1:8-10 only after queue thresholds
      pass. Confirm language/time zone, accessible breaks, late-arrival route,
      and named technical/policy escalation owners.

### Required capability matrix

Publish `Green / Amber / Red`, owner, approved client/version, and fallback for:
Ask/Plan/Agent, model selector/Auto, AI-credit budget, content exclusion, cloud
agent, code review, MCP, CLI, proxy/network, and captured artifacts. Participants
confirm their route; they do not discover enterprise policy during the workshop.

Live-elective Green means:

- **5A:** exact approved MCP server plus disposable host configuration tested;
- **5B:** CLI installed, authenticated, policy-enabled, and permission behavior
  tested;
- **5C:** chat surface tested and explicit attachment method understood.

Amber/Red selects captured/local delivery before arrival. Lab 5 never installs,
authenticates, repairs proxy/SSL, requests policy changes, or activates
scenario-local drafts as real client settings.

Prepare one 30-second unrepresented-elective card for 5A, 5B, and 5C from the
validated captured fixtures: evidence label, control under review, one negative
event, and one limitation. Do not add a solution or claim live operation.

## Day-of: before doors open

- [ ] Start the Supported lane from a clean checkout; run the focused smoke test and one deliberate failure/recovery.
- [ ] Open the starter repository, fixture data, test commands, pre-created captures, rubric, linked lab files, and run-of-show tabs before participants arrive.
- [ ] Verify screen sharing, captions, microphones, timer, chat, breakout rooms, whiteboard, power, adapters, and visible support route.
- [ ] Confirm the current product UI against the release manifest; if any item differs, use the capture and note the deviation.
- [ ] Check no browser tabs, terminal history, logs, screenshots, or examples contain tokens, personal data, customer code, or private repositories.
- [ ] Give each attendee the Supported/Core/Extension choice and captured/offline fallback, plus the “pass” option; do not make sign-in a public troubleshooting exercise.
- [ ] Take an anonymous green/amber/red confidence signal; assign helpers before Lab 1.
- [ ] Confirm planned breaks and quiet space; ask privately whether anyone needs an adjustment, without asking for a diagnosis.
- [ ] If cloud status, policy, network, or credits are amber/red, announce the captured/offline fallback once and continue. Do not burn Lab 0 or Lab 1 on repeated retries.

## Five-minute smoke test

1. Open the fixture.
2. Reproduce the known issue.
3. Run the focused test.
4. Make a disposable one-line change.
5. Review the diff and revert through the documented reset path.
6. Open the capture for the optional cloud flow.

## Fallback lanes

- **Local-only (preferred):** repository, local tests, static fixtures, and preloaded editor prompts; no network dependency after setup.
- **Captured:** facilitator screen recording or screenshots with sanitized data, plus a transcript of actions and expected evidence.
- **Pair/helper:** helper drives only when an accessibility adjustment requires it; otherwise the participant retains control.
- **Paper/whiteboard:** Understand/Plan, Implement/Test, Review, and Explain checklist when a device is unavailable.

## References

- GitHub Copilot documentation: https://docs.github.com/en/copilot
- GitHub Actions documentation: https://docs.github.com/en/actions
- GitHub MCP documentation: https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp
- GitHub Codespaces documentation: https://docs.github.com/en/codespaces
- GitHub security best practices: https://docs.github.com/en/code-security
