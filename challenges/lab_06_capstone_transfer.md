# Lab 6 - Capstone: transfer under mild adversity

**Block:** 15:45-16:35 (50 minutes) - **Mode:** individual
**Loop stages:** all four
**Scenario:** `capstone-transfer`

---

## Outcome

You run the whole loop alone on an unseen, domain-light task. Treat every
supplied claim as something to check against the acceptance evidence.

This is an assessment of **transfer**, not typing speed or feature access. A
small, reviewed result with honest evidence is stronger than a rushed full
implementation. Your work and self-assessment remain private: facilitators do not
collect code, prompts, notes, transcripts, or scores. You may choose to show an
artifact for feedback.

Live Copilot features are optional. The scenario, tests, standard library, and
captured fallback are enough.

---

## What fits in 50 minutes

The scenario supplies:

- a four-operation utility skeleton;
- a complete standard-library acceptance suite;
- synthetic sample data; and
- a short handover template.

For Core, you implement the four missing operations, run the supplied tests, add
one participant-owned check for a material assumption, review the diff, complete
the handover, and use the private rubric. You do **not** need another test suite
or dependency. A helper that sums stored amount strings with `Decimal` is already
implemented.

The four operations are:

1. calculate the UTC selection window for a Berlin business date;
2. select the records in that half-open window;
3. produce the ISO-dated filename; and
4. format the display total with an explicit currency.

That is the entire scope.

---

## Set up and establish the baseline - 4 minutes

```bash
python scripts/workshop.py start capstone-transfer
python scripts/workshop.py verify capstone-transfer
```

Work only in `workshop/scenarios/capstone-transfer/work/`. The first verification
is expected to fail because the staged operations are not implemented. Record
the command and the first useful failure; do not diagnose every downstream
failure.

If `start` is unavailable, move immediately to
`workshop/fallbacks/capstone-transfer/README.md`. Do not spend the capstone
troubleshooting workshop tooling.

---

## Read these artifacts in order

| Artifact | What to take from it |
|---|---|
| `issue.md` | The requested behaviour, supplied claims, and explicit non-goals |
| `acceptance.md` | The authority when the issue and expected behaviour disagree |
| `data/records_2026-08-19.json` | UTC timestamps and dot-decimal amount strings |
| `work/test_daily_export.py` | The supplied observable checks; read before editing |
| `work/daily_export.py` | Four missing operations and one supplied Decimal helper |
| `work/NOTES.md` | The handover you must finish even if code is incomplete |

Do not ask an assistant to summarise these before you read them. Independent
transfer includes deciding which source is authoritative.

## Choose a role-equivalent route

Both routes perform the same loop and use the same lane and rubric.

| Route | Substantive Implement/Test evidence |
|---|---|
| **Builder** | Implement the selected-lane operations and add one participant-owned adversarial check for a material assumption not safely left implicit |
| **Supervising architect** | Turn one material assumption into a participant-owned adversarial check, request or produce a candidate for the selected lane, inspect the complete diff, make at least one bounded correction, and run the focused checks |

The architect route is not a prose review. It changes a test and code, or
corrects a concrete candidate, and records the same command/result evidence.

---

## Business invariants at stake

Everything needed is stated in
[reference/invariants.md](reference/invariants.md). No trading knowledge is
required.

- **INV-TIME-1** - stored and exchanged timestamps are timezone-aware UTC.
- **INV-TIME-3** - business date `D` is
  `[D 00:00 Europe/Berlin, D+1 00:00 Europe/Berlin)`, converted to UTC. It is not
  a fixed 24-hour UTC window and not UTC plus a constant offset.
- **INV-FMT-1** - machine values use a decimal point; German-language display
  uses a decimal comma and dot thousands separators.
- **INV-FMT-2** - a displayed amount carries its currency.
- **INV-FMT-3** - rounding happens only for display, never in stored values or
  intermediate arithmetic.
- **INV-FMT-4** - identifiers and filenames use ISO 8601 dates.

Amounts remain `Decimal` throughout storage and arithmetic; do not introduce
binary float.

### Expected values

Selection windows:

| Business date (Europe/Berlin) | Window start (UTC) | Window end (UTC) | Length |
|---|---|---|---|
| `2026-03-29` | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 hours |
| `2026-08-19` | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 hours |
| `2026-10-25` | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 hours |

Filename for business date `2026-08-19`:

```text
daily_export_2026-08-19.csv
```

Display total for the stored value `1234567.891`:

```text
1.234.567,89 EUR
```

A record whose UTC timestamp is exactly the window end belongs to the **next**
business date.

---

