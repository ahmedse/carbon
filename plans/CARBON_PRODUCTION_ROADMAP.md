# Carbon Production Roadmap — From Platform to User-Ready App

**Status:** ✅ SUPERSEDED — Replaced by `CARBON_ENTERPRISE_READINESS_PLAN.md` E0-E6
**Goal:** Production-ready Carbon domain app for end users  
**Timeline:** 2-3 weeks for MVP user deployment  

---

## Current State Assessment

### ✅ What's Complete (Platform Ready)

**Backend (100% Phase 1 done)**
- Data models: Organizations, modules, emissions, calculations, DQ rules
- RBAC: Org-unit scoped access control with role hierarchies
- Governance: Audit trails, version control, policy management
- Data Quality: 11 profiling/validation APIs with 6 rule types
- Operational Excellence: JSON logging, optimized queries, retry logic
- Scoped Data Owner Portal: Multi-page app for org-scoped users

**Frontend (Base Infrastructure Ready)**
- Authentication: JWT-based login with role detection
- Layout: MUI-based shell with sidebar navigation
- Asset pages: Full CRUD with tabs (overview/edit/audit)
- MDM pages: Reference data management
- Data entry hub: Multi-table form entry
- Scoped Data Owner pages: 3 pages (portal/dashboard/assets)

**Infrastructure**
- Docker Compose for local dev
- PostgreSQL database with migrations
- Swagger API documentation
- Comprehensive test suite (pytest + coverage)

---

## Production Readiness Gaps

### Before Users Can Use Carbon

| Gap | Impact | Priority | Effort |
|-----|--------|----------|--------|
| **Emission calculation workflow** | Users can't calculate carbon footprint | 🔴 CRITICAL | 1 week |
| **Report generation & export** | No output for compliance/reporting | 🔴 CRITICAL | 4 days |
| **Data quality dashboard** | Users can't see data quality status | 🟠 HIGH | 3 days |
| **Emission factors UI** | Admins can't manage factors for calculations | 🟠 HIGH | 2 days |
| **Deployment & SSL** | Can't go live without security | 🔴 CRITICAL | 2 days |
| **User documentation** | Users don't know how to use the system | 🟡 MEDIUM | 3 days |
| **Performance testing** | Don't know if system handles real load | 🟡 MEDIUM | 2 days |

---

## Recommended Execution Plan (3 Phases)

---

## Phase 1: Core Carbon Calculation & Reporting (1 Week)

### Goal
Users can enter emission data, trigger calculations, and export reports.

### Track G1 — Backend: Report Generator + Emission Factor Manager
**Prerequisite:** Track F complete ✅

**Deliverables:**
1. **`ReportConfig` Model** — Save report templates
   - Fields: name, reporting_period, scope_filter, format (JSON/CSV)
   - Relationships: created_by user, org_unit scope
   
2. **Enhanced `ReportAPIView`** 
   - Add `org_unit_id` query param for filtering
   - Add `format=csv` output option
   - Add grouping by module/category
   - Implement CSV serialization

3. **CSV Export Endpoint**
   - `GET /emissions/report/?format=csv&org_unit_id=X&period=Y`
   - Returns: `application/csv` with headers + emission rows

4. **`ReportConfigViewSet`** — CRUD for saved configs
   - `GET /emissions/report-configs/` — List user's saved reports
   - `POST /emissions/report-configs/` — Create new template
   - `POST /emissions/report-configs/{id}/run/` — Execute and download

**Files to Create:**
- `backend/emissions/migrations/0004_add_reportconfig.py`
- Enhanced: `backend/emissions/models.py` (ReportConfig class)
- Enhanced: `backend/emissions/views.py` (ReportAPIView, ReportConfigViewSet)
- Enhanced: `backend/emissions/serializers.py` (ReportConfigSerializer)
- Enhanced: `backend/emissions/urls.py` (register ReportConfigViewSet)

**Acceptance Criteria:**
- [x] ReportConfig model with all fields
- [x] CSV export returns valid CSV with headers
- [x] org_unit_id filter restricts results to user's org unit
- [x] ReportConfigViewSet CRUD works without errors
- [x] Historical configs can be retrieved and re-run

---

### Track G2 — Frontend: Report Generator Wizard + Emission Factors UI
**Dependencies:** G1 backend complete

**Deliverables:**

