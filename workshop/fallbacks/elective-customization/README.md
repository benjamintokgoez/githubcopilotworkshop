# Offline fallback - elective-customization (Lab 5C)

The customization elective is self-contained by design; this directory is the
copy you can work from when the scenario tooling is unavailable.

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
2. Measure a small repeatable task **before** adding any context, and keep the
   output.
3. Critique `instructions_draft.md` against `fixtures/review_criteria.md`, then
   rewrite it down to three to five checkable, scoped rules.
4. Measure the same task again and record the observable difference.
5. Ask for something that contradicts one of your rules and record what actually
   happened.

## Scope reminder

Do not edit `.github/copilot-instructions.md` for this elective. The staged draft
is a practice file, deliberately separate from the repository's real durable
context, which other people are working against today.

*Synthetic material written for the workshop.*
