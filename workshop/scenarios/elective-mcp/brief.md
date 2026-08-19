# Brief - secure MCP context (elective 5A)

You are deciding what an assistant may reach on your behalf. The mechanism is
MCP; the exercise is data minimisation, confinement, and approval - which is the
part that transfers to whatever your organisation adopts next.

Everything here works locally and offline. No registry entry, no hosted server,
and no network access beyond the Copilot connection your organisation already
permits is required.

## The material

| File | What it is |
|---|---|
| `fixtures/tool_inventory.md` | The tool surface this repository's MCP server actually exposes, and where each control lives |
| `fixtures/mcp_config_sample.json` | A real, current VS Code stdio configuration - and a deliberately broad one |
| `fixtures/config_notes.md` | What each key in that file does, and which keys it is not using yet |
| `fixtures/tool_call_log.md` | A captured session: bounded results, a rejected argument, and a tool that does not exist |
| `work/mcp_config_reduced.json` | Your copy of the configuration, to narrow |
| `work/permission_inventory.md` | Your inventory and governance note |

## The task

1. **Read the surface first.** Go through `fixtures/tool_inventory.md` against
   the source and answer, per tool: what could this reach, and what could a buggy
   or hostile version of it do? Not what you intend to use it for - what it is
   capable of.
2. **Narrow the configuration.** Edit `work/mcp_config_reduced.json` from broad
   to least-privilege using only keys the VS Code MCP configuration reference
   documents: turn on `sandboxEnabled`, add a top-level `sandbox` object with
   `filesystem` and `network` rules, and cut anything the server does not need -
   starting with an `envFile` that hands it your whole environment file.
   Every removal is a decision you should be able to defend in one sentence.

   Read `fixtures/config_notes.md` before you flip `sandboxEnabled` to `true`.
   Enabling the sandbox **auto-approves tool confirmations for that server**,
   because the confinement is what is protecting you instead of the prompt. You
   are not adding a layer, you are swapping one: your `sandbox` rules become the
   approval boundary, and they are only as good as you wrote them.
3. **Say where each control lives.** For every restriction you claim, name the
   layer that enforces it: the process configuration in `mcp.json`, the client's
   tool picker and approval settings, or the server's own registration and
   argument validation. A control you attribute to the wrong layer is a control
   you do not have. State explicitly whether per-call confirmation is still part
   of your setup, or whether you traded it for the sandbox.
4. **Prove an answer came from the tool.** If you have a server connected, ask
   something that cannot be answered without it and record what came back. If you
   do not, use `fixtures/tool_call_log.md` and say in your note that your
   evidence is captured rather than live. Both are honest; pretending is not.
5. **Break it on purpose.** Ask for something outside what you granted - a write
   on a read-only server, or an argument outside the documented bounds. Record
   what actually happened, including *which layer* refused - and note whether you
   were asked to confirm anything at all, which will depend on whether that
   server is sandboxed.
6. **Write the governance note.** Who approves this in your organisation, what
   data leaves the machine, and what the configuration does *not* protect
   against.

## Design rules worth applying while you narrow

- **Capability beats configuration.** A tool that is never registered cannot be
  approved by mistake. Prefer a server built without the dangerous tool over a
  server whose dangerous tool you promise not to select.
- **Least privilege in the process, too.** Sandbox the process, deny reads of
  anything holding credentials, and allow writes only where the task needs them.
  Sandboxing is macOS and Linux only - write that limitation down.
- **A sandbox moves the approval boundary; it does not add to it.** With
  `sandboxEnabled` on, confirmations for that server are auto-approved, so every
  path and domain you allow is a standing grant nobody will be asked about again.
  Write the rules as if no human will ever see another prompt for that server,
  because none will.
- **No secrets in configuration.** Reference an input or the environment, never a
  value, and never point `envFile` at a file with more in it than the server
  needs.
- **Validate at the boundary.** Every argument from a model is untrusted input:
  bound sizes and ranges, constrain types, reject unknown identifiers. That is
  server-side work and nothing else can do it for you.
- **Bound the output.** A tool that can return an unbounded blob can exfiltrate
  one, and it will also destroy your context window.
- **Annotations are not authorization.** `readOnlyHint` and its siblings are
  metadata a server asserts about itself, for the client's user interface. A tool
  that lies still runs.
- **Log what was called.** Traceability is not optional when something goes wrong
  at 03:00.

## Policy is part of the lesson

If your organisation restricts MCP servers to a registry or an allowlist, that
restriction **is** the lesson. Document it as a finding and name the approval
owner; do not work around it.
