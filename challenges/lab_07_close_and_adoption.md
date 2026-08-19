# Lab 7 - Close: remediation, retrieval, adoption

**Block:** 16:35-16:55 (20 minutes) - **Mode:** whole room, written individually
**Loop stage:** Explain, applied to yourself

---

## Outcome

You leave with three things written down: what you will finish, what you actually
retained, and what changes in your work next week. Nothing here is optional
decoration - a workshop whose effects end at 17:00 was entertainment.

---

## 1. Remediation - what you did not finish (4 minutes)

Being behind is expected. The lanes and resync checkpoints exist because a room of
16 engineers never moves at one speed.

Write down, for each lab you did not complete:

| Lab | What is unfinished | When you will finish it | What you need |
|---|---|---|---|

Guidance:

- Every lab has a **Solo path** section written for exactly this. It works after
  the workshop, offline, without a facilitator.
- The highest-value labs to finish alone are **Lab 3** (baseline, plan, batch,
  verify) and **Lab 6** (transfer). Lab 2 is the most enjoyable and the least
  necessary to repeat.
- If a lab was blocked by policy rather than time, it goes in the adoption section
  below, not here. That is not remediation; that is an organisational ask.

---

## 2. Retrieval - what you actually kept (6 minutes)

Write the answers before you look anything up. Recall is what builds durable
memory; recognition is what makes you feel like you learned something.

1. Name the four stages of the loop, in order.
2. Name the three parts of the uncertainty sentence.
3. Ask, Plan, or Agent: which one do you choose for a change spanning eight files
   with a serialisation contract you must not break - and what must exist first?
4. Name three of the five model selection factors.
5. What is the difference between local Agent and the cloud agent, in one
   sentence, including who is accountable?
6. Name the four failure modes of unattended work.
7. What makes a regression test credible?
8. Give one reason a fixed `+2` hour offset is wrong for `Europe/Berlin`.
9. What must be true before you accept a diff?
10. Which is display-only: the decimal comma or the decimal point?

Then check yourself against [reference/invariants.md](reference/invariants.md),
[reference/evidence.md](reference/evidence.md) and
[reference/model_selection.md](reference/model_selection.md).

**Schedule the repeat.** Put a 15-minute appointment in your calendar for one week
from today and answer these ten questions again from memory. That repetition is
worth more than any additional hour today.

---

## 3. Adoption - what changes at work (8 minutes)

Take the sanitized problem pattern from Lab 0, or the supplied toy problem. Do
not paste work code, internal identifiers, personal/customer data, or secrets
into this note or an assistant. Write:

### Monday, within your existing permissions

- [ ] A local draft proposing **three** checkable durable-context rules
      (Elective 5C is the template); do not commit shared instructions without
      repository-owner agreement
- [ ] One approved task or synthetic exercise run deliberately as **Plan first**,
      with the plan edited before execution
- [ ] The uncertainty sentence in one pull request description this week
- [ ] One baseline captured before a refactor, as in Lab 3

### This month, with your team

- [ ] Review, revise, and decide whether to adopt the durable-context proposal
- [ ] Agree what evidence your team requires for an agent-assisted change
- [ ] Agree who reviews agent-authored pull requests, and confirm they know
- [ ] Decide whether generated changes need a marker in the commit or PR, for
      traceability (Nachvollziehbarkeit)
- [ ] Add one invariant that currently lives only in reviewers' heads to a test or
      a lint rule

### Needs a decision from someone else

Write the ask, and the name of the person or function who owns it:

- [ ] Model availability, or premium request budget - owner: ____
- [ ] Cloud agent enablement, and for which repositories - owner: ____
- [ ] MCP servers: allowlist or private registry - owner: ____
- [ ] Content exclusion for sensitive paths - owner: ____
- [ ] Usage measurement, and its treatment under co-determination
      (Mitbestimmung / Betriebsrat) - owner: ____
- [ ] AI literacy and governance expectations under EU rules - owner: your legal
      or compliance function, not you

Useful links to attach to the ask:
<https://docs.github.com/en/copilot/concepts/policies> ,
<https://docs.github.com/en/copilot/get-started/enterprise-ai-governance> ,
<https://docs.github.com/en/copilot/reference/copilot-feature-matrix> ,
<https://github.com/trust-center>

---

## 4. Close (last 2 minutes)

Answer the Lab 0 question again:

> The capability I am least sure my organisation has enabled is ____, and the way
> I will find out is ____.

Compare it with what you wrote at 09:15. If the answer changed, the day worked.

One last framing, worth carrying out of the room: the loop you practised is not a
GitHub Copilot technique. It is professional engineering with a fast, confident,
occasionally wrong collaborator. The judgement stayed yours all day. It stays
yours on Monday.

---

## Reflection and retrieval

1. What did you believe about agentic tooling at 09:00 that you no longer believe?
2. What is the one habit from today that you will still be doing in three months?
   Be realistic; one is a good number.
3. Who else on your team should hear the two most useful things you learned, and
   when will you tell them?

---

*Curious about what a second day would add? See
[appendix_two_day.md](appendix_two_day.md) - explicitly out of scope for the
one-day core.*

*Back to the [labs index](README.md) or the [workshop README](../README.md).*
