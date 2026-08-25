# Lab 0 - Preflight (before the day) and landing check

**Preflight:** complete by **T-72 hours** (allow 60-90 minutes on a cold machine;
a prepared managed image may take less).
**Landing check on the day:** 09:00-09:20 (20 minutes).
**Loop stage:** readiness for
**Understand/Plan -> Implement/Test -> Review -> Explain**.

Installation, authentication, proxy repair, and policy discovery finish at
T-72; none belongs in a timed lab. If an approved prerequisite is still missing,
select the organizer-provided, paired, or captured route rather than relying on a
last-minute exception.

---

## Outcome

You arrive with a working environment, known model access, a clear picture of what
your organisation has and has not enabled, and a repository state you can reset
to.

This produces one shared control picture: a developer knows which local commands
and interaction style are safe to use; an architect knows which policy,
authorization, data, and budget assumptions the exercises rely on. Neither has to
infer the other's constraints during an incident.

---

## Preflight - do this before the day

### Assumptions and stop rules

- Use only this synthetic training repository or an organizer-provided copy. Do
  not test access with production code, customer data, credentials, or private
  repository content.
- Use your organisation's approved IDE and latest permitted stable client or
  extension. Record the version: feature availability depends on both the client
  and policy.
- Start with an approved Python 3.12 interpreter and package-index route. If you
  cannot obtain either within 30 minutes, stop and contact the named support
  owner. Do not disable TLS, bypass a proxy, or paste a token into chat.
- A live Copilot connection is optional. A local repository route and
  captured/offline evidence route are part of the design.

### 1. Tooling

```bash
python --version          # must report 3.12.x - the workshop baseline
git --version
code --version            # or your IDE of choice
```

**Python 3.12.x is the baseline**, and it is the version the platform is built and
verified against. Any 3.12 patch release is fine. A newer minor version is not:
if `python --version` reports something else, create the virtual environment below
from a 3.12 interpreter explicitly (for example `python3.12 -m venv .venv`) rather
than hoping it works on the day.

### 2. Repository and environment

```bash
git clone <repo-url>
cd githubcopilotworkshop

python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\Activate.ps1    # Windows PowerShell

python -m pip install -e ".[dev]"
```

### 3. Preflight check

```bash
python scripts/workshop_doctor.py    # environment and repository structure
python -m pytest -q                  # the test baseline
```

Two commands, because they answer two different questions.

`workshop_doctor.py` reports your Python version, whether the expected
dependencies import, whether the repository revision and the expected baseline
files are present, whether `settings.yaml` and `instruments.json` are structurally
valid, and a few environment hints - it tells you whether a relevant variable is
set, never what it contains. Read the whole output rather than scanning for the
absence of red; a warning you skim past now is a broken lab at 11:00.

What the doctor deliberately does **not** do: it does not run the test suite, it
does not generate sample data, and it cannot see inside your IDE, so it says
nothing about whether Copilot is signed in or reachable. `pytest -q` covers the
first of those, and step 4 below covers the last - by hand, because no script can
do it for you.

If `scripts/workshop_doctor.py` is not present, first confirm that you are on the
workshop revision supplied by the organizer. If that is intentional, run this
manual minimum and record the missing doctor as a warning:

```bash
python -c "import sys; print(sys.version)"
python -m pytest -q
```

> **The baseline must be green, and that means both commands.** On a clean
> checkout the doctor reports no failures **and** `pytest -q` shows no failing
> tests. A green doctor with a red test run is not a passing baseline, and neither
> is the reverse.
>
> Nothing in this repository is "expected to fail" before the
> day. The broken checks you will investigate are
> introduced by the scenario tooling when you run
> `python scripts/workshop.py start <scenario-id>` during a lab, and they
> disappear again on `reset`. So a red preflight means a real problem - a wrong
> Python version, a missing dependency, a partial checkout - and it is much
> cheaper to fix now than at 09:10.

### 4. Product access and operating boundary

If you are using the primary live route:

1. Record the client, version, account context, and repository you are using.
2. Open chat and ask one read-only question about this synthetic repository.
   Record whether a response arrives; do not paste unrelated workspace context.
