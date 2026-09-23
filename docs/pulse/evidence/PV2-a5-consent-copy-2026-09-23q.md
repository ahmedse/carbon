# PV2 A5 — consent copy on the 23q plans

Read from `nibras_dev` after verify 23q. No new host write. The write step is the consent step. `draft_text` is the `step_templates` render, stored before confirm.

Utterances were English, so the copy is the `en` template.

| Plan | Write-step intent | Draft before confirm |
|---|---|---|
| leave `69a4436b…` | Submit leave request (annual) on 2027-08-31 · 1 day(s) | Leave request submitted: annual, 2027-08-31 → 2027-08-31 (1 days). Awaiting manager review in Team. |
| loan `378e4451…` | Submit loan request (personal) · 551.0 · 12 mo from 2027-09-14 | Loan request submitted: personal, 551 over 12 months, start 2027-09-14. Awaiting manager then finance review in Team. |
| attendance `261cdd1a…` | Submit attendance permission (official) on 2027-09-21 · 2.0h | Attendance permission submitted: official on 2027-09-21 (2 hours). Awaiting manager review in Team. |

Each write step names the action and the bound values. Arabic twins use the same slots (`test_every_step_template_has_matching_en_ar_slots`). This run did not pause an Arabic consent.

Review note: leave said “1 days”. Template `en` is now “{days} day(s)”. The stored row was not rewritten.
