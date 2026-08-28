# Elective 5A - Secure MCP context

**Block:** 15:00-15:35 (35 minutes) - **Scenario:** `elective-mcp`
**Parent:** [Lab 5 - Elective](lab_05_elective.md)

---

## Outcome

You reduce one local MCP configuration, trace a positive and a negative tool
event to the layer that controlled it, and write a defensible platform decision.
Connecting a new server is **not** the outcome and is not part of the timebox.

Work in `workshop/scenarios/elective-mcp/work/`. If staging or live MCP is
unavailable, use `workshop/fallbacks/elective-mcp/`.

## Route decision

| Delivery mode | Use this material | What it proves |
|---|---|---|
| **Captured/offline** | Sample `mcp.json`, tool inventory, configuration notes, captured tool log | Engineering and control analysis; no claim that a server was operated |
| **Live** | The same artifacts plus one already-approved, already-running local server | Whether this host/server combination behaved as recorded today |
| **Follow-up (not a delivery mode)** | GitHub MCP Server or enterprise allowlist proposal | Awareness only; do not install, authenticate, or request registry approval during this block |

If live eligibility was not Green at T-72, use captured/offline mode immediately.
If a Green server does not answer by **15:03**, switch to the capture. Do not
replace evidence work with connection troubleshooting.

---

## Understand/Plan (5 minutes)

MCP is a protocol boundary. Four different control layers can be involved:

| Layer | It can control | It does not prove |
|---|---|---|
| **Enterprise/client policy** | Whether a client may start or connect to a server | That a permitted server or tool is safe |
| **Host configuration** | Process command, environment, working directory, and local stdio sandbox rules | Which capabilities the server registered or whether tool input is valid |
| **Client tool selection and approval** | Which offered tools the model can select and whether a user is prompted | Server-side authorization, OAuth/PAT scope, or process confinement |
| **Server implementation and upstream identity** | Registered tools, argument validation, authorization, and data returned | That the host confined a buggy process or that returned data was minimal |

Answer before editing:

1. What can the **process** reach?
2. What can the **registered tools** reach?
3. What data enters model context or leaves the machine?
4. Which layer will produce each piece of evidence?

### Current product boundaries - as of 2026-08-25

- The GitHub MCP Registry is **public preview**. Discovery through a registry is
  not the same as enterprise approval.
- GitHub documents enterprise `managed-settings.json` MCP allowlists as
  **generally available** and stronger than private-registry restriction. MCP is
  policy-dependent for Business and Enterprise seats, and the policy is disabled
  by default.
- Individual GitHub MCP Server tools retain the plan and feature permissions of
  the GitHub capability they call. Its default toolsets are not a promise of
  read-only operation.
- The GitHub MCP Server supports a server-side `--read-only` mode. Toolsets reduce
  the offered surface; read-only mode removes write tools. Neither changes the
  signed-in identity's upstream access.
- Enterprise `managed-settings.json` allowlists govern supported IDE/CLI clients;
  cloud-agent MCP is configured separately at repository or custom-agent level.
  A private registry is preview and weaker enforcement, not an equivalent
  replacement.
- VS Code documents `sandboxEnabled` and top-level `sandbox` rules for local
  stdio servers on macOS and Linux. When enabled, tool confirmations are
  auto-approved because the server runs in a controlled environment. That
  trades per-call confirmation for standing filesystem/network rules; it does
  not add server authorization and is not portable to every host.
- Approval and sandbox behavior still depends on the supported client and
  version. Inspect proposed calls and verify the exact host policy at T-72.

Official references:

- <https://docs.github.com/en/copilot/concepts/context/mcp>
- <https://docs.github.com/en/copilot/concepts/mcp-management>
- <https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/configure-toolsets>
- <https://github.com/github/github-mcp-server#read-only-mode>
- <https://code.visualstudio.com/docs/agent-customization/mcp-servers>
- <https://code.visualstudio.com/docs/agents/reference/mcp-configuration>

