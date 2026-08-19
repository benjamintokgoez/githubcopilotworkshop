# Acceptance - elective-customization

```bash
python scripts/workshop.py verify elective-customization
```

reads `work/customization_notes.md` and checks that:

| Requirement | Field or section |
|---|---|
| The measured task is named precisely | `## 1. The task I measured with` |
| A before and an after both exist for the same task | `## 2. Before`, `## 3. After` |
| The difference is concrete, not "it felt better" | `- Observable difference:` |
| At least three rules exist, each with a check and a home | `### Rule` blocks |
| Something was deleted or rewritten, with the reason | `- Rule I deleted or rewrote:` and `- Why its effect was not observable:` |
| The contradiction test was run and recorded as observed | `- What I asked for that contradicts a rule:` and `- Observed behaviour:` |
| The limits of durable context are named | `## 7. What durable context cannot enforce` |

## What it does not check

Your rewritten `work/instructions_draft.md` is not parsed. Rules are judged by
their observable effect, which lives in your before/after note - and by the room
at the resync. A checker that graded instruction files by counting them would
reward exactly the behaviour this elective argues against.

## Scope

`verify` only ever reads files under this scenario. `.github/copilot-instructions.md`
is out of scope for the elective and is never touched by `start` or `reset`.

## Restore

```bash
python scripts/workshop.py reset elective-customization
```
