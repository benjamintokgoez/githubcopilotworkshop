# Lab 3 - Plan-driven migration of a legacy model layer

**Block:** 12:30-13:40 (70 minutes) - **Mode:** pairs or solo
**Loop stages:** Understand/Plan (heavily) -> Implement/Test -> Review -> Explain
**Scenario:** `migration-legacy-models`
**Hard reset:** 13:35

---

## Outcome

You supervise a multi-file migration with a captured baseline, a plan that you
challenge before implementation, task context that survives individual prompts,
small verified batches, and an explicit contract comparison.

The Core route is achievable for a prepared pair, but it is a stretch target, not
the definition of a successful lab. A verified first batch with useful evidence
is a complete Supported outcome. A rushed full migration with no readable
evidence is not.

---

## Set up and choose roles - 12:30-12:35

```bash
python scripts/workshop.py start migration-legacy-models
python scripts/workshop.py status
python scripts/workshop.py verify migration-legacy-models  # expected to fail; save the output
```

The clean repository was green before `start`. The scenario introduces a legacy
surface whose contract checks mostly pass while its migration target does not.
This first run is fail-before evidence; it is not evidence that the clean
repository was broken. See
[reference/scenario_tooling.md](reference/scenario_tooling.md#the-healthy-baseline-contract).

Work only in `workshop/scenarios/migration-legacy-models/work/`. Create
`MIGRATION_NOTES.md` there and keep all participant-created evidence in it.
`reset` archives participant additions before restoring the pre-start tree.

For pairs:

- **Operator:** controls the IDE or terminal and makes one requested change at a
  time.
- **Contract reviewer:** controls the manifest, baseline, diff reading, and
  evidence note. The reviewer can stop a batch.
- **Rotate at 12:56**, before implementation. The first reviewer becomes the
  operator; the first operator becomes the contract reviewer.

For solo work, write `Operator` and `Contract reviewer` in your note. At 12:56,
stop prompting for one minute, switch roles, and challenge your own plan before
you implement it.

If `start` is blocked, use
`python scripts/workshop.py fallback migration-legacy-models` and follow the
captured/offline route. Do not spend the block repairing workshop tooling.

---

## Artifacts

| Artifact | Use it as |
|---|---|
| `issue.md` | The migration request and business constraint |
| `inventory.md` | The authoritative file scope and public surface |
| Staged model and adapter modules | The code you may migrate or update |
| `acceptance.md` | What the verifier proves, and what it cannot prove |

The request is deliberately underspecified in one respect. Record the decision
you make; do not guess silently. The hints do not identify it.

---

## Business invariant

**The external contract does not change.**

- Serialised field names, aliases, nesting, order where consumers rely on it,
  and value types stay identical across model, REST, MCP, and batch boundaries.
- Accepted inputs remain accepted. Rejected inputs still raise the public
  exception with a useful message.
- **INV-TIME-1:** timestamps remain timezone-aware UTC after a round trip.
- **INV-FMT-1:** machine JSON uses a dot decimal separator. DACH formatting is a
  presentation concern, not a payload concern.
- **INV-ASSET-1** and **INV-SLA-3** remain true for downstream systems.

See [reference/invariants.md](reference/invariants.md).

---

## The 70-minute route

| Clock | Budget | Phase | Required output |
|---|---:|---|---|
| 12:30-12:35 | 5 min | Start and orient | Saved fail-before run, roles, scope |
| 12:35-12:43 | 8 min | Capture baseline | One representative valid/invalid contract capture per model family |
| 12:43-12:53 | 10 min | Generate and edit plan | Saved plan plus at least two recorded edits |
| 12:53-12:56 | 3 min | Persist task context | Context source and loading route; rotate roles |
| 12:56-13:16 | 20 min | Implement/test in batches | One or more read and verified batches |
| 13:16-13:26 | 10 min | Review and explain | Contract comparison and handover |
| 13:26-13:35 | 9 min | Final check and reset | Actual verifier result, archive, scenario inactive |
| 13:35-13:40 | 5 min | Room resync | One evidence-based observation per selected pair |

The clocks are part of the exercise. Do not borrow from the protected break.

### Stop and cut decisions

- **12:40:** if baseline evidence is missing, use the supplied harness and narrow
  to Supported. No implementation starts without a saved baseline.
- **12:55:** if the plan is not edited and bounded, use the pre-staged plan
  shape and require two substantive edits. Choose one batch only.
- **13:16:** start no new batch. Keep verified work; do not enlarge a batch to
  chase completion.
- **13:26:** freeze edits. Run the verifier once, record the observed result, and
  reset by 13:35.
- **13:35:** reset even if verification is red. Reset is the completion of the
  workshop transaction, not an admission of failure.

---

## Run the loop

### 1. Understand: capture a bounded baseline - 8 minutes

Use the public surface in `inventory.md`, not internal model methods. Capture:

1. The initial verifier command, exit status, and observed failing/passing split.
2. The public imports and call signatures.
3. One valid equipment reference and one valid service-rate record through their
   public parser, payload, and JSON paths. Preserve representations and relevant
   runtime types.
4. One invalid equipment reference and one invalid service-rate record through the public error
   boundary. Preserve the exception type and whether the message is non-empty.
5. One representative REST document, MCP result, and batch record. Preserve
   envelope names, nested shape, runtime types, timestamp text, and decimal text.

This matrix covers both model families and every consumer category without
multiplying equivalent invalid cases across each adapter. The supplied contract
tests cover more cases; your capture proves that you observed the boundaries
before changing them.

### 2. Plan, then edit the plan - 10 minutes

In current VS Code, choose the **Local** session target and the built-in
**Plan** agent role, or start with `/plan`. If that role is unavailable, ask for
a plan without permitting edits.
Require:

- exact in-scope files and explicit out-of-scope files;
- old-to-new idiom categories without speculative modernisation;
- dependency order and batches independently verifiable in under five minutes;
- an exact verification command and expected observation after each batch;
- the unresolved request decision and a rollback point.

Challenge the draft. Save the final plan in `MIGRATION_NOTES.md` and record at
least two changes you made to the generated draft. Delete invented scope, split
oversized batches, correct ordering, and replace vague checks with observable
ones.

VS Code's Plan role also stores a plan in session memory, but that memory is
cleared when the conversation ends. The saved copy in your scenario note is the
durable workshop artifact.

Reference:
<https://code.visualstudio.com/docs/agents/run/planning>.

### 3. Persist and load task context - 3 minutes

Add a short implementation brief to `MIGRATION_NOTES.md`: contract rules, scope,
the explicit ambiguity decision, the current batch, and its verification.

Be precise about how the next agent receives it:

- hand off directly from the Plan role, where the plan and conversation context
  carry forward; or
- explicitly attach or reference `MIGRATION_NOTES.md` in the implementation
  request.

An arbitrary Markdown file is **not** automatically loaded just because it is in
the work directory. Repository instructions such as
`.github/copilot-instructions.md`, path-specific instruction files, and
`AGENTS.md` are recognised forms, but adding or changing repository-wide
instructions is outside this scenario's scope. Use the repository's existing
instructions; do not edit them for the lab.

This exercise does not use **Copilot Memory**, which is a separate public-preview
capability. A saved task note and recognised repository instructions keep the
route deterministic and available without that feature.

Ask the implementation agent to name the scope and verification it loaded before
it edits. Record the source it names. Correct behaviour alone does not prove
which context was applied.

References:
<https://docs.github.com/en/copilot/reference/custom-instructions-support> -
<https://code.visualstudio.com/docs/agent-customization/custom-instructions> -
<https://docs.github.com/en/copilot/concepts/agents/copilot-memory>.

### 4. Implement/test in batches - 20 minutes

For each batch:

1. State the files and intended contract-preserving change.
2. Permit only that batch.
3. Read the entire diff. If two minutes is not enough, reject and split it.
4. Run the batch check and paste the command, exit status, and observed result.
5. Continue only when the reviewer can explain the diff and the evidence.

Watch for semantic validation loss, changed defaults or aliases, boundary
serialisation changes, and unrequested modernisation. A request to edit outside
the inventory is a claim to investigate, not permission.

### 5. Review and explain - 10 minutes

- Compare the valid baseline with the post-change model, REST, MCP, and batch
  output, including types, nesting, UTC representation, and machine number
  formatting.
- Re-run the invalid boundary cases.
- Inspect the complete scenario diff for scope.
- Write the handover: completed batches, remaining batches, ambiguity decision,
  verification results, and the three-part uncertainty sentence.

---

## Outcomes

| Lane | Evidence-complete outcome |
|---|---|
| **Supported** | Bounded baseline, edited plan, recorded context-loading route, one batch whose diff was read and verified, honest final verifier result, handover of remaining work, and reset. The full migration may remain incomplete. |
| **Core** | Supported evidence plus all planned batches, matching before/after contract capture, rejected-input comparison, passing scenario verifier, complete handover, and reset. |
| **Extension** | Only after Core and only before 13:26: add one narrow adversarial contract check or extract a reusable migration-plan template. Record what new risk it covers. Do not delay reset. |

The captured/offline route is a delivery route, not a fourth achievement lane.
Judge it against the same evidence standard that its available tools can support.

---

## Completion is not evidence

`python scripts/workshop.py verify migration-legacy-models` proves that the
supplied contract checks pass and the compatibility shim is gone. It cannot prove
that you captured the baseline first, edited the plan, loaded the intended
context, read each diff, or made a sound ambiguity decision.

Conversely, a red final verifier does not erase useful Supported evidence. Record
the failing check, the last verified batch, and the next bounded action. Never
describe a partial migration as Core-complete.

### Evidence checklist

- [ ] Fail-before output was saved before code changed
- [ ] Baseline covers both public model families and both error boundaries
- [ ] Final plan is saved with at least two recorded edits to the draft
- [ ] Ambiguity decision and out-of-scope files are explicit
- [ ] Context source and loading route are recorded accurately
- [ ] Every attempted batch has a readable diff and observed check result
- [ ] Before/after output differences are named, including "none"
- [ ] Invalid inputs were compared after the change
- [ ] Final verifier result is copied exactly, whether red or green
- [ ] Handover separates completed, verified, assumed, and remaining work
- [ ] No unexplained file outside the inventory changed
- [ ] Reset completed and the archive location was noted

---

## Facilitator cues

- At 12:35, ask for the saved fail-before run, not a verbal "it failed".
- At 12:56, call the role rotation and ask reviewers what they removed or split
  in the plan. Do not supply API mappings.
- At 13:16, announce "no new batches". Route stalled participants to Supported or
  `resync`, not to a hidden solution:

  ```bash
  python scripts/workshop.py resync migration-legacy-models --blocked-at implement-test
  ```

- At 13:26, announce the edit freeze. Protect nine minutes for honest
  verification and reset.
- Announce and post every cut time; do not rely on colour, a projected timer, or
  one participant relaying instructions. Pairing is optional.
- At resync, ask three pairs for one sentence each: a plan edit, a refused scope
  change, or a baseline difference. A completed migration is not required.

---

## Solo and captured/offline routes

Solo participants use the same clocks and lane definitions. The deliberate
one-minute role switch at 12:56 replaces conversational peer challenge; do not
skip it.

Without the runner, use
`workshop/fallbacks/migration-legacy-models/`, copy the inert staged files to a
permitted working directory, and use the captured initial verifier output as the
fail-before command evidence. Record which observations are captured rather than
personally executed. That distinction is part of the evidence.

---

## Hints

[hints/lab_03.md](hints/lab_03.md) - three collapsed levels.

---

## Reflection and retrieval

1. Which generated plan step did you change, and what risk did the edit remove?
2. Name three properties that make a migration batch supervisable.
3. Which evidence remains useful even if the final verifier is red?
4. What belongs in reusable repository instructions, and what belongs only in a
   task-specific migration note?

---

*Next: [Lab 4 - Review and delegation](lab_04_review_and_delegation.md)*
