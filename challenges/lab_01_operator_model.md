# Lab 1 - The operator model and a worked example

**Block:** 09:20-10:00 (40 minutes) - **Mode:** pairs
**Loop stages:** Understand/Plan and Explain

---

## Outcome

You can choose between an **Ask**, **Plan**, and **Agent** workflow for a concrete
task and defend the choice, and you can turn a generated explanation into
something you have personally verified.

This is the lab that sets the standard for the whole day: **you are the operator**.
The tool proposes; you decide, verify, and remain accountable.

---

## The three workflows

| Workflow | You get | Use it when | Cost of misuse |
|---|---|---|---|
| **Ask** | An answer in chat. Nothing changes on disk. | You need to understand, compare, or decide. Reading code, triaging an error, checking a convention. | Low. Wasted minutes. |
| **Plan** | A written plan you can edit before anything is executed. | The task spans several files, has ordering constraints, or has a contract you must not break. | Medium. A bad plan executed confidently. |
| **Agent** | Multi-step edits, commands, and iterations in your working tree. | The plan exists, the scope is bounded, and you can verify the result. | High. A large diff you did not ask for and cannot review. |

Two rules that survive contact with reality:

1. **Never start in Agent because you are in a hurry.** Hurry is the exact
   condition under which an unreviewable diff is most expensive.
2. **Plan is not paperwork.** A plan is the artifact that makes supervision
   possible: it is what you compare the diff against.

Reference:
<https://docs.github.com/en/copilot/how-tos/chat-with-copilot/chat-in-ide> -
<https://code.visualstudio.com/docs/agents/run/planning> -
<https://code.visualstudio.com/docs/chat/chat-overview>

---

## Artifacts you are working from

- This repository, as checked out.
- [reference/invariants.md](reference/invariants.md) - the source of truth for
  every number in this lab.
- Your evidence note ([reference/evidence.md](reference/evidence.md)).

No scenario staging is needed for Lab 1.

---

## Business invariant at stake

**INV-GREEK-1** (call delta in `[0, 1]`, put delta in `[-1, 0]`) and
**INV-VAR-1** (VaR and CVaR are non-negative loss magnitudes).

You are not being asked to fix anything. You are being asked to find out whether
what you were *told* about the code matches what these invariants require.

---

## Part A - Worked example, facilitator-led (12 minutes)

Watch one full loop on a deliberately small task. Do not type; watch the
decisions. The facilitator will narrate:

1. **Understand/Plan** - what question was asked first, and why it was not
   "fix this".
2. **Implement/Test** - how the scope was bounded before anything was accepted.
3. **Review** - one generated suggestion is **rejected on camera**, with the
   reason stated. This is the most important 60 seconds of the demonstration.
4. **Explain** - the three-part uncertainty sentence, said out loud.

What to write down: the moment the facilitator chose a workflow, and the reason
given. You will be asked for yours in Part C.

---

## Part B - Your first rep (18 minutes)

Work in pairs, one keyboard, swap after 9 minutes.

1. Pick **one** area: the VaR calculations, or the option Greeks.
2. Use **Ask** to get an explanation of how that area computes its result and what
   sign and scaling conventions it uses. Do not ask it to change anything.
3. From the explanation, extract **three factual claims** - statements that could
   be true or false, for example "put delta is returned as a negative number" or
   "vega is scaled per one percentage point of volatility".
4. **Verify two of them yourself** against
   [reference/invariants.md](reference/invariants.md) and the code. Verification
   means you ran something or read the relevant lines - not that the explanation
   sounded consistent.
5. Find **one claim you cannot verify** in the time available. Write it down.
   Every real task has one.
6. Write the uncertainty sentence from
   [reference/evidence.md](reference/evidence.md#explaining-uncertainty).

You may find a discrepancy between the explanation and the invariants. Do **not**
fix it. Note it. Lab 2 is where fixing starts, and arriving there with a real
observation is an advantage.

---

## Part C - Workflow triage (5 minutes, whole room)

For each task, decide Ask, Plan, or Agent, and give a one-clause reason. There is
more than one defensible answer for some of them; the reason is what is being
assessed.

1. "Why does the order book negate keys on one side?"
2. "Rename a helper used in four files."
3. "Move every model in this package to a new validation library."
4. "A customer says they were filled at a price that was never quoted."
5. "Add a regression test for the fix we just made."

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Part B with one claim verified instead of two. Use the L1 hint immediately if the area is unfamiliar - this is what it is for. |
| **Core** | Part B as written: three claims, two verified, one open, uncertainty sentence. |
| **Extension** | Also ask the same question a second time with a different framing (for example, ask for the sign conventions specifically). Compare the two answers and note what changed. Context shape moves output more than model choice does. |

---

## Evidence and acceptance

- [ ] Your evidence note names the workflow you chose and why
- [ ] Your evidence note names the model (Auto or approved) and the dominant
      selection factor
- [ ] Three claims are written down, and it is clear which two you verified
- [ ] Verification is evidence, not impression: a command, an output, or a line
      reference
- [ ] One unverified claim is stated explicitly
- [ ] The three-part uncertainty sentence is written and could be read aloud

---

## Resync checkpoint - 09:55

At 09:55 everyone stops, regardless of progress. Two pairs read their uncertainty
sentence aloud. Nothing in Lab 2 depends on completing Lab 1, so being
mid-sentence here costs you nothing.

If your environment is still broken at 09:55, you move to pair mode for the day.
That decision is made once, here, and not revisited every lab.

---

## Solo path

Doing this alone, later? Replace Part A by reading
[reference/evidence.md](reference/evidence.md) end to end, then do Part B exactly
as written and answer Part C in writing. Budget 30 minutes. The pair swap is a
facilitation device, not a learning requirement - but say the uncertainty sentence
out loud anyway. It is harder than it looks.

---

## Hints

[hints/lab_01.md](hints/lab_01.md) - three collapsed levels.

---

## Reflection and retrieval

1. Which of the three workflows do you personally over-use, and what does it cost
   you?
2. Without looking: what are the three parts of the uncertainty sentence?
3. You verified two claims. What made the third one hard - missing evidence,
   missing time, or missing knowledge? Those need different responses.

---

*Next: [Lab 2 - Guided incident](lab_02_incident_triage.md)*
