# Elective 5C - Customization that survives Monday

**Block:** 15:15-15:55 (40 minutes) - **Scenario:** `elective-customization`
**Parent:** [Lab 5 - Elective](lab_05_elective.md)

---

## Outcome

You encode a team standard as durable context, prove it changes generated output,
and know the difference between customization that survives contact with a real
team and customization that quietly rots.

This is the elective with the widest transfer and the fewest blockers: it needs
nothing but an editor and a repository.

---

After starting the scenario from the parent lab, work only in
`workshop/scenarios/elective-customization/work/`. The captured no-live path is
under `workshop/fallbacks/elective-customization/`.

---

## Understand/Plan (7 minutes)

Durable context replaces the sentence you retype in every prompt. Several
mechanisms exist, and they differ in scope and lifetime:

| Mechanism | Scope | Good for |
|---|---|---|
| Repository instructions | Everyone working in the repository | Standards that are true for all work here |
| Path-scoped instructions | A directory or file type | "Tests look like this", "API handlers must do that" |
| Prompt files | One repeatable task | The review checklist you run every Friday |
| Custom agents | A role with a defined toolset and behaviour | A reviewer persona, a migration assistant |
| Personal instructions | You, everywhere | Your own working preferences, not team rules |

References:
<https://docs.github.com/en/copilot/concepts/prompting/response-customization> ,
<https://docs.github.com/en/copilot/how-tos/configure-custom-instructions-in-your-ide/add-repository-instructions-in-your-ide> ,
<https://docs.github.com/en/copilot/reference/custom-instructions-support> ,
<https://docs.github.com/en/copilot/reference/customization-cheat-sheet> ,
<https://code.visualstudio.com/docs/agent-customization/custom-instructions>

A rule that belongs to you personally does not belong in a repository file, and a
rule the whole team depends on does not belong in your personal settings. Getting
that split wrong is the most common customization mistake.

---

## Implement/Test (18 minutes)

1. **Measure before.** Pick a small, repeatable task in this repository - a test
   for a small function, a docstring, a short refactor. Run it with no
   customization and keep the output.
2. **Write the standard.** Add durable context encoding **three to five** rules
   this repository actually needs. Draw them from what you have seen today, for
   example:
   - store timestamps as timezone-aware UTC; format for `Europe/Berlin` only at
     the presentation edge,
   - a dot decimal separator in code, config and payloads; the comma is display
     only,
   - VaR and CVaR are non-negative loss magnitudes,
   - a test must fail before the fix and pass after,
   - do not change files outside the stated scope.
3. **Measure after.** Run the same task again. Compare the two outputs and write
   down what changed. If nothing changed, your rules are too vague to act on -
   rewrite one to be checkable and try again.
4. **Keep it small.** Delete any rule you could not detect the effect of. Long
   instruction files are usually a sign that nobody is verifying them.

---

## Review: break it on purpose (5 minutes)

Ask for something that **contradicts** one of your rules. Does the rule hold?
Record what actually happened. Durable context shapes behaviour; it is not an
enforcement mechanism. Anything that must be guaranteed belongs in a test, a
linter, or a CI check - and knowing which of your five rules those are is the most
useful thing you will write today.

---

## Explain (5 minutes)

Complete `work/customization_notes.md` with the before/after evidence, the rules
you kept or rejected, the contradiction result, and the boundary between
instructions and enforceable tests or CI.

---

## Business invariant at stake

**Conventions that live only in reviewers' heads are re-litigated forever.** The
invariants in [reference/invariants.md](reference/invariants.md) - sign
conventions, UTC storage, decimal separators - are exactly the class of rule that
belongs in durable context, because they are objective, checkable, and expensive
to get wrong.

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Three rules, one before/after comparison, and a note on what changed. |
| **Core** | The full Do and Break-it sections, including deleting rules whose effect you could not observe. |
| **Extension** | Convert your review checklist from Lab 4 into a reusable prompt file or a custom agent, then use it on the Lab 4 diff and compare the result with your manual review. |

---

## Evidence and acceptance

See the [shared acceptance list](lab_05_elective.md#shared-acceptance), plus:

- [ ] Before and after outputs both captured, for the same task
- [ ] Three to five rules, each specific enough that a reviewer could check it
- [ ] At least one rule deleted or rewritten because its effect was not observable
- [ ] A note on which rules need a test or CI check rather than an instruction

---

## Solo path

Fully self-contained and offline-friendly. Alone, the temptation is to write ten
rules and verify none. Verify each one, or delete it.

---

## Reflection and retrieval

1. Which of your rules would a new colleague have needed on their first day?
2. Retrieval: which belongs in repository instructions and which in personal
   instructions - "we always use tabs" or "I prefer terse explanations"?
3. What is your plan for keeping these rules true in six months? An instruction
   file nobody maintains is worse than none, because people trust it.

---

*Back to [Lab 5](lab_05_elective.md). Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
