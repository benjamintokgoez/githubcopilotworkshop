# Offline fallback - incident-fill-price (Lab 2)

Captured copies of everything the scenario stages, for when the runner, live
product, network, or local execution path is unavailable. No active scenario or
network is required; the read-only route needs no dependencies.

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

## Route A - runner unavailable, Python available

1. Copy the two files in `staged_copy/` to a participant-owned working directory
   outside this repository. Do not edit the fallback copies and do not use the
   scenario `work/` path without an active scenario.
2. Remove only the trailing `.txt` from the copied file names.
3. Run the checks from your copied directory:

   ```bash
   python -m unittest discover -s . -t . -p "test_*.py"
   ```

   Keep that first failing output. It is your fail-before evidence, exactly as it
   would be with `verify`.
4. Work the same
   **Understand/Plan -> Implement/Test -> Review -> Explain** loop from
   `issue.md`, `logs/` and `invariants.md`. Keep the supplied acceptance check
   unchanged and add your regression check separately.
5. Re-run the same command to prove pass-after, or record the honest failure at
   the implementation cut.

`captured_acceptance_output.txt` shows what that first run looks like, so you can
compare your starting state.

## Route B - read-only or no Python

1. Use `captured_acceptance_output.txt` as labelled **captured fail-before**
   evidence.
2. Separate observed, concluded, and assumed statements in `issue.md`.
3. Name the invariant, localise the relevant path in the staged copies, and write
   one bounded next action.
4. Review that next action for scope, invariant, test, contract, non-functional,
   and explanation risk.
5. Write the desk handover and state that pass-after was **not run**.

This is a complete Supported result. The captured failure is not evidence that a
repair passes, and the read-only route must not be reported as Core.

## Route C - pair or helper machine

Keep your own evidence note while a verified partner machine runs the commands.
Take the navigator or reviewer role and make the invariant, scope, review, and
handover decisions yourself. Do not copy credentials or unrelated workspace
content between machines.

## Time cuts

- At 10:23 without fail-before evidence, use the captured output.
- At the implementation cut, stop editing and preserve Review and Explain.
- By 11:20, record the actual status. There is no active scenario
  to reset on this route; clean up only your participant-owned working copy.

## What is deliberately not here

No answer key, no defect map, no annotated source. The diagnosis is the lab.

*Everything in this directory is synthetic: simulated prices, an invented client
reference, and a ticket written for the workshop.*
