# Carbon Data Trust Platform — Enterprise Top-Tier Phased Plan

**Date:** 2026-08-09  
**Author:** Master Architect  
**Basis:** Industry benchmark vs Palantir Foundry, Ataccama ONE, Collibra, Immuta, Monte Carlo  
**Key Corrections from v1.0 Audit:** CBAC not RBAC, Pulse = AI Agent (WIP), no encryption-at-rest needed yet

---

## 0. Access Control Correction — CBAC, NOT RBAC

Carbon does **NOT** use RBAC. It uses **CBAC** — Capability-Based Access Control.

### What Carbon Has: CBAC

```
User → ScopedRole(group) → Capability Set → View Authorization
                                  ↓
                            IMPLIES (inheritance)
                                  ↓
                           Expanded FrozenSet
```

| Property | CBAC (Carbon) |
|---|---|
| **Authorization unit** | Named capability: `carbon:manage_emission_factors` |
| **Grouping** | Groups (`carbon_lead`, `auditors_group`, etc.) map to capability sets |
| **Inheritance** | `IMPLIES`: admin caps auto-grant view caps (transitive closure) |
| **Wildcard** | `"*"` = all capabilities for admin groups |
| **Resolution** | `get_user_capabilities(user)` → expanded `FrozenSet` cached per request |
| **Views** | Declare `required_capability` / `required_write_capability` |
| **Registry** | Single source of truth: `backend/accounts/capabilities.py` |
| **Frontend** | Mirrored in `src/capabilities.js`, API at `/capability-matrix/` |
| **Scoping** | `ScopedRole` binds user+group to specific OrgUnit+Module |

### What PBAC Is (Palantir's Model)

**Purpose-Based Access Control** — access is tied to a declared **business purpose**, not just a role or capability.

| PBAC Property | Description |
|---|---|
| **Purpose declaration** | User states *why* they need access: "Patient care for Ward 7" |
| **Policy evaluation** | System checks: is this purpose compatible with data use restrictions? |
| **Example** | A doctor can see ALL patient records when purpose = "emergency care", but only OWN patients when purpose = "routine checkup" |
| **GDPR alignment** | Maps directly to GDPR Art. 6 lawful bases for processing |
| **Carbon relevance** | Low for Phase 1/2 — overkill for a single-org carbon accounting platform |

### What ABAC Is (NIST Standard)

**Attribute-Based Access Control** — policies evaluate **attributes** of user, resource, action, and environment.

| ABAC Property | Description |
|---|---|
| **Attributes** | User: clearance=3, department=engineering. Resource: classification=confidential, owner=carbon-team. Environment: time=09:00-17:00, location=office-network |
| **Policy language** | XACML or similar: "Allow IF user.clearance >= resource.classification AND user.department == resource.department" |
| **Dynamic** | Policies re-evaluate on every request — attributes can change at runtime |
| **Carbon relevance** | Medium — we already have scoping (OrgUnit), adding time/location attributes would be ABAC-lite |

### CBAC vs PBAC vs ABAC — The Spectrum

```
RBAC ──── CBAC (Carbon) ──── ABAC ──── PBAC (Palantir)
Simpler ←──────────────────────────────────────→ More complex
Roles     Named capabilities    Attributes      Purpose-based
                                + policies      + policies
```

**Carbon's CBAC is already ahead of RBAC.** It's a solid foundation. ABAC would be a Phase 3 enhancement. PBAC is overkill unless Carbon becomes a multi-tenant SaaS with GDPR-regulated data sharing.

---

## 1. Design Principle: Admin-First Configuration

> **Every feature in this plan is configurable from the Carbon Platform Admin interface.**
> No hardcoded settings, no config files to edit on the server, no deployment needed to change behavior.

