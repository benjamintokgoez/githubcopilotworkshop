# Scenario: incident-fill-price (Lab 2)

A desk ticket about an average fill price that was never on the book, plus the
logs and invariants you need to decide what actually happened.

```bash
python scripts/workshop.py start incident-fill-price
python scripts/workshop.py verify incident-fill-price   # run this before changing anything
python scripts/workshop.py reset incident-fill-price
```

## Inventory

| Path | What it is |
|---|---|
| `issue.md` | The ticket, in the reporter's words, including their theory |
| `logs/qxm-engine-2026-08-19.log` | Engine log excerpt, timestamps in UTC |
| `logs/execution_report_ORD-2026-0819-0442.txt` | The confirmation the client received |
| `invariants.md` | The rules the desk believes were broken, and the reference book state |
| `acceptance.md` | The acceptance check, what it asserts, and what it does not |
| `payloads/` | Pristine sources of the staged files. Do not edit these. |
| `work/` | Created by `start`: your working copy of the reproduction and its checks |

## What `start` stages

- `work/fill_engine.py` - a bounded reproduction of the fill-pricing path
- `work/test_fill_price.py` - the acceptance checks

Nothing under `qxm/` is touched. The baseline test suite stays green while this
scenario is active, which is why the acceptance check - not `pytest tests/` - is
the thing that must fail before your change.

## Working notes

- Read `issue.md` before any source file, and separate observed from concluded.
- Diff your work against the pristine starting point at any time:
  `git diff --no-index workshop/scenarios/incident-fill-price/payloads/fill_engine.py.txt
  workshop/scenarios/incident-fill-price/work/fill_engine.py`
- There is no answer key in this repository, and no file names the defect.

## Offline

`workshop/fallbacks/incident-fill-price/` holds the same ticket, the same logs, a
copy of both staged files, and a captured failing run, for when the tooling is
unavailable.
