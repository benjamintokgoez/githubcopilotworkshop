# Hints - Lab 2 (guided incident)

No hint level names a file, a function, or a fix. If you want the answer, the
honest move is to ask a human, and that is an allowed move.

<details>
<summary><strong>L1 - Orientation</strong> (where to look, what to ask first)</summary>

- Separate the ticket into three columns before you touch code: **observed**,
  **concluded**, **assumed**. Most tickets have one line in the first column and
  five in the other two.
- Start from the reported symptom and follow the data, not the file names. Ask:
  what path does an incoming order take before a fill exists?
- The worked example in
  [../reference/invariants.md](../reference/invariants.md#1-order-book-and-matching)
  is a ready-made reproduction. You do not have to invent a scenario.

</details>

<details>
<summary><strong>L2 - Method</strong> (which step you are skipping)</summary>

- If you have been reading code for 15 minutes with no failing reproduction, stop
  reading. Build the reproduction first. Everything is faster afterwards, including
  asking for help.
- A reproduction is only useful if it fails **for the reported reason**. Check
  that the value you assert on is the value the desk complained about.
- If you are in an Agent session and unsure what changed, you have lost
  supervision. Reset and restart with a narrower instruction rather than continuing
  to steer a session you no longer understand.
- Ask "which invariant does this violate?" before "what is the fix?". The
  invariant tells you what the test must assert.

</details>

<details>
<summary><strong>L3 - Structure</strong> (the shape of a good result)</summary>

A complete result contains:

1. A reproduction that fails before, with the observed and expected values written
   next to each other.
2. The invariant identifier, from
   [../reference/invariants.md](../reference/invariants.md).
3. A change whose diff you can justify file by file.
4. A regression test that asserts the **invariant**, not the specific line you
   changed - it should still be meaningful after a future refactor.
5. A handover: what the customer saw, which rule was broken, what changed, blast
   radius, and the three-part uncertainty sentence.

If your regression test would still pass with the change reverted, it is not a
regression test.

</details>
