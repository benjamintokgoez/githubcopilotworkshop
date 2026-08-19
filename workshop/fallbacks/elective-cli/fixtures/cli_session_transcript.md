# Captured terminal-agent session

Synthetic capture of a read-only task run in a checkout of this repository, with
deny-by-default permissions. Timestamps are UTC. No credentials, no private
hosts, and no real repository other than this one appear in it.

---

```
2026-08-19T13:20:04Z  session.start   cwd=<repo> approvals=ask-every-command
2026-08-19T13:20:04Z  task            "Summarise how a risk metric reaches the API response, and
                                       name where the sign convention is enforced."

2026-08-19T13:20:11Z  request         run: rg -n "value_at_risk|var" --type py
                      reason          "locate the risk calculation and its consumers"
2026-08-19T13:20:19Z  approval        granted by user
2026-08-19T13:20:19Z  result          exit=0 lines=64

2026-08-19T13:20:33Z  request         read: qxm/risk/var.py
2026-08-19T13:20:35Z  approval        granted by user
2026-08-19T13:20:35Z  result          exit=0 bytes=9214

2026-08-19T13:21:02Z  request         run: python -m pytest tests/test_risk_v2.py -q
                      reason          "confirm the documented values still hold"
2026-08-19T13:21:09Z  approval        granted by user
2026-08-19T13:21:31Z  result          exit=0 duration_s=21 "24 passed"

2026-08-19T13:22:40Z  request         run: git stash --include-untracked
                      reason          "clean the tree before comparing behaviour"
2026-08-19T13:22:44Z  approval        DENIED by user
2026-08-19T13:22:44Z  agent           "Understood. I will compare without changing the working tree."

2026-08-19T13:24:02Z  config.change   user added allowlist entry: "python -m pytest *"
2026-08-19T13:24:02Z  note            subsequent pytest invocations run without a prompt

2026-08-19T13:25:16Z  request         run: python -m pytest tests/ -q --maxfail=1
2026-08-19T13:25:16Z  approval        auto (matched allowlist entry "python -m pytest *")
2026-08-19T13:25:58Z  result          exit=0 duration_s=42

2026-08-19T13:27:03Z  request         run: python -m pytest tests/ -q -p no:cacheprovider
                                      --rootdir=/ --co -q
2026-08-19T13:27:03Z  approval        auto (matched allowlist entry "python -m pytest *")
2026-08-19T13:27:04Z  note            the entry matched a command that reaches outside the working
                                      directory; the wildcard grants arguments, not just the command

2026-08-19T13:28:40Z  request         run: curl -s https://example.invalid/health
                                      reason "check whether the service is reachable"
2026-08-19T13:28:44Z  approval        DENIED by user
2026-08-19T13:28:44Z  agent           "Understood. I will not make network calls."

2026-08-19T13:31:12Z  session.end     duration_s=668 commands=7 approved=5 denied=2 auto=2
```

---

## What to notice

- The denial at `13:22:44` cost nothing. The agent continued without the thing it
  asked for, which is the normal case and the reason denying is cheap.
- The allowlist entry added at `13:24:02` looked narrow and was not. It granted a
  command **with any arguments**, and at `13:27:03` those arguments reached
  outside the working directory. This is the most valuable finding in the
  transcript.
- Two commands were auto-approved. Nobody read them. That is what "convenience"
  costs, and it is a decision, not a default of nature.

*Synthetic capture, written for the workshop.*
