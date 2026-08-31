# Scenario: migration-legacy-models (Lab 3)

An equipment and service-rate model surface that still runs through a deprecated
compatibility shim, plus REST, MCP, and batch consumers whose contracts define
"behaviour preserving".

```bash
python scripts/workshop.py start migration-legacy-models
python scripts/workshop.py verify migration-legacy-models   # capture this first run
python scripts/workshop.py reset migration-legacy-models
```

## Inventory

| Path | What it is |
|---|---|
| `issue.md` | The migration request, written by a tech lead in fifteen minutes |
| `inventory.md` | The authoritative scope and the public surface consumers depend on |
| `acceptance.md` | What the acceptance check asserts, and what it cannot see |
| `payloads/` | Pristine sources of the staged files. Do not edit these. |
| `work/` | Created by `start`: the in-scope modules and their contract checks |

## What `start` stages

- `work/legacy_models.py` - the models, on the 1.x idioms
- `work/legacy_service.py` - the shared parser and serializer
- `work/legacy_api.py` - REST documents and machine JSON
- `work/legacy_mcp.py` - text and structured MCP results
- `work/legacy_batch.py` - deterministic JSON-lines publication
- `work/test_contract.py` - the contract checks

`mittelwerk/` is untouched. The canonical runtime models are deliberately **not** part of
this exercise: a migration you can reset in one command is a better place to
practise supervision than the live core.

## Prerequisite

This scenario needs the project's validation library importable, so `start`
checks for it first:

```bash
python -m pip install -r requirements.txt
```

## Working notes

- Create `work/MIGRATION_NOTES.md`. Capture the initial verifier run, one valid
  equipment reference and service-rate record through their public
  parser/payload/JSON paths, one REST/MCP/batch representation, and one invalid
  case per model family **before** the first edit.
- Save the edited plan, how task context was loaded, each batch's diff/check
  result, the contract comparison, and handover in that note. An arbitrary note
  is not automatic agent context; explicitly attach, reference, or hand it off.
- Diff against the pristine starting point at any time:
  `git diff --no-index workshop/scenarios/migration-legacy-models/payloads/legacy_models.py.txt
  workshop/scenarios/migration-legacy-models/work/legacy_models.py`
- The request is underspecified in one place. Finding it is part of the planning
  work, and nothing in this folder tells you where it is.
- Lab cuts are deliberate: start no new batch after 13:16, freeze edits at
  13:26, and reset by 13:35. A verified partial migration is preferable to an
  unread complete diff.

## Offline

`workshop/fallbacks/migration-legacy-models/` carries the ticket, the inventory,
copies of all staged files, and a captured run of the acceptance check.
Mark captured results as captured rather than personally executed.
