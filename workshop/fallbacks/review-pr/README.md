# Offline fallback - review-pr (Lab 4)

This is the complete Lab 4 package. It is captured, not live: identical for
everyone, no network, no cloud agent, no code-review entitlement required. It is
also the **default** path for the lab, not a degraded one.

## Inventory

| File | What it is | Read it as |
|---|---|---|
| `issue.md` | The original task, written by a human | What was asked for |
| `pr_diff.patch` | The captured multi-file diff | What was actually done |
| `pr_description.md` | The summary written with the pull request | A claim, not evidence |
| `session_transcript.md` | The unattended session record, including one abandoned attempt | What was tried |
| `review_thread.md` | Comments already on the pull request | What you are inheriting |
| `captured_code_review.md` | Automated code-review result for this exact diff | A second pass, after your own |
| `brief.md` | Copy of the scenario brief: reading order and severity vocabulary | How to work it |
| `acceptance.md` | Copy of the acceptance contract | What a complete review contains |
| `staged_copy/review_notes.md.txt` | Byte-identical copy of the staged review-note template | Your worksheet |
| `captured_acceptance_output.txt` | A captured run of the evidence check against the untouched template | What "not filled in yet" looks like |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished work that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## How to use it without the tooling

1. Read `issue.md`, then `pr_diff.patch`. Write down what you think the change
   does, before reading anything else.
2. Read `pr_description.md` and note where it differs from your reading.
3. Work the six-point checklist - scope, invariant, tests, contracts,
   non-functional, explanation - and record each finding with location, severity,
   evidence, and a requested change.
4. Only then open `captured_code_review.md` and answer: what did it find that you
   missed, what did you find that it could not see, and which of its comments
   would you not forward to the author?
5. Decide: approve, or request changes with a named condition.

If the scenario tooling is available, `python scripts/workshop.py start review-pr`
stages a review-note template with those sections already laid out, and
`verify review-pr` checks that you filled them in substantively.

## Note on the diff

`pr_diff.patch` is a reading artifact. Do not apply it: it is written against a
snapshot of the runtime, it is deliberately imperfect, and nothing in the lab
requires it to run.

## Simulation notice

Every artifact here is synthetic and written for this workshop. There is no real
author, no real reviewer, no customer data, and no real product output in this
directory. Prices, portfolios and identifiers are invented.
