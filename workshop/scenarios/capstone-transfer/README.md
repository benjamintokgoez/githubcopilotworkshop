# Scenario: capstone-transfer (Lab 6)

An individual, domain-light task: dates, windows and formatting. No order book,
no options maths, no risk model. The difficulty is staying disciplined when the
task looks small.

```bash
python scripts/workshop.py start capstone-transfer
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

| Path | What it is |
|---|---|
| `issue.md` | The request from operations, including their notes |
| `data/records_2026-08-19.json` | Sample records, timestamped in UTC |
| `acceptance.md` | The expected values and what the check asserts |
| `work/daily_export.py` | Created by `start`: the skeleton you implement |
| `work/test_daily_export.py` | Created by `start`: the acceptance checks |
| `work/NOTES.md` | Created by `start`: your handover |

The brief contains at least one confident claim that does not survive checking.
Nothing in this repository tells you which one, and the hints deliberately do not
either.

Everything runs on the standard library. Offline copies live under
`workshop/fallbacks/capstone-transfer/`.
