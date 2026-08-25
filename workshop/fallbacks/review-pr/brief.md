# Brief - review a change you did not write

A pull request is waiting for your review. You did not write it, you did not watch
it being written, and the person who produced it is not available to explain it.
That is the normal case for delegated work, and it is the case this lab trains.

The default route is this captured package. It needs no network, cloud-agent
session, live pull request, or Copilot code review entitlement.

## Timing and roles

The working review ends at 14:28, the structural check ends at 14:32, and reset
finishes by 14:35. Stop finding new issues at 14:19 and open the captured
automated review at 14:22 even if your human review is incomplete.

In pairs, one person is the primary reviewer and one is the evidence editor. The
editor challenges every severity with "which line and which rule?" Rotate at
14:19: the editor leads the process and automated-review comparison. Solo
participants pause briefly at 14:19 before starting that second pass.

## The package

Everything is captured and offline. Read it in this order:

| Order | Artifact | Read it as |
|---|---|---|
| 1 | `workshop/fallbacks/review-pr/issue.md` | The task that was actually asked for |
| 2 | `workshop/fallbacks/review-pr/pr_diff.patch` | What was actually done |
| 3 | `workshop/fallbacks/review-pr/pr_description.md` | A claim about what was done, not evidence |
| 4 | `workshop/fallbacks/review-pr/captured_code_review.md` | The automated review of this exact diff - **only after your own findings are written** |

`session_transcript.md` and `review_thread.md` are Extension or targeted process
evidence. Open one only if a specific question would change your decision.

The diff is a captured artifact for reading. Do not apply it; nothing in this lab
asks you to run it, and the point is the reading.

## What you produce

`work/review_notes.md`, staged by `start`. It has five sections:

1. What you think the diff does, written **before** you read the description.
2. Your findings, each with location, severity, evidence, and a requested change.
3. The comparison against the captured automated review.
4. A decision: approve, or request changes with a named condition.
5. A three-part uncertainty sentence.

## How to prioritise

There are more findings in this diff than you have time for. Three findings with
evidence beat eleven nits. Use the six-point checklist from
[challenges/reference/evidence.md](../../../challenges/reference/evidence.md#reviewing-generated-work):
scope, invariant, tests, contracts, non-functional, explanation.

Severity is a judgement, not a property of the code. Use:

| Severity | Meaning |
|---|---|
| `blocking` | I will not approve until this changes |
| `should-fix` | I will approve, and I expect this fixed before or shortly after merge |
| `nit` | Preference. Say it once, do not insist. |

## What the verifier does not grade

`verify` checks minimum structure: required headings, non-placeholder text, two
finding blocks and fields, comparison fields, and a decision. Length and presence
checks cannot establish that a location is correct, evidence supports the claim,
severity is proportionate, the human review came first, or uncertainty is honest.

Core requires a green structural check **and** a useful human review. Supported
evidence may remain useful with a red check when the exact gap is recorded. The
room judges evidence and severity at the resync; the verifier does not.

## Optional, never required

The current product name is **Copilot cloud agent** (formerly Copilot coding
agent). A live cloud run is not part of this 45-minute lab. If the facilitator has
a prepared isolated pull request and policy/budget approval, a live Copilot code
review or cloud-agent result may be shown later in Slack B. It supplements the
captured comparison and never delays reset.
