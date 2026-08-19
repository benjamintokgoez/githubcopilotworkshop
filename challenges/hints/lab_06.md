# Hints - Lab 6 (capstone)

These hints deliberately do not tell you which claim in the brief is wrong, and no
level names a library or an implementation.

<details>
<summary><strong>L1 - Orientation</strong> (which assumption to check first)</summary>

- List every assumption the brief makes about **time** before you write code.
  There are more than you think, and they are the ones with expected values printed
  in the lab.
- The three business dates in the acceptance table were not chosen at random. Ask
  yourself why those three.
- If a suggestion arrives with a constant in it, ask where that constant came from
  and when it stops being true.

</details>

<details>
<summary><strong>L2 - Method</strong> (which step you are skipping)</summary>

- Write the three window tests first. They are the specification, and they will
  reject a wrong approach in seconds rather than in review.
- Keep computation and formatting apart. If a formatted string can reach an
  arithmetic path, you have a defect waiting for a bigger number.
- Test the boundary explicitly: a record whose timestamp equals the window end
  belongs to the next day.
- Do not extend the task. Any output beyond the three that were asked for is scope
  creep, and scope is on the acceptance list.

</details>

<details>
<summary><strong>L3 - Structure</strong> (the shape of a good result)</summary>

```
workshop/scenarios/capstone-transfer/work/
  daily_export.py       window(business_date) -> (start_utc, end_utc)
                        filename(business_date) -> str
                        display_total(amount, currency) -> str
  test_daily_export.py  three dated window cases, one boundary case,
                        one filename case, one formatting case
  NOTES.md              workflow + model choice, the claim you rejected,
                        the three-part uncertainty sentence
```

Acceptance targets are printed in the lab: three windows, one filename, one
formatted total. If your tests assert those values and pass, you are done - resist
adding more.

</details>
