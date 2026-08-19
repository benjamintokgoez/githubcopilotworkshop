# Lab 3 - Plan-driven migration of a legacy model layer

**Block:** 12:30-13:55 (85 minutes) - **Mode:** pairs
**Loop stages:** Understand/Plan (heavily) -> Implement/Test -> Review -> Explain
**Scenario:** `migration-legacy-models`

---

## Outcome

You run a multi-file migration the way it should be run: a written plan you edited
before execution, a captured baseline, batched execution with verification between
batches, and a change whose external contract is provably unchanged.

This is the lab where **Agent earns its place** - and where an unsupervised Agent
session does the most damage. Both lessons land in the same 85 minutes.

---

## Set up

```bash
python scripts/workshop.py start migration-legacy-models
python scripts/workshop.py status
python scripts/workshop.py verify migration-legacy-models  # expected to fail; capture it
```

The scenario stages a **legacy model surface**: a set of modules still written
against the old validation-library idioms, plus the code that consumes them. The
scenario manifest lists which files are in scope. Do not assume the file list from
another attendee's screen or from a previous run - read your manifest.

No tooling? See the "Solo path" section below.

> The repository is green before `start`, and the scenario is what stages the
> legacy surface. Capture the acceptance and test output straight after `start` -
> that is the state your migration has to end at least as healthy as. See
> [reference/scenario_tooling.md](reference/scenario_tooling.md#the-healthy-baseline-contract).

Work only in `workshop/scenarios/migration-legacy-models/work/`. Create
`MIGRATION_NOTES.md` there for the baseline, edited plan, ambiguity decision,
batch checkpoints, contract comparison, and handover. Reset archives that
participant-added file with the code attempt.

---

## Artifacts you are working from

| Artifact | What it is |
|---|---|
| `issue.md` | A migration request written by a tech lead: the reason (support window ending), the constraint (no behaviour change), and the deadline |
| Staged legacy modules | The in-scope files, listed in the scenario manifest |
| `acceptance.md` | The contract checks the migration must satisfy |

The request is deliberately underspecified in one respect. Finding what is missing
and deciding it explicitly is part of the planning work.

---

## Business invariant at stake

**The external contract does not change.**

- Serialised field names, nesting, and types stay identical.
- Inputs that were rejected before are still rejected, with an error a caller can
  act on. Inputs that were accepted are still accepted.
- **INV-TIME-1**: timestamps remain timezone-aware UTC after a round trip.
- **INV-FMT-1**: numeric values are serialised with a dot decimal separator. A
  migration that "helpfully" localises numbers into `1.234,56` inside a payload has
  broken every consumer.
- **INV-VAR-1** and **INV-GREEK-1** still hold for anything the models feed. Sign
  conventions are contract, not style.

See [reference/invariants.md](reference/invariants.md).

---

## Run the loop

### 1. Capture the baseline first (10 minutes)

Before a single line changes, capture what "unchanged" means. Suggestions:

- Serialise a representative instance of each in-scope model and save the output.
- Record the current test results, including which tests fail today.
- Note the public import paths that other modules rely on.

A migration without a captured baseline cannot be verified, only believed. This
step is where most of today's real-world transfer value sits.

### 2. Plan - and edit the plan (15 minutes)

Use the **Plan** workflow. Ask for a migration plan that covers the in-scope files,
the idiom-by-idiom mapping, the order of work, and the verification after each
step.

Then **edit it**, which is the actual exercise. Check the plan for:

- **Scope**: does it list files the manifest does not? Delete them.
- **Batching**: is it one giant step, or steps you can verify independently? Split
  anything you cannot verify in under five minutes.
- **Ordering**: are dependencies migrated before their dependents?
- **The missing decision**: the request left something ambiguous. Does the plan
  silently choose an answer? Make the choice explicit and write down why.
- **Verification**: does each batch end with a check, or do all checks live at the
  end? Only the first is supervisable.
- **Rollback**: what is the reset point if batch three goes wrong?

Save the edited plan. It is a deliverable.

### 3. Provide durable context (5 minutes)

Stop re-typing constraints into every prompt. Put the constraints somewhere the
session reads automatically - repository instructions, an agent brief file, or a
task file the plan references. Include the contract rules, the sign conventions,
the time and number rules, and "do not change files outside the manifest".

References:
<https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide> -
<https://docs.github.com/en/copilot/reference/custom-instructions-support> -
<https://code.visualstudio.com/docs/agent-customization/custom-instructions>

Test whether it worked: does the next response respect a constraint you did not
repeat? If not, your durable context is decoration.

### 4. Execute in batches (25 minutes)

- Execute **one batch at a time**. Verify. Only then continue.
- Read every diff. If a batch produces a diff you cannot read in two minutes, it
  was too big; reset and split it.
- Watch for the three classic migration failures: an idiom translated
  syntactically but not semantically; a validation rule quietly dropped; a
  "modernisation" nobody asked for.
- If the session insists a change is required outside the manifest, that is
  information. Investigate it; do not just permit it.
- Hard rule: **you never accept a diff you have not read.** Time pressure is not
  an exception, it is the reason for the rule.

### 5. Review and explain (15 minutes)

- Diff the serialised baseline against the post-migration output. Any difference
  is either a defect or a decision you must be able to name.
- Confirm rejected inputs are still rejected. This is the check that generated
  migrations most often quietly break, because tests usually cover happy paths.
- Write the handover: what moved, what stayed, which ambiguity you resolved and
  how, and the three-part uncertainty sentence.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Baseline capture, plan editing, and **one** batch executed and verified end to end. A well-verified single batch teaches the loop better than a rushed complete migration. |
| **Core** | Baseline, edited plan, durable context, all batches with verification between them, contract diff, handover. |
| **Extension** | Add a contract test that would fail if any serialised field name changes, so the next migration is cheap. Then answer: which part of your plan would you keep as a reusable template for your own repository? |

---

## Evidence and acceptance

- [ ] A captured baseline exists and was captured **before** any change
- [ ] The edited plan is saved, and you can point at two things you changed in it
- [ ] The ambiguity in the request is identified and resolved explicitly
- [ ] Durable context exists as a file, and you tested that it is being applied
- [ ] Each batch was verified before the next one started
- [ ] Serialised output matches the baseline, or every difference is deliberate and
      documented
- [ ] Previously invalid inputs are still rejected
- [ ] `python scripts/workshop.py verify migration-legacy-models` passes (or the
      acceptance commands in `acceptance.md`)
- [ ] No file outside the manifest is modified without a written reason
- [ ] Handover note with the uncertainty sentence

---

## Resync checkpoint - 13:40

At 13:40 everyone stops. Verify, then reset whether or not the migration is
complete. Reset archives the attempt and prints its location before restoring the
pre-start tree; Lab 4 cannot start while this scenario remains active.

```bash
python scripts/workshop.py verify migration-legacy-models
python scripts/workshop.py reset migration-legacy-models
```

Three pairs answer one question each, in one sentence:

1. What did you delete from the generated plan?
2. What did a batch try to do that you refused?
3. What did your baseline catch that a test did not?

Nothing after this lab depends on your migration being complete.

---

## Solo path

Budget 70 minutes and keep the same phase timings. Alone, the discipline that slips
first is batching, so set a timer and force a verification every 10 minutes.

No tooling? Do the same exercise on any legacy-idiom surface in this repository:
capture the baseline, write and edit a plan, migrate one module, prove the
serialised output is unchanged. The transferable skill is
**baseline -> plan -> batch -> verify**, not the specific library idiom.

---

## Hints

[hints/lab_03.md](hints/lab_03.md) - three collapsed levels.

---

## Reflection and retrieval

1. Your plan had a flaw you fixed. Would you have noticed that flaw if you had
   read the plan *after* execution instead of before?
2. Retrieval: name three things a migration plan must contain to be supervisable.
3. Which is more dangerous in your own repository - a migration that fails loudly
   in CI, or one that silently changes a serialised field name? What do you
   currently have in place against the second?
4. What is the smallest piece of durable context you could add to your own
   repository on Monday that would pay for itself in a week?

---

*Next: [Lab 4 - Review and delegation](lab_04_review_and_delegation.md)*
