# Facilitator guide: one-day advanced GitHub Copilot workshop

**Audience:** experienced developers and technical leads in a DACH enterprise setting  
**Language:** accessible international English; use the short German phrases below when helpful  
**Delivery contract:** use an organizer-tested GitHub Codespace as the easiest
starting route. Keep a tested local environment and captured/offline artifacts
ready for anyone who cannot use Codespaces. Every participant can complete the
learning objective without live cloud services.

## Canonical learning loop

**Understand/Plan -> Implement/Test -> Review -> Explain**

Use this exact wording on the facilitator screen, attendee agenda, lab briefings, resync cards, and release manifest. Do not substitute another workshop loop.

## Roles and room setup

- For first pilots, use one helper per six participants or add a floating
  technical producer. Move to 1:8-10 only after queue thresholds are met.
- Keep one visible timer and one visible “now / next / cut” board.
- Every lab uses the curriculum’s **Supported**, **Core**, and **Extension** lanes. A **captured/offline fallback** preserves the objective when a product, policy, network, or entitlement path is unavailable.
- Treat one checkout as one transactional workspace. Pairs use one driver
  terminal for scenario lifecycle commands; simultaneous work uses separate
  checkouts, not competing `start`, `verify`, or `reset` commands.
- Reinforce “map, verify, stop”: repository-aware assistance narrows an
  unfamiliar codebase to an evidence chain; it does not make reading the whole
  repository a prerequisite.
- Do not ask for passwords, tokens, production code, customer data, or screenshots containing secrets.
- Participants work in isolated training repositories and disposable branches.
- Say: **“You can pass; the goal is transfer, not tool completion.”** / **„Sie können jederzeit passen; es geht um Transfer, nicht um Tool-Vollständigkeit.“**

| Role | Before the room | During the room |
| --- | --- | --- |
| Lead facilitator | Owns objectives, timebox, safety, and cut decisions | Teaches, models uncertainty, calls resyncs |
| Helpers (1:6 for pilots; 1:8-10 only after thresholds pass) | Run preflight, know recovery lanes, check accessibility privately | Unblock without taking the keyboard; route issues |
| Technical producer | Tests display, microphones, captures, links, and offline artifacts | Watches rooms, timer, network, and fallback screen |
| Host / sponsor | Confirms policy and support path | Opens and closes; handles organizational escalations |
| Participants | Complete preflight and bring a non-sensitive scenario for Lab 7 adoption/transfer | Follow **Understand/Plan -> Implement/Test -> Review -> Explain** |

**Physical room:** U-shaped or small tables with clear sightlines; one facilitator screen; one confidence monitor if possible; power at every table; quiet seat; accessible route; printed large-text run card; visible break clock; no camera requirement.  
**Remote/hybrid:** stable host connection, captioning enabled, chat monitored by a helper, one shared help channel, breakout rooms pre-created, captions and recording policy stated before any recording.  
**Technical kit:** organizer-tested Codespace, offline copy of the starter
repository, known-good local Python 3.12 environment, test fixtures,
answer-neutral hints, sanitized captures, printed QR/short links, spare
adapters, microphones, and a local timer.

## Run of show (09:00–17:15 Europe/Berlin)

The day has **60 minutes of protected slack** in Slack A, Slack B, and Slack C, plus protected breaks and lunch. Slack is for recovery, questions, accessibility adjustments, or optional Extension work; do not fill it in advance. If all runs green, release slack as an early break or quiet work time.