## Use the clock

| Time | Stage | Work and stop rule |
|---|---|---|
| 15:45-15:49 | Set up | Start the scenario and capture the expected failing baseline. Switch to fallback immediately if staging is blocked. |
| 15:49-15:57 | Understand/Plan | Read the six artifacts. Record behaviour, claim to check, non-goal, role route, lane, and workflow. |
| 15:57-16:17 | Implement/Test | Work one observable behaviour at a time; add one participant-owned adversarial check. At 16:10, narrow if Core is not on course. |
| 16:17-16:23 | Review | Freeze behaviour. Read the diff line by line; for the architect route, record the bounded correction. |
| 16:23-16:28 | Explain | Complete the handover with evidence, checked claim, blast radius, and uncertainty. |
| 16:28-16:31 | [Private rubric](../workshop/ops/ASSESSMENT_RUBRIC.md) | Self-score the five dimensions and name one next practice action. Scores remain private. |
| 16:31-16:35 | Preserve/reset | Run the full verifier once, record the result, and reset. |

The stop times are part of the assessment. Scope control and a usable handover
are engineering work.

---

## Choose one lane by 15:57

| Lane | Completion boundary |
|---|---|
| **Supported** | Implement and verify the selection window and record membership, including all three dates, timezone-aware UTC bounds, and the half-open boundary. Review the diff and complete the handover. Filename and display formatting remain explicitly unfinished. |
| **Core** | Implement all four missing operations, pass the full supplied suite, add one participant-owned adversarial check, review the diff, complete the handover, and self-score. |
| **Extension** | Only after Core evidence and the handover are complete: add one focused test of a risk not already covered, without a new dependency, and explain what failure it would detect. |

A Supported attempt is intentionally allowed to fail the full verifier on the
unfinished groups. Record which focused behaviour passed and the first remaining
failure. Do not present it as Core.

### Partial-success protocol

If you are blocked or behind:

1. keep the last passing behaviour and stop expanding scope;
2. record the exact command, observed result, and first unresolved failure;
3. state what remains unimplemented in the handover;
4. inspect the diff you do have; and
5. verify and reset at 16:31 with everyone else.

This is an honest incomplete result, not a penalty and not a reason to skip
Review or Explain.

---

## Acceptance

### Supported and Core

- [ ] The baseline command and its observed starting failure are recorded
- [ ] The plan names the requested behaviour, one claim to check, one non-goal,
      the role route, and the chosen lane
- [ ] One participant-owned adversarial check tests a material assumption without
      weakening or merely copying a supplied assertion
- [ ] The 23-, 24-, and 25-hour windows are correct and timezone-aware UTC
- [ ] Record membership is half-open: the start is included and the end is
      excluded
- [ ] The diff contains only work needed for the selected lane
- [ ] The handover states what passed, what remains, and the three-part
      uncertainty sentence
- [ ] The private rubric was used and one next practice action was named; no
      score was submitted
- [ ] The full verifier result is recorded honestly, then the scenario is reset

### Core adds

- [ ] Selected stored amount strings are summed without binary float
- [ ] Machine values keep a decimal point; only display output uses a comma
- [ ] The displayed total carries its currency
- [ ] The filename is ISO-dated and sortable
- [ ] `python scripts/workshop.py verify capstone-transfer` passes

The verifier checks the complete Core scenario. It does not read `NOTES.md`, so a
green command alone is not complete transfer evidence.

---

## Preserve and reset - 16:31

Everyone stops at 16:31. Run both commands even if the utility is incomplete:

```bash
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

Reset archives the attempt and prints its location before restoring the
pre-start tree. Put that archive path and the first unfinished behaviour in the
Lab 7 remediation line. Nothing in Lab 7 depends on a green verifier.

While the room resets, answer in one sentence:
**what did you check that you were tempted to take on trust?**

---

## Solo path

Use the same 50-minute clock and stop rules. If scenario tooling is unavailable,
follow `workshop/fallbacks/capstone-transfer/README.md`; it contains the same
brief, data, skeleton, tests, and handover template. No network or live Copilot
feature is required.

---

## Hints

[hints/lab_06.md](hints/lab_06.md) provides process nudges only. It does not name
which claim to challenge, prescribe code structure, or disclose a test name.

---

## Reflection and retrieval

1. Which result came from evidence rather than familiarity?
2. Where did you narrow scope, and what did that preserve?
3. Without looking: why can a Berlin business date be 23 or 25 hours?
4. Where in your own systems is a "day" silently treated as 24 hours?

---

*Next: [Lab 7 - Close](lab_07_close_and_adoption.md)*
