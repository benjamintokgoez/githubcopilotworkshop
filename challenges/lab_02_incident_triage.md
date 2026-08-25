# Lab 2 - Guided incident: a fill that never happened

**Block:** 10:15-11:20 (65 minutes) - **Mode:** pairs, with solo and
captured/offline routes
**Loop stages:** all four - Understand/Plan -> Implement/Test -> Review -> Explain
**Scenario:** `incident-fill-price`

---

## Outcome

You take a real-shaped incident from an ambiguous ticket to a defensible
disposition: reproduced, localised, reviewed, and explained with honest
uncertainty. Core adds a supervised repair and independent fail-before/pass-after
regression evidence; Supported preserves the same incident reasoning when
implementation is blocked.

This is the first lab where you change code. It is guided: the structure is given,
the answer is not.

The same incident evidence supports two decisions: a developer can decide whether
a bounded repair is safe to merge, and an architect can decide whether the
diagnostic path, controls, and regression evidence are strong enough for a
client-facing system. Work on one shared artifact rather than producing separate
role reports.

---

## Set up and assumptions

Start only from the green baseline established in Lab 0, with no other active
scenario. Use the synthetic scenario only; do not paste a real ticket, client
identifier, log, or private repository content into any product.

```bash
python scripts/workshop.py status  # must report no active scenario
python scripts/workshop.py start incident-fill-price
python scripts/workshop.py verify incident-fill-price  # expected to fail; capture it
```

This verifier needs Python but no project dependencies. Its non-zero starting
result is expected **only after** the scenario starts. A red clean baseline is an
environment problem, not lab material.

If the runner is unavailable, use the complete copy under
`workshop/fallbacks/incident-fill-price/`. If Python is available, copy the two
`.txt` staged files to a participant-owned working directory and remove only the
trailing `.txt`. If execution is unavailable, use the captured failing output,
inspect the staged copies read-only, and complete the Supported evidence without
claiming a pass. See
[reference/scenario_tooling.md](reference/scenario_tooling.md).

