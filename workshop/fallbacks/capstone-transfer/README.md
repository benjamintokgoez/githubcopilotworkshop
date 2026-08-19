# Offline fallback - capstone-transfer (Lab 6)

The capstone runs on the standard library alone, so this directory is a complete
copy of it. No network, no dependencies, no active scenario.

## Inventory

| File | What it is |
|---|---|
| `issue.md` | The request from operations, including their notes |
| `data/records_2026-08-19.json` | Sample records, timestamped in UTC |
| `acceptance.md` | The expected values and what the check asserts |
| `staged_copy/daily_export.py.txt` | Byte-identical copy of the staged skeleton |
| `staged_copy/test_daily_export.py.txt` | Byte-identical copy of the staged acceptance checks |
| `staged_copy/NOTES.md.txt` | Byte-identical copy of the handover template |
| `captured_acceptance_output.txt` | A captured run of the acceptance checks in the starting state |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working without the tooling

1. Copy `staged_copy/` into a directory that sits **next to** a `data/` directory
   containing `records_2026-08-19.json` - the checks look for the sample input one
   level up, exactly as in the scenario layout:

   ```
   <your directory>/
     data/records_2026-08-19.json
     work/daily_export.py
     work/test_daily_export.py
   ```

2. Run the checks from your `work/` directory:

   ```bash
   python -m unittest discover -s . -t . -p "test_*.py"
   ```

3. Implement the four functions until the checks pass, and write the handover.

## Reminder

The brief contains at least one confident claim that does not survive checking.
Nothing in this directory tells you which one, and the expected values in
`acceptance.md` are the specification when the ticket and the checks disagree.

*Synthetic material: generated records, invented amounts, no real counterparty.*
