# Acceptance - elective-mcp

```bash
python scripts/workshop.py verify elective-mcp
```

reads `work/permission_inventory.md` and checks that:

| Requirement | Field or section |
|---|---|
| The reachable surface is described, not the intended use | `## 1. What this server can reach` |
| What leaves the machine is stated | `- Data that leaves this machine:` |
| A real inventory exists | `- Tools offered:` / `- Tools enabled:` / `- Tools disabled:` |
| Each restriction is attributed to the layer that enforces it | `- Where the control lives:` |
| The approval and process-confinement assumptions are stated | `- Approval boundary:` |
| Tool provenance is evidenced, live or captured/offline | `## 3. Evidence the answer came from the tool` |
| The negative case is labelled and attributed | `- What I asked for outside the permission:` and `- Observed behaviour:` |
| The boundary of the control is named | `## 5. What MCP configuration does not protect against` |
| The governance ask has an owner | `- Approval owner:` |

No template placeholder may remain **anywhere** in the file - not in a checked
section, not in the preamble - and each section must contain real content rather
than a restatement of its heading.

## Evidence routes

Both routes are complete:

- **Live:** identify the host/server, record a fresh call and negative result, and
  label the evidence live.
- **Captured/offline:** edit the reduced configuration, trace events in
  `fixtures/tool_call_log.md`, and label them captured/offline. Any sandbox result not
  present in the capture must be labelled predicted.

The captured route must still name the controlling layer and produce the edited
configuration and governance decision. Merely reading the fixtures is not
completion.

The field label `Observed behaviour` is fixed by the staged template. Begin a
captured trace with `Captured:`; reserve `Observed live:` for a request made
against the preflight-approved server.

## What it does not check

Whether your reduced configuration is the right one, whether a server is
connected, or whether your organisation permits MCP at all. If it does not, say
so in the inventory and name the approval owner - a documented policy blocker is
a complete result only when it is accompanied by the local configuration review,
captured event trace, and negative case.

`work/mcp_config_reduced.json` is yours to edit and is restored by `reset`. It is
not parsed by the checker: a configuration is evidence only together with the
reasoning next to it.

It also cannot tell whether you attributed a control to the right layer - only
that you named one. Getting that attribution wrong is the most common mistake in
this elective, and the resync is where it gets caught.

The same applies to the approval boundary: the checker sees that you named one,
not whether a proposed host policy would survive calls it did not exercise. See
`fixtures/config_notes.md` and label unrun confinement outcomes predicted.

`verify` cannot establish that a sandbox, tool picker, authentication scope, or
enterprise policy actually ran. Your evidence labels carry that meaning.

## Restore

```bash
python scripts/workshop.py reset elective-mcp
```
