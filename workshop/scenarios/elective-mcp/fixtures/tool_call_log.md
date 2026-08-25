# Captured tool-call log - local QuantCore MCP server

A short synthetic session against the default (read-only) server, captured so the
elective works with nothing connected. Timestamps are UTC; a Berlin desk would
read them as local time.

---

```
2026-08-19T13:02:11Z  session.start     server=quantcore-local transport=stdio sandboxEnabled=false
2026-08-19T13:02:11Z  tools.list        list_instruments, get_order_book, calculate_risk
2026-08-19T13:02:11Z  note              the two write tools are not in this list: the server was
                                        constructed read-only, so they were never registered
2026-08-19T13:02:12Z  annotations       list_instruments readOnlyHint=true openWorldHint=false
                                        get_order_book   readOnlyHint=true openWorldHint=false
                                        calculate_risk   readOnlyHint=true openWorldHint=false

2026-08-19T13:02:40Z  tool.call         name=list_instruments args={} approval=auto
2026-08-19T13:02:40Z  tool.result       name=list_instruments returned=6 total=6 bytes=1180
2026-08-19T13:02:41Z  note              the question concerned one symbol; six came back, and all
                                        six are now in the model context

2026-08-19T13:03:05Z  tool.call         name=get_order_book args={"symbol": "SIMX", "depth": 5}
                                        approval=prompted
2026-08-19T13:03:11Z  approval          granted by user
2026-08-19T13:03:11Z  tool.result       name=get_order_book levels=5 bytes=1104

2026-08-19T13:04:22Z  tool.call         name=get_order_book args={"symbol": "SIMX", "depth": 500}
2026-08-19T13:04:22Z  tool.error        code=-32602 message="Input validation error: depth must be
                                        less than or equal to 20"
2026-08-19T13:04:23Z  note              the bound is enforced by the server's own argument
                                        validation, not by the client and not by mcp.json

2026-08-19T13:05:19Z  tool.call         name=submit_order args={"symbol": "SIMX", "side": "BUY",
                                        "quantity": 100, "order_type": "MARKET"}
2026-08-19T13:05:19Z  tool.error        code=-32601 message="Unknown tool: submit_order"
2026-08-19T13:05:41Z  model.reply       "That tool is not available in this session. I can show you
                                        the book and describe what such an order would do."

2026-08-19T13:06:20Z  tool.call         name=calculate_risk args={"portfolio_value": "1000000.00",
                                        "daily_volatility": "0.015", "confidence": "0.95"}
                                        approval=granted_by_user
2026-08-19T13:06:20Z  tool.result       name=calculate_risk parametric_var=24672.80 bytes=412

2026-08-19T13:09:02Z  session.end       duration_s=411 calls=5 errors=2 approved=2 auto=1
```

---

## What to notice

- The refusal at `13:05:19` is not an allowlist decision. The tool was never
  registered, because the server was built read-only. That is the strongest form
  of "not permitted": the capability does not exist to be approved.
- The refusal at `13:04:22` came from the server's own input validation. Bounds
  on arguments are server-side work; no client setting would have caught it.
- The finding most people miss is the note at `13:02:41`. Nothing failed. The
  call was approved, it returned more than the question needed, and that data is
  now in a context window.
- One call was auto-approved and nobody read it. That is a configuration
  decision, usually made by accepting a default.

## What would change under the documented VS Code sandbox

This capture records `sandboxEnabled=false` and one `approval=prompted` event. It
does not establish why every approval decision applied or whether another
process-control layer ran.

With `"sandboxEnabled": true`, there would be no `approval=prompted` line at all:
VS Code auto-approves confirmations for a sandboxed server, and the top-level
filesystem/network rules become the host boundary. That is a prediction from the
documented configuration, not an observed sandbox run in this capture. The
refusals at `13:04:22` and `13:05:19` remain server validation and registration
decisions.

*Synthetic capture. No real client, order, endpoint, or credential appears in
this log.*
