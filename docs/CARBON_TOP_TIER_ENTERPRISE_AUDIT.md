# Carbon Data Trust Platform — Enterprise Top-Tier Feature Audit

> **⚠️ SUPERSEDED by [`CARBON_ENTERPRISE_PHASED_PLAN.md`](./CARBON_ENTERPRISE_PHASED_PLAN.md) — 2026-08-09**
> This document has the original benchmark research. The phased plan incorporates corrections:
> - **CBAC** (not RBAC) — Carbon uses Capability-Based Access Control
> - **No encryption-at-rest** for now
> - **Pulse = AI Agent** (work in progress — out of scope)
> - **Free email via Brevo/SendGrid**
> - **Everything admin-configurable**

**Date:** 2026-08-08  
**Author:** Master Architect  
**Basis:** Industry benchmark vs Palantir Foundry, Ataccama ONE, Collibra, Immuta, Monte Carlo, DataRobot, Datadog  
**Existing v1.0 Assessment:** 85/100 — Strong Foundation, Clear Upgrade Path  
**Goal:** Identify ALL features required for a world-class data trust platform + domain app

---

## Executive Summary

Carbon v1.1.0 has a **solid foundation** (JWT auth, **CBAC** — Capability-Based Access Control with 34 named capabilities across 7 groups, DQ engine with 7 rule types, governance audit trail with 316 events, MDM with 10 reference sets, 1,993 carbon calculations, 982 passing tests). But to compete with Palantir/Ataccama/Collibra, it needs significant investment across 8 enterprise pillars.

### Scorecard After This Audit

| Pillar | Current Score | Target | Gap |
|--------|:---:|:---:|:---:|
| Auth & Identity | 70/100 | 95 | MFA, SSO, password reset/recovery |
| Data Protection | 55/100 | 95 | Encryption at rest, column masking, DLP |
| DQ & Observability | 60/100 | 90 | Column lineage, anomaly detection, freshness |
| Governance & Compliance | 65/100 | 95 | GDPR tooling, consent mgmt, retention policies |
| Operations & DR | 25/100 | 90 | Backups, HA, monitoring, alerting |
| Notifications | 5/100 | 85 | Email, in-app, webhooks, digest |
| Performance & Scale | 45/100 | 85 | Connection pooling, query optimization, CDN |
| Developer Experience | 50/100 | 85 | API versioning, SDK, docs portal, sandbox |
| **Overall** | **~47/100** | **90+** | |

---

## 1. Industry Benchmark — What The Leaders Have

### 1.1 Palantir Foundry — The Ontology Operating System

| Capability | Description | Carbon Status |
|---|---|---|
| **Ontology** | Semantic layer mapping all data objects, actions, processes into a unified model | ❌ No semantic ontology |
| **Pipeline Builder** | Visual ETL with 200+ connectors, streaming & batch | ❌ No pipelines |
| **Digital Twin** | Real-time operational mirror of physical assets | ❌ N/A |
| **Purpose-Based Access Control (PBAC)** | Access tied to business purpose, not just roles | ❌ Only CBAC today (CBAC > RBAC; PBAC overkill for single-org) |
| **Real-Time Alerting** | Rules engine triggering on streaming data | ❌ No streaming/alerting |
| **Process Mining** | Discover, analyze, optimize business processes | ❌ N/A |
| **Marketplace** | Reusable data products, models, apps across org | ❌ No marketplace |
| **Apollo** | Continuous delivery across air-gapped/classified environments | ❌ Single VPS deploy |
| **Edge AI** | Deploy models to edge devices | ❌ N/A |
| **Secure Collaboration** | Multi-party data sharing with granular controls | ❌ No sharing |

### 1.2 Ataccama ONE — The Agentic Data Trust Platform

| Capability | Description | Carbon Status |
|---|---|---|
| **Data Quality** | Profile, monitor, cleanse, standardize — write rules once, apply anywhere | ⚠️ 7 rule types, no profiling |
| **Data Catalog** | Find, understand, govern across structured & unstructured | ⚠️ Basic catalog |
| **Data Observability** | Detect pipeline anomalies early, resolve before impact | ❌ None |
| **Data Lineage** | Column-level trace from source to consumption | ❌ Entity-level only |
| **Reference Data Management** | Standardize codes, audit-ready by default | ✅ Solid |
| **Master Data Management** | AI-powered matching, golden record, provisioning | ❌ No MDM |
| **AI Agent** | Autonomous rule generation, anomaly detection, issue resolution | ❌ No AI agent |
| **MCP Server** | Model Context Protocol for AI ecosystem integration | ❌ None |

