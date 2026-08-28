# Brief - Copilot CLI permissions and confinement (elective 5B)

A terminal agent can read files, run commands, and change state. The useful
question is which action is visible, auto-approved, denied, path/URL-gated, or
confined - and what remains reachable through the user account.

**Default route:** captured/offline. No CLI installation or authentication is required.
Use live evidence only when Copilot CLI was ready before Lab 5.

## Material

| File | Purpose |
|---|---|
| `fixtures/repo_safe_task.md` | A decision worksheet to complete before seeing events |
| `fixtures/cli_session_transcript.md` | Synthetic captured events with approvals, denials, and an over-broad argument scope |
| `work/permission_policy.md` | Your current allow/ask/deny policy and evidence |

The transcript's wildcard line is risk notation, not current command-line syntax.
Its "deny-by-default" header describes that invented session posture, not the
product default. Translate the finding into the documented `Kind(argument)`
permission model.

## Controls to keep separate

| Control | Decision |
|---|---|
| `--available-tools` / `--excluded-tools` | What tools the model can choose |
| `--allow-tool` / `--deny-tool` | Which matching uses are auto-approved or blocked; deny takes precedence |
| Path and URL permissions | Whether detected paths or URLs need approval; shell detection is heuristic |
| Trusted directory | Whether you trust the starting tree; this is not confinement |
| Local/cloud sandbox | A separate preview execution boundary, not required here |
| Hooks and managed settings | Organisation automation and policy, requiring separate deployment evidence |

Read-only search and file operations are normally allowed automatically. Other
actions may prompt unless a session flag or saved approval applies. Do not
describe the product default as "deny every command."

## 29-minute working task

| Time | Work | Evidence |
|---|---|---|
| 5 min | Choose route, unmatched-action default, and required tool surface | Decision plan |
| 13 min | Complete pre-verdicts, then map captured events or run one live baseline/change | Policy plus positive trace |
| 7 min | Evaluate one safe out-of-policy request | Negative-case trace |
| 4 min | Write shared/CI posture and residual risk | Team-facing decision |

At minute 18, stop refining rules.

## Work sequence

1. Fill the verdict columns in `fixtures/repo_safe_task.md` before opening the
   transcript.
2. For each event, record the required capability, verdict, current control, and
   blast radius.
3. Write at least three rules in `work/permission_policy.md`. State the command
   argument scope; a tool name alone is incomplete.
4. Identify the transcript event that exceeded intended scope. Rewrite the policy
   decision using current terminology without claiming it ran.
5. Trace one file-write, invalid-domain network request, or remote-write request
   through the policy. Label a captured/offline evaluation `policy-traced`, not live.
6. State what permissions do not confine: permitted shell effects, heuristic
   path/URL detection, available credentials, hostile input, and audit retention
   are separate questions.

## Current product status - as of 2026-08-25

- Copilot CLI is generally available to Copilot subscribers and can be disabled
  by Business or Enterprise policy.
- Command-line allow/deny options apply to the current session. Location-scoped
  saved approvals are stored in `~/.copilot/permissions-config.json`; that file
  does not carry deny/default/URL/tool-filtering/shared-repository policy.
  Permanent URL approvals instead enter `allowedUrls` in
  `~/.copilot/settings.json` and apply across sessions.
- Enterprise managed settings can disable bypass/YOLO-style modes and require
  sandbox restrictions on supported clients.
- The sandboxing surface is public preview. Both local and cloud CLI sandbox
  experiences currently require experimental features. Local sandboxing is off
  by default and is lighter-weight OS isolation; its platform requirements and
  in-process tool limits matter.
- Copilot CLI documentation identifies limitations for organisation-level MCP
  server policies. Verify policy coverage per client.

References:

- <https://github.blog/changelog/2025-10-28-github-copilot-cli-is-now-generally-available/>
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools>
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/configure-copilot-cli>
- <https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-config-dir-reference>
- <https://docs.github.com/en/copilot/concepts/about-cloud-and-local-sandboxes>
- <https://docs.github.com/en/copilot/reference/enterprise-administrators/enterprise-managed-settings>

## Live-route safety

- Use only this training checkout and remove production credentials from the
  environment.
- Do not use allow-all/YOLO, persist a broad approval, install a package, or
  enable preview sandboxing during the block.
- A safe negative test requests an action and records the refusal; it does not
  perform a destructive action.
