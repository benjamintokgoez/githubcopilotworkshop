# Pilot checklist

Run a pilot before publishing the workshop as ready. The pilot must test learning transfer and operational recovery, not only that a demo works.

## Cohorts

- [ ] Include a representative technical cohort: mixed experience, keyboard layouts, language confidence, accessibility needs, and remote/onsite participation.
- [ ] Include an enterprise-restricted cohort: Copilot policy restrictions, proxy/TLS inspection, SSO, limited Actions/MCP/cloud-agent access, and restricted package indexes.
- [ ] Use synthetic or approved data and disposable repositories throughout.

## Pilot execution

- [ ] Run the complete one-day schedule, including all breaks and buffer.
- [ ] Verify helper ratio of about 1:8–10 and record where queues formed.
- [ ] Execute Supported/Core/Extension lanes and captured/offline fallback for each lab with optional cloud tooling.
- [ ] Trigger each recovery scenario in `RECOVERY_PLAYBOOK.md` at least once across pilots.
- [ ] Test clean-room checkpoint validation: fresh clone, known fixture, focused test, bounded patch, diff review, reset.
- [ ] Test keyboard-only, captions, zoom, quiet/solo route, and readable documents with representative users.
- [ ] Check German keyboard, decimal, date, and time examples in the actual room.
- [ ] Collect only the minimum approved feedback; no full prompt capture or surveillance.
- [ ] Confirm participants can self-score transfer with `ASSESSMENT_RUBRIC.md`;
      do not collect individual artifacts or scores. Use aggregate, anonymous
      feedback to improve the workshop.

## Exit criteria

- [ ] Every objective has a captured/offline fallback path.
- [ ] No lab requires credentials, production data, or an unavailable service.
- [ ] At least 80% of pilot participants can complete the transfer workflow or identify a supported next step.
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
