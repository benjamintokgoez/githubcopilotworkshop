# In-scope inventory - migration-legacy-models

| File after `start` | Role | In scope |
|---|---|---|
| `work/legacy_models.py` | Equipment reference and service-rate models | Yes - migrate |
| `work/legacy_service.py` | Published parser and serialisation boundary | Yes - migrate |
| `work/test_contract.py` | Existing contract checks | Read and run; do not weaken |
| Everything under `mittelwerk/` | Canonical runtime | No |
| Everything under `tests/` | Baseline suite | No |

## Public surface

```text
legacy_models.EquipmentRef
legacy_models.ServiceRatePayload
legacy_service.ContractError
legacy_service.parse_equipment(raw)
legacy_service.parse_service_rate(raw)
legacy_service.equipment_payload(raw)
legacy_service.equipment_json(raw)
legacy_service.service_rate_payload(raw)
legacy_service.service_rate_json(raw)
```

Capture one valid and one invalid example for each model family through these
public functions. Migrate in independently verifiable batches, then compare the
same outputs and errors against the baseline.
