# Offline fallback - capstone-transfer (Lab 6)

This is the complete cross-module capstone without a network, active scenario,
third-party dependency, or live Copilot feature.

## Inventory

| File | What it is |
|---|---|
| `issue.md` | Synthetic operations request and behavioural constraints |
| `acceptance.md` | Observable registry, freshness, policy, and payload contract |
| `staged_copy/*.py.txt` | Byte-identical inert copies of the staged policy modules and checks |
| `staged_copy/NOTES.md.txt` | Byte-identical handover template |
| `captured_acceptance_output.txt` | Captured starting-state failure |

Copy every staged file to a participant-owned `work/` directory and remove only
the final `.txt` suffix. Then run:

```bash
python -m unittest discover -s . -t . -p "test_*.py"
```

Choose Builder or Supervising architect. Both routes map the full staged path,
add one participant-owned adversarial check, inspect the complete diff, and
record the actual result in `NOTES.md`.

- **Supported:** registry, freshness, sample-count, and threshold behaviour.
- **Core:** the complete service and machine-payload contract.
- **Extension:** one additional bounded risk after Core and handover.

At 16:17, stop adding behaviour and finish review and handover even if the full
check remains red.
