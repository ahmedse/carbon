# TASK A9 - PHASE 4: Testing & Validation

**Phase:** 4 of 5  
**Focus:** Comprehensive Testing - Backend, Frontend, Integration  
**Duration:** Step-by-step execution

---

## Objective

Execute comprehensive testing of the bulk import/export feature across backend API, frontend components, and end-to-end integration. Achieve 100% test pass rate and verify all acceptance criteria.

---

## Scope - IN

✅ Backend API tests (bulk import, template, validation)  
✅ Frontend component tests (BulkImportWizard)  
✅ Integration tests (end-to-end import flow)  
✅ Browser testing (manual verification)  
✅ Error handling verification  
✅ RBAC enforcement testing  
✅ Build verification

---

## Scope - OUT

❌ Performance/load testing  
❌ Security penetration testing  
❌ Accessibility (a11y) testing  
❌ Cross-browser compatibility testing

---

## Testing Strategy

### Backend Tests (7 tests)
1. Bulk import CSV success
2. Bulk import with column mapping
3. Bulk import validation errors
4. Bulk import invalid file type
5. Download template
6. Download template with example
7. RBAC enforcement (dataowners_group)

### Frontend Tests (5 tests)
1. Component renders upload step
2. Component shows stepper
3. File upload triggers parsing
4. Column mapping renders
5. Validation preview renders

### Integration Tests (4 tests)
1. End-to-end import flow
2. Template download flow
3. Import completion refreshes table
4. Error handling displays correctly

### Browser Tests (Manual)
1. Import button opens modal
2. Template button downloads file
3. CSV upload → mapping → validation → import
4. Success notification appears
5. Table refreshes with new data

---

## Implementation Steps

### Step 1: Run Backend Tests

**File:** `backend/dataschema/tests/test_bulk_import.py` (created in Phase 1)

**Command:**

```bash
cd backend
python manage.py test dataschema.tests.test_bulk_import
```

**Expected Output:**

```
Creating test database for alias 'default'...
System check identified no issues (0 silenced).
.......
----------------------------------------------------------------------
Ran 7 tests in X.XXXs

OK
```

**Verification:**
- [ ] All 7 tests PASS
- [ ] No errors or failures
- [ ] Test coverage includes:
  - [ ] Bulk import CSV success
  - [ ] Column mapping
  - [ ] Validation errors
  - [ ] Invalid file type
  - [ ] Template download
  - [ ] Template with example
  - [ ] (RBAC test if added)

---

### Step 2: Run Frontend Tests

**File:** `carbon-frontend/src/components/import/BulkImportWizard.test.jsx` (created in Phase 2)

**Command:**

```bash
cd carbon-frontend
npm run test
```

**Expected Output:**

```
 ✓ carbon-frontend/src/components/import/BulkImportWizard.test.jsx (3)
   ✓ BulkImportWizard (3)
     ✓ renders upload step initially
     ✓ shows stepper with 3 steps
     ✓ cancel button closes dialog

 Test Files  1 passed (1)
      Tests  3 passed (3)
```

**Verification:**
- [ ] All 3 tests PASS
- [ ] No errors or warnings
- [ ] Test coverage includes:
  - [ ] Component renders
  - [ ] Stepper displays
  - [ ] Cancel button works

---

### Step 3: Frontend Build Verification

**Command:**

```bash
cd carbon-frontend
npm run build
```

**Expected Output:**

```
vite v5.x.x building for production...
✓ XXXX modules transformed.
dist/index.html                   X.XX kB
dist/assets/index-XXXXXXXX.js     X.XX MB
✓ built in X.XXs
```

**Verification:**
- [ ] Build completes successfully
- [ ] No TypeScript errors
- [ ] No linting errors
- [ ] Bundle size reasonable (< 2MB)

---

### Step 4: Integration Test - Template Download

**Test Case:** Download CSV template for a table

**Steps:**

1. **Setup:**
   - Backend running: `python manage.py runserver 0.0.0.0:8009`
   - Login and get token
   - Know a table ID (e.g., from /carbon-api/data-tables/)

2. **Execute:**
   ```bash
   curl -X GET "http://localhost:8009/carbon-api/datarows/download-template/?data_table={table_id}" \
     -H "Authorization: Token {your_token}" \
     -o template.csv
   ```

3. **Verify:**
   ```bash
   cat template.csv
   # Should show CSV headers matching table fields
   ```

**Expected Result:**
- [ ] HTTP 200 response
- [ ] template.csv downloaded
- [ ] CSV contains field names as headers
- [ ] Headers match table schema

---

### Step 5: Integration Test - Bulk Import

**Test Case:** Upload CSV file and import rows

**Steps:**

1. **Prepare Test CSV:**
   ```bash
   echo "date,distance,fuel_type" > test_data.csv
   echo "2026-01-15,120,diesel" >> test_data.csv
   echo "2026-01-16,95,gasoline" >> test_data.csv
   ```

