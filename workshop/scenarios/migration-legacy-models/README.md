# Scenario: migration-legacy-models (Lab 3)

A bounded legacy model surface that still runs through a deprecated compatibility
shim, its consumer, and the contract checks that define "behaviour preserving".

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
- `work/legacy_service.py` - the consumer that serialises them
- `work/test_contract.py` - the contract checks

`qxm/` is untouched. The canonical runtime models are deliberately **not** part of
this exercise: a migration you can reset in one command is a better place to
practise supervision than the live core.

## Prerequisite

This scenario needs the project's validation library importable, so `start`
checks for it first:

```bash
python -m pip install -r requirements.txt
```

## Working notes

- Capture the baseline **before** the first edit. `inventory.md` lists exactly
  which callables to capture.
- Diff against the pristine starting point at any time:
  `git diff --no-index workshop/scenarios/migration-legacy-models/payloads/legacy_models.py.txt
  workshop/scenarios/migration-legacy-models/work/legacy_models.py`
- The request is underspecified in one place. Finding it is part of the planning
  work, and nothing in this folder tells you where it is.

## Offline

`workshop/fallbacks/migration-legacy-models/` carries the ticket, the inventory,
copies of all three staged files, and a captured run of the acceptance check.
