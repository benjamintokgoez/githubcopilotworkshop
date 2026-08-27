# MW-2026-118 - Daily service-cost export

| Field | Value |
|---|---|
| Raised | 2026-08-18, 17:40 CEST |
| Raised by | Regional service operations |
| Needed | Before 08:00 tomorrow |

Operations needs a deterministic file for yesterday's Berlin business date:

1. select the service-cost records in the local-day window;
2. create a sortable ISO-dated filename; and
3. format the exact total with currency for a German-language covering note.

Records are stored as aware UTC timestamps and dot-decimal strings. The ticket
author claims Berlin is always UTC+2 and suggests a fixed 22:00-to-22:00 UTC
window. Check that claim against the acceptance evidence.

A record on the end boundary belongs to the next business date. The filename
prefix is `service_export`. No scheduler, email, dashboard, CSV writer, or
personal technician data is in scope.

---

*Synthetic ticket and generated service-cost records.*
