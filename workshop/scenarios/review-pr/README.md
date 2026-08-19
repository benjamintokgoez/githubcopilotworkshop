# Scenario: review-pr (Lab 4)

A pre-created pull request, reviewed offline. Nothing in this scenario needs a
network, a cloud agent, or code review to be enabled for your account.

```bash
python scripts/workshop.py start review-pr
python scripts/workshop.py verify review-pr
python scripts/workshop.py reset review-pr
```

## Inventory

| Path | What it is |
|---|---|
| `brief.md` | How to work the review, and in which order to read the package |
| `acceptance.md` | What `verify` checks in your review note, and what it deliberately does not |
| `payloads/` | Pristine source of the staged template |
| `work/review_notes.md` | Created by `start`: your review note |
| `../../fallbacks/review-pr/` | The pull request package itself: issue, description, diff, transcript, review thread, captured automated review |

The package lives under `workshop/fallbacks/review-pr/` on purpose. It is captured
rather than live, it is identical for everyone, and it is exactly what you fall
back to when the tooling is unavailable - so there is one copy, not two that can
drift apart.

## What `start` stages

- `work/review_notes.md` - the review-note template

No source file is modified. This scenario stages an evidence task, not a defect:
the thing that has to become true is your review, not the code.

## Simulation notice

The pull request, its author, the reviewers in the thread, the session transcript
and the automated review are all synthetic, written for this workshop. No real
person, repository, or product output is reproduced.
