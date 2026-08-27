# Tool surface - MittelWerk local MCP server

`mittelwerk/mcp_server/server.py` exposes a synthetic service-operations system,
not the GitHub MCP Server.

## Default read-only tools

| Tool | Purpose | Data reached | Bounds |
|---|---|---|---|
| `list_equipment` | List synthetic equipment reference data | `equipment.json` | limit 1-50, bounded offset |
| `get_dispatch_queue` | Read pending capacity and requests for one asset | In-memory dispatch engine | depth 1-20, known asset only |
| `calculate_service_risk` | Estimate overdue workload from caller-supplied values | Arguments only | finite non-negative inputs, bounded horizon |

## Optional mutation tools

`submit_work_order` and `cancel_work_order` are absent by default. They are
not registered at all unless construction explicitly enables writes and binds an
organisation identity. Identity is never a model argument. Cancellation is
limited to work orders created by that bound server identity.

Annotations are metadata, not authorization. Registration,
server-side validation, client tool selection, approval behavior, process
confinement, and operating-system permissions are separate control layers.
With VS Code `sandboxEnabled`, tool confirmations auto-approve and standing
filesystem/network rules become the active boundary.

Questions for the exercise:

1. Does listing all equipment return more context than the task needs?
2. Which negative call proves the write surface is absent?
3. What can a permitted read tool still expose or return unexpectedly?
