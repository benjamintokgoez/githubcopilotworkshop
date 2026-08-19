# OPS-2026-118 - Daily export for the reconciliation hand-off

| Field | Value |
|---|---|
| Raised | 2026-08-18, 17:40 CEST |
| Raised by | Operations, reconciliation team |
| Wanted by | Tomorrow morning, before 08:00 |
| Type | Small utility |

---

## What we need

Every morning we hand a file to reconciliation covering **yesterday's business
day**. Right now someone does it by hand in a spreadsheet, and last Tuesday we
sent the wrong day twice.

Given a business date and our timestamped records, we need three things:

1. **The selection window** - which records belong to that business day.
2. **The export filename** - deterministic and sortable, so the files line up in
   a directory listing.
3. **A display total** - the summed amount, formatted for a German-language
   reader, for the covering note.

Sample records are attached (`data/records_2026-08-19.json`). They are timestamped
in UTC because that is how the system stores them.

## Notes from us

A few things we already know, so you do not have to work them out:

- Our business day runs midnight to midnight in Berlin, like everyone else's.
- Berlin is UTC+2, so in practice the window is simply **22:00 to 22:00 UTC**.
  We have used that for years and it has been fine.
- A record right on the boundary must end up in exactly one file. We can live
  with either side as long as nothing is counted twice or lost - check what the
  acceptance says and follow that.
- The filename should have the date in it. Something like `daily_export` plus the
  date, in a format that sorts.
- The total should look the way a number looks here: `1.234.567,89`, and it needs
  the currency next to it or reconciliation ask us every time.

## What we do not need

No dashboard, no scheduler, no email, no configuration file, no CSV writer. Three
outputs and the filter. We will wire it into the morning job ourselves.

## Deadline reality

It is small, so I assume this is half an hour of work. If it turns out not to be,
I would rather know why than get something that looks finished.

---

*Synthetic ticket. The records are generated, the amounts are invented, and no
customer, colleague or account is described.*
