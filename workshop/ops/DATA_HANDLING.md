# Data handling policy

This workshop uses the minimum information needed to deliver, support, and improve the session. It is operational guidance, **not legal advice**. The organizer is responsible for identifying a lawful basis, giving notices, handling data-subject rights, and confirming works-council and security requirements.

## Potentially allowed after notice and organizer approval

- Aggregate attendance and lane counts.
- Aggregate, anonymous role-group completion counts with small-cell suppression
  when a pilot tests developer/architect parity.
- Aggregate anonymous feedback themes.
- Technical incident category, status, time, impact, and fallback lane.
- Sanitized synthetic repositories, fixtures, screenshots, and captures.

For each collection, state the purpose, fields, optionality, access, and
retention before it begins. Nothing in this list authorizes collection merely
because it would be convenient.

## Never collect as workshop data

- Production or customer code, personal data, confidential business data, or regulated data.
- Passwords, API keys, access tokens, recovery codes, cookies, or private URLs.
- Full prompt/response logs, browser history, keystrokes, screen recordings, or hidden chain-of-thought.
- Individual surveillance, productivity metrics, or tool-usage scores.
- Individual artifacts, rubric scores, lane histories, or identifiable
  completion/latency/performance telemetry.
- Public rankings or participant performance comparisons.

A separate employer process does not become workshop collection by changing its
label. It needs its own documented purpose, transparency, lawful basis, and
privacy/works-council review.

## Operating checklist

- [ ] State purpose, fields, access, retention, optionality, and contact before collection.
- [ ] Use purpose limitation: collect only what supports delivery, support, or explicitly approved learning evaluation.
- [ ] Minimise fields; prefer aggregate counts and short structured notes over free text.
- [ ] Use synthetic data and disposable repositories; stop and delete if sensitive content is pasted.
- [ ] Treat `.workshop-state/attempts/` as participant-owned temporary data. It
      may contain a complete scenario work directory after a size or file-type
      fallback; inspect only with consent and delete it after the approved
      retention window.
- [ ] Restrict access to the organizer’s named roles; do not share raw feedback with employers or vendors outside the approved process.
- [ ] Keep a retention date for each approved dataset; delete captures, branches,
      and incident notes when no longer needed.
- [ ] Secure storage and transfer according to the organizer’s policy; do not put workshop data in personal drives.
- [ ] Provide a confidential correction/deletion/contact route defined by the organizer.
- [ ] Review vendors, cloud settings, subprocessors, transfer mechanisms, and AI product data controls before delivery.
- [ ] Report suspected disclosure through the organizer’s incident route; do not investigate by copying more data.

## Suggested retention schedule

| Item | Default retention | Owner |
| --- | --- | --- |
| Attendance / lane aggregate | 30 days | Organizer |
| Technical incident summary | 90 days or policy limit | Technical producer |
| Anonymous feedback themes | 90 days | Facilitator |
| Raw captures / temporary branches | Delete after delivery and incident window | Producer / repository owner |

The organizer may shorten these periods or require a documented alternative. Do not treat these defaults as a legal retention rule.

## References

- GDPR principles, including purpose limitation, data minimisation, storage limitation, and integrity/confidentiality: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- European Data Protection Board: https://www.edpb.europa.eu/
