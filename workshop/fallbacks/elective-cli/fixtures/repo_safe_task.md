# A repository-safe task

Use this as the task you give the agent, or as the task you work through by hand
from the captured transcript. It is read-only, needs no credentials, and touches
nothing outside this checkout.

## The task

> Summarise how overdue service hours reach the API response in this repository, and
> name the place where its sign convention is enforced. Do not change any file.

## Decision worksheet

Complete every blank **before** opening the transcript. A policy invented after
seeing an event is an explanation, not a preventive control.

| Requested action | Reach or effect | Needed for this task? | `allow` / `ask` / `deny` | Current control and argument scope |
|---|---|---|---|---|
| `rg -n "<pattern>" --type py` | Reads matching source under the working directory | | | |
| Read one named file | Reads its full contents | | | |
| `python -m pytest tests/test_analytics_v2.py -q` | Executes repository code in the current environment | | | |
| A pytest command with different arguments or root | May execute or collect code beyond the intended test | | | |
| `git status` | Reads repository state | | | |
| `git stash` | Changes the working tree and index | | | |
| `git push` | Changes a remote repository | | | |
| `curl <url>` | Reaches a network destination | | | |
| `pip install <package>` | Changes the environment and executes package installation code | | | |
| `rm -rf <path>` | Deletes data reachable by the user account | | | |

For the last column, distinguish tool availability, tool permission, path/URL
approval, and sandbox policy. More than one layer may apply.

## Rules while you work

- Before approving anything, say out loud what the command will do. If you
  cannot, deny it. The habit is the deliverable, not the outcome of any one
  approval.
- Note which command or argument pattern you were tempted to widen and why.
- Do not run this in a directory that has production credentials exported.
- In the captured route, trace a request through your policy and label the result
  captured. Do not report it as a live CLI refusal.
