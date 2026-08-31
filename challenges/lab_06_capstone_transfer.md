# Lab 6 - Capstone: transfer across unfamiliar boundaries

**Block:** 15:45-16:35 (50 minutes) - **Mode:** individual
**Loop stages:** all four
**Scenario:** `capstone-transfer`

---

## Outcome

You run the complete engineering loop alone on an unseen cross-module change.
The task is small enough to verify in the block, but no single file contains the
behaviour: you must map a policy registry, time-window selector, concrete policy,
application service, machine serializer, and their tests.

This is an assessment of transfer, not typing speed or feature access. A bounded,
reviewed result with honest evidence is stronger than an unreviewed full repair.
Your work and self-assessment remain private.

---

## Set up and establish the baseline - 4 minutes

```bash
python scripts/workshop.py start capstone-transfer
python scripts/workshop.py verify capstone-transfer
```

The first verification is expected to fail at several observable boundaries.
Record the command and the first useful failure. Do not diagnose every failure
before you have mapped the path they share.

If staging is unavailable, move immediately to
`workshop/fallbacks/capstone-transfer/`.

---

## Read these artifacts in order

| Order | Artifact | What to take from it |
|---:|---|---|
| 1 | `issue.md` | Required behaviour, authority, and non-goals |
| 2 | `acceptance.md` | Observable contract and focused Supported check |
| 3 | `work/test_recommendation.py` | Public effects, not an implementation recipe |
| 4 | `work/policy_models.py` | Typed time, decimal, and error boundaries |
| 5 | `work/policy_base.py` and `work/policy_catalog.py` | Registration and discovery path |
| 6 | `work/telemetry_window.py` | Shared freshness selection |
| 7 | `work/deviation_policy.py` | Concrete policy calculation |
| 8 | `work/recommendation_service.py` | Construction and machine-facing output |
| 9 | `work/NOTES.md` | Handover that remains required if code is incomplete |

Do not ask for a repository-wide fix. Ask for the smallest map from a failing
observation to its source, related contract, and downstream consumer. Require
named files and unknowns, then verify the map yourself.

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
| **Builder** | Map the complete path, repair one boundary at a time, add one participant-owned adversarial check, and run focused checks after each batch |
| **Supervising architect** | Produce or request a candidate for one bounded batch, inspect its complete diff, make at least one evidence-based correction, and verify the same observable contract |

The architect route is not prose-only. Both routes change and test concrete
artifacts.

---

## Use the clock

| Time | Stage | Required result |
|---|---|---|
| 15:45-15:49 | Set up | Expected fail-before run captured |
| 15:49-15:58 | Understand/Plan | Dependency map, invariant, non-goal, route, lane, verification |
| 15:58-16:17 | Implement/Test | Small verified batches and participant-owned adversarial check |
| 16:17-16:23 | Review | Behaviour frozen; complete diff read line by line |
| 16:23-16:28 | Explain | Handover with actual evidence and uncertainty |
| 16:28-16:31 | Private rubric | Self-score and next practice action |
| 16:31-16:35 | Preserve/reset | Final verifier recorded and scenario reset |

At 16:17, stop adding behaviour. Review and handover are not optional rewards for
finishing implementation.

---

## Understand/Plan

Create a bounded map with:

1. the failing observable behaviour;
2. the public test or consumer that observes it;
3. every file crossed before the value reaches that consumer;
4. the invariant enforced at each boundary;
5. the smallest independently verifiable repair batch; and
6. one adjacent risk you will not solve.

Do not assume all failures share one cause. Do not change the registry,
calculation, and payload in one unreviewable prompt. A useful plan separates:

- time-window membership;
- policy threshold and sample semantics; and
- service or machine-serialization behaviour.

---

## Implement/Test

For each batch:

1. State the files and intended behavioural change.
2. Run the narrowest relevant check before editing.
3. Permit or make only that batch.
4. Read the complete diff.
5. Re-run the same check and record its observed result.
6. Continue only when you can explain why the result changed.

Add one participant-owned `test_*.py` check for a material assumption not merely
copied from the supplied suite. Good checks challenge another timezone offset,
input ordering, the exact freshness boundary, negative deviation, or registry
construction. Pick one; do not build another suite.

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

---

## Reflection

1. Which failing observations shared a cause, and which did not?
2. Where did repository-aware assistance save navigation time?
3. Which generated suggestion would have crossed a contract boundary?
4. What evidence would you require before applying the same policy change in an
   unfamiliar production repository?

---

*Next: [Lab 7 - Close](lab_07_close_and_adoption.md)*
