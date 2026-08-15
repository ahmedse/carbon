# TASK-CARBON-PHASE1-ENTERPRISE-GAPS.md

## Phase 1 Enterprise Gaps — Implementation Plan

**Created:** 2026-08-09 | **Architect:** Master Architect  
**Status:** Spec written, awaiting delegation  
**Excludes:** Gap #3 (Encryption at rest) — deferred

---

## Gap Matrix

| # | Gap | Backend | Frontend | Ops | Est. Days |
|---|-----|---------|----------|-----|-----------|
| 1 | Password reset (frontend + email) | ✅ Done | 🔴 Missing | 🔴 Console only | 2 |
| 2 | Automated DB backups (scheduler) | ✅ Done | N/A | 🔴 No cron | 0.5 |
| 4 | Email infra (real backend) | ✅ Model ready | N/A | 🔴 Config only | 0.5 |
| 5 | Centralized log viewer | 🔴 Missing | 🔴 Missing | N/A | 3 |
| B1 | export-audits 500 error | 🔴 Bug | N/A | N/A | 0.25 |
| B2 | Table Manager not in sidebar | N/A | 🔴 Missing nav | N/A | 0.1 |

**Total: ~6.5 days** (3 gaps + 2 quick fixes)

---

## G1 — Password Reset Frontend + Email

### Prerequisites
- Backend endpoints already live & tested:
  - `POST /carbon-api/password-reset/` → sends email, fires in-app notification
  - `GET /carbon-api/password-reset/<uidb64>/<token>/` → renders reset form (HTML template)
  - `POST /carbon-api/password-reset/<uidb64>/<token>/` → sets new password
  - Templates exist: `password_reset_email.html`, `password_reset_subject.txt`, `password_reset_confirm.html`
- `EmailConfig` model supports 7 backends — currently on `console.EmailBackend` (emails go to stdout)

### Files to Create (3 new)

#### 1. `carbon-frontend/src/pages/ForgotPasswordPage.jsx` (~80 lines)
- Email input field
- Submits to `/carbon-api/password-reset/` via `apiFetch` (public, no auth header)
- On success: show "Check your email" message
- On error: show error alert (user not found, rate-limited, etc.)
- Link back to Login
- Set `useDocumentTitle("Forgot Password")`

#### 2. `carbon-frontend/src/pages/ResetPasswordPage.jsx` (~90 lines)
- Extract `uidb64` + `token` from URL params
- New password + confirm password fields
- Password policy hints (min 12 chars, uppercase, lowercase, number, special)
- Submit to `/carbon-api/password-reset/${uidb64}/${token}/` via fetch
- On success: redirect to `/login` with `?reset=1` param
- On error: show error alert (invalid/expired link)
- Set `useDocumentTitle("Reset Password")`

### Files to Modify (2 existing)

#### 3. `carbon-frontend/src/pages/Login.jsx`
**ADD** below the password TextField (after line ~60, inside the form Paper):
```jsx
<Typography variant="body2" sx={{ textAlign: 'right', mt: 0.5 }}>
  <Link to="/forgot-password" color="primary" underline="hover">
    Forgot Password?
  </Link>
</Typography>
```
Import `Link` from react-router-dom (already imported at top).

#### 4. `carbon-frontend/src/App.jsx`
**ADD** routes (BEFORE the `RequireAuth` block — password reset does NOT require auth):
```jsx
<Route path="/forgot-password" element={<ForgotPasswordPage />} />
<Route path="/reset-password/:uidb64/:token" element={<ResetPasswordPage />} />
```
Add lazily:
```jsx
const ForgotPasswordPage = React.lazy(() => import("./pages/ForgotPasswordPage"));
const ResetPasswordPage = React.lazy(() => import("./pages/ResetPasswordPage"));
```

### Ops: Switch Email Backend
See G4 below — configure a real SMTP backend so reset emails actually send. This is a prerequisite for testing G1 end-to-end.

### Acceptance Gates
- [ ] `npm run build` passes
- [ ] "Forgot Password?" link visible on Login page
- [ ] Clicking it navigates to /forgot-password
- [ ] Submitting email calls POST /carbon-api/password-reset/ → 302
- [ ] With real email backend: user receives reset link
- [ ] Clicking link → /reset-password/{uidb64}/{token} page loads
- [ ] Entering new password → password changed, redirected to login
- [ ] Login with new password works
- [ ] Password policy validations show errors (too short, missing uppercase, etc.)

