# In-scope inventory - migration-legacy-models

| File after `start` | Role | In scope |
|---|---|---|
| `work/legacy_models.py` | Equipment reference and service-rate models | Yes - migrate |
| `work/legacy_service.py` | Published parser and serialisation boundary | Yes - migrate deprecated calls |
| `work/legacy_api.py` | REST document and machine-JSON adapter | Yes - preserve |
| `work/legacy_mcp.py` | MCP text and structured-result adapter | Yes - preserve |
| `work/legacy_batch.py` | Deterministic batch publication adapter | Yes - preserve |
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
legacy_api.equipment_document(raw, request_id=..., generated_at=...)
legacy_api.service_rate_document(raw, request_id=..., generated_at=...)
legacy_api.service_rate_http_json(raw, request_id=..., generated_at=...)
legacy_mcp.equipment_tool_result(raw)
legacy_mcp.service_rate_tool_result(raw)
legacy_batch.publication_record(equipment, rate)
legacy_batch.publication_json_lines(publications)
```

Capture the model boundary first, then one REST, MCP, and batch representation.
Migrate in independently verifiable dependency order and compare the same
outputs, runtime types, errors, and nested shapes against the baseline.
