# Criteria for judging durable context

Use these before editing, after the rewrite, and after deleting one rule. They
are deliberately mechanical: a rule you cannot check is a wish.

## Evidence label

- Route: `local` / `live explicitly attached`
- Output: `local candidate` / `observed live`
- Target role:
- Intended production instruction path:
- Intended `applyTo` glob, if path-scoped:

| Criterion | The question | Failure looks like |
|---|---|---|
| **Checkable** | Could a reviewer say "yes" or "no" without a debate? | "Write clean, idiomatic code" |
| **Scoped** | Does it say where it applies - repository, path, file type, task? | A test-only rule applied to everything |
| **Verifiable in output** | Could you tell from a generated diff whether it was followed? | "Be careful about performance" |
| **Durable** | Will it still be true in six months? | A pinned model name, a version number, a person's name |
| **Non-conflicting** | Does another rule contradict it? | "Always add type hints" plus "keep changes minimal" with no priority |
| **Right home** | Repository rule, path rule, prompt file, or personal preference? | A personal style preference in a shared file |
| **Enforceable elsewhere?** | Should this be a test, a linter, or a CI check instead? | An invariant defended only by an instruction |

## The four failure modes, named

1. **Unfalsifiable** - nobody can tell whether it was followed.
2. **Expiring** - it pins something that changes underneath it.
3. **Misplaced** - a personal preference in a team file, or a team rule in
   personal settings.
4. **Unverified** - it was never tested, so nobody knows whether it does anything.

## The two-line test

For every rule, write:

```
A reviewer checks this by: <what they look at>
If it is violated, this breaks: <what actually goes wrong>
```

If either line is hard to write, the rule is not ready. Delete it or make it
specific enough to survive the sentence.

## Stable comparison

Use the same input from `brief.md` before, after, and after deletion.

- Starting-draft score:
- Rewritten-draft score:
- Rule removed:
- Material difference, or `no material difference`:
- Keep, rewrite, or delete:

## Control boundary

- Behavior this instruction can guide:
- Deterministic control it cannot enforce:
- Owner or system that should enforce that boundary:
