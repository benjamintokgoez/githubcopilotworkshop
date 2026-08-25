# Scenario: incident-fill-price (Lab 2)

A desk ticket about an average fill price that was never on the book, plus the
logs and invariants you need to decide what actually happened.

```bash
python scripts/workshop.py status
python scripts/workshop.py start incident-fill-price
python scripts/workshop.py verify incident-fill-price   # run this before changing anything
python scripts/workshop.py reset incident-fill-price    # run at the room checkpoint
```

Start only when `status` reports no active scenario. The first verifier run must
fail in the staged scenario; keep that output before editing.

## Inventory

| Path | What it is |
|---|---|
| `issue.md` | The ticket, in the reporter's words, including their theory |
| `logs/qxm-engine-2026-08-19.log` | Engine log excerpt, timestamps in UTC |
| `logs/execution_report_ORD-2026-0819-0442.txt` | The confirmation the client received |
| `invariants.md` | The rules the desk believes were broken, and the reference book state |
| `acceptance.md` | The read-only acceptance contract, what it asserts, and what it does not |
| `payloads/` | Pristine sources of the staged files. Do not edit these. |
| `work/` | Created by `start`: your working copy of the reproduction and its checks |

## What `start` stages

- `work/fill_engine.py` - a bounded reproduction of the fill-pricing path
- `work/test_fill_price.py` - the acceptance checks

Nothing under `qxm/` is touched. The baseline test suite stays green while this
scenario is active, which is why the acceptance check - not `pytest tests/` - is
the thing that must fail before your change.

Treat `work/test_fill_price.py` as read-only. Add a separate participant-owned
regression check under `work/`; `reset` archives participant-added files with the
attempt.

## Working notes

- Read `issue.md` before any source file, and separate observed from concluded.
- Diff your work against the pristine starting point at any time:
  `git diff --no-index workshop/scenarios/incident-fill-price/payloads/fill_engine.py.txt
  workshop/scenarios/incident-fill-price/work/fill_engine.py`
- At 10:23 without a reproduction, take the first lab hint and use the
  Supported route. At the implementation cut, keep the incomplete diff and run
  `python scripts/workshop.py resync incident-fill-price --blocked-at implement-test`.
- Stop implementation at 10:46. Verify once and reset by 11:20 whether acceptance passes or
  fails. Reset is non-destructive to the attempt: it archives before restoring.
- There is no answer key in this repository, and no file names the defect.

## Offline

`workshop/fallbacks/incident-fill-price/` holds the same ticket, logs, staged-file
copies, and captured failing run. It supports an executable copy when Python is
available and an honest read-only Supported result when it is not.
