# QuantCore - a one-day workshop in supervised agentic engineering

QuantCore is a **simulated** quantitative trading engine written in Python. It
exists for one purpose: to give professional engineers a realistic system in which
to practise working with agentic AI tooling under supervision - incidents,
migrations, reviews, and handovers that look like the ones they already have at
work.

This is **not** a tour of GitHub Copilot features. It is a day of engineering
practice in which the assistant is one participant and you are accountable for the
result.

> **Simulation notice.** QuantCore is teaching software. The market data is
> generated and the risk analytics are simplified. Familiar real-world reference
> instruments and symbols may appear so the domain reads naturally, but every
> price, order, position, event, and scenario in this repository is simulated and
> describes no real market, issuer, or venue.
> **Nothing here is investment advice**, and no output of this workshop should be
> used to make trading decisions.

---

## The loop

```
Understand/Plan -> Implement/Test -> Review -> Explain
```

Every lab is one or more turns of this loop. By the end of the day you should be
running it without being prompted, and be able to teach it to a colleague.

---

## Audience

**Who this is for:** practising software engineers, tech leads, and architects who
already write and review production code, primarily in Europe and specifically in
the DACH region. Comfort with Python helps, but the labs are about engineering
judgement, not Python trivia.

**Who this is not for:** people new to programming, people looking for an
introduction to what an AI assistant is, or teams wanting a procurement demo.

**Assumed experience:** you have debugged something in an unfamiliar codebase, you
have reviewed someone else's pull request, and you have opinions about tests.

**Language:** English throughout, written plainly for a mixed-proficiency
international audience. Questions in German are welcome; answers come in English
so the whole room benefits. German terms appear only where they are operationally
useful - see
[challenges/reference/glossary_en_de.md](challenges/reference/glossary_en_de.md).
For reproducibility, the simulator uses `de-DE`, EUR, and `Europe/Berlin`; the
[DACH conventions](challenges/reference/dach_conventions.md) explicitly note
where Austrian and Swiss production requirements differ.

**Domain knowledge is not assessed.** Every financial rule and expected number you
need is written down in
[challenges/reference/invariants.md](challenges/reference/invariants.md).

---

## Learning outcomes

By the end of the day you can:

1. Choose deliberately between an **Ask**, **Plan**, and **Agent** workflow, and
   justify the choice.
2. Choose a model as a decision, not a habit: complexity, latency, policy,
   credits, and evidence needs. **No model names are prescribed anywhere in this
   material.**
3. Provide **durable context** - repository instructions, task briefs, invariants -
   instead of retyping constraints into every prompt.
4. **Supervise implementation**: bound scope, checkpoint, interrupt, and reject.
5. Produce **evidence** a reviewer accepts: a test that fails before and passes
   after, and a diff you can justify file by file.
6. **Review work you did not write**, including unattended agent output.
7. **Explain uncertainty** in three parts: what you verified, what you assumed,
   what could still be wrong.
8. **Transfer** the loop to your own repository, with a written plan for the
   following week.

---

## Scope: one day, and what that excludes

This is a **single-day** workshop. That is a design decision, not a limitation to
apologise for: one day is enough to build one loop to competence, and adding
surfaces converts practice time into demonstration time.

**In scope:** the loop, workflow selection, durable context, supervision, testing,
review of unattended work, one elective, and transfer to your own work.

**Explicitly out of scope for the core day:** delegation at scale, agents in CI,
custom agent authoring, internal-system MCP integrations, and adoption measurement.
These are described in
[challenges/appendix_two_day.md](challenges/appendix_two_day.md), which
facilitators should not open before 17:00.

---

## Agenda (one day)

All times are 24-hour, local workshop time (Europe/Berlin: CET in winter, CEST in
summer). **Sixty minutes of the day are protected slack** - they exist so that
overruns, questions, and human beings are survivable.

