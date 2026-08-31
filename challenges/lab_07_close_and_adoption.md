# Lab 7 - Close: retrieve, commit, govern

**Block:** 16:35-17:00 (25 minutes) - **Mode:** whole room, written individually
**Loop stage:** Explain, applied to your next use

---

## Outcome

You leave with:

1. one pointer for unfinished learning;
2. one bounded engineering habit to use once next week; and
3. one bounded, reversible adoption experiment that a team could approve,
   revise, or reject.

Everyone writes all three. The habit is usable when making or reviewing a change;
the experiment is usable when shaping team controls. There is no audience split.

Use toy labels in the room. Do not include work code, repository names, internal
identifiers, personal or customer data, secrets, or private links. Organisers do
not collect these notes, Lab 6 artifacts, prompts, transcripts, or scores.

---

## 1. Remediation pointer - 3 minutes

Write one line for each incomplete lab; do not try to finish it now.

| Lab | Last observed evidence | Archive or fallback pointer | Next 20-minute action | Date |
|---|---|---|---|---|

For Lab 6, use the archive path printed by `reset` and name the first unfinished
behaviour. If a live path was blocked by policy, put it in the experiment's
decision gate below instead. A policy boundary is a finding, not failed learning.

---

## 2. Retrieval before reference - 5 minutes

Answer from memory, then check the linked references.

1. For an incident with an uncertain cause, name the four loop stages and the
   evidence that moves you between them.
2. Before a multi-file contract migration, what must the reviewed plan contain?
3. What two observations make a test credible evidence rather than a green
   decoration?
4. What makes a telemetry reading fresh at the exact lower boundary, and which
   representation keeps exact operational values?
5. When a live feature is unavailable, what delivery mode and evidence labels
   keep the engineering claim honest?

Check
[reference/evidence.md](reference/evidence.md),
[reference/invariants.md](reference/invariants.md), and
[reference/model_selection.md](reference/model_selection.md). Schedule a
10-minute private repeat for one week from today using the delayed bank below.
Recall, not a longer feature tour, is the follow-up.

---

## 3. Write one engineering habit - 4 minutes

Complete this card:

```text
Trigger: Before I accept or hand over one agent-assisted change,
Action:  I name one invariant, read the diff, run the smallest check that could
         falsify the change, and write the three-part uncertainty sentence.
Scope:   One synthetic or approved low-risk change before <date>.
Evidence: One private evidence note; I share only the result needed for review.
Stop:    No baseline, required reviewer, or approval means no acceptance.
```

Keep the habit this small for four weeks before adding another. "Use Copilot
more" is not a habit; this observable gate is.

---

## 4. Make three bounded commitments - 8 minutes

Write exactly these three lines before expanding any experiment:

| Commitment | Required fields |
|---|---|
| **Monday action** | one action, your date, and an observable success signal |
| **Team decision** | one decision, decision date, and evidence the team needs |
| **Externally owned ask** | one approval or policy ask, owner role, due date, and fallback if unanswered |

These three commitments are the timed result. If the Team decision is to propose
a pilot, use the following template after the workshop in an approved team
system. It is not additional work in this block.

<details>
<summary>Post-workshop pilot template</summary>

```text
Question: Does the invariant + falsifying check + uncertainty gate make a small
          agent-assisted change ready for human review?
Boundary: Two weeks, one volunteer team, one synthetic or approved low-risk
          repository, at most five changes, and one permitted Copilot surface.
Controls: Existing branch protections and human review stay in force. No work
          data enters this workshop note. No unattended trigger, write-capable
          external MCP tool, or broad CLI auto-approval is in the first trial.
Evidence: Aggregate completed / stopped / revised counts and one short team
          observation. No prompts, transcripts, keystrokes, code samples,
          person-level acceptance rates, or individual ranking.
Stop rule: Stop on unexpected data access, an unapproved tool or permission,
           uncontrolled spend, bypassed required checks, or unclear attribution.
Owner:    Before the first run, <role> confirms the policy, repository, data,
          budget, review, and support routes required by the organisation.
Decision: On <date>, <role> chooses adopt, revise, or stop and records why.
```