---

## G2 — Automated DB Backup Scheduler

### Current State
- `BackupConfig` singleton model (frequency, retention_days, s3_bucket, s3_path) ✅
- `BackupRecord` model (audit trail per execution) ✅
- `manage.py run_backup` command (pg_dump → .sql.gz + optional S3 upload) ✅
- `pg_dump` (PostgreSQL 18.4) is available at `/usr/bin/pg_dump` ✅
- Admin change form has "Run Backup Now" button ✅
- **No scheduler to call `manage.py run_backup` automatically** ❌

### Implementation

#### Option A: Cron (simplest, ~5 min)
Add to crontab:
```
0 2 * * * cd /home/ahmed/aast/carbon && .venv/bin/python backend/manage.py run_backup >> /home/ahmed/aast/carbon/logs/cron-backup.log 2>&1
```
- Runs daily at 2 AM
- Logs output to `logs/cron-backup.log`
- Uses the project venv at `.venv` (Python 3.12.13)

#### Option B: Systemd timer (more robust, ~20 min)
Create two files:
- `/etc/systemd/system/carbon-backup.service` — runs `run_backup` as a oneshot
- `/etc/systemd/system/carbon-backup.timer` — triggers daily at 2 AM

**Recommendation: Option A (cron).** Simple, one line, zero new files. systemd timer is overkill for a single command.

### Acceptance Gates
- [ ] `crontab -l` shows the backup entry
- [ ] Manual test: `cd /home/ahmed/aast/carbon && .venv/bin/python backend/manage.py run_backup` succeeds
- [ ] Backup file created in `backups/` directory (`.sql.gz`)
- [ ] `BackupRecord` created with status=success
- [ ] Health endpoint `/carbon-api/health/` shows `last_backup_at` within last 24h
- [ ] Old backups auto-cleaned per `retention_days`

---

## G4 — Email Infrastructure (Real Backend)

### Current State
- `EmailConfig` singleton model: supports Brevo, SendGrid, Mailgun, SES, Resend, SMTP, Console ✅
- `email_config.py`: runtime override of Django settings from DB ✅
- `EmailConfig.load().as_django_settings()` returns complete config dict ✅
- `send_test_email()` diagnostic function exists ✅
- **Currently on `console.EmailBackend`** — all emails print to stdout ❌

### Implementation

**Step 1:** Choose a provider. Recommendation: **SendGrid** (free tier: 100 emails/day, no credit card for trial).

**Step 2:** Update `EmailConfig` in Django admin or via `manage.py shell`:

```python
from accounts.models import EmailConfig
cfg = EmailConfig.load()
cfg.backend = 'anymail.backends.sendgrid.EmailBackend'
cfg.host = 'smtp.sendgrid.net'
cfg.port = 587
cfg.username = 'apikey'
cfg.password = 'SG.YOUR_SENDGRID_API_KEY'  # masked in admin UI
cfg.from_email = 'noreply@carbon.clearturn.tech'
cfg.from_name = 'Carbon Data Trust'
cfg.use_tls = True
cfg.enabled = True
cfg.save()
```

**Step 3:** Test: `python manage.py send_test_email`

**Step 4:** Verify password reset flow delivers real email.

### Alternative: SMTP (no third-party needed)
If you have an existing SMTP server or Gmail with app password:
```python
cfg.backend = 'django.core.mail.backends.smtp.EmailBackend'
cfg.host = 'smtp.gmail.com'
cfg.port = 587
cfg.username = 'your@gmail.com'
cfg.password = 'app-password'
cfg.use_tls = True
cfg.save()
```

### Acceptance Gates
- [ ] `EmailConfig.enabled = True` with real backend
- [ ] `send_test_email(to='your@email.com')` delivers
- [ ] Password reset flow sends real email (G1 end-to-end)
- [ ] `Health endpoint` reports email status green

---

## G5 — Centralized Log Viewer

