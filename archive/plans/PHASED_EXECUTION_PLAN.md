# Carbon Platform — Phased Execution Plan
**Role**: Master Architect  
**Date**: 2026-08-06  
**Based on**: `plans/SYSTEM_AUDIT_2026_08_06.md`  
**Starting state**: 663/664 tests, 0 lint errors, build clean, DQ fix + lint fix applied

---

## PHASE 0 — System Cleanup 🧹 (15 min)
**Priority**: Immediate quick-win — frees disk, reduces repo noise

| # | Task | Action | Impact |
|---|------|--------|--------|
| 0.1 | Delete `raw/` directory | `rm -rf raw/` — contains PPTX/XLSX/DOCX, not source | Frees ~50 MB |
| 0.2 | Delete SQL backup | `rm backend/carbon_dev_20260112.sql` — 363 MB | Frees 363 MB |
| 0.3 | Truncate logs | Truncate `backend/logs/*.log` > 10 MB, keep last 1000 lines | Reduces repo noise |
| 0.4 | Archive legacy plans | Move TASK-*.md (completed tasks) to `plans/archive/` | Reduces root file count |
| 0.5 | Clean __pycache__ | `find . -type d -name __pycache__ -exec rm -rf {} +` | Standard hygiene |
| 0.6 | Clean .pyc files | `find . -name '*.pyc' -delete` | Standard hygiene |
| 0.7 | Update .gitignore | Add `raw/`, `*.sql` (backups), `*.dump` entries | Prevents recurrence |

---

## PHASE 1 — Swagger Docs ✅ (45 min)
**Priority**: Kills last 11 test failures → 664/664 passing

| # | Task | Action |
|---|------|--------|
| 1.1 | Audit all 11 missing endpoints | Run `test_swagger_docs.py` verbose, capture exact endpoint names |
| 1.2 | Add `@swagger_auto_schema` to MDM custom actions | `OrgUnitViewSet` custom actions: tree, children, ancestors, descendants, by_type, search, stats, move, reorder |
| 1.3 | Add `@swagger_auto_schema` to DQ custom actions | `DQRuleViewSet` execute, `DQProfileViewSet` custom actions, `DQResultViewSet` custom actions |
| 1.4 | Fix schema generation test | `test_swagger_schema_generation` — ensure all endpoints have operation_id |
| 1.5 | Verify | Run full backend test suite → 664/664 ✅ |

---

## PHASE 2 — GHG Protocol Compliance 🌿 (2-3 days)
**Priority**: Certification-blocking for GHG Protocol / ISO 14064

| # | Task | Effort | Description |
|---|------|--------|-------------|
| 2.1 | Scope 2 dual calculation | Medium | Add `calculation_method` field (market-based / location-based) to CalculationRule. Create dual-result on Scope 2 electricity calculations. |
| 2.2 | Organizational boundary | Medium | Add `OrganizationalBoundary` model with consolidation approach (equity share / financial control / operational control). Wire to ReportingPeriod. |
| 2.3 | Base year + recalculation policy | Medium | Add `BaseYear` model. Add `RecalculationTrigger` model (structural change, methodology change, error correction, threshold). Auto-flag when trigger conditions met. |
| 2.4 | GHG Inventory Report PDF | Small | Generate printable PDF with: org boundary statement, methodology, scope 1/2/3 totals, base year comparison, verification status. Use WeasyPrint or ReportLab. |
| 2.5 | Emission factor version tracking | Small | Add `applied_at` timestamp to CalculationResult. Snapshot emission factor version at calculation time. |
| 2.6 | Activity data quality rating | Medium | Add `data_quality_tier` (1/2/3 per IPCC) to ActivityData. Roll up to calculation quality score. |

---

## PHASE 3 — Test Coverage (1-2 days)
**Priority**: connections, evidence, importexport have near-zero coverage but active frontend pages

| # | Task | Effort |
|---|------|--------|
| 3.1 | `connections` test suite | Create `connections/tests/test_api.py` — CRUD, RBAC, config masking, connection test endpoint |
| 3.2 | `evidence` test suite | Create `evidence/tests/test_api.py` — upload, attach, detach, RBAC, file type validation |
| 3.3 | `importexport` test suite | Create `importexport/tests/test_api.py` — import, export, audit trail, RBAC, error handling |

---

## PHASE 4 — CBAC Completion (1 day)
**Priority**: Architectural consistency — wire or deprecate can()

| # | Task | Effort |
|---|------|--------|
| 4.1 | Decision: wire `can()` or deprecate | Assess if `can()` adds value over direct `userCapabilities` check |
| 4.2 | Implement decision | Either wire `can()` into AdminRoute + 5 gate points, or remove `can()` from authz.js public API |
| 4.3 | CBAC test hardening | Ensure `cbac.test.jsx` has full coverage of capability inheritance graph |
| 4.4 | Sidebar capability-gating | Menu items gated on capabilities, not perspectives |

---

## PHASE 5 — Production Infrastructure (3-5 days)
**Priority**: Go-live blockers

| # | Task | Effort |
|---|------|--------|
| 5.1 | PROD_HOST configuration | Set production hostname in config, test nginx routing |
| 5.2 | Sentry integration | Add `sentry-sdk` to requirements, configure DSN, test error capture |
| 5.3 | CI/CD pipeline | GitHub Actions: lint → test → build → deploy workflow |
| 5.4 | PostgreSQL prod tuning | Connection pooling (pgbouncer), backup schedule, WAL archiving |
| 5.5 | Redis prod config | Persistence (RDB + AOF), memory limit, eviction policy |
| 5.6 | SSL/TLS | Certbot/Let's Encrypt, auto-renewal cron |

---

## PHASE 6 — Performance Optimization (1 day)
**Priority**: User experience at scale

| # | Task | Effort |
|---|------|--------|
| 6.1 | OrgUnit serializer N+1 | `prefetch_related` for `full_path`, `children_count`, `descendants_count` |
| 6.2 | Dataschema table list N+1 | `select_related` / `prefetch_related` for field/dataset joins |
| 6.3 | Frontend bundle splitting | Split `index-xxx.js` (330 KB) into route-based chunks |

---

## EXECUTION ORDER

```
Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Phase 5 → Phase 6
  ↓         ↓
 TODAY    TODAY
```

**Rationale**: Phase 0 (cleanup) and Phase 1 (swagger docs) are independent quick-wins that can be done in a single session. Phase 2 (GHG) is the highest business-value work. Phase 3 (tests) is prerequisite for confident Phase 5 (production). Phase 4 (CBAC) is architectural cleanup that should happen before new features. Phase 5 (prod infra) gates go-live. Phase 6 (perf) is optimization that can happen in parallel with production.

---

## SUCCESS METRICS

| Metric | Current | Target |
|--------|---------|--------|
| Backend tests passing | 663/664 | 664/664 |
| Swagger doc coverage | ~85% | 100% |
| GHG Protocol gaps | 8 open | 0 open (or documented deferrals) |
| Test coverage (thin apps) | <10% | >60% |
| Lint errors | 0 | 0 |
| CBAC dead code | `can()` unused | Resolved (wired or removed) |
| Production deployable | ❌ | ✅ |
| N+1 queries on list views | 2 known | 0 |
