# Tool surface - QuantCore local MCP server

What `qxm/mcp_server/server.py` exposes today. Read the source alongside this
table; a summary is exactly the kind of thing that drifts from the code it
describes, so check it rather than trusting it.

This is the local QuantCore training server, not the GitHub MCP Server. Its
read-only default comes from server construction: write tools are not registered
at all. GitHub MCP Server toolsets and its `--read-only` mode are separate
product mechanisms and do not describe this code.

## Registered by default (read-only server)

`run_server()` builds a read-only server over stdio. It registers three tools:

| Tool | Effect | Reaches | Bounded by |
|---|---|---|---|
| `list_instruments` | Read - simulated instrument reference data | The instrument map loaded from `instruments.json` | `limit` 1-50, `offset` 0-10000 |
| `get_order_book` | Read - one simulated order book snapshot | Resting orders for one symbol in the local engine | `depth` 1-20, known symbols only |
| `calculate_risk` | Read - VaR and expected shortfall from **caller-supplied** numbers | Nothing beyond its own arguments | bounded value, volatility and confidence, horizon up to 252 days, up to 256 observations |

## Registered only on request (write tools)

`submit_order` and `cancel_order` exist in the source, but they are **not
registered at all** unless the server is constructed with writes enabled and a
client identity bound at construction time:

| Tool | Effect | Registration condition |
|---|---|---|
| `submit_order` | Write - creates an order in the local simulated engine | writes enabled **and** a non-empty bound client identity |
| `cancel_order` | Write - cancels an order this server identity opened | the same, and only for orders this server itself opened |

Two design details are worth copying rather than just noting:

- The client identity is **bound when the server is built** and is never a tool
  argument, so a model cannot choose whose account it acts on.
- `cancel_order` refuses identifiers the server did not open itself, so the write
  surface cannot be steered onto someone else's order.

There is no credential anywhere in this server. It reads local simulated state,
holds no API token, and reaches no network.

## Where each control actually lives

This is the part people get wrong, and the reason a configuration file alone is
never the answer:

| Control | Lives in |
|---|---|
| Whether the server process starts at all, and with which command, working directory and environment | `mcp.json` |
| Filesystem and network confinement of that process (macOS and Linux in current VS Code) | `mcp.json`: `sandboxEnabled` on the server plus the top-level `sandbox` object |
| Which of the server's tools a chat session may pick | The client's tool picker and settings - **not** `mcp.json`, sandboxed or not |
| Whether you are asked to confirm each call | The client's approval settings - **unless** this VS Code server is sandboxed, in which case confirmations are auto-approved and the `sandbox` rules become the host boundary |
| Which tools exist to be offered at all | The server itself: registration is code, and here the write tools are gated at construction |
| `readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint` | Server metadata attached to each tool. They are **hints for the client's user interface, not authorization**. A tool whose annotations lie still runs. |

This table also does not prove that an enterprise policy, client tool selection,
authentication scope, or process sandbox was active. Those require evidence from
their own layers. In the captured route, only the events in
`fixtures/tool_call_log.md` are observed; the reduced sandbox configuration is a
reviewed proposal. Sandboxing is not confinement plus per-call prompts: in the
documented VS Code path it replaces those confirmations with standing rules.

## Questions the table does not answer

Write these down in your inventory:

1. `list_instruments` returns every instrument by default. Is that the smallest
   result that answers your question, and what happens to the remainder once it
   sits in a model context?
2. The write tools are absent from a default server. What in **your** setup
   guarantees the server was built that way - a code path, a review, or a habit?
3. `calculate_risk` computes from numbers the caller supplies. What does that
   mean for how much you trust its answer, as opposed to how safe it is?
4. What is recorded when a tool is called here, and could you reconstruct
   tomorrow what ran tonight?
5. If you propose `sandboxEnabled`, every path and domain you allow becomes a
   standing grant with no per-call confirmation. Which allowances would you
   still defend under that rule, and which outcomes remain untested?

## Simulation notice

This server operates on a simulated engine with generated data. Nothing here
reaches a real venue, account, or market feed. The governance questions are real;
the trades are not.
