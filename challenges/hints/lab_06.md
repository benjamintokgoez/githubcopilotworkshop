# Hints - Lab 6 (capstone)

These hints support the loop without prioritising a claim, prescribing code
structure, giving a solution, or naming a test.

<details>
<summary><strong>L1 - Frame the evidence</strong> (take at 15:55 without a bounded plan and first check)</summary>

- Make four columns: requested behaviour, source of the claim, evidence that
  would confirm or reject it, and explicit non-goal.
- Treat the issue, acceptance document, sample data, and checks as separate
  evidence. Record any disagreement before deciding what to trust.
- Mark every boundary where a value changes meaning or representation. Ask what
  must remain true on each side.

</details>

<details>
<summary><strong>L2 - Recover a vertical slice</strong> (take at 16:05 without a passing slice)</summary>

- Choose one observable acceptance behaviour. Run its narrowest available check,
  make the smallest related change, and run that check again.
- When a check passes, state what it rules out and what it does not cover.
- Read the current diff before starting another behaviour. Remove anything you
  cannot connect to acceptance.
- If five minutes pass without new evidence, narrow to Supported and record the
  first unresolved failure instead of broadening the change.

</details>

<details>
<summary><strong>L3 - Finish safely</strong> (take at 16:17 and finish)</summary>

- At 16:17, stop adding behaviour even if a check still fails.
- Make the handover usable: task and invariant, claim checked and evidence,
  command and observed result, files changed and non-goals, then the three-part
  uncertainty sentence.
- For a partial result, say exactly which behaviour is complete and which is
  next. Do not turn a failing full check into a success-shaped summary.
- Use the private rubric before the final check. Run the full verifier once,
  record the result, and reset so the
  archive preserves the attempt.

</details>
