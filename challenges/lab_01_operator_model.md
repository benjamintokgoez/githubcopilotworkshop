# Lab 1 - The operator model and a worked example

<!-- journeys:card:1:start -->
## Run card

| Decision | This lab |
|---|---|
| Outcome | Choose a workflow and verify claims without editing code. |
| First action | Open [the invariants](reference/invariants.md) and choose one calculation. |
| Edit boundary | Read-only checkout; do not repair code in this lab. |
| Evidence | `.workshop-state/notes/lab-01.md`; private and Git-ignored. |
| Lane boundary | Supported: two claims, one verified. Core: three claims, two verified. Both: one open claim and uncertainty. Extension: narrower comparison. |
| Delivery | Default: **local**. Routes: local, captured/offline, live. Mode does not raise or lower the lane; follow the acceptance checklist. |
| Clock | **40 elapsed minutes**; cohort **09:20-10:00 Europe/Berlin**. [Self-paced route](README.md#self-paced-route): start at T+0, pause between phases, keep the same cuts. |
| Recovery | Keep the actual result in your private note; use the supplied capture or approved route. |

**Phase clock** (elapsed minutes; solo work uses the left column):

| Elapsed | Cohort | Phase |
|---|---|---|
| T+0-12 | 09:20-09:32 | Worked example / solo reading |
| T+12-30 | 09:32-09:50 | Your full loop |
| T+30-35 | 09:50-09:55 | Workflow triage |
| T+35-40 | 09:55-10:00 | Review note / rejoin |

**Cuts — move on with honest evidence:**
- **T+15 / 09:35:** Use the captured statement if live input is missing; stop any live wait at 90 seconds.
- **T+26 / 09:46:** Open no new code paths; finish evidence and uncertainty.
- **T+35 / 09:55:** Stop the task and review the note; cut extra triage and Extension.

[Return: Lab 0](lab_00_preflight.md) · [Next: Lab 2](lab_02_incident_triage.md) · [All labs](README.md) · [Terms](README.md#terms-used-in-the-labs)
<!-- journeys:card:1:end -->

**Block:** 09:20-10:00 (40 minutes) - **Mode:** pairs, with solo and
captured/offline routes
**Loop stages:** **Understand/Plan -> Implement/Test -> Review -> Explain**.
For the participant task, the bounded implementation decision is deliberately
"do not change code"; Test means verifying claims.

---

## Outcome

Choose **Ask**, **Plan**, or **Agent** for one task and explain why. Map only the
code needed for that decision. Turn a generated explanation into claims you can
check yourself. The tool proposes; you decide and remain accountable.

---

## Three local interaction roles

Current GitHub and VS Code documentation uses **Ask**, **Plan**, and **Agent** for
the built-in local roles. Other supported clients may group or label them
differently. If your client does, use the equivalent action boundary and record
the label you actually see.

| Role used in this lab | Expected action boundary | Use it when | Operator check |
|---|---|---|---|
| **Ask** | Read-only Q&A and suggestions; no workspace edits. | You need to understand, compare, or decide. | Can I state claims that evidence could prove wrong? |
| **Plan** | Read-only research and an implementation plan for review before handoff. | The task spans files, has ordering constraints, or must preserve a contract. | Are scope, non-goals, risks, and verification explicit? |
| **Agent** | Local edits, tool calls, commands, and iteration. | The task is bounded and you can supervise and verify it. | Which tools, approvals, isolation, stop rule, and rollback apply? |

The local Agent role is not the GitHub-hosted **cloud agent**. A role selection is
also not an authorization control: client policy, enabled tools, approvals,
sandboxing, and repository permissions still decide what can happen.

Plan is a product-gated role, not merely the phrase "make a plan". On supported
clients it uses read-only planning tools, produces a structured artifact for
review, and requires an explicit **Start Implementation** or equivalent handoff
before edits. If that role is unavailable, request a read-only plan and record
that you used the fallback rather than claiming the product workflow.

Three rules that survive contact with reality:

1. **Use the least authority the next step needs.** Hurry is not a reason to grant
   edit or command access.
2. **Plan is not paperwork.** It is an inspectable artifact that makes scope and
   verification reviewable before implementation.
3. **A mode or model is not evidence.** The source, diff, command, and observed
   result decide whether the output is safe to use.

Reference:
<https://docs.github.com/en/copilot/how-tos/chat-with-copilot/chat-in-ide> -
<https://code.visualstudio.com/docs/agents/run/planning> -
<https://code.visualstudio.com/docs/agents/run/agent-harnesses>

---

## Artifacts you are working from

- This repository, as checked out.
- [reference/invariants.md](reference/invariants.md) - the source of truth for
  every number in this lab.
- Your evidence note ([reference/evidence.md](reference/evidence.md)).

No scenario staging or network-only feature is needed for Lab 1.

---

## Business invariant at stake

**INV-SLA-1** (operational magnitudes are non-negative), **INV-SLA-2**
(overdue hours cannot exceed open hours), and **INV-SLA-4** (utilization is
bounded).

You are not being asked to fix anything. You are being asked to find out whether
what you were *told* about the code matches what these invariants require.

---

## Part A - Worked example, facilitator-led (09:20-09:32)

Watch one full loop on a deliberately small task. Do not type; watch the
decisions. The facilitator will narrate:

1. **Understand/Plan** - what question was asked first, and why it was not
   "fix this".
2. **Implement/Test** - how the scope was bounded before anything was accepted.
3. **Review** - one generated suggestion is **rejected in the demonstration**,
   with the reason stated. Recording is not required.
4. **Explain** - the three-part uncertainty sentence, said out loud.

Write down the moment the facilitator chose an interaction role, the authority it
granted, and the reason. You will be asked for your decision in Part C.

---

## Part B - Your first rep (09:32-09:50)

Work in pairs with one driver and one evidence challenger. Swap after the first
verified claim or at 09:41, whichever comes first. Speaking is optional; the
challenger may use the shared note.

### Understand/Plan - 3 minutes

1. Pick **one** area: overdue-workload calculations or capacity utilization.
2. Choose the read-only Q&A role - **Ask** in current VS Code/GitHub
   documentation - or your client's equivalent. Record why editing authority is
   unnecessary.
3. Ask for the shortest repository map from the public result to the calculation
   and one relevant test or consumer. Require named files or symbols, sign, unit,
   scaling and boundary conventions, plus unknowns. Do not ask for every related
   file or for a change.

### Implement/Test - 8 minutes

4. Extract **three factual claims** from the explanation. Each must be capable of
   being true or false. Supported may stop after two claims.
5. **Verify two claims yourself** against
   [reference/invariants.md](reference/invariants.md) and the code. Verification
   means a command plus observed result, or a precise line reference - not that
   the explanation sounded plausible. Supported may stop after one verified
   claim.

No live Q&A? Use the facilitator's captured explanation from Part A, or treat
this synthetic statement as untrusted input:

> The selected calculation follows the repository's sign and scaling conventions
> and handles its boundary inputs consistently.

Split it into claims and verify it exactly as you would a generated response.
The offline input is evidence to test, not an answer.

### Review - 4 minutes

6. Mark every claim **verified**, **contradicted**, or **open**. Check whether the
   response cited evidence it actually used and whether it crossed the read-only
   boundary.
7. Keep at least one open claim. State whether the blocker is time, evidence,
   access, or knowledge; those require different next actions.

### Explain - 3 minutes

8. Write the three-part uncertainty sentence from
   [reference/evidence.md](reference/evidence.md#explaining-uncertainty).
9. Record the model selection as `Auto`, the approved model you selected, or
   `captured/offline`. If Auto was selected, do not invent the routed model; add
   it only when the client reports it.

You may find a discrepancy between the explanation and the invariants. Do **not**
fix it. Note it. Lab 2 is where fixing starts, and arriving there with a real
observation is an advantage.

---

## Part C - Workflow triage (09:50-09:55, whole room)

For each task, decide Ask, Plan, or Agent, and give a one-clause reason. There is
more than one defensible answer for some of them; the reason is what is being
assessed.

1. "Why is the provider-capacity queue ordered by rate and arrival time?"
2. "Rename a helper used in four files."
3. "Move every model in this package to a new validation library."
4. "Operations says an assignment used a service rate no provider offered."
5. "Add a regression test for the fix we just made."

Decide all five silently in the first minute. The facilitator calls only items
1, 3, and 4 unless the room is ahead; items 2 and 5 are the cut. For one answer,
name the approval, isolation, or review control you would require in addition to
the role selection.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Use live or offline input. Verify one falsifiable claim, name one open claim and why it is open, and write the uncertainty sentence. Take L1 after three minutes without a claim. |
| **Core** | Three claims, two independently verified, one open, a reviewed action boundary, and the uncertainty sentence. |
| **Extension** | Ask the same question with a narrower framing. Compare scope, caveats, and cited evidence without attributing the difference to a model unless you controlled for it. State one control required before handing the task to an editing agent. |

---

## Evidence and acceptance

| Evidence | Supported | Core |
|---|:---:|:---:|
| Local role or equivalent is named, with the reason and action boundary | Required | Required |
| Model source is recorded as Auto, approved selection, or captured/offline; one selection factor is named | Required | Required |
| Falsifiable claims are written | At least 2 | 3 |
| Claims independently verified by command/result or precise line reference | 1 | 2 |
| One claim is open, with the blocker classified | Required | Required |
| Response is reviewed for evidence and boundary crossing | Required | Required |
| Three-part uncertainty sentence is written | Required | Required |

An offline or Supported result is complete when its column is satisfied. It does
not need a live product response or Core claim count.

---

## Resync checkpoint - 09:55

At 09:55 everyone stops, regardless of progress. Two volunteer pairs share an
uncertainty sentence in writing or aloud. Nothing in Lab 2 depends on completing
Core here.

If no response arrived, use the offline statement and verify one claim. If no
command can run, use a precise code and invariant reference. Record the
limitation, then select a default local, captured/offline, solo, pair, or helper
route for the next block. Reconsider it only at a planned checkpoint; do not
spend each lab repeating setup work.

### Cut rules

1. At 09:35, cut the live request and use the offline input if no usable response
   exists.
2. At 09:46, stop opening new code paths. Finish one evidence item and the
   uncertainty sentence.
3. Cut Part C items 2 and 5, then Extension. Do not cut independent verification
   or honest uncertainty.

---

## Solo path

Use the run card's **40-minute elapsed clock**: 12 minutes for the role table,
[reference/evidence.md](reference/evidence.md), and the worked-loop decisions;
18 for Part B; 5 for Part C; 5 to review the note and move on.
Use live Q&A or the offline statement. Close the response before your review
pass. At T+26, open no new paths: finish evidence and uncertainty. Write your
answers; speaking aloud is not required.

---

## Hints

[hints/lab_01.md](hints/lab_01.md) - three collapsed levels.

---

## Reflection and retrieval

1. Which of the three workflows do you personally over-use, and what does it cost
   you?
2. Without looking: what are the three parts of the uncertainty sentence?
3. What made the open claim hard - missing evidence, access, time, or knowledge?
   Those need different responses.

---

*Next: [Lab 2 - Guided incident](lab_02_incident_triage.md)*
