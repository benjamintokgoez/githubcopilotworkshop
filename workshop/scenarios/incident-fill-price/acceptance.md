# Acceptance - incident-fill-price

## The check

```bash
python scripts/workshop.py verify incident-fill-price
```

which runs exactly this, from the repository root:

```bash
python -m unittest discover \
  -s workshop/scenarios/incident-fill-price/work \
  -t workshop/scenarios/incident-fill-price/work \
  -p "test_*.py"
```

`pytest workshop/scenarios/incident-fill-price/work -q` runs the same checks if
you prefer pytest. Neither command needs project dependencies.

## Run it before you change anything

The scenario stages the failing state; your checkout was green before `start`.
Run the check now, while the code is untouched, and keep the output. That is your
fail-before evidence, and no evidence you collect later can replace it.

Treat the supplied acceptance file as read-only. Add your own focused regression
check in a separate participant-added file so that its fail-before/pass-after
evidence is independent of this contract.

## What the check asserts

| Check | Invariant |
|---|---|
| A market buy of 120 fills 100 from A1 and 20 from A2, both at `101.20` | INV-MATCH-2 |
| The following market buy of 200 averages `101.455` | INV-MATCH-2 |
| No fill carries a null price, including when no indicative price was supplied | INV-MATCH-2 |
| The 101.50 level is untouched by the first order, and remaining quantities add up | INV-MATCH-1, INV-MATCH-3 |

## What the check is not

- It is not a file list. It never names the function you have to change.
- It is not participant implementation space. Weakening an assertion, deleting a
  case, or making the expected value follow the observed one invalidates the
  evidence, and `reset` will archive the difference.
- It is not sufficient on its own. Acceptance is the floor: the lab also asks for
  a regression test you can defend and a handover the desk can read.

## Passing

`verify` prints a `Summary: 1/1 acceptance checks passed` line and exits 0. Paste
the fail-before and the pass-after output into your evidence note, in that order,
with the command above.

Passing is required for Core. A Supported result may remain red, but must record
the actual result, the bounded next action, and the uncertainty without implying
that acceptance passed.

## Restore

```bash
python scripts/workshop.py reset incident-fill-price
```

Your edited files are archived under `.workshop-state/attempts/` first, then the
pre-start bytes are restored exactly.