| Time | Block | Duration |
|---|---|---|
| 09:00-09:20 | [Lab 0](challenges/lab_00_preflight.md) - landing check, recovery lane, room contract | 20 min |
| 09:20-10:00 | [Lab 1](challenges/lab_01_operator_model.md) - operator model and worked example | 40 min |
| 10:00-10:15 | Break | 15 min |
| 10:15-11:20 | [Lab 2](challenges/lab_02_incident_triage.md) - guided authentic incident | 65 min |
| 11:20-11:45 | **Slack A** - recovery and resync | 25 min |
| 11:45-12:30 | Lunch | 45 min |
| 12:30-13:40 | [Lab 3](challenges/lab_03_plan_driven_migration.md) - plan-driven legacy migration | 70 min |
| 13:40-13:55 | Break | 15 min |
| 13:55-14:40 | [Lab 4](challenges/lab_04_review_and_delegation.md) - human review plus captured automated comparison | 45 min |
| 14:40-15:00 | **Slack B** - recovery and resync | 20 min |
| 15:00-15:35 | [Lab 5](challenges/lab_05_elective.md) - one bounded elective | 35 min |
| 15:35-15:45 | Break | 10 min |
| 15:45-16:35 | [Lab 6](challenges/lab_06_capstone_transfer.md) - capstone, individual | 50 min |
| 16:35-17:00 | [Lab 7](challenges/lab_07_close_and_adoption.md) - retrieval and one-action adoption | 25 min |
| 17:00-17:15 | **Slack C** - questions and quiet completion | 15 min |

Each lab has a **resync checkpoint** where the whole room stops and can return to a
known-good state, and three **achievement lanes** (Supported, Core, Extension).
Live, local, and captured/offline are delivery modes, not achievement levels.
Lane evidence is stated separately from whether a live product surface was
operated.

---

## Prerequisites - honestly stated

**Required:**

- **Python 3.12.x** - the workshop baseline the platform is built and verified
  against - plus `git` and an editor, or an organizer-provided approved
  environment containing them. Newer minor versions are not supported for the
  workshop day; check with `python --version` before you install anything else.
- A machine permitted to run the provided synthetic repository, or a managed
  workshop environment. The offline route does not require installing a
  particular editor extension.
- **60-90 minutes for a cold-machine preflight**, completed by T-72 hours. A
  prepared managed image may take less.

