# One-day competency map

MittelWerk is not a feature tour. It is a sequence of increasingly independent
repetitions of one engineering loop:

```text
Understand/Plan -> Implement/Test -> Review -> Explain
```

The assistant proposes work; the participant remains accountable for the
decision, evidence, and explanation.

## How the day progresses

```text
OPERATE          SUPERVISE SMALL WORK       SUPERVISE LARGE WORK
Lab 0-1     ->   Lab 2                 ->   Lab 3
ready, choose     diagnose, repair,          plan, batch, preserve
a workflow        test, reject or amend      an external contract

REVIEW UNATTENDED WORK     SPECIALISE       TRANSFER       ADOPT
Lab 4                  ->  Lab 5        ->  Lab 6      ->  Lab 7
review evidence,           test one          run the       choose a safe
not confidence             control boundary  loop alone    Monday action
```

| Lab | New responsibility | Developer and architect application | Minimum useful evidence |
|---|---|---|---|
| [0 - Preflight](lab_00_preflight.md) | Know environment and policy boundary | Developer: executable route. Architect: owner/control route. | Green baseline or named fallback |
| [1 - Operator model](lab_01_operator_model.md) | Choose Ask, Plan, or Agent deliberately | Developer: safe next action. Architect: authority and review cost. | Verified claims and uncertainty |
| [2 - Incident](lab_02_incident_triage.md) | Supervise a bounded repair | Developer: localise/test repair. Architect: assess invariant, blast radius, handover. | Reproduction, focused evidence, reviewed handover |
| [3 - Migration](lab_03_plan_driven_migration.md) | Control multi-file work | Developer: verified batches. Architect: contract, ordering, rollback. | Edited plan, verified batch, contract comparison |
| [4 - Review](lab_04_review_and_delegation.md) | Judge unattended work | Developer: actionable findings. Architect: scope, control, merge accountability. | Prioritised findings, comparison, decision |
| [5 - Elective](lab_05_elective.md) | Test one control boundary | Developer: predict/run behavior. Architect: policy owner and residual risk. | Positive and negative observations |
| [6 - Capstone](lab_06_capstone_transfer.md) | Run the loop independently | Builder or supervising architect; both change/test/review concrete artifacts. | Tested slice, review, private self-score, uncertainty |
| [7 - Close](lab_07_close_and_adoption.md) | Transfer the method to work | One shared habit plus team/owner decisions. | Dated action, decision, externally owned ask |

Developers and architects follow the same sequence and produce the same evidence.
Developers usually emphasise implementation correctness and operability;
architects usually emphasise contracts, authority, reversibility, and review
load. Neither role has a prose-only exemption: both perform an Implement/Test
action, review concrete evidence, and explain uncertainty.

## The large-codebase rule: map, verify, stop

This repository is intentionally larger than anyone should read during a timed
lab. The skill is not remembering the whole system. It is using GitHub Copilot or
another repository-aware workflow to build the **smallest evidence map** that
supports the next decision:

1. Ask for named files, symbols, contracts, tests, and consumers relevant to one
   question; require references and unknowns.
2. Verify the important links in code or with a focused command. A repository map
   is a hypothesis until you check it.
3. Stop expanding the map when it supports the next reversible action. Record
   adjacent risk as uncertainty instead of reading the repository without a
   bound.

The scenario `work/` directories isolate attendee edits so reset stays safe; they
do not turn the exercises into toy problems. The diagnosis and review evidence
still crosses tickets, invariants, implementation, tests, serialised contracts,
and downstream consumers. This is the practical advantage of Copilot in a large
codebase: no participant, including an architect, needs a complete mental model
before making one well-evidenced decision.

## The run card for every timed lab

1. **Outcome:** say what capability this lab adds.
2. **Invariant:** identify what must remain true.
3. **Artifact:** know where the work and evidence belong.
4. **Timebox:** stop the current phase when its time expires.
5. **Evidence:** record what was observed, not what was intended.
6. **Resync:** verify once, archive/reset, and rejoin the room.

Completion is not the only successful outcome. A participant who cannot complete
one phase should still practise the later phases on the incomplete attempt. For
scenario labs, the runner prints an answer-neutral continuation route:

```bash
python scripts/workshop.py resync <scenario-id> --blocked-at implement-test
```

Valid phases are `tooling`, `understand-plan`, `implement-test`, `review`, and
`explain`. The command does not add a solution or change acceptance. It tells the
participant how to preserve evidence, continue with the remaining loop stages,
and reset in time for the next lab.

## What remains constant

- Supported, Core, and Extension are achievement lanes through the same
  objective; each has its own evidence boundary.
- Live, local, and captured/offline are delivery modes orthogonal to achievement.
  Captured work can preserve engineering judgement but never counts as operating
  a live product surface.
- A failing verifier can be honest evidence; weakening acceptance cannot.
- No participant should miss the next lab while trying to rescue a low-value
  environment or tooling problem.
- Reset archives the attempt before restoring the known-good state.

Detailed timings remain in the [labs index](README.md). Scenario commands and
fallbacks are in [scenario tooling](reference/scenario_tooling.md).
