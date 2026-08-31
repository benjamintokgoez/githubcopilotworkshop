# Scenario: capstone-transfer (Lab 6)

An individual cross-module task over a metaclass-registered telemetry policy.
The participant must map and repair freshness selection, threshold semantics,
service construction, and machine serialization without changing unrelated
boundaries.

```bash
python scripts/workshop.py start capstone-transfer
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

## Inventory

| Path | What it is |
|---|---|
| `issue.md` | Synthetic operations request and behavioural constraints |
| `acceptance.md` | Observable registry, freshness, policy, and payload contract |
| `work/policy_models.py` | Typed telemetry and recommendation records |
| `work/policy_base.py` | Policy metaclass registry and abstraction |
| `work/telemetry_window.py` | Shared aware-UTC freshness selector |
| `work/deviation_policy.py` | Concrete registered policy |
| `work/policy_catalog.py` | Read-only registry projection |
| `work/recommendation_service.py` | Policy construction and machine payload |
| `work/test_recommendation.py` | Supplied observable checks |
| `work/NOTES.md` | Participant handover |

## Lanes

- **Supported:** registry, time-window, sample-count, and threshold behaviours,
  with a reviewed diff and handover. The service boundary may remain incomplete.
- **Core:** the complete observable contract, participant-owned adversarial
  check, reviewed diff, handover, and green verifier.
- **Extension:** after Core, add one bounded check for a risk not represented in
  the supplied suite.

Offline copies live under `workshop/fallbacks/capstone-transfer/`.
