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
| The contradiction test is labelled and recorded | `- What I asked for that contradicts a rule:` and `- Observed behaviour:` |
| The limits of durable context are named | `## 7. What durable context cannot enforce` |

The field label `Observed behaviour` is fixed by the staged template. For the
local-analysis mode, begin its value with `Local expected:` or `Local policy
trace:`. Use `Observed live:` only when a compatible Copilot surface actually
ran.

## Evidence routes

- **Local analysis:** baseline score, edited draft, labelled local candidate
  before/after, deletion-case difference, and expected contradiction result.
- **Preflight-green live:** same prompt, model, surface, and repository state
  without and with the scenario draft explicitly attached, followed by one
  attached deletion run.

The live route proves only that supplied context influenced that comparison. It
does not prove automatic discovery, path matching, or instruction precedence.

## What it does not check

Your rewritten `work/instructions_draft.md` is not parsed. Rules are judged by
their observable effect, which lives in your before/after note - and by the room
at the resync. A checker that graded instruction files by counting them would
reward exactly the behaviour this elective argues against.

`verify` also cannot call a model or identify the origin of pasted output.
Preserve route and evidence labels in the note.

## Scope

`verify` only ever reads files under this scenario.
`.github/copilot-instructions.md` and `.github/instructions/` are out of scope
for the elective and are never touched by `start` or `reset`.

## Restore

```bash
python scripts/workshop.py reset elective-customization
```
