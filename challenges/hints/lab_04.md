# Hints - Lab 4 (reviewing work you did not write)

<details>
<summary><strong>L1 - Orientation</strong> (where to look first)</summary>

- Compare the diff against the **issue**, not against the pull request
  description. The description is the thing under review.
- Count the files. Then ask: which of these does the issue actually require? Scope
  findings are usually the fastest to establish and the most useful to the author.
- Read the tests in the diff before the implementation. Tests reveal what the
  author believed the task was.

</details>

<details>
<summary><strong>L2 - Method</strong> (which step you are skipping)</summary>

- If you are reviewing line by line from the top, you will run out of time before
  the important part. Review by concern: scope, then invariants, then tests, then
  contracts, then non-functional.
- For anything numeric, check the **convention**, not the arithmetic: sign, unit,
  scaling, timezone, separator. Generated code gets arithmetic right far more often
  than it gets conventions right.
- A test that was changed in the same diff as the behaviour it covers deserves a
  specific question: was it corrected, or was it weakened?
- If you cannot explain why a change works, that is a finding about the change, not
  about you.

</details>

<details>
<summary><strong>L3 - Structure</strong> (the shape of a good review)</summary>

```
Summary (3 sentences, for a busy author):
  What this change does, what it should do, and the decision.

Blocking:
  [file:line] <finding> - evidence: <what you ran or read> - requested: <specific change>

Should fix:
  [file:line] ...

Nits (optional, marked as such):
  ...

Decision: approve / request changes
Condition that would flip it: <one sentence>
```

Rules of thumb: every blocking item needs evidence; severity is a judgement you
must be able to defend; and "please explain this" is a legitimate blocking item
when traceability matters.

</details>
