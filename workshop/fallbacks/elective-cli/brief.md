# Brief - terminal agent permissions (elective 5B)

An agent in a terminal can read files, run commands, and change state. The
interesting question is never "can it help?" but "what is it permitted to do when
nobody is watching?"

**You do not need a terminal agent installed to complete this elective.** A
captured session ships with the scenario, and a policy you can defend is the
deliverable either way. If you do have one installed, run the task for real and
say so in your note - live evidence and captured evidence are both honest, as
long as you state which you have.

## The material

| File | What it is |
|---|---|
| `fixtures/cli_session_transcript.md` | A captured session: approvals, one denial, and one entry that granted more than intended |
| `fixtures/repo_safe_task.md` | A read-only task for this repository, safe to run anywhere |
| `work/permission_policy.md` | Your allow / ask / deny policy |

## The task

1. **Decide the default posture first.** Everything else is a deviation from it,
   and the default matters more than any single entry.
2. **Work the task** in `fixtures/repo_safe_task.md`, live or from the captured
   transcript, and write down every command an agent would need for it.
3. **Write at least three rules.** Each one: the command, the verdict
   (`allow` / `ask` / `deny`), why, and the blast radius if the verdict is wrong.
4. **Break it on purpose.** Ask for something outside the policy - a write, a
   network call, a command outside the working directory - and record what
   actually happened rather than what should have.
5. **Name the boundary.** What does an allowlist not protect against? If you
   cannot answer that, the control is a belief.

## Three questions worth answering in the note

1. What does an allowlist entry actually grant - a command, a command with any
   arguments, or a shell? The difference is the whole risk.
2. What is the blast radius of the directory the agent was started in?
3. Would you be able to reconstruct tomorrow what an agent ran tonight?
   Traceability (Nachvollziehbarkeit) is not an afterthought in a regulated
   environment.

## Safety rules for this elective

- Do not run any of this against a repository with production credentials in the
  environment.
- Do not allowlist a broad shell entry to save time. That shortcut is the risk
  this elective is about.
- Nothing in this elective needs write access to anything outside this checkout.
