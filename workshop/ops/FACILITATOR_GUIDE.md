# Facilitator guide: one-day advanced GitHub Copilot workshop

**Audience:** experienced developers and technical leads in a DACH enterprise setting  
**Language:** accessible international English; use the short German phrases below when helpful  
**Delivery contract:** every participant can complete the learning objective without live cloud services. Use pre-created repositories, fixtures, captures, and offline artifacts by default. Live cloud tooling is optional and never critical-path.

## Canonical learning loop

**Understand/Plan -> Implement/Test -> Review -> Explain**

Use this exact wording on the facilitator screen, attendee agenda, lab briefings, resync cards, and release manifest. Do not substitute another workshop loop.

## Roles and room setup

- One facilitator for each 8–10 participants, with a named helper for each room or remote breakout.
- Keep one visible timer and one visible “now / next / cut” board.
- Every lab uses the curriculum’s **Supported**, **Core**, and **Extension** lanes. A **captured/offline fallback** preserves the objective when a product, policy, network, or entitlement path is unavailable.
- Do not ask for passwords, tokens, production code, customer data, or screenshots containing secrets.
- Participants work in isolated training repositories and disposable branches.
- Say: **“You can pass; the goal is transfer, not tool completion.”** / **„Sie können jederzeit passen; es geht um Transfer, nicht um Tool-Vollständigkeit.“**

| Role | Before the room | During the room |
| --- | --- | --- |
| Lead facilitator | Owns objectives, timebox, safety, and cut decisions | Teaches, models uncertainty, calls resyncs |
| Helpers (1:8–10) | Run preflight, know recovery lanes, check accessibility privately | Unblock without taking the keyboard; route issues |
| Technical producer | Tests display, microphones, captures, links, and offline artifacts | Watches rooms, timer, network, and fallback screen |
| Host / sponsor | Confirms policy and support path | Opens and closes; handles organizational escalations |
| Participants | Complete preflight and bring a non-sensitive scenario for Lab 7 adoption/transfer | Follow **Understand/Plan -> Implement/Test -> Review -> Explain** |

**Physical room:** U-shaped or small tables with clear sightlines; one facilitator screen; one confidence monitor if possible; power at every table; quiet seat; accessible route; printed large-text run card; visible break clock; no camera requirement.  
**Remote/hybrid:** stable host connection, captioning enabled, chat monitored by a helper, one shared help channel, breakout rooms pre-created, captions and recording policy stated before any recording.  
**Technical kit:** offline copy of the starter repository, known-good Python 3.12 environment or approved devcontainer, test fixtures, answer-neutral hints, sanitized captures, printed QR/short links, spare adapters, microphones, and a local timer.

## Run of show (09:00–17:15 Europe/Berlin)

The day has **60 minutes of protected slack** in Slack A, Slack B, and Slack C, plus protected breaks and lunch. Slack is for recovery, questions, accessibility adjustments, or optional Extension work; do not fill it in advance. If all runs green, release slack as an early break or quiet work time.

