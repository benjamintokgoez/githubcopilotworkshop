# Elective 5B - CLI permissions and sandboxing

**Block:** 15:15-15:55 (40 minutes) - **Scenario:** `elective-cli`
**Parent:** [Lab 5 - Elective](lab_05_elective.md)

---

## Outcome

You run an agent in a terminal with deny-by-default permissions, you can explain
what it may execute and what it may not, and you have tested the boundary rather
than assumed it.

This matters most for anyone thinking about agents in CI, on shared machines, or
on anything with production credentials in the environment.

---

After starting the scenario from the parent lab, record your work in
`workshop/scenarios/elective-cli/work/`. The captured no-live path is under
`workshop/fallbacks/elective-cli/`.

---

## Understand/Plan (7 minutes)

A terminal agent can read files, run commands, and change state. The interesting
question is never "can it help?" but "what is it permitted to do when I am not
watching?"

Three questions:

1. What is the **default** - approve each action, or run freely?
2. What does an allowlist entry actually grant? A command, a command with any
   arguments, or a shell?
3. What is the **blast radius** of the working directory it was started in?

References:
<https://docs.github.com/en/copilot/concepts/agents/copilot-cli/about-copilot-cli> ,
<https://docs.github.com/en/copilot/how-tos/copilot-cli/use-copilot-cli/allowing-tools> ,
<https://docs.github.com/en/copilot/how-tos/copilot-cli/cli-best-practices> ,
<https://docs.github.com/en/copilot/reference/copilot-cli-reference/cli-command-reference>

---

## Implement/Test (18 minutes)

1. Install and authenticate the CLI if you have not already:
   <https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/install-copilot-cli>.
2. Start a session **in this repository directory** and give it a read-only task,
   for example: summarise how a module reaches a result, or find where a
   convention is enforced.
3. Observe every approval prompt. For each one, before approving, say out loud what
   the command will do. If you cannot, deny it.
4. Now configure an explicit allowlist for the **narrow** set of commands your task
   needs (for example, a specific test invocation) and re-run. Confirm the prompts
   you expected to disappear disappeared, and that nothing else did.
5. Record: what you allowed, what remained gated, and what you would allow on a
   shared machine versus your laptop.

**Do not** run this against a repository with production credentials in the
environment, and do not allowlist a broad shell command to save time. That
shortcut is the entire risk.

---

## Review: break it on purpose (5 minutes)

Ask for something outside your allowlist - a write, a network call, or a command
outside the working directory. Record what happened: a prompt, a refusal, or
success you did not expect. If a broad allowlist entry turned out to grant more
than you intended, that is the most valuable finding of the elective.

---

## Explain (5 minutes)

Complete the team-facing policy in `work/permission_policy.md`: the default
posture, at least three allow/ask/deny rules, each rule's blast radius, and the
control boundary you would explain before using the CLI on a shared machine.

---

## Business invariant at stake

**An agent's permissions are a production concern, not a personal preference.**
On a shared or CI machine, the permissions you grant apply to everything that
environment can reach, including credentials you forgot were exported.

Traceability (Nachvollziehbarkeit) applies too: if an agent changed something, the
record of what it ran must exist. See
[reference/dach_conventions.md](reference/dach_conventions.md#4-works-council-and-organisational-governance).

---

## Lanes

| Lane | What you do |
|---|---|
| **Supported** | Run one read-only session, narrate three approval prompts before answering them, and write the permission inventory. |
| **Core** | The full Do and Break-it sections, including the narrow allowlist and its verification. |
| **Extension** | Write the rule set you would propose for your team: what is allowlisted by default, what always requires a human, and what is forbidden outright on machines with production access. |

---

## Evidence and acceptance

See the [shared acceptance list](lab_05_elective.md#shared-acceptance), plus:

- [ ] The allowlist configuration exists and you can point at it
- [ ] Evidence that prompts changed after configuring it
- [ ] The negative-case result, recorded as observed
- [ ] One sentence naming what an allowlist does **not** protect against

---

## Solo path

Fully self-contained. If the CLI cannot be installed on your machine - a common and
legitimate enterprise restriction - do this instead: write the permission policy
you would want, then read the allowlist documentation and mark which parts of your
policy the mechanism can actually enforce. Policy that the tool cannot enforce is
a hope, and knowing which parts those are is the real outcome.

---

## Reflection and retrieval

1. Which allowlist entry did you write that is broader than it needs to be? Be
   honest; there usually is one.
2. Retrieval: what is the default posture, and why does the default matter more
   than the allowlist?
3. If an agent ran in your CI tonight, could you reconstruct tomorrow what it did?

---

*Back to [Lab 5](lab_05_elective.md). Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
