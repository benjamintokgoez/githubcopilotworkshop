# Scenario: elective-customization (Lab 5C)

```bash
python scripts/workshop.py start elective-customization
python scripts/workshop.py verify elective-customization
python scripts/workshop.py reset elective-customization
```

| Path | What it is |
|---|---|
| `brief.md` | The task, and why the draft is scenario-local |
| `fixtures/review_criteria.md` | Mechanical criteria for judging durable context, and the four failure modes |
| `acceptance.md` | What `verify` checks |
| `work/instructions_draft.md` | Created by `start`: a badly written draft, for you to rewrite |
| `work/customization_notes.md` | Created by `start`: your before/after evidence |

The staged draft is a practice file. It is not read by any tool, and this
scenario never touches `.github/copilot-instructions.md` - the repository's real
durable context belongs to everyone working in it today.

Offline-friendly and self-contained: an editor and this repository are the only
requirements.
