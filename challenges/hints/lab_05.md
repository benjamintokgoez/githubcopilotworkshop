# Hints - Lab 5 (electives)

General: 40 minutes is enough to configure one thing and test it. It is not enough
to configure three things and test none. If you are running out of time, cut the
configuration, never the verification.

## 5A - Secure MCP context

<details>
<summary><strong>L1 - Orientation</strong></summary>

- Start by listing what the server exposes before you use any of it. The inventory
  is the deliverable, not the demo.
- "Read-only" is a property you should verify, not a label you should trust.

</details>

<details>
<summary><strong>L2 - Method</strong></summary>

- Prove the answer came from the tool: ask something that cannot be answered from
  the repository text alone, then check the tool call actually happened.
- Turn off half the tools and try your task again. If it still works, you did not
  need them - that is your least-privilege configuration.

</details>

<details>
<summary><strong>L3 - Structure</strong></summary>

```
Server:            <name, how it runs, where it runs>
Reaches:           <systems and data it can touch>
Tools offered:     <list>
Tools enabled:     <list>  Why: <one line each>
Tools disabled:    <list>  Why: <one line each>
Negative test:     <what you asked for outside scope> -> <what actually happened>
Not protected against: <one sentence>
Approval needed from: <role>
```

</details>

## 5B - CLI permissions and sandboxing

<details>
<summary><strong>L1 - Orientation</strong></summary>

- Before configuring anything, run one session and simply count the approval
  prompts. That count is your baseline.
- Start the session in a directory whose contents you are willing to lose.

</details>

<details>
<summary><strong>L2 - Method</strong></summary>

- Allowlist the narrowest thing that removes a prompt you saw, then re-run and
  confirm exactly that prompt disappeared and no other did.
- Test the boundary deliberately. An untested control is a belief.
- If an entry grants more than you expected, that is the finding worth reporting
  at 15:50.

</details>

<details>
<summary><strong>L3 - Structure</strong></summary>

```
Default posture:     <prompt for everything / free-running>
Allowlisted:         <entries>  Scope each one actually grants: <...>
Still gated:         <what remained>
Negative test:       <request> -> <observed behaviour>
Would allow on a shared or CI machine:   <...>
Would never allow there:                 <...>
Not protected against:                   <one sentence>
```

</details>

## 5C - Customization

<details>
<summary><strong>L1 - Orientation</strong></summary>

- Capture the "before" output first. Without it you cannot show the rules did
  anything.
- Pick rules from today's invariants. They are already specific, which is exactly
  what makes a rule effective.

</details>

<details>
<summary><strong>L2 - Method</strong></summary>

- A rule you cannot check is a wish. Rewrite "write clean code" as something a
  reviewer could mark pass or fail.
- Verify the rule is applied by omitting it from your prompt entirely. If you have
  to mention it, the durable context is not doing the work.
- Distinguish shaping from enforcing: anything that must be guaranteed belongs in a
  test or a CI check.

</details>

<details>
<summary><strong>L3 - Structure</strong></summary>

```
Task used for before/after: <small, repeatable>
Rule 1: <checkable statement>   Observable effect: <yes/no, what changed>
Rule 2: ...
Rule 3: ...
Deleted: <rule with no observable effect>
Needs a test or CI check instead: <which rules>
Where it lives: <repository / path-scoped / personal>  Why: <one line>
```

</details>
