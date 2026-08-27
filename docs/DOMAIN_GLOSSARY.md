# Domain glossary - MittelWerk

MittelWerk is a synthetic industrial equipment and field-service platform. The
[business invariants](../challenges/reference/invariants.md) are normative; this
glossary explains the vocabulary.

## Equipment and service operations

| Term | Meaning |
|---|---|
| **Equipment / asset** | A machine or installation identified by a stable, uppercase `asset_code`. |
| **Site code** | A synthetic organisational location identifier, never a postal address. |
| **Service interval** | Planned number of days between maintenance activities. |
| **Hourly service rate** | Exact `Decimal` amount with explicit currency. |
| **Service request** | Work an organisation needs for one asset, including requested hours and a maximum eligible rate. |
| **Capacity offer** | Hours a regional provider makes available at a stated rate. |
| **Assignment** | Capacity allocated from one provider offer to one service request. |
| **Rate-time priority** | Lowest eligible provider rate first; FIFO among equal-rate offers. |
| **Work order** | The lifecycle record for a service request or provider-capacity offer. |
| **Assigned hours** | Hours already allocated; never greater than requested or offered hours. |
| **Terminal state** | Completed, cancelled, rejected, or expired; a terminal work order cannot return to the active queue. |
| **ID reservation** | The first submission attempt permanently reserves a work-order ID. |

## Operational analytics

| Term | Meaning |
|---|---|
| **Open hours** | Requested work not yet completed. A non-negative magnitude. |
| **Overdue hours** | Open hours past their SLA deadline; bounded by open hours. |
| **Utilization** | Assigned hours divided by available capacity, bounded to `[0, 1]`. |
| **Estimated service cost** | Sum of assigned hours multiplied by accepted provider rates using `Decimal`. |
| **Operational snapshot** | Point-in-time counts, hours, utilization, costs, and aware-UTC timestamp. |
| **Service risk** | A bounded operational estimate such as overdue workload or SLA exposure. |

## Telemetry and time

| Term | Meaning |
|---|---|
| **Telemetry reading** | Synthetic asset status or measurement with a finite value and aware-UTC timestamp. |
| **Status feed** | Deterministic offline stream used to exercise lifecycle and data-boundary code. |
| **Aware UTC** | Timestamp with timezone information normalized to UTC. |
| **Naive timestamp** | Timestamp without timezone information; external and persistence boundaries reject it. |
| **Europe/Berlin** | Presentation timezone applying CET/CEST from timezone data. |
| **Local business day** | Half-open local interval `[00:00, next 00:00)` converted to UTC; it may contain 23, 24, or 25 hours. |
| **Decimal comma** | Human-facing `de-DE` output such as `1.234,56`; machine values remain `1234.56`. |
| **Currency basis** | Equipment/rate metadata carries EUR or CHF. MittelWerk performs no FX conversion. |

## Platform and governance

| Term | Meaning |
|---|---|
| **Event log** | Bounded in-process lifecycle history with sequence-based replay; not a production event store. |
| **API-key principal** | `X-API-Key` resolves to an organisation and permissions. Request bodies cannot override it. |
| **HMAC** | SHA-256 keyed digest used for safe key storage and canonical request signatures. |
| **MCP** | Model Context Protocol. MittelWerk exposes bounded tools through the official Python SDK v2. |
| **Tool annotation** | Intent metadata; it does not authorize a call. |
| **Least privilege** | Provide only the tools, data, filesystem access, and network access required for the task. |
| **Four-eyes principle** | `Vier-Augen-Prinzip`: generated changes still require competent human review. |
| **Traceability** | `Nachvollziehbarkeit`: retain task, evidence, checks, decision, and uncertainty without unnecessary personal data. |
