# Scenario: incident-service-rate (Lab 2)

This scenario stages an isolated, dependency-free reproduction of a service
dispatch incident.

```bash
python scripts/workshop.py start incident-service-rate
python scripts/workshop.py verify incident-service-rate
python scripts/workshop.py reset incident-service-rate
```

Read `issue.md`, the two log artifacts, and `invariants.md` before opening the
staged source. Work only under `work/`. Keep the failing first run, add a focused
regression check, inspect the complete diff, and write `NOTES.md` with the
operations handover and uncertainty.

The scenario contains no answer map. The accepted rate is observable in the
provider offers and the checks, but the repair location is yours to establish.
The complete offline route is in `workshop/fallbacks/incident-service-rate/`.