| Time | Block and direct challenge link | Lead | Facilitation and observable outcome |
| --- | --- | --- | --- |
| 09:00–09:20 | [Lab 0 - Preflight and landing](../../challenges/lab_00_preflight.md) | Host + producer | Welcome, accessible-room check, support path, privacy and recording statement, Python 3.12/offline check, policy-safe lane choice, and confidence signal. Outcome: each participant can name their Supported/Core/Extension lane and fallback. |
| 09:20–10:00 | [Lab 1 - Operator model and worked example](../../challenges/lab_01_operator_model.md) | Facilitator | Model **Understand/Plan -> Implement/Test -> Review -> Explain** with a small safe example. Outcome: participants can distinguish a suggestion from evidence and record uncertainty. |
| 10:00–10:15 | **Protected break** | All | Predictable break; helpers privately triage red/amber issues. |
| 10:15–11:25 | [Lab 2 - Guided incident](../../challenges/lab_02_incident_triage.md) | Helpers | Facilitate the incident in the participant’s selected lane. Outcome: reproduction or handover, a bounded implementation/test step, and evidence-based review. At 11:10, verify and reset every active scenario. |
| 11:25–11:45 | **Slack A (20m)** | Facilitator | Dignified resync: return to the lab invariant, choose Supported/Core/Extension or captured/offline fallback, and route red issues. Use Extension only if the Core evidence is complete. |
| 11:45–12:30 | **Protected lunch** | Host | No required technical content. |
| 12:30–13:55 | [Lab 3 - Plan-driven migration](../../challenges/lab_03_plan_driven_migration.md) | Helpers | Protect baseline, plan, batch, verification, contract diff, and handover. Outcome: participants understand why a reversible plan and test evidence matter. At 13:40, verify and reset every active scenario. |
| 13:55–14:10 | **Protected break** | All | Quiet option available; helpers privately resolve accessibility or policy needs. |
| 14:10–14:55 | [Lab 4 - Review and delegation](../../challenges/lab_04_review_and_delegation.md) | Facilitator + helpers | Review work the participant did not write. Outcome: prioritized findings with locations, evidence, requested changes, and an accept/request-changes decision. Verify and reset at 14:45 before the room report. |
| 14:55–15:15 | **Slack B (20m)** | Facilitator | Resync and optional captured product demonstration. Confirm Lab 5 is exactly one elective; do not run multiple electives. |
| 15:15–15:55 | [Lab 5 - Elective (choose exactly one)](../../challenges/lab_05_elective.md) ([secure MCP](../../challenges/lab_05a_secure_mcp.md), [CLI permissions](../../challenges/lab_05b_cli_permissions.md), or [customization](../../challenges/lab_05c_customization.md)) | Helpers | Participant chooses exactly one elective and one curriculum lane. If blocked, use the relevant captured/offline artifact without changing the objective. Verify and reset the one active elective during the 15:50 resync. |
| 15:55–16:35 | [Lab 6 - Individual capstone transfer](../../challenges/lab_06_capstone_transfer.md) | Facilitator + helpers | Individual capstone and assessment. Participants use `ASSESSMENT_RUBRIC.md` for private self/peer feedback; do not collect artifacts or scores. View only an artifact a participant chooses to show. Verify and reset during the 16:30 resync. |
| 16:35–16:55 | [Lab 7 - Close and adoption](../../challenges/lab_07_close_and_adoption.md) | Facilitator + host | Adoption plan, retrieval, safe next experiment, policy route, and 1–2 week follow-up. Outcome: a bounded work-safe next action. |
| 16:55–17:15 | **Slack C (20m)** | Host | Feedback, confidential help route, final questions, and early close or quiet completion. No public scoring. |

## Lab lane contract

- **Supported:** the smallest complete evidence set described by the linked lab; use the lab hint or helper reset early.
- **Core:** the full lab path and its verification/review evidence.
- **Extension:** only after Core evidence is complete; offer deeper adversarial review, durable context, or policy analysis as specified by the lab.
- **Captured/offline fallback:** use sanitized captures, pre-created outputs, local fixtures, and paper/whiteboard evidence when cloud, policy, network, or access fails. A fallback is not a fourth achievement lane.
- Do not force pair work. Use triads with rotating roles only when useful, or provide the same Supported/Core/Extension task individually.

## Worked-example script for Lab 1 (10–15 minutes inside the block)

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
4. Lab 4 automated-review comparison; retain human critical review.
5. Lab 5 Extension detail; run exactly one elective at Supported or Core.
6. Non-essential Q&A; move it to the approved follow-up channel.

Never cut Slack A/B/C as if it were disposable: use slack to absorb the delay, resync, or accessibility need, then stop on time.

## Resync moments and helper card

Use the planned landing, breaks, Slack A, Slack B, and Slack C so recovery does not single anyone out. Script: “This is a checkpoint for everyone. Return to **Understand/Plan -> Implement/Test -> Review -> Explain**, choose your Supported/Core/Extension lane or captured/offline fallback, and continue. No explanation is required.”

- Give a hint, not a solution; ask the participant to narrate the next action.
- Timebox one intervention to five minutes, then route to captured/offline recovery.
- Mark issues **red** (stops learning), **amber** (workaround needed), or **green** (continue).
- Never request credentials or inspect private unrelated tabs/files.
- Record only aggregate issue type and lane used, not prompts, source code, or personal performance.