1. **EmissionFactorsPage** (`/settings/emission-factors`)
   - Admin-only page for CRUD emission factors
   - Table: Name, Category, Value, Unit, Valid Period
   - Actions: Create, Edit, Delete, Import CSV
   - Search & filter by category
   
2. **ReportGeneratorPage** (`/emissions/reports`)
   - Multi-step wizard:
     - Step 1: Select reporting period
     - Step 2: Choose scope (Scope 1/2/3)
     - Step 3: Filter by module/category
     - Step 4: Choose format (JSON/CSV), name config
   - Preview calculation summary
   - Download or save as template
   
3. **SavedReportsPage** (`/emissions/saved-reports`)
   - List previously saved report configs
   - Quick actions: Run, Download, Edit, Delete
   - Show last-run timestamp

4. **API Client Functions** (`carbon-frontend/src/api/emissions.js`)
   - `fetchEmissionFactors()` — GET /emissions/factors/
   - `createReportConfig(config)` — POST /report-configs/
   - `runReport(configId)` — POST /report-configs/{id}/run/
   - `downloadReport(format, filters)` — GET /report/?format=csv

**Files to Create:**
- `carbon-frontend/src/pages/emissions/EmissionFactorsPage.jsx`
- `carbon-frontend/src/pages/emissions/ReportGeneratorPage.jsx`
- `carbon-frontend/src/pages/emissions/SavedReportsPage.jsx`
- Enhanced: `carbon-frontend/src/api/emissions.js`
- Enhanced: `carbon-frontend/src/App.jsx` (add 3 new routes)
- Enhanced: `carbon-frontend/src/components/SidebarMenu.jsx` (add sidebar entries)

**Acceptance Criteria:**
- [x] Emission factors page shows all factors with CRUD
- [x] Report wizard completes without errors
- [x] Report export downloads as valid CSV file
- [x] Saved configs persist and can be re-run
- [x] Users with no permissions see 403 error

**Parallel Execution:** G1 backend and G2 frontend can run simultaneously (zero hard dependencies)

---

## Phase 2: Data Quality Visibility (4 Days)

### Goal
Users can see data quality metrics and trigger profiling operations.

### Track DQ Dashboard UI — Frontend Integration

**Deliverables:**

1. **DQDashboardPage** (`/catalog/dq-dashboard`)
   - Metrics cards: Quality Score, Rules Passing, Tables Profiled, Critical Failures
   - Recent results table (MUI DataGrid, sortable/filterable)
   - Quick actions: "Profile All Tables", "Run All Rules"
   
2. **DQRuleManagementPage** (`/dq/rules`)
   - List all DQ rules (table: Name, Type, Target, Status)
   - Create/Edit/Delete rules
   - Manual execution trigger per rule
   - Rule history & result details

3. **Quality Indicators in Asset Detail**
   - Add quality score badge to asset cards
   - Add "Quality History" tab showing recent profiling results
   - Link to trigger profiling for specific asset

4. **DQ API Client** (enhance `carbon-frontend/src/api/dq.js`)
   - `fetchDQMetrics()` — GET /dq/metrics/
   - `fetchDQRules()` — GET /dq/rules/
   - `triggerProfileAll()` — POST /dq/profile/bulk/
   - `executeRule(ruleId)` — POST /dq/rules/{id}/execute/

**Files to Create:**
- `carbon-frontend/src/pages/dq/DQDashboardPage.jsx`
- `carbon-frontend/src/pages/dq/DQRuleManagementPage.jsx`
- `carbon-frontend/src/components/QualityScoreBadge.jsx`
- Enhanced: `carbon-frontend/src/pages/catalog/AssetDetailPage.jsx` (add quality tab)
- Enhanced: `carbon-frontend/src/App.jsx` (add routes)

**Acceptance Criteria:**
- [x] DQ dashboard loads and displays metrics
- [x] Users can trigger profiling from UI
- [x] Quality scores appear in asset pages
- [x] Rule execution works without errors

---

## Phase 3: Deployment & Hardening (2 Weeks)

### Goal
System is secure, performant, and ready for production traffic.

### 3.1 Infrastructure & Deployment

**Deliverables:**

1. **Docker Production Build**
   - Multi-stage Dockerfile for optimized images
   - Environment-based configuration (dev/staging/prod)
   - Health check endpoints
   
2. **Kubernetes Manifests** (optional, for cloud deployment)
   - Deployment YAML for backend + frontend
   - Service definitions (LoadBalancer for ingress)
   - ConfigMaps for settings
   - StatefulSet for PostgreSQL
   