### Current State
- Structured JSON logs at `backend/logs/carbon.log` (rotated: carbon.log.1-5)
- Each line: `{asctime, levelname, name, message, pathname, lineno, correlation_id, method, path, status_code, duration_ms, user, remote_addr, ...}`
- No backend API to query logs ❌
- No frontend page to view/search ❌

### Design Decisions
- **No ELK/Loki/Grafana** — overkill for this stage. Use Django's ability to read log files.
- **Read-only** — never write to logs from the viewer.
- **Security** — AdminRoute-protected, reads file on disk (no forwarding).
- **Performance** — tail-read last N lines by default; search uses grep-style line matching. No full-text index needed at current log volume (~3000 lines).
- **Correlation ID** is the key UX feature: filter all lines for a request chain.

### Files to Create (4 new)

#### 1. `backend/config/log_viewer.py` (~60 lines)
Pure Python helper, no Django ORM:
```python
def read_logs(log_file: str, lines: int = 200, level: str = None, 
              search: str = None, correlation_id: str = None) -> dict:
    """Read last N lines from a JSON-lines log file with optional filters.
    Returns {lines: [...], total_matched: int, file_size_bytes: int, ...}"""
```
- Opens file in binary, seeks to near-end, reads backwards
- Parses each JSON line
- Filters by level (INFO/WARNING/ERROR/CRITICAL), search text, correlation_id
- Returns structured dict for API serialization

#### 2. `backend/config/log_api.py` (~40 lines)
```python
# APIView — only GET, AdminOrSuperuserOnly
class LogViewerAPIView(APIView):
    permission_classes = [IsAuthenticated, IsAdminUser]  # superuser or admins_group
    def get(self, request):
        # query params: lines (default 200), level, search, correlation_id, log_file (default 'carbon')
        # calls log_viewer.read_logs()
        # returns JSON response
```

#### 3. `backend/config/urls.py` — ADD 1 route
```python
from .log_api import LogViewerAPIView
# In urlpatterns:
path(f'{api_prefix}/system/logs/', LogViewerAPIView.as_view(), name='system-logs'),
```

#### 4. `carbon-frontend/src/pages/admin/LogViewerPage.jsx` (~250 lines)
- DataGrid or Table listing log entries
- Filters: Level (dropdown: ALL/INFO/WARNING/ERROR/CRITICAL), Search (text input), Correlation ID (text input)
- Columns: Timestamp, Level (color-coded chip), Message, Path, Status Code (color-coded), Duration (ms)
- Click row → expand details (full JSON, correlation ID copy button)
- "Copy correlation ID" button → clipboard
- Auto-refresh toggle (every 30s)
- Empty state: "No log entries match filters"
- `useDocumentTitle("System Logs")`

### Files to Modify (2 existing)

#### 5. `carbon-frontend/src/App.jsx`
**ADD** route:
```jsx
<Route path="/admin/logs" element={<AdminRoute><LogViewerPage /></AdminRoute>} />
```
**ADD** lazy import:
```jsx
const LogViewerPage = React.lazy(() => import("./pages/admin/LogViewerPage"));
```

#### 6. `carbon-frontend/src/shell/ShellSidebar.jsx`
**ADD** to admin case:
```jsx
{ label: 'System Logs', path: '/admin/logs', icon: ArticleIcon, role: 'admin' },
```
Import `ArticleIcon` from `@mui/icons-material/Article`.

### Acceptance Gates
- [ ] `GET /carbon-api/system/logs/` returns 401 without token
- [ ] `GET /carbon-api/system/logs/` returns 403 for data owner
- [ ] `GET /carbon-api/system/logs/` returns 200 with log entries for admin
- [ ] `GET /carbon-api/system/logs/?level=ERROR` returns only errors
- [ ] `GET /carbon-api/system/logs/?search=password` returns matching lines
- [ ] `GET /carbon-api/system/logs/?correlation_id=xxx` returns single request chain
- [ ] Frontend: LogViewerPage loads, shows entries, filters work
- [ ] Frontend: "Copy correlation ID" copies to clipboard
- [ ] Sidebar: "System Logs" appears under Platform Admin
- [ ] `npm run build` passes
- [ ] No new lint errors

---

## B1 — Fix export-audits 500 Error

