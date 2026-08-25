# Offline fallback - elective-mcp (Lab 5A)

This is the captured/local mode for secure MCP analysis. It needs no connected
server, registry entry, authentication, or network access. You still produce a
reduced configuration, a positive and negative event trace, and a governance
decision.

## Inventory

| File | What it is |
|---|---|
| `brief.md` | The task, the design rules, and why a policy blocker counts as a result |
| `fixtures/tool_inventory.md` | The tool surface of this repository's MCP server, and where each control lives |
| `fixtures/mcp_config_sample.json` | The over-broad starting configuration, in current VS Code MCP syntax |
| `fixtures/config_notes.md` | What each configuration key does, and the sandbox keys it is not using yet |
| `fixtures/tool_call_log.md` | A captured session: bounded results, a rejected argument, and a tool that does not exist |
| `acceptance.md` | What the evidence check looks for |
| `staged_copy/mcp_config_reduced.json.txt` | Byte-identical copy of the configuration to narrow |
| `staged_copy/permission_inventory.md.txt` | Byte-identical copy of the inventory template |
| `captured_acceptance_output.txt` | A captured run of the evidence check against the untouched template |

> The files in `staged_copy/` carry a trailing `.txt` so that a checkout never
> contains half-finished code that linting or test collection would pick up.
> Drop that suffix when you copy them into your working directory.

## Working mode

1. Copy the two files from `staged_copy/` into a directory you can edit.
2. In five minutes, separate process, client, server, and upstream controls.
3. Reduce the configuration using documented keys. State approval and
   confinement assumptions, and label the unrun policy proposed.
4. Trace at least three events in `fixtures/tool_call_log.md` to their controlling
   layers. Include one successful result and one refusal.
5. Mark any sandbox behavior not shown in the capture as predicted.
6. Complete the inventory and platform paragraph. Label the evidence captured.

The captured trace proves server registration and argument validation. It does
not prove that your edited sandbox rules ran.

## Note on secrets

The sample configuration contains no credential value, and neither should your
copy: reference an input or a variable, never a literal secret. Note what the
`envFile` entry does before you keep it - it loads an entire environment file
into the server process, whether the server needs those variables or not.

*Synthetic material. No real server, endpoint, credential, or client appears in
this directory.*
