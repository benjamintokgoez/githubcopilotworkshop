# Hints - Lab 3 (plan-driven migration)

Open only the next level you need. A hint should restore the method, not disclose
the migration.

<details>
<summary><strong>L1 - Orientation</strong> (recover scope and evidence)</summary>

- Stop editing. Read `issue.md`, `inventory.md`, and `acceptance.md` in that
  order.
- The baseline is not only the initial test output. Capture representative valid
  output and rejected-input behaviour through the public boundary before a code
  change.
- In a pair, ask the contract reviewer to state the file scope and the current
  stop time. Solo, write those two lines before continuing.
- If it is already 12:55 and no edited plan exists, take the Supported route:
  plan and verify one batch rather than rushing the whole migration.

</details>

<details>
<summary><strong>L2 - Method</strong> (recover a supervisable batch)</summary>

- Split by a dependency boundary that can be checked independently. If its diff
  cannot be read in two minutes or its check cannot run in five, split again.
- For every batch, write four lines before execution: files, intended contract,
  exact check, and rollback point.
- A task note becomes agent context only when you explicitly attach, reference,
  or hand it off. Do not assume every Markdown file is discovered automatically.
- Compare accepted and rejected behaviour. Happy-path output alone misses
  defaults, aliases, validation, and error translation.
- A proposed out-of-inventory edit is a question to investigate. It is never an
  automatic expansion of scope.

</details>

<details>
<summary><strong>L3 - Recovery</strong> (finish honestly when time is short)</summary>

Use this structure in `MIGRATION_NOTES.md`:

```text
Baseline:
  command and observed result
  valid public outputs
  rejected public inputs and error boundary

Plan edits:
  generated draft assumption -> my change -> risk removed

Batch N:
  files -> diff reviewed -> exact check -> observed result

Final state:
  verified complete / verified incomplete / not checked
  next bounded action
  I verified ... I assumed ... It could still be wrong if ...
```

At 13:16, start no new batch. At 13:26, stop editing and record the real verifier
result before reset. A useful incomplete handover is a Supported outcome; changing tests,
inventing evidence, or skipping reset is not.

</details>
