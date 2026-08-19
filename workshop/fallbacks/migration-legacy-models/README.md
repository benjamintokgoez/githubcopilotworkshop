# Offline fallback - migration-legacy-models (Lab 3)

Captured copies of the Lab 3 material. No network and no active scenario needed.
The migration itself needs the project's validation library installed
(`python -m pip install -r requirements.txt`); everything else here is readable
without it.

## Inventory

| File | What it is |
|---|---|
| `issue.md` | The migration request from the tech lead |
| `inventory.md` | The authoritative scope and the public surface consumers depend on |
| `acceptance.md` | The contract checks and what they mean |
| `staged_copy/legacy_models.py.txt` | Byte-identical copy of the staged models |
| `staged_copy/legacy_service.py.txt` | Byte-identical copy of the staged consumer |
| `staged_copy/test_contract.py.txt` | Byte-identical copy of the staged contract checks |
| `captured_acceptance_output.txt` | A captured run of the contract checks in the starting state |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working without the tooling

1. Copy `staged_copy/` into a directory you can edit.
2. Capture your baseline **before** touching anything: serialise one valid and one
   invalid input through every callable listed in `inventory.md` and save the
   output.
3. Run the checks from that directory:

   ```bash
   python -m unittest discover -s . -t . -p "test_*.py"
   ```

   In the starting state most checks pass and the migration checks fail. That
   split is the point: the passing ones are your contract, the failing ones are
   your target.
4. Plan, batch, execute, and verify between batches. Re-run the command after
   each batch, and diff your serialised output against the baseline from step 2.

## What is deliberately not here

No migration recipe, no idiom mapping table, no worked example of the new API.
Producing and editing that plan is the lab.

*Synthetic material written for the workshop.*
