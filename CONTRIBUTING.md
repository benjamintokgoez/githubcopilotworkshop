# Contributing to the training substrate

This repository is a trustworthy training substrate for an advanced GitHub Copilot workshop. Changes must make exercises reproducible, safe, accessible, and honest about current product behavior. Workshop operations live under `workshop/ops/`; keep operational guidance there and do not mix it into exercises or product code.

## Scope and scenario isolation

- Keep each scenario self-contained: starter state, fixture data, expected evidence, reset path, and facilitator notes belong together.
- Use synthetic, non-sensitive data only. Never add production/customer code, credentials, tokens, personal data, or private URLs.
- Isolate scenarios with disposable branches, fixtures, and repositories. A participant must be able to reset without affecting another scenario.
- Prefer deterministic local tests and pre-created artifacts. Cloud services, model availability, network access, MCP, Actions, and organization policy must never be the only route to the learning objective.
- Label optional live paths and keep local/captured alternatives current.
- Preserve the learning loop: diagnose, identify an invariant, retrieve context, plan, generate, critically review, verify, and explain uncertainty.

## Content quality

- Write accessible international English. Add concise German participant-facing phrases where they improve DACH delivery; do not translate code, identifiers, or commands unnecessarily.
- Use real headings, short paragraphs, descriptive links, readable tables, meaningful alt text, and non-colour status cues.
- Keep keyboard, captions, zoom, reduced-motion, quiet, solo, and confidential-help alternatives in mind.
- Do not add comments, prompts, test names, or fixture labels that reveal an exercise answer. Hints should point to evidence or a question, not state the patch.
- Model uncertainty: do not claim a generated result is correct without a reproducible check. Prefer “verify with…” to unsupported certainty.
- Do not imply that a product feature, model, policy, quota, or UI is universal. Record validation date, scope, and fallback in `workshop/ops/RELEASE_CHECKLIST.md`.

## Changes and scenario review

Before opening a change:

- [ ] Identify the learning objective and the invariant it tests.
- [ ] Confirm the scenario can start from a clean checkout.
- [ ] Confirm no answer is revealed by comments, names, expected output, or setup instructions.
- [ ] Confirm the local lane works without network and the captured lane is sanitized.
- [ ] Check accessibility and localization implications.
- [ ] Add or update the reset path and facilitator intervention questions.
- [ ] Update the release manifest if product behavior, links, commands, or policy assumptions changed.

## Tests and CI

Run the smallest relevant checks, then the repository’s full required checks for release:

```bash
python -m compileall -q mittelwerk main.py scripts security_check.py tests
python -m pytest tests/ -v
python -m ruff check .
python -m ruff format --check .
python -m mypy mittelwerk main.py scripts
python -m pip check
python scripts/workshop_doctor.py --strict
python -m bandit -r mittelwerk main.py -ll
python security_check.py
```

If a check is not applicable, record why in the change description rather than silently skipping it. New or changed executable examples need deterministic tests or a documented manual verification path. Test fixture isolation, reset behavior, error handling, and privacy-safe logging. Do not add telemetry, prompt capture, or external calls merely to make a scenario observable.

## Accessibility and localization review

- Test participant-facing documents at 200% zoom and with keyboard-only navigation.
- Do not use colour as the only signal; include text labels such as `Green`, `Amber`, and `Red`.
- Provide captions/transcripts for media and written alternatives for spoken instructions.
- Check German keyboard shortcuts, decimal separators, date formats, CET/CEST plus UTC, and 24-hour times where relevant.
- Keep a solo route and a quiet/low-stimulation route for exercises.
- Route privacy, accessibility, works-council, and legal questions to the organizer; repository maintainers must not give legal advice.

## Product-current release discipline

Every delivery must have a dated manifest entry covering Copilot login and entitlement, models/Auto, Agent, cloud agent, code review, MCP, Actions/runners, organization policies, AI-credit budgets/rate limits, network/proxy/SSL, devcontainer/Codespaces, and privacy. Revalidate two weeks before delivery and quarterly thereafter. A changed UI without a tested fallback is not release-ready.

## Review standard

Reviewers should ask:

- Can a participant learn the objective if Copilot or the network is unavailable?
- Is the scenario isolated, resettable, and free of sensitive data?
- Does the exercise require evidence and critical review rather than acceptance of generated text?
- Are permissions, policy boundaries, rate limits, and uncertainty visible?
- Are accessibility, localization, break, and support paths practical?
- Are tests/CI sufficient and are comments free of answer leakage?

Keep changes surgical and explain meaningful trade-offs. Do not revert concurrent changes or modify unrelated workshop paths.
