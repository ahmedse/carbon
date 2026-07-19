# RAPTOR EXECUTION PROMPT — RUN A9 (Phases 3-5) + RUN A10 (All 5 Phases) — PARALLEL

**Date:** 2026-07-19  
**Master:** Architect (you) | **Worker:** Raptor (execute this)  
**Mode:** Parallel execution with checkpoint handoffs  
**Status:** 🚀 READY FOR IMMEDIATE EXECUTION

---

## OVERVIEW

You have two RUNs to execute in parallel:

1. **RUN A9 (Bulk Import/Export) — 30% remaining**
   - Phases 1-2 ✅ DONE (backend endpoint + wizard component)
   - Phases 3-5 📋 PENDING (template download, export features, testing)

2. **RUN A10 (Data Quality Integration) — 100% to do**
   - All 5 phases from scratch
   - Backend APIs, frontend components, integration, testing

**Why Parallel?**
- A9 and A10 are independent (no code dependencies)
- Keep momentum: Don't idle waiting for A9 completion
- Estimated: Both ready for sign-off by end of day if executed efficiently

---

## EXECUTION STRATEGY

### Phase Sequencing

**Week 1 (Today):**
- A9 Phase 3 (Template endpoint) + A10 Phase 1 (Backend APIs) — ~2 hours
- Checkpoint review by Master
- A9 Phase 4 (Export features) + A10 Phase 2 (Frontend API layer) — ~2 hours
- Checkpoint review by Master
- A9 Phase 5 (Testing) + A10 Phase 3 (Components) — ~3 hours
- Master review of both before moving to final phases

**Week 2:**
- A10 Phase 4 (Integration) + A10 Phase 5 (Testing) — ~2-3 hours
- Final sign-off by Master
- Prepare for RUN A11 (Reporting & Analytics)

### Checkpoint Protocol

