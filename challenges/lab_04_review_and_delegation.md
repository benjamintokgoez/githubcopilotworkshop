# Lab 4 - Reviewing work you did not write

**Block:** 14:10-14:55 (45 minutes) - **Mode:** pairs
**Loop stages:** Review -> Explain
**Scenario:** `review-pr`

---

## Outcome

You review a change you did not write and did not watch being written, produce a
review a colleague could act on without you, and can state the difference between
a local Agent session and a cloud agent - including who is accountable for each.

Reviewing unattended work is the skill that decides whether delegation is safe.
It is also the skill most workshops skip.

---

## Local Agent is not the cloud agent

| | **Local Agent** (in your IDE) | **Cloud agent** (on GitHub) |
|---|---|---|
| Where it runs | Your machine, your working tree | GitHub-hosted environment |
| What it touches | Your files, your terminal, your credentials | A branch, in a pull request |
| Supervision | Live: you watch, interrupt, reject | After the fact: you read the session log and the diff |
| Typical trigger | You, in chat | An assigned issue or a delegated task |
| Failure mode | Scope creep you did not stop in time | A confident pull request nobody read closely |
| Your accountability | Total | Total. Delegation does not transfer responsibility. |

References:
<https://docs.github.com/en/copilot/concepts/agents> -
<https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent> -
<https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations> -
<https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/review-copilot-output>

### Enterprise reality, stated plainly

- The cloud agent may simply **not be enabled** for you, your organisation, or this
  repository. That is a policy decision, not a defect, and this lab does not
  depend on it.
- Delegated runs consume budget in plans that meter premium requests. Do not spend
  a team budget on a demonstration without asking:
  <https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing>.
- Agent runs on private code are subject to your organisation's policies, network
  rules, and content exclusion. If your employer has not decided how it treats
  agent-authored branches, that is a question to take home, and a good one.
- Nothing today should be run against a production repository.

---

## Set up

```bash
python scripts/workshop.py start review-pr
```

The scenario provides a **pre-created pull request**: the diff, the description
written by whoever produced it, the linked issue, and the session transcript. It
is captured, not live, so it is identical for everyone and available offline:
`workshop/fallbacks/review-pr/`.

Write your findings in
`workshop/scenarios/review-pr/work/review_notes.md`. The scenario verifier checks
that file; a separate scratch note does not count as the lab evidence.

---

## Artifacts you are working from

| Artifact | What it is |
|---|---|
| The issue | The original task, written by a human |
| The PR description | A confident summary of what was done. Treat it as a claim, not as evidence. |
| The diff | Several files. Not all of them needed to change. |
| The session transcript | What was attempted, including at least one thing that was abandoned |
| The captured automated review | A saved automated code-review result for this exact diff, under `workshop/fallbacks/review-pr/`. It exists so step 3 works for everyone, whether or not code review is enabled for your account. |

---

## Business invariant at stake

Every invariant in [reference/invariants.md](reference/invariants.md) is fair game,
because the reviewer's job is to know which ones the diff could touch. The ones
most at risk in this change: **INV-MATCH-3** (quantity conservation),
**INV-VAR-1** (VaR sign), **INV-TIME-1/2** (UTC storage, local display), and
**INV-FMT-1** (decimal comma at the edge only).

---

## Run the loop

### 1. Review before you read the summary (5 minutes)

Read the **issue** and the **diff**. Do not read the PR description yet. Write down
what you think the change does.

Then read the description. Where it differs from what you concluded, one of you is
wrong - and finding out which is the review.

### 2. Structured review (20 minutes)

