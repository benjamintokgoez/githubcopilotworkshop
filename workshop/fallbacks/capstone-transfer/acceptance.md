# Acceptance - capstone-transfer

## Full check

From the directory containing the copied modules:

```bash
python -m unittest discover -s . -t . -p "test_*.py"
```

The starting state intentionally fails at multiple boundaries; save the first
run before changing code.

## Observable contract

| Boundary | Required observation |
|---|---|
| Registry | `fresh-telemetry-deviation` appears through the metaclass registry and catalogue |
| Freshness | Only the requested asset's readings in `[as_of - 15 minutes, as_of]` are selected |
| Time | Naive values fail; future values are excluded; machine timestamps remain aware UTC |
| Samples | Fewer than three fresh readings produce no recommendation |
| Threshold | An absolute deviation equal to the threshold produces a recommendation |
| Arithmetic | Average, target, deviation, and confidence remain `Decimal` internally |
| Machine payload | Decimal values are dot-decimal strings, never binary floats |
| Errors | An unknown policy fails explicitly |

## Focused Supported check

```bash
python -m unittest -v \
  test_recommendation.RegistryContractTest \
  test_recommendation.WindowContractTest \
  test_recommendation.PolicyContractTest
```

Supported still requires a reviewed diff and completed handover. Core adds the
service and machine-payload boundary and a passing full check.

Do not edit or weaken the supplied checks. Add one participant-owned adversarial
check for a material assumption in a separate `test_*.py` file.
