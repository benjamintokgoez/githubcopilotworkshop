# Optional first win: a service request becomes an assignment

**Timebox: 2–3 minutes. Optional before Lab 2, not a new lab or a prerequisite.**
Use this if the equipment/service vocabulary is unfamiliar. Supported, Core,
Extension, and Solo participants can all use either route below. No Copilot,
model access, server, network connection, or real service integration is needed.
Every identifier and quantity is synthetic.

## Choose one route

Run commands from the repository root with the workshop environment activated.

| Route | Exact action | What happens |
|---|---|---|
| No execution | Read [the captured journey](fixtures/simulator_first_win.txt) | Nothing runs; suitable for a printed or offline pack |
| Captured CLI | `python scripts/workshop_demo.py` | Prints that same file; Python standard library only, no domain imports |
| Local execution | `python scripts/workshop_demo.py --run` | Uses the real existing `DispatchEngine`, `WorkOrder`, `EventBus`, and `Workload` in a fresh in-memory session |

With an unactivated macOS/Linux checkout, substitute `.venv/bin/python` for
`python`. Local execution needs the repository's existing installed runtime
dependencies from preflight; it does **not** use an HTTP client or require an
additional package. If preflight is unavailable, use the capture rather than
installing or troubleshooting during this timebox. `--help` lists the one flag.

The CLI writes a mode label to stderr: `Mode: captured; no domain code executed.`
or `Mode: executed locally; event bus stopped; no persistent state.` The journey
on stdout is identical in both modes. An execution error fails visibly; it does
not silently substitute the capture.

## Follow the domain, not a feature tour

1. **Understand/Plan (30 seconds):** `demo-requester` needs **2.50 hours**
   for `DEMO-CNC-01`, with a ceiling of **100.00 EUR/hour**. Preparing this
   request creates a `NEW` work order; it has **not been submitted** yet.
2. **Implement/Test (45 seconds):** `demo-provider` publishes **3.00 hours**
   at **80.50 EUR/hour**. Its capacity offer is `ACCEPTED`. The prepared
   request is then submitted against that available capacity. This ordering
   is intentional: publishing the offer precedes submitting the request.
3. **Review (45 seconds):** an assignment allocates **2.50 hours** at the
   accepted provider-offer rate, **80.50 EUR/hour**, not the request ceiling.
   The request is `ASSIGNED`, the offer `PARTIALLY_ASSIGNED`, and **0.50 hours**
   of provider capacity remain. This is allocation, not completed maintenance,
   a bill, or a message to a real technician.
4. **Explain (30 seconds):** the estimated assigned service cost is
   **2.50 × 80.50 = 201.25 EUR**. Explain why **250.00 EUR** is not the assigned
   cost, and why **0.50 hours** remain available. No code changes are required.

The domain field `max_hourly_rate` means a requester ceiling on a `REQUEST`,
but the provider's asking rate on an `OFFER`. The general provider selection
rule is lowest eligible rate, FIFO at equal rates; this small example has one
provider and demonstrates the accepted-offer rate rather than a provider
competition.

### Expected output

Both routes show these exact lines; the linked capture contains the complete
transcript:

```text
   DEMO-REQUEST-001 -> ASSIGNED
   DEMO-OFFER-001 -> PARTIALLY_ASSIGNED
   Assigned: 2.50 h at 80.50 EUR/h
   Unassigned request: 0.00 h | available provider capacity: 0.50 h
```

```text
   Requester net workload: +2.50 h
   Provider net workload: -2.50 h
   Estimated assigned service cost: 2.50 h x 80.50 EUR/h = 201.25 EUR
   Requester workload revaluation cost: 0.00 EUR (not an invoice total)
```

**Read the signs and costs carefully.** Signed net workload records the two
sides: positive for the requester, negative for the provider's committed
capacity. It does not mean negative available capacity or negative overdue
hours. The existing workload `total_cost` measures realised/unrealised
revaluation, not the assignment's estimated service cost. With no rate change,
that revaluation is **0.00 EUR** even though allocated service costs
**201.25 EUR**. Do not treat dashboard revaluation as an invoice.

