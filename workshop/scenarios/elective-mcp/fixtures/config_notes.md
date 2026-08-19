# What the sample configuration does, key by key

`mcp_config_sample.json` is a real, current VS Code MCP configuration for a
local stdio server. It is also deliberately broad. Every key in it is documented
in the VS Code MCP configuration reference; nothing here is invented.

## The keys it uses

| Key | What it does | Why it is broad here |
|---|---|---|
| `type` | Connection type. `"stdio"` runs the server as a local child process. | Fine as it stands. |
| `command`, `args` | What is executed to start the server. | This is arbitrary local code execution by definition - it is the thing you are deciding to trust. |
| `cwd` | The working directory of that process. | The whole workspace. |
| `env` | Environment variables passed to the server. | Only a marker here, but this is where people paste secrets. Use `${input:...}` for anything sensitive so it is prompted and stored by the client, never written into the file. |
| `envFile` | A file whose variables are loaded into the server process. | Points at the entire `.env`. Everything in that file reaches the server process, whether the server needs it or not. |
| `dev` | Development-mode file watching and debugging. | Convenience for a server author, noise (and restarts) for everyone else. |
| `sandboxEnabled` | Runs this server confined, on macOS and Linux. | Set to `false`, so the process has your own filesystem and network reach. |

## The keys it does not use yet

Sandbox rules live in a **top-level `sandbox` object**, a sibling of `servers`,
and apply to servers that set `"sandboxEnabled": true`:

| Property | Meaning |
|---|---|
| `filesystem.allowWrite` | Paths the server may write to |
| `filesystem.denyRead` | Paths the server may not read |
| `filesystem.denyWrite` | Paths the server may not write to |
| `network.allowedDomains` | Domains the server may reach; wildcards are supported |
| `network.deniedDomains` | Domains the server may not reach |

Predefined variables such as `${workspaceFolder}` and `${userHome}` work in those
path values.

Sandboxing is available on macOS and Linux only. On Windows the same
configuration is not a confinement, and your inventory should say so.

### The trade you are making when you turn the sandbox on

This is the single most important sentence in the whole reference, and it is easy
to read past:

> When sandboxing is enabled, tool confirmations are auto-approved because the
> server runs in a controlled environment.
> (<https://code.visualstudio.com/docs/agents/reference/mcp-configuration#_sandbox-configuration>)

So enabling the sandbox does **not** give you confinement *plus* the prompts you
had before. It **moves the boundary**: per-call confirmation stops being the
thing that protects you, and the accuracy of your `sandbox` rules becomes the
thing that protects you. Two consequences follow.

- **Write the rules as if nobody will read a prompt again**, because for that
  server nobody will. Every path in `filesystem.allowWrite` and every domain in
  `network.allowedDomains` is now a standing permission, granted once, for every
  call the session makes.
- **A sandboxed server with sloppy rules is worse than an unsandboxed one with
  attentive approvals**, and it feels safer, which is exactly what makes it worth
  saying out loud. `"allowWrite": ["${workspaceFolder}"]` on a repository holding
  deployment credentials is a broad grant that nothing will ask you about again.

Neither posture is automatically correct. An unsandboxed server keeps a human in
the loop per call and depends on that human actually reading; a sandboxed server
removes the interruption and depends on rules you wrote once. Choose
deliberately, write down which you chose, and say what would make you change your
mind.

What the sandbox does **not** change is which tools a session may pick: tool
enable and disable state lives in the client, not in `mcp.json`, whether or not
the server is sandboxed.

## What this file cannot do

`mcp.json` starts and confines a **process**. It does not choose which tools a
chat session may use - that lives in the client's tool picker and settings. It
does influence approval, but only in one direction: turning the sandbox on
auto-approves confirmations for that server. A server's tool annotations
(`readOnlyHint` and friends) are metadata for that user interface, not a
permission system, and whether a tool exists at all is decided in the server's
own code.

So a complete answer to "what may this reach?" always has three parts: the
process configuration here, the client's approval settings, and the server's own
registration and validation.
