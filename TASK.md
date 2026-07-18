# TASK.md — RUN A3: Data-Owner Scoped Experience

---

## MASTER CONTEXT

**Protocol:** Master/Worker handoff (see `.clinerules/master-worker-protocol.md`)  
**Master:** Planner (this file's author)  
**Worker:** Raptor/Copilot (executor)  
**Active RUN sequence:** A0 ✅ → A1 ✅ → A2 ✅ → **A3** → A4 → A5 → A6

**Previous RUN findings:**
- **A0:** Data-owner read scoping works perfectly; DataSchema rows returned 403 (unclear why)
- **A1:** Repository cleaned
- **A2:** Governance RBAC fixed (global admins only can write catalog/mdm/dq)

**Current state (from A0 audit):**
- ✅ Emissions dashboard scoping works perfectly (facilities sees 44 calcs, transport sees 0)
- ✅ Governance writes correctly blocked for data-owners (403s verified)
- ⚠️ **DataSchema rows returned 403** for facilities.officer on table 7 (belongs to their module 5)
- ⚠️ **Unclear:** Can data-owners CRUD DataTable/DataField (schema)? Can they upsert DataRows?

**Roadmap:**
- **A0** ✅: Ground-truth audit
- **A1** ✅: Repo hygiene & doc truth
- **A2** ✅: Core governance RBAC fix
- **A3** (this RUN): Data-owner scoped experience — verify & close gaps
- **A4**: Admin experience — verify & close gaps
- **A5**: Data Trust surfacing decision
- **A6**: Deployment-readiness gate

---

## 1. HEADER

**RUN ID:** A3  
**Title:** Data-Owner Scoped Experience  
**Type:** BACKEND (investigation + fixes)  
**Worker:** Raptor  
**Master:** Planner  
**Date Issued:** 2026-07-18

---

## 2. OBJECTIVE

**Problem:** The A0 audit found that DataSchema rows returned 403 for a data-owner (facilities.officer) even though the table belonged to their module scope. The permission model is unclear about whether data-owners can:
1. **Read/write DataTable and DataField** (schema management)
2. **CRUD DataRows** (data entry)
3. **Bulk upsert DataRows** (CSV upload)

**Goal:** Clarify and fix the data-owner permission model so that:
1. Data-owners can **read** DataTable/DataField within their org scope (to see schema)
2. Data-owners **cannot write** DataTable/DataField (schema is admin-only, per design)
3. Data-owners **can CRUD** DataRows within their org scope (data entry)
4. Data-owners **can bulk upsert** DataRows (CSV upload)
5. All operations are properly scoped to their OrgUnit subtree

**Success:** A test showing that a data-owner can:
- ✅ Read DataTable/DataField in their scope
- ❌ Cannot create/update DataTable/DataField (403)
- ✅ Can CRUD DataRows in their scope
- ✅ Can bulk upsert DataRows via CSV upload

---

## 3. SCOPE — IN

- **Analyze current DataSchema permission model** (`dataschema/views.py`, `dataschema/permissions.py`)
- **Investigate the 403 error** from A0 Step 4.5 (DataSchema rows for facilities.officer)
- **Test data-owner CRUD operations** on DataTable, DataField, DataRow
- **Fix permission gaps** if data-owners should have access but don't
- **Test bulk upsert** (if endpoint exists)
- **Document findings** in TASK-RESULT-A3.md

---

## 4. SCOPE — OUT (DO NOT TOUCH)

- **No changes to governance apps** (catalog/mdm/dq — that's A2, done)
- **No changes to emissions app** (that's working per A0)
- **No frontend work** (that's A5)
- **No deployment config** (that's A6)
- **No admin experience work** (that's A4)
- **No schema migrations** unless absolutely necessary to fix a blocker

---

## 5. PRECONDITIONS / SETUP

1. **A0, A1, A2 complete** — repo is clean, governance RBAC fixed
2. **Backend boots** — `python manage.py check` succeeds
3. **Test users exist:**
   - facilities.officer (dataowners_group on OrgUnit=5)
   - transport.officer (dataowners_group on OrgUnit=4)
4. **Test data exists:**
   - Module 5 (Facilities - Electricity, org_unit=5)
   - DataTable 7 (belongs to module 5)
   - DataRows in table 7

---

## 6. CONSTRAINTS (MUST / MUST NOT)

### MUST:
- Test backend boots after each change (`python manage.py check`)
- Use **existing test users** (facilities.officer, transport.officer) — do NOT create new users
- Document **every curl test** with full command + response
- If fixing permissions, explain the **design rationale** (why this change aligns with strategy docs)
- Commit changes in **logical groups** (investigation, permission fix, test, doc update)

### MUST NOT:
- Break existing admin access (admins should still have full CRUD on schema+data)
- Break existing data-owner read scoping (emissions dashboard must still work)
- Change governance app permissions (catalog/mdm/dq — that's A2, done)
- Create schema migrations unless absolutely necessary

---

## 7. STEPS

### Step 1: Analyze Current DataSchema Permission Model

**Objective:** Understand how DataSchema permissions currently work.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 1.1 Review dataschema/views.py permission model
head -100 dataschema/views.py

# 1.2 Check if dataschema has its own permissions.py
cat dataschema/permissions.py 2>/dev/null || echo "No dataschema/permissions.py found"

# 1.3 Find the permission classes used by DataTable/DataField/DataRow ViewSets
grep -n "permission_classes" dataschema/views.py

# 1.4 Review the required_role for each ViewSet
grep -A 5 "required_role" dataschema/views.py

# 1.5 Check the HasScopedRole permission logic
grep -A 20 "class HasScopedRole" accounts/permissions.py
```

**Record:**
- What permission classes are used by DataTableViewSet, DataFieldViewSet, DataRowViewSet?
- What are the `required_role` values for each?
- Does `HasScopedRole` check for `dataowners_group`?
- Is there any special logic that might block data-owners?

**Analysis Questions:**
1. Should data-owners be able to read DataTable/DataField? (Answer: YES, to see schema)
2. Should data-owners be able to write DataTable/DataField? (Answer: NO, schema is admin-only)
3. Should data-owners be able to CRUD DataRows? (Answer: YES, that's their job)

---

### Step 2: Reproduce the A0 403 Error

**Objective:** Reproduce the 403 error from A0 Step 4.5 to understand why it happened.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 2.1 Get a fresh token for facilities.officer
FAC_TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"facilities.officer","password":"FacOfficer_2025"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

echo "FAC_TOKEN: ${FAC_TOKEN:0:20}..."

# 2.2 Test GET DataRows for table 7 (belongs to module 5 = facilities scope)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/rows/?data_table=7' \
  -H "Authorization: Bearer $FAC_TOKEN"

# 2.3 Test GET DataTable 7
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/tables/7/' \
  -H "Authorization: Bearer $FAC_TOKEN"

# 2.4 Test GET DataFields for table 7
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/fields/?data_table=7' \
  -H "Authorization: Bearer $FAC_TOKEN"
```

**Record:**
- Full curl output for each test (response body + HTTP code)
- Which endpoints returned 403? Which returned 200?
- If 403, what was the error message?

**Analysis:** Based on the responses, identify:
- Is the 403 coming from `HasScopedRole` permission check?
- Is it coming from queryset filtering?
- Is the `required_role` too restrictive?

---

### Step 3: Test Data-Owner Schema Read Access

**Objective:** Verify if data-owners can read schema (DataTable/DataField) in their scope.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 3.1 Test GET all DataTables (should be scoped to module 5)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/tables/?module_id=5' \
  -H "Authorization: Bearer $FAC_TOKEN"

# 3.2 Test GET specific DataTable 7
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/tables/7/' \
  -H "Authorization: Bearer $FAC_TOKEN"

# 3.3 Test GET DataFields for table 7
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/fields/?data_table=7' \
  -H "Authorization: Bearer $FAC_TOKEN"
```

**Record:**
- Full curl output for each test
- Did data-owner successfully read schema? (Expected: YES)
- If 403, what's blocking them?

**Expected Outcome:** Data-owners should be able to READ schema in their scope (to see table structure for data entry).

---

### Step 4: Test Data-Owner Schema Write Access

**Objective:** Verify that data-owners CANNOT write schema (create/update DataTable/DataField).

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 4.1 Test POST DataTable (should be blocked)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X POST 'http://localhost:8009/carbon-api/dataschema/tables/' \
  -H "Authorization: Bearer $FAC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Table","module":5,"table_type":"activity"}'

# 4.2 Test PATCH DataTable 7 (should be blocked)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X PATCH 'http://localhost:8009/carbon-api/dataschema/tables/7/' \
  -H "Authorization: Bearer $FAC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"description":"Updated by data-owner"}'

# 4.3 Test POST DataField (should be blocked)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X POST 'http://localhost:8009/carbon-api/dataschema/fields/' \
  -H "Authorization: Bearer $FAC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"field_name":"test_field","data_table":7,"field_type":"text"}'
```

**Record:**
- Full curl output for each test
- Did all write attempts return 403? (Expected: YES)
- If any succeeded, that's a bug (schema should be admin-only)

**Expected Outcome:** Data-owners should be BLOCKED from writing schema (403 Forbidden).

---

### Step 5: Test Data-Owner DataRow CRUD Access

**Objective:** Verify that data-owners CAN CRUD DataRows in their scope.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 5.1 Test GET DataRows for table 7 (should succeed)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/rows/?data_table=7' \
  -H "Authorization: Bearer $FAC_TOKEN"

# 5.2 Test POST DataRow (create new row)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X POST 'http://localhost:8009/carbon-api/dataschema/rows/' \
  -H "Authorization: Bearer $FAC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data_table":7,"row_data":{"test_field":"test_value"},"period":"2026-01"}'

# 5.3 Get the created row ID from the response, then test PATCH
# (Replace ROW_ID with actual ID from step 5.2 response)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X PATCH 'http://localhost:8009/carbon-api/dataschema/rows/ROW_ID/' \
  -H "Authorization: Bearer $FAC_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"row_data":{"test_field":"updated_value"}}'

# 5.4 Test DELETE DataRow
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X DELETE 'http://localhost:8009/carbon-api/dataschema/rows/ROW_ID/' \
  -H "Authorization: Bearer $FAC_TOKEN"
```

**Record:**
- Full curl output for each test
- Did GET succeed? (Expected: YES)
- Did POST succeed? (Expected: YES)
- Did PATCH succeed? (Expected: YES)
- Did DELETE succeed? (Expected: YES)
- If any failed with 403, that's the bug we need to fix

**Expected Outcome:** Data-owners should have full CRUD access to DataRows in their scope.

---

### Step 6: Investigate Permission Gaps (If Any)

**Objective:** If Step 5 revealed 403 errors, investigate and fix the permission model.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 6.1 Review the DataRowViewSet permission logic
grep -A 30 "class DataRowViewSet" dataschema/views.py

# 6.2 Check if HasScopedRole is blocking data-owners
# Review the has_permission method
grep -A 40 "def has_permission" accounts/permissions.py

# 6.3 Check if get_queryset is filtering correctly
# Review the get_queryset method in DataRowViewSet
grep -A 20 "def get_queryset" dataschema/views.py | grep -A 20 "DataRowViewSet" -B 5
```

**Analysis:**
- Is `required_role` for DataRowViewSet including `dataowners_group`?
- Is `HasScopedRole` checking for `dataowners_group` correctly?
- Is `get_queryset` filtering by allowed modules correctly?

**If Fix Needed:**
1. Identify the exact issue (permission check vs queryset filtering)
2. Make the minimal change to fix it
3. Test backend boots (`python manage.py check`)
4. Re-run Step 5 tests to verify fix
5. Commit with clear message

**Record:**
- What was the root cause?
- What change was made?
- Did the fix work?

---

### Step 7: Test Cross-Scope Isolation

**Objective:** Verify that data-owners CANNOT access DataRows outside their scope.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 7.1 Get token for transport.officer (org_unit=4, different from facilities)
TRANS_TOKEN=$(curl -s -X POST http://localhost:8009/carbon-api/token/ \
  -H "Content-Type: application/json" \
  -d '{"username":"transport.officer","password":"TransOfficer_2025"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access'])")

# 7.2 Test if transport.officer can access table 7 (belongs to facilities, org 5)
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/rows/?data_table=7' \
  -H "Authorization: Bearer $TRANS_TOKEN"

# 7.3 Test if transport.officer can access DataTable 7
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  'http://localhost:8009/carbon-api/dataschema/tables/7/' \
  -H "Authorization: Bearer $TRANS_TOKEN"
```

**Record:**
- Full curl output for each test
- Did transport.officer get 403 or empty results? (Expected: YES, blocked or empty)
- If they saw facilities data, that's a scoping bug

**Expected Outcome:** Cross-scope data leakage should be prevented (transport cannot see facilities data).

---

### Step 8: Test Bulk Upsert (If Endpoint Exists)

**Objective:** Check if data-owners can bulk upsert DataRows via CSV upload.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 8.1 Check if bulk upsert endpoint exists
grep -rn "bulk" dataschema/views.py dataschema/urls.py

# 8.2 Check if there's a CSV upload endpoint
grep -rn "upload\|import\|csv" dataschema/views.py dataschema/urls.py

# 8.3 List all dataschema URLs
cat dataschema/urls.py
```

**Record:**
- Does a bulk upsert endpoint exist? (Yes/No)
- If yes, what's the URL pattern?
- If no, note that this is a missing feature (not a blocker for A3)

**If Endpoint Exists:**
```bash
# 8.4 Create a test CSV file
cat > /tmp/test_upload.csv << 'EOF'
field1,field2,field3
value1,value2,value3
value4,value5,value6
EOF

# 8.5 Test CSV upload
curl -s -w '\nHTTP_CODE: %{http_code}\n' \
  -X POST 'http://localhost:8009/carbon-api/dataschema/BULK_ENDPOINT/' \
  -H "Authorization: Bearer $FAC_TOKEN" \
  -F "file=@/tmp/test_upload.csv" \
  -F "data_table=7"
```

**Record:**
- Full curl output
- Did upload succeed? (Expected: YES if endpoint exists)
- If 403, investigate permission issue

---

### Step 9: Document Findings and Recommendations

**Objective:** Summarize the data-owner experience and any gaps found.

**Commands:**
```bash
cd /home/ahmed/aast/carbon

# 9.1 Review the design doc to confirm expected behavior
grep -A 20 "dataowners_group" docs/DESIGN_ORG_ACCESS_MODEL.md

# 9.2 Create a summary of findings
```

**Document in TASK-RESULT-A3.md:**
1. **Current State:** What works, what doesn't
2. **Permission Model:** How DataSchema permissions are structured
3. **Gaps Found:** Any 403 errors that shouldn't happen
4. **Fixes Applied:** What was changed and why
5. **Remaining Gaps:** Any missing features (e.g., bulk upsert endpoint)
6. **Recommendations:** What should be done in future RUNs

---

### Step 10: Final Verification

**Objective:** Confirm backend boots, all tests pass, and git is clean.

**Commands:**
```bash
cd /home/ahmed/aast/carbon/backend

# 10.1 Test backend boots
python manage.py check

# 10.2 Re-run key tests from Steps 3, 4, 5, 7
# (Paste the successful test commands here)

# 10.3 Check git status
cd ..
git status

# 10.4 Review commit history
git log --oneline -10
```

**Record:**
- `manage.py check` output
- Test results (confirm all pass)
- `git status` output
- Last 10 commit hashes

---

## 8. ACCEPTANCE CRITERIA

| # | Criterion | Pass Threshold | Status | Evidence Ref |
|---|-----------|----------------|--------|--------------|
| AC1 | Permission model analyzed | Documented how DataTable/DataField/DataRow permissions work | | Step 1 |
| AC2 | A0 403 error reproduced | Reproduced the 403 from A0 Step 4.5 | | Step 2 |
| AC3 | Schema read access verified | Data-owner can read DataTable/DataField in their scope | | Step 3 |
| AC4 | Schema write blocked | Data-owner cannot create/update DataTable/DataField (403) | | Step 4 |
| AC5 | DataRow CRUD works | Data-owner can GET/POST/PATCH/DELETE DataRows in their scope | | Step 5 |
| AC6 | Permission gaps fixed | If 403 errors found, root cause identified and fixed | | Step 6 |
| AC7 | Cross-scope isolation | Data-owner cannot access DataRows outside their scope | | Step 7 |
| AC8 | Bulk upsert investigated | Documented whether bulk upsert endpoint exists and works | | Step 8 |
| AC9 | Backend boots | `manage.py check` exit 0 after all changes | | Step 10 |
| AC10 | Findings documented | TASK-RESULT-A3.md has complete analysis and recommendations | | Step 9, 10 |

**Worker: fill the "Status" column with PASS/FAIL and reference the step where evidence is found.**

---

## 9. DELIVERABLE FORMAT

**File:** `TASK-RESULT-A3.md`

**Required structure:**

```markdown
# TASK-RESULT-A3.md — RUN A3: Data-Owner Scoped Experience

## Summary
[One paragraph: what was investigated, what was found, what was fixed]

## Blockers
[List any blockers encountered, or state "None"]

## Step 1: Analyze Current DataSchema Permission Model
**Commands:**
[paste commands]

**Output:**
[paste raw output]

**Analysis:**
[answer the analysis questions]

## Step 2: Reproduce the A0 403 Error
[same structure - paste full curl outputs]

## Step 3: Test Data-Owner Schema Read Access
[same structure]

## Step 4: Test Data-Owner Schema Write Access
[same structure]

## Step 5: Test Data-Owner DataRow CRUD Access
[same structure - this is the critical test]

## Step 6: Investigate Permission Gaps (If Any)
[same structure - document root cause and fix if needed]

## Step 7: Test Cross-Scope Isolation
[same structure]

## Step 8: Test Bulk Upsert (If Endpoint Exists)
[same structure]

## Step 9: Document Findings and Recommendations
**Current State:**
[what works]

**Permission Model:**
[how it's structured]

**Gaps Found:**
[list any issues]

**Fixes Applied:**
[what was changed]

**Remaining Gaps:**
[missing features]

**Recommendations:**
[what should be done next]

## Step 10: Final Verification
[same structure]

## Acceptance Criteria Table
[Copy the AC table from TASK.md, fill Status column with PASS/FAIL + evidence refs]

## Git Commit Summary
[List all commits with hashes and messages, if any changes were made]

## Test Results Summary
[Summarize: which tests passed, what was proven, what was fixed]

## Definition of Done Status
[Explicit statement: "DoD met" or "DoD not met because..."]

## Final Git Status
```
[paste output of `git status`]
```
```

---

## 10. DEFINITION OF DONE

- All 10 acceptance criteria filled with PASS or documented as N/A
- Backend boots cleanly (`manage.py check` exit 0)
- Data-owner can read schema in their scope (AC3 PASS)
- Data-owner cannot write schema (AC4 PASS)
- Data-owner can CRUD DataRows in their scope (AC5 PASS) **← CRITICAL**
- Cross-scope isolation verified (AC7 PASS)
- If permission gaps found, they are fixed or documented as future work
- `TASK-RESULT-A3.md` returned with all required sections
- **Gate:** A3 completion unblocks A4 (Admin experience)

---

## 11. ESCALATION

**If blocked:**
1. Stop the blocked step immediately
2. Mark it `BLOCKED: <specific reason>` in the result
3. Continue with remaining independent steps
4. Summarize all blockers at the top of `TASK-RESULT-A3.md`
5. Never guess, assume, or fabricate missing information

**If test fails:** Paste the full error, mark the step BLOCKED, explain what was expected vs actual.

**If backend breaks:** Revert the change, mark the step BLOCKED, report the error.

**If permission logic is unclear:** Mark it `BLOCKED: unclear permission model`, explain why, continue with other tests.

---

**END OF TASK.md — RUN A3**

**Worker (Raptor):** Execute this RUN and return `TASK-RESULT-A3.md`. This is an investigation + fix RUN. Focus on Step 5 (DataRow CRUD) — that's the critical test. Good luck.
