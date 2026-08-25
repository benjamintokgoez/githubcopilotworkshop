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
2. Create `MIGRATION_NOTES.md`. Before touching code, capture one valid instrument
   and quote through their public parser, payload, and JSON paths, plus one
   invalid case per model family through the public error boundary.
3. Run the checks from that directory:

   ```bash
   python -m unittest discover -s . -t . -p "test_*.py"
   ```

   In the starting state most checks pass and the migration checks fail. That
   split is the point: the passing ones are your contract, the failing ones are
   your target.
4. Save and edit the plan. Record at least two changes you made to its draft.
   Explicitly attach or reference `MIGRATION_NOTES.md` when using it as agent
   context; its location alone does not make it automatic context.
5. Batch, execute, and verify. Re-run the command after each batch and diff the
   public output against step 2. Start no new batch after 13:16, freeze edits at
   13:26, and preserve an honest handover before reset by 13:35.

The supplied `captured_acceptance_output.txt` is valid fail-before evidence for
the fallback route, but label it as captured rather than personally executed.
Completion of the supplied checks and useful supervision evidence are separate:
Core needs both; Supported may finish with one verified batch and a red final
check.

## What is deliberately not here

No migration recipe, no idiom mapping table, no worked example of the new API.
Producing and editing that plan is the lab.

*Synthetic material written for the workshop.*