| Feature Area | Admin Model | Configurable |
|---|---|---|
| Email backend | `EmailConfig` | SMTP host, port, credentials, from address, templates |
| Password policy | `PasswordPolicy` | Min length, complexity, expiry days, lockout threshold |
| MFA settings | `MFAConfig` | Enable/disable, TOTP issuer name, remember-device days |
| Notification rules | `NotificationRule` | Event→Channel mapping, severity thresholds, digest schedule |
| Backup schedule | `BackupConfig` | Frequency, retention, S3 bucket, time of day |
| DQ profiling | `DQProfileConfig` | Auto-profile tables, freshness thresholds, anomaly sensitivity |
| Logging | `LogConfig` | Log level per logger, retention days, JSON/plain toggle |
| Rate limiting | `RateLimitConfig` | Anon rate, user rate, burst multiplier |
| Feature flags | `FeatureFlag` | Enable/disable any feature globally |
| API versioning | `APIConfig` | Active version, deprecation warnings, sunset dates |

### Admin Dashboard Philosophy

The Carbon Platform Admin index page becomes the **Platform Operations Console**:

```
┌─────────────────────────────────────────────────────────┐
│  CARBON PLATFORM ADMINISTRATION                          │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Users   │ │  Groups  │ │   Apps   │ │  Access  │  │
│  │   15     │ │   11     │ │   10     │ │  Active  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │
│  │  Email   │ │ Backups  │ │  Logs    │ │  Health  │  │
│  │  ✅ OK   │ │  ⚠ 12h  │ │  234/hr  │ │  🟢 All  │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │
│                                                          │
│  ┌──────────────────────────────────────────────────┐   │
│  │  Feature Flags                          [MANAGE]  │   │
│  │  ✅ Password Reset   ✅ MFA   ⬜ ABAC   ✅ API v2│   │
│  └──────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

---

## 2. Free Email Service Selection

| Service | Free Tier | Daily Limit | SMTP | API | DKIM |
|---|---|---|---|---|---|
| **SendGrid** | 100 emails/day | Forever | ✅ | ✅ | ✅ |
| **Mailgun** | 100 emails/day | First 3 months | ✅ | ✅ | ✅ |
| **Brevo (Sendinblue)** | 300 emails/day | Forever | ✅ | ✅ | ✅ |
| **Resend** | 100 emails/day | Forever | ❌ API only | ✅ | ✅ |
| **Amazon SES** | 62,000/month | Forever | ✅ | ✅ | ✅ |

**Recommendation: Brevo (Sendinblue)** — 300/day free forever, SMTP support, simple setup. Fallback: SendGrid.

Integration via `django-anymail` — single package, switch backends with one config change.

---

## 3. Detailed Phased Plan

---

# PHASE 1 — Production Trust (2 Weeks)

## Week 1: Foundation

### 1.1 Password Reset & Recovery · 2 days · `backend-worker`

**Admin-configurable via:** `PasswordPolicy` model

| Task | Details |
|---|---|
| 1.1a | Install `django-anymail` + Brevo/SendGrid backend |
| 1.1b | Create `EmailConfig` model: host, port, username, password, from_email, use_tls |
| 1.1c | Register `EmailConfig` as singleton in admin (only one config row) |
| 1.1d | Wire Django's built-in `PasswordResetView` with email template |
| 1.1e | Create HTML email templates: reset, welcome, notification digest |
| 1.1f | Add `email/test/` endpoint so host can verify email config works |
| 1.1g | Create `PasswordPolicy` model: min_length, require_special, max_age_days, lockout_after_n |
| 1.1h | Add `django-axes` for brute-force account lockout tied to PasswordPolicy |
| 1.1i | Tests: reset flow end-to-end, lockout after N failures, email sent confirmation |

**Deliverable:** User clicks "Forgot Password" → gets email → sets new password → locked out after N failures.

---

### 1.2 Automated DB Backups · 1 day · `devops-worker`

**Admin-configurable via:** `BackupConfig` model

| Task | Details |
|---|---|
| 1.2a | Create `BackupConfig` model: frequency_cron, retention_days, s3_bucket, s3_path, enabled |
| 1.2b | Create `backup_db.sh` script: `pg_dump` → compress → timestamp → optional S3 upload |
| 1.2c | Create Django management command `manage.py run_backup` wrapping the script |
| 1.2d | Register in admin with "Run Backup Now" action button |
| 1.2e | Add cron job on VPS: `0 2 * * * /srv/carbon/backend/manage.py run_backup` |
| 1.2f | Add `BackupRecord` model: timestamp, size_bytes, status, location → admin list view |
| 1.2g | Add restore instructions in admin help text |
| 1.2h | Test: backup runs, file created, restore verified |

**Deliverable:** Daily automated backups, configurable retention, admin-triggerable manual backup, test restore documented.

---

### 1.3 Centralized Log Viewer · 2 days · `backend-worker`

**Admin-configurable via:** `LogConfig` model

| Task | Details |
|---|---|
| 1.3a | Create `LogConfig` model: default_level (DEBUG/INFO/WARN/ERROR), retention_days, json_format |
| 1.3b | Enhance `RequestLoggingMiddleware` to write to DB for ERROR-level only (avoid fill-up) |
| 1.3c | Create `RequestLog` model: correlation_id, method, path, user, status_code, duration_ms, timestamp |
| 1.3d | Register `RequestLog` in admin: list_display, search on correlation_id/path/user, date_hierarchy |
| 1.3e | Add admin filter sidebar: by level, by status_code, by user, by slow_request (>5s) |
| 1.3f | Add "Purge logs older than X days" admin action (respects retention_days) |
| 1.3g | Add file-log tail viewer: read last N lines from `logs/carbon.log` in admin view |
| 1.3h | Tests: log entry created, admin filters work, purge action verified |

**Deliverable:** Admin panel shows all request logs with filter/search, configurable log levels, auto-purge old entries.

---

### 1.4 API Pagination (DRF Default) · 0.5 day · `backend-worker`

**Admin-configurable via:** `APIConfig` model

| Task | Details |
|---|---|
| 1.4a | Add `DEFAULT_PAGINATION_CLASS = PageNumberPagination` to DRF settings |
| 1.4b | Set `PAGE_SIZE = 50` (configurable via `APIConfig` model) |
| 1.4c | Add `page_size_query_param = 'page_size'` and `max_page_size = 200` |
| 1.4d | Audit all viewsets: any that override pagination → remove override unless justified |
| 1.4e | Add `X-Total-Count` header in response (via custom pagination) |
| 1.4f | Tests: verify pagination on 5 key endpoints |

**Deliverable:** All list endpoints paginated. No accidental 2,000-row responses.

---

### 1.5 Environment Separation · 0.5 day · `devops-worker`

**Admin-configurable via:** `DJANGO_ENV` environment variable (set at deploy, visible in admin header)

| Task | Details |
|---|---|
| 1.5a | Formalize 3 environments: `development` (WSL), `staging` (VPS:8009), `production` (VPS:8006) |
| 1.5b | Add env badge in admin header: red "STAGING" / green "PRODUCTION" / yellow "DEV" |
| 1.5c | Gate dangerous admin actions (flush logs, run backups, delete users) on `DJANGO_ENV != 'production'` |
| 1.5d | Add `settings.STAGING` and `settings.PRODUCTION` boolean flags |

**Deliverable:** Clear env indication everywhere. Dangerous actions blocked in production.

---

## Week 2: Observability & Notifications

### 1.6 In-App Notification Center · 2 days · `frontend-worker` + `backend-worker`

**Admin-configurable via:** `NotificationRule` + `NotificationChannel` models

| Task | Details |
|---|---|
| 1.6a | Create `Notification` model: user (FK), title, body, category, is_read, link, created_at |
| 1.6b | Create `NotificationChannel` model: user (FK), channel_type (in_app/email/both), enabled |
| 1.6c | Create `NotificationRule` model: event_type, min_severity, channel, group_target, enabled |
| 1.6d | API: `GET /api/notifications/` (paginated, unread count), `POST .../mark-read/` |
| 1.6e | Frontend: Bell icon in navbar with unread badge, dropdown with recent list |
| 1.6f | Frontend: `/notifications/` full page with filters (category, read/unread), mark-all-read |
| 1.6g | Wire DQ violations → `dq_violation` event → NotificationRule → notification created |
| 1.6h | Wire password reset request → notification to user |
| 1.6i | Tests: notification CRUD, DQ violation trigger, bell badge count |

**Deliverable:** Bell icon with unread count, notification center page, DQ violations generate notifications.

---

### 1.7 Data Profiling Engine · 2 days · `backend-worker`

**Admin-configurable via:** `DQProfileConfig` model

| Task | Details |
|---|---|
| 1.7a | Create `DQProfileConfig` model: auto_profile_enabled, freshness_threshold_hours, volume_anomaly_pct, sample_size |
| 1.7b | Create `TableProfile` model: table (FK), row_count, null_counts (JSON), distinct_counts (JSON), min/max/mean (JSON), profiled_at |
| 1.7c | Create management command `manage.py profile_all` — scans all DataTables, computes stats |
| 1.7d | Register in admin with "Profile All Tables" action |
| 1.7e | API: `POST /api/dq/profile/{table_id}/` — profile single table on demand |
| 1.7f | API: `GET /api/dq/profile/{table_id}/` — return latest profile results |
| 1.7g | Frontend: DQ Dashboard → "Data Profiles" tab showing column distributions as mini bar charts |
| 1.7h | Tests: profile accuracy, null detection, field-level stats verified |

**Deliverable:** Click "Profile" on any table → see column distributions, null %, distinct count, min/max.

---

### 1.8 Freshness & Schema Monitoring · 1 day · `backend-worker`

**Admin-configurable via:** `DQProfileConfig` model

| Task | Details |
|---|---|
| 1.8a | Create `FreshnessCheck` model: table (FK), expected_max_age_hours, last_data_timestamp, is_fresh, checked_at |
| 1.8b | Create management command `manage.py check_freshness` — compares `updated_at` vs threshold |
| 1.8c | Create `SchemaSnapshot` model: table (FK), column_schema (JSON), snapshot_at |
| 1.8d | Create `SchemaChange` model: table (FK), change_type (added/dropped/modified), field, old_def, new_def |
| 1.8e | Schedule: `check_freshness` runs hourly, `schema_snapshot` runs daily |
| 1.8f | Stale data → notification (if rule configured) |
| 1.8g | Schema change → notification to dq_lead group |

**Deliverable:** Automatic detection of stale tables and schema drift with notifications.

---

### 1.9 Health Dashboard · 0.5 day · `backend-worker`

**Admin-configurable via:** (read-only status page, no config needed)

| Task | Details |
|---|---|
| 1.9a | Enhance `/carbon-api/health/` to return: DB status, Redis status (if configured), disk_free_pct, last_backup_at, recent_error_count |
| 1.9b | Add admin dashboard widget showing health status lights (green/yellow/red) |
| 1.9c | Add `/carbon-api/health/metrics/` — Prometheus text format endpoint (using `django-prometheus`) |

**Deliverable:** Health endpoint returns comprehensive status. Admin sees health lights.

---

## PHASE 1 DELIVERABLES SUMMARY

| # | Feature | Days | Configurable Via |
|---|---|---|---|
| 1.1 | Password Reset + Email | 2 | `EmailConfig`, `PasswordPolicy` |
| 1.2 | DB Backups | 1 | `BackupConfig` |
| 1.3 | Log Viewer | 2 | `LogConfig` |
| 1.4 | API Pagination | 0.5 | `APIConfig` |
| 1.5 | Environment Separation | 0.5 | `DJANGO_ENV` |
| 1.6 | Notification Center | 2 | `NotificationRule`, `NotificationChannel` |
| 1.7 | Data Profiling | 2 | `DQProfileConfig` |
| 1.8 | Freshness/Schema Monitoring | 1 | `DQProfileConfig` |
| 1.9 | Health Dashboard | 0.5 | Read-only |
| | **PHASE 1 TOTAL** | **11.5 days** | |

**Phase 1 Gate:** All 9 features demoable from admin panel, all tests passing, deployed to staging.

---

# PHASE 2 — Enterprise Differentiators (4-6 Weeks)

## Week 3-4: Security & Access

### 2.1 Multi-Factor Authentication · 2 days · `backend-worker`

**Admin-configurable via:** `MFAConfig` model

| Task | Details |
|---|---|
| 2.1a | Install `django-otp` + `qrcode` |
| 2.1b | Create `MFAConfig` model: enabled, issuer_name, remember_device_days, required_for_groups (M2M) |
| 2.1c | Add `TOTPDevice` to User admin inline |
| 2.1d | API: `POST /api/auth/setup-mfa/` → returns QR code + secret |
| 2.1e | API: `POST /api/auth/verify-mfa/` → validates TOTP token, returns JWT |
| 2.1f | Login flow: password → if MFA required → prompt for TOTP → JWT |
| 2.1g | "Remember this device for 30 days" cookie |
| 2.1h | Admin can reset MFA for any user |

**Deliverable:** Login requires TOTP code. QR setup via Google Authenticator. Device remember.

---

### 2.2 SSO / OIDC · 3 days · `backend-worker`

**Admin-configurable via:** `SSOConfig` model

| Task | Details |
|---|---|
| 2.2a | Install `mozilla-django-oidc` |
| 2.2b | Create `SSOConfig` model: enabled, provider (OIDC/SAML), issuer_url, client_id, client_secret, scope, auto_create_users |
| 2.2c | Add "Login with SSO" button on login page |
| 2.2d | Auto-map OIDC claims → User fields (email, first_name, last_name) |
| 2.2e | Auto-assign to default group on first SSO login |
| 2.2f | Test with Google Workspace OIDC (free for testing) |

**Deliverable:** "Login with Google/Microsoft" button. Users auto-provisioned on first SSO login.

---

### 2.3 CBAC Enhancements — ABAC-Lite · 3 days · `backend-worker`

**Admin-configurable via:** `AccessPolicy` model (new)

| Task | Details |
|---|---|
| 2.3a | Create `AccessPolicy` model: name, conditions_json, priority, enabled |
| 2.3b | Conditions support: `time_range`, `ip_range`, `user.attributes`, `resource.tags` |
| 2.3c | Policy engine: evaluate all enabled policies on each request, deny if any fail |
| 2.3d | Add `user.attributes` JSONField to User model (extensible per-user attrs) |
| 2.3e | Add `resource.tags` — leverage existing catalog metadata |
| 2.3f | Admin: policy test tool — "would user X be allowed to access endpoint Y at time Z?" |

**Deliverable:** Admin can create policies like "Deny access outside 08:00-20:00" or "Deny from non-office IPs".

---

## Week 5-6: Data Protection & Governance

### 2.4 Column-Level Data Masking · 2 days · `backend-worker`

**Admin-configurable via:** `MaskingRule` model

| Task | Details |
|---|---|
| 2.4a | Create `MaskingRule` model: field (FK), mask_type (hash/nullify/partial/last4/k_anonymize), groups_exempt (M2M) |
| 2.4b | Add `DataMaskingMiddleware` — intercepts API responses, applies masking rules |
| 2.4c | Mask types: `hash` → SHA256, `nullify` → None, `partial` → `Ah***`, `last4` → `****1234` |
| 2.4d | Groups in `groups_exempt` see unmasked data |
| 2.4e | Admin preview: "see as user X" test tool |
| 2.4f | Tests: masked in response, unmasked for exempt group, masks survive pagination |

**Deliverable:** Tag `email` field → auditors see `a***@d***.com`, data owner sees real email.

---

### 2.5 PII Detection & Classification · 2 days · `backend-worker`

**Admin-configurable via:** `PIIScannerConfig` model

| Task | Details |
|---|---|
| 2.5a | Create `PIIScannerConfig`: regex_patterns (JSON), ml_model_enabled, scan_on_ingest |
| 2.5b | Create `DataClassification` model: field (FK), pii_type (email/phone/ssn/credit_card/name/address), confidence, classified_at |
| 2.5c | Scanner: regex patterns for common PII types + column name heuristics |
| 2.5d | Admin "Scan All Fields" action |
| 2.5e | Results in admin with color-coded severity badges |
| 2.5f | Auto-suggest masking rules for detected PII |

**Deliverable:** Click "Scan" → fields tagged with PII type → one-click create masking rule.

---

### 2.6 Data Stewardship & Approval Workflows · 3 days · `backend-worker`

**Admin-configurable via:** `ApprovalWorkflow` model

| Task | Details |
|---|---|
| 2.6a | Create `ApprovalWorkflow` model: name, entity_type, steps (JSON ordered list of groups/roles), enabled |
| 2.6b | Create `ApprovalRequest` model: workflow (FK), entity_id, requester, status (pending/approved/rejected), current_step, comments |
| 2.6c | API: `POST /api/approvals/request/` — create request |
| 2.6d | API: `POST /api/approvals/{id}/approve/` + `.../reject/` |
| 2.6e | Notification on new request, approval, rejection |
| 2.6f | Admin: approval queue with approve/reject buttons |
| 2.6g | Wire to DQ rule changes (require approval to modify production DQ rules) |
| 2.6h | Wire to emission factor changes (require approval to modify factors) |

**Deliverable:** DQ rule change → approval request → dq_lead reviews → approve/reject → notification.

---

### 2.7 Webhook Registry · 1.5 days · `backend-worker`

**Admin-configurable via:** `WebhookSubscription` model

| Task | Details |
|---|---|
| 2.7a | Create `WebhookSubscription` model: url, secret, events (M2M), is_active, last_sent_at, failure_count |
| 2.7b | Create `WebhookDelivery` model: subscription (FK), event, payload, response_code, sent_at |
| 2.7c | HMAC-SHA256 signature on each delivery |
| 2.7d | Auto-disable after 10 consecutive failures |
| 2.7e | Admin: test webhook button, delivery log viewer |
| 2.7f | Events: `dq.violation`, `backup.completed`, `backup.failed`, `user.password_reset`, `approval.requested` |

**Deliverable:** Register Slack/Discord webhook → DQ violations ping channel automatically.

---

## PHASE 2 DELIVERABLES SUMMARY

| # | Feature | Days | Configurable Via |
|---|---|---|---|
| 2.1 | MFA (TOTP) | 2 | `MFAConfig` |
| 2.2 | SSO / OIDC | 3 | `SSOConfig` |
| 2.3 | ABAC-Lite Policies | 3 | `AccessPolicy` |
| 2.4 | Column Data Masking | 2 | `MaskingRule` |
| 2.5 | PII Detection | 2 | `PIIScannerConfig` |
| 2.6 | Approval Workflows | 3 | `ApprovalWorkflow` |
| 2.7 | Webhook Registry | 1.5 | `WebhookSubscription` |
| | **PHASE 2 TOTAL** | **16.5 days** | |

---

# PHASE 3 — World-Class (6-8 Weeks)

### 3.1 Column-Level Data Lineage · 5 days · `backend-worker`

**Admin-configurable via:** `LineageConfig` model

| Task | Details |
|---|---|
| 3.1a | Create `ColumnLineage` model: source_table, source_column, target_table, target_column, transformation, confidence |
| 3.1b | Auto-detect: match source columns → calculation fields via emission factor mappings |
| 3.1c | Manual: admin can add/edit lineage edges |
| 3.1d | API: `GET /api/lineage/column/{table_id}/{column}/` — upstream/downstream graph |
| 3.1e | Frontend: D3/ReactFlow interactive lineage graph (Table → Column → Calculation → Report) |
| 3.1f | Impact analysis: "Changing X affects Y calculations, Z reports" |

---

### 3.2 Visual Lineage Graph · 3 days · `frontend-worker`

| Task | Details |
|---|---|
| 3.2a | Install `reactflow` |
| 3.2b | Nodes: Table → Column → EmissionFactor → Calculation → Report |
| 3.2c | Edge labels: "maps to", "used in", "generates" |
| 3.2d | Click node → slide-out detail panel |
| 3.2e | Search: highlight path from X to Y |

---

### 3.3 Data Marketplace / Self-Service · 3 days · `backend-worker` + `frontend-worker`

**Admin-configurable via:** `MarketplaceConfig` model

| Task | Details |
|---|---|
| 3.3a | Create `DataProduct` model: name, description, tables (M2M), owner, terms_of_use, approval_required |
| 3.3b | Frontend: Catalog page → "Request Access" button → approval workflow |
| 3.3c | Auto-provision: approved → CBAC capability granted |
| 3.3d | Usage stats: who accessed what, when |

---

### 3.4 Automated Anomaly Detection (ML) · 4 days · `data-ml-worker`

**Admin-configurable via:** `AnomalyConfig` model

| Task | Details |
|---|---|
| 3.4a | Time-series anomaly detection: rolling Z-score on row counts, null %, value distributions |
| 3.4b | Train on 30-day baseline, detect >3σ deviations |
| 3.4c | Daily anomaly report in admin |
| 3.4d | Notification on anomaly detection |

---

### 3.5 OpenAPI SDK Generation · 2 days · `devops-worker`

| Task | Details |
|---|---|
| 3.5a | Generate OpenAPI 3.0 spec from drf-yasg |
| 3.5b | Use `openapi-generator` to create Python + TypeScript SDKs |
| 3.5c | Publish Python SDK to PyPI, TypeScript SDK to npm |
| 3.5d | Auto-regenerate in CI on tag push |

---

### 3.6 Blue/Green Deployments · 2 days · `devops-worker`

| Task | Details |
|---|---|
| 3.6a | Docker Compose with `blue` + `green` service groups |
| 3.6b | Nginx switch: update upstream, reload (zero downtime) |
| 3.6c | Health check on green before switching |
| 3.6d | Rollback: switch back to blue |

---

### 3.7 Point-in-Time Recovery (WAL) · 2 days · `devops-worker`

| Task | Details |
|---|---|
| 3.7a | Configure PostgreSQL WAL archiving |
| 3.7b | `wal-g` push to S3 |
| 3.7c | PITR restore script: `restore_to_point.sh 2026-08-09T14:30:00` |
| 3.7d | Admin: "Restore to point in time" with datetime picker (gated on env != production) |

---

### 3.8 Semantic Search · 3 days · `backend-worker` + `data-ml-worker`

| Task | Details |
|---|---|
| 3.8a | Embed table metadata, field names, descriptions using sentence-transformer |
| 3.8b | Store in ChromaDB (already in requirements) |
| 3.8c | API: `GET /api/search/?q=electricity consumption 2025` |
| 3.8d | Frontend: search bar in catalog page |

---

## PHASE 3 DELIVERABLES SUMMARY

| # | Feature | Days |
|---|---|---|
| 3.1 | Column-Level Lineage | 5 |
| 3.2 | Visual Lineage Graph | 3 |
| 3.3 | Data Marketplace | 3 |
| 3.4 | Anomaly Detection (ML) | 4 |
| 3.5 | SDK Generation | 2 |
| 3.6 | Blue/Green Deployments | 2 |
| 3.7 | Point-in-Time Recovery | 2 |
| 3.8 | Semantic Search | 3 |
| | **PHASE 3 TOTAL** | **24 days** |

---

## 4. Overall Roadmap

```
Week 1-2    Week 3-6        Week 7-14
────────    ────────        ─────────
PHASE 1     PHASE 2         PHASE 3
11.5 days   16.5 days       24 days