Work the six-point checklist from
[reference/evidence.md](reference/evidence.md#reviewing-generated-work): scope,
invariant, tests, contracts, non-functional, explanation.

For each finding, record:

| Field | Example |
|---|---|
| Location | file and line |
| Severity | blocking / should-fix / nit |
| Evidence | what you ran, read, or checked |
| Requested change | what specifically must happen |

There are more findings in this diff than you will have time for. Prioritising is
part of the exercise: three blocking findings with evidence beat eleven nits.

Watch specifically for the four failure modes that unattended work produces:

1. **Scope creep** - files changed that the issue never mentioned.
2. **A weakened check** - a test, assertion, or validation relaxed so the change
   passes. This is the one that gets shipped.
3. **A plausible-but-wrong convention** - a sign, unit, timezone, or separator that
   looks reasonable and violates an invariant.
4. **A confident explanation** that describes intent rather than the code in front
   of you.

### 3. Second pass with automated review (10 minutes)

Now compare your review with an automated one. **Everyone does this step**, and it
needs nothing to be enabled:

- **Captured result (default).** Open the saved automated review of this exact
  diff in `workshop/fallbacks/review-pr/`. It is identical for everyone, works
  offline, and is the version the resync discussion is built on.
- **Live result (optional).** If Copilot code review is enabled for you, request a
  review on the same diff as well and use it *in addition* to the captured one.
  Where the two disagree, that difference is itself worth a sentence in your
  notes.

Read the captured review **after** you have written your own findings, not
before - being anchored by it defeats the exercise.

Reference:
<https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review>
-
<https://docs.github.com/en/copilot/concepts/agents/code-review>.

Answer in writing:

- What did it find that you missed?
- What did you find that it missed - and why could it not see that?
- Which of its comments would you **not** forward to the author, and why?

The reviewer of the reviewer is still you. An automated review is an input to your
judgement, never a substitute for it - and noticing which of its comments you
would suppress is a sharper skill than noticing which ones you would forward.

### 4. Optional bonus: watch a live delegation (parallel, unattended)

**This is a bonus. Nothing in the acceptance criteria depends on it.**

If - and only if - the cloud agent is enabled for you and the facilitator has
opened the demonstration repository:

1. At the **start** of the lab, delegate the small prepared issue and then ignore
   it. Do not watch it run; you have a review to do.
2. At 14:50, look at what came back: the branch, the diff, the session log.
3. Answer one question: **would your review of this take longer or shorter than
   the review you just did, and why?**

If it fails, is slow, is disabled, or produces something poor, that is a
legitimate and instructive outcome. Record it as an observation. The default path
for this lab is the pre-created pull request, and it always was.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Find and fully document **two** findings, at least one blocking, with evidence and a requested change. Depth over coverage. |
| **Core** | The structured review, at least three prioritised findings with evidence, plus the comparison against the captured automated review. |
| **Extension** | Write the review as you would actually post it: a summary paragraph a busy author will read, the blocking items, and an explicit accept/request-changes decision with the condition that would flip it. Then state what you would add to the repository so this class of change cannot recur. |

---

## Evidence and acceptance

- [ ] Your pre-description reading of the diff is written down, before the summary
- [ ] At least two findings (Supported) or three (Core), each with location,
      severity, evidence, and a requested change
- [ ] At least one finding is about **scope**, not correctness
- [ ] The comparison against the **captured** automated review in
      `workshop/fallbacks/review-pr/` is written, and names one thing it found
      that you missed and one thing you found that it missed. (A live code-review
      run may be added; it is never required.)
- [ ] A clear decision: approve, or request changes with a named condition
- [ ] You can state, without notes, the difference between local Agent and cloud
      agent, and who is accountable for each
- [ ] Any cloud-agent observation is recorded as a bonus note, not as a dependency
- [ ] `python scripts/workshop.py verify review-pr` passes, or its failing items
      are copied into your Lab 7 remediation note

---

## Preserve and reset - 14:45

Run the verifier, then reset even if your evidence is incomplete. Reset archives
the attempt and prints its location before restoring the pre-start tree; Lab 5
cannot start while `review-pr` remains active.

```bash
python scripts/workshop.py verify review-pr
python scripts/workshop.py reset review-pr
```

---

## Resync checkpoint - 14:50

Two pairs read out **one blocking finding and its evidence**. The room compares
severity calls - disagreement here is the useful part, because severity is a
judgement your team has to align on, not a property of the code.

The 20 minutes of slack at 14:55 absorb any overrun.

---

## Solo path

The captured pull request under `workshop/fallbacks/review-pr/` is complete and
works offline, and so is the captured automated review that sits beside it. Do
your own review first, take a ten-minute break, then open the captured automated
review and do the comparison - the full step 3, not a reduced version of it.
Nothing in this lab requires Copilot code review to be enabled. Skip the
delegation bonus entirely if the cloud agent is unavailable; it changes nothing
about the outcome.

---

## Hints

[hints/lab_04.md](hints/lab_04.md) - three collapsed levels.

---

## Reflection and retrieval

1. Which finding would you have missed if the PR description had been accurate and
   well written? That is the risk that grows as generated summaries get better.
2. Retrieval: name the four failure modes of unattended work.
3. In your own team, who currently reviews agent-authored changes, and do they know
   they are doing it?
4. What would have to be true for you to approve an agent-authored PR touching a
   payment or risk path? Write the conditions down; that list is a policy draft.

---

*Next: [Lab 5 - Elective](lab_05_elective.md)*
