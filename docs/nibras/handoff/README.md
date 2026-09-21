# Nibras customer handoff pack (v0.1)

Generated: 2026-09-20

## Files

| File | Format | Audience |
|------|--------|----------|
| `Nibras-My-Employee-User-Guide-v0.1.docx` | Word | Employees |
| `Nibras-People-HR-Admin-Guide-v0.1.docx` | Word | HR / People admins |
| `Nibras-Team-Manager-Guide-v0.1.docx` | Word | Managers |
| `Nibras-UAT-QA-Checklist-v0.1.xlsx` | Excel | Customer QA + delivery lead |

## How to hand over

1. Confirm the **release tag / build** matches production; put it on the Excel Environment sheet.
2. Send the **three Word guides** for training (and optional PDF export from Word).
3. Run **UAT** with the Excel workbook on the customer tenant; collect Sign-off sheet.
4. Keep internal ops runbook (`../GOFSCO-ONBOARDING-RUNBOOK.md`) — do not send raw unless the customer ops team needs it.

## Regenerate

```bash
/home/ahmed/ws/carbon/.venv/bin/python /home/ahmed/ws/carbon/docs/nibras/handoff/generate_handoff_pack.py
```
