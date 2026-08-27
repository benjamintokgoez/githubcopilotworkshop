# Acceptance - incident-service-rate

Run:

```bash
python scripts/workshop.py verify incident-service-rate
```

The unchanged checks require:

- assignments use the accepted provider offer's rate;
- lower eligible rates are consumed before higher rates;
- equal-rate offers remain FIFO;
- assigned hours are conserved; and
- rates remain positive `Decimal` values.

The first run after `start` must fail. Add participant-owned regression evidence
under `work/`; do not weaken the staged acceptance file. At the checkpoint run
`python scripts/workshop.py reset incident-service-rate`.
