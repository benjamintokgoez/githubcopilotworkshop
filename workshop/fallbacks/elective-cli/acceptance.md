# Acceptance - elective-cli

```bash
python scripts/workshop.py verify elective-cli
```

reads `work/permission_policy.md` and checks that:

| Requirement | Field or section |
|---|---|
| The evidence is labelled live or captured | `- Evidence source:` |
| A default posture is stated, and it is a posture rather than a mood | `- Default posture:` |
| At least three rules exist | `### Rule` blocks |
| Each rule has a command, a verdict of `allow`/`ask`/`deny`, a reason, and a blast radius | fields inside each rule block |
| The broadest entry is identified honestly | `- Broadest entry I wrote:` |
| The negative case was run and recorded as observed | `- What I asked for outside the policy:` and `- Observed behaviour:` |
| The boundary of the control is named | `## 4. What an allowlist does not protect against` |
| The shared-machine and CI case is considered | `## 5. Shared machines and CI` |

## What it does not check

Whether a terminal agent is installed, whether your rules are the right ones, or
whether your team would agree with them. A policy that says "deny everything" and
defends it is a valid result; so is discovering that the mechanism cannot enforce
half of what you wrote down. Say which half.

## Restore

```bash
python scripts/workshop.py reset elective-cli
```
