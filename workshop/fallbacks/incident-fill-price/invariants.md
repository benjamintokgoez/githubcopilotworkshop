# Invariants the desk believes were broken

This is the desk's reading of the rules, not a list of files to change and not a
diagnosis. The authoritative text, with worked numbers, is
[challenges/reference/invariants.md](../../../challenges/reference/invariants.md#1-order-book-and-matching).

## Primary

**INV-MATCH-2 - the maker's price wins.** A market order fills at the resting
(maker) order's price. The incoming order never sets the fill price, and a fill
price is never null.

The desk's two complaints map onto the two halves of that sentence:

| Observation | Half of INV-MATCH-2 it touches |
|---|---|
| Confirmation shows `101,35`, a price that never rested | The incoming order must not set the price |
| Follow-up confirmation shows a blank price | A fill price is never null |

Whether those are one defect or two is exactly what the ticket asks you to state.

## Supporting

**INV-MATCH-1 - price-time priority.** Best price first; at the same price, the
earlier arrival fills first. Note what this implies for the reporter's theory: an
order resting at a worse price does not fill first just because it arrived first.

**INV-MATCH-3 - quantity conservation.** Quantity removed from the buy side
equals quantity removed from the sell side, cumulative fills never exceed the
order quantity, and remaining quantity is never negative.

**INV-TIME-1 - storage is UTC.** The logs are UTC; the desk quotes CEST. If your
change touches anything that carries a timestamp, it stays timezone-aware UTC.

## Reference book state (from the depth snapshot in the ticket)

| Resting order | Side | Price | Quantity | Arrived (UTC) |
|---|---|---|---|---|
| A1 | SELL | 101.20 | 100 | 2026-08-19T07:14:02Z |
| A2 | SELL | 101.20 | 50 | 2026-08-19T07:14:09Z |
| A3 | SELL | 101.50 | 200 | 2026-08-19T07:13:55Z |

Expected behaviour under the invariants above: a market buy of 120 fills 100 from
A1 and 20 from A2, both at `101.20`; a following market buy of 200 fills 30 from
A2 at `101.20` and 170 from A3 at `101.50`, average `101.455`. A3 is untouched by
the first order even though it arrived first.
