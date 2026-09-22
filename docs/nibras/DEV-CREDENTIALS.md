# Nibras forever-dev credentials (locked 2026-09-21)

| Role | User | Password |
|------|------|----------|
| Superuser | `ahmed` | `AdminPa_132` |
| Brand admin | `admin` | `AdmNibras_132` |
| Any employee | `emp_*` (e.g. `emp_1067`) | `mozafNibrasPa_132` |

Pinned in:
- `.cursor/rules/nibras-dev-credentials.mdc`
- `backend/.env` + `.env.example`
- `ensure_nibras_admins` / `get_default_password()` (nibras DEBUG fallback)
- All `emp_*` hashes on `nibras_dev` reset (550 users) — token smoke 200
