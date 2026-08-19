# Review thread - PR #212

Captured comments already on the pull request when it reached you. Synthetic;
the reviewers are roles, not people.

---

**Reviewer A (platform, drive-by)** - 2026-08-14, 09:12 CEST

> Skimmed it. Clean helpers, single place for the convention, tests are green.
> LGTM from my side, though I have not looked at the risk maths.

---

**Reviewer B (risk reporting, the requester)** - 2026-08-14, 10:41 CEST

> Two questions before I can say anything useful:
>
> 1. We parse this response by field name. Did anything about the response shape
>    change? The ticket says it must not.
> 2. Which direction did you settle on for the sign, and against which of our
>    conventions did you check it?
>
> Also, why are the store and the serialiser in this diff? I did not ask for
> either, and I do not know what they do.

---

**Author (agent run, automated reply)** - 2026-08-14, 10:44 CEST

> Thanks for the review. The response shape is unchanged and existing consumers
> are unaffected. The sign convention follows the profit-and-loss reading, which
> keeps the dashboard sort order intuitive. The store and serialiser changes are
> small robustness and formatting improvements made while the files were open.

---

**Reviewer B** - 2026-08-14, 10:58 CEST

> That answers the second question. I am not sure it answers the first one.
> Assigning to whoever picks up the review rota today.

---

*No further comments. The thread is where you inherit the review, and the last
unanswered question is a legitimate starting point.*
