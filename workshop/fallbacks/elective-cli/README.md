# Offline fallback - elective-cli (Lab 5B)

Everything needed for the terminal-agent permissions elective without installing
an agent and without network access.

## Inventory

| File | What it is |
|---|---|
| `brief.md` | The task and the three questions the policy has to answer |
| `fixtures/cli_session_transcript.md` | A captured session: two denials, two auto-approvals, and an allowlist entry broader than it looked |
| `fixtures/repo_safe_task.md` | A read-only task with a verdict column to fill in before you see the transcript |
| `acceptance.md` | What the evidence check looks for |
| `staged_copy/permission_policy.md.txt` | Byte-identical copy of the policy template |
| `captured_acceptance_output.txt` | A captured run of the evidence check against the untouched template |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working without the tooling

1. Fill in the verdict column of `fixtures/repo_safe_task.md` **before** reading
   the transcript. Guessing after the fact is not a policy exercise.
2. Read `fixtures/cli_session_transcript.md` and compare it against your verdicts.
   The entry added at `13:24:02` and its consequence at `13:27:03` are the point
   of the transcript.
3. Copy `staged_copy/permission_policy.md.txt` somewhere you can edit and complete it,
   labelling your evidence as captured.

## If you do have an agent installed

Run the task in `fixtures/repo_safe_task.md` for real, in this checkout, with
deny-by-default permissions, and label your evidence as live. Do not run it in a
directory with production credentials in the environment, and do not allowlist a
broad shell entry to save time.

*Synthetic capture. No credentials, no private hosts, and no real session history
appear in this directory.*
