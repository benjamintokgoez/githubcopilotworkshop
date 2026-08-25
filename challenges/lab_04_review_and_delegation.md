# Lab 4 - Reviewing work you did not write

**Block:** 13:55-14:40 (45 minutes) - **Mode:** pairs or solo
**Loop stages:** Review -> Explain
**Scenario:** `review-pr`
**Hard reset:** 14:35

---

## Outcome

You review a change you did not write or watch being written, produce prioritised
findings another contributor could act on, compare your judgement with an
automated review, and make an explicit review decision.

The default route is captured and offline. No cloud run, live pull request, or
Copilot code review entitlement is needed. Forty-five minutes is enough for the
Core route only when the reading order and cut times are protected.

---

## Local agent session and Copilot cloud agent

**Copilot cloud agent** is the current name for the product formerly called
**Copilot coding agent**. In VS Code, the broader **Cloud** session target may
also list third-party cloud agents; this lab means GitHub's Copilot cloud agent.

| | **Local agent session in VS Code** | **Copilot cloud agent session** |
|---|---|---|
| Execution | On your machine, using a local harness; changes go to the current folder or an isolated worktree, depending on the harness and selection | In a GitHub Actions-powered ephemeral environment; changes go to one repository branch |
| Working style | Interactive or background; you can inspect and steer the session in VS Code | Asynchronous; you can monitor and steer it from its session log |
| Result | Local workspace/worktree changes that you decide whether to keep and commit | A branch first; a pull request is created when requested or when you choose to create it |
| Context boundary | Local workspace, enabled tools, and approved permissions | Repository context and cloud-configured tools; no access to your local editor state or terminal context |
| Review evidence | Conversation, tool output, commands, tests, and diff | Session log, signed commits, checks, and diff or pull request |
| Responsibility | You validate and decide what to keep | Humans still review and merge; the cloud agent cannot approve or merge its own work |

Neither a session log nor a confident pull request description proves the change
is correct. They are process evidence to compare with the issue, code, and
observed checks.

### Availability and responsibility boundaries - checked 2026-08-25

- Copilot cloud agent is available with paid Copilot plans, but enterprise or
  organisation policy and repository settings can disable it. It consumes AI
  credits and GitHub Actions minutes, and budget controls can block usage.
- Copilot code review is generally available on supported plans and surfaces,
  subject to policy and budget. It consumes AI credits and uses GitHub Actions
  minutes. A review from Copilot is always a **Comment**: it does not approve,
  request changes, satisfy required approvals, or block a merge.
- **AI credits** is the current general billing term. **Premium requests** now
  refers only to eligible legacy request-based annual Pro and Pro+ subscriptions;
  do not use it as a generic label for current cloud-agent or review usage.
- Cloud-agent sessions are shared with repository collaborators by default;
  local sessions are unshared by default unless explicitly shared. Do not put
  secrets, personal data, or production material in a demonstration.
- The VS Code Agents window is Preview. This lab does not require it.
- The cloud agent can research, propose a plan, and accept iteration before a
  pull request is created. Automations are GA for eligible private/internal
  repositories; custom agents are GA on GitHub.com. Both add scale, not reduced
  accountability, and require separate trigger, tool, approval, cost, and review
  decisions.
- Code-review effort and context are trade-offs. Current **Lite** and
  **Balanced** choices trade latency/cost against reasoning depth and repository
  context. Use higher effort for complex, security-sensitive, or cross-service
  work. More effort can consume more AI credits and runner time; neither setting
  replaces human review.
- Third-party coding agents are governed separately. Hooks can add deterministic
  lifecycle controls on supported surfaces; rationale or confidence labels from
  an automation remain process metadata, not authorization.

Official references:

- <https://github.blog/changelog/2026-04-01-research-plan-and-code-with-copilot-cloud-agent/>
- <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-cloud-agent>
- <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-automations>
- <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-custom-agents>
- <https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/manage-and-track-agents>
- <https://docs.github.com/en/copilot/concepts/agents/cloud-agent/risks-and-mitigations>
- <https://docs.github.com/en/copilot/concepts/agents/code-review>
- <https://docs.github.com/en/copilot/how-tos/use-copilot-agents/request-a-code-review/use-code-review>
- <https://github.blog/changelog/2026-06-01-updates-to-github-copilot-billing-and-plans/>
- <https://docs.github.com/en/copilot/reference/copilot-billing/request-based-billing-legacy/copilot-requests>
- <https://docs.github.com/en/copilot/concepts/policies>
- <https://docs.github.com/en/copilot/concepts/billing/budgets-for-usage-based-billing>

