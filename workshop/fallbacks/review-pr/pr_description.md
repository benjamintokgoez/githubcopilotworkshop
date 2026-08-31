# PR #212 - Add organisation SLA snapshots

## Summary

Adds the requested one-day and seven-day SLA endpoint, a typed core snapshot,
exact machine serialization, and API coverage. The result is cached per horizon
to avoid rebuilding analytics state for repeated reads.

## Validation claimed

- API tests pass for both horizons and invalid horizon values.
- Aware-UTC output and non-negative values are asserted.
- Application-factory isolation is covered.
- No authentication or organisation-isolation behaviour changed.

## Risk

Low. The endpoint is read-only, uses the existing analytics permission, and does
not add storage or dashboard behavior.

---

*This description is a claim from a synthetic unattended run, not evidence.*
