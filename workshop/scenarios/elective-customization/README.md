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

The staged draft is a practice file. It is not at a recognised Copilot discovery
path, and this scenario never touches `.github/copilot-instructions.md` or
`.github/instructions/`.

- **Local mode:** edit and score the draft, then produce a labelled local
  before/after and deletion-case comparison.
- **Live mode:** only with a preflight-Green Copilot surface, explicitly attach
  the draft to one stable review prompt and compare it with an unattached
  baseline. This tests the content, not repository discovery or `applyTo`
  matching.

Both modes require an edited artifact and evidence, and either can support the
selected achievement lane. Reading the draft is not a complete run.