---

## Implement/Test (13 minutes)

### Captured/offline mode

1. Read `fixtures/tool_inventory.md` and identify the maximum reach of each
   offered tool. Do not confuse intended use with capability.
2. Reduce `work/mcp_config_reduced.json`:
   - remove environment and development access the server does not need,
   - choose and defend one documented VS Code host posture: keep per-call
     confirmations with the sandbox disabled, or enable `sandboxEnabled` and add
     the narrowest top-level filesystem/network rules you can defend,
   - label an unexecuted edited policy proposed, and state platform/client
     limitations.
3. In `work/permission_inventory.md`, trace at least three captured events:
   tool selection, one accepted bounded result, and one refusal. For each, name
   the client, sandbox, server registration, server validation, or upstream
   authorization as the controlling layer.
4. Mark sandbox outcomes that you did not run as **predicted**, not observed. The
   capture proves the server's registration and validation behaviour; it does
   not prove your edited sandbox policy.

### Optional live addition

Use only the preflight-approved local server. Record the tool list, one call
whose result contains a fresh value, and the host's tool-call record. Do not add
the GitHub MCP Server or authenticate a new service during the block.

**Cut at 15:18:** you now need a reduced configuration and an evidence trace.
Stop improving the rules.

---

## Review: test the boundary (7 minutes)

Choose one negative case whose enforcing layer you can identify:

- request a tool that the read-only server never registered,
- pass an argument outside a documented server bound,
- in a preflight-green live sandbox, request access outside an allowed path or
  domain.

Record the request and result. A model refusal is not equivalent to a client
deny, a sandbox error, an unknown tool, or a server validation error. For the
captured route, trace an existing failed call and label it captured.

Then name two non-goals. Examples of relevant categories are malicious server
code, excessive but valid output, stolen upstream credentials, prompt injection
inside returned content, or unsupported operating systems. Select the ones your
evidence actually supports.

---

## Explain (4 minutes)

Complete the platform-team paragraph in `work/permission_inventory.md`:

- server and transport,
- process and data reach,
- tools offered/enabled/absent,
- positive and negative evidence source,
- approval owner and policy status,
- residual risk and monitoring requirement.

### Role lens

- **Developer:** Could you reproduce which tool ran and why the result was
  accepted?
- **Architect/platform owner:** Could you approve this exact server identity,
  command/URL, authentication scope, and process reach without approving a
  category of unknown servers?

---

## Business invariant at stake

**Data minimisation is a design constraint, not a preference.** A source that can
read more than the task requires is a finding even if no misuse occurred. See
[reference/dach_conventions.md](reference/dach_conventions.md#3-data-protection-datenschutz-and-data-minimisation).

In a DACH enterprise, access to internal systems can involve privacy, security,
and works-council review. This lab produces a proposal and evidence, not
organisational approval.

---

## Evidence and acceptance

See the [shared acceptance list](lab_05_elective.md#shared-acceptance), plus:

Supported completes the first three branch items on one positive and one negative
event and records the actual verifier result. Core completes every item below
and requires the structural verifier to pass.

- [ ] Inventory of tools offered, enabled, disabled, or never registered
- [ ] Process reach separated from tool capability and upstream authorization
- [ ] One positive and one negative event attributed to an enforcing layer
- [ ] Live, captured, and predicted statements labelled accurately
- [ ] One sentence explaining why tool annotations and toolsets are not
      authorization

---

## Solo path

Use the supplied configuration and capture. Produce the same reduced file,
three-event control trace, negative case, and platform paragraph. If policy
blocks MCP, record the policy owner and evaluate the proposed configuration
without trying to bypass the policy.

---

## Reflection and retrieval

1. If the server process were hostile, what could it reach before any tool was
   called?
2. What is the difference between a tool being offered, selected, approved, and
   authorized upstream?
3. Which statement in your note is observed, and which is only predicted?

---

*Back to [Lab 5](lab_05_elective.md). Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
