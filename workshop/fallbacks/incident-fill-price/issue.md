# QXM-4471 - "Client was charged a price that was never on the screen"

| Field | Value |
|---|---|
| Raised | 2026-08-19, 09:47 CEST (07:47 UTC) |
| Raised by | Desk Operations (Handelsunterstuetzung), Frankfurt desk, on-call rota |
| Severity (reporter's assessment) | High - client-facing |
| Order reference | ORD-2026-0819-0442 |
| Environment | Simulation environment, order flow replay |

---

## What the client told us

> "We sent a market order for 120 at just after 09:14 our time. The screen showed
> 101,20 on the offer, twice, and the confirmation came back at 101,35. Nobody was
> at 101,35. The second order, later that morning, came back with no price at all
> on the confirmation - just an empty field. Please explain both."

We checked the depth snapshot the client had at the time and it matches ours: two
offers at 101,20 (100 and 50) and one at 101,50 (200). So 101,35 was not on the
book at any point during that second.

## What we can see from here

- The confirmation for ORD-2026-0819-0442 shows an average price of `101.35`.
- The follow-up order that morning came back with an empty price field on the
  confirmation. Our confirmation template does not have a "no price" state, so
  the client saw a blank.
- Both orders did fill. Nobody is complaining about missing quantity, and the
  positions look right to us.

## What we think is going on

This looks like the queue is being served in the wrong order. The 101,50 offer
was entered *before* the two at 101,20 - I checked, it was resting first - and
the engine is probably filling the oldest one first and then blending the price.
That would explain a number in the middle. Somebody changed something in the
matching path last week, so I would start there.

I am not an engineer, so treat that last paragraph as a guess. The part I am sure
about is the two prices on the confirmations.

## What we need

1. An explanation the desk can send to the client this afternoon.
2. Whatever the fix is, evidence it actually holds - we have been told "fixed"
   twice this quarter on things that came back.
3. If the blank price and the 101,35 turn out to be the same problem, say so
   explicitly. Two separate incidents are two separate client letters.

## Attachments

- `logs/qxm-engine-2026-08-19.log` - engine log excerpt, timestamps in UTC
- `logs/execution_report_ORD-2026-0819-0442.txt` - the confirmation the client got

---

*Synthetic ticket. The client, the desk, the order references and every price in
this scenario are simulated for the workshop; the ticket contains no personal
data, and neither should your notes about it.*
