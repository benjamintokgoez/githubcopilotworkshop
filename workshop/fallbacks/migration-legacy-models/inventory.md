# In-scope inventory - migration-legacy-models

This is the authoritative scope for QXM-4520. It is also what the scenario
manifest stages. Read it from your own checkout; do not copy a file list from
someone else's screen.

| File (after `start`) | Role | In scope |
|---|---|---|
| `work/legacy_models.py` | Reference-data models: instrument reference, quote payload | Yes - migrate |
| `work/legacy_service.py` | The consumer: parses input, serialises for downstream | Yes - migrate |
| `work/test_contract.py` | Contract checks for both of the above | Read, run, do not weaken |
| Everything under `qxm/` | The canonical runtime models | **No** - out of scope |
| Everything under `tests/` | The baseline suite | **No** - out of scope |

## Public surface that consumers depend on

These are the import paths and callables other systems use. Names, arguments and
return types are contract:

```
legacy_models.InstrumentRef
legacy_models.QuotePayload
legacy_service.ContractError
legacy_service.parse_instrument(raw: dict) -> InstrumentRef
legacy_service.parse_quote(raw: dict) -> QuotePayload
legacy_service.instrument_payload(raw: dict) -> dict
legacy_service.instrument_json(raw: dict) -> str
legacy_service.quote_payload(raw: dict) -> dict
legacy_service.quote_json(raw: dict) -> str
```

## Suggested batching

Not a plan - a starting point for the plan you are going to write and edit:

1. Capture one valid instrument and one valid quote through their public parser,
   payload, and JSON paths. Capture one invalid case per model family through
   the public error boundary. This covers every public adapter without repeating
   equivalent invalid inputs.
2. Migrate the models.
3. Migrate the consumer.
4. Re-run the capture and diff it against step 1.

Each batch ends with a verification you can run in under five minutes. If yours
does not, split it further. At the lab cut time, keep the last verified batch and
handover the remainder rather than combining batches to chase completion.
