# Pilot checklist

Run a pilot before publishing the workshop as ready. The pilot must test learning transfer and operational recovery, not only that a demo works.

## Cohorts

- [ ] Include a representative technical cohort: mixed experience, keyboard layouts, language confidence, accessibility needs, and remote/onsite participation.
- [ ] Include an enterprise-restricted cohort: Copilot policy restrictions, proxy/TLS inspection, SSO, limited Actions/MCP/cloud-agent access, and restricted package indexes.
- [ ] Use synthetic or approved data and disposable repositories throughout.

## Pilot execution

- [ ] Run the canonical 09:00-17:15 schedule, including every protected break,
      lunch, and all 60 minutes of slack.
- [ ] Start with one helper per six participants or a floating technical
      producer; record privacy-safe queue counts and wait distributions.
- [ ] Execute Supported/Core/Extension evidence and live/captured delivery as
      separate dimensions for every lab.
- [ ] Trigger each recovery scenario in `RECOVERY_PLAYBOOK.md` at least once across pilots.
- [ ] Test clean-room checkpoint validation: fresh clone, known fixture, focused test, bounded patch, diff review, reset.
- [ ] Test keyboard-only, captions, zoom, quiet/solo route, and readable documents with representative users.
- [ ] Check German keyboard, decimal, date, and time examples in the actual room.
- [ ] Collect only the minimum approved feedback; no full prompt capture or surveillance.
- [ ] Confirm participants can self-score transfer with `ASSESSMENT_RUBRIC.md`;
      do not collect individual artifacts or scores. Use aggregate, anonymous
      feedback to improve the workshop.

## Quantitative release thresholds

Collect only anonymous aggregate counts and timings after notice. For a
16-person cohort, report counts and percentages. Never collect prompts, code,
individual artifacts or scores, lane histories linked to people, or identifiable
performance telemetry.

| Measure | Release threshold | Revise or hold |
|---|---|---|
| Preflight | >=90% Green before arrival; 100% assigned a viable mode by 09:15 | >10% need day-of repair |
| Per-lab Core | >=70% of preflight-Green Core entrants meet lane evidence | <60% in any two core labs |
| Supported evidence | >=90% show at least three loop stages plus uncertainty/next action | >10% blank or verifier-only artifacts |
| Lab 3 transfer | >=70% baseline + edited plan + verified batch + review/handover; >=50% full Core | <70% reach verified batch |
| Lab 6 transfer | >=80% bounded plan + tested slice + self-review + uncertainty; >=60% Core | <75% independent transfer or role gap >15 points |
| Hint use | L1 20-60%; L2 <=35%; L3 <=15% | L3 >25% |
| Reset | >=98% first attempt within 2 min; 100% within 5 min; zero lost work | Any lost work or next-lab block |
| Helper queue | p95 <4 min; <=2 pairs per helper; nobody >5 min | Queue >2 pairs for >5 min in two labs |
| Tool latency | p90 assistant turn <90 sec; captured switch within 2 min | >10% wait through a second slow retry |
| Schedule | breaks within 2 min, lunch within 5, capstone within 5, finish 17:15; >=10 min Slack C remains in 80% of pilots | Any break cut, capstone >10 min late, routine late finish |
| Slack | median lab consumes <=5 min adjacent slack; debt <=5 min at lunch/capstone | median consumes >10 min cumulative |
| Captured mode | >=80% meet engineering evidence and label it captured | live-operation claims or >15-point mode gap |
| Elective awareness | >=80% name one control and limitation from an unchosen elective | <70%; do not call reports coverage |
| Immediate retrieval | >=75% answer 4/5 | <65% |
| One-week retrieval | voluntary repeat retains >=60% | no feasible delayed route |
| Adoption | >=80% have one dated action, owner where needed, and success signal | mostly undated/multiple aspirations |
| Remote parity | completion and partial evidence within 10 points of in-room | gap >15 points or p95 help >5 min |

Run at least two timed pilots, including one enterprise-restricted or hybrid
cohort, before normal release.

## Exit criteria

- [ ] Every objective has a captured/offline fallback path.
- [ ] No lab requires credentials, production data, or an unavailable service.
- [ ] The quantitative thresholds above are met or the release decision is
      explicitly `revise`/`hold`.
- [ ] Red incidents have an owner and a tested recovery; amber incidents are explicitly non-critical-path.
- [ ] Accessibility blockers are fixed or have a documented equivalent adjustment.
- [ ] Timing stays within the published ranges while preserving breaks and verification.
- [ ] Facilitator, helper, and organizer sign off the release checklist.

## Pilot record template

```text
Pilot date / zone:
Cohort:
Facilitator / helpers:
Product and repository revision:
Green paths:
Amber paths and fallback:
Red paths and owner:
Clean-room checkpoint result:
Accessibility adjustments:
Timing changes:
Evidence of transfer:
Decision: release / revise / hold
Next review date:
```
