# Scenario: incident-service-rate (Lab 2)

This scenario stages an isolated multi-module reproduction of a service
assignment incident. The path crosses domain records, capacity priority,
matching, versioned events, projection, and confirmation persistence.

```bash
python scripts/workshop.py start incident-service-rate
python scripts/workshop.py verify incident-service-rate
python scripts/workshop.py reset incident-service-rate
```

Read `issue.md`, the two log artifacts, and `invariants.md` before opening the
staged source. Work only under `work/`. Keep the failing first run, add a focused
regression check, inspect the complete diff, and write `NOTES.md` with the
operations handover and uncertainty.

The scenario contains no answer map. The engine assignment and the operations
confirmation are separate observable boundaries; establish where they diverge
before choosing a repair.
The complete offline route is in `workshop/fallbacks/incident-service-rate/`.
