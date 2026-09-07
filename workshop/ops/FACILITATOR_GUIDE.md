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

<!-- journeys:agenda:start -->
| Time | Block | Duration |
|---|---|---|
| 09:00-09:20 | [Lab 0 - Preflight and landing](../../challenges/lab_00_preflight.md) | 20 min |
| 09:20-10:00 | [Lab 1 - Operator model](../../challenges/lab_01_operator_model.md) | 40 min |
| 10:00-10:15 | **Protected break** | 15 min |
| 10:15-11:20 | [Lab 2 - Guided incident](../../challenges/lab_02_incident_triage.md) | 65 min |
| 11:20-11:45 | **Slack A - recovery and rejoin** | 25 min |
| 11:45-12:30 | **Protected lunch** | 45 min |
| 12:30-13:40 | [Lab 3 - Plan-driven migration](../../challenges/lab_03_plan_driven_migration.md) | 70 min |
| 13:40-13:55 | **Protected break** | 15 min |
| 13:55-14:40 | [Lab 4 - Review unattended work](../../challenges/lab_04_review_and_delegation.md) | 45 min |
| 14:40-15:00 | **Slack B - recovery and rejoin** | 20 min |
| 15:00-15:35 | [Lab 5 - Choose one elective](../../challenges/lab_05_elective.md) | 35 min |
| 15:35-15:45 | **Protected break** | 10 min |
| 15:45-16:35 | [Lab 6 - Independent capstone](../../challenges/lab_06_capstone_transfer.md) | 50 min |
| 16:35-17:00 | [Lab 7 - Close and next action](../../challenges/lab_07_close_and_adoption.md) | 25 min |
| 17:00-17:15 | **Slack C - questions or quiet completion** | 15 min |
<!-- journeys:agenda:end -->

The host and producer lead landing; helpers support Labs 2, 3, and 5; the
facilitator leads Labs 1, 4, and 6 and closes Lab 7 with the host. Each linked
lab's run card names the outcome and evidence boundary. For Lab 5, choose
[secure MCP](../../challenges/lab_05a_secure_mcp.md),
[CLI permissions](../../challenges/lab_05b_cli_permissions.md), or
[customization](../../challenges/lab_05c_customization.md), not all three.

Read the card aloud in this order: **outcome, first action, edit boundary, cut**.
Define unfamiliar words using the [short glossary](../../challenges/README.md#terms-used-in-the-labs).
Show elapsed and room clocks together so solo, late-arrival, and accessibility
routes do not require mental time conversion. In Lab 6 Core, ask participants to
build their own map from the issue and contracts; do not project the optional
Supported reading route.

Before delivery, run `python scripts/workshop_journeys.py --check`. The
[journey definition](../journeys.json) generates these tables and the lab cards;
update it and regenerate rather than changing a copied clock. A captured
[simulator introduction](../../docs/SIMULATOR_WALKTHROUGH.md) is available
before the labs or during released slack. Live services are never the next
lab's prerequisite.

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

<!-- journeys:cuts:start -->
| Lab | Elapsed / cohort | Action |
|---|---|---|
| 0 | T+8 / 09:08 | Stop setup repair; choose an approved or captured route. |
| 0 | T+15 / 09:15 | Keep the route decision and privacy statement; cut Extension. |
| 1 | T+15 / 09:35 | Use the captured statement if live input is missing; stop any live wait at 90 seconds. |
| 1 | T+26 / 09:46 | Open no new code paths; finish evidence and uncertainty. |
| 1 | T+35 / 09:55 | Stop the task and review the note; cut extra triage and Extension. |
| 2 | T+8 / 10:23 | No repeatable failure: take L1 and use the supplied failure. |
| 2 | T+31 / 10:46 | Freeze implementation; review and explain the actual result. |
| 2 | T+51 / 11:06 | Stop file changes; verify once and reset before the next block. |
| 3 | T+10 / 12:40 | Missing baseline: use the harness and narrow to Supported. |
| 3 | T+25 / 12:55 | Unedited plan: use the template, make two meaningful edits, choose one batch. |
| 3 | T+46 / 13:16 | Start no new batch; review and explain. |
| 3 | T+56 / 13:26 | Freeze edits; verify once and record the actual result. |
| 3 | T+65 / 13:35 | Reset even if verification is red. |
| 4 | T+9 / 14:04 | Write your account before opening the description. |
| 4 | T+12 / 14:07 | Fewer than two concerns: take L1 and review one concern at a time. |
| 4 | T+24 / 14:19 | Find no new issues; strengthen existing findings. |
| 4 | T+27 / 14:22 | Open the captured automated review, even if your review is incomplete. |
| 4 | T+33 / 14:28 | Stop analysis; fix only missing note structure. |
| 4 | T+40 / 14:35 | Reset; do not borrow Slack B to finish Core. |
| 5 | T+3 / 15:03 | If the preflight-approved live route does not work, use the capture; no installation or sign-in. |
| 5 | T+18 / 15:18 | Stop adding configuration; use captured observations if needed. |
| 5 | T+29 / 15:29 | Stop work; verify and reset. |
| 5 | T+33 / 15:33 | Keep the control / negative case / limitation report. |
| 6 | T+10 / 15:55 | No bounded plan and first check: take L1 and narrow the lane. |
| 6 | T+20 / 16:05 | No passing slice: take L2 and choose one observable behaviour. |
| 6 | T+32 / 16:17 | Freeze behaviour; review the full diff. |
| 6 | T+46 / 16:31 | Record the last result and reset, including incomplete work. |
| 7 | T+8 / 16:43 | Stop retrieval; protect the habit and three commitments. |
| 7 | T+20 / 16:55 | Do not expand the pilot; close and save the next action. |
<!-- journeys:cuts:end -->

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
