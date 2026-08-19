# Lab 0 - Preflight (before the day) and landing check

**Preflight:** complete **before** the workshop day, in your own time (30-45 min).
**Landing check on the day:** 09:00-09:20 (20 minutes).
**Loop stage:** none yet - this is the setup that makes the loop possible.

A room of 16 engineers debugging virtual environments at 09:15 costs the whole
cohort an hour of the day. Preflight is the single highest-leverage thing you can
do for the workshop, and it is on you, not on the facilitator.

---

## Outcome

You arrive with a working environment, known model access, a clear picture of what
your organisation has and has not enabled, and a repository state you can reset to.

---

## Preflight - do this before the day

### 1. Tooling

```bash
python --version          # must report 3.12.x - the workshop baseline
git --version
code --version            # or your IDE of choice
```

**Python 3.12.x is the baseline**, and it is the version the platform is built and
verified against. Any 3.12 patch release is fine. A newer minor version is not:
if `python --version` reports something else, create the virtual environment below
from a 3.12 interpreter explicitly (for example `python3.12 -m venv .venv`) rather
than hoping it works on the day.

### 2. Repository and environment

```bash
git clone <repo-url>
cd githubcopilotworkshop

python -m venv .venv
source .venv/bin/activate       # macOS/Linux
# .venv\Scripts\Activate.ps1    # Windows PowerShell

pip install -e ".[dev]"
```

### 3. Preflight check

```bash
python scripts/workshop_doctor.py    # environment and repository structure
pytest -q                            # the test baseline
```

Two commands, because they answer two different questions.

`workshop_doctor.py` reports your Python version, whether the expected
dependencies import, whether the repository revision and the expected baseline
files are present, whether `settings.yaml` and `instruments.json` are structurally
valid, and a few environment hints - it tells you whether a relevant variable is
set, never what it contains. Read the whole output rather than scanning for the
absence of red; a warning you skim past now is a broken lab at 11:00.

What the doctor deliberately does **not** do: it does not run the test suite, it
does not generate sample data, and it cannot see inside your IDE, so it says
nothing about whether Copilot is signed in or reachable. `pytest -q` covers the
first of those, and step 4 below covers the last - by hand, because no script can
do it for you.

If `scripts/workshop_doctor.py` is not present in your checkout, run this instead
and note anything that fails:

```bash
python -c "import sys; print(sys.version)"
pytest -q
```

> **The baseline must be green, and that means both commands.** On a clean
> checkout the doctor reports no failures **and** `pytest -q` shows no failing
> tests. A green doctor with a red test run is not a passing baseline, and neither
> is the reverse.
>
> Nothing in this repository is "expected to fail" before the
> day. The broken checks you will investigate are
> introduced by the scenario tooling when you run
> `python scripts/workshop.py start <scenario-id>` during a lab, and they
> disappear again on `reset`. So a red preflight means a real problem - a wrong
> Python version, a missing dependency, a partial checkout - and it is much
> cheaper to fix now than at 09:10.

### 4. Copilot access

If you are using the primary live route:

1. Sign in to GitHub Copilot in your IDE.
2. Open Chat and record whether you get an answer to a trivial question about
   this synthetic repository.
3. Open the **model picker** and write down what is actually listed for you. Do
   not look for a specific model name - the workshop never requires one. See
   [reference/model_selection.md](reference/model_selection.md).
4. Record which chat workflows you have: **Ask**, **Plan**, and **Agent**.

If sign-in, entitlement, policy, or the network blocks any step, write down the
observed blocker and select the local/captured lane. Do not bypass policy and do
not treat unavailable Copilot access as a failed repository baseline.

References:
<https://docs.github.com/en/copilot/how-tos/chat-with-copilot/chat-in-ide> -
<https://code.visualstudio.com/docs/chat/chat-overview> -
<https://code.visualstudio.com/docs/agents/run/planning>

### 5. Policy reality check (15 minutes, and worth every one)

Answer these for **your** organisation. "I do not know" is a valid answer to bring
to the room - it is often the most useful thing an attendee contributes all day.

- [ ] Which Copilot plan or entitlement is assigned to me, is it personal or
      organisation-managed, and who administers it?
- [ ] Which models appear in my picker?
- [ ] Is the **cloud agent** enabled for me, and for which repositories?
- [ ] Is **Copilot code review** enabled?
- [ ] Are **MCP servers** allowed, and is there an allowlist or private registry?
- [ ] Is **Copilot CLI** installed or installable on my machine?
- [ ] Do we meter **premium requests**, and is there a budget I should respect?
- [ ] Are there **content exclusion** rules on my work repositories?
- [ ] Has our works council (Betriebsrat) agreed how usage data may be used?

Sources: <https://docs.github.com/en/copilot/concepts/policies> -
<https://docs.github.com/en/copilot/reference/copilot-feature-matrix> -
<https://docs.github.com/en/copilot/concepts/context/content-exclusion>

Nothing in this workshop assumes any of these are switched on. Every lab has a
path that works when the answer is "no".

### 6. Bring

- A laptop allowed to run the synthetic repository, or the organizer-provided
  managed environment. You do not need permission to install a particular
  editor extension for the offline route.
- Headphones, if a noisy room is hard for you.
- One sanitized, one-sentence problem pattern from your own work, with no code,
  personal data, customer data, secrets, or internal identifiers. You will use
  it only to plan transfer in Lab 7. Use the supplied toy problem instead if
  bringing even a sanitized example is not approved.

---

## On the day: 09:00-09:20 landing check

**09:00-09:20 (20 minutes).** Not a lecture. Three things happen:

1. **Green light (10 min).** In a pair, solo, or with a helper, run the two
   preflight commands - `python scripts/workshop_doctor.py` and `pytest -q`.
   Share only the pass/fail result unless you choose to show more. Two people
   looking at one terminal often find setup problems faster, but pairing is not
   required.
2. **Recovery lane (running in parallel).** If your environment is broken, raise a
   hand now. Your options, in order:
   - the facilitator's fix list for the three most common failures,
   - a devcontainer or Codespace if your organisation permits it,
   - **pair mode**: work on your partner's machine for the day, taking the
     navigator and reviewer roles. This is a full-value path, not a consolation
     prize. Lab 4 is entirely a reviewer's lab.
3. **Room contract (5 min).** Times are 24-hour. Breaks are protected. No
   leaderboards. Ask questions in German if that is easier; answers come in
   English. The organisers do not collect your working material - no prompts,
   transcripts, keystrokes, code, or individual lab work. Optional feedback is a
   separate, transparent process. What the assistant itself processes and
   retains is set by your GitHub plan and your organisation, so apply the
   data-minimisation rule anyway
   (see
   [reference/dach_conventions.md](reference/dach_conventions.md#3-data-protection-datenschutz-and-data-minimisation)).

### Landing acceptance

- [ ] `python scripts/workshop_doctor.py` reports no failures, or the manual
      equivalent runs clean
- [ ] `pytest -q` is **green** on the clean checkout, before any scenario is
      started
- [ ] Copilot Chat answers a question about this repository, **or** you recorded
      the blocker and selected the local/captured lane
- [ ] You can name what the picker offers, say "Auto only", or say "unavailable"
- [ ] You know your three most likely policy blockers
- [ ] You have a scratch file open for evidence notes
      (see [reference/evidence.md](reference/evidence.md))

---

## Reflection and retrieval

Write one sentence in your evidence note:

> The capability I am least sure my organisation has enabled is ____, and the way
> I will find out is ____.

You will answer this again at 16:35 in Lab 7.

---

*Next: [Lab 1 - The operator model](lab_01_operator_model.md)*
