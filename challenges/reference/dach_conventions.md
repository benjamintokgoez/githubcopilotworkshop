# Working conventions: DACH and European realities

These conventions apply to everything you write today: code, tests, review notes,
evidence, and the way you talk to each other. They are the same conventions that
cause real defects in real DACH systems.

**Scope note:** the exercises choose one deterministic presentation contract:
German (Germany) formatting, EUR, and `Europe/Berlin`. That is not a claim that
DACH is one locale. Austrian requirements may select `de-AT`; Swiss systems
commonly use `de-CH`, CHF, different number separators, and `Europe/Zurich`.
Those zones share the workshop's 2026 DST transitions, but production software
must follow its actual locale, currency, and IANA-zone requirements.

## 1. Time

- **Write 24-hour times.** `14:30`, not `2:30 PM`. This applies to schedules,
  logs, tickets, and screenshots.
- **Store UTC, display local.** Persist timezone-aware UTC timestamps. Convert to
  `Europe/Berlin` only at the presentation edge.
- **CET is UTC+1, CEST is UTC+2.** Never hard-code either. A fixed `+2` offset is
  correct for roughly half the year and silently wrong for the other half.
- **Daylight saving transitions are business events.** In 2026 the EU switches on
  Sunday 2026-03-29 (CET to CEST, local `02:00` does not exist) and Sunday
  2026-10-25 (CEST to CET, local `02:00` occurs twice). One local day that year is
  23 hours long and one is 25 hours long. See
  [invariants.md](invariants.md#5-time-and-calendar-invariants) for the exact
  UTC windows.
- **ISO 8601 for machines, `dd.MM.yyyy` for German-language humans.** Filenames
  and identifiers use ISO dates, because `2026-08-19` sorts and
  `19.08.2026` does not.

## 2. Numbers and money

- **Display uses a decimal comma and a dot as thousands separator**: `1.234.567,89`
  and `101,455`.
- **Code, config, JSON, and SQL use a dot**: `1234567.89`, `101.455`. A decimal
  comma inside `settings.yaml` or a JSON payload is a defect, not a localisation.
- **Formatting belongs at the edge.** Parse and compute on numbers, format once,
  as late as possible. Round-tripping a formatted string back into arithmetic is
  one of the most common defects in DACH reporting code.
- Aggregate display examples default to EUR. Instrument metadata or an explicit
  payload currency is authoritative; QuantCore performs no FX conversion.

## 3. Data protection (Datenschutz) and data minimisation

- **Do not paste personal data into prompts.** Names, emails, customer IDs,
  employee records, ticket bodies containing personal data: all out of scope for a
  prompt unless your organisation has cleared it.
- **Do not paste production secrets or credentials**, and do not paste code from a
  repository you are not allowed to share.
- **Minimise, do not maximise, context.** "Give the model everything" is bad
  privacy practice and usually bad engineering practice. Give it the smallest
  context that makes the task decidable.
- **Content exclusion exists** for files that must never be sent:
  <https://docs.github.com/en/copilot/concepts/context/content-exclusion>.
- **The workshop organisers do not collect working material.** Facilitators do
  not gather prompts, transcripts, keystrokes, code, or individual lab work, and
  no individual artifact or rubric score is stored by them. Lab 6 uses private
  self/peer scoring; a facilitator may give feedback on an artifact a participant
  chooses to show in the room, without recording it. Optional feedback states
  separately what it collects and why. If your employer wants to collect working
  material after the workshop, that is a separate decision that needs a
  documented purpose, transparency towards the people affected, an appropriate
  lawful basis, and the privacy and works-council review your organisation's
  policy requires. "We enabled it and told nobody" is not a plan.
- **Do not assume consent is the answer.** In an employment context, consent is
  frequently *not* the appropriate lawful basis, precisely because the power
  imbalance makes "freely given" hard to argue; other bases are often the correct
  ones. Which applies is a determination for your privacy function and, where
  relevant, your works council - this material is deliberately not legal advice
  and will not tell you which basis to pick. The useful engineering habit is
  simply to ask *who decided this, on what documented basis, and were people
  told* before usage data starts flowing.
- **Be precise about the scope of that guarantee.** It applies to the people
  running the workshop and to participants' working material. It is **not** a
  claim about the assistant, the IDE, or any other platform you use: those are
  products, and what they transmit, process, and retain is governed by your
  GitHub plan and your organisation's settings, not by this room. Treat the
  product side as a question to answer with your own policy
  documentation - see
  <https://docs.github.com/en/copilot/concepts/policies>,
  <https://docs.github.com/en/copilot/concepts/context/content-exclusion>, and
  <https://docs.github.com/en/copilot/get-started/enterprise-ai-governance> -
  and note that this is exactly why the minimisation rules above apply even when
  nobody in the room is recording anything.

## 4. Works council and organisational governance

In Germany and Austria, tooling that can produce individual performance data is
usually a co-determination topic.

- **Betriebsrat** (works council) and **Mitbestimmung** (co-determination): if
  usage metrics can be attributed to a person, expect a works agreement
  (`Betriebsvereinbarung`) to be required before rollout.
- Prefer **aggregate, non-individual** measurement. Team-level adoption trends are
  usually defensible; per-developer acceptance rates usually are not.
- Administrators can see what is available and what is used:
  <https://docs.github.com/en/copilot/concepts/copilot-usage-metrics> and
  <https://docs.github.com/en/copilot/how-tos/administer-copilot/manage-for-organization/manage-policies>.
- **Vier-Augen-Prinzip** (four-eyes principle) already governs most of your
  release process. Agent-generated changes do not get an exemption. Lab 4 is
  built around this.
- **Nachvollziehbarkeit** (traceability): a change you cannot explain is a change
  you cannot ship, regardless of who or what wrote it.

## 5. EU AI Act literacy - governance framing, not legal advice

This workshop is **not legal advice** and does not classify any system.

What is useful for you as an engineer:

- The EU AI Act is a product-and-risk regulation. Obligations depend on the
  **role** your organisation plays (provider, deployer) and the **risk category**
  of the system. Your legal and compliance function decides both. You do not.
- Organisations are expected to build **AI literacy** in staff who use these
  systems. A day like this one contributes to that; it does not discharge it.
- Two things engineers reliably own regardless of classification:
  **traceability** (what was generated, reviewed, and by whom) and
  **human oversight** (a competent person can understand, override, and stop it).
  Both are the point of the loop you practise today.
- Primary sources, if you want them: the regulation itself
  (<https://eur-lex.europa.eu/eli/reg/2024/1689/oj>) and the Commission's
  overview (<https://digital-strategy.ec.europa.eu/en/policies/regulatory-framework-ai>).
  GDPR itself: <https://eur-lex.europa.eu/eli/reg/2016/679/oj>.
- Vendor-side governance material lives in the GitHub Trust Center
  (<https://github.com/trust-center>) and
  <https://docs.github.com/en/copilot/get-started/enterprise-ai-governance>.

Bring specific questions back to your own compliance colleagues. The correct
answer to "is this high-risk?" from a facilitator is "ask your legal function".

## 6. Accessibility

- Everything in this repository is keyboard-navigable Markdown. There are no
  screenshots that you must be able to see in order to complete a lab.
- No instruction depends on colour alone. If a lab says "the red line", it also
  says what the line contains.
- Facilitators state times out loud and also write them down.
- You may resize, restyle, or read these materials in any tool you like. Nothing
  requires a specific editor theme or font.
- If a demo is shown on a shared screen, the same content exists as text in the
  lab file. You never have to squint to keep up.
- Ask for what you need (breaks, captions, a quieter room, a written copy). No
  justification required.

## 7. Language and psychological safety

- The workshop language is English. Plain, short sentences; idioms avoided.
- Ask your question in German if that is easier; the answer will come in English
  so the whole room benefits, and the facilitator will confirm you got what you
  needed.
- Operational German terms are collected in
  [glossary_en_de.md](glossary_en_de.md). We do not translate the whole
  curriculum: a duplicated German track would drift out of date and split the room.
- No leaderboards, no "who finished first", no public failure. Every lab has a
  Supported lane and a resync checkpoint precisely so that being behind is
  survivable and normal.
- "I do not trust this output" is a complete and respected contribution.
