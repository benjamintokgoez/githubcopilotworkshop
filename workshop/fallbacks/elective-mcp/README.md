# Offline fallback - elective-mcp (Lab 5A)

Everything needed for the secure-MCP elective without a connected server, a
registry entry, or network access.

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

## Working without the tooling

1. Copy `staged_copy/` somewhere you can edit.
2. Narrow the configuration using only keys the VS Code MCP configuration
   reference documents - `sandboxEnabled` plus a top-level `sandbox` object with
   `filesystem` and `network` rules - and record each removal.
3. Use `fixtures/tool_call_log.md` as your captured evidence: it contains a tool
   that was never registered, an argument the server rejected, an auto-approved
   call nobody read, and a response that returned more than the question needed.
   Label your evidence as captured in the note.
4. Fill in the inventory template. The headings in it are exactly what the
   evidence check looks for, so a complete note passes whether or not you ran it.

## Note on secrets

The sample configuration contains no credential value, and neither should your
copy: reference an input or a variable, never a literal secret. Note what the
`envFile` entry does before you keep it - it loads an entire environment file
into the server process, whether the server needs those variables or not.

*Synthetic material. No real server, endpoint, credential, or client appears in
this directory.*
