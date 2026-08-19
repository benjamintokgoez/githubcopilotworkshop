# Acceptance - review-pr

## The check

```bash
python scripts/workshop.py verify review-pr
```

It reads `work/review_notes.md` and checks, deterministically:

| Requirement | Why it is checkable |
|---|---|
| All four sections are present and non-empty | A review with a missing section is not a review |
| No template placeholder is left anywhere | An unfilled field is not an answer |
| At least two `### Finding` blocks | Depth over coverage, but not zero |
| Each finding has location, severity, evidence, requested change | These are the fields an author can act on |
| Severity is one of `blocking`, `should-fix`, `nit` | Shared vocabulary beats adjectives |
| The comparison names one thing the captured review found that you missed, one thing you found that it missed, and one comment you would not forward | This is the whole point of step 3 |
| The decision is `approve` or `request changes`, with a condition that would flip it | A review without a decision is a conversation |

## What it does not check

It does not judge whether your findings are correct, whether your severities are
right, or whether your decision is the one the room would make. No automated check
can do that honestly, and a check that pretended to would teach you to write for
the checker instead of for the author.

That judgement happens at the resync, out loud, where disagreement about severity
is the useful part.

## Failing is the normal first state

Right after `start`, the template is still a template, so `verify` fails and names
every unfilled field. That is your fail-before state for an evidence scenario:
the check goes green when the work exists, not when the code changes.

## Passing

`Summary: N/N acceptance checks passed`, exit code 0.

## Restore

```bash
python scripts/workshop.py reset review-pr
```

Your notes are archived under `.workshop-state/attempts/` before the template is
restored, so a reset never costs you the review you wrote.
