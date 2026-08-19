# DACH delivery notes

This is delivery guidance, not legal advice. The organizer remains responsible for local employment, privacy, security, accessibility, and AI-governance decisions.

## Time and notation

- Publish the agenda in **CET/CEST** and include UTC in the same line, for example: `09:00 CEST (07:00 UTC)`.
- Name the zone as `Europe/Berlin` or the participant’s actual IANA zone when locations differ; do not rely on “CET” during daylight-saving time.
- Use the **24-hour clock** and ISO dates (`2026-08-19`) in links, tickets, and run sheets.
- Reconfirm daylight-saving transitions and calendar invitations; do not assume every DACH participant is in the same country or time zone.

## Language and keyboard conventions

| Context | Use |
| --- | --- |
| Code and commands | Keep commands, identifiers, and error text unchanged; explain in plain English |
| Participant-facing phrase | “Please take a break.” / “Bitte machen Sie eine Pause.” |
| Support | “I can help privately.” / “Ich helfe Ihnen gern vertraulich.” |
| Uncertainty | “We do not know yet.” / “Das wissen wir noch nicht.” |
| Verification | “What evidence would change your mind?” / “Welche Evidenz würde Sie umstimmen?” |
| Governance | “This tool is optional and policy-bound.” / “Dieses Tool ist optional und durch Richtlinien begrenzt.” |

- Demonstrate both US and German keyboard paths where shortcuts differ; do not assume `Ctrl`, `Cmd`, `AltGr`, or a US layout.
- German layouts include `ß`, umlauts, and `AltGr`; display exact keys in text and offer mouse/menu alternatives.
- Clarify decimal conventions: German prose commonly uses comma for decimals and period for thousands; Python/code/data formats commonly require a period decimal separator and may require a dot in machine-readable numbers. Keep examples unambiguous and label units.
- Explain quotation marks, path separators, date formats, and CSV delimiters when they affect a command. Never “fix” a participant’s locale silently.
- Keep identifiers and code in English unless the lab explicitly tests localization; use accessible international English in explanations.

## Data protection, works councils, and AI literacy

- Use fictional, synthetic, or organizer-approved data only. No production or customer code, personal data, secrets, or confidential business material in prompts, repositories, logs, captures, or feedback.
- Explain what is collected, why, who can access it, and when it is deleted before any telemetry or recording. Make non-recorded participation possible where practical.
- In Germany, employee monitoring and technical systems that may monitor behavior or performance can engage works-council consultation rights; coordinate with the organizer and works council before enabling telemetry, recording, or individual scoring. See German Works Constitution Act §87: https://www.gesetze-im-internet.de/betrvg/__87.html
- Discuss human oversight, transparency, safe use, and AI literacy as operational practices, not as a compliance certification. The EU AI Act includes AI-literacy obligations and transparency provisions; applicability depends on role and system. See Regulation (EU) 2024/1689: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
- Do not give legal conclusions. Route questions to the organizer’s privacy, works-council, security, and legal contacts.

## Corporate proxy and SSL realities

- Enterprise proxies, TLS inspection, SSO, allowlists, private package indexes, and runner egress can change behavior without a code defect.
- Test approved proxy and certificate instructions before the session. Never advise disabling certificate validation, bypassing SSO, or pasting a corporate token into a prompt.
- Keep a local-only lane and sanitized captures for every network-dependent activity.

## Mixed-English room norms

- State that questions may be asked in English or German; answer in the language that preserves clarity.
- Put important instructions in writing, speak at a measured pace, avoid idioms and culturally loaded jokes, and define acronyms.
- Allow silent reading and individual work; do not equate quick English speaking with technical confidence.
- Ask before switching languages or translating someone’s contribution. Do not stereotype by nationality, accent, age, role, or communication style.
- Use anonymous or private help routes for questions involving policy, accessibility, or safety.

## Breaks and pacing

- Keep the published breaks; add a short reset after a cognitively dense block.
- Offer water, a quiet seat, and a no-camera option where feasible. Avoid scheduling essential content over lunch or religious observance known to the organizer.
- Make pair rotation optional and avoid forced networking.

## References

- European Commission time and daylight-saving overview: https://transport.ec.europa.eu/transport-themes/summertime_en
- GDPR, Article 5 principles: https://eur-lex.europa.eu/eli/reg/2016/679/oj
- EU AI Act, Regulation (EU) 2024/1689: https://eur-lex.europa.eu/eli/reg/2024/1689/oj
