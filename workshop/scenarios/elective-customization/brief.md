# Brief - repository and path-scoped instructions (elective 5C)

Bad custom instructions are invisible technical debt. They look authoritative,
apply too widely, and are rarely tested. Turn the vague reviewer draft into a
small, testable repository contract for one role.

## Material and discovery boundary

| File | Purpose |
|---|---|
| `work/instructions_draft.md` | Editable scenario-local draft |
| `work/customization_notes.md` | Evidence template |
| `fixtures/review_criteria.md` | Scoring and comparison sheet |

The draft is not at a recognised discovery path. Editing it does not prove that
Copilot loaded repository instructions or matched a path rule.

Recognised repository mechanisms are:

- `.github/copilot-instructions.md` for repository-wide guidance;
- `.github/instructions/NAME.instructions.md` with frontmatter `applyTo` globs
  for path-specific guidance.

Do not relocate the scenario file in this block. A production proposal should
name its intended path and glob.

## 29-minute working task

| Time | Work | Evidence |
|---|---|---|
| 5 min | Choose reviewer or architect, choose route, and score the draft | Baseline score |
| 13 min | Rewrite at most five observable rules and produce one comparison | Edited draft plus before/after |
| 7 min | Delete one rule and evaluate the same input | Ablation trace |
| 4 min | Record contradiction, enforcement boundary, and owner | Decision note |

At minute 18, stop adding rules. At minute 25, stop testing and explain.

## Stable review input

Use the same input for every comparison:

> A draft review comment for a proposed change to `mittelwerk/analytics/sla.py` says:
> "This looks risky. Consider changing it." Rewrite the comment for a pull
> request. No diff or test output has been provided.

Do not edit application code.

## Local delivery

1. Score the starting draft using `fixtures/review_criteria.md`.
2. Rewrite it with three to five observable rules. Include scope, required
   evidence, one negative instruction, and a stop/escalation condition.
3. Write a candidate output for the stable input before and after your rules.
   Label both `local candidate`, not Copilot output.
4. Delete one rule and record the output difference you would expect. Use
   `no material difference` if that is the honest result.
5. Trace this contradiction: the user requests a complete patch even though the
   role is review-only. In the template's `Observed behaviour` field, begin with
   `Local expected:` and name the human or system that owns the deterministic
   boundary.

## Optional preflight-Green live addition

Use the same model, surface, input, and repository state for every run:

1. Run the stable input without attaching the scenario draft.
2. Explicitly attach the edited draft to the same request and repeat.
3. Remove one rule, explicitly attach the changed draft, and repeat once.
4. Preserve prompts, responses, model/surface, and evidence labels.

This tests content supplied as context. It does **not** test automatic discovery,
`applyTo` matching, or instruction precedence because the file remains outside a
recognised path.

## What instructions do and do not do

Instructions can shape task approach, evidence, terminology, and stop
conditions. They do not enforce permissions, authentication, branch protection,
CODEOWNERS, required checks, data-loss prevention, or runtime policy. A model can
ignore or misapply guidance; deterministic controls need another owner.

## Current status - as of 2026-08-25

- Repository-wide and path-specific instructions are documented GitHub Copilot
  mechanisms. Support and combination behavior vary by surface, so test in the
  deployment target.
- Prompt files are public preview. Current VS Code Agent Host guidance recommends
  agent skills for reusable capabilities because Agent Host does not use prompt
  files.
- Custom agents are supported on GitHub.com, VS Code, Visual Studio, and Copilot
  CLI; JetBrains, Eclipse, and Xcode support remains preview.
- Agent skills can carry instructions, resources, and executable scripts. Review
  bundled scripts before trusting a skill.
- GitHub documents hooks for Copilot CLI and Copilot cloud agent, and the current
  customization support matrix lists VS Code hooks in preview. They are
  follow-up awareness, not a second mechanism for this lab.
- Personal/custom instructions are surface-specific. Do not promise that one
  personal setting follows a user everywhere.

References:

- <https://docs.github.com/en/copilot/how-tos/configure-custom-instructions/add-repository-instructions>
- <https://docs.github.com/en/copilot/concepts/prompting/response-customization>
- <https://docs.github.com/en/copilot/reference/custom-instructions-support>
- <https://docs.github.com/en/copilot/reference/customization-cheat-sheet>
- <https://code.visualstudio.com/docs/agent-customization/custom-instructions>
- <https://code.visualstudio.com/docs/agent-customization/prompt-files>
- <https://code.visualstudio.com/docs/agent-customization/custom-agents>
- <https://code.visualstudio.com/docs/agent-customization/agent-skills>
- <https://code.visualstudio.com/docs/agent-customization/hooks>

The room report may mention one follow-up mechanism. Do not implement prompt
files, custom agents, skills, and hooks as extra work in this block.
