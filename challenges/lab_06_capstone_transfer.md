# Lab 6 - Capstone: transfer under mild adversity

**Block:** 15:55-16:35 (40 minutes) - **Mode:** individual
**Loop stages:** all four
**Scenario:** `capstone-transfer`

---

## Outcome

You run the whole loop alone, on a task you have not seen, in an area of the
system nobody touched today, with a brief that contains at least one confident
claim that does not survive checking.

This is the only individual assessment of the day, and it assesses **transfer**,
not speed. Finishing early is not a result. Producing a small, correct, well
evidenced change with an honest uncertainty statement is.

---

## Why it looks easy

The task is deliberately **domain-light**. There is no options maths, no order
book, no risk model. It is date handling, windows, and formatting - the kind of
work every team has, and the kind that produces production incidents twice a year
in every DACH company.

If it feels straightforward, that is the point. The difficulty is not the domain.
It is staying disciplined when the task looks small.

---

## Set up

```bash
python scripts/workshop.py start capstone-transfer
```

Work in `workshop/scenarios/capstone-transfer/work/`, where the scenario stages
the utility skeleton, its tests, and `NOTES.md`. Each participant works in their
own checkout, so no initials-based directory is needed. Nothing from earlier labs
is required.

---

## Artifacts you are working from

| Artifact | What it is |
|---|---|
| `issue.md` | A request from an operations colleague for a daily export utility, with a deadline and an opinion |
| Sample input | A small set of timestamped records, stored in UTC |
| `acceptance.md` | The expected outputs, restated from this page |

> **The brief contains at least one confident claim that is wrong.** It may be in
> the ticket, in a colleague's comment, or in the first suggestion your assistant
> offers. It will sound reasonable and it will be easy to implement. Finding it is
> part of the task, and nobody will tell you which claim it is.

---

## The task

Build a small utility that, given a **business date** and a set of UTC-timestamped
records, produces:

1. **The selection window.** The UTC interval covering that business date in
   `Europe/Berlin`, as a half-open interval `[start, end)`.
2. **The export filename.** Deterministic, sortable, ISO-dated.
3. **A display total.** The summed amount, formatted for a German-language reader.

That is all. Resist every temptation to build more.

---

## Business invariants at stake

All of these are stated in full, with worked values, in
[reference/invariants.md](reference/invariants.md). **No domain knowledge is
required or assessed.**

- **INV-TIME-1** - stored timestamps are timezone-aware UTC.
- **INV-TIME-3** - the window for business date `D` is
  `[D 00:00 Europe/Berlin, D+1 00:00 Europe/Berlin)`, converted to UTC. It is not
  a fixed 24-hour UTC window, and it is not UTC plus a constant offset.
- **INV-FMT-1** - display uses a decimal comma and dot thousands separators;
  stored and transmitted values use a dot.
- **INV-FMT-2** - a displayed amount carries its currency.
- **INV-FMT-4** - identifiers and filenames use ISO 8601 dates.

### Expected values (these are the acceptance targets)

Selection windows:

| Business date (Europe/Berlin) | Window start (UTC) | Window end (UTC) | Length |
|---|---|---|---|
| `2026-03-29` | `2026-03-28T23:00:00Z` | `2026-03-29T22:00:00Z` | 23 hours |
| `2026-08-19` | `2026-08-18T22:00:00Z` | `2026-08-19T22:00:00Z` | 24 hours |
| `2026-10-25` | `2026-10-24T22:00:00Z` | `2026-10-25T23:00:00Z` | 25 hours |

Filename for business date `2026-08-19`:

```
daily_export_2026-08-19.csv
```

Display total, for a summed amount whose stored value is `1234567.891`:

```
1.234.567,89 EUR
```

A record whose UTC timestamp is exactly the window end belongs to the **next**
business date. The interval is half-open.

---

## Run the loop

1. **Understand/Plan (8 min).** Read the brief. Write down what is asked, what is
   assumed, and which assumption you intend to check. Choose your workflow and
   record why.
2. **Implement/Test (15 min).** Write the tests for the three dates in the table
   **before or alongside** the implementation. The two DST dates are not edge cases
   here; they are the specification.
3. **Review (7 min).** Read your own diff as a stranger. Is anything in it not
   required by the task? Does any formatting leak into stored values?
4. **Explain (5 min).** Write the handover, including the three-part uncertainty
   sentence and one line naming the claim in the brief that did not survive
   checking - or stating that you found none, if that is your honest conclusion.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | The selection window only, with the three dates covered by tests. Filename and formatting can be stated in prose rather than implemented. |
| **Core** | All three outputs, tests for the three dates, the misleading-claim note, and the handover. |
| **Extension** | Add a property-based or table-driven test that covers both DST transitions for a second year without new code paths. Then write the two sentences you would add to your own repository's durable context so this class of defect cannot recur. |

---

## Evidence and acceptance

- [ ] Tests exist for all three business dates in the table, and they pass
- [ ] The 23-hour and 25-hour windows are correct, not just the 24-hour one
- [ ] The half-open boundary is tested: a record exactly at the window end is
      excluded
- [ ] Stored values use a dot; only display output uses a comma
- [ ] The displayed total carries its currency
- [ ] The filename is ISO-dated and sortable
- [ ] Your handover names the claim you rejected, or states that you found none
- [ ] The three-part uncertainty sentence is present
- [ ] Nothing outside `workshop/scenarios/capstone-transfer/work/` is modified
- [ ] `python scripts/workshop.py verify capstone-transfer` passes, or its failing
      check is copied into your Lab 7 remediation note

---

## Resync, preserve, and reset - 16:30

Everyone stops at 16:30 whether or not the utility is finished. Nothing in Lab 7
depends on completing it. Run the verifier, then reset even if the utility is
incomplete. Reset archives your attempt and prints its location before restoring
the pre-start tree.

```bash
python scripts/workshop.py verify capstone-transfer
python scripts/workshop.py reset capstone-transfer
```

While the room resets, three people answer one question in one sentence:
**what did you check that you were tempted to take on trust?**

---

## Solo path

This lab is already individual, so it works unchanged outside a workshop. If the
scenario tooling is unavailable, everything you need is on this page: the task,
the invariants, and the expected values. Write the brief yourself in three
sentences, including one claim you are unsure about, and then test it.

---

## Hints

[hints/lab_06.md](hints/lab_06.md) - three collapsed levels. Level 1 is a nudge
about which of your assumptions is worth checking first, not a location.

---

## Reflection and retrieval

1. Which of the three outputs did you get right by knowledge, and which by
   checking? Only the second one transfers.
2. If you accepted the wrong claim: what would have caught it - a test, a
   reviewer, a durable-context rule, or reading the brief more slowly?
3. Retrieval, without looking: how many hours long is `2026-10-25` in
   `Europe/Berlin`, and why?
4. Where in your own codebase is there a "day" that is silently assumed to be 24
   hours?

---

*Next: [Lab 7 - Close](lab_07_close_and_adoption.md)*