### 1.3 Collibra — The Data Intelligence Platform

| Capability | Description | Carbon Status |
|---|---|---|
| **Data Catalog** | Semantic graph bridging raw data & business meaning | ⚠️ Basic |
| **Data Privacy** | Automated PII detection, classification, masking | ❌ None |
| **Data Lineage** | End-to-end technical + business lineage | ❌ Entity-only |
| **Data Marketplace** | Self-service data product discovery & access requests | ❌ None |
| **Data Governance** | Policy management, stewardship, workflows | ⚠️ Partial |
| **Data Quality & Observability** | Continuous monitoring with 100+ native integrations | ❌ No observability |
| **Collibra Everywhere** | Browser extension surfacing context in Salesforce, Tableau, Slack | ❌ None |
| **Flexible Operating Model** | Federated governance tailored to org structure | ❌ Central only |

### 1.4 Monte Carlo — Data Observability

| Capability | Description | Carbon Status |
|---|---|---|
| **Freshness Monitoring** | Detect stale/outdated data automatically | ❌ None |
| **Volume Monitoring** | Anomaly detection on row counts/ingestion volume | ❌ None |
| **Schema Monitoring** | Alert on schema changes (new/dropped columns, type changes) | ❌ None |
| **Lineage-Based Monitoring** | Incident impact analysis via column lineage | ❌ None |
| **DQ Monitors** | Custom SQL rules with threshold-based alerting | ⚠️ Rules exist, no alerting |

### 1.5 Immuta — Data Security & Access Control

| Capability | Description | Carbon Status |
|---|---|---|
| **Attribute-Based Access Control (ABAC)** | Dynamic policy enforcement based on user/ data/resource/environment attributes | ❌ RBAC only |
| **Dynamic Data Masking** | Column-level masking (hash, nullify, k-anonymize, differential privacy) | ❌ None |
| **Purpose-Based Restrictions** | Limit access based on declared purpose (GDPR Art. 6) | ❌ None |
| **Data Minimization** | Automatically enforce least-privilege at query time | ❌ None |
| **Audit of ALL Data Access** | Full query-level audit trail | ⚠️ API-level only |

---

## 2. Enterprise Pillar Gap Analysis

### 2.1 🔐 Authentication & Identity Management

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| JWT Authentication | P0 | ✅ Done | Standard |
| Token blacklisting | P0 | ✅ Done | Standard |
| Rate limiting (anon + user) | P0 | ✅ Done | Standard |
| RBAC (7 personas) | P0 | ✅ Done | Standard |
| **Password Reset / Recovery** | **P0** | ❌ Missing | **Mandatory** |
| **Multi-Factor Authentication (MFA/TOTP)** | **P0** | ❌ Missing | **Mandatory** |
| **SSO / OIDC / SAML** | **P1** | ❌ Missing | Enterprise standard |
| **Session Management** | **P1** | ❌ No session listing/revocation | Standard |
| **Login History / Anomaly Detection** | **P2** | ❌ Missing | Advanced |
| **Brute-Force Protection** | P1 | ⚠️ Login throttle only | Needs account lockout |
| **Email Verification** | P1 | ❌ Missing | Standard |

**Action Items:**
- Implement `django-allauth` or custom password reset flow with email tokens
- Add `django-otp` / TOTP-based MFA
- Add `mozilla-django-oidc` or `social-auth-app-django` for SSO
- Add `django-axes` for brute-force + account lockout

