# Elective 5A - Secure MCP context

**Block:** 15:15-15:55 (40 minutes) - **Scenario:** `elective-mcp`
**Parent:** [Lab 5 - Elective](lab_05_elective.md)

---

## Outcome

You connect an assistant to an external context source through MCP with the
narrowest useful permissions, you can say what data leaves your machine and what
does not, and you know which of these decisions is yours and which belongs to your
administrator.

---

After starting the scenario from the parent lab, record your work in
`workshop/scenarios/elective-mcp/work/`. The captured no-live path is under
`workshop/fallbacks/elective-mcp/`.

---

## Understand/Plan (7 minutes)

MCP lets a chat session reach tools and data outside the editor: repositories,
issues, documentation, internal services. That is exactly why it is a governance
surface and not just a convenience.

Three questions to answer before you configure anything:

1. **What can this server read?** Not what you intend to use it for - what it is
   capable of reaching.
2. **Where does the data go?** Local process, your network, a vendor's service?
3. **Who approved it?** Your organisation may operate an allowlist or a private
   registry, in which case the answer is "not you, and that is correct".

References:
<https://docs.github.com/en/copilot/concepts/context/mcp> ,
<https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/extend-copilot-chat-with-mcp> ,
<https://docs.github.com/en/copilot/concepts/mcp-management> ,
<https://code.visualstudio.com/docs/agent-customization/mcp-servers> ,
<https://code.visualstudio.com/docs/agents/reference/mcp-configuration>

---

## Implement/Test (18 minutes)

1. Configure **one** MCP server in this workspace. The local QuantCore server is
   the safe choice; the GitHub MCP server is the realistic one if your policy
   permits it
   (<https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/set-up-the-github-mcp-server>).
2. **Reduce it.** Enable the smallest set of tools that makes your task possible.
   If the server supports toolsets or read-only modes, use them
   (<https://docs.github.com/en/copilot/how-tos/provide-context/use-mcp-in-your-ide/configure-toolsets>).
   Write down what you disabled and why.
3. **Use it for something real**: ask a question that can only be answered with the
   external context, and confirm the answer actually came from the tool rather
   than from the model's guess.
4. **Read the approval boundary.** Without sandboxing, read each proposed tool
   call before approving it. Current VS Code auto-approves calls for a server
   with `sandboxEnabled: true`, so in that path inspect the sandbox policy and
   server output instead: an inaccurate allow rule is now the boundary you
   trusted.
5. Record: which tools were offered, which you allowed, and what a malicious or
   buggy tool could have done with that permission.

---

## Review: break it on purpose (5 minutes)

Ask for something **outside** the permission you granted - a write when you allowed
reads, or a resource outside the configured scope. Observe what happens: refusal,
an approval prompt, or silent success. Record the actual behaviour, not the
expected one.

---

## Explain (5 minutes)

Complete the platform-team paragraph in `work/permission_inventory.md`: what the
server reaches, what you disabled, what approval you need, and what the
configuration still cannot protect against.

---

## Business invariant at stake

**Data minimisation is a design constraint, not a preference.** A context source
that can read more than the task requires is a finding, even when nothing bad has
happened yet. See
[reference/dach_conventions.md](reference/dach_conventions.md#3-data-protection-datenschutz-and-data-minimisation).

In a DACH enterprise, "which internal systems may an assistant reach" is a
Datenschutz question and often a Betriebsrat question. Your configuration is a
draft proposal, not a decision.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Configure the local server, list its tools, and answer the three understanding questions in writing. |
| **Core** | The full Do and Break-it sections, with the permission inventory written down. |
| **Extension** | Draft the paragraph you would send to your platform team proposing an allowlist entry: what the server is, what it reaches, what you disabled, what you need approved, and what you would monitor. |

---

## Evidence and acceptance

See the [shared acceptance list](lab_05_elective.md#shared-acceptance), plus:

- [ ] A written inventory: tools offered / tools enabled / tools disabled
- [ ] Evidence that an answer came from the tool, not the model
- [ ] The negative-case result, recorded as observed
- [ ] One sentence naming what MCP configuration does **not** protect against

---

## Solo path

Everything here works with the local server and no network beyond your existing
Copilot connection. If your organisation blocks MCP entirely, do the understanding
questions and the extension paragraph - the governance reasoning is most of the
value and needs no server.

---

## Reflection and retrieval

1. If this server were compromised tomorrow, what is the worst thing it could have
   done with the permissions you granted today?
2. Retrieval: what is the difference between a tool being *available* and a tool
   being *approved*?
3. Who in your organisation currently decides which MCP servers are permitted? If
   the answer is "nobody", that is your finding.

---

*Back to [Lab 5](lab_05_elective.md). Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