After each parallel pair of phases:
1. Create summary report: `PHASE{N}_A9_COMPLETION.txt` + `PHASE{N}_A10_COMPLETION.txt`
2. Include: Objective, steps completed, acceptance criteria checklist, test results, git commits
3. Post to Master channel/repo for review
4. **Wait for Master "Approved for next phase"** before proceeding
5. If revisions needed: Fix and resubmit same checkpoint (don't move forward)

---

## DETAILED EXECUTION PLAN

### CHECKPOINT 1: A9 Phase 3 + A10 Phase 1

#### A9 Phase 3: Template Download Endpoint

**What:** Create API endpoint to download blank CSV template for data import

**File to modify:** `backend/dataschema/views.py`

**Steps:**

1. **Review existing template endpoint (if it exists)**
   ```bash
   grep -n "download.*template\|template.*download" backend/dataschema/views.py
   ```
   - If found, extend it
   - If not, add new action to `DataRowViewSet`

2. **Implement `GET /carbon-api/datarows/download-template/` action**
   ```python
   @action(detail=False, methods=['get'], url_path='download-template')
   def download_template(self, request):
       """Generate CSV template for bulk import"""
       data_table_id = request.query_params.get('data_table')
       if not data_table_id:
           return Response({'error': 'data_table required'}, status=400)
       
       # Fetch table and fields
       table = DataTable.objects.get(id=data_table_id)
       fields = DataField.objects.filter(data_table=table)
       
       # Create CSV with headers (field names)
       import csv, io
       output = io.StringIO()
       writer = csv.writer(output)
       writer.writerow([f.name for f in fields])
       
       # Optional: add example row
       example_row = []
       for f in fields:
           if f.field_type == 'number':
               example_row.append('0')
           elif f.field_type == 'boolean':
               example_row.append('true')
           else:
               example_row.append('example value')
       writer.writerow(example_row)
       
       response = HttpResponse(output.getvalue(), content_type='text/csv')
       response['Content-Disposition'] = 'attachment; filename="template.csv"'
       return response
   ```

3. **Test endpoint manually**
   ```bash
   curl -X GET "http://localhost:8000/carbon-api/datarows/download-template/?data_table=1" \
     -H "Authorization: Bearer YOUR_TOKEN" \
     -o template.csv
   
   # Verify: template.csv should have headers + example row
   cat template.csv
   ```

4. **Verify permission scoping**
   - User should only download template for tables in their assigned modules (same as bulk-import)
   - Check: `DataRowViewSet.get_permissions()` applies `HasScopedRole`

5. **Git commit**
   ```bash
   git add backend/dataschema/views.py
   git commit -m "A9 Phase 3: Add template download endpoint"
   ```

**Acceptance Criteria — A9 Phase 3:**
- [ ] Endpoint responds with 200 OK + CSV attachment
- [ ] CSV has field headers (from table)
- [ ] CSV has example row
- [ ] File name is "template.csv"
- [ ] Permission check: User can only download for assigned tables
- [ ] No console errors

---

#### A10 Phase 1: Backend API Setup & RBAC Fixes

**What:** Fix DQ ViewSet permissions + create 5 new API endpoints

**Files to modify:**
- `backend/dq/views.py` — Fix existing ViewSets + add new endpoints
- `backend/accounts/permissions.py` — Add `ReadScopedWriteAdmin` if not present (from A3)

**Steps:**

1. **Audit existing DQ views**
   ```bash
   grep -n "class.*ViewSet\|permission_classes" backend/dq/views.py
   ```
   - Should see: `TableProfileViewSet`, `FieldProfileViewSet`, `DQRuleViewSet`, `DQResultViewSet`
   - Check permission: Should be `ReadAnyWriteGlobalAdmin` (needs fixing)

2. **Check if `ReadScopedWriteAdmin` exists**
   ```bash
   grep -n "class ReadScopedWriteAdmin" backend/accounts/permissions.py
   ```
   - If NOT found, copy from TASK-RESULT-A3.md or create it:
     ```python
     class ReadScopedWriteAdmin(permissions.BasePermission):
         """Org-scoped read, admin-only write"""
         def has_permission(self, request, view):
             if not request.user or not request.user.is_authenticated:
                 return False
             if request.method in ['GET', 'HEAD', 'OPTIONS']:
                 return True  # Org-scoped read enforced in queryset
             # Write (POST/PUT/DELETE) only for global admins
             return user_is_global_admin(request.user)
     ```

3. **Fix ViewSet permissions in `backend/dq/views.py`**
   - Import: `from accounts.permissions import ReadScopedWriteAdmin`
   - For each ViewSet:
     ```python
     class TableProfileViewSet(viewsets.ReadOnlyModelViewSet):
         serializer_class = TableProfileSerializer
         permission_classes = [ReadScopedWriteAdmin]  # Changed from ReadAnyWriteGlobalAdmin
         
         def get_queryset(self):
             qs = TableProfile.objects.all()
             # Add org scoping
             from accounts.rbac_utils import get_allowed_org_unit_ids
             org_ids = get_allowed_org_unit_ids(self.request.user, [])
             qs = qs.filter(data_table__org_unit_id__in=org_ids)
             
             if self.request.query_params.get('data_table'):
                 qs = qs.filter(data_table_id=self.request.query_params['data_table'])
             return qs
     ```
   - Do same for: `FieldProfileViewSet`, `DQRuleViewSet`, `DQResultViewSet`

4. **Add new API endpoints in `DQResultViewSet` or create new viewset**

   **Endpoint 1: GET `/carbon-api/dq/metrics/`**
   ```python
   # Add custom action in new viewset or update existing
   @action(detail=False, methods=['get'])
   def org_metrics(self, request):
       """Aggregate DQ metrics for user's org units"""
       from accounts.rbac_utils import get_allowed_org_unit_ids
       org_ids = get_allowed_org_unit_ids(request.user, [])
       
       profiles = TableProfile.objects.filter(
           data_table__org_unit_id__in=org_ids
       )
       
       total_rows = sum(p.row_count for p in profiles)
       avg_completeness = sum(p.completeness_pct * p.row_count for p in profiles) / total_rows if total_rows > 0 else 0
       
       return Response({
           'org_count': len(org_ids),
           'table_count': profiles.count(),
           'total_rows': total_rows,
           'completeness_pct': round(avg_completeness, 2),
           'uniqueness_pct': 85.0,  # TODO: Calculate from FieldProfile
           'compliance_pct': 88.0,  # TODO: Calculate from DQResult
       })
   ```
   - Route: Should auto-register as `/carbon-api/dq/metrics/`

   **Endpoint 2: GET `/carbon-api/dq/metrics/table/{tableId}/`**
   ```python
   @action(detail=False, methods=['get'], url_path='table-metrics')
   def table_metrics(self, request):
       """Get table + field profiles + active rules"""
       table_id = request.query_params.get('table_id')
       table = DataTable.objects.get(id=table_id)
       
       # Check permission
       if not user_has_module_role(request.user, table.module_id, ['any']):
           return Response({'error': 'Not authorized'}, status=403)
       
       profile = TableProfile.objects.filter(data_table=table).first()
       fields = DataField.objects.filter(data_table=table)
       field_profiles = FieldProfile.objects.filter(data_field__data_table=table)
       rules = DQRule.objects.filter(data_table=table, is_active=True)
       
       return Response({
           'table_id': table.id,
           'table_name': table.name,
           'row_count': profile.row_count if profile else 0,
           'completeness_pct': profile.completeness_pct if profile else 0,
           'field_profiles': FieldProfileSerializer(field_profiles, many=True).data,
           'active_rules': DQRuleSerializer(rules, many=True).data,
       })
   ```

   **Endpoints 3-5:** Similar pattern (field metrics, results, run validation)
   - See TASK-A10.md for full specs

5. **Test endpoints with curl**
   ```bash
   # Test as org-scoped user
   TOKEN="..."
   curl -X GET "http://localhost:8000/carbon-api/dq/metrics/" \
     -H "Authorization: Bearer $TOKEN"
   
   # Expected: { table_count: X, completeness_pct: Y, ... }
   
   # Test as non-assigned table
   curl -X GET "http://localhost:8000/carbon-api/dq/metrics/table/999/" \
     -H "Authorization: Bearer $TOKEN"
   
   # Expected: 403 Forbidden or empty result
   ```

6. **Git commit**
   ```bash
   git add backend/dq/views.py backend/accounts/permissions.py
   git commit -m "A10 Phase 1: DQ API endpoints + RBAC scoping"
   ```

**Acceptance Criteria — A10 Phase 1:**
- [ ] All 5 endpoints respond 200 OK for authorized users
- [ ] Org-scoped user gets only their org's data
- [ ] Global admin gets all data
- [ ] Non-admin cannot POST/DELETE rules (403)
- [ ] Endpoints return expected schemas (see TASK-A10)
- [ ] No console errors in backend logs

---

### CHECKPOINT 2: A9 Phase 4 + A10 Phase 2

*(After Master approves Phase 1 of each)*

#### A9 Phase 4: Enhanced Export Features

**What:** Improve export functionality (export with filters, export selected rows)

**File:** `carbon-frontend/src/api/dataschema.js` + `carbon-frontend/src/components/TableDataPage.jsx`

**Tasks:**
- [ ] Verify export button already works (it should from earlier work)
- [ ] Add "Export Selected" button (export only checked rows)
- [ ] Add "Export Filtered" button (export with current filter applied)
- [ ] Test: All 3 export modes work

**Acceptance Criteria:**
- [ ] Export All: Downloads all rows
- [ ] Export Selected: Downloads only checked rows
- [ ] Export Filtered: Downloads rows matching current filters
- [ ] Filename format: `export_{tableName}_{timestamp}.csv`

---

#### A10 Phase 2: Frontend API Integration Layer

**What:** Create `carbon-frontend/src/api/dq.js` with all DQ API calls

**File to create:** `carbon-frontend/src/api/dq.js`

**Functions to implement:**
1. `getOrgDQMetrics(token)` — GET `/carbon-api/dq/metrics/`
2. `getTableDQMetrics(token, tableId)` — GET `/carbon-api/dq/metrics/table/{tableId}/`
3. `getFieldDQMetrics(token, fieldId)` — GET `/carbon-api/dq/metrics/field/{fieldId}/`
4. `getDQResults(token, tableId)` — GET `/carbon-api/dq/results/?data_table={tableId}`
5. `runDQValidation(token, tableId)` — POST `/carbon-api/dq/rules/run-now/`

**Pattern:**
```javascript
export async function getOrgDQMetrics(token) {
  try {
    return await apiFetch('/carbon-api/dq/metrics/', {
      method: 'GET',
      headers: { 'Authorization': `Bearer ${token}` },
    });
  } catch (error) {
    console.error('DQ metrics fetch failed:', error);
    return null;
  }
}
```

**Acceptance Criteria:**
- [ ] All 5 functions exported
- [ ] Error handling graceful (console.error, return null)
- [ ] Browser console test: `getOrgDQMetrics(token)` returns object

---

### CHECKPOINT 3: A9 Phase 5 + A10 Phase 3

*(After Master approves Phase 2 of each)*

#### A9 Phase 5: Testing & Documentation

**What:** Complete A9 with testing, build verification, and final documentation

**Tasks:**
- [ ] Frontend build: `npm run build` — must succeed
- [ ] Manual browser test:
  - Login as data-owner
  - Navigate to module page
  - Click Import button → Wizard should open
  - Upload CSV → Should parse and map columns
  - Validate → Should show summary
  - Click Import → Should create rows + show summary
- [ ] Test template download: `GET /carbon-api/datarows/download-template/?data_table=1` should return CSV
- [ ] Test export variants: All 3 modes (all, selected, filtered) work
- [ ] Create `TASK-RESULT-A9.md` with full documentation

**Deliverable:**
- `TASK-RESULT-A9.md` (400-500 lines, same format as A8)
- Updated `docs/RUN_LOG.md` with A9 entry
- Git commit: "A9 complete: Bulk Import/Export full cycle"

---

#### A10 Phase 3: Frontend Components — DQ Card & Drawer

**What:** Create Material-UI components for DQ visualization

**Components to create:**
1. `carbon-frontend/src/components/dq/DataQualityCard.jsx` (summary card)
2. `carbon-frontend/src/components/dq/DQMetricsDrawer.jsx` (detailed drawer with tabs)
3. `carbon-frontend/src/components/dq/DQRulesList.jsx` (rules list)

**Design:**
- DataQualityCard: Shows completeness/uniqueness/compliance % with color bars
- DQMetricsDrawer: 3 tabs (Overview | Rules | Results) with detailed breakdowns
- DQRulesList: Simple list of active rules

**Acceptance Criteria:**
- [ ] Components render without errors
- [ ] Pass mock data props → Verify rendering
- [ ] Color coding works (green >90%, yellow 70-90%, red <70%)
- [ ] Drawer opens/closes properly
- [ ] No console errors

---

### FINAL PHASES: A10 Phase 4 + A10 Phase 5

*(After Master approves Phase 3 of A10)*

#### A10 Phase 4: Integration

**What:** Integrate DQ components into ModuleLandingPage and TableDataPage

**Tasks:**
- [ ] Add DataQualityCard to ModuleLandingPage
- [ ] Add DQMetricsDrawer integration
- [ ] Add "Data Quality" button to TableDataPage toolbar
- [ ] Verify breadcrumbs not broken
- [ ] Frontend build succeeds

#### A10 Phase 5: Testing & Documentation

**What:** Complete testing, validation, and A10 documentation

**Tasks:**
- [ ] Backend tests: `pytest backend/dq/tests/test_api_scoping.py` (5 tests, target 5/5 PASS)
- [ ] Browser tests: 8 scenarios per TASK-A10.md
- [ ] Build verification: `npm run build` success
- [ ] Create `TASK-RESULT-A10.md` with full validation
- [ ] Update `docs/RUN_LOG.md` with A10 entry
- [ ] Git commit: "A10 complete: DQ Integration full cycle"

---

## KEY REMINDERS FOR WORKER

1. **Checkpoints are MANDATORY** — Don't skip Master review between phases
2. **Report format:** Use same format as `PHASE2_A9_COMPLETION_SUMMARY.txt` (clear sections, checkboxes, test results)
3. **Git commits:** Make one commit per checkpoint (not per phase), include summary in message
4. **Testing:** Test as you go (don't wait for Phase 5)
5. **Communication:** If blocked → Escalate to Master immediately
6. **Code quality:** Follow existing patterns (see reference files in TASK-A10.md)

---

## SUCCESS CRITERIA FOR BOTH RUNs

**RUN A9 COMPLETE when:**
- ✅ Template download works (GET endpoint)
- ✅ Export variants work (all, selected, filtered)
- ✅ Frontend build succeeds
- ✅ Manual browser tests pass (import + export full cycle)
- ✅ TASK-RESULT-A9.md created
- ✅ docs/RUN_LOG.md updated

**RUN A10 COMPLETE when:**
- ✅ 5 backend API endpoints working with RBAC
- ✅ Frontend API layer (`dq.js`) complete
- ✅ 3 components (Card, Drawer, RulesList) rendering
- ✅ Components integrated into ModuleLandingPage + TableDataPage
- ✅ All 8 browser test scenarios pass
- ✅ Backend tests pass (5/5)
- ✅ TASK-RESULT-A10.md created
- ✅ docs/RUN_LOG.md updated

**Both RUNs passing = Ready for A11 (Reporting & Analytics)**

---

## NEXT STEPS

1. ✅ **You are reading this prompt** — Master has set clear expectations
2. 👉 **BEGIN CHECKPOINT 1:**
   - A9 Phase 3: Template download endpoint (backend only, ~1 hour)
   - A10 Phase 1: DQ backend APIs + RBAC (backend only, ~2 hours)
3. 📤 **Report back:** Create summary reports for both phases
4. ⏸️ **Wait:** Master will review and approve or request fixes
5. ➡️ **Proceed:** If approved, move to Checkpoint 2

---

**Ready? Begin Checkpoint 1. Report back with results.**
