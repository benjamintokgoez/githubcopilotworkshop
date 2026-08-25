# Hints - Lab 4 (reviewing work you did not write)

Open only the next level you need. These hints restore review method without
identifying a finding or location.

<details>
<summary><strong>L1 - Orientation</strong> (take at 14:07 without two candidate concerns)</summary>

- Close the pull request description, session transcript, review thread, and
  automated review. Start with the issue and diff.
- Write three lines: requested outcome, explicit exclusions, and files changed.
  Compare those sets before reading any explanation.
- In a pair, one person calls the concern and the other asks, "What line and what
  rule support that?" Solo, write the answer before assigning severity.
- If it is already 14:19, stop searching. Select the strongest two findings and
  make their evidence and requested changes complete.

</details>

<details>
<summary><strong>L2 - Method</strong> (turn an observation into a finding)</summary>

- Review by concern rather than top-to-bottom: scope, contract or invariant,
  tests, non-functional behaviour, then explanation.
- Evidence needs both sides: what the issue or invariant requires, and what the
  changed line does. A conclusion without that comparison is not yet a finding.
- Ask whether a changed test became more precise, changed because the contract
  changed, or merely stopped detecting the old failure.
- Use the session transcript to understand decisions and abandoned attempts. It
  cannot prove that final code is correct or that a stated command tested the
  right contract.
- Severity follows impact and merge decision, not confidence of wording.

</details>

<details>
<summary><strong>L3 - Recovery</strong> (complete the review without an answer key)</summary>

Use this compact structure:

```text
Finding N
  Location: exact file and hunk
  Severity: blocking | should-fix | nit
  Evidence: required rule + observed change + consequence
  Requested change: observable outcome

Automated comparison
  useful comment I missed + why
  material concern it missed + why
  comment I would suppress + why

Decision
  approve | request changes
  condition that would reverse the decision
```

At 14:22, open the captured automated review even if your list is short. At
14:28, stop analysis and run the structural verifier. Do not add invented
evidence to make it green; record the gap and reset at 14:35.

</details>
