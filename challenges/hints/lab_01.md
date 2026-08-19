# Hints - Lab 1 (operator model)

Take the smallest hint that unblocks you. Stopping after L1 is a better outcome
than reading all three.

<details>
<summary><strong>L1 - Orientation</strong> (where to look, what to ask first)</summary>

- You are not looking for a defect. You are looking for **claims**: sentences in
  the explanation that are either true or false about this code.
- Good first question shape: "How does this module compute its result, and what
  sign and scaling conventions does it use?" Not "is this correct?"
- A claim you can check in two minutes is worth more than a claim that is more
  interesting.

</details>

<details>
<summary><strong>L2 - Method</strong> (which step you are skipping)</summary>

- If you are stuck, you are probably still in Ask and have not moved to
  verification. Verification means running something or reading the specific lines
  the claim is about.
- Turn each claim into a yes/no question with an observable answer. "Vega is
  scaled per percentage point" becomes "does the returned vega match `0.391043`
  for the reference inputs?"
- The reference inputs and expected values are in
  [../reference/invariants.md](../reference/invariants.md). Use them instead of
  inventing your own.

</details>

<details>
<summary><strong>L3 - Structure</strong> (the shape of a good answer)</summary>

A complete Part B result looks like this:

```
Claim 1: <statement>  -> verified by: <command or line reference> -> holds / does not hold
Claim 2: <statement>  -> verified by: <command or line reference> -> holds / does not hold
Claim 3: <statement>  -> not verified, because <time / missing evidence / missing knowledge>

I verified ...
I assumed ...
It could still be wrong if ...
```

If a claim does not hold, write it down and move on. Lab 2 is where changes start.

</details>