---

## Set up and choose roles - 13:55-13:59

```bash
python scripts/workshop.py start review-pr
python scripts/workshop.py verify review-pr  # expected to fail on the empty template; save it
```

Write only in
`workshop/scenarios/review-pr/work/review_notes.md`. The pull request package
under `workshop/fallbacks/review-pr/` is the default reading set, not a degraded
fallback. Do not apply its patch.

For pairs:

- **Primary reviewer:** reads the issue and diff, calls severity, and proposes the
  requested change.
- **Evidence editor:** records location, rule or contract, observation, and
  requested change; challenges unsupported severity.
- **Rotate at 14:19.** The evidence editor leads the session-log and automated
  review comparison; the first reviewer challenges what should be forwarded.

Solo participants use two distinct passes: write the human review first, pause
briefly at 14:19, then return as reviewer of the process and automated
comments.

---

## Artifacts and reading order

| Order | Artifact | Treat it as |
|---:|---|---|
| 1 | The issue | What was requested and explicitly excluded |
| 2 | The diff | What changed |
| 3 | Your pre-description note | Your independent account of the change |
| 4 | The pull request description | A claim to test, not evidence |
| 5 | The synthetic session transcript | Extension or targeted evidence when a final-diff question requires process context |
| 6 | The review thread | Extension or targeted evidence when an inherited assertion affects your decision |
| 7 | The captured synthetic automated review | A second pass, opened only at 14:22 |

The transcript and captured automated review are synthetic workshop artifacts.
They model review inputs without reproducing personal prompts, private code, or
real product output.

---

## Business invariants

Use the issue and
[reference/invariants.md](reference/invariants.md) to identify which contracts
each changed file could affect. Consider business, API, test, security, privacy,
and non-functional boundaries, but record only connections supported by a
specific changed line.

Do not assume a named invariant is violated. Establish the connection from the
issue and diff.

---

## The 45-minute route

| Clock | Budget | Phase | Required output |
|---|---:|---|---|
| 13:55-13:59 | 4 min | Start and orient | Empty-template fail-before run, roles |
| 13:59-14:04 | 5 min | Independent read | Issue + diff account written before summary |
| 14:04-14:19 | 15 min | Structured human review | Two or three prioritised findings with evidence |
| 14:19-14:22 | 3 min | Process check and decision | Description/log/thread comparison; role rotation |
| 14:22-14:28 | 6 min | Automated-review comparison | Three comparison statements |
| 14:28-14:32 | 4 min | Verify and cut | Structural check fixed or honest gap recorded |
| 14:32-14:35 | 3 min | Reset | Attempt archived; scenario inactive |
| 14:35-14:40 | 5 min | Room resync | Blocking call and evidence, not a defect count |

### Stop and cut decisions

- **14:04:** stop reading the diff and write your independent account. Do not
  consume the summary first.
- **14:07:** if you do not have two candidate concerns, take L1 and switch to
  concern-first review.
- **14:19:** stop searching for more findings. Fully evidence the best two or
  three; discard unsupported nits. Rotate roles.
- **14:22:** open the captured automated review even if your own review is
  incomplete. Comparison is a Core skill, not an optional reward for finding
  everything.
- **14:28:** stop analysis. Run the verifier and correct only missing note
  structure; do not invent evidence to make it green.
- **14:35:** reset. Do not use Slack B to finish findings unless the facilitator
  explicitly releases Extension time after the room is resynchronised.

---

## Run the review

### 1. Independent read - 5 minutes

Read the issue and diff only. In two or three sentences, record:

- what the change appears to do;
- its actual file scope;
- the highest-risk contract it could affect.

Write this before opening the pull request description. The timestamp is not
important; the order is.

### 2. Structured human review - 15 minutes

