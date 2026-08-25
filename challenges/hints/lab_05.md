# Hints - Lab 5 (electives)

Use one level at a time. These prompts help you inspect your own evidence; they
do not provide configuration values or a finished policy.

**Time recovery:** at 15:18, stop adding controls. Move to the supplied capture
if necessary, then complete the negative case and explanation. A labelled
captured result is stronger than an unfinished live claim.

Use L1 at 15:06 if the control/evidence boundary is not written, L2 at 15:12 if
no positive trace exists, and L3 at 15:18 to finish. The same gates apply to all
three branches.

## 5A - Secure MCP context

<details>
<summary><strong>L1 - Re-orient</strong></summary>

- Write four headings before looking at settings: enterprise/client, host
  process, client tool approval, and server/upstream.
- Put every control you plan to claim under exactly one heading. Which heading is
  empty, and is that intentional?
- Mark every evidence sentence `observed`, `captured`, or `predicted`.

</details>

<details>
<summary><strong>L2 - Diagnose</strong></summary>

- Follow one successful call from model selection to returned data. At which
  steps could it have been stopped?
- Follow one failed call. What error distinguishes a missing tool, invalid input,
  sandbox refusal, client denial, and upstream authorization failure?
- Compare process reach with tool reach. Which is larger?

</details>

<details>
<summary><strong>L3 - Evidence frame</strong></summary>

```text
Route and platform:
Server identity and transport:
Process reach:
Tool capability:
Positive event -> controlling layer -> evidence:
Negative event -> controlling layer -> evidence:
Predictions not run:
Residual risk:
Approval owner:
```

If two rows cite the same evidence for different layers, revisit the attribution.

</details>

## 5B - CLI permissions and confinement

<details>
<summary><strong>L1 - Re-orient</strong></summary>

- Separate "the model cannot see this tool" from "the tool is visible but cannot
  run" and "the tool can run only after a prompt."
- For captured work, fill the verdict column before opening the transcript.
- Name the directory, credentials, network, and user account in the blast radius.

</details>

<details>
<summary><strong>L2 - Diagnose</strong></summary>

- Take the broadest rule and vary only its arguments. Does your reasoning still
  produce the same verdict?
- For a shell request, ask which control evaluates the tool name, command,
  filesystem path, URL, and process environment. Do not assign all five to one
  flag.
- Check whether the evidence is a live refusal or a policy trace. Label it before
  drawing a conclusion.

</details>

<details>
<summary><strong>L3 - Evidence frame</strong></summary>

```text
Evidence route:
Unmatched-action default:
Tool visibility decision:
Permission decision:
Path/URL decision:
Broadest grant and argument scope:
Negative request -> evaluation -> result:
Confinement not provided by this policy:
Shared/CI difference:
Audit evidence:
```

A rule that says only "safe commands" or "read-only" needs another pass.

</details>

## 5C - Customization

<details>
<summary><strong>L1 - Re-orient</strong></summary>

- Keep the task exactly the same before and after.
- State whether the draft was explicitly attached, scored locally, or
  automatically discovered. These are different claims.
- Give each rule one scope and one reviewer-visible check.

</details>

<details>
<summary><strong>L2 - Diagnose</strong></summary>

- For each rule, write one output that passes and one that fails. If both are
  plausible, make the rule more specific.
- Ask whether the rule applies to most repository work, one path, one repeatable
  task, or one person's preferences.
- For the contradiction case, identify what would make the result deterministic:
  test, lint, CI, permission, review, or hook.

</details>

<details>
<summary><strong>L3 - Evidence frame</strong></summary>

```text
Route and exact task:
Before measure:
After measure:
Rule -> scope -> reviewer check -> failure impact:
Rule removed or rewritten -> evidence:
Contradiction -> observed or analysed result:
Deterministic control still needed:
Discovery claim you did not test:
Owner and review date:
```

If the "after" is only longer, you have measured volume rather than quality.

</details>