Live tooling is optional. The later experiment can use this repository, a
captured result, or a manual change. Success means the team can make the decision
with evidence; it does not mean faster output or maximum usage.

The named owner routes any security, privacy, works-council, procurement, or AI
literacy obligation. This lab is not legal advice and does not classify a system.

</details>

---

## 5. Close - 2 minutes

Answer the Lab 0 question again:

> The capability I am least sure my organisation has enabled is ____, and the way
> I will find out is ____.

Then write only these two commitments:

> **My engineering gate next week is:** ____.
>
> **The bounded experiment I can take to a decision owner is:** ____.

The method is not a Copilot trick. It is professional engineering applied to a
fast, confident, occasionally wrong collaborator. Accountability stays with the
people who define, review, approve, and operate the change.

## Delayed one-week retrieval bank

Use these ten prompts privately one week later; they are not additional timed
work today:

1. Write the four loop stages.
2. Write the three uncertainty clauses.
3. Choose Ask, Plan, or Agent for a multi-file migration and state why.
4. Name the minimum contents of a reviewable plan.
5. State what fail-before/pass-after proves.
6. Distinguish a verifier result from evidence of supervision.
7. Distinguish achievement lane from delivery mode.
8. Name one control and limitation from an unchosen elective.
9. State the inclusive freshness interval and the minimum sample rule from the
   capstone.
10. State the stop rule and owner for your bounded adoption experiment.

---

## Optional decision lookup - official-source status as of 2026-08-25

