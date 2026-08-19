# Brief - customization that survives Monday (elective 5C)

A team standard that lives only in reviewers' heads is re-litigated forever. This
elective turns three to five of them into durable context, and - the part people
skip - proves which ones actually changed anything.

This elective needs nothing but an editor and this repository.

## Where you work

`work/instructions_draft.md`, staged by `start`. It is a **scenario-local** draft
written badly on purpose.

> Do not edit `.github/copilot-instructions.md` for this elective. That file is
> the repository's real durable context and other people are working against it
> today. Rewriting the staged draft is the exercise; deciding what you would
> propose for the real file is the outcome.

## The task

1. **Measure before.** Pick one small, repeatable task in this repository - a test
   for a small function, a docstring, a short refactor. Run it with no extra
   context and keep the output.
2. **Critique the draft.** `work/instructions_draft.md` has the classic problems:
   rules nobody can check, rules that pin things that change, rules that
   contradict each other, and rules that belong in someone's personal settings.
   The criteria in `fixtures/review_criteria.md` name the failure modes.
3. **Rewrite it** down to three to five rules that are specific, scoped, and
   checkable. Draw them from what you have seen today - UTC storage, dot decimal
   separators in code and payloads, non-negative loss magnitudes, a test that
   fails before the fix, no changes outside the stated scope.
4. **Measure after.** Run the same task again with the rewritten context applied
   and record the observable difference. If nothing changed, the rule was too
   vague to act on: rewrite one to be checkable and try again.
5. **Contradict it on purpose.** Ask for something that violates one of your
   rules and record what actually happened. Durable context shapes behaviour; it
   does not enforce it.
6. **Sort your rules.** Which need a test, a linter, or a CI check rather than an
   instruction? That list is the most useful thing you will write today.

## Scope and lifetime

A rule that belongs to you personally does not belong in a repository file, and a
rule the whole team depends on does not belong in your personal settings. Getting
that split wrong is the most common customization mistake, and the draft you are
about to read gets it wrong twice.

Avoid pinning specific model names in durable context. Model availability changes
by organisation and over time; a rule that names one is a rule that expires.
