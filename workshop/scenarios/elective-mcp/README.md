# Scenario: elective-mcp (Lab 5A)

```bash
python scripts/workshop.py start elective-mcp
python scripts/workshop.py verify elective-mcp
python scripts/workshop.py reset elective-mcp
```

| Path | What it is |
|---|---|
| `brief.md` | The task, the design rules, and why policy blockers count as results |
| `fixtures/tool_inventory.md` | The tool surface of this repository's MCP server, and where each control lives |
| `fixtures/mcp_config_sample.json` | The over-broad starting configuration, in current VS Code MCP syntax |
| `fixtures/config_notes.md` | What each configuration key does, and the sandbox keys it is not using yet |
| `fixtures/tool_call_log.md` | A captured session, including one denial, for the offline path |
| `acceptance.md` | What `verify` checks |
| `work/` | Created by `start`: your narrowed configuration and your inventory |

The **captured/local delivery mode** requires no live server, registry entry,
authentication, or network access. You still edit the reduced
configuration, trace positive and negative events to their controlling layers,
and write the platform decision. Label sandbox outcomes you did not run as
predicted.

Either mode can support Supported or Core evidence; record the achievement lane
separately. Use a live server only if it was approved, connected, and smoke-tested before
Lab 5. Do not spend the elective installing or authenticating one.

The tool surface described here is the one this repository ships today: a
read-only server with `list_instruments`, `get_order_book` and `calculate_risk`,
plus `submit_order` and `cancel_order` that are only registered when a server is
deliberately constructed with writes enabled and a bound client identity.

This is the QuantCore training server, not the GitHub MCP Server. Product status,
GitHub toolsets, registry governance, and VS Code sandbox boundaries are recorded
in `brief.md` and `fixtures/config_notes.md`.