This is a lookup for the experiment, not a list of features to enable. Recheck it
before a real pilot because plans, policies, billing, and previews change. Do not
assume one setting governs every client; check the
[supported policy surfaces](https://docs.github.com/en/copilot/reference/supported-surfaces-for-policies).

<details>
<summary>Open the official-source decision lookup after the timed close</summary>

### 1. Execution and review

**Decision:** Use the current term **Copilot cloud agent**. Treat cloud agent and
Copilot code review as separate controls; retain human review and branch rules.
Choose repository scope, Actions runner policy, review effort, and payer. Chat
model settings do not determine the code-review model.

**Gate:** Cloud agent requires a paid plan; Business/Enterprise administrators
must enable it, and repositories can opt out. Code review has its own policy and
uses AI credits plus Actions runners for agentic capabilities. See
[cloud-agent access](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/access-management)
and [code review](https://docs.github.com/en/copilot/concepts/agents/code-review).

### 2. CLI execution

**Decision:** Set available and approved tools, paths, and URLs; review saved
approvals. Never make an allow-all option the normal launch path.

**Gate:** Copilot CLI has a client policy independent of the Copilot app. The
sandboxing surface is public preview; both local and cloud CLI experiences
currently require experimental features, and cloud access has separate policy
and billing. See
[Copilot CLI](https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli),
[tool permissions](https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools),
and [sandboxes](https://docs.github.com/en/copilot/concepts/about-cloud-and-local-sandboxes).

### 3. Context and customization

**Decision:** For MCP, approve the server, identity, data boundary, and smallest
read-only tool allowlist. Repository MCP tools are shared by cloud agent and code
review and can run without per-call approval; registry discovery is not approval.
Review shared instructions, custom-agent profiles, skills, and hooks like code.
Restrict custom-agent tools explicitly, and leave Copilot Memory out of the first
trial unless its ownership and review/deletion route are approved.

**Gate:** The managed **MCP servers in Copilot** policy is disabled by default and
does not govern third-party hosts; the MCP Registry is public preview.
Organisation instructions require Business/Enterprise, surface support varies,
and Memory is public preview and off by default for managed plans. See
[MCP](https://docs.github.com/en/copilot/concepts/context/mcp),
[repository MCP configuration](https://docs.github.com/en/copilot/how-tos/copilot-on-github/customize-copilot/configure-mcp-servers),
the [customization comparison](https://docs.github.com/en/copilot/reference/customization-cheat-sheet),
[response customization](https://docs.github.com/en/copilot/concepts/prompting/response-customization),
and [Memory](https://docs.github.com/en/copilot/concepts/agents/copilot-memory).

### 4. Models and cost controls

**Decision:** Set permitted models, whether Auto is acceptable, the user-level
hard stop, and whether paid overage is allowed.

**Gate:** Business/Enterprise usage is measured in **GitHub AI Credits**.
"Premium requests" now applies only to qualifying individual Pro/Pro+
subscribers retained on legacy annual billing after 1 June 2026. Model
availability depends on plan, client, and administrator policy; Auto respects
those policies. Paid AI-credit usage is enabled by default for organisations and
enterprises unless disabled. See
[AI-credit billing](https://docs.github.com/en/copilot/concepts/billing/usage-based-billing-for-organizations-and-enterprises),
[budgets](https://docs.github.com/en/copilot/concepts/billing/budgets-for-usage-based-billing),
and [model access](https://docs.github.com/en/copilot/how-tos/copilot-on-github/set-up-copilot/configure-access-to-ai-models).

### 5. Data boundaries and measurement

**Decision:** Treat content exclusion as one context control, not data-loss
prevention; test the actual client and mode. Before measuring, agree the purpose,
lawful and works-council route, aggregation, access, retention, and decision. Do
not capture prompts or tool content in this pilot.

**Gate:** Content exclusion is for Business/Enterprise but is not currently
supported in editor Edit and Agent modes; website/mobile support is public
preview, with symlink and remote-filesystem limits. Usage metrics can expose
user-level reports, have coverage gaps, and lag by two full days.
Enterprise-managed OpenTelemetry is separate; optional content capture may
contain sensitive material. See
[content exclusion](https://docs.github.com/en/copilot/concepts/context/content-exclusion),
[usage metrics](https://docs.github.com/en/copilot/concepts/copilot-usage-metrics/copilot-metrics),
and [agent monitoring](https://docs.github.com/en/copilot/concepts/agents/opentelemetry).

For enterprise adoption, use the **AI Controls** view as the policy inventory for
agents, models, MCP, and related controls, then verify supported surfaces.
Metrics describe adoption and workflow outcomes with coverage/lag limits; they
must not become identifiable participant or employee performance telemetry.

### 6. Workflow expansion

**Decision:** Prefer research, plan, and iteration before a pull request for the
first enabled follow-up. Keep unattended automation out of scope until triggers,
tools, safe outputs, costs, logs, and stop ownership receive a separate review.

**Gate:** Cloud-agent research/plan/iterate is available on GitHub.com. Copilot
automations need a paid plan, a private/internal repository, and cloud-agent plus
automation enablement. GitHub Agentic Workflows require Actions and CLI and are
public preview. See
[research/plan/iterate](https://docs.github.com/en/copilot/how-tos/copilot-on-github/use-copilot-agents/research-plan-iterate),
[automations](https://docs.github.com/en/copilot/concepts/agents/cloud-agent/about-automations),
and [agentic workflows](https://docs.github.com/en/copilot/concepts/agents/about-github-agentic-workflows).

### 7. Mention-only emerging surfaces

These are awareness topics, not hands-on outcomes today:

| Surface | Status as of 2026-08-25 | Why it is only mentioned |
|---|---|---|
| Plugins | GA | Packaging for agents, skills, hooks, and MCP |
| Third-party coding agents | Public preview | Separate provider and policy boundary |
| IDE subagents | Available when `runSubagent` is enabled | Isolated delegation depth; no nested spawning |
| GitHub Copilot app | GA; cloud sandboxing preview | Parallel workspaces and app-specific modes/policy |
| GitHub Agentic Workflows | Public preview | Versioned CI automation with separate safety/cost review |

They add packaging, provider, delegation-depth, parallel-workspace, or CI
surfaces while preserving the same accountability requirement. Recheck status
and separate policy before adoption; do not infer approval from presence.

</details>

---

## Reflection

1. Which part of your engineering gate is easiest to skip under deadline?
2. Which stop rule makes the adoption experiment genuinely reversible?
3. What evidence would let the decision owner say "stop" without calling the
   experiment a failure?

---

*Curious about a second day? See
[appendix_two_day.md](appendix_two_day.md). It is explicitly out of scope for the
one-day core.*

*Back to the [labs index](README.md) or the [workshop README](../README.md).*