### 2.2 🛡️ Data Protection & Privacy

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| TLS in Transit (HTTPS) | P0 | ✅ Via nginx | Standard |
| **Encryption at Rest (database)** | **P0** | ❌ Not implemented | **Mandatory** |
| **Column-Level Encryption** | **P1** | ❌ Missing | PII protection |
| **Data Masking (Dynamic)** | **P1** | ❌ Missing | Immuta-level |
| **PII Detection & Classification** | **P1** | ❌ Missing | Collibra-level |
| **Data Retention Policies** | **P1** | ❌ No automated retention | GDPR requirement |
| **Right to Erasure (GDPR Art. 17)** | **P1** | ❌ No deletion workflow | GDPR requirement |
| **Data Export (GDPR Art. 20)** | **P2** | ❌ No portability API | GDPR requirement |
| **Consent Management** | **P2** | ❌ Missing | GDPR/CCPA |
| **Data Classification Labels** | P2 | ❌ Missing | Internal/Confidential/Public |
| **Field-Level Access Control** | P2 | ❌ RBAC at entity level only | Fine-grained needed |

**Action Items:**
- PostgreSQL TDE (pg_tde extension) or filesystem-level LUKS encryption
- Implement `django-fernet-fields` or `pgcrypto` for column-level encryption
- Build PII scanner (regex patterns + ML classification for sensitive fields)
- Add automated retention jobs (archive/delete data older than X days per policy)

### 2.3 📊 Data Quality & Observability

**Current DQ Engine (v1.1.0):** 7 rule types — `not_null`, `range`, `uniqueness`, `pattern`, `custom_sql`, `reference_integrity`, `threshold`

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| DQ Rules Engine | P0 | ✅ 7 rule types | Good foundation |
| DQ Results & Violations | P0 | ✅ Done | Standard |
| DQ Dashboard | P0 | ⚠️ Basic page exists | Needs richness |
| **Data Profiling** | **P0** | ❌ Missing | **Ataccama-level** |
| **Freshness Monitoring** | **P1** | ❌ Missing | Monte Carlo core |
| **Schema Change Detection** | **P1** | ❌ Missing | Monte Carlo core |
| **Volume Anomaly Detection** | **P1** | ❌ Missing | Monte Carlo core |
| **DQ Trend Analysis** | **P1** | ❌ Missing | Ataccama-level |
| **DQ Scorecard / SLI** | **P2** | ❌ Missing | Operational metric |
| **Automated Rule Suggestions** | **P2** | ❌ Missing | AI-assisted (Ataccama) |
| **Cross-Table DQ Rules** | P2 | ❌ Missing | Enterprise need |
| **Real-Time DQ on Ingestion** | P2 | ❌ Batch only | Streaming need |

**Action Items:**
- Build automated data profiling (column stats, distributions, cardinality, null %)
- Implement freshness checks (last_updated timestamp monitoring)
- Add schema change detection (compare current vs. stored schema snapshots)
- Build DQ trend dashboard (violations over time, improvement/regression)
- Implement DQ score (% compliant rules, % clean records)

### 2.4 ⛓️ Data Lineage

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| Entity-Level Lineage | P1 | ✅ 5 entity types | Good start |
| **Column-Level Lineage** | **P1** | ❌ Missing | **Collibra/Ataccama-level** |
| Visual Lineage Graph | P1 | ❌ Missing | Standard |
| Impact Analysis | P2 | ❌ Missing | Enterprise |
| Cross-System Lineage | P2 | ❌ N/A | Enterprise |

**Action Items:**
- Implement column-level lineage: track `source_table.column → target_table.column` mappings
- Build D3/ReactFlow lineage visualization
- Add "what if" impact analysis (changing column X affects Y reports/Z models)

### 2.5 🏛️ Governance & Compliance

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| Audit Trail | P0 | ✅ 316 events | Good |
| Role-Based Access Control | P0 | ✅ 7 personas | Good |
| Policy Engine | P1 | ⚠️ Basic | Needs expansion |
| **Data Stewardship Workflows** | **P1** | ❌ Missing | Collibra-level |
| **Approval Workflows** | **P1** | ❌ Missing | Enterprise |
| **Data Certification / Endorsement** | **P2** | ❌ Missing | Collibra-level |
| **Business Glossary** | **P2** | ⚠️ GlossaryTerm model exists | Needs UI richness |
| **Compliance Reporting** | **P2** | ❌ Missing | SOC2/GDPR evidence |
| **Policy Violation Alerts** | **P2** | ❌ Missing | Operational need |

### 2.6 🔔 Notifications & Alerts

