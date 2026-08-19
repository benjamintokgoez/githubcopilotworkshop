# Brief - review a change you did not write

A pull request is waiting for your review. You did not write it, you did not watch
it being written, and the person who produced it is not available to explain it.
That is the normal case for delegated work, and it is the case this lab trains.

## The package

Everything is captured and offline. Read it in this order:

| Order | Artifact | Read it as |
|---|---|---|
| 1 | `workshop/fallbacks/review-pr/issue.md` | The task that was actually asked for |
| 2 | `workshop/fallbacks/review-pr/pr_diff.patch` | What was actually done |
| 3 | `workshop/fallbacks/review-pr/pr_description.md` | A claim about what was done, not evidence |
| 4 | `workshop/fallbacks/review-pr/session_transcript.md` | What was attempted, including what was abandoned |
| 5 | `workshop/fallbacks/review-pr/review_thread.md` | What colleagues have said so far |
| 6 | `workshop/fallbacks/review-pr/captured_code_review.md` | The automated review of this exact diff - **only after your own findings are written** |

The diff is a captured artifact for reading. Do not apply it; nothing in this lab
asks you to run it, and the point is the reading.

## What you produce

`work/review_notes.md`, staged by `start`. It has four sections:

1. What you think the diff does, written **before** you read the description.
2. Your findings, each with location, severity, evidence, and a requested change.
3. The comparison against the captured automated review.
4. A decision: approve, or request changes with a named condition.

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

## What is not being graded

`verify` checks that your review is **substantive and complete**: real sections,
real findings with evidence, a real comparison, a real decision. It does not judge
whether your severity calls are right - a machine cannot, and pretending otherwise
would teach the wrong lesson. The room does that at the resync.

## Optional, never required

If a cloud agent and Copilot code review are enabled for you, run a live review of
the same diff as well and note where it differs from the captured one. If they are
not enabled - a normal enterprise situation - you lose a demonstration and nothing
else.