2. **Execute:**
   ```bash
   curl -X POST "http://localhost:8009/carbon-api/datarows/bulk-import/" \
     -H "Authorization: Token {your_token}" \
     -F "file=@test_data.csv" \
     -F "data_table={table_id}" \
     -F "mode=create"
   ```

3. **Verify Response:**
   ```json
   {
     "created": 2,
     "failed": 0,
     "errors": []
   }
   ```

4. **Verify Database:**
   ```bash
   curl -X GET "http://localhost:8009/carbon-api/datarows/?data_table={table_id}" \
     -H "Authorization: Token {your_token}"
   ```

**Expected Result:**
- [ ] HTTP 200 response
- [ ] `created: 2` in response
- [ ] `failed: 0` in response
- [ ] Rows visible in database
- [ ] Row values match CSV data

---

### Step 6: Integration Test - Validation Errors

**Test Case:** Upload CSV with invalid data

**Steps:**

1. **Prepare Invalid CSV (missing required field):**
   ```bash
   echo "distance,fuel_type" > invalid_data.csv
   echo "120,diesel" >> invalid_data.csv
   ```

2. **Execute:**
   ```bash
   curl -X POST "http://localhost:8009/carbon-api/datarows/bulk-import/" \
     -H "Authorization: Token {your_token}" \
     -F "file=@invalid_data.csv" \
     -F "data_table={table_id}" \
     -F "mode=create"
   ```

3. **Verify Response:**
   ```json
   {
     "created": 0,
     "failed": 1,
     "errors": [
       {
         "row": 2,
         "data": {"distance": "120", "fuel_type": "diesel"},
         "error": "{'date': 'This field is required.'}"
       }
     ]
   }
   ```

**Expected Result:**
- [ ] HTTP 200 response
- [ ] `created: 0` in response
- [ ] `failed: 1` in response
- [ ] Error details include row number and message
- [ ] No rows created in database

---

### Step 7: Browser Testing - Import Flow

**Test Case:** Complete import flow in browser

**Steps:**

1. **Navigate to Data Entry:**
   - Open browser: http://localhost:5179
   - Login
   - Go to Data Hub → Data Entry
   - Select a module and table

2. **Download Template:**
   - Click "Template" button
   - Verify download starts
   - Open template.csv
   - Verify headers are correct

3. **Fill Template:**
   - Add 3 rows of test data
   - Save as `my_import.csv`

4. **Import Data:**
   - Click "Import" button
   - Verify modal opens with stepper
   - Drag & drop `my_import.csv` onto upload zone
   - Verify "Next" button enabled
   - Click "Next"

5. **Column Mapping:**
   - Verify auto-mapping shows correct mappings
   - Verify all columns mapped
   - Click "Next"

6. **Validation Preview:**
   - Verify "X rows valid" message
   - Verify no errors (or expected errors)
   - Click "Import"

7. **Completion:**
   - Verify success notification appears
   - Verify notification says "X rows created"
   - Verify table refreshes
   - Verify new rows visible in grid

**Expected Result:**
- [ ] Template button downloads CSV
- [ ] Import button opens modal
- [ ] File upload works (drag-and-drop)
- [ ] Auto-mapping works
- [ ] Validation preview shows results
- [ ] Import button enabled when valid
- [ ] Import succeeds
- [ ] Notification displays
- [ ] Table refreshes
- [ ] New rows visible

---

### Step 8: Browser Testing - Error Handling

**Test Case:** Import with validation errors

**Steps:**

1. **Prepare Invalid CSV:**
   - Create CSV with missing required field
   - Or invalid data type (text in number field)

2. **Import:**
   - Click "Import" button
   - Upload invalid CSV
   - Proceed through mapping

3. **Validation Preview:**
   - Verify error count displayed
   - Verify error details shown
   - Verify "Import only valid rows" checkbox
   - Click "Import" (if any valid rows)

4. **Completion:**
   - Verify warning notification (partial success)
   - Or error notification (all failed)
   - Verify table refreshes
   - Verify only valid rows created

**Expected Result:**
- [ ] Validation errors displayed clearly
- [ ] Error count accurate
- [ ] Error details include row numbers
- [ ] Checkbox option to import only valid rows
- [ ] Partial import works
- [ ] Notification reflects partial success

---

### Step 9: Console Error Check

**Test Case:** Verify no console errors

**Steps:**

1. Open browser DevTools (F12)
2. Go to Console tab
3. Clear console
4. Perform import flow (Step 7)
5. Check for errors

**Expected Result:**
- [ ] No red error messages in console
- [ ] No network errors (400, 500) in Network tab
- [ ] Warnings about Pulse are OK (known issue)

---

### Step 10: RBAC Verification (Optional)

**Test Case:** Verify RBAC enforcement

**Steps:**

1. **Login as Data Owner (non-admin):**
   - User assigned to specific module

2. **Try to Import to Allowed Module:**
   - Navigate to assigned module
   - Click Import
   - Upload CSV
   - Verify import succeeds