🔴 Critical  🟡 Enterprise   🟢 World-Class
───────────  ─────────────   ─────────────
Password     MFA/TOTP        Column Lineage
Backups      SSO/OIDC        Visual Graph
Log Viewer   ABAC-Lite       Marketplace
Pagination   Data Masking    ML Anomalies
Env Sep      PII Detection   SDK Gen
Notifications Approval Flow  Blue/Green
Profiling    Webhooks        PITR
Freshness                    Semantic Search
Health
```

## 5. What's NOT Included (Intentionally Skipped)

| Feature | Why Skipped |
|---|---|
| **Encryption at rest** | User says not needed now. PostgreSQL runs on VPS with disk encryption. |
| **AI Agent / Pulse** | Work in progress — Pulse is Carbon's AI agent. Leave for Pulse team. |
| **PBAC (Purpose-Based)** | Overkill for single-org platform. Revisit if Carbon becomes multi-tenant SaaS. |
| **Multi-Region Replication** | Premature for current scale. Revisit at 1,000+ users. |
| **HashiCorp Vault Integration** | Secrets via `.env` + GitHub Secrets is sufficient for now. |
| **Kubernetes / Helm** | Docker Compose is sufficient for single-VPS. |

## 6. Immediate Next Steps

1. **Today:** Start Phase 1.1 (Password Reset + Email) — foundation for everything else
2. **Week 1:** Complete 1.1–1.5 (Foundation pillar)
3. **Week 2:** Complete 1.6–1.9 (Observability pillar)
4. **End of Week 2:** Phase 1 gate review — tag `v1.2.0` with all 9 features
5. **Then:** Decide go/no-go on Phase 2 based on AASTMT feedback
