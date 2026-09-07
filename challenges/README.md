# Labs - supervised agentic engineering (one day)

This directory holds the attendee-facing labs for the MittelWerk workshop. It is a
one-day, hands-on curriculum for junior through senior professional engineers,
tech leads, and architects who already write and review production code. It is
not a feature tour of GitHub Copilot or an introduction to programming.

All times are in 24-hour format and refer to local workshop time (Europe/Berlin,
CET in winter and CEST in summer). The workshop language is English, written
plainly for a mixed-proficiency international audience. German terms appear only
where they are operationally useful in a DACH workplace.

## The loop you practise all day

```
Understand/Plan -> Implement/Test -> Review -> Explain
```

Every lab is one or more turns of this loop. You stay the operator: you decide
what gets attempted, what evidence is enough, and what you are willing to sign
your name to. The word "supervised" is the point of the day.

## Mission

By 17:15 you should be able to:

1. Choose deliberately between an **Ask**, **Plan**, and **Agent** workflow for a
   given task, and say why.
2. Supply **durable context** (repository instructions, task briefs, invariants,
   reproduction steps) instead of re-typing context into every prompt.
3. **Supervise implementation**: scope changes, checkpoint, interrupt, and reject.
4. **Test** the change with evidence a reviewer would accept.
5. **Review** generated work, including work you did not watch being produced.
6. **Explain uncertainty**: state what you verified, what you assumed, and what
   could still be wrong.
7. **Transfer the loop** to your own repository on the next working day.

## Lab sequence

Start with the [one-day competency map](overview.md). It shows how responsibility
progresses from workflow choice, through supervised implementation and review, to
independent transfer. The table below is the timed delivery sequence.

Want a quick view of the simulator before Lab 2? The optional
[simulator walkthrough](../docs/SIMULATOR_WALKTHROUGH.md) starts with a
two-to-three-minute captured example. Use it before a solo timer starts or in
released cohort slack, not instead of a lab phase. Live execution is optional;
keep runtime/dashboard exploration separate from scenario `work/` edits.

