# Acceptance - review-pr

## The check

```bash
python scripts/workshop.py verify review-pr
```

It reads `work/review_notes.md` and checks, deterministically:

| Requirement | Why it is checkable |
|---|---|
| All four verifier-required sections are present and non-empty | The structural core of the review note exists |
| No template placeholder is left anywhere | An unfilled field is not an answer |
| At least two `### Finding` blocks | A minimum number of structured claims exists |
| Each finding has location, severity, evidence, requested change | These are the fields an author can act on |
| Severity is one of `blocking`, `should-fix`, `nit` | Shared vocabulary beats adjectives |
| The comparison names one thing the captured review found that you missed, one thing you found that it missed, and one comment you would not forward | This is the whole point of step 3 |
| The decision is `approve` or `request changes`, with a condition that would flip it | A review without a decision is a conversation |

## What passing does and does not prove

| A passing verifier proves | It does not prove |
|---|---|
| Required headings and minimum text are present | The independent diff account was written before the summary |
| At least two finding blocks contain every required field | Locations are correct or evidence supports the finding |
| Comparison and decision fields are filled | Severity and requested changes are proportionate |
| Template placeholders are gone | Scope was assessed or the uncertainty sentence is honest |

The staged template has a fifth uncertainty section, but the verifier does not
evaluate it. It also cannot evaluate the quality of prose that passes a length
threshold. Core requires a green structural verifier **and** a useful review
against the issue, diff, and contracts. Supported evidence may remain useful with
a red verifier when the exact missing structure is recorded.

Judgement happens at the resync, where disagreement about evidence and severity
is useful. Do not write for the checker instead of for the author.

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
