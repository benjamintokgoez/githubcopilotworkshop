# Workshop scenarios

Every lab that changes something works from a scenario. A scenario is a folder of
realistic artifacts - a ticket, log excerpts, a legacy module set, a pre-created
pull request - plus a machine-readable `manifest.json` that tells the runner what
to stage, how to check acceptance, and how to restore the previous state exactly.

```bash
python scripts/workshop.py list
python scripts/workshop.py start <scenario-id>
python scripts/workshop.py status
python scripts/workshop.py resync <scenario-id> --blocked-at <phase>
python scripts/workshop.py verify <scenario-id>
python scripts/workshop.py reset <scenario-id>
python scripts/workshop.py fallback <scenario-id>
```

## The healthy-baseline contract

- A clean checkout is green. Nothing here is broken at rest.
- `start` is the only command that stages a failing or questionable state, and it
  prints exactly what it changed.
- `reset` restores the exact pre-start bytes, after archiving anything you wrote.

`resync` changes nothing. It prints a phase-specific route that lets a participant
continue to Review and Explain, preserve a failing result honestly, and reset in
time for the next lab without exposing a solution.

## Layout of a scenario

| Path | Meaning |
|---|---|
| `manifest.json` | Declarative contract: staged payloads, targets, acceptance checks, fallback |
| `issue.md` / `brief.md` | The human task, written the way a colleague would write it |
| `acceptance.md` | What the acceptance check actually checks, and what it does not |
| `logs/`, `fixtures/`, `data/` | Supporting evidence you read but do not edit |
| `payloads/*.txt` | Pristine sources of the staged files; never imported directly |
| `work/` | Created by `start`. This is your working copy - edit here. |

`payloads/` files carry a `.txt` suffix on purpose: they are inert data until the
runner stages them, so linting, type checking, and test collection never see a
deliberately incomplete starter file.

## Runtime state

`start` writes `.workshop-state/` in the repository root: the active scenario, the
pre-start hashes and modes of every target, byte backups, and - on `reset` - a
timestamped archive of your own attempt. The directory is git-ignored and can be
deleted once no scenario is active.

Two different things live in there, and they deserve different care:

- **State and backups** are written by the tooling. It records paths, hashes,
  modes and timestamps, and copies the files it is about to overwrite. It never
  collects credentials or environment variables of its own.
- **Attempt archives** are copies of *your* files, made by `reset` so a reset
  never costs you your work. They contain whatever you wrote, so nobody can
  promise they are free of sensitive content.

So: do not put secrets, personal data, or customer material into scenario files
in the first place, and delete `.workshop-state/attempts/` when you are done with
it, following the workshop's data-handling rules
([workshop/ops/DATA_HANDLING.md](../ops/DATA_HANDLING.md)). Deleting the whole
`.workshop-state/` directory while no scenario is active is always safe.

One scenario is active at a time. That is deliberate: two half-staged scenarios are
indistinguishable from a broken checkout.

## Offline

Captured, non-live copies of every scenario live under `workshop/fallbacks/<id>/`
and need no network, no cloud agent, and no active scenario:

```bash
python scripts/workshop.py fallback <scenario-id>
```

## Simulation notice

Every symbol, price, order, ticket, transcript and review in these scenarios is
synthetic and generated for teaching. No customer data, no production system, and
no real market data is represented here.
