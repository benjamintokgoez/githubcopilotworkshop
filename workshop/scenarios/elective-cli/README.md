# Scenario: elective-cli (Lab 5B)

```bash
python scripts/workshop.py start elective-cli
python scripts/workshop.py verify elective-cli
python scripts/workshop.py reset elective-cli
```

| Path | What it is |
|---|---|
| `brief.md` | The task and the three questions the policy has to answer |
| `fixtures/cli_session_transcript.md` | Captured session: approvals, denials, and one entry that granted too much |
| `fixtures/repo_safe_task.md` | A read-only task for this repository, with a verdict column to fill in first |
| `acceptance.md` | What `verify` checks |
| `work/permission_policy.md` | Created by `start`: your allow / ask / deny policy |

No agent installation is required. If you have one, run the task live and label
your evidence as live; if you do not, the captured transcript carries the same
findings, including the allowlist entry that turned out to be broader than it
looked.
