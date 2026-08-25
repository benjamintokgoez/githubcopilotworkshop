# Elective 5B - CLI permissions and confinement

**Block:** 15:00-15:35 (35 minutes) - **Scenario:** `elective-cli`
**Parent:** [Lab 5 - Elective](lab_05_elective.md)

---

## Outcome

You design and test one GitHub Copilot CLI permission policy, distinguish tool
availability from approval and confinement, and state the residual blast radius.
Installing, authenticating, or enabling experimental sandbox features is not
part of the block.

Work in `workshop/scenarios/elective-cli/work/`. The no-live route is in
`workshop/fallbacks/elective-cli/`.

## Route decision

| Delivery mode | Prerequisite | Evidence |
|---|---|---|
| **Captured** | None | Predicted verdicts, a trace through the supplied session, and a current policy mapping |
| **Live addition** | Copilot CLI already installed, authenticated, policy-enabled, and smoke-tested by T-72 | Baseline prompts plus one explicit allow/deny change and one negative request |
| **Follow-up** | Approved preview use | Evaluate local or cloud sandbox policy after the course |

The captured transcript is a synthetic risk case, not executable CLI
configuration. Its `python -m pytest *` notation illustrates an argument scope
that became too broad. Translate the case into the current documented
`Kind(argument)` permission model; do not copy that line into settings.

---

## Understand/Plan (5 minutes)

Current Copilot CLI has separate controls. Do not call all of them an allowlist.

| Control | What it does | Important boundary |
|---|---|---|
| `--available-tools` / `--excluded-tools` | Changes which tools the model can choose | A remaining shell tool may still perform many effects |
| `--allow-tool` / `--deny-tool` | Auto-approves or blocks matching tool use; deny wins | An allowed command pattern may cover more arguments than intended |
| Path permissions | Gates access outside allowed directories | Shell path detection is heuristic, not a security boundary |
| URL permissions | Gates detected URLs and domains | Detection in shell text is incomplete |
| Trusted directory | Records that you trust the starting tree | It is not a sandbox and protection outside the tree is not guaranteed |
| Local/cloud sandbox | Constrains execution through a separate policy | Public preview; local sandbox is experimental and platform behavior varies |
| Hooks/managed settings | Can enforce organisation-defined decisions | They execute code and need their own review, rollout, and audit |

Read-only searches and file reads are normally approved automatically. Operations
that may modify state or access URLs normally require approval unless a saved or
command-line permission applies. Therefore the current default is not accurately
described as "deny every command."

Plan one task and answer:

1. Which tools must be visible to the model?
2. Which matching uses may run without a prompt?
3. Which uses must be denied rather than merely omitted?
4. Which filesystem, URL, credential, and working-directory risks remain?

### Current product boundaries - as of 2026-08-25

- GitHub Copilot CLI is **generally available** to Copilot subscribers. Business
  and Enterprise administrators can disable it.
- Command-line allow/deny flags apply to the current session. Saved
  location-scoped approvals live in `~/.copilot/permissions-config.json`; that
  file does not define deny rules, default modes, URL rules, tool filtering, or
  shared repository policy. Permanent URL approvals instead enter
  `allowedUrls` in `~/.copilot/settings.json` and apply across sessions.
- `--allow-all-tools`, `--allow-all`/`--yolo`, and
  `/allow-all`/`/yolo` widen authority. Enterprise managed settings can block
  those bypass modes and require sandbox restrictions on supported clients;
  they are not repository configuration.
- The Copilot sandboxing surface is **public preview**. Both the local and cloud
  CLI sandbox experiences currently require experimental features. Local
  sandboxing is off by default, uses lighter-weight OS isolation, and does not
  make every in-process file operation an OS-enforced boundary.
- Current Copilot CLI documentation notes limitations in support for
  organisation-level MCP server policies. Do not assume an IDE policy has the
  same effect in the CLI; verify the supported surface.

Official references:

