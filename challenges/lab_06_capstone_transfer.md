# Lab 6 - Capstone: transfer across unfamiliar boundaries

<!-- journeys:card:6:start -->
## Run card

| Decision | This lab |
|---|---|
| Outcome | Build your own bounded map, test a change, review it, and explain uncertainty. |
| First action | `python scripts/workshop.py start capstone-transfer` |
| Edit boundary | workshop/scenarios/capstone-transfer/work/ only. |
| Evidence | `workshop/scenarios/capstone-transfer/work/NOTES.md`; reset archives this work. |
| Lane boundary | Supported: stated bounded checks and handover; service output may remain unfinished. Core: full suite, own risk check, review, private rubric. Extension: one extra check. |
| Delivery | Default: **local**. Routes: local, captured/offline, live. Mode does not raise or lower the lane; follow the acceptance checklist. |
| Clock | **50 elapsed minutes**; cohort **15:45-16:35 Europe/Berlin**. [Self-paced route](README.md#self-paced-route): start at T+0, pause between phases, keep the same cuts. |
| Recovery | `python scripts/workshop.py resync capstone-transfer --blocked-at <phase>`; then verify and reset. [Recovery commands](reference/scenario_tooling.md). |

**Phase clock** (elapsed minutes; solo work uses the left column):

| Elapsed | Cohort | Phase |
|---|---|---|
| T+0-4 | 15:45-15:49 | Set up |
| T+4-13 | 15:49-15:58 | Understand/Plan |
| T+13-32 | 15:58-16:17 | Implement/Test |
| T+32-38 | 16:17-16:23 | Review |
| T+38-43 | 16:23-16:28 | Explain |
| T+43-46 | 16:28-16:31 | Private rubric |
| T+46-50 | 16:31-16:35 | Verify and reset |

**Cuts — move on with honest evidence:**
- **T+10 / 15:55:** No bounded plan and first check: take L1 and narrow the lane.
- **T+20 / 16:05:** No passing slice: take L2 and choose one observable behaviour.
- **T+32 / 16:17:** Freeze behaviour; review the full diff.
- **T+46 / 16:31:** Record the last result and reset, including incomplete work.

[Return: Lab 5](lab_05_elective.md) · [Next: Lab 7](lab_07_close_and_adoption.md) · [All labs](README.md) · [Terms](README.md#terms-used-in-the-labs)
<!-- journeys:card:6:end -->

**Block:** 15:45-16:35 (50 minutes) - **Mode:** individual
**Loop stages:** Understand/Plan -> Implement/Test -> Review -> Explain
**Scenario:** `capstone-transfer`

---

## Outcome

Run the complete engineering loop alone on an unfamiliar change. Begin with the
issue and observable contracts. Build and verify your own small map of the path
needed for one decision; do not try to read the whole repository.

This is an assessment of transfer, not typing speed or feature access. A bounded,
reviewed result with honest evidence is stronger than an unreviewed full repair.
Your work and self-assessment remain private.

---

## Set up and establish the baseline - 4 minutes

```bash
python scripts/workshop.py start capstone-transfer
```

Read `workshop/scenarios/capstone-transfer/issue.md` and `acceptance.md` first.
State the requested behaviour and one non-goal in `work/NOTES.md`. Then run:

```bash
python scripts/workshop.py verify capstone-transfer
```

The first check is expected to fail. Record the command and first useful
observation before editing. Do not assume the failures share a cause.

If staging is unavailable, move immediately to
`workshop/fallbacks/capstone-transfer/`.

---

## Read these artifacts in order

**Core starts with the issue and acceptance contract, not a supplied file tour.**
Use repository search, read-only assistance, or direct reading to connect one
failure to its source and consumer. Record file or symbol references, check the
important links yourself, and stop when the map supports one reversible step.

If orientation is blocking the loop, use the
[optional Supported reading route](#supported-reading-route) or the hint ladder.
It gives file responsibilities, not a diagnosis or repair.

---

## Business invariants

- Fresh readings for asset `A` belong to the inclusive interval
  `[as_of - max_age, as_of]`.
- Stored and exchanged timestamps are timezone-aware UTC.
- The policy requires at least three fresh readings.
- Absolute deviation equal to the threshold is actionable.
- Calculation remains `Decimal`; machine JSON uses dot-decimal strings.
- Policies register through the existing metaclass mechanism.
- A recommendation is advisory. It does not automatically submit work.

Everything required is in the issue, acceptance document, staged code, and
repository instructions. No equipment-domain knowledge is assessed.

---

## Choose a route

| Route | Implement/Test evidence |
|---|---|
| **Builder** | Map the path needed for the chosen behaviour, repair one boundary at a time, add one participant-owned adversarial check for Core, and run focused checks after each batch |
| **Supervising architect** | Produce or request a candidate for one bounded batch, inspect its complete diff, make at least one evidence-based correction, and verify the same observable contract |

The architect route is not prose-only. Both routes change and test concrete
artifacts.

---

## Use the clock

Follow the [run card](#run-card). Setup is part of the 50-minute budget.
Keep time for the complete diff review, handover, private rubric, and reset.

At 16:17, stop adding behaviour. Review and handover are not optional rewards for
finishing implementation.

---

## Understand/Plan

Create a bounded map with:

1. the failing observable behaviour;
2. the public test or consumer that observes it;
3. the files crossed on that path, with evidence for each link;
4. the invariant enforced at each boundary;
5. the smallest independently verifiable repair batch; and
6. one adjacent risk you will not solve.

Do not assume all failures share one cause. Split the plan by independently
testable behaviour, not by an assistant's preferred file list. Record adjacent
risks as unknowns instead of widening the task.

---

## Implement/Test

For each batch:

1. State the files and intended behavioural change.
2. Run the narrowest relevant check before editing.
3. Permit or make only that batch.
4. Run `python scripts/workshop.py diff capstone-transfer` and read the full output.
5. Re-run the same check and record its observed result.
6. Continue only when you can explain why the result changed.

For Core, add one participant-owned `test_*.py` check for an important assumption.
Choose it from your map and the issue; do not merely copy a supplied test.
Try to disprove one claim, not to build another suite.

Interrupt an editing agent if it introduces a service switch statement, binary
float conversion, naive timestamps, automatic work-order submission, or a new
dependency.

---

## Review

Freeze code at 16:17 and review the diff using these questions:

- Does freshness include the lower bound and exclude future readings?
- Are asset filtering and input-order independence preserved?
- Is the threshold inclusive without changing insufficient-sample behaviour?
- Does every exact value remain `Decimal` until machine serialization?
- Is policy registration still automatic and discoverable?
- Did any change cross into dispatch mutation, storage, networking, or dashboard
  behaviour?
- Does the participant-owned check fail against the original staged state?

For the architect route, record the bounded correction you made to the candidate.

---

## Explain

Complete `NOTES.md` with:

- task and chosen lane;
- map and files actually changed;
- material claim challenged;
- fail-before and latest observed command results;
- blast radius and non-goals;
- what remains if incomplete; and
- the three-part uncertainty sentence.

---

## Lanes

| Lane | Completion boundary |
|---|---|
| **Supported** | Registry, freshness window, sample count, and threshold behaviour are mapped and verified; the diff is reviewed and the handover is complete. The service payload may remain explicitly unfinished. |
| **Core** | Full supplied suite passes, one participant-owned adversarial check is included, the complete diff is reviewed, and the handover and private rubric are complete. |
| **Extension** | Only after Core: one additional focused risk check or a reusable policy-change plan template. No new dependency or second feature. |

A red full verifier can accompany honest Supported evidence. It cannot be
described as Core.

---

## Partial-success protocol

If blocked or behind:

1. keep the last passing boundary;
2. stop expanding the dependency map;
3. record the exact unresolved failure;
4. review the diff you do have;
5. complete the handover; and
6. verify once and reset at 16:31.

---

## Solo path

This lab is individual in every arrangement. Use the **50-minute elapsed clock**
in the run card. At T+10, take L1 if you have no bounded plan and first check.
At T+32, freeze behaviour and read the diff in a separate view. Keep T+43-46 for
the [private rubric](../workshop/ops/ASSESSMENT_RUBRIC.md), then verify and reset
by T+50. Review and Explain are required even when implementation is incomplete.

If you pause for another day, save the phase, last check, and next safe action;
verify/reset first. Follow [pause and return](reference/scenario_tooling.md#pause-and-return)
to resume your own attempt later. Use the same lane criteria, not a new easier
task.

---

## Preserve and reset

```bash
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

Reset archives the attempt before restoring the known-good tree. Put the archive
path and first unfinished boundary into the Lab 7 remediation line.

While the room resets, answer:

**Which architectural link did you verify instead of taking on trust?**

---

## Hints

[hints/lab_06.md](hints/lab_06.md) supports mapping, batching, review, and honest
completion without identifying a defect or prescribing a repair.

### Supported reading route

<details>
<summary>Optional orientation: file responsibilities, not files to repair</summary>

Use this only when finding an initial path is blocking progress. You still need
to test each connection; the table does not say which code is wrong or must
change.

| Order | Artifact | Question it can help you answer |
|---:|---|---|
| 1 | `issue.md` | What behaviour is requested, and what is excluded? |
| 2 | `acceptance.md` | What can be observed, including the Supported check? |
| 3 | `work/test_recommendation.py` | Which public effects do the supplied checks observe? |
| 4 | `work/policy_models.py` | What types and errors cross the model boundary? |
| 5 | `work/policy_base.py` and `work/policy_catalog.py` | How are policies registered and found? |
| 6 | `work/telemetry_window.py` | How are readings selected? |
| 7 | `work/deviation_policy.py` | Where does the concrete policy calculate a result? |
| 8 | `work/recommendation_service.py` | How is the service built and its output represented? |
| 9 | `work/NOTES.md` | What does the next person need, including unfinished work? |

Stop reading when you can name one observable behaviour and its narrow check.
Keep the issue's contract as the authority, not this navigation aid.

</details>

---

## Reflection

1. Which failing observations shared a cause, and which did not?
2. Where did repository-aware assistance save navigation time?
3. Which generated suggestion would have crossed a contract boundary?
4. What evidence would you require before applying the same policy change in an
   unfamiliar production repository?

---

*Next: [Lab 7 - Close](lab_07_close_and_adoption.md)*
