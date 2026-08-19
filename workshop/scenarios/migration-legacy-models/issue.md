# QXM-4520 - Move the SIMX reference-data surface off the 1.x compatibility shim

| Field | Value |
|---|---|
| Raised | 2026-08-17, 16:20 CEST |
| Raised by | Tech lead, Platform Services |
| Type | Technical debt with a date on it |
| Deadline | End of the current sprint (2026-08-28) |

---

## Why now

The reference-data models in this surface are still written against the 1.x
idioms of our validation library. They only keep working because we import them
through the library's compatibility shim. That shim is a migration aid, not a
support commitment: it is deprecated, it is excluded from our dependency
security policy exceptions from October, and the next major release removes it.

We are not doing this because the new API is nicer. We are doing it because
"our models only run through a deprecated shim" is an answer I do not want to
give in the next audit.

## The constraint that matters

**The external contract does not change.** Downstream systems parse what this
surface emits, and we do not control all of them:

- Serialised field names, aliases, nesting and types stay identical.
- Numeric values keep a dot decimal separator in payloads (INV-FMT-1). Nobody
  wants to discover a localised number inside a JSON body again.
- Timestamps stay timezone-aware UTC through a round trip (INV-TIME-1), and the
  serialised representation stays the one consumers already parse.
- Inputs we rejected before are still rejected, and the caller still gets an
  error it can act on - same exception type, same place.

If you find a difference you think is an improvement, it is still a difference.
Write it down, decide it explicitly, and say so in the handover.

## Scope

The in-scope files are listed in `inventory.md` and in the scenario manifest.
Nothing else in the repository is in scope for this ticket. If the work
genuinely requires touching something outside that list, that is worth a
sentence in the handover and a moment of suspicion first.

## What "done" looks like

- Nothing in the in-scope files imports the compatibility shim any more.
- The contract checks pass.
- The handover names what changed, what deliberately did not, and which decision
  you had to make that this ticket did not make for you.

## What I have not specified

I wrote this ticket in fifteen minutes between meetings, so assume it is
underspecified in at least one place. If you find the gap, decide it, and tell me
what you decided - do not guess quietly and do not wait for me to answer. The
current behaviour of the code is a better specification than my prose; capture it
before you change anything.

---

*Synthetic ticket for the workshop. No real system, customer, or colleague is
described here.*
