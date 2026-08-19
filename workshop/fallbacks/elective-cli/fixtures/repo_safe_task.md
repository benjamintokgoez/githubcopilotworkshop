# A repository-safe task

Use this as the task you give the agent, or as the task you work through by hand
from the captured transcript. It is read-only, needs no credentials, and touches
nothing outside this checkout.

## The task

> Summarise how a risk metric reaches the API response in this repository, and
> name the place where its sign convention is enforced. Do not change any file.

## Commands a reasonable agent will want

Write your verdict next to each one **before** you see it asked for. That is the
exercise: a policy written under time pressure, mid-session, is not a policy.

| Command | What it can do | Your verdict |
|---|---|---|
| `rg -n "<pattern>" --type py` | Read source anywhere under the working directory | |
| `cat <file>` / `read <file>` | Read one file | |
| `python -m pytest tests/ -q` | Execute the test suite, which executes repository code | |
| `python -m pytest *` | Execute pytest **with any arguments**, including paths outside the repository | |
| `git status` | Read repository state | |
| `git stash` | **Change** your working tree | |
| `git push` | Change a remote | |
| `curl <url>` | Reach the network | |
| `pip install <package>` | Change the environment the agent runs in | |
| `rm -rf <path>` | Destroy data | |

## Rules while you work

- Before approving anything, say out loud what the command will do. If you
  cannot, deny it. The habit is the deliverable, not the outcome of any one
  approval.
- Note which entries you were tempted to widen and why. There is usually one.
- Do not run this in a directory that has production credentials exported.