> **Before and after.** Your checkout was green when you arrived; the scenario is
> what introduces the failure. So run the acceptance check **immediately after**
> `start`, before you change anything, and keep the output. That failing run is
> your fail-before evidence, and the same check is what proves pass-after. See
> [reference/scenario_tooling.md](reference/scenario_tooling.md#the-healthy-baseline-contract).

Make the bounded repair in
`workshop/scenarios/incident-fill-price/work/`. Create `NOTES.md` in that
directory for your reproduction, challenge decision, review, and handover; reset
archives participant-added files along with the staged repair.

Treat the staged acceptance check as read-only. Put your own focused regression
check in a separate participant-added file under `work/`.

---

## Artifacts you are working from

You should have, under `workshop/scenarios/incident-fill-price/`:

| Artifact | What it is | What it is not |
|---|---|---|
| `issue.md` | A ticket raised at **09:47 CEST** by a desk operations colleague, in their words. Includes a client complaint, an order reference, and an opinion about the cause. | An engineering diagnosis. The stated cause may be wrong. |
| `logs/` | Application log excerpts. Timestamps are stored in UTC and quoted by the desk in local time. | Complete. Some of what you want was never logged. |
| `invariants.md` | The specific invariants the desk believes were broken. | A list of files to change. |
| `acceptance.md` | The check the change must pass. | A test you may edit to make green. |

**No `BUG` map exists in this repository.** Nothing tells you which file, function,
or line is at fault. Finding that is the work.

For the timed path, open only `issue.md`, `acceptance.md`, the relevant log
excerpt, and `invariants.md` before reproducing. Open staged source only after
the failure is stable. The scenario README is recovery reference, not required
timed reading.

> **Data note.** The ticket is fictional and contains no personal data. Keep it
> that way: if you paste ticket text into a prompt, you are practising the habit
> you will use on real tickets, which do contain personal data. See
> [reference/dach_conventions.md](reference/dach_conventions.md#3-data-protection-datenschutz-and-data-minimisation).

---

## Business invariant at stake

**INV-MATCH-2 - the maker's price wins.** A market order fills at the resting
order's price. The incoming order never sets the fill price, and a fill price is
never null.

Supporting invariants you may also need: **INV-MATCH-1** (price-time priority),
**INV-MATCH-3** (quantity conservation).

The worked numbers - including the `101.455` average fill example - are in
[reference/invariants.md](reference/invariants.md#1-order-book-and-matching).
**You are not expected to know how exchanges work.** Everything required is on
that page.

---

## Timebox

| Time | Phase | Required output |
|---|---|---|
| 10:15-10:28 | **Understand/Plan** | Fail-before evidence, observed/concluded/assumed split, invariant, bounded plan |
| 10:28-10:46 | **Implement/Test** | Focused regression attempt, bounded diff or honest incomplete state, verifier result |
| 10:46-10:56 | **Review** | Evidence-based finding and scope decision |
| 10:56-11:06 | **Explain** | Desk handover and uncertainty |
| 11:06-11:20 | **Resync** | Verify once, archive/reset, share method |

Setup and reproduction are inside Understand/Plan. The external 11:20-11:45
Slack A block is protected recovery time, not hidden Core-lab budget.

---

## Run the loop

### 1. Understand/Plan (10:15-10:28)

- Read `issue.md` **before** you open any source file. Write down, in your own
  words: what the reporter observed, what they concluded, what you are assuming,
  and which statements the supplied evidence supports.
- Use **Ask**, another read-only Q&A role, or direct code reading to orient: how
  does an incoming order become a fill in this bounded scenario? This is a map,
  not a diagnosis.
- **Reproduce it.** A failing reproduction that you can run on demand is the
  single most valuable artifact in this lab. Until you have one, you are guessing.
- Name the violated invariant, one non-goal, the files you expect to touch, and
  the verification command.
- Decide the interaction role for the fix - Ask, Plan, Agent, or direct editing -
  and write the reason and action boundary before you act.

A trap worth naming: the ticket contains a plausible cause. Chase it if you like,
but timebox it. Reporters often describe symptoms more reliably than causes.

**10:23 cut:** if you do not have a runnable reproduction, take L1 and move to the
Supported or captured route. Do not spend the implementation phase searching
without a stable observation.

### 2. Implement/Test (10:28-10:46)

Supervision is the skill being trained here. Whichever workflow you chose:

- **Write one focused regression check before the repair.** Keep its failing
  result. Do not edit, delete, or weaken the supplied acceptance check.
- **Bound the scope before you start.** Name the files you expect to change. If
  the diff exceeds that, stop and ask why.
- **Checkpoint.** Inspect the diff after each meaningful step. Scenario reset is
  the archive-and-restore route, not a substitute for reading the current diff.
- **Interrupt early.** If a session starts refactoring, renaming, or "improving"
  code you did not ask about, stop it. Do not let it finish out of politeness.
- **Challenge one proposed claim or change.** Reject or narrow it when evidence
  warrants that decision. If it survives the challenge, record what evidence
  justified acceptance; do not manufacture a rejection.
- Re-run the focused check and the unchanged scenario verifier after the repair.

**10:46 cut:** stop changing code, keep the diff,
run the verifier once, and use:

```bash
python scripts/workshop.py resync incident-fill-price --blocked-at implement-test
```

Continue to Review and Explain with the honest result. An incomplete,
well-reviewed attempt is preferable to an unreviewed last-minute patch.

### 3. Review (10:46-10:56)

Swap keyboards. The person who did not implement reviews, using the checklist in
[reference/evidence.md](reference/evidence.md#reviewing-generated-work):
scope, invariant, tests, contracts, non-functional, explanation.

Specific things worth checking in this incident:

- Is the invariant restored, or is the symptom suppressed?
- Does the change alter behaviour for order types the ticket never mentioned?
- Are timestamps still timezone-aware UTC (INV-TIME-1)?
- Did anything about quantity accounting change as a side effect (INV-MATCH-3)?
- Did missing evidence expose an observability gap? Record it as a bounded
  follow-up rather than widening the incident repair.

If you are solo or only one machine is available, close the implementation view
and review from the diff after a short pause. If the diff is incomplete, review
the proposed scope, current failure, and next safe action rather than pretending
there is a completed repair.

### 4. Explain (10:56-11:06)

Write the handover as if the desk will read it at 08:00 tomorrow:

- What the customer experienced, in one sentence, without jargon.
- Which invariant was violated.
- What changed - or remains incomplete - and the blast radius.
- The acceptance status and next safe action.
- The three-part uncertainty sentence.

Use dot decimals in machine evidence and decimal commas only when quoting the
human-facing ticket. Keep UTC in logs; convert to Europe/Berlin only in the
handover when local time is useful.

---

## Pair and blocked-participant routes

- **Pair:** one person drives reproduction while the other challenges the ticket
  theory and records evidence. Swap after fail-before evidence. The implementer
  does not lead Review.
- **Live product blocked:** use direct code reading/editing and local tests. For
  the challenge step, test the ticket's proposed diagnosis or a partner's
  proposal. Copilot access is not required.
- **Runner blocked, Python available:** follow the copy-and-run route in
  `workshop/fallbacks/incident-fill-price/README.md`.
- **Read-only or no Python:** use the captured failure and staged source. Complete
  Supported evidence: observation, invariant, localization, bounded next action,
  review finding, and handover. Label all unrun verification explicitly.
- **Blocked mid-phase:** while the scenario is active, run `resync` with
  `tooling`, `understand-plan`, `implement-test`, `review`, or `explain`, then
  continue the remaining phases. The command does not install a repair or weaken
  acceptance.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Reproduce or use the captured failure, name the invariant, localise the relevant path, review one bounded next action, and write an honest handover. A pair may drive the repair, but a passing verifier is not required for Supported. |
| **Core** | Full loop: fail-before, separate regression check, bounded repair, pass-after, independent review, one evidence-based challenge decision, and handover. |
| **Extension** | After the fix passes: add a test for the *adjacent* invariant nobody asked about (price-time priority at equal prices, or quantity conservation). Then answer in writing: what would have caught this in CI before it reached the desk? |

---

## Evidence and acceptance

### Supported - complete even when implementation is blocked

- [ ] Fail-before evidence is captured from a live or supplied run and labelled
      accurately
- [ ] Observed, concluded, and assumed statements are separated
- [ ] The violated invariant is named by identifier
- [ ] The relevant path is localised and one bounded next action is justified
- [ ] One review finding records location, evidence, risk, and requested action
- [ ] Handover states the actual acceptance status and includes the uncertainty
      sentence

### Core adds

- [ ] `python scripts/workshop.py verify incident-fill-price` passes, or the
      unchanged offline acceptance command in `acceptance.md` passes
- [ ] A separate regression check demonstrably fails before and passes after
- [ ] The diff touches only required files, and every changed file is justified
- [ ] One proposed claim or change has a recorded accept, narrow, or reject
      decision with evidence
- [ ] Supplied acceptance artifacts were not edited or weakened

---

## Resync checkpoint - 11:06

At 11:06 everyone stops changing files. If blocked and the scenario is active,
run the relevant `resync` route first. Then everyone verifies once and resets:

```bash
python scripts/workshop.py verify incident-fill-price
python scripts/workshop.py reset incident-fill-price
```

Reset is for everyone, including pairs whose verifier passes. It archives the
attempt and prints its location before restoring the pre-start tree, so Lab 3 can
start from a known state.

Two volunteer pairs describe **how they localised the problem** - not what the fix
was. The method is transferable; the fix is not. A written contribution is
equally valid.

Slack A begins at 11:20, after every scenario is reset. Use it for recovery,
questions, accessibility adjustments, or Extension analysis; do not reopen the
scenario to make Core fit.

### Cut rules

1. Cut Extension first.
2. At 10:23, cut open-ended diagnosis and use L1 plus the Supported/captured
   route.
3. At 10:46, cut implementation, keep the honest result, and preserve Review and
   Explain.
4. At 11:06, cut all file changes. Never cut the final verifier/reset or turn a
   failing result into a success claim.

---

## Solo path

Budget the full 65 minutes: 13 Understand/Plan, 18 Implement/Test, 10 Review in a
diff viewer, 10 Explain, and 14 verify/archive/reset/resync. Do not
review in the same editor view you implemented in.

No runner? Use the offline working-copy or read-only route above. Do not
reconstruct a different incident when the same synthetic ticket, logs, staged
source, invariant, and captured failure are already supplied.

---

## Hints

[hints/lab_02.md](hints/lab_02.md) - three collapsed levels. Take L1 at 10:23 if
you do not have a repeatable failure.

---

## Reflection and retrieval

1. What in the ticket turned out to be a symptom, and what turned out to be an
   opinion?
2. Which proposal did you challenge, what evidence decided accept, narrow, or
   reject, and would you have checked it at 16:00 on a Friday?
3. Retrieval: state INV-MATCH-2 from memory, then check it.
4. Which part of this incident would have been *slower* without an assistant, and
   which part was *riskier* with one? Both answers exist.

---

*Next: [Lab 3 - Plan-driven migration](lab_03_plan_driven_migration.md)*