**Current status: ZERO notification infrastructure.** No email, no in-app, no webhooks, no SMS.

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| **Email Notifications** | **P0** | ❌ Missing | **Mandatory** |
| **Password Reset Email** | **P0** | ❌ Missing | **Mandatory** |
| **In-App Notification Bell** | **P1** | ❌ Missing | Standard |
| **DQ Violation Alerts** | **P1** | ❌ Missing | Operational need |
| **Webhook Integration** | **P1** | ❌ Missing | Slack/Teams/API |
| **Notification Preferences** | **P2** | ❌ Missing | User control |
| **Digest Emails (Daily/Weekly)** | **P2** | ❌ Missing | Standard |
| **SMS / Push Notifications** | P3 | ❌ Missing | Optional |

**Action Items:**
- Integrate `django-anymail` for email backend (SendGrid/Mailgun/SES)
- Build notification model with `NotificationType`, `NotificationChannel`, user prefs
- Create in-app notification center (bell icon + dropdown in navbar)
- Add webhook registry (register URL + event types + secret signing)
- DQ violations → fan out to email/Slack/webhook based on severity

### 2.7 📈 Observability, Monitoring & Logging

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| Structured JSON Logging | P0 | ✅ `python-json-logger` | Good |
| Correlation IDs | P0 | ✅ RequestLoggingMiddleware | Good |
| Request Timing | P0 | ✅ Middleware logs duration | Good |
| **Centralized Log Viewer** | **P0** | ❌ Missing | **Mandatory** |
| **Log Level Control (Runtime)** | **P1** | ❌ Missing | Operational need |
| **Metrics Export (Prometheus)** | **P1** | ❌ Missing | Standard |
| **Health Check Dashboard** | **P1** | ⚠️ Has /health/ endpoint | Needs UI |
| **Alerting Rules** | **P1** | ❌ Missing | Standard |
| **APM / Tracing (Sentry/OpenTelemetry)** | **P1** | ❌ Missing | Standard |
| **DB Query Performance Monitoring** | **P2** | ⚠️ django-silk in dev only | Needs production |
| **Uptime Monitoring** | P2 | ❌ Missing | Standard |

**Action Items:**
- Build admin log viewer page (search, filter by level/correlation_id/time)
- Add `django-prometheus` for `/metrics` endpoint
- Integrate Sentry SDK for error tracking
- Add OpenTelemetry instrumentation for distributed tracing
- Build `/admin/logs/` UI (or dedicated page) for log browsing
- Add runtime log level switching (admin action — no restart needed)

### 2.8 💾 Backups & Disaster Recovery

**Current status: ZERO backup infrastructure.** No automated DB dumps, no offsite storage, no recovery procedure.

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| **Automated DB Backups (Daily)** | **P0** | ❌ Missing | **Mandatory** |
| **Point-in-Time Recovery (WAL)** | **P1** | ❌ Missing | Enterprise |
| **Offsite Backup Storage** | **P1** | ❌ Missing | S3/Backblaze |
| **Backup Encryption** | **P1** | ❌ Missing | Security |
| **Backup Verification (Test Restore)** | **P1** | ❌ Missing | Reliability |
| **Disaster Recovery Runbook** | **P1** | ❌ Missing | Operations |
| **High Availability (DB Replica)** | **P2** | ❌ Missing | Enterprise |
| **Multi-Region Replication** | P3 | ❌ Missing | Global scale |

**Action Items:**
- Set up `pg_dump` cron job (daily full, hourly WAL archiving)
- Configure `pgBackRest` or `wal-g` for WAL-based PITR
- Ship encrypted backups to S3/Backblaze B2
- Schedule monthly restore test to verify backup integrity
- Write DR runbook (RTO < 4h, RPO < 1h for Phase 1)

### 2.9 ⚡ Performance & Scalability

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| Redis Caching | P0 | ✅ Config ready, Redis optional | Good |
| DB Connection Pooling | P1 | ⚠️ Django default (no pgBouncer) | Needs pooling |
| **Query Optimization** | **P1** | ⚠️ `select_related`/`prefetch_related` unknown | Needs audit |
| **API Pagination (DRF Default)** | **P1** | ⚠️ Not consistently applied | Standard |
| **CDN for Static Assets** | **P1** | ❌ Missing | Standard |
| **Database Indexing Audit** | **P1** | ❌ Not audited | Standard |
| Read Replicas | P2 | ❌ Missing | Scale |
| Async Task Queue (Celery) | P2 | ❌ Missing | Background jobs |
| Horizontal Scaling | P3 | ❌ Missing | Scale |

