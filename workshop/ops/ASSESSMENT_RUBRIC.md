# Lab 6 individual capstone assessment

This rubric is the individual evidence component of [Lab 6 - Capstone transfer](../../challenges/lab_06_capstone_transfer.md). It measures whether a participant can transfer **Understand/Plan -> Implement/Test -> Review -> Explain** to a new, bounded scenario. It does not measure typing speed, English fluency, Copilot entitlement, prompt cleverness, or access to cloud features.

The score is a private self/peer learning aid. Organisers do not collect the
artifact or score, and it is not an employment or performance-management input.
A facilitator may give feedback on an artifact the participant chooses to show
in the room, but does not record it.

## Rubric (100 points)

| Dimension | Weight | Full-credit evidence |
| --- | ---: | --- |
| Diagnosis and invariant | 20% | Reproduces or states the symptom, identifies the relevant evidence, and names a testable invariant or business rule |
| Context and plan | 20% | Requests/reads relevant context, states assumptions and unknowns, bounds files and non-goals, and proposes focused verification |
| Critical review and verification | 30% | Challenges generated output, finds risks or counterexamples, runs appropriate tests/checks, and reports evidence and failures honestly |
| Patch scope and quality | 20% | Makes the smallest reviewable change, preserves unrelated behaviour, follows repository conventions, and avoids secrets/data leakage |
| Explanation and uncertainty | 10% | Explains what changed, why, evidence, remaining uncertainty, and rollback/follow-up path in clear language |

**Interpretation:** 85–100 demonstrates strong independent transfer; 70–84 demonstrates transfer with minor support; 50–69 needs a coached follow-up; below 50 requires a supported reset and another practice opportunity. These bands guide support, not employment decisions.

## Participant workflow

1. Read the Lab 6 scenario and record the observable problem, relevant context, invariant, and non-goal.
2. Select the Supported, Core, or Extension lane; use the captured/offline fallback if a product path is unavailable.
3. Choose Builder or Supervising architect. Both make a concrete code/test
   change; neither is prose-only.
4. Implement the selected lane, add one participant-owned adversarial check for
   a material assumption, then inspect the full diff.
5. Test with focused verification. On the architect route, review a candidate
   implementation and make at least one bounded correction.
6. Review the evidence and reject or amend unsupported output.
7. Explain the change, reason, evidence, uncertainty, and next step.
8. Self-score during the allocated three minutes and mark one confidence level.

## Self / peer workflow

- Self-review first; the author retains control of the keyboard and final decision.
- Peer reviewer asks: “What is the invariant?”, “What would falsify this?”, “What is out of scope?”, and “What remains uncertain?”
- Reviewer scores evidence, not personality, speed, accent, or tool access.
- A participant may use the solo route or helper instead of peer pairing.
- A facilitator only views an artifact the participant chooses to show, gives
  in-room feedback, and does not retain the artifact or score.

## Lab 7 adoption and delayed follow-up (1–2 weeks)

Use [Lab 7 - Close and adoption](../../challenges/lab_07_close_and_adoption.md) to create a voluntary transfer prompt: apply **Understand/Plan -> Implement/Test -> Review -> Explain** to a safe work-like toy issue or approved internal example. Ask for:

- the invariant and bounded plan;
- one verification result;
- one rejected or amended suggestion;
- one remaining uncertainty;
- the next safe action.

Accept a short written response, a 10-minute conversation, or “not yet.” Do not require surveillance, browser history, full prompt capture, keystroke data, or continuous telemetry. Keep the follow-up separate from performance management unless the organizer has a separate lawful, transparent process.
