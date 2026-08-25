# Hints - Lab 2 (guided incident)

No hint level names a file, a function, or a fix. If you want the answer, the
honest move is to ask a human, and that is an allowed move.

<details>
<summary><strong>L1 - Orientation</strong> (take by 10:23 without a reproduction)</summary>

- Separate the ticket into three columns before you touch code: **observed**,
  **concluded**, **assumed**. Most tickets have one line in the first column and
  five in the other two.
- Start from the reported symptom and follow the data, not the file names. Ask:
  what path does an incoming order take before a fill exists?
- The worked example in
  [../reference/invariants.md](../reference/invariants.md#1-order-book-and-matching)
  is a ready-made reproduction. You do not have to invent a scenario.
- If execution is blocked, use the captured failing output and label it
  `captured`. You can still localise the path and review the next action.

</details>

<details>
<summary><strong>L2 - Method</strong> (take after a stable failure, before changing code)</summary>

- If you have been reading without a stable failure, stop opening new paths. Use
  the supplied scenario or captured output first.
- A reproduction is only useful if it fails **for the reported reason**. Check
  that the value you assert on is the value the desk complained about.
- Ask "which invariant does this violate?" before "what is the fix?". The
  invariant tells you what the test must assert.
- Before a repair, write one separate focused regression check. Keep the supplied
  acceptance artifact unchanged.
- If an editing session has changed more than you can explain, stop it, inspect
  the diff, and narrow the next action. At the phase cut, use the lab's
  `implement-test` resync route instead of rushing.

</details>

<details>
<summary><strong>L3 - Structure</strong> (take at 10:46 and finish the remaining loop)</summary>

Core evidence contains:

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

Supported evidence stops after a captured or live failure, invariant,
localization, one review finding, bounded next action, and honest handover. Do not
claim that unrun or failing acceptance passed.

</details>