| Time | Block and direct challenge link | Lead | Facilitation and observable outcome |
| --- | --- | --- | --- |
| 09:00–09:20 | [Lab 0 - Preflight and landing](../../challenges/lab_00_preflight.md) | Host + producer | Welcome, accessible-room check, support path, privacy and recording statement, Python 3.12/offline check, policy-safe lane choice, and confidence signal. Outcome: each participant can name their Supported/Core/Extension lane and fallback. |
| 09:20–10:00 | [Lab 1 - Operator model and worked example](../../challenges/lab_01_operator_model.md) | Facilitator | Model **Understand/Plan -> Implement/Test -> Review -> Explain** with a small safe example. Outcome: participants can distinguish a suggestion from evidence and record uncertainty. |
| 10:00–10:15 | **Protected break** | All | Predictable break; helpers privately triage red/amber issues. |
| 10:15–11:20 | [Lab 2 - Guided incident](../../challenges/lab_02_incident_triage.md) | Helpers | Reproduce, bound one implementation/test step, review, explain, and reset by 11:20. |
| 11:20–11:45 | **Slack A (25m)** | Facilitator | Recovery, questions, accessibility adjustment, or released Extension time. Do not make it routine Lab 2 time. |
| 11:45–12:30 | **Protected lunch** | Host | No required technical content. |
| 12:30–13:40 | [Lab 3 - Plan-driven migration](../../challenges/lab_03_plan_driven_migration.md) | Helpers | Save baseline, edit plan, verify one batch, review, explain, and reset by 13:35. |
| 13:40–13:55 | **Protected break** | All | Quiet option available; helpers privately resolve accessibility or policy needs. |
| 13:55–14:40 | [Lab 4 - Review and delegation](../../challenges/lab_04_review_and_delegation.md) | Facilitator + helpers | Human review first, then required captured automated comparison; verify/reset by 14:35. |
| 14:40–15:00 | **Slack B (20m)** | Facilitator | Recovery and resync. Optional live/cloud extras only after the room is green. |
| 15:00–15:35 | [Lab 5 - Elective (choose exactly one)](../../challenges/lab_05_elective.md) ([secure MCP](../../challenges/lab_05a_secure_mcp.md), [CLI permissions](../../challenges/lab_05b_cli_permissions.md), or [customization](../../challenges/lab_05c_customization.md)) | Helpers | One bounded control artifact, positive/negative evidence, decision, reset, and cross-elective awareness report. |
| 15:35–15:45 | **Protected break** | All | Required cognitive reset before individual assessment. No setup or sign-in. |
| 15:45–16:35 | [Lab 6 - Individual capstone transfer](../../challenges/lab_06_capstone_transfer.md) | Facilitator + helpers | Builder or supervising-architect route; actual Implement/Test evidence, self-review, private rubric, verify/reset. |
| 16:35–17:00 | [Lab 7 - Close and adoption](../../challenges/lab_07_close_and_adoption.md) | Facilitator + host | Five retrieval decisions; one Monday action, team decision, and externally owned ask; one-week repeat. |
| 17:00–17:15 | **Slack C (15m)** | Host | Final questions or quiet completion. At least ten minutes remains unused in a healthy pilot. |

## Lab lane contract

- **Supported:** the smallest complete evidence set described by the linked lab; use the lab hint or helper reset early.
- **Core:** the full lab path and its verification/review evidence.
- **Extension:** only after Core evidence is complete; offer deeper adversarial review, durable context, or policy analysis as specified by the lab.
- **Captured/offline fallback:** use sanitized captures, pre-created outputs, local fixtures, and paper/whiteboard evidence when cloud, policy, network, or access fails. A fallback is not a fourth achievement lane.
- Record achievement lane and delivery mode separately. Captured work can meet a
  Core engineering contract when the lab says so, but `live surface operated`
  remains `none`.
- Do not force pair work. Use triads with rotating roles only when useful, or provide the same Supported/Core/Extension task individually.

## Worked-example script for Lab 1 (12 minutes inside the block)

Use the linked Lab 1 example and keep the patch small and observable.

1. **Understand/Plan (3m):** state the symptom, relevant context, invariant, non-goals, and uncertainty. Ask participants what evidence would change the plan.
2. **Implement/Test (3m):** request or write a bounded change, review the diff before accepting it, and run the focused test plus one edge case.
3. **Review (3m):** challenge one plausible but unsupported claim; inspect scope, security, data-handling, accessibility, and test evidence.
4. **Explain (1–3m):** state what changed, why, evidence, remaining uncertainty, and rollback path. Say aloud whether the result is Supported or Core evidence.

Useful phrasing: “The suggestion is a draft, not evidence.” / “Der Vorschlag ist ein Entwurf, kein Beleg.” / “Show me the source, test, or assumption behind that claim.”

## Intervention questions

Use questions before touching a participant’s keyboard:

- **Understand/Plan:** What is observable? Which file or symbol is evidence? What must remain true? What is out of scope?
- **Implement/Test:** What is the smallest reversible change? Which focused test or edge case will you run?
- **Review:** What would make this unsafe? Which claim is unverified? What finding would change your decision?
- **Explain:** Can you explain the change without reopening the prompt? What remains uncertain and how would you roll back?
- Is this a capability, authorization, policy, network, or understanding problem?
- Which Supported/Core/Extension lane is appropriate right now?
- Should we use the captured/offline fallback and keep the learning objective moving?