- <https://github.blog/changelog/2025-10-28-github-copilot-cli-is-now-generally-available/>
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools>
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/configure-copilot-cli>
- <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference>
- <https://docs.github.com/en/copilot/concepts/about-cloud-and-local-sandboxes>
- <https://docs.github.com/en/copilot/reference/enterprise-administrators/enterprise-managed-settings>

---

## Implement/Test (13 minutes)

### Captured mode

1. In `fixtures/repo_safe_task.md`, record your verdicts **before** reading the
   transcript.
2. Read `fixtures/cli_session_transcript.md` as an event trace. For each requested
   action, record:
   - whether the model needed that capability,
   - whether the action should be `allow`, `ask`, or `deny`,
   - which current control could express that decision,
   - what remains outside that control.
3. In `work/permission_policy.md`, write at least three rules. Use current
   permission pattern terminology and label the evidence `captured`.
4. Identify the transcript event that exceeded its intended scope and rewrite the
   policy decision without claiming you executed it.

### Optional live addition

Start only from this repository, with no production credentials in the
environment. Use the repository-safe task. Capture the baseline approvals, then
restart with one narrow availability or permission change taken from the current
CLI help/reference. Re-run the same task and record exactly which prompt or
refusal changed.

Do not use an allow-all option, persist a broad approval, install a package, or
enable preview sandboxing for this exercise.

**Cut at 15:18:** stop refining patterns. The policy and before/after or captured
trace are now the deliverables.

---

## Review: test the boundary (7 minutes)

Use one safe negative request: a file write, a network request to the supplied
invalid domain, or `git push`. Do not perform a destructive action merely to test
a deny rule.

For live work, record whether the CLI removed the tool, denied it, asked, or
allowed it. For captured work, apply your written policy to an event that lies
outside it and show the rule evaluation step by step. Label that result
**policy-traced**, not live.

Then identify a bypass category your policy does not solve, such as:

- an allowed shell command with harmful arguments,
- a path or URL hidden from heuristic detection,
- credentials already available to a permitted process,
- hostile repository content influencing the model,
- inadequate audit retention.

---

## Explain (4 minutes)

Complete `work/permission_policy.md` with:

- the unmatched-action default,
- tool availability versus permission rules,
- the broadest grant and its argument scope,
- the negative result and evidence route,
- laptop versus shared/CI posture,
- the audit record and approval owner.

### Role lens

- **Developer:** Can you predict whether the next requested action will run,
  prompt, or fail?
- **Architect/security owner:** Can you enforce the policy across clients and
  runners, retain evidence, and prevent users from selecting an allow-all mode?

---

## Business invariant at stake

**An agent's authority is an environment property, not a personal preference.**
On a shared or CI machine, anything the user account, credentials, network, and
filesystem can reach may be in the blast radius.

Traceability (Nachvollziehbarkeit) matters too: if an agent changed something,
you need a durable record of what ran and which policy applied. See
[reference/dach_conventions.md](reference/dach_conventions.md#4-works-council-and-organisational-governance).

---

## Evidence and acceptance

See the [shared acceptance list](lab_05_elective.md#shared-acceptance), plus:

Supported completes the first three branch items and one policy-traced negative
event, then records the actual verifier result. Core completes every item below
and requires the structural verifier to pass.

- [ ] Evidence is labelled live or captured
- [ ] Tool visibility, permission, path/URL gates, and sandboxing are not treated
      as interchangeable
- [ ] At least three allow/ask/deny decisions include blast radius
- [ ] The negative case is observed live or traced through the written policy
- [ ] One sentence states why trusted directories and permission patterns are not
      complete confinement

---

## Solo path

Use the captured route. Make verdicts before opening the transcript, then compare,
write the current policy mapping, and trace the negative case. This produces a
reviewable artifact without pretending that the CLI or a sandbox ran.

---

## Reflection and retrieval

1. Which rule is broader because of its arguments rather than its command name?
2. What is the difference between hiding a tool, denying it, asking for approval,
   and sandboxing its process?
3. Could you reconstruct tomorrow what ran, under which saved and managed
   settings?

---

*Back to [Lab 5](lab_05_elective.md). Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