**Action Items:**
- Add `pgBouncer` sidecar for connection pooling (transaction mode)
- Run Django Debug Toolbar/Silk in staging to identify N+1 queries
- Enforce DRF `PageNumberPagination` as default across all viewsets
- Add CloudFlare or nginx `proxy_cache` for static assets
- Audit all model queries for missing `select_related`/`prefetch_related`
- Add Celery + Redis for async tasks (DQ runs, report generation, email)

### 2.10 🧩 Developer Experience & API Maturity

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| Swagger/OpenAPI Docs | P0 | ✅ drf-yasg (dev only) | Should be always available |
| **API Versioning** | **P1** | ❌ Missing | `/api/v1/`, `/api/v2/` |
| **SDK / Client Libraries** | **P2** | ❌ Missing | Python/JS SDK |
| **Webhook Signature Verification** | **P1** | ❌ Missing | Security |
| **Rate Limit Headers** | **P2** | ⚠️ DRF default minimal | `X-RateLimit-*` headers |
| **API Changelog** | **P2** | ❌ Missing | Developer docs |
| **Sandbox Environment** | **P2** | ❌ Missing | Testing |
| **Postman Collection** | P3 | ❌ Missing | Onboarding |

### 2.11 🤖 AI/ML Integration (The Differentiator)

Industry trend: Every platform now has an AI agent. Ataccama ONE AI agent generates DQ rules, detects anomalies, resolves issues. Palantir AIP is an AI operating system. Collibra has an AI Command Center.

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| **AI-Powered DQ Rule Suggestions** | **P2** | ❌ Missing | Ataccama differentiator |
| **Natural Language Query** | **P2** | ❌ Missing | Palantir AIP |
| **Automated Anomaly Detection** | **P2** | ❌ Missing | Monte Carlo |
| **AI Copilot for Data Stewards** | P3 | ⚠️ `ai_copilot/` app scaffolded | Needs implementation |
| **Semantic Search** | P3 | ❌ Missing | Collibra |
| **Automated Metadata Tagging** | P3 | ❌ Missing | Collibra |

### 2.12 🏗️ Tenant & Multi-Environment Architecture

| Feature | Priority | Status | Industry Standard |
|---|---|---|---|
| Multi-Tenant Isolation | P1 | ⚠️ Via OrgUnit scoping | Adequate for now |
| **Environment Separation (dev/stage/prod)** | **P0** | ❌ Only dev + "production" | **Mandatory** |
| **Feature Flags** | **P2** | ❌ Missing | Operational safety |
| Blue/Green Deployments | P3 | ❌ Missing | Zero-downtime |
| Canary Releases | P3 | ❌ Missing | Risk mitigation |

---

## 3. Priority Implementation Roadmap

### 🔴 Phase 1 — Critical (Must Have for Production Trust)

| # | Feature | Effort | Pillar |
|---|---|---|---|
| 1 | **Password Reset/Recovery** | 2d | Auth |
| 2 | **Automated DB Backups (pg_dump + S3)** | 1d | DR |
| 3 | **Encryption at Rest (PostgreSQL TDE)** | 1d | Protection |
| 4 | **Email Infrastructure (django-anymail)** | 1d | Notifications |
| 5 | **Centralized Log Viewer UI** | 2d | Observability |
| 6 | **Data Profiling Engine** | 3d | DQ |
| 7 | **API Pagination (DRF default)** | 1d | Performance |
| 8 | **Environment Separation** | 1d | Architecture |
| 9 | **CI/CD Fix & Verified Deploy** | 1d | DevOps |
| | **Phase 1 Total** | **13d** | |

### 🟡 Phase 2 — Enterprise (Differentiators)

| # | Feature | Effort | Pillar |
|---|---|---|---|
| 10 | **Multi-Factor Authentication (TOTP)** | 2d | Auth |
| 11 | **SSO / OIDC Integration** | 3d | Auth |
| 12 | **Column-Level Data Masking** | 3d | Protection |
| 13 | **PII Detection & Classification** | 3d | Protection |
| 14 | **Freshness & Schema Monitoring** | 3d | Observability |
| 15 | **Column-Level Data Lineage** | 5d | Lineage |
| 16 | **In-App Notifications (Bell + Center)** | 3d | Notifications |
| 17 | **Webhook Registry + DQ Alerts** | 3d | Notifications |
| 18 | **Prometheus Metrics + Grafana** | 2d | Observability |
| 19 | **Approval Workflows for DQ/Data Changes** | 4d | Governance |
| 20 | **Celery + Redis for Async Processing** | 2d | Performance |
| | **Phase 2 Total** | **33d** | |

