# Acceptance - migration-legacy-models

## The check

```bash
python scripts/workshop.py verify migration-legacy-models
```

which runs, from the repository root:

```bash
python -m unittest discover \
  -s workshop/scenarios/migration-legacy-models/work \
  -t workshop/scenarios/migration-legacy-models/work \
  -p "test_*.py"
```

`pytest workshop/scenarios/migration-legacy-models/work -q` runs the same checks.
Both need the project's validation library installed
(`python -m pip install -r requirements.txt`); the scenario refuses to start
without it rather than failing confusingly later.

## Run it immediately after `start`

Straight after `start`, most of these checks already pass and the migration
checks fail. That is the point: the contract checks are your **baseline**, and
the migration checks are your **target**. A migration that turns a passing
contract check red has broken something a consumer depends on, and the run tells
you which one.

Capture this first run. It is the only honest "before".

## What the check asserts

| Group | Asserts |
|---|---|
| Serialised shape | Alias names, key order, types, the optional field, the dot decimal separator, and the timestamp representation consumers parse |
| Accepted input | Inputs that work today still work, including the ones the ticket forgot to mention |
| Rejected input | Everything rejected today is still rejected, through the same public exception, with a non-empty message |
| Migration completed | The in-scope modules no longer reach the surface through the 1.x compatibility shim, at import level and at runtime, and the public names still exist |

## What passing does and does not prove

| A passing verifier proves | It does not prove |
|---|---|
| The supplied contract checks are green | You captured public output before editing |
| The compatibility shim is gone from the staged surface | You edited and challenged the generated plan |
| Public names covered by the checks still exist | The intended context source was actually loaded |
| Covered accepted and rejected inputs still behave as asserted | You read each batch diff or made a sound ambiguity decision |

This is not a migration recipe. It states what must hold, never how to achieve
it. Save the baseline, final plan, context-loading route, per-batch command and
observed result, before/after comparison, and handover in `MIGRATION_NOTES.md`.

A red final verifier can accompany a complete Supported outcome when one batch is
well evidenced and the remaining work is handed over honestly. Core requires the
green verifier **and** the manual evidence. Never present structural completion
as proof of the process that produced it.

## Passing

`Summary: 1/1 acceptance checks passed`, exit code 0. Attach the before and after
runs to your handover, plus your own serialised baseline diff - the check proves
the covered contract held; your baseline proves you observed it before editing.

## Restore

```bash
python scripts/workshop.py reset migration-legacy-models
```