Complete [Lab 0 preflight](lab_00_preflight.md) before the day. The
[landing check](lab_00_preflight.md#on-the-day-0900-0920-landing-check) is only a
short confirmation, not an installation session.

<!-- journeys:agenda:start -->
| Time | Block | Duration |
|---|---|---|
| 09:00-09:20 | [Lab 0 - Preflight and landing](lab_00_preflight.md) | 20 min |
| 09:20-10:00 | [Lab 1 - Operator model](lab_01_operator_model.md) | 40 min |
| 10:00-10:15 | **Protected break** | 15 min |
| 10:15-11:20 | [Lab 2 - Guided incident](lab_02_incident_triage.md) | 65 min |
| 11:20-11:45 | **Slack A - recovery and rejoin** | 25 min |
| 11:45-12:30 | **Protected lunch** | 45 min |
| 12:30-13:40 | [Lab 3 - Plan-driven migration](lab_03_plan_driven_migration.md) | 70 min |
| 13:40-13:55 | **Protected break** | 15 min |
| 13:55-14:40 | [Lab 4 - Review unattended work](lab_04_review_and_delegation.md) | 45 min |
| 14:40-15:00 | **Slack B - recovery and rejoin** | 20 min |
| 15:00-15:35 | [Lab 5 - Choose one elective](lab_05_elective.md) | 35 min |
| 15:35-15:45 | **Protected break** | 10 min |
| 15:45-16:35 | [Lab 6 - Independent capstone](lab_06_capstone_transfer.md) | 50 min |
| 16:35-17:00 | [Lab 7 - Close and next action](lab_07_close_and_adoption.md) | 25 min |
| 17:00-17:15 | **Slack C - questions or quiet completion** | 15 min |
<!-- journeys:agenda:end -->

Full timing, including breaks and the 60 minutes of protected slack, is in the
[workshop README](../README.md#agenda-one-day).

Extension material that is deliberately **out of scope** for the one-day core is
in [appendix_two_day.md](appendix_two_day.md). Do not start it during the core day.

If one phase blocks progress, do not spend the rest of the lab rescuing it. For
Labs 2-6, use `python scripts/workshop.py resync <scenario-id> --blocked-at
<phase>` to continue with the remaining loop stages, then verify and reset at the
room checkpoint. The route preserves honest evidence and never inserts a solution.

## Self-paced route

Use the same labs, lane criteria, and evidence as the cohort. **T+0 means the
start of your current lab**, not 09:00. Each run card pairs elapsed minutes with
the room clock; use the elapsed column and ignore the time of day.

1. Complete Lab 0 setup first. Then follow Labs 1-4, **one** Lab 5 elective,
   Lab 6, and Lab 7. Allow the run-card duration for each; breaks are extra.
2. Choose Supported, Core, or Extension separately from `live`, `local`, or
   `captured/offline`. Working alone does not require a live assistant or a
   higher lane.
3. Start the phase timer only when the required artifacts are open. Pause
   between phases if needed. Keep the phase cuts: when implementation time
   ends, practise Review and Explain on the result you actually have.
4. Replace a partner with two distinct passes. Save the proposal, close the
   chat or implementation view, pause briefly, then challenge it from the diff
   and observed checks. Write both the operator and reviewer observations.
5. Before a longer break, record the lab, phase, last check, and next action.
   For an active scenario, verify and reset to archive the attempt. Use the
   [pause and return commands](reference/scenario_tooling.md#pause-and-return)
   later; do not leave an editing agent running unattended.
6. Use **Next** to move forward or **Return** to revisit the previous lab.
   Complete the later phases before spending another session on an incomplete
   repair. Lab 7 keeps your dated return-later plan.

No facilitator? Use the captured input in Lab 1 and the shipped review package
in Lab 4. After your elective, read one unchosen elective's control table and
write `control / negative case / limitation`; this is awareness, not completion
of that elective. Keep Lab 6 individual and the rubric private.

## Terms used in the labs

- **Invariant:** a rule that must stay true, such as “hours cannot be negative”.
- **Contract:** behaviour that another part of the system relies on, such as
  accepted inputs, field names, units, or error types.
- **Bounded:** limited to named files, one behaviour, and a clear stop point.
- **Blast radius:** what else a change or permission could affect.
- **Resync:** stop, save honest evidence, and return to a known state. In a
  cohort, rejoin the room; alone, prepare for the next phase or lab.
- **Regression check:** a check that fails on the original problem and passes
  after the repair.
- **Adversarial check:** a safe test that tries to disprove an important claim.

No industrial-equipment knowledge is assumed. The [invariants](reference/invariants.md)
provide the domain rules; the [EN/DE glossary](reference/glossary_en_de.md)
explains operational terms.

## Maintaining run cards

[workshop/journeys.json](../workshop/journeys.json) is the source for lab IDs,
documents, scenarios, clocks, cuts, evidence paths, and routes. Author-written
instructions remain Markdown outside the `journeys` markers.

After changing the definition, run:

```bash
python scripts/workshop_journeys.py
python scripts/workshop_journeys.py --check
```

The second command makes no changes and fails if a generated run card, agenda,
or facilitator cut table has drifted. It also checks retained Markdown timing
tables, block headings, and paired elapsed/cohort clocks in the labs and hints.
Edit the definition, not generated text; update author-written timing references
when the check identifies a mismatch.

## Achievement lanes and delivery modes

Every lab offers three lanes. Choose per lab, not once for the day. Changing lanes
mid-lab is normal and carries no penalty.

| Lane | What it proves | What changes |
|---|---|---|
| **Supported** | The same competency on a narrower artifact, with evidence from every loop stage | Fewer lane-specific acceptance items; the full Core verifier may legitimately remain red |
| **Core** | The complete scenario and evidence contract | Full task, full evidence note, and the stated Core verifier |
| **Extension** | Additional depth after Core evidence exists | One harder constraint or transfer question |

The lanes are not seniority labels. Supported reduces breadth without removing
the engineering loop, Core is the prepared default, and Extension protects the
timebox when experienced participants finish early. Architects do not receive a
prose-only route: they still change or test a concrete artifact.

Separately record the delivery mode as `live`, `local`, or `captured/offline`,
and whether a live product surface was operated. Captured work can demonstrate
Core engineering judgement; it does not prove live product operation. The
**lane-specific acceptance criteria** in each lab define the bar. Speed and
product access are never the bar.

## Hints

Each lab links a three-level hint ladder in [hints/](hints/). Hints are kept in
separate files, and each level is collapsed, so you can take exactly the help you
need and no more.

| Level | Gives you | Never gives you |
|---|---|---|
| L1 Orientation | Where to look, what question to ask first | The location of the defect |
| L2 Method | Which loop step you are skipping, which technique fits | The change to make |
| L3 Structure | The shape of a good plan, test, or review note | A copy-paste prompt or the answer |

There is no hint level that hands you a solution, and no `BUG` map anywhere in this
repository. If you feel stuck after L3, that is a signal to ask a human, not a
signal that you failed.

## Shared references

| File | Use it for |
|---|---|
| [reference/invariants.md](reference/invariants.md) | Every financial rule and expected number you need. Domain knowledge is **not** assessed. |
| [reference/model_selection.md](reference/model_selection.md) | How to choose a model without memorising model names |
| [reference/dach_conventions.md](reference/dach_conventions.md) | Time, number, privacy, governance and accessibility conventions |
| [reference/evidence.md](reference/evidence.md) | The evidence and uncertainty template used by every lab |
| [reference/scenario_tooling.md](reference/scenario_tooling.md) | Scenario commands, artifacts, resets, and offline fallbacks |
| [reference/glossary_en_de.md](reference/glossary_en_de.md) | Short EN/DE glossary of operational terms |

## Ground rules

- **This is a simulation.** MittelWerk is a teaching codebase. Every company,
  asset, provider, work order, rate, and telemetry reading is synthetic.
- **No fixed model names.** Use **Auto** or a model your administrator has
  approved and made available to you. See
  [reference/model_selection.md](reference/model_selection.md).
- **Local Agent is not the cloud agent.** Lab 4 explains the difference. Live
  cloud results are always a bonus, never a dependency.
- **Data minimisation applies to prompts too.** Do not paste personal data,
  customer data, production secrets, or internal documents into any prompt during
  this workshop. See [reference/dach_conventions.md](reference/dach_conventions.md).
- **No workshop collection of working material.** Facilitators and organisers do
  not gather prompts, transcripts, keystrokes, code, or individual lab work, and
  no individual artifact or rubric score is kept by them. Lab 6 scoring is
  private self/peer feedback; a facilitator may comment on an artifact you
  choose to show without recording it. Optional feedback states separately what
  it collects and why. Any further collection your organisation wants needs a
  documented purpose, transparency, an appropriate lawful basis, and the privacy
  and works-council review its own policy requires - a decision for your privacy
  function, not for this workshop.
- **That says nothing about the tooling.** What the assistant transmits,
  processes, and retains is determined by your GitHub plan and your
  organisation's settings, not by this workshop - which is exactly why the
  data-minimisation rule above applies regardless. See
  [reference/dach_conventions.md](reference/dach_conventions.md#3-data-protection-datenschutz-and-data-minimisation).
- **Psychological safety.** No leaderboards, no public rankings, no
  screen-sharing without your agreement. Asking for help is an expected move in the
  loop, not an exception to it.
