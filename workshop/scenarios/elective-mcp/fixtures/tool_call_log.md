# Captured tool-call log - local MittelWerk MCP server

All data and identifiers are synthetic.

```text
2026-08-19T13:02:11Z session.start server=mittelwerk-local transport=stdio sandboxEnabled=false
2026-08-19T13:02:11Z tools.list list_equipment, get_dispatch_queue, calculate_service_risk
2026-08-19T13:02:12Z annotations list_equipment readOnlyHint=true openWorldHint=false
2026-08-19T13:02:40Z tool.call name=list_equipment args={"limit": 2} approval=confirm
2026-08-19T13:02:40Z tool.result returned=2 total=4 assets=["PRESS-17","PUMP-04"]
2026-08-19T13:03:05Z tool.call name=get_dispatch_queue args={"asset_code":"PRESS-17","depth":5}
2026-08-19T13:03:11Z tool.result offers=3 requests=1 bytes=824
2026-08-19T13:04:22Z tool.call name=get_dispatch_queue args={"asset_code":"PRESS-17","depth":500}
2026-08-19T13:04:22Z tool.error code=-32602 message="depth must be between 1 and 20"
2026-08-19T13:05:19Z tool.call name=submit_work_order args={"asset_code":"PRESS-17","requested_hours":"4"}
2026-08-19T13:05:19Z tool.error code=-32601 message="Unknown tool: submit_work_order"
2026-08-19T13:06:20Z tool.call name=calculate_service_risk args={"open_hours":"120","overdue_fraction":"0.20"}
2026-08-19T13:06:20Z tool.result overdue_hours="24.00"
```

Because `sandboxEnabled=false`, the capture records an explicit approval result.
With the sandbox enabled there would be no approval=prompted line at all; tool
confirmations are auto-approved and standing confinement rules apply.