For an over-broad patch: “Which line is required by the lab?”  
For an unverified answer: “What evidence would change your mind?”  
For a stuck participant: “Choose the Supported lane, the captured/offline fallback, or a five-minute helper reset.”

## Retrieval prompt cards

Use prompts that request evidence and uncertainty, not hidden reasoning:

```text
Read only the named repository paths. Summarise the relevant files and symbols,
with exact references. List assumptions and unknowns. Do not edit files.
```

```text
Given this symptom and invariant, propose two bounded plans. For each, list
files touched, non-goals, risks, and focused verification commands. Do not write code.
```

```text
Review this diff as a critical teammate. Find correctness, security, data-handling,
accessibility, and scope risks. Cite the changed lines and suggest tests. Do not
assume the patch is correct.
```

```text
Verify the claim using the repository tests or a small reproducible example.
Report what passed, what failed, and what remains uncertain. Do not invent results.
```

## Explicit cut list

Cut in this order when behind; never cut protected breaks, lunch, accessibility support, privacy briefing, Lab 6 individual evidence, or Lab 7 adoption guidance:

1. Any live cloud-agent, MCP, Actions, or code-review demonstration; show the sanitized capture.
2. Lab 1 optional comparison; retain one worked example and its verification.
3. Lab 2 or Lab 3 Extension work; keep Supported/Core evidence.
4. Lab 4 optional live/cloud observation and secondary transcript/thread
   reading; retain human review **and** the captured automated comparison.
5. Lab 5 live addition and Extension detail; retain the local or captured/offline control
   loop and awareness report.
6. Non-essential Q&A; move it to the approved follow-up channel.

Never cut Slack A/B/C as if it were disposable: use slack to absorb the delay, resync, or accessibility need, then stop on time.

## Operational cut triggers

| Lab | Trigger | Mandatory action |
|---|---|---|
| 0 | T+12 and not green | Assign paired work or captured/offline delivery; stop environment repair |
| 1 | First live response exceeds 90 seconds | Use the captured explanation |
| 2 | T+8 without repeatable failure | Show L1; use shipped acceptance failure |
| 2 | T+35 without bounded change | Freeze code; continue Review and Explain |
| 3 | T+10 without baseline evidence | Use baseline harness; narrow to Supported |
| 3 | T+25 without edited plan | Use plan template; require two edits |
| 3 | T+50 without one verified batch | Stop implementation; review, hand over, reset |
| 4 | T+12 without two candidate findings | Show concern-first review order |
| 4 | T+27 | Freeze human findings; open captured automated review |
| 5 | T+3 and live eligibility is not Green from T-72 | Switch to captured; do not install or authenticate |
| 5 | T+18 without positive and negative observations | Use prepared captured observations |
| 6 | T+10 without bounded plan and first check | Narrow lane or use supervising-architect route |
| 6 | T+35 without passing bounded slice | Freeze implementation; review, self-score, reset |
| 7 | T+8 | Stop retrieval; complete the three commitments |

Cut any acceptance command after 90 seconds. Record the timeout and use the
captured result; do not wait for a manifest safety timeout during delivery.

## Cross-elective awareness

Use a 30-second report card: `control / negative case / limitation`. If a branch
has no participant, read the prepared captured card. Call the result awareness,
not coverage or competence. In Lab 7, ask for one control and one limitation from
an unchosen elective.

## Resync moments and helper card

Use the planned landing, breaks, Slack A, Slack B, and Slack C so recovery does not single anyone out. Script: “This is a checkpoint for everyone. Return to **Understand/Plan -> Implement/Test -> Review -> Explain**, choose your Supported/Core/Extension lane or captured/offline fallback, and continue. No explanation is required.”

- Give a hint, not a solution; ask the participant to narrate the next action.
- Timebox one intervention to five minutes, then route to captured/offline recovery.
- Mark issues **red** (stops learning), **amber** (workaround needed), or **green** (continue).
- Never request credentials or inspect private unrelated tabs/files.
- Record only aggregate issue type and lane used, not prompts, source code, or personal performance.