### Root Cause
`ExportAuditViewSet.get_queryset()` at `emissions/views.py:1213`:
```python
qs = ExportAudit.objects.select_related('exported_by', 'period', 'org_unit')
```
But `ExportAudit` model has `period_id` + `org_unit_id` as `PositiveIntegerField`, NOT ForeignKeys. `select_related('period')` raises `FieldError` → 500.

Also `ExportAuditSerializer` line 368:
```python
period_name = serializers.CharField(source='period.name', read_only=True, allow_null=True)
```
Same problem — `period` is not a relation.

### Files to Modify (2)

#### 1. `backend/emissions/views.py`
Line 1213 — change:
```python
qs = ExportAudit.objects.select_related('exported_by', 'period', 'org_unit')
```
To:
```python
qs = ExportAudit.objects.select_related('exported_by')
```

#### 2. `backend/emissions/serializers.py`
Line 368 — remove `period_name` field:
```python
# DELETE this line:
period_name = serializers.CharField(source='period.name', read_only=True, allow_null=True)
```
(Or if resolution is needed: convert `period_id` → FK to `ReportingPeriod` with a migration. But the simpler fix is removing the broken field since `period_id` integer is already in `fields = '__all__'`.)

### Acceptance Gates
- [ ] `GET /carbon-api/carbon/export-audits/` returns 200 (was 500)
- [ ] `GET /carbon-api/carbon/export-audits/` returns valid JSON array (likely empty `[]`)
- [ ] `python manage.py check` passes (no new warnings)
- [ ] Existing tests still pass

---

## B2 — Table Manager Sidebar Entry

### Root Cause
`/schema-admin/table-manager` has a route (App.jsx:213) and the page builds (59.63KB chunk), but there's no sidebar nav entry to reach it.

### File to Modify (1)

#### 1. `carbon-frontend/src/shell/ShellSidebar.jsx`
**ADD** to admin case (after `{ label: 'Registered Apps', ... }`):
```jsx
{ type: 'divider' },
{ type: 'group', label: 'Schema Tools' },
{ label: 'Table Manager', path: '/schema-admin/table-manager', icon: TableChartIcon, role: 'admin' },
```
`TableChartIcon` is already imported (line 12).

### Acceptance Gates
- [ ] "Table Manager" appears in Platform Admin sidebar
- [ ] Clicking navigates to `/schema-admin/table-manager`
- [ ] Page loads (59.63KB chunk)
- [ ] `npm run build` passes

---

## Execution Order (Dependency Chain)

```
G4 (Email infra) ──┐
                   ├──> G1 (Password reset frontend)
                   │
G2 (Backup cron) ──┤
                   │
B1 (fix export-audits) ──┐
                         ├── independent, any order
B2 (Table Manager nav) ──┘
                         │
G5 (Log viewer) ─────────┘
```

- **Day 1**: G4 (email config) + B1 (export-audits fix) + B2 (sidebar fix) — quick wins
- **Day 2-3**: G1 (password reset frontend) — needs email working first
- **Day 4**: G2 (backup cron) — trivial, but test overnight
- **Day 5-7**: G5 (log viewer) — most complex, independent

---

## DO NOT TOUCH

- `backend/dq/executor.py` — current DQ work in progress (user has this file open)
- `backend/config/settings.py` — no structural changes, only EmailConfig DB updates
- `backend/carbon-frontend/src/auth/AuthContext.jsx` — complex auth, out of scope
- `backend/carbon-frontend/src/shell/Breadcrumbs.jsx` — unified breadcrumb, out of scope
- `backend/carbon-frontend/src/shell/Layout.jsx` — out of scope
- `backend/accounts/models.py` — EmailConfig model is complete, do not modify
- `backend/accounts/email_config.py` — complete, do not modify

## Architecture Rules

- G5 log viewer: backend API reads files — zero Django ORM imports in `log_viewer.py`. Keep it a pure Python module.
- All new frontend pages use `useDocumentTitle` hook (established pattern).
- All new frontend pages use `apiFetch` from `src/api/api.js` for API calls.
- All admin pages wrap in `AdminRoute` in App.jsx.
- Sidebar entries go through `ShellSidebar.jsx` case blocks.
- No new npm packages required.
- No new pip packages required (SendGrid/Anymail is already in requirements or installable).
