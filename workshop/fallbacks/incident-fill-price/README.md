# Offline fallback - incident-fill-price (Lab 2)

Captured copies of everything the scenario stages, for when the tooling is
unavailable, the checkout is in an odd state, or you simply want to read the
ticket on a train. No network, no active scenario, and no dependencies required.

## Inventory

| File | What it is |
|---|---|
| `issue.md` | The desk ticket, including the reporter's theory |
| `logs/qxm-engine-2026-08-19.log` | Engine log excerpt, timestamps in UTC |
| `logs/execution_report_ORD-2026-0819-0442.txt` | The confirmation the client received |
| `invariants.md` | The invariants the desk believes were broken, and the reference book state |
| `acceptance.md` | The acceptance contract |
| `staged_copy/fill_engine.py.txt` | Byte-identical copy of the staged reproduction |
| `staged_copy/test_fill_price.py.txt` | Byte-identical copy of the staged acceptance checks |
| `captured_acceptance_output.txt` | A captured run of the acceptance check in its starting state |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working without the tooling

1. Copy `staged_copy/` somewhere you can edit, for example a scratch directory
   outside the repository or `workshop/scenarios/incident-fill-price/work/`.
2. Run the checks yourself, from that directory:

   ```bash
   python -m unittest discover -s . -t . -p "test_*.py"
   ```

   Keep that first failing output. It is your fail-before evidence, exactly as it
   would be with `verify`.
3. Work the incident from `issue.md`, `logs/` and `invariants.md`.
4. Re-run the same command to prove pass-after.

`captured_acceptance_output.txt` shows what that first run looks like, so you can
compare even if you cannot run Python at all.

## What is deliberately not here

No answer key, no defect map, no annotated source. The diagnosis is the lab.

*Everything in this directory is synthetic: simulated prices, an invented client
reference, and a ticket written for the workshop.*
