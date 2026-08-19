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
| The approval boundary is stated: per-call confirmation, or the sandbox that auto-approves it | `- Approval boundary:` |
| Tool provenance is evidenced, live or captured | `## 3. Evidence the answer came from the tool` |
| The negative case was actually run and recorded as observed | `- What I asked for outside the permission:` and `- Observed behaviour:` |
| The boundary of the control is named | `## 5. What MCP configuration does not protect against` |
| The governance ask has an owner | `- Approval owner:` |

No template placeholder may remain **anywhere** in the file - not in a checked
section, not in the preamble - and each section must contain real content rather
than a restatement of its heading.

## What it does not check

Whether your reduced configuration is the right one, whether a server is
connected, or whether your organisation permits MCP at all. If it does not, say
so in the inventory and name the approval owner - a documented policy blocker is
a complete result for this elective, not a failure of it.

`work/mcp_config_reduced.json` is yours to edit and is restored by `reset`. It is
not parsed by the checker: a configuration is evidence only together with the
reasoning next to it.

It also cannot tell whether you attributed a control to the right layer - only
that you named one. Getting that attribution wrong is the most common mistake in
this elective, and the resync is where it gets caught.

The same applies to the approval boundary: the checker sees that you named one,
not whether your sandbox rules would survive the calls nobody will be asked
about. Enabling `sandboxEnabled` auto-approves tool confirmations for that
server, so the rules become the boundary - see
`fixtures/config_notes.md`.

## Restore

```bash
python scripts/workshop.py reset elective-mcp
```
