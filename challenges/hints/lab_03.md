# Hints - Lab 3 (plan-driven migration)

<details>
<summary><strong>L1 - Orientation</strong> (where to look, what to ask first)</summary>

- The manifest is the scope. If you are looking at a file that is not in it, ask
  why before you edit it.
- The first thing to produce is not a plan. It is a **baseline**: what the code
  emits today, captured so you can compare later.
- The request is underspecified in one respect. Read it twice and ask: "what would
  two reasonable engineers do differently here?"

</details>

<details>
<summary><strong>L2 - Method</strong> (which step you are skipping)</summary>

- If you cannot verify a batch in under five minutes, the batch is too big. Split
  by module, not by idiom.
- If you are repeating a constraint in prompts, you have skipped the durable
  context step. Move it into a file and test that it is applied by omitting it from
  your next message.
- Happy-path tests do not prove a migration. The things that break silently are:
  inputs that used to be rejected, optional fields, aliases, and defaults.
- When a session says a change outside scope is "required", treat that as a claim
  to investigate. Sometimes it is true, and then it belongs in the plan.

</details>

<details>
<summary><strong>L3 - Structure</strong> (the shape of a good plan)</summary>

A supervisable migration plan has, per batch:

```
Batch N
  Files:            <from the manifest, explicit list>
  Idioms mapped:    <old -> new, one line each>
  Verification:     <exact command, expected result>
  Rollback point:   <how to get back if this batch goes wrong>
  Risk:             <what could silently change>
```

Plus, once, at the top:

```
Contract that must not change: <field names, types, error behaviour, units, timezones>
Ambiguity in the request:      <what it was, what I decided, why>
Out of scope:                  <explicitly listed>
```

If your plan has no "out of scope" section, it has no scope.

</details>