Use the six concerns from
[reference/evidence.md](reference/evidence.md#reviewing-generated-work): scope,
invariant, tests, contracts, non-functional behaviour, and explanation.

For each finding, record:

| Field | Required evidence |
|---|---|
| Location | File and line or patch hunk precise enough for the author |
| Severity | `blocking`, `should-fix`, or `nit` |
| Evidence | The issue rule or invariant, the changed code, and the observed conflict or risk |
| Requested change | A specific outcome, not "please fix" |

At least one finding must evaluate scope. Two findings with traceable evidence
are Supported; a third makes the Core set. Both beat eleven observations with no
consequence. A changed test is evidence about
what the author chose to assert; a green test claim is not proof that the test
remained strong.

### 3. Check the description and decide - 3 minutes

Open the pull request description. Use it to answer:

- Which claim is supported by the diff?
- Which claim remains unsupported or contradicted?
- Do the recorded commands test the issue's contract, or only produce green
  output?

Then make a provisional decision: `approve` or `request changes`, with the
specific condition that would reverse it. Open the transcript or review thread
only if one targeted process question would change that decision; otherwise they
are Extension reading. Process records never lower the evidence bar.

### 4. Compare with the captured automated review - 6 minutes

Only now open `captured_code_review.md`. Record:

- one useful comment it produced that your review missed;
- one material concern your review produced that it missed, plus why its available
  context or prioritisation may not have surfaced it;
- one comment you would not forward, with the contract or trade-off that makes it
  unhelpful.

Do not count comments. Compare relevance, evidence, severity, and actionability.
The final approve/request-changes decision remains yours.

If the facilitator has a prepared isolated pull request and live Copilot code
review is pre-approved for policy and budget, a live result may be shown in
Slack B. It supplements the captured comparison; it never replaces it or delays
reset.

---

## Outcomes

| Lane | Evidence-complete outcome |
|---|---|
| **Supported** | Independent pre-description account, two fully structured findings with at least one scope assessment, complete captured automated-review comparison, explicit decision and condition, honest verifier result, uncertainty sentence, and reset. |
| **Core** | Supported evidence plus at least three prioritised findings, the complete captured automated-review comparison, green structural verifier, and reset. Findings include both scope and a contract or invariant concern. |
| **Extension** | Only after Core: rewrite the note as a concise review you would post, and name one repository control that would reduce recurrence. Use released Slack B time only; never delay reset. |

The captured/offline route is the normal route and supports Core. A live product
run does not raise the achievement lane.

---

## A green note is not necessarily a useful review

`python scripts/workshop.py verify review-pr` checks note structure: required
headings, non-placeholder text, two finding blocks and fields, comparison fields,
and an explicit decision. It cannot judge whether a location is correct,
evidence supports the claim, severity is proportionate, the scope assessment is
sound, the human review came first, or the uncertainty sentence is honest.

Core therefore requires both a green structural verifier and human-readable
evidence. Supported evidence can remain useful with a red verifier if the exact
gap is recorded before reset.

### Evidence checklist

- [ ] Empty-template fail-before output was saved
- [ ] Diff account was written before opening the description
- [ ] Each finding has traceable location, severity, evidence, and requested change
- [ ] Scope was assessed against the issue, not the pull request summary
- [ ] Test changes were reviewed as part of the behaviour change
- [ ] Any transcript/thread claim used was treated as process evidence, not
      correctness evidence
- [ ] Captured automated review was opened only after the human findings
- [ ] Comparison covers useful, missed, and suppressed comments with reasons
- [ ] Decision and condition that would reverse it are explicit
- [ ] Three-part uncertainty sentence separates checked, assumed, and unknown
- [ ] Actual verifier result was recorded
- [ ] Reset completed and the archive location was noted

---

## Facilitator cues

- Keep the pull request description, transcript, thread, and automated review
  closed until their clock points. Protect the independent first pass.
- At 14:19, announce "no new findings" and rotate pair roles. Help participants
  strengthen evidence; do not point to defect locations.
- At 14:22, require the captured comparison. Do not troubleshoot a live product
  path during the lab.
- At 14:28, announce the analysis freeze; at 14:35, verify that every active
  scenario resets.
- Announce and post every cut time; do not rely on colour, a projected timer, or
  one participant relaying instructions. Pairing is optional.
- During resync, ask for one blocking call, the evidence, and the condition that
  would change the decision. Disagreement about severity is useful; a contest to
  count hidden findings is not.

---

## Solo and captured/offline routes

Solo work uses the same clocks. The role change at 14:19 prevents the
automated review from becoming an answer key: first defend your own evidence,
then challenge it.

The complete package under `workshop/fallbacks/review-pr/` is the default route
and works offline. If the scenario runner is unavailable, copy the staged
review-note template to a permitted working location and perform the same ordered
review. Mark the verifier output as captured rather than personally executed.

---

## Hints

[hints/lab_04.md](hints/lab_04.md) - three collapsed levels.

---

## Reflection and retrieval

1. Which evidence changed your severity call, rather than merely adding another
   comment?
2. What can a session log establish, and what can only the diff and contract
   establish?
3. Why can Copilot code review comment without satisfying a required approval?
4. Which team policy should govern cloud-agent tasks, review ownership, and AI
   credit budget before you delegate production work?

---

*Next: [Lab 5 - Elective](lab_05_elective.md)*