3. **Try to Import to Restricted Module:**
   - Navigate to module NOT assigned
   - Verify Import button present (UI doesn't hide it)
   - Try to import
   - Verify backend returns 403 Forbidden

**Expected Result:**
- [ ] Data owners can import to assigned modules
- [ ] Data owners cannot import to restricted modules
- [ ] Admins can import to all modules

---

## Test Results Summary Template

**Create file:** `PHASE4_A9_TEST_RESULTS.md`

```markdown
# Phase 4 Test Results: RUN A9 Bulk Import/Export

**Date:** 2026-07-18  
**Status:** [PASS/FAIL]

---

## Backend API Tests (7 tests)

| # | Test | Status | Details |
|---|------|--------|---------|
| 1 | Bulk import CSV success | ✅ PASS | 2 rows created |
| 2 | Column mapping | ✅ PASS | Mapping applied correctly |
| 3 | Validation errors | ✅ PASS | Error details returned |
| 4 | Invalid file type | ✅ PASS | 400 error returned |
| 5 | Template download | ✅ PASS | CSV generated |
| 6 | Template with example | ✅ PASS | Example row included |
| 7 | RBAC enforcement | ✅ PASS | 403 for unauthorized access |

**Backend Tests: 7/7 PASS (100%)**

---

## Frontend Component Tests (3 tests)

| # | Test | Status | Details |
|---|------|--------|---------|
| 1 | Renders upload step | ✅ PASS | Component displays |
| 2 | Shows stepper | ✅ PASS | 3 steps visible |
| 3 | Cancel button works | ✅ PASS | Modal closes |

**Frontend Tests: 3/3 PASS (100%)**

---

## Integration Tests (4 tests)

| # | Test | Status | Details |
|---|------|--------|---------|
| 1 | Template download | ✅ PASS | CSV downloaded via cURL |
| 2 | Bulk import | ✅ PASS | 2 rows created via cURL |
| 3 | Validation errors | ✅ PASS | Errors returned correctly |
| 4 | RBAC enforcement | ✅ PASS | Forbidden for wrong module |

**Integration Tests: 4/4 PASS (100%)**

---

## Browser Tests (Manual)

| # | Test | Status | Details |
|---|------|--------|---------|
| 1 | Import button opens modal | ✅ PASS | Modal displays |
| 2 | Template download | ✅ PASS | File downloaded |
| 3 | File upload | ✅ PASS | Drag-and-drop works |
| 4 | Column mapping | ✅ PASS | Auto-mapping works |
| 5 | Validation preview | ✅ PASS | Valid/error counts shown |
| 6 | Import succeeds | ✅ PASS | Rows created |
| 7 | Notification displays | ✅ PASS | Success message shown |
| 8 | Table refreshes | ✅ PASS | New rows visible |
| 9 | Error handling | ✅ PASS | Errors displayed clearly |
| 10 | No console errors | ✅ PASS | Console clean |

**Browser Tests: 10/10 PASS (100%)**

---

## Build Verification

| Check | Status | Details |
|-------|--------|---------|
| Backend tests pass | ✅ PASS | 7/7 tests |
| Frontend tests pass | ✅ PASS | 3/3 tests |
| Frontend builds | ✅ PASS | No errors |
| No console errors | ✅ PASS | DevTools clean |
| API accessible | ✅ PASS | All endpoints responding |

---

## Overall Results

**Total Tests: 24**  
**Passed: 24**  
**Failed: 0**  
**Pass Rate: 100%**

**Status: ✅ ALL TESTS PASS**

---

## Notes

- All 28 acceptance criteria from TASK-A9 met
- No critical issues identified
- Ready for Phase 5 (Documentation)
```

---

## Acceptance Criteria

- [ ] Backend tests run and pass (7/7)
- [ ] Frontend tests run and pass (3/3)
- [ ] Integration tests pass (4/4)
- [ ] Browser tests pass (10/10)
- [ ] Frontend builds without errors
- [ ] No console errors in browser
- [ ] Template download works (cURL + browser)
- [ ] Bulk import works (cURL + browser)
- [ ] Validation errors display correctly
- [ ] RBAC enforced (403 for unauthorized)
- [ ] Table refresh works after import
- [ ] Notifications display correctly
- [ ] Test results documented

**Total: 13 Acceptance Criteria**

---

## Verification Checklist

Before proceeding to Phase 5:

- [ ] Run backend tests: `python manage.py test dataschema.tests.test_bulk_import`
- [ ] All backend tests PASS
- [ ] Run frontend tests: `npm run test`
- [ ] All frontend tests PASS
- [ ] Run build: `npm run build`
- [ ] Build successful (no errors)
- [ ] Template download test (cURL) PASS
- [ ] Bulk import test (cURL) PASS
- [ ] Browser testing complete (10 scenarios)
- [ ] All browser tests PASS
- [ ] Console error check PASS
- [ ] Test results documented in `PHASE4_A9_TEST_RESULTS.md`
- [ ] All 28 acceptance criteria from main plan met

---

## Next Phase

✅ Phase 4 Complete → Proceed to **Phase 5: Documentation**

Phase 5 will update `RUN_LOG.md` and create `TASK-RESULT-A9.md` with complete deliverables summary.
