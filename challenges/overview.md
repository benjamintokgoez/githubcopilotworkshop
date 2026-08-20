# One-day competency map

QuantCore is not a feature tour. It is a sequence of increasingly independent
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

| Lab | New responsibility | Minimum useful evidence |
|---|---|---|
| [0 - Preflight](lab_00_preflight.md) | Know the environment and policy boundary | Green baseline or a named fallback |
| [1 - Operator model](lab_01_operator_model.md) | Choose Ask, Plan, or Agent deliberately | Verified claims and an uncertainty statement |
| [2 - Incident](lab_02_incident_triage.md) | Supervise a bounded repair | Reproduction, focused evidence, reviewed handover |
| [3 - Migration](lab_03_plan_driven_migration.md) | Control multi-file work | Edited plan, verified batches, contract comparison |
| [4 - Review](lab_04_review_and_delegation.md) | Judge work you did not watch being produced | Prioritised findings and a decision |
| [5 - Elective](lab_05_elective.md) | Test one control boundary | Positive and negative observations |
| [6 - Capstone](lab_06_capstone_transfer.md) | Run the loop independently | Small change, tests, review, honest uncertainty |
| [7 - Close](lab_07_close_and_adoption.md) | Transfer the method to work | One bounded action and its approval path |

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

- Supported, Core, and Extension are routes through the same objective.
- Captured/offline work replaces unavailable product behavior, not engineering
  judgement.
- A failing verifier can be honest evidence; weakening acceptance cannot.
- No participant should miss the next lab while trying to rescue a low-value
  environment or tooling problem.
- Reset archives the attempt before restoring the known-good state.

Detailed timings remain in the [labs index](README.md). Scenario commands and
fallbacks are in [scenario tooling](reference/scenario_tooling.md).
