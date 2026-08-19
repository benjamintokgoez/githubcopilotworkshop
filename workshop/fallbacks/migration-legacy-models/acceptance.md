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

## What the check is not

- It is not a migration recipe. It says what must hold, never how to get there.
- It does not grade your plan, your batching, or your handover - the lab does,
  and those are where most of the marks live.
- It cannot see a decision you made silently. The ambiguity in the ticket is real;
  resolving it explicitly is your job, not the checker's.

## Passing

`Summary: 1/1 acceptance checks passed`, exit code 0. Attach the before and after
runs to your handover, plus your own serialised baseline diff - the check proves
the contract held, your baseline proves you knew what it was.

## Restore

```bash
python scripts/workshop.py reset migration-legacy-models
```
