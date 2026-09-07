# Elective 5C - Customization that survives Monday

<!-- journeys:card:5C:start -->
## Run card

| Decision | This lab |
|---|---|
| Outcome | Rewrite and test three to five instruction rules on one stable task. |
| First action | `python scripts/workshop.py start elective-customization` |
| Edit boundary | workshop/scenarios/elective-customization/work/; never shared repository instructions. |
| Evidence | `workshop/scenarios/elective-customization/work/customization_notes.md`; reset archives this work. |
| Lane boundary | Supported: first three branch items and one contradiction. Core: all branch items and structure check. Extension: follow-up only. |
| Delivery | Default: **local**. Routes: local, captured/offline, live. Mode does not raise or lower the lane; follow the acceptance checklist. |
| Clock | **35 elapsed minutes**; cohort **15:00-15:35 Europe/Berlin**. [Self-paced route](README.md#self-paced-route): start at T+0, pause between phases, keep the same cuts. |
| Recovery | `python scripts/workshop.py resync elective-customization --blocked-at <phase>`; then verify and reset. [Recovery commands](reference/scenario_tooling.md). |

**Phase clock** (elapsed minutes; solo work uses the left column):

| Elapsed | Cohort | Phase |
|---|---|---|
| T+0-5 | 15:00-15:05 | Understand/Plan |
| T+5-18 | 15:05-15:18 | Implement/Test |
| T+18-25 | 15:18-15:25 | Review |
| T+25-29 | 15:25-15:29 | Explain |
| T+29-33 | 15:29-15:33 | Verify and reset |
| T+33-35 | 15:33-15:35 | Cross-elective awareness |

**Cuts — move on with honest evidence:**
- **T+3 / 15:03:** If the preflight-approved live route does not work, use the capture; no installation or sign-in.
- **T+18 / 15:18:** Stop adding configuration; use captured observations if needed.
- **T+29 / 15:29:** Stop work; verify and reset.
- **T+33 / 15:33:** Keep the control / negative case / limitation report.

[Return: Lab 5](lab_05_elective.md) · [Next: Lab 6](lab_06_capstone_transfer.md) · [All labs](README.md) · [Terms](README.md#terms-used-in-the-labs)
<!-- journeys:card:5C:end -->

**Block:** 15:00-15:35 (35 minutes) - **Scenario:** `elective-customization`
**Parent:** [Lab 5 - Elective](lab_05_elective.md)

---

## Outcome

Turn a weak instruction draft into three to five scoped, testable rules.
Compare them on one repeatable task. Decide which requirements need checks that
run every time, rather than relying on the model to follow instructions.

This route needs only an editor and the scenario. A live model comparison is
optional. Work only in
`workshop/scenarios/elective-customization/work/`; the fallback copy is under
`workshop/fallbacks/elective-customization/`.

The staged `instructions_draft.md` is deliberately **not** an automatically
discovered instruction file. That protects the repository's real shared
instructions. If you attach the draft explicitly in a live comparison, you test
the content of the rules, not automatic discovery or path matching.

## Route decision

| Delivery mode | Method | Honest claim |
|---|---|---|
| **Local** | Rewrite the draft and score the before/after rules and one candidate output with the mechanical rubric | The proposed rules became more scoped and checkable |
| **Live** | Run the same task in two fresh sessions; explicitly attach only the rewritten draft in the second | The rule content influenced this model run |
| **Follow-up (not a delivery mode)** | Test a real repository/path instruction, skill, prompt file, custom agent, or hook in an isolated repository | Discovery and cross-surface behavior require separate evidence |

Do not edit `.github/copilot-instructions.md` during the workshop.

---

## Understand/Plan (5 minutes)

Choose the mechanism by scope, trigger, and enforcement strength.

| Mechanism | Trigger and scope | What it does not enforce |
|---|---|---|
| Repository instructions | Automatically supplied for supported work in one repository | Deterministic compliance or identical support on every surface |
| Path-specific `*.instructions.md` | Applies when supported clients work on matching paths/tasks | A repository-wide rule; matching and support must be tested per surface |
| Prompt file | Manually invoked reusable task in supported IDEs | Always-on behavior; GitHub Docs labels prompt files public preview |
| Custom agent | Selected or delegated specialist with instructions and available tools | Authorization merely because a tool is omitted; runtime permissions still apply |
| Agent skill | Task-relevant folder of instructions/resources loaded on demand | Automatic use on every request or safety of bundled scripts |
| Hook | Runs code at lifecycle events and can block/approve supported tool calls | Safe policy by default; hook code, policy availability, and bypass risks need review |
| Personal instructions | User-scoped in the client that stores them | A team contract; locations and support differ between GitHub.com, IDEs, and CLI |

For this block, implement only **repository-wide or path-specific instruction
content** in the scenario-local draft. Prompt files, agents, skills, and hooks
belong in the room report or follow-up.

### Current product boundaries - as of 2026-08-25

<details>
<summary>Optional product lookup: discovery, supported clients, and official sources</summary>

- `.github/copilot-instructions.md` is the repository-wide file.
  `.github/instructions/**/*.instructions.md` carries path-specific instructions
  using `applyTo`. Support differs by Copilot surface; consult the current
  support matrix rather than assuming.
- GitHub Docs labels prompt files **public preview**. Current VS Code guidance
  says local extension-host agents use them, while Agent Host sessions use
  skills instead.
- Custom agents are supported in VS Code, Visual Studio, GitHub.com, and Copilot
  CLI; JetBrains, Eclipse, and Xcode support is currently preview. Tool lists
  define what the agent can select, not permission to execute.
- Agent skills are supported across several Copilot agent surfaces and load when
  relevant. Review any bundled scripts and `allowed-tools` before adoption.
- GitHub documents hooks for Copilot CLI and Copilot cloud agent. The current
  customization support matrix also lists VS Code hooks in preview. Unlike
  natural-language instructions, hook code can make deterministic lifecycle
  decisions, subject to the hook's own correctness, client support, and
  deployment.
- Organisation instructions require Copilot Business or Enterprise and do not
  apply uniformly to every surface.
- Copilot Memory is public preview, repository/user scoped, expires after 28 days
  of inactivity, and is governed through owner/admin review and deletion routes.
  It is not a replacement for versioned critical instructions.

Official references:

- <https://docs.github.com/en/copilot/concepts/prompting/response-customization>
- <https://docs.github.com/en/copilot/reference/custom-instructions-support>
- <https://docs.github.com/en/copilot/reference/customization-cheat-sheet>
- <https://docs.github.com/en/copilot/how-tos/copilot-cli/customize-copilot/add-custom-instructions>
- <https://code.visualstudio.com/docs/agent-customization/custom-instructions>
- <https://code.visualstudio.com/docs/agent-customization/prompt-files>
- <https://code.visualstudio.com/docs/agent-customization/custom-agents>
- <https://code.visualstudio.com/docs/agent-customization/agent-skills>
- <https://code.visualstudio.com/docs/agent-customization/hooks>

</details>

---

## Implement/Test (13 minutes)

Use the stable review input in the scenario `brief.md`. Keep the input identical
before, after, and during the deletion test.

### Local mode

1. Without reading the draft, write a short candidate response for the stable
   review input, or exchange one with a partner. Keep it to ten lines.
2. Score the original draft with `fixtures/review_criteria.md`. Record which rules
   cannot be tested, belong elsewhere, conflict, or are likely to become outdated.
3. Rewrite `work/instructions_draft.md` to three to five rules. For each rule,
   state scope, a reviewer check, and the failure it prevents.
4. Apply the rewritten rules to the same input and write the after-candidate.
   Record concrete changes. This is a repeatable rule-quality comparison, not
   evidence that a model discovered the file.

### Optional live addition

Run the same task in two fresh sessions with the same model. Do not mention the
rules in either prompt. In the second session, explicitly attach the rewritten
scenario-local draft as context. Capture only the relevant output difference and
label the result `live, explicitly attached`. Non-determinism means one comparison
is evidence for this run, not a guarantee.

Delete or rewrite any rule whose effect you cannot test.

**Cut at 15:18:** stop adding mechanisms. You need one before/after comparison,
not a prompt file plus agent plus skill.

---

## Review: contradict one rule (7 minutes)

Create a request that conflicts with one retained rule while keeping the task
safe. For the live route, run it with the same explicit context and record the
result. For local mode, ask a partner to apply the request, or write the two
plausible outcomes and use the rule's reviewer check to decide which passes.
Label the route.

An instruction shapes model behaviour; it does not guarantee it. Move any
must-always-hold invariant to a test, linter, CI rule, permission boundary, or
review gate. A hook can execute deterministic logic on supported surfaces, but a
poor hook is still poor policy and is outside this elective.

---

## Explain (4 minutes)

Complete `work/customization_notes.md`:

- evidence route and exact task,
- before/after outputs or rule-quality scores,
- retained, rewritten, and deleted rules,
- contradiction result,
- proposed repository or path scope,
- deterministic control needed for each invariant.

### Role lens

- **Developer/maintainer:** Can a reviewer detect compliance in a diff without
  debating intent?
- **Architect/engineering leader:** Who owns the rule, which surfaces consume it,
  how is it versioned, and which controls enforce the non-negotiable parts?

---

## Business invariant at stake

**Write shared rules down so every review need not debate them again.** The
invariants in [reference/invariants.md](reference/invariants.md) are useful source
material because they are objective and expensive to get wrong. The highest-risk
ones still need tests or CI; instructions are not a substitute.

---

## Evidence and acceptance

See the [shared acceptance list](lab_05_elective.md#shared-acceptance), plus:

Supported completes the first three branch items and one analysed contradiction,
then records the actual verifier result. Core completes every item below and
requires the structural verifier to pass.

- [ ] Route and task are named; the same task is used before and after
- [ ] Three to five rules each have a scope, reviewer check, and failure impact
- [ ] The observable difference is concrete, whether produced by a live run or a
      local rule-quality comparison
- [ ] At least one rule is deleted or rewritten based on evidence
- [ ] The contradiction result distinguishes guidance from deterministic
      enforcement
- [ ] No claim is made that the scenario-local draft was automatically discovered

---

## Solo path

Use the shared 35-minute elapsed clock. Write the ten-line candidate response,
set it aside, then rewrite and score the rules. At T+18 stop adding rules and
test one conflicting request. Record both scores and concrete edits, explain
the limits, and verify/reset at T+29. This is local evidence, not a model run.
If you use supplied rather than personally produced observations, label them
captured and keep any unrun check explicit. Finish the awareness step in
[Lab 5](lab_05_elective.md#solo-path).

---

## Reflection and retrieval

1. Which rule would a new colleague need on day one, and which is only your
   preference?
2. What evidence would prove a path-specific file applied on every client your
   team uses?
3. Who removes or updates an instruction when the architecture changes?

---

*Back to [Lab 5](lab_05_elective.md). Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
