# Scenario tooling, resets, and offline fallbacks

The labs use realistic artifacts - a ticket, log excerpts, a staged legacy module,
a pre-created pull request - rather than instructions that reveal the answer. Those
artifacts are produced by the workshop scenario system so that every attendee gets
the same starting state and can return to it.

## Command surface

| Command | What it does |
|---|---|
| `python scripts/workshop_doctor.py` | Preflight: Python version, dependency imports, repository and config structure, environment hints. It does **not** run tests or check your IDE - pair it with `pytest -q` and a manual Copilot check. |
| `python scripts/workshop.py list` | List available scenarios and their state |
| `python scripts/workshop.py start <scenario-id>` | Stage a scenario: artifacts, working tree state, checkpoint |
| `python scripts/workshop.py status` | Show the active scenario and the last checkpoint |
| `python scripts/workshop.py resync <scenario-id> --blocked-at <phase>` | Print an answer-neutral route around a blocked phase without changing files |
| `python scripts/workshop.py verify <scenario-id>` | Run the scenario's acceptance checks |
| `python scripts/workshop.py reset <scenario-id>` | Archive participant additions and restore the exact pre-start files and modes |
| `python scripts/workshop.py fallback <scenario-id>` | Print the path to the captured, non-live artifacts |

`reset` is the safety net that makes the resync checkpoints work. Use it without
embarrassment: rejoining the room is worth more than salvaging a tangled tree.

## Phase recovery without an answer key

Do not require completion of one phase before a participant may practise the
next. If a scenario lab is blocked, run:

```bash
python scripts/workshop.py resync <scenario-id> --blocked-at <phase>
```

`<phase>` is one of `tooling`, `understand-plan`, `implement-test`, `review`, or
`explain`. The command is deliberately non-mutating. It does not install a
solution, mark acceptance as passed, or reveal the defect. Instead, it gives a
short continuation route such as reviewing the incomplete diff, recording the
failing verifier honestly, writing the uncertainty statement, and resetting at
the checkpoint.

This distinction matters. Auto-completing a repair would turn the repository into
an answer key and would teach participants to trust a hidden patch. Continuing
with an incomplete artifact still teaches review, evidence, explanation, and
time-bounded recovery.

## The healthy-baseline contract

This matters more than any single command, so it is stated once, plainly:

- **A clean checkout is green.** Before you start any scenario, the doctor reports
  no failures and `pytest -q` passes. Nothing in this repository is broken on
  purpose at rest.
- **Scenarios introduce the failing state.** `python scripts/workshop.py start
  <id>` is what stages a defect, a legacy surface, or a questionable diff, and it
  tells you that it has changed your working tree.
- **`reset` restores green.** `python scripts/workshop.py reset <id>` returns you
  to the known-good checkpoint, and the baseline passes again.

Two consequences worth internalising. First, a red result **before** you start a
scenario is a real environment problem - fix it or raise it, do not shrug it off
as workshop material. Second, every scenario gives you a genuine fail-before /
pass-after pair: you can run the acceptance check immediately after `start`, watch
it fail, and use that same check to prove your change worked. Evidence you
collected before touching anything is the only kind that cannot be
rationalised afterwards.

## Scenario ids used by the labs

| Lab | Scenario id | Artifacts you should find |
|---|---|---|
| 2 | `incident-fill-price` | `issue.md`, `logs/`, `invariants.md`, `acceptance.md` |
| 3 | `migration-legacy-models` | `issue.md`, staged legacy module set, `acceptance.md` |
| 4 | `review-pr` | Pre-created PR diff, PR description, review thread, agent session transcript, captured automated code-review result |
| 5 | `elective-mcp`, `elective-cli`, `elective-customization` | Elective-specific briefs and sample configuration |
| 6 | `capstone-transfer` | Task brief, sample input, expected values, utility skeleton, and acceptance suite |

Artifacts live under `workshop/scenarios/<scenario-id>/`. Captured, non-live
copies - used when there is no network, no cloud agent, or no time - live under
`workshop/fallbacks/<scenario-id>/`.

## Fallback ladder

Work down this list until something works. Every step below the first is a normal
outcome, not a degraded workshop.

1. **Local scenario runner.** `python scripts/workshop.py start <id>`.
2. **Captured artifacts.** Read `workshop/fallbacks/<id>/` directly. The ticket,
   logs, diff and transcripts are real captures, so the analysis work is
   unchanged; only the staging is skipped.
3. **Manual fallback.** Each lab has a "Solo path" and a "No tooling" note telling
   you how to reconstruct the same starting state by hand from the repository and
   the invariants.
4. **Paired observation.** Work with someone whose environment is healthy. Being
   the reviewer in a pair is a full-value role in this workshop, and Lab 4 is built
   on exactly that skill.
5. **Phase resync.** Use the runner's `resync` command, finish the remaining loop
   stages on the incomplete attempt, then archive/reset and join the next lab.

## Offline and restricted networks

- Labs 1, 2, 3, 6 and the customization elective work without any cloud
  service beyond the Copilot connection your organisation already permits.
- Lab 4's **cloud agent** portion is optional by design. Its default path uses a
  pre-created pull request. If the cloud agent is disabled, unavailable, or slow,
  you lose a demonstration, not a learning outcome.
- Lab 4's automated-review comparison is also fully offline: a captured
  code-review result for the same diff ships under `workshop/fallbacks/review-pr/`,
  so the comparison step is completable whether or not Copilot code review is
  enabled for your account.
- The MCP elective can be completed against a local server. If your organisation
  restricts MCP servers to a registry or allowlist, that restriction **is** the
  lesson; document it instead of working around it.
- If your network blocks documentation links, ask the facilitator for the offline
  copy of the linked pages. Do not tunnel around corporate network policy.

## Enterprise and policy caveats

Nothing in this workshop assumes a feature is enabled for you.

- Availability of chat surfaces, agents, models, MCP, and code review is
  controlled by enterprise and organisation policy:
  <https://docs.github.com/en/copilot/concepts/policies> and
  <https://docs.github.com/en/copilot/reference/supported-surfaces-for-policies>.
- AI-credit allowances, paid usage, and spending budgets are real constraints in
  many organisations:
  <https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing>.
- If a lab step is blocked by policy, record it in your evidence note as a finding.
  "This workflow is not available to my team, and here is what I would need from
  our administrators" is a legitimate and genuinely useful lab outcome to take back
  to work.