### 🟢 Phase 3 — World-Class (Industry Leaders)

| # | Feature | Effort | Pillar |
|---|---|---|---|
| 21 | **AI-Powered DQ Rule Suggestions** | 5d | AI/ML |
| 22 | **Natural Language Query** | 5d | AI/ML |
| 23 | **Visual Lineage Graph (D3/ReactFlow)** | 3d | Lineage |
| 24 | **Data Marketplace / Self-Service** | 4d | Catalog |
| 25 | **Automated Anomaly Detection (ML)** | 4d | Observability |
| 26 | **SDK Generation (OpenAPI → Python/JS)** | 2d | DevEx |
| 27 | **Semantic Search (Embeddings + Vector DB)** | 3d | AI/ML |
| 28 | **Blue/Green Deployments** | 2d | DevOps |
| 29 | **Point-in-Time Recovery (WAL Archiving)** | 2d | DR |
| 30 | **Attribute-Based Access Control (ABAC)** | 5d | Protection |
| | **Phase 3 Total** | **35d** | |

---

## 4. Comparison Summary: Carbon vs Industry Leaders

| Dimension | Carbon v1.1 | Ataccama ONE | Palantir Foundry | Collibra | Target |
|---|---|---|---|---|---|
| DQ Rule Types | 7 | 20+ | 15+ | 10+ | 15+ |
| Data Lineage | Entity-level | Column-level | Column-level | Column-level | Column-level |
| AI Agent | None | ONE AI Agent | AIP | AI Command Center | P3 |
| Access Control | RBAC | RBAC + ABAC | PBAC | RBAC | ABAC |
| MFA/SSO | None | ✅ | ✅ | ✅ | Phase 2 |
| Notifications | None | ✅ | ✅ | ✅ | Phase 1 |
| Backups | None | ✅ | ✅ | ✅ | Phase 1 |
| Observability | Logging only | Full stack | Full stack | Full stack | Phase 2 |
| Data Masking | None | ✅ | ✅ | ✅ | Phase 2 |
| API Versioning | None | ✅ | ✅ | ✅ | Phase 1 |
| Multi-Tenant | OrgUnit scoping | Full tenant isolation | Project-based | Domain-based | Phase 2 |

---

## 5. Immediate Next Steps

1. **Fix CI/CD** — Merge is done, verify CI passes on next push
2. **Phase 1 Critical Features** — Start with password reset + backups + email
3. **Re-tag v1.1.1** — After CI passes and Phase 1 criticals are in

**Estimated time to 90/100 score:** ~8-10 weeks (Phase 1 + 2)
**Estimated time to 95/100 (world-class):** ~14-16 weeks (all 3 phases)

---

## Appendix A: Existing Strengths (Don't Regress)

Carbon's current advantages over competitors:

1. **Domain-Specific Carbon Calculations** — Purpose-built for GHG accounting, not generic
2. **7-Persona RBAC** — More granular than most out-of-box solutions
3. **Integrated DQ + Governance** — Audit trail tied directly to data quality rules
4. **Lightweight & Fast** — Django + React is simpler than Palantir's complexity
5. **Open Source Core** — No vendor lock-in, full code ownership
6. **982 Tests** — Strong testing culture already in place

## Appendix B: Quick Wins (Each ≤1 Day)

| # | Quick Win | Impact |
|---|---|---|
| 1 | Enable Swagger in production (gated to authenticated users) | DevEx |
| 2 | Add `X-RateLimit-Remaining` headers | API maturity |
| 3 | Add `django-axes` for brute-force protection | Security |
| 4 | Create `backup_db.sh` script with cron | DR |
| 5 | Configure Sentry SDK | Observability |
| 6 | Add `/health/` detailed status (DB, Redis, disk) | Operations |
| 7 | Default DRF pagination class | Performance |
| 8 | Add `.env.example` for all required vars | DevEx |
