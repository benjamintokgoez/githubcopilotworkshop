# Offline fallback - elective-cli (Lab 5B)

This is the captured/offline mode for Copilot CLI permission analysis. It requires no
installation, authentication, or network access and still produces a policy,
positive event trace, and negative-case evaluation.

## Inventory

| File | What it is |
|---|---|
| `brief.md` | The task, current control layers, and product status |
| `fixtures/cli_session_transcript.md` | A synthetic risk trace whose wildcard wording is not current configuration syntax |
| `fixtures/repo_safe_task.md` | A read-only task with a decision worksheet to complete before seeing the transcript |
| `acceptance.md` | What the evidence check looks for |
| `staged_copy/permission_policy.md.txt` | Byte-identical copy of the policy template |
| `captured_acceptance_output.txt` | A captured run of the evidence check against the untouched template |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working mode

1. Copy `staged_copy/permission_policy.md.txt` into a directory you can edit.
2. Fill every decision in `fixtures/repo_safe_task.md` before opening the
   transcript.
3. Map each captured event to current controls: tool availability, tool
   permission, path/URL gate, human approval, or sandbox.
4. Translate the transcript's abstract wildcard risk into the current
   `Kind(argument)` model. Do not copy the transcript notation as configuration.
5. Trace one out-of-policy event through your rules, label the delivery mode
   `captured/offline`, and label the result `policy-traced`.
6. Complete the shared/CI posture, residual risk, and audit evidence.

Merely reading the capture is not the fallback outcome.

## If you do have an agent installed

Use a live route only when Copilot CLI was installed, authenticated, and
policy-enabled before the block. Run the task in this checkout, capture the
default approval behavior, and test one narrow current permission change. Do not
use allow-all/YOLO, persist a broad approval, enable an experimental sandbox, or
run with production credentials in the environment.

*Synthetic capture. No credentials, no private hosts, and no real session history
appear in this directory.*
