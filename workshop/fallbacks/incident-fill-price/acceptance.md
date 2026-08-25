# Acceptance - incident-fill-price

## The check

After copying both files from `staged_copy/` to a participant-owned directory and
removing only their trailing `.txt` suffixes, run this from the copied directory:

```bash
python -m unittest discover -s . -t . -p "test_*.py"
```

The command needs Python but no project dependencies. If Python is unavailable,
use `captured_acceptance_output.txt` only as labelled fail-before evidence and
follow the read-only Supported route in `README.md`.

## Run it before you change anything

Run the copied check before editing either copied file and keep the output. That
is your fail-before evidence. The supplied captured output can replace this step
only when execution is unavailable; it cannot prove pass-after.

Keep the copied acceptance check unchanged. Add a separate focused regression
check for your own fail-before/pass-after evidence.

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
  evidence.
- It is not sufficient on its own. Acceptance is the floor: the lab also asks for
  a regression test you can defend and a handover the desk can read.

## Passing

The command exits 0 when all copied checks pass. Paste the fail-before and
pass-after output into your evidence note, in that order, with the command above.

Passing is required for Core. A read-only or incomplete Supported result records
the failure or `not run`, the bounded next action, and the uncertainty without
claiming a pass.

## Clean up

This fallback route has no active scenario, so `reset` does not apply. Preserve
your evidence according to the workshop data policy, then remove only the
participant-owned working copy you created. Do not edit or delete the versioned
fallback files.