**Expected for the primary live route, but not required for the learning
outcomes:** active GitHub Copilot access under either a personal plan or a plan
managed by your organisation. What you can actually do differs by entitlement
and policy, and both change over time - the current picture is in the
[feature availability matrix](https://docs.github.com/en/copilot/reference/copilot-feature-matrix)
and
[billing and pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing),
not in this README. If access is absent or blocked, use the local/captured lane;
do not bypass policy or spend the lab troubleshooting sign-in in public.

**Helpful but not required:**

- Familiarity with Python type hints and `pytest`.
- Access to a repository of your own to think about during Lab 7.

**Not required, and never assumed:**

- Any specific AI model. Use **Auto** or a model your administrator has approved.
  See
  [challenges/reference/model_selection.md](challenges/reference/model_selection.md).
- The cloud agent, Copilot code review, MCP servers, or Copilot CLI. Each appears
  in exactly one place, always with a fallback.
- Any knowledge of finance, trading, or derivatives.

---

## Preflight - exact steps

Do this **before** the workshop day. Full detail, including the policy checklist,
is in [challenges/lab_00_preflight.md](challenges/lab_00_preflight.md).

```bash
git clone <repo-url>
cd githubcopilotworkshop

python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\Activate.ps1    # Windows PowerShell

pip install -e ".[dev]"

python scripts/workshop_doctor.py    # environment and repository structure
pytest -q                            # the test baseline
```

`workshop_doctor.py` checks your Python version, that the expected dependencies
import, that the repository, `settings.yaml`, and `instruments.json` have the
structure the labs assume, and it reports environment hints - including whether
relevant variables are set, never their values. It does **not** run the test
suite, generate sample data, or check anything inside your IDE. Those are
separate steps, which is why `pytest -q` is listed above and the IDE check below.

**Expected result: a clean checkout has a passing baseline.** `python
scripts/workshop_doctor.py` reports no failures **and** `pytest -q` is green. Both
are required; neither one alone is the baseline. If anything fails - a doctor
check, a test, an import, or collection - your environment needs
attention before the day. Do not assume a red result is "workshop material": the
failing checks you will work on appear only **after** you start a scenario with
`python scripts/workshop.py start <scenario-id>`, and the scenario tooling tells
you when it has changed your working tree.

If you plan to use the live route, check Copilot **by hand, in your IDE** - no
script can do this for you. Confirm whether Copilot Chat answers a question about
this repository and record which models and workflows (Ask, Plan, Agent) are
actually available. An unavailable or policy-blocked result selects the
local/captured lane; it does not fail the repository preflight.

---

## Supported modes

| Mode | What it means | Fully supported? |
|---|---|---|
| **In-person cohort** | Facilitated, pairs, shared resync checkpoints | Yes - this is the primary design |
| **Remote cohort** | Same agenda, pairs in breakout rooms, resync in the main room | Yes |
| **Pair mode** | Your environment is broken, so you work on your partner's machine as navigator and reviewer | Yes - a full-value path, not a consolation prize |
| **Solo, self-paced** | Every lab has a "Solo path" section with adjusted timings | Yes |
| **Offline / restricted network** | Local scenarios and sanitized captures replace live product calls | Yes - every lab keeps the same learning objective, with less live-product practice |
| **No cloud agent** | The cloud agent is disabled or unavailable | Yes - it is bonus material in exactly one lab |
| **Air-gapped, no Copilot at all** | No live assistant is available | Yes as a captured/reviewer route for the engineering loop, but not equivalent hands-on product practice; the facilitator states that limitation explicitly |

---

## Policy checklist

Answer these for your own organisation before the day. "I do not know" is a valid
answer and often the most useful thing an attendee brings.

- [ ] Which Copilot plan or entitlement is assigned to me, and who manages it?
- [ ] Which models appear in my picker?
- [ ] Is the **cloud agent** enabled for me, and for which repositories?
- [ ] Is **Copilot code review** enabled?
- [ ] Are **MCP servers** allowed, and does the supported client receive the
      enterprise `managed-settings.json` allowlist? Treat a private registry as
      preview and weaker enforcement; check cloud-agent MCP separately.
- [ ] Can I install **Copilot CLI** on this machine?
- [ ] What **GitHub AI Credits** allowance, paid-usage policy, or stop rule
      applies?
- [ ] Are there **content exclusion** rules on my work repositories?
- [ ] Has our works council (Betriebsrat) agreed how usage data may be used?

Live references (revalidate before delivery):
[policies](https://docs.github.com/en/copilot/concepts/policies) ,
[feature availability](https://docs.github.com/en/copilot/reference/copilot-feature-matrix) ,
[content exclusion](https://docs.github.com/en/copilot/concepts/context/content-exclusion) ,
[billing and pricing](https://docs.github.com/en/copilot/reference/copilot-billing/models-and-pricing) ,
[enterprise agent management](https://docs.github.com/en/copilot/concepts/agents/enterprise-management).

The current-product statements in this curriculum were reconciled against
official sources **as of 2026-08-25**. Plans, previews, policies, client support,
and billing can change. The maintenance path is
[workshop/ops/RELEASE_CHECKLIST.md](workshop/ops/RELEASE_CHECKLIST.md): revalidate
the release manifest two weeks before delivery and use the captured route when a
surface differs.

**Nothing in this workshop assumes a feature is enabled for you.** If a step is
blocked by policy, record it as a finding and take it to Lab 7's adoption list.

---

## Privacy, governance, and the room

- **No workshop collection of working material.** The organisers and
  facilitators do not gather prompts, transcripts, keystrokes, code, or
  individual lab work, and no individual artifact or rubric score is kept by
  them. Lab 6 uses private self/peer scoring; a facilitator may give feedback on
  an artifact you choose to show in the room, without recording it. Optional
  feedback must state separately what it collects and why. Any further
  collection your organisation might want is its own decision and needs a
  documented purpose, transparency towards the people affected, an appropriate
  lawful basis, and whatever privacy and works-council review its policy
  requires. Which lawful basis fits is a question for your privacy function, not
  for this README.
- **That is a statement about us, not about the tooling.** The assistant you use
  is a product: what it processes, transmits, and retains is governed by your
  GitHub plan and your organisation's settings, not by this workshop. Check them
  before you decide what is safe to type -
  [Copilot policies](https://docs.github.com/en/copilot/concepts/policies),
  [content exclusion](https://docs.github.com/en/copilot/concepts/context/content-exclusion),
  [enterprise AI governance](https://docs.github.com/en/copilot/get-started/enterprise-ai-governance).
- **Data minimisation applies to prompts.** Do not paste personal data, customer
  data, production secrets, or internal documents into any prompt during this
  workshop.
- **Works council and co-determination** (Betriebsrat, Mitbestimmung) are treated
  as real constraints, not obstacles, throughout the material.
- **EU AI Act literacy** is framed as organisational governance - traceability and
  human oversight - and explicitly **not as legal advice**. Classification
  questions belong to your legal and compliance function.
- **Accessibility:** no lab depends on seeing a screenshot, no instruction depends
  on colour alone, and all times are stated aloud and in writing.
- **Psychological safety:** no leaderboards, no rankings, no screen sharing without
  agreement. Asking for help is a step in the loop.

Details:
[challenges/reference/dach_conventions.md](challenges/reference/dach_conventions.md).

---

## Delivery contract

Use a tagged checkout for a delivery. A clean checkout must pass both the doctor
and the test suite before any scenario is started; a red baseline is a repository
or environment defect, not workshop material.

| Area | Included contract |
|---|---|
| Attendee curriculum (`README.md`, `challenges/`) | One-day Supported/Core/Extension journeys, no fixed model names, no answer keys |
| Runtime (`qxm/`), tests, tooling, dashboard | Python 3.12 baseline, simulated trading engine, `de-DE`/`en-GB` presentation with explicit DACH scope, healthy tests |
| Scenario system (`workshop/scenarios/`, `workshop/fallbacks/`, `scripts/workshop.py`) | Seven deterministic scenarios, exact reset with participant-work archive, captured offline fallbacks |
| Preflight tooling (`scripts/workshop_doctor.py`) | Environment, dependency, configuration, and workshop-structure checks without reading secret values |
| Facilitator and operations material (`workshop/ops/`) | Matching agenda plus accessibility, privacy, works-council, assessment, and recovery guidance |
| Technical documentation (`ARCHITECTURE.md`, `docs/`) | Runtime architecture, REST/MCP contracts, and domain terminology |

There is **no `proctor/` directory** and there are no solution guides, answer keys,
or `BUG` maps in this repository. That is deliberate: the labs teach a method, and
published answers destroy the exercise. Facilitator guidance lives in the
operations material, and it deliberately contains prompts to *ask*, not solutions
to *reveal*.

Every lab has a Solo path and a non-live fallback. Optional cloud capabilities
can improve the experience, but none sits on the critical path.

---

## Repository layout

```
githubcopilotworkshop/
  qxm/                  Main package: core matching, risk, data, strategy,
                        auth, API, MCP server, utilities
  tests/                Test suite
  challenges/           The workshop: labs, hints, shared references
  dashboard/            Trading dashboard frontend
  scripts/              Data generation and workshop tooling
  docs/                 API reference and domain glossary
  workshop/ops/         Facilitator, accessibility, privacy and recovery material
  main.py               Application entry point
  settings.yaml         Configuration
  instruments.json      Instrument definitions
```

Architecture detail: [ARCHITECTURE.md](ARCHITECTURE.md). Contribution guidelines:
[CONTRIBUTING.md](CONTRIBUTING.md).

**Facilitators:** delivery, accessibility, privacy, and recovery material lives in
`workshop/ops/`, and it follows the same agenda, block names, and loop as this
curriculum. Start with `workshop/ops/FACILITATOR_GUIDE.md` and
`workshop/ops/PREFLIGHT.md`.

---

## Start here

1. Read the [one-day competency map](challenges/overview.md).
2. Read the [labs index](challenges/README.md).
3. Complete [Lab 0 - Preflight](challenges/lab_00_preflight.md) **before** the day.
4. Skim
   [challenges/reference/invariants.md](challenges/reference/invariants.md) so you
   know where the numbers live. You are not expected to memorise them.

---

## Licence

MIT. A workshop repository intended for educational use.
