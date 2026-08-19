# Appendix - what a second day would add

**This appendix is out of scope for the one-day core.** Nothing in the one-day
agenda depends on it, no lab links into it as a required step, and facilitators
should not open it before 17:00. It exists so that teams commissioning a longer
engagement can see what the extra time buys, and so that individuals know where to
go next.

If you are attending the one-day workshop, the correct use of this page is to read
it on the train home.

---

## Why the one-day core stops where it does

A single day can build one loop to competence:
`Understand/Plan -> Implement/Test -> Review -> Explain`, applied to an incident, a
migration, a review, and a transfer task. Adding more surfaces to that day does
not add capability; it converts practice time into demonstration time, which is
exactly the failure mode of the feature-tour curriculum this one replaced.

Everything below needs practice time that a single day does not have.

---

## Day 2 modules (each 60-90 minutes)

### A. Delegation at scale

Running several cloud agent tasks in parallel against real backlog items: writing
delegable issues, deciding what is safe to delegate, triaging several returned pull
requests in one sitting, and measuring how review load changes. Requires the cloud
agent to be enabled and a repository with genuine backlog.
<https://docs.github.com/en/copilot/tutorials/cloud-agent/pilot-cloud-agent> ,
<https://docs.github.com/en/copilot/tutorials/cloud-agent/build-guardrails>

### B. Custom agents and reusable roles

Turning the review checklist, the migration procedure, and the incident triage from
Day 1 into custom agents and prompt files that a whole team uses, then maintaining
them as the codebase changes.
<https://docs.github.com/en/copilot/reference/custom-agents-configuration> ,
<https://code.visualstudio.com/docs/agent-customization/custom-agents>

### C. Agents in CI and automation

Running an agent non-interactively: what changes when there is no human at the
approval prompt, how to bound it, how to make its actions auditable, and when not
to do it at all.
<https://docs.github.com/en/copilot/how-tos/copilot-cli/automate-copilot-cli/run-cli-programmatically> ,
<https://docs.github.com/en/copilot/concepts/agents/copilot-cli/copilot-cli-in-github-actions>

### D. MCP for internal systems

Beyond the elective: connecting an internal service, threat-modelling the
connection, negotiating an allowlist entry, and writing the operational documents
your platform and security teams will ask for.
<https://docs.github.com/en/copilot/concepts/mcp-management> ,
<https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-mcp-usage/configure-enterprise-allowlist>

### E. Measurement without surveillance

Deciding what to measure about adoption, in a way that survives a works council
conversation: aggregate over individual, outcomes over activity, and what the
available metrics genuinely support.
<https://docs.github.com/en/copilot/concepts/copilot-usage-metrics> ,
<https://docs.github.com/en/copilot/reference/copilot-usage-metrics/interpret-copilot-metrics>

### F. Legacy systems clinic

The Day 1 migration on the participants' own repository, with their own baseline,
their own contract, and their own reviewers. This module is the one most teams
want and the one that cannot be simulated well in a shared codebase.

---

## Self-study track (after a one-day workshop)

In rough order of value per hour:

1. Finish your remediation list from [Lab 7](lab_07_close_and_adoption.md).
2. Repeat the Lab 7 retrieval questions after one week, from memory.
3. Do [Lab 3](lab_03_plan_driven_migration.md) again on your own repository.
4. Take the two electives you did not choose in [Lab 5](lab_05_elective.md).
5. Work through the task-shaped recipes in the GitHub cookbook:
   <https://docs.github.com/en/copilot/tutorials/copilot-cookbook>
6. Read the practice guides:
   <https://docs.github.com/en/copilot/get-started/best-practices> ,
   <https://code.visualstudio.com/docs/agents/best-practices>

---

## What a second day does not fix

- Missing organisational decisions. If nobody has decided who reviews
  agent-authored changes, a second day of practice does not decide it.
- Absent tests. Supervision is cheap when a suite tells you what broke, and
  expensive when nothing does.
- Policy blockers. If a capability is disabled, more training does not enable it.

Those three are the most common reasons adoption stalls after a good workshop, and
all three are addressed by the Lab 7 adoption list rather than by more lab time.
