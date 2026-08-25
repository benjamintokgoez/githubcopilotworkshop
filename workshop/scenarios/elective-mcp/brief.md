# Brief - secure MCP context (elective 5A)

You are deciding what an assistant may reach on your behalf. The mechanism is
MCP; the transferable work is data minimisation, process confinement, tool
capability, upstream authorization, and evidence.

**Default route:** captured/local. No live server, registry entry, authentication,
or network access is required. A live call is optional and only for a server
approved and tested before this block.

## Material

| File | Purpose |
|---|---|
| `fixtures/tool_inventory.md` | QuantCore's actual server capability and the layer for each control |
| `fixtures/mcp_config_sample.json` | A current but deliberately broad VS Code local stdio configuration |
| `fixtures/config_notes.md` | Documented VS Code fields and the sandbox approval trade-off |
| `fixtures/tool_call_log.md` | Captured positive and negative events |
| `work/mcp_config_reduced.json` | Configuration proposal to reduce |
| `work/permission_inventory.md` | Evidence trace and platform decision |

## 29-minute working task

| Time | Work | Evidence |
|---|---|---|
| 5 min | Separate enterprise/client, host process, client approval, and server/upstream controls | Four-layer plan |
| 13 min | Reduce the configuration and trace captured or live events | Edited configuration plus positive trace |
| 7 min | Trace one failed request to the enforcing layer | Negative-case record |
| 4 min | Write the platform-team paragraph | Owner, non-goals, and next decision |

At minute 18, stop changing configuration. Finish the trace and explanation.

## Work sequence

1. **Inventory capability before intent.** For each tool, record maximum data and
   side-effect reach. Include the server process's working directory,
   environment, filesystem, and network reach.
2. **State the approval and confinement boundary.** Record the per-call approval
   and host process-confinement assumptions. Treat the edited policy as a
   proposal unless that exact client/version was preflight-tested.
3. **Reduce the process.** Remove environment, development, filesystem, or network
   access the server does not need. Defend each retained grant.
4. **Trace evidence.** For each event, distinguish tool selection, user approval,
   process sandboxing, server registration, server input validation, and upstream
   authorization. The capture proves only the layers it exercised.
5. **Test or trace one negative case.** An unknown tool and an invalid argument
   fail at different server layers. A sandbox prediction is not an observed
   sandbox denial.
6. **Write the governance decision.** State data flow, policy owner, operating
   system limitation, residual risk, and what would be monitored.

## Current product status - as of 2026-08-25

- GitHub MCP Registry discovery is public preview.
- GitHub documents enterprise `managed-settings.json` MCP allowlists as generally
  available and more strongly enforced than private-registry restriction.
- GitHub MCP Server toolsets reduce the offered surface. Its `--read-only` mode
  removes write tools. Neither is upstream authorization.
- `managed-settings.json` allowlists are the GA enterprise reference for
  supported IDE/CLI clients. Private registries are preview and weaker
  enforcement. Cloud-agent MCP uses separate repository/custom-agent
  configuration and is not governed by that client registry boundary.
- VS Code documents `sandboxEnabled` plus top-level filesystem/network rules for
  local stdio servers on macOS and Linux. Enabling it auto-approves tool
  confirmations, so it trades per-call prompts for standing policy rules. That
  host confinement is not server authorization and is not portable to every
  MCP client.

References:

- <https://docs.github.com/en/copilot/concepts/context/mcp>
- <https://docs.github.com/en/copilot/concepts/mcp-management>
- <https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/configure-toolsets>
- <https://github.com/github/github-mcp-server#read-only-mode>
- <https://code.visualstudio.com/docs/agent-customization/mcp-servers>
- <https://code.visualstudio.com/docs/agents/reference/mcp-configuration>

## Design checks

- A tool never registered cannot be selected by mistake.
- Tool selection and annotations are not server authorization.
- The process receives every environment value you pass, whether a tool uses it
  or not.
- Model-supplied arguments require server-side validation.
- Valid but excessive output is still a data-minimisation failure.
- A record of tool, arguments, result, approval route, and policy version is
  needed for traceability.

If policy blocks MCP, do not work around it. Record the policy owner, complete the
configuration review and captured trace, and label the result accurately.
