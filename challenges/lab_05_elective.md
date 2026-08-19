# Lab 5 - Elective (choose exactly one)

**Block:** 15:15-15:55 (40 minutes) - **Mode:** pairs or solo
**Loop stages:** Understand/Plan -> Implement/Test -> Review -> Explain

---

## Choose one. Not two.

Forty minutes is enough for one elective done properly and not enough for two done
badly. Half-finished configuration is worse than none, because it looks
configured.

| Elective | Choose it if | Scenario id |
|---|---|---|
| **5A - [Secure MCP context](lab_05a_secure_mcp.md)** | Your team wants an assistant that can see your systems (issues, telemetry, docs) and you own the decision about what it may reach | `elective-mcp` |
| **5B - [CLI permissions and sandboxing](lab_05b_cli_permissions.md)** | You work in terminals, run agents on servers or in CI, and need deny-by-default to be real rather than aspirational | `elective-cli` |
| **5C - [Customization that survives Monday](lab_05c_customization.md)** | Your team keeps re-explaining the same standards in every prompt and every review | `elective-customization` |

If you cannot decide: **5C** transfers to the widest range of teams, works with no
extra tooling, and has the fewest policy blockers.

### Policy check before you choose

All three electives can be blocked by organisation policy. Check your Lab 0 policy
answers before you commit 40 minutes:

- 5A needs MCP servers to be permitted. Some organisations restrict them to a
  registry or allowlist.
- 5B needs Copilot CLI to be installable on your machine.
- 5C needs nothing beyond an editor and this repository.

If your chosen elective is blocked, that finding is worth writing down - and then
switch to 5C.

---

## Start the scenario

Run exactly one command for the elective you chose:

```bash
python scripts/workshop.py start elective-mcp            # 5A
python scripts/workshop.py start elective-cli            # 5B
python scripts/workshop.py start elective-customization  # 5C
```

Do not run all three. If staging is unavailable, replace `start` with `fallback`
and work from the captured directory the command prints.

---

## Shared structure

The work stops at 15:50 so the final five minutes remain a room-wide resync.
Every elective follows the same 35-minute shape, and each elective file gives
you the specifics:

1. **Understand/Plan (7 min)** - what the mechanism actually controls, what it
   does not, and what evidence will be enough.
2. **Implement/Test (18 min)** - configure the smallest useful thing and prove it
   took effect.
3. **Review (5 min)** - try the thing the configuration should prevent. A
   control whose negative case you have not tested is a belief.
4. **Explain (5 min)** - write the team-facing paragraph required by the shared
   acceptance list.
4. **Explain (5 min)** - what you would take to your team, and what you would need
   permission for.

---

## Shared acceptance

- [ ] The configuration exists as a file or setting you can point at
- [ ] You demonstrated that it took effect - observed behaviour, not the presence
      of a config file
- [ ] You tested the negative case: the thing it should prevent was prevented, or
      you discovered it was not
- [ ] You wrote one paragraph you could send to your team, including the
      permission or approval you would need
- [ ] Your evidence note records the workflow and model choice, as in every lab

---

## Resync checkpoint - 15:50

Everyone stops. One person per elective gives a 60-second report:

- What the control actually protects.
- What surprised them.
- One thing they would **not** recommend to their team, and why.

You will hear about the two electives you did not take. That is the design: the
report is the coverage.

Before Lab 6 starts, verify and then reset the one active elective scenario.
Reset archives your attempt and prints its location before restoring the pre-start
tree:

```bash
python scripts/workshop.py verify <your-elective-scenario-id>
python scripts/workshop.py reset <your-elective-scenario-id>
```

---

## Hints

[hints/lab_05.md](hints/lab_05.md) - three collapsed levels, with a section per
elective.

---

## Reflection and retrieval

1. What is the smallest version of your elective you could ship to your team next
   week without asking anyone's permission?
2. What is the version that needs a decision from someone else, and who is that
   person?
3. Retrieval: name one thing your elective's mechanism does **not** protect
   against. Every control has a boundary; knowing it is the difference between
   security and theatre.

---

*Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