3. Record whether the client offers these **local roles**, or an equivalent:
   read-only Q&A, read-only planning, and an editing/command-running agent. The
   current GitHub and VS Code labels are **Ask**, **Plan**, and **Agent**. The
   local Agent role is not the GitHub-hosted **cloud agent**.
4. Open the model selector and record exactly what it shows: **Auto**, explicit
   models, both, or unavailable. The workshop requires no named model. If you
   choose Auto, record `Auto`; do not guess the routed model. Note the routed
   model separately only if the client exposes it after the response. See
   [reference/model_selection.md](reference/model_selection.md).
5. Find the tool, approval, or permission control for the local editing agent.
   A role label is a workflow choice, not an authorization boundary.

If sign-in, entitlement, client support, policy, budget, or the network blocks a
step, record the observed blocker and select the local/captured route. Do not
bypass policy, and do not treat unavailable Copilot access as a failed repository
baseline.

Current official references:

- [Ask, Plan, and Agent in an IDE](https://docs.github.com/en/copilot/how-tos/chat-with-copilot/chat-in-ide)
- [VS Code built-in agent roles and execution targets](https://code.visualstudio.com/docs/agents/run/agent-harnesses)
- [VS Code planning workflow](https://code.visualstudio.com/docs/agents/run/planning)
- [Auto model selection](https://docs.github.com/en/copilot/concepts/models/auto-model-selection)
- [Copilot feature matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix)

### 5. Organizer capability matrix and policy reality check

By T-72, the organizer provides a Green/Amber/Red capability matrix for the
approved client versions, model/Auto policy, AI-credit stop rule, content
exclusion, cloud agent, code review, MCP, CLI, proxy, and captured fallbacks.
Participants confirm only their assigned route; they are not expected to
discover organisation policy alone.

Answer these for **your** organisation. "I do not know" is a valid answer to bring
to the room - it is often the most useful thing an attendee contributes all day.

- [ ] Which Copilot plan or entitlement is assigned to me, is it personal or
      organisation-managed, and who administers it?
- [ ] Which local chat roles and models are enabled for my chosen client and
      version?
- [ ] Is the **cloud agent** enabled for me, and for which repositories?
- [ ] Is **Copilot code review** enabled on the surface we expect to use?
- [ ] Is the **MCP servers in Copilot** policy enabled, and do enterprise-managed
      allow or deny lists apply to this client?
- [ ] Is **Copilot CLI** permitted and installed, or is the IDE/local-only route
      required?
- [ ] What **GitHub AI credits** allowance, additional-usage budget, or stop rule
      applies to workshop requests?
- [ ] Which content exclusions apply on the planned surface, and where do they
      not apply? Do not assume an exclusion protects every editing or agent path.
- [ ] Which retention, processing, and works-council requirements apply to
      prompts, generated output, usage data, and agent-authored branches?

Use the policy owner or approved admin page as the source of truth for your
organisation. Product references:

- [Copilot policies](https://docs.github.com/en/copilot/concepts/policies)
- [Supported policy surfaces](https://docs.github.com/en/copilot/reference/supported-surfaces-for-policies)
- [Content exclusion and its limitations](https://docs.github.com/en/copilot/concepts/context/content-exclusion)
- [Models and GitHub AI credits pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing)
- [Enterprise-managed MCP allowlists](https://github.blog/changelog/2026-08-06-mcp-allowlists-in-enterprise-managed-settings)

Nothing in this workshop assumes any of these are switched on. Every lab has a
path that works when the answer is "no".

### 6. Bring

- A laptop allowed to run the synthetic repository, or the organizer-provided
  managed environment. You do not need permission to install a particular
  editor extension for the offline route.
- Headphones, if a noisy room is hard for you.
- One sanitized, one-sentence problem pattern from your own work, with no code,
  personal data, customer data, secrets, or internal identifiers. You will use
  it only to plan transfer in Lab 7. Use the supplied toy problem instead if
  bringing even a sanitized example is not approved.

### 7. Live-elective eligibility at T-72

- **5A:** the exact approved local server and disposable host configuration are
  connected and smoke-tested.
- **5B:** Copilot CLI is installed, authenticated, policy-enabled, and its
  current permission mechanism is smoke-tested.
- **5C:** the approved chat surface is working; the exercise explicitly attaches
  the scenario-local draft and does not claim automatic activation.

Amber or Red selects captured/local mode before the day. Timed Lab 5 never
installs, authenticates, repairs a proxy, requests policy changes, or treats a
scenario draft as active client configuration.

---

## On the day: 09:00-09:20 landing check

**09:00-09:08 - green light.** In a pair, solo, or with a helper, run:

```bash
python scripts/workshop_doctor.py
python -m pytest -q tests/test_workshop_scenarios_v2.py
```

Share only the pass/fail result unless you choose to show more. The full suite
belongs at T-72. Run it on the day only if pilot evidence shows p95 is under four
minutes on attendee hardware; otherwise it consumes the landing decision window.

**09:08 hard cut - route, do not repair.** If either command fails or is still
running, stop troubleshooting in the main room. Choose one route:

1. the organizer's known-good environment, if already approved;
2. a permitted devcontainer or Codespace;
3. a partner's verified machine, as driver, navigator, or reviewer;
4. the local/captured route, using the static repository artifacts.

Helpers may diagnose in parallel, privately, for at most five minutes. Do not
install packages, repeat sign-in, or change corporate security settings during
the block.

**09:08-09:15 - capability card.** Record `available`, `blocked`, or `unknown`
for local Q&A, planning, editing agent, model selector, and the first relevant
policy owner. A product retry is not required.

**09:15-09:20 - room contract.** Times are 24-hour. Breaks are protected. No
leaderboards. Ask questions in German if that is easier; answers come in English.
The organisers do not collect your working material - no prompts, transcripts,
keystrokes, code, or individual lab work. Optional feedback is a separate,
transparent process. What the assistant processes and retains depends on your
plan and organisation, so apply data minimisation anyway. See
[reference/dach_conventions.md](reference/dach_conventions.md#3-data-protection-datenschutz-and-data-minimisation).

---

## Lanes

| Lane | Complete before 09:15 |
|---|---|
| **Supported** | Name one executable route for the day: your green checkout, an approved organizer environment, a verified partner machine, or captured/offline artifacts. Record any blocker and its owner. |
| **Core** | Supported plus a green local baseline, the client/version and available local roles, the model-selector result, and the policy card above. |
| **Extension** | Map one uncertain capability to its controlling policy, named decision owner, evidence needed, and workshop fallback. Do not spend the landing block enabling it. |

The captured/offline route is not a fourth achievement lane. It is how any lane
continues when a live product, policy, entitlement, or network path is
unavailable.

### Landing acceptance

- [ ] One usable workshop route is named and tested; if it is not your machine,
      your role on that route is explicit
- [ ] The clean-checkout baseline is recorded as green, failed, or not run - never
      implied
- [ ] Live chat answered a synthetic-repository question, **or** the blocker and
      local/captured route are recorded
- [ ] The client/version and model selector are recorded as observed, including
      `Auto`, explicit models, or `unavailable`
- [ ] At least one likely policy or authorization blocker has a named decision
      owner or escalation route
- [ ] You have a scratch file open for evidence notes
      (see [reference/evidence.md](reference/evidence.md))
- [ ] No credential, private URL, production content, or personal data was used
      to prove access

### Cut rules

1. Cut Extension first.
2. At 09:08, cut all live repair and sign-in retries.
3. Do not cut the privacy statement, the route decision, or the honest baseline
   status. Those are the acceptance criteria that protect the rest of the day.

### Resync checkpoint - 09:15

Everyone shows only a Green/Amber/Red route status. Red means "use the approved
fallback", not "explain the failure in public". By 09:15 each participant has a
route and an evidence note; unresolved installation or entitlement work moves to
the named support channel.

### Solo path

Run the same checks and write the same capability card. Replace pair confirmation
with the exact command and observed result. If blocked, notify the organizer
before the day and use the captured/offline route; pairing is optional, not a
learning requirement.

---

## Reflection and retrieval

Write one sentence in your evidence note:

> The capability I am least sure my organisation has enabled is ____, and the way
> I will find out is ____.

You will answer this again at 16:35 in Lab 7.

---

*Next: [Lab 1 - The operator model](lab_01_operator_model.md)*
