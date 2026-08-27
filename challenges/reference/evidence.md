# Evidence, acceptance, and explaining uncertainty

A change is finished when someone else can accept it without redoing your work.
That is the bar in every lab today, and it is the bar your reviewers already apply
to human-written code.

## The evidence note

Keep one Markdown scratch file per lab (anywhere outside the repository history is
fine; `notes/` in your working copy works). Fill in these seven lines. They take
about three minutes once you have the habit.

```markdown
## Lab N - <title>

1. Task in one sentence:
2. Invariant at stake:                 (INV-... from reference/invariants.md)
3. Workflow chosen:                    Ask | Plan | Agent  - because ...
4. Model used:                         Auto or approved model - because ...
5. Evidence that it works:             command + observed result (paste output)
6. Blast radius:                       files touched, what else could break
7. Uncertainty:                        what I verified / what I assumed /
                                       what could still be wrong
8. Achievement lane:                   Supported | Core | Extension
9. Delivery mode:                      live | local | captured/offline
10. Live surface operated:             <surface> | none
```

Line 7 is the one people skip and the one reviewers value most.

Lines 8-10 prevent two false conclusions. A deliberately narrower Supported
artifact does not need to pass a full Core verifier, and a captured analysis
does not prove live product operation. Report both dimensions.

## What counts as evidence

| Strong | Weak |
|---|---|
| A test that fails before the change and passes after | "Tests pass" with no before-state |
| Command output pasted verbatim, including the command | A screenshot of a green tick |
| A named invariant restored, with the expected value | "It looks right now" |
| A diff you have read line by line | A diff you accepted in bulk |
| An explicit statement of what you did not check | Silence about scope |

## Explaining uncertainty

Use this three-part sentence. It is short enough to say in a stand-up and precise
enough for a reviewer.

> **I verified** \<what you actually ran and observed\>.
> **I assumed** \<what you took on trust: an interface, a fixture, a generated explanation\>.
> **It could still be wrong if** \<the concrete condition that would break it\>.

Worked example:

> I verified that a 12-hour request now uses the accepted 110.00 EUR/h provider rate, using
> the scenario's acceptance command, and that the regression test fails on the
> pre-change commit. I assumed the fixture's arrival timestamps reflect real
> arrival order rather than insertion order. It could still be wrong if two offers
> share a timestamp, which the fixture does not cover.

"I am not sure" on its own is not an answer. "I am not sure **whether**, because
I could not check **that**" is.

## Reviewing generated work

Whether the change came from a local Agent session, a cloud agent, or a colleague,
review it the same way:

1. **Scope** - does the diff touch only what the task required? Unrequested
   "improvements" are the most common defect in agent output.
2. **Invariant** - is the stated business rule actually restored, or just the
   symptom?
3. **Tests** - do the new tests fail without the change? A test written after the
   fix that only asserts current behaviour proves nothing.
4. **Contracts** - public signatures, serialised field names, API shapes, units
   and sign conventions.
5. **Non-functional** - secrets, logging of personal data, timezone handling,
   number formatting, error swallowing.
6. **Explanation** - can you restate why the change works without reading the
   generated commentary? If not, you are not the reviewer yet.

Copilot code review is a useful **second** pass, not a substitute for the first:
<https://docs.github.com/en/copilot/concepts/agents/code-review>.

## Acceptance criteria in the labs

Each lab lists separate Supported and Core acceptance criteria. They are
deliberately about **evidence quality**, not speed. Supported still touches
Understand/Plan, Implement/Test, Review, and Explain on a narrower artifact. Its
full scenario verifier may remain red when the lab says so. Core requires the
full scenario contract plus the evidence note. Extension starts only after Core.
