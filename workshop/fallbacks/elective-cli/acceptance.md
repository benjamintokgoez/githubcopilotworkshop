# Acceptance - elective-cli

```bash
python scripts/workshop.py verify elective-cli
```

reads `work/permission_policy.md` and checks that:

| Requirement | Field or section |
|---|---|
| The delivery mode is labelled live or captured/offline | `- Evidence source:` |
| A default posture is stated, and it is a posture rather than a mood | `- Default posture:` |
| At least three rules exist | `### Rule` blocks |
| Each rule has a command, a verdict of `allow`/`ask`/`deny`, a reason, and a blast radius | fields inside each rule block |
| The broadest entry is identified honestly | `- Broadest entry I wrote:` |
| The negative case is labelled and evaluated | `- What I asked for outside the policy:` and `- Observed behaviour:` |
| The boundary of the control is named | `## 4. What an allowlist does not protect against` |
| The shared-machine and CI case is considered | `## 5. Shared machines and CI` |

The heading `## 4. What an allowlist does not protect against` is retained by the
staged template for verifier compatibility. In your content, use the more precise
terms tool availability, permission pattern, path/URL gate, and confinement.

## Evidence routes

- **Live:** record the baseline, one narrow permission or availability change,
  and the observed negative request.
- **Captured/offline:** make verdicts before reading the transcript, map captured events
  to current controls, and trace one event through your completed policy. Label
  the mode captured/offline and the result `policy-traced`.

Both routes require a written policy and a negative-case evaluation. Reading the
transcript without making and testing decisions is not completion.

The field label `Observed behaviour` is fixed by the staged template. Begin a
captured/offline result with `Policy-traced:`; reserve `Observed live:` for a CLI
request that actually ran or prompted.

## What it does not check

Whether a terminal agent is installed, whether your rules are the right ones, or
whether your team would agree with them. A policy that says "deny everything" and
defends it is a valid result; so is discovering that the mechanism cannot enforce
half of what you wrote down. Say which half. `verify` also cannot establish that
a live CLI, sandbox, saved approval, or managed setting ran; your evidence label
must do that.

## Restore

```bash
python scripts/workshop.py reset elective-cli
```