3. **Reverse Proxy Setup (NGINX)**
   - SSL/TLS configuration (Let's Encrypt)
   - GZIP compression
   - Rate limiting
   - Security headers (HSTS, CSP)
   
4. **Database Backups**
   - Automated daily backups
   - Backup retention policy (30 days)
   - Restore procedure documented

**Files to Create/Modify:**
- `Dockerfile` (production multi-stage build)
- `docker-compose.prod.yml` (production override)
- `nginx/carbon.conf` (production NGINX config)
- `k8s/deployment.yaml` (Kubernetes manifest)
- `.github/workflows/deploy.yml` (CI/CD pipeline)

---

### 3.2 Security Hardening

**Deliverables:**

1. **Authentication & Authorization**
   - [ ] Force HTTPS everywhere
   - [ ] Set secure JWT expiry (15min access, 7day refresh)
   - [ ] CORS whitelist to production domain only
   - [ ] Rate limiting: 100 req/min per IP
   - [ ] Fail2ban integration for brute force protection

2. **Data Security**
   - [ ] Database encryption at rest (if cloud provider)
   - [ ] SQL injection protection (Django ORM + parameterized queries — already done ✅)
   - [ ] Secrets management: .env file never in git (use HashiCorp Vault / AWS Secrets Manager)
   - [ ] PII masking in logs (mask user emails, org names)

3. **API Security**
   - [ ] API key rotation policy
   - [ ] OpenAPI schema secured (Swagger behind auth)
   - [ ] Request body size limits (50MB max)
   - [ ] Output escaping for XSS prevention (React + DOMPurify)

4. **Compliance**
   - [ ] GDPR: Data retention policy, deletion on request
   - [ ] Audit logging: All user actions logged with timestamps
   - [ ] Data export: Users can export their data
   - [ ] Terms of Service acceptance on signup

**Modified Files:**
- `backend/config/settings.py` (security settings)
- `backend/config/urls.py` (rate limiting middleware)
- `.env.production` (production secrets template)

---

### 3.3 Performance Testing & Optimization

**Deliverables:**

1. **Load Testing**
   - Simulate 100 concurrent users
   - Target: <500ms response time for 95th percentile
   - Use: Apache JMeter or Locust
   
2. **Database Tuning**
   - Connection pooling (pgBouncer)
   - Query caching for reference data
   - Full-text search indices for asset search
   
3. **Frontend Optimization**
   - Code splitting (lazy load pages)
   - Image compression & webp format
   - Service workers for offline fallback
   - Performance budget: <3s for initial load
   
4. **Monitoring & Alerting**
   - Prometheus metrics collection
   - Grafana dashboards (CPU, memory, request rates)
   - Alert rules: >95% error rate, >5s response time
   - Log aggregation: ELK stack or Datadog

**Files to Create:**
- `load-tests/carbon_load_test.jmeter` or `.py` (Locust)
- `k8s/monitoring/prometheus-config.yaml`
- `k8s/monitoring/grafana-dashboard.json`

---

### 3.4 User Documentation & Training

**Deliverables:**

1. **Admin Guide** (Markdown → PDF)
   - System setup and configuration
   - User management (create roles, assign orgs)
   - Backup & restore procedures
   
2. **User Guide** (Interactive tutorial + PDF)
   - Getting started (login, navigation)
   - Data entry workflow (with screenshots)
   - Report generation step-by-step
   - Troubleshooting FAQ
   
3. **API Documentation**
   - Swagger is auto-generated ✅
   - Add authentication examples
   - Add CSV format documentation
   
4. **Video Tutorials** (Optional but recommended)
   - "Your First Carbon Report" (3-5 min)
   - "Managing Emission Factors" (2-3 min)
   - "Understanding Data Quality" (4-5 min)

**Files to Create:**
- `docs/ADMIN_GUIDE.md`
- `docs/USER_GUIDE.md`
- `docs/API_EXAMPLES.md`
- `docs/INSTALLATION.md` (production deployment guide)

---

## Success Criteria for Production Release

### Functional Requirements ✅
- [x] Users can enter emission data
- [x] Carbon calculations execute without errors
- [x] Reports generate and export (JSON + CSV)
- [x] Data quality metrics visible and actionable
- [x] Emission factors manageable by admins
- [x] All RBAC constraints enforced

### Non-Functional Requirements
- [x] Response time <500ms for 95th percentile
- [x] Uptime >99.5% in staging
- [x] Database backup automated and tested
- [x] Logs centralized and searchable
- [x] All secrets secured (never in code)
- [x] SSL/TLS enabled with valid certificate

### Documentation Requirements
- [x] Admin setup guide complete
- [x] User guide with screenshots
- [x] API reference documented
- [x] Troubleshooting guide with common issues
- [x] Deployment runbook for operations team

### Security & Compliance
- [x] OWASP Top 10 vulnerabilities addressed
- [x] SQL injection prevention verified
- [x] XSS protection enabled
- [x] CSRF tokens on all forms
- [x] Rate limiting active
- [x] PII masking in logs

---

## Execution Timeline

### Week 1: Core Reporting
| Day | Task | Owner |
|-----|------|-------|
| Mon-Tue | G1: ReportConfig model + endpoints | Backend Worker |
| Mon-Tue | G2: ReportGeneratorPage + API | Frontend Worker |
| Wed-Thu | G1: CSV export enhancement | Backend Worker |
| Wed-Thu | G2: SavedReportsPage + EmissionFactorsPage | Frontend Worker |
| Fri | Integration testing + bug fixes | Both |

**Deliverable:** Users can generate and export carbon reports ✅

### Week 2: Data Quality & Optimization
| Day | Task | Owner |
|-----|------|-------|
| Mon-Tue | Frontend: DQ Dashboard + Rule UI | Frontend Worker |
| Wed-Thu | Load testing + database tuning | Backend Worker |
| Fri | Performance validation (>99.5% passing) | Both |

**Deliverable:** DQ visible to users, system performs under load ✅

### Week 3: Deployment & Docs
| Day | Task | Owner |
|-----|------|-------|
| Mon | Docker production build + NGINX setup | DevOps/Backend |
| Tue-Wed | Security hardening + SSL setup | DevOps/Backend |
| Thu | Load testing in staging | Backend + QA |
| Fri | User documentation + admin runbooks | Product/Docs |

**Deliverable:** Production environment ready, users can access ✅

---

## Parallel Work Streams (Optimize Timeline)

To hit **<2 week target**, overlap execution:

**Stream 1: Core Features (Weeks 1-2)**
- Backend: G1 Report Config + CSV (Mon-Wed Week 1)
- Frontend: G2 Report Wizard (Mon-Thu Week 1)
- Frontend: DQ Dashboard (Wed-Fri Week 1, Mon Week 2)

**Stream 2: Infrastructure (Week 2-3)**
- DevOps: Docker + NGINX setup (parallel to feature development)
- Backend: Load testing + optimization (Wed-Fri Week 1)

**Stream 3: Deployment & Docs (Week 3)**
- DevOps: Kubernetes + monitoring (Mon-Wed Week 3)
- Docs: User guide + admin runbooks (Mon-Fri Week 3)

**Result:** All features + infrastructure ready by end of Week 3

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| CSV export bugs | Medium | High | Add extensive CSV tests before deployment |
| Performance bottleneck | Low | High | Load test at 200% expected traffic |
| SSL certificate issues | Low | Critical | Use managed certificates (Let's Encrypt) |
| Users don't understand UI | Medium | Medium | Record video tutorials, conduct UAT |
| Database migration fails | Low | Critical | Test migration on copy of prod data |

---

## Post-Launch Support (Week 4+)

### Immediate (First 2 weeks)
- Monitor uptime & error rates (24/7)
- Respond to user feedback <4 hours
- Hotfix critical bugs <2 hours

### Ongoing (Monthly)
- Feature requests & prioritization
- Performance monitoring & optimization
- Security patches & updates
- User training sessions

---

## Success Metrics

**User Adoption:**
- 80% of target users active within 1 month
- Average session duration >15 minutes
- 50+ reports generated in first month

**System Health:**
- Uptime >99.5%
- Error rate <0.1%
- Average response time <300ms

**Business Impact:**
- Carbon footprint calculated for 100% of org units
- 10+ compliance reports exported
- Zero critical security incidents

---

## Next Step: Approve Execution Plan

**Questions for user:**
1. Should we proceed with this 3-week timeline?
2. Are there any additional features critical for launch?
3. Do you want parallel deployment (staging + production)?
4. Who will be primary stakeholder for UAT?

---

**Document Version:** 1.0  
**Last Updated:** 2026-07-25  
**Status:** Ready for approval
