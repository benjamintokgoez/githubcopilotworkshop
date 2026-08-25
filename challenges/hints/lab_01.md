# Hints - Lab 1 (operator model)

Take the smallest hint that unblocks you. Stopping after L1 is a better outcome
than reading all three.

<details>
<summary><strong>L1 - Orientation</strong> (take after 3 minutes without a claim)</summary>

- You are not looking for a defect. You are looking for **claims**: sentences in
  the explanation that are either true or false about this code.
- Ask for the computation path and its sign, unit, scaling, and boundary
  conventions. Avoid "is this correct?"; it invites a conclusion instead of
  evidence.
- A claim you can check in two minutes is worth more than a claim that is more
  interesting.
- No live response? Use the offline statement in the lab. Product access is not
  the learning objective.

</details>

<details>
<summary><strong>L2 - Method</strong> (take after 8 minutes without evidence)</summary>

- If you are stuck, you are probably still in Ask and have not moved to
  verification. Close or collapse the response and work from the claim alone.
- Turn one claim into a yes/no question with an observable answer. Match it to
  the relevant invariant, reuse that invariant's reference inputs, and compare
  the observed value or code path with the documented convention.
- A precise line reference is valid evidence when execution is unavailable. An
  uncited restatement by the assistant is not.

</details>

<details>
<summary><strong>L3 - Structure</strong> (take at 14 minutes and finish)</summary>

Use this evidence shape; it contains no expected answer:

```
Claim 1: <statement>  -> verified by: <command or line reference> -> holds / does not hold
Claim 2: <statement>  -> verified by: <command or line reference> -> holds / does not hold
Claim 3: <statement>  -> not verified, because <time / missing evidence / missing knowledge>

I verified ...
I assumed ...
It could still be wrong if ...
```

Supported lane: complete one verified claim, one open claim, and the uncertainty
sentence. Core: complete all three lines. If a claim does not hold, record the
contradiction and move on; this lab does not change code.

</details>