Hours, rates, and costs remain exact `Decimal` values. The transcript uses dot
decimals and explicit EUR to make arithmetic easy to compare with machine
values. In a German human-facing presentation, the same amount is
**201,25 EUR**; there is no FX conversion.

## What is deterministic, and what is isolated?

- Input work-order IDs, quantities, and the aware-UTC fixture creation time
  `2026-01-15T08:00:00+00:00` are fixed. The transcript is repeatable.
- Real execution still generates fresh assignment IDs and actual aware-UTC
  execution/update timestamps. They are deliberately omitted from the
  transcript, not overwritten or presented as fixture-time execution.
  No global clock, UUID generator, or shared application state is patched.
- UTC is the data convention. `Europe/Berlin` is a presentation conversion,
  not a fixed timezone offset; see the [time conventions](../challenges/reference/dach_conventions.md).
- Every run builds new equipment, work orders, a queue, workload state, and
  an in-memory event log. The event bus is stopped on success and failure.
  No server, HTTP request, telemetry feed, or database is created.
- The CLI does not write files or change the repository. Ordinary Python
  import caching can be suppressed with `python -B scripts/workshop_demo.py --run`.
  Repeating the command starts fresh; there is nothing to reset.

The tests compare the real run with the captured file, verify Decimal rates,
UTC timestamps, lifecycle transitions, repeated/concurrent isolation, and
cleanup on failure. A guarded CLI test rejects file writes, network operations,
and database creation:

```bash
python -m pytest tests/test_workshop_demo_v2.py -q
```

## Optional: recognise the same concepts in the existing dashboard

**Skip this section within the 2–3 minute timebox.** The dashboard is a separate
application session, not required evidence for this first win.

From a prepared checkout, configure a **disposable local** `MITTELWERK_API_KEY`
privately in the server environment and set
`MITTELWERK_API_ORGANIZATION_ID=demo-dashboard`. Keep the key out of shell history,
chat, commits, screenshots, and recordings. Follow the existing
[API authentication instructions](API_REFERENCE.md#authentication-and-permissions);
`.env` is not loaded automatically. Then launch the existing app:

```bash
python main.py --host 127.0.0.1 --port 8443
```

Open **http://127.0.0.1:8443/** on the same machine. In **API key**, privately
enter the same disposable key and select **Save**. The browser sends it as
`X-API-Key` to the same-origin API; its tab uses session storage. Only that
key's organisation can see its work orders and workloads. The public dashboard
shell and health check do not make protected metrics public. Missing keys
return **401**; invalid, expired, revoked, or under-permissioned keys return
**403**. Never disable authentication or make a forwarded port public to
troubleshoot this optional view.

An initially empty work-order/workload view is expected: this demo does not
seed the running app, and its `DEMO-CNC-01` asset exists only in the demo.
The dashboard can display requests and workloads submitted separately through
the app's authenticated API; it does not import this transcript. Unlike the
demo, the normal app follows `settings.yaml`, runs simulated telemetry, and
can create the local `mittelwerk.db` store. To finish, select **Clear**, close
the tab, stop the server with **Ctrl+C**, and remove the disposable key from
your shell environment.

## The application and workshop scenarios are different workspaces

**Fixing a scenario does not update the running application or dashboard.**

`scripts/workshop.py start <scenario>` creates an isolated working copy under
that scenario's `work/` directory from inert `*.txt` payloads. Scenario checks
exercise that working copy. They do not replace `mittelwerk/`, change this
demo, deploy a fix, or restart any app. The healthy baseline remains separate.
This walkthrough neither starts nor solves a scenario.

Return to your chosen [Lab 2 route](../challenges/lab_02_incident_triage.md).
Keep the sequence **Understand/Plan -> Implement/Test -> Review -> Explain**;
the first win supplies domain vocabulary, not an additional workshop outcome.
