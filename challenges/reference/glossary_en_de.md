# Short glossary (EN / DE)

The workshop runs in English. This list exists so that a German-speaking
participant can map workshop vocabulary onto the words their organisation actually
uses, and so that English-speaking facilitators understand the DACH terms that come
up in discussion. It is deliberately short: it covers terms that change what you
*do*, not every noun in the room.

## Workshop and engineering terms

| English | Deutsch | Note |
|---|---|---|
| Supervised agentic engineering | Beaufsichtigtes agentisches Arbeiten | The whole point of the day |
| Loop (Understand/Plan, Implement/Test, Review, Explain) | Arbeitsschleife | Used as a noun all day |
| Durable context | Dauerhafter Kontext | Instructions/briefs that survive between sessions |
| Invariant | Invariante / Geschaeftsregel | The rule a change must not break |
| Blast radius | Auswirkungsbereich | What else your change can break |
| Evidence | Nachweis | Command output, failing-then-passing test |
| Acceptance criteria | Abnahmekriterien | The bar for "done" |
| Rollback / reset | Zuruecksetzen | `workshop.py reset` |
| Regression test | Regressionstest | Fails before the fix, passes after |
| Review | Pruefung / Review | Human judgement, not a rubber stamp |
| Handover | Uebergabe | What you leave for the next person |

## Governance and workplace terms

| Deutsch | English | Why it matters today |
|---|---|---|
| Betriebsrat | Works council | Usually involved before tooling that can measure individuals is rolled out |
| Mitbestimmung | Co-determination | The legal reason the above is not optional in DE/AT |
| Betriebsvereinbarung | Works agreement | The document that makes a rollout acceptable |
| Datenschutz | Data protection | Applies to prompt content, not just databases |
| Datensparsamkeit | Data minimisation | Give the smallest context that makes the task decidable |
| Freigabe | Approval / sign-off | Who says a change may ship |
| Vier-Augen-Prinzip | Four-eyes principle | Agent-written code does not get an exemption |
| Nachvollziehbarkeit | Traceability | If you cannot explain it, you cannot ship it |
| Sorgfaltspflicht | Duty of care | Your professional responsibility does not transfer to a tool |
| Revisionssicherheit | Audit-proof record keeping | Why review threads and evidence notes are kept |

## Formatting vocabulary

| English | Deutsch | Example |
|---|---|---|
| Decimal comma | Dezimalkomma | Display: `101,455` |
| Decimal point | Dezimalpunkt | Code and config: `101.455` |
| Thousands separator | Tausendertrennzeichen | Display: `1.234.567,89` |
| 24-hour time | 24-Stunden-Zeit | `14:30` |
| Timezone-aware timestamp | Zeitzonenbehaftete Zeitangabe | Stored as UTC, shown as CET/CEST |

Umlauts are written as `ae`, `oe`, `ue` in this file so that it renders identically
in every terminal, diff viewer and screen reader used in the room.
