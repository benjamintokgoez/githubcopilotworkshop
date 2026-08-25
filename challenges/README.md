# Labs - supervised agentic engineering (one day)

This directory holds the attendee-facing labs for the QuantCore workshop. It is a
one-day, hands-on curriculum for professional engineers who already write and
review production code. It is not a feature tour of GitHub Copilot.

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

| Time | Lab | Focus | Mode |
|---|---|---|---|
| before the day | [Lab 0 - Preflight](lab_00_preflight.md) | Environment, access, policy | Individual |
| 09:00-09:20 | [Lab 0 - Landing](lab_00_preflight.md#on-the-day-0900-0920-landing-check) | Confirm preflight, recover stragglers | Individual |
| 09:20-10:00 | [Lab 1 - Operator model](lab_01_operator_model.md) | Worked example of the loop | Pairs |
| 10:15-11:20 | [Lab 2 - Guided incident](lab_02_incident_triage.md) | Authentic incident, end to end | Pairs |
| 12:30-13:40 | [Lab 3 - Plan-driven migration](lab_03_plan_driven_migration.md) | Contract-preserving migration under a plan | Pairs |
| 13:55-14:40 | [Lab 4 - Review and delegation](lab_04_review_and_delegation.md) | Human review plus captured automated comparison | Pairs |
| 15:00-15:35 | [Lab 5 - Elective](lab_05_elective.md) | Exactly one bounded elective | Pairs or solo |
| 15:45-16:35 | [Lab 6 - Capstone](lab_06_capstone_transfer.md) | Unseen, domain-light transfer task | Individual |
| 16:35-17:00 | [Lab 7 - Close](lab_07_close_and_adoption.md) | Retrieval and one-action adoption | Whole room |

Full timing, including breaks and the 60 minutes of protected slack, is in the
[workshop README](../README.md#agenda-one-day).

Extension material that is deliberately **out of scope** for the one-day core is
in [appendix_two_day.md](appendix_two_day.md). Do not start it during the core day.

If one phase blocks progress, do not spend the rest of the lab rescuing it. For
Labs 2-6, use `python scripts/workshop.py resync <scenario-id> --blocked-at
<phase>` to continue with the remaining loop stages, then verify and reset at the
room checkpoint. The route preserves honest evidence and never inserts a solution.

## Achievement lanes and delivery modes

Every lab offers three lanes. Choose per lab, not once for the day. Changing lanes
mid-lab is normal and carries no penalty.

| Lane | What it proves | What changes |
|---|---|---|
| **Supported** | The same competency on a narrower artifact, with evidence from every loop stage | Fewer lane-specific acceptance items; the full Core verifier may legitimately remain red |
| **Core** | The complete scenario and evidence contract | Full task, full evidence note, and the stated Core verifier |
| **Extension** | Additional depth after Core evidence exists | One harder constraint or transfer question |

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

- **This is a simulation.** QuantCore is a teaching codebase. Nothing here is
  investment advice, and no output of this workshop should be used to trade.
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
