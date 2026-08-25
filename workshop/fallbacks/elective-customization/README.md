# Offline fallback - elective-customization (Lab 5C)

This is the local-analysis mode when scenario tooling or a live model is
unavailable. It still produces an edited artifact, comparison, ablation, and
contradiction trace.

## Inventory

| File | What it is |
|---|---|
| `brief.md` | The task, and why the draft is scenario-local |
| `fixtures/review_criteria.md` | Mechanical criteria for judging durable context, and the four failure modes |
| `acceptance.md` | What the evidence check looks for |
| `staged_copy/instructions_draft.md.txt` | Byte-identical copy of the badly written draft |
| `staged_copy/customization_notes.md.txt` | Byte-identical copy of the before/after note template |
| `captured_acceptance_output.txt` | A captured run of the evidence check against the untouched template |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working without the tooling

1. Copy `staged_copy/` somewhere you can edit.
2. Score the draft and write a baseline local candidate for the stable review
   input in `brief.md`.
3. Rewrite three to five checkable, scoped rules, then write and score the
   after-candidate for the same input.
4. Remove one rule, repeat the comparison, and record the material difference or
   `no material difference`.
5. Trace the review-only versus patch-request contradiction and name the
   deterministic owner of the boundary. Label the result `local expected`, not
   observed Copilot behavior.

## Scope reminder

Do not edit `.github/copilot-instructions.md` or `.github/instructions/` for this
elective. The staged draft is not automatically discovered. A later live run may
explicitly attach it, which can prove content influence but not discovery,
path-scope matching, or precedence.

*Synthetic material written for the workshop.*
