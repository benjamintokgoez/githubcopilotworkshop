# Recovery playbook

Recovery is part of the design, not a failure of the participant. Name the issue, choose a lane, preserve dignity, and return to the learning objective. Never request credentials or expose private code while troubleshooting.

## Routing rule

1. Stop retries after two attempts or five minutes, whichever comes first.
2. Say what is known, what is unknown, and which fallback is active.
3. Return to the current lab’s evidence checkpoint: **Understand/Plan -> Implement/Test -> Review -> Explain**.
4. Log only aggregate issue type, status, lane, and time.

## Incident matrix

| Situation | Immediate response | Reset / fallback path |
| --- | --- | --- |
| Copilot authentication outage | Do not ask for credentials; confirm whether it is account, organization, or service scope | Offline prompt cards and captured suggestions; complete the current lab’s Supported evidence without Copilot |
| Rate limit, AI-credit budget, or quota | Stop repeated requests; notify organizer owner | Share one pre-created result, then work locally; reserve live calls for optional demo |
| Cloud-agent timeout or bad result | Cancel, preserve the branch/diff, and inspect it as untrusted output | Reset to clean branch; use manual implementation or captured run; verify tests before any reuse |
| MCP disabled or policy-blocked | Do not bypass policy or install an unapproved server | Use a fixture representing the tool response; discuss authorization and provenance |
| Actions unavailable or runner queue stuck | Save workflow text and status; do not wait beyond the timebox | Run equivalent local command and inspect captured run/artifacts; explain runner-specific differences |
| Dependency install failure | Record exact package/error and avoid changing global machine state | Use prebuilt environment/devcontainer, vendored fixture, or captured test result; do not weaken SSL or pin ad hoc |
| Repository damage or accidental broad edit | Stop editing; preserve evidence; tell the participant it is recoverable | Reset to clean checkpoint or disposable branch; reapply only the bounded change; helper owns reset commands |
| Weak network / proxy / SSL | Move immediately to the captured/offline fallback; do not disable certificate checks | Offline artifacts and tests; organizer handles network ticket after the session |
| Late arrival | Welcome privately and provide the one-page checkpoint | Join at the next dignified resync; skip live demo; pair with helper or use solo catch-up; no public apology required |
| Participant behind | Normalize different pace; remove extension task and offer a five-minute reset | Work from invariant and smallest test; helper gives one hint, then capture progress |
| Participant ahead | Preserve challenge without making them a helper by default | Offer extension: adversarial review, accessibility check, rollback, or uncertainty note; optional peer support only with consent |
| Odd numbers for pairing | Do not leave a person visibly excluded | Use triads with rotating driver/navigator/reviewer, or make the lab individual |
| Accessibility need emerges | Thank the participant; ask privately what adjustment would help | Caption/mic/quiet seat/large text/keyboard/solo Supported lane; do not request diagnosis or disclose it |
| Conduct or safety concern | Pause the interaction, ensure immediate safety, and route to named host/HR/safeguarding path | Separate people if needed; document facts only; never investigate publicly or require mediation on the spot |

## Dignified resync moments

Use these planned checkpoints so recovery does not single anyone out:

- Opening confidence poll
- After the worked example
- After each break
- Before the transfer assessment
- Closing transfer plan

Script: “This is a checkpoint for everyone. Return to **Understand/Plan -> Implement/Test -> Review -> Explain**, choose Supported/Core/Extension or captured/offline fallback, and continue. No explanation is required.”

## Reset recipes

**Clean repository reset**

1. Save only the participant’s notes or patch summary.
2. Close running tools.
3. Restore the approved clean checkpoint or create a fresh disposable branch.
4. Reproduce the original symptom.
5. Reapply the smallest bounded change.
6. Run verification and record the evidence.

**Cloud result reset**

1. Treat output as untrusted.
2. Inspect changed files and permissions.
3. Compare against the requested non-goals.
4. Discard unrelated or unverifiable changes.
5. Continue with the captured/offline fallback; mention the service result only as an example, not as proof.

**Human resync**

1. Ask “What do we know from the test?”
2. Restate the invariant in one sentence.
3. Select one next action under five minutes.
4. Ask for a confidence signal.
5. Route red issues to the helper; keep the group moving.

## Aftercare

- Host sends a concise incident note to the organizer: time, category, impact, lane, and follow-up owner.
- Remove temporary branches, captures, and fixture copies according to the retention policy.
- Do not retain full prompt logs, source code, or participant performance data unless a separately approved purpose requires it.
- Revalidate any failed product path before the next delivery; update the release manifest, not just the lab capture.
