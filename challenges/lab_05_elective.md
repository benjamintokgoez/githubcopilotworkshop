# Lab 5 - Elective (choose exactly one)

<!-- journeys:card:5:start -->
## Run card

| Decision | This lab |
|---|---|
| Outcome | Test one control, its negative case, and its limits. |
| First action | Choose 5A, 5B, or 5C below; start only that branch. If unsure, choose 5C. |
| Edit boundary | The selected elective's work/ directory only. |
| Evidence | `.workshop-state/notes/lab-05-choice.md`; private and Git-ignored. |
| Lane boundary | Supported: one positive and one negative case plus decision. Core: branch checklist and structure check. Extension: one follow-up question only. |
| Delivery | Default: **captured/offline**. Routes: local, captured/offline, live. Mode does not raise or lower the lane; follow the acceptance checklist. |
| Clock | **35 elapsed minutes**; cohort **15:00-15:35 Europe/Berlin**. [Self-paced route](README.md#self-paced-route): start at T+0, pause between phases, keep the same cuts. |
| Recovery | Keep the actual result in your private note; use the supplied capture or approved route. |

**Phase clock** (elapsed minutes; solo work uses the left column):

| Elapsed | Cohort | Phase |
|---|---|---|
| T+0-5 | 15:00-15:05 | Understand/Plan |
| T+5-18 | 15:05-15:18 | Implement/Test |
| T+18-25 | 15:18-15:25 | Review |
| T+25-29 | 15:25-15:29 | Explain |
| T+29-33 | 15:29-15:33 | Verify and reset |
| T+33-35 | 15:33-15:35 | Cross-elective awareness |

**Cuts — move on with honest evidence:**
- **T+3 / 15:03:** If the preflight-approved live route does not work, use the capture; no installation or sign-in.
- **T+18 / 15:18:** Stop adding configuration; use captured observations if needed.
- **T+29 / 15:29:** Stop work; verify and reset.
- **T+33 / 15:33:** Keep the control / negative case / limitation report.

[Return: Lab 4](lab_04_review_and_delegation.md) · [Next: Lab 6](lab_06_capstone_transfer.md) · [All labs](README.md) · [Terms](README.md#terms-used-in-the-labs)
<!-- journeys:card:5:end -->

**Block:** 15:00-15:35 (35 minutes) - **Mode:** pairs or solo
**Loop stages:** Understand/Plan -> Implement/Test -> Review -> Explain

---

## Choose one outcome, one route, and one lane

Thirty-five minutes means **one** bounded elective. It does not include product
installation, sign-in, registry approval, or enterprise configuration. Those are
preflight activities. Do not spend the block trying to turn a red preflight check
green.

| Elective | Best fit | Scenario id | Honest default |
|---|---|---|---|
| **5A - [Secure MCP context](lab_05a_secure_mcp.md)** | Developers who integrate tools; architects or platform owners who approve data access | `elective-mcp` | Analyse and reduce the local configuration, then trace captured tool evidence |
| **5B - [CLI permissions and confinement](lab_05b_cli_permissions.md)** | Terminal-heavy developers; platform, CI, and security architects | `elective-cli` | Build and test a permission policy against the captured session |
| **5C - [Customization that survives Monday](lab_05c_customization.md)** | Maintainers and architects who want shared standards to travel with the repository | `elective-customization` | Rewrite and test a scenario-local instruction proposal |

If you cannot decide, choose **5C**. It has no installation prerequisite and its
scope decisions transfer across Copilot surfaces.

### Pick the delivery mode before the timer starts

| Delivery mode | Use it only when | Evidence label |
|---|---|---|
| **Live** | The required client is Green in the T-72 capability matrix: installed, authenticated, policy-enabled, and smoke-tested | `live` |
| **Local** | The elective explicitly defines a personally executed local analysis, such as 5C's mechanical comparison | `local` |
| **Captured/offline** | Behavioural evidence comes from the shipped transcript, log, or other capture | `captured/offline` |

Working solo is an arrangement, not a delivery mode. Record it separately and
write both the operator and reviewer observations.

Local and captured/offline work still needs an edited artifact, a positive case,
a negative case, and a reviewable decision. Do not claim a configuration ran if
you only analysed it.

**Preflight gates:**

- **5A live:** an approved MCP host/server pair and disposable configuration are
  already tested. Policy may disable MCP or restrict supported clients through
  managed settings; cloud-agent MCP is a separate boundary.
- **5B live:** GitHub Copilot CLI is already installed and authenticated, the
  account has an active Copilot subscription, and organisation policy permits
  the CLI. The sandboxing documentation is public preview; both local and cloud
  CLI sandbox experiences currently require experimental features. Neither is
  required for this lab.
- **5C live comparison:** a Copilot chat surface is already working. The local
  analysis route needs only an editor and the scenario.

---

## Start exactly one scenario

```bash
python scripts/workshop.py start elective-mcp            # 5A
python scripts/workshop.py start elective-cli            # 5B
python scripts/workshop.py start elective-customization  # 5C
```

If staging is unavailable, use the matching fallback:

```bash
python scripts/workshop.py fallback <your-elective-scenario-id>
```

Do not start another elective. The room report provides measured awareness, not
competency, in the other two.

---

## The 35-minute block

Work stops at 15:29 so verification, reset, and the awareness report stay inside
the block.

Follow the [run card](#run-card). Every branch uses the same phase clock:
positive evidence during Implement/Test, negative evidence during Review,
then a decision and owner during Explain. Verification, reset, and the
awareness report stay inside the 35 minutes.

**Mandatory cut at 15:18:** stop adding configuration. If live work has not
produced evidence, move to the supplied capture and finish the same reasoning
there. Never cut the negative case or explanation to preserve setup work.

### Lane cuts

- **Supported:** complete the full loop on one positive event, one negative
  event, and one control decision. The full scenario verifier may remain red if
  Core-only fields are incomplete.
- **Core:** complete the shared and branch-specific evidence contract and the
  structural verifier. Live, local, or captured/offline mode can demonstrate Core
  engineering judgement.
- **Extension:** only after Core. During this block, record one follow-up
  question; do not add a second mechanism.

---

## Shared acceptance

| Evidence | Supported | Core |
|---|:---:|:---:|
| Elective, lane, delivery mode, and live surface operated (`none` unless live) | Required | Required |
| One bounded configuration, policy, or instruction artifact | Required | Required |
| Positive event or comparison attributed to a control | 1 | Complete branch trace |
| Negative event or comparison attributed to a control | 1 | Complete branch trace |
| What the control enforces and cannot enforce | Required | Required |
| Team decision, owner, policy dependency, and next test | Bounded decision | Complete branch template |
| Branch-specific evidence checklist and structural verifier | Actual result recorded | Pass required |

The positive evidence must be behavioural: a live observation, a captured event
traced to its control, or a repeatable rule-quality comparison. File presence
alone is not evidence. Predicted results remain labelled predictions.

---

## Resync checkpoint - 15:33

One person per represented elective gives a 30-second report:

1. What control was tested, and which part of the system enforced it?
2. What evidence changed your confidence?
3. What does the control **not** protect?
4. Is the product capability GA, preview, experimental, optional, or
   policy-dependent?

This is **cross-elective awareness**, not competency or coverage in an unchosen
elective. If an elective is unrepresented, the facilitator reads its captured
report card with the same three fields: control, negative case, limitation. Lab
7 checks recall of one control and one limitation from an unchosen elective.

Verify and reset before the report. Reset archives the attempt before restoring
the pre-start tree.

```bash
python scripts/workshop.py verify <your-elective-scenario-id>
python scripts/workshop.py reset <your-elective-scenario-id>
```

---

## Hints

[hints/lab_05.md](hints/lab_05.md) contains an answer-neutral three-level ladder
for each elective.

---

## Solo path

Choose one branch before T+0; branch reading and setup are part of its 35-minute
budget. Follow the elapsed run card. At T+18 stop adding configuration and
protect the negative case. At T+29 verify and reset. At T+33 read one unchosen
branch's control table and write `control / negative case / limitation`.
That is awareness, not completion of a second elective. Return to Lab 6.

---

## Reflection and retrieval

1. What is the smallest version of your elective you could propose next week
   without changing enterprise policy?
2. Which next step needs a decision from someone else, and which role owns it?
3. Name one thing your elective's control does **not** protect. Why would claiming
   broader protection be misleading?

---

*Next: [Lab 6 - Capstone](lab_06_capstone_transfer.md)*
