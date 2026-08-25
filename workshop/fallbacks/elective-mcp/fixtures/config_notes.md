# What the sample configuration does, key by key

`mcp_config_sample.json` is a current VS Code MCP configuration for a local stdio
server. It is deliberately broad. Every key shown in the sample is documented.

**Reference check:** 25 August 2026 against
<https://code.visualstudio.com/docs/agents/reference/mcp-configuration> and
<https://code.visualstudio.com/docs/agent-customization/mcp-servers>.
This file describes VS Code's local stdio host configuration. It is not the
schema for Copilot CLI, a remote MCP server, or repository MCP settings on
GitHub.com.

## The keys it uses

| Key | What it does | Why it is broad here |
|---|---|---|
| `type` | Connection type. `"stdio"` runs the server as a local child process. | Fine as it stands. |
| `command`, `args` | What is executed to start the server. | This is arbitrary local code execution by definition - it is the thing you are deciding to trust. |
| `cwd` | The working directory of that process. | The whole workspace. |
| `env` | Environment variables passed to the server. | Only a marker here, but this is where people paste secrets. Use `${input:...}` for anything sensitive so it is prompted and stored by the client, never written into the file. |
| `envFile` | A file whose variables are loaded into the server process. | Points at the entire `.env`. Everything in that file reaches the server process, whether the server needs it or not. |
| `dev` | Development-mode file watching and debugging. | Convenience for a server author, noise (and restarts) for everyone else. |
| `sandboxEnabled` | Runs this local stdio server in the VS Code sandbox on macOS and Linux. | Set to `false`, so this file provides no sandbox confinement. |

## Approval, confinement, and enterprise policy

VS Code sandbox rules live in a top-level `sandbox` object, a sibling of
`servers`, and apply to local stdio servers that set `"sandboxEnabled": true`:

| Property | Meaning |
|---|---|
| `filesystem.allowWrite` | Paths the server may write to |
| `filesystem.denyRead` | Paths the server may not read |
| `filesystem.denyWrite` | Paths the server may not write to |
| `network.allowedDomains` | Domains the server may reach; wildcards are supported |
| `network.deniedDomains` | Domains the server may not reach |

Predefined variables such as `${workspaceFolder}` and `${userHome}` work in path
values. This sandbox is available on **macOS and Linux only**, not as a portable
MCP server property across every host.

### The approval trade

The current VS Code reference states:

> When sandboxing is enabled, tool confirmations are auto-approved because the
> server runs in a controlled environment.
> (<https://code.visualstudio.com/docs/agents/reference/mcp-configuration#_sandbox-configuration>)

So enabling `sandboxEnabled` does not preserve per-call prompts and add
confinement. It trades those confirmations for standing filesystem and network
rules. Every allowed path and domain must therefore be reviewed as a persistent
grant. In captured/local mode, an edited sandbox policy is a **proposal**; no
sandbox denial is observed unless the capture or a preflight-approved live run
records one.

Enterprise `managed-settings.json` allowlists are the GA governance reference
for supported IDE/CLI clients. Private registries are preview and weaker
enforcement. Cloud-agent MCP is a distinct boundary: repository or custom-agent
configuration controls its servers, not the IDE/CLI registry.

Server trust is another separate decision. VS Code asks whether you trust a new
or changed server configuration before starting it, unless you start it directly
from the configuration file. Trusting the server to start is not approval of
every data source it can reach and is not upstream authorization.

## What this file cannot do

`mcp.json` starts a **process** and supplies its working directory and
environment.
It does not choose which tools a chat session may use - that state is stored
separately by the client. A server's tool annotations (`readOnlyHint` and
friends) are metadata for that user interface,
not a permission system, and whether a tool exists at all is decided in the
server's own code.

So a complete answer to "what may this reach?" always has three parts: the
process configuration here, the client's approval settings, and the server's own
registration, validation, and upstream authorization. For captured work, the
edited configuration is a proposal; only the captured server events are
observed.
