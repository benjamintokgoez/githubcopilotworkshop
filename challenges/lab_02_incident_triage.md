# Lab 2 - Guided incident: a fill that never happened

**Block:** 10:15-11:25 (70 minutes) - **Mode:** pairs
**Loop stages:** all four - Understand/Plan -> Implement/Test -> Review -> Explain
**Scenario:** `incident-fill-price`

---

## Outcome

You take a real-shaped incident from an ambiguous ticket to a defensible change:
reproduced, localised, fixed under supervision, covered by a regression test,
reviewed, and explained - including what you are still unsure about.

This is the first lab where you change code. It is guided: the structure is given,
the answer is not.

---

## Set up

```bash
python scripts/workshop.py start incident-fill-price
python scripts/workshop.py status
python scripts/workshop.py verify incident-fill-price  # expected to fail; capture it
```

If the tooling is not available, read the artifacts directly from
`workshop/fallbacks/incident-fill-price/`. See
[reference/scenario_tooling.md](reference/scenario_tooling.md).

> **Before and after.** Your checkout was green when you arrived; the scenario is
> what introduces the failure. So run the acceptance check **immediately after**
> `start`, before you change anything, and keep the output. That failing run is
> your fail-before evidence, and the same check is what proves pass-after. See
> [reference/scenario_tooling.md](reference/scenario_tooling.md#the-healthy-baseline-contract).

Make the bounded repair in
`workshop/scenarios/incident-fill-price/work/`. Create `NOTES.md` in that
directory for your reproduction, rejected suggestion, review, and handover; reset
archives participant-added files along with the staged repair.

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

## Run the loop

### 1. Understand/Plan (target: 15 minutes)

- Read `issue.md` **before** you open any source file. Write down, in your own
  words: what the reporter observed, what they concluded, and which of those two
  you actually trust.
- Use **Ask** to orient: how does an incoming order become a fill in this
  codebase? Which components are involved? This is a map, not a diagnosis.
- **Reproduce it.** A failing reproduction that you can run on demand is the
  single most valuable artifact in this lab. Until you have one, you are guessing.
- Decide your workflow for the fix - Ask, Plan, or Agent - and write the reason
  down before you act.

A trap worth naming: the ticket contains a plausible cause. Chase it if you like,
but timebox it. Reporters describe symptoms accurately and causes speculatively.

### 2. Implement/Test (target: 20 minutes)

Supervision is the skill being trained here. Whichever workflow you chose:

- **Bound the scope before you start.** Name the files you expect to change. If
  the diff exceeds that, stop and ask why.
- **Checkpoint.** Keep the working tree clean enough that
  `python scripts/workshop.py reset incident-fill-price` is a cheap escape, not a
  disaster.
- **Interrupt early.** If a session starts refactoring, renaming, or "improving"
  code you did not ask about, stop it. Do not let it finish out of politeness.
- **Reject at least once, deliberately.** If nothing deserved rejection, you
  either got lucky or you are not reading closely enough. Write down what you
  rejected and why.
- **Write the regression test yourself, or read it as if you wrote it.** It must
  fail before the change and pass after. A test that only asserts the new
  behaviour, written after the fix, proves nothing.

### 3. Review (target: 10 minutes)

Swap keyboards. The person who did not implement reviews, using the checklist in
[reference/evidence.md](reference/evidence.md#reviewing-generated-work):
scope, invariant, tests, contracts, non-functional, explanation.

Specific things worth checking in this incident:

- Is the invariant restored, or is the symptom suppressed?
- Does the change alter behaviour for order types the ticket never mentioned?
- Are timestamps still timezone-aware UTC (INV-TIME-1)?
- Did anything about quantity accounting change as a side effect (INV-MATCH-3)?

### 4. Explain (target: 10 minutes)

Write the handover as if the desk will read it at 08:00 tomorrow:

- What the customer experienced, in one sentence, without jargon.
- Which invariant was violated.
- What changed, and the blast radius.
- The three-part uncertainty sentence.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Reproduce and localise the problem, and write the handover. Implement the fix with your pair driving, or take L2 as soon as the reproduction is stable. Reproduction plus a clear handover is a complete Supported-lane result. |
| **Core** | The full loop as written, including your own regression test and one deliberate rejection. |
| **Extension** | After the fix passes: add a test for the *adjacent* invariant nobody asked about (price-time priority at equal prices, or quantity conservation). Then answer in writing: what would have caught this in CI before it reached the desk? |

---

## Evidence and acceptance

- [ ] A reproduction that fails reliably before the change
- [ ] The violated invariant is named by its identifier
- [ ] `python scripts/workshop.py verify incident-fill-price` passes (or the
      acceptance command in `acceptance.md` if tooling is unavailable)
- [ ] A regression test that **fails on the pre-change state** and passes after -
      you can show both
- [ ] The diff touches only what the task required, and you can justify every file
      in it
- [ ] One rejected suggestion is recorded, with the reason
- [ ] Handover note written, including the uncertainty sentence
- [ ] Acceptance artifacts were not weakened to make them pass

---

## Resync checkpoint - 11:10

At 11:10 everyone stops. The facilitator states the known-good state and how to
get there:

```bash
python scripts/workshop.py verify incident-fill-price
python scripts/workshop.py reset incident-fill-price
```

Reset is for everyone, including pairs whose verifier passes. It archives the
attempt and prints its location before restoring the pre-start tree, so Lab 3 can
start from a known state.

Two pairs describe **how they localised the problem** - not what the fix was. The
method is transferable; the fix is not. If you have not finished, you have lost
nothing: Lab 3 starts from a fresh scenario.

The 20 minutes of slack at 11:25 exist for exactly this. Use them to finish, or to
get coffee. Both are correct.

---

## Solo path

Run `start`, then work the four phases with a timer: 15 / 20 / 10 / 10 minutes.
Without a pair, do the review after a deliberate five-minute break, in a diff
viewer rather than in the editor you implemented in. Reviewing your own work in
the same window is how scope creep survives.

No tooling? Reconstruct the incident from
[reference/invariants.md](reference/invariants.md#1-order-book-and-matching):
build the three-order book from the worked example, submit the market orders,
compare the fill prices you get against `101.20` and `101.455`, and start there.

---

## Hints

[hints/lab_02.md](hints/lab_02.md) - three collapsed levels. Take L1 before you
have spent 15 minutes without a reproduction.

---

## Reflection and retrieval

1. What in the ticket turned out to be a symptom, and what turned out to be an
   opinion?
2. You rejected a suggestion. What signal made you reject it, and would you have
   noticed that signal at 16:00 on a Friday?
3. Retrieval: state INV-MATCH-2 from memory, then check it.
4. Which part of this incident would have been *slower* without an assistant, and
   which part was *riskier* with one? Both answers exist.

---

*Next: [Lab 3 - Plan-driven migration](lab_03_plan_driven_migration.md)*
