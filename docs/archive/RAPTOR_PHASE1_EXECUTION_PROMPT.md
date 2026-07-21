# RAPTOR EXECUTION PROMPT: RUN A9 - PHASE 1 (Backend Bulk Import API)

## Context

You are Raptor, the autonomous execution agent. RUN A9 (Bulk Import/Export) Phase 1 backend implementation has been partially completed:

**✅ COMPLETED:**
- Added imports to [`backend/dataschema/views.py`](backend/dataschema/views.py:1): pandas, json, io, Response, action, status, HttpResponse
- Added [`bulk_import()`](backend/dataschema/views.py:134) custom action to DataRowViewSet (CSV/Excel parsing, validation, bulk create)
- Added [`download_template()`](backend/dataschema/views.py:268) custom action to DataRowViewSet (CSV template generation)
- Created [`backend/dataschema/tests/test_bulk_import.py`](backend/dataschema/tests/test_bulk_import.py:1) with 9 test cases

**❌ PENDING:**
- Run backend tests and verify all pass
- Fix any test failures
- Perform manual cURL testing
- Verify endpoints are accessible

---

## Your Task

Execute the remaining Phase 1 verification tasks following the step-by-step checklist below.

---

## Step 1: Verify pandas Installation

**Command:**
```bash
cd backend && python -c "import pandas; print(f'pandas version: {pandas.__version__}')"
```

**Expected Output:**
```
pandas version: 2.3.0
```

**If pandas not installed:**
```bash
cd backend && pip install pandas==2.3.0
```

---

## Step 2: Run Backend Tests

**Command:**
```bash
cd backend && python manage.py test dataschema.tests.test_bulk_import --verbosity=2
```

**Expected Output:**
- All 9 tests should PASS:
  - `test_bulk_import_csv_success`
  - `test_bulk_import_with_column_mapping`
  - `test_bulk_import_validation_errors`
  - `test_bulk_import_invalid_file_type`
  - `test_download_template`
  - `test_download_template_with_example`
  - `test_bulk_import_missing_file`
  - `test_bulk_import_missing_table_id`

**If tests fail:**
1. Read error messages carefully
2. Check if fixtures are properly set up (User, Organization, Module, DataTable, DataField)
3. Verify DataRowSerializer validation logic in [`backend/dataschema/serializers.py`](backend/dataschema/serializers.py:58-105)
4. Check if bulk_import and download_template actions are properly registered
5. Fix issues and re-run tests

---

## Step 3: Start Django Development Server

**Command:**
```bash
cd backend && python manage.py runserver 0.0.0.0:8009
```

**Keep server running in background for manual testing.**

---

## Step 4: Get Authentication Token

**Command:**
```bash
curl -X POST http://localhost:8009/accounts/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

**Expected Response:**
```json
{
  "token": "abc123...",
  "user": { ... }
}
```

**Save the token for next steps.**

---

## Step 5: Manual Test - Download Template (Without Example)

**Prerequisites:**
- Get a valid `table_id` from existing DataTable (use Django shell or admin panel)
- Replace `{token}` with authentication token from Step 4
- Replace `{table_id}` with actual table ID

**Command:**
```bash
curl -X GET "http://localhost:8009/carbon-api/datarows/download-template/?data_table={table_id}" \
  -H "Authorization: Token {token}" \
  -o template.csv
```

**Verify:**
```bash
cat template.csv
```

**Expected:**
- CSV file with field names as headers (e.g., `"date","distance","fuel_type"`)
- No example row (only header)

---

## Step 6: Manual Test - Download Template (With Example)

**Command:**
```bash
curl -X GET "http://localhost:8009/carbon-api/datarows/download-template/?data_table={table_id}&include_example=true" \
  -H "Authorization: Token {token}" \
  -o template_with_example.csv
```

**Verify:**
```bash
cat template_with_example.csv
```

**Expected:**
- CSV file with field names as headers
- Second line with example values (e.g., `"example text",123,"diesel"`)

---

## Step 7: Manual Test - Bulk Import CSV (Success Case)

**Create test CSV file:**
```bash
cat > test_import.csv << 'EOF'
date,distance,fuel_type
2026-01-01,100,diesel
2026-01-02,150,gasoline
2026-01-03,200,diesel
EOF
```

**Upload CSV:**
```bash
curl -X POST http://localhost:8009/carbon-api/datarows/bulk-import/ \
  -H "Authorization: Token {token}" \
  -F "file=@test_import.csv" \
  -F "data_table={table_id}" \
  -F "mode=create"
```

**Expected Response:**
```json
{
  "created": 3,
  "failed": 0,
  "errors": []
}
```

---

## Step 8: Manual Test - Bulk Import with Column Mapping

**Create CSV with different headers:**
```bash
cat > test_mapping.csv << 'EOF'
Date,Dist,Fuel
2026-01-04,50,gasoline
2026-01-05,75,diesel
EOF
```

**Upload with column mapping:**
```bash
curl -X POST http://localhost:8009/carbon-api/datarows/bulk-import/ \
  -H "Authorization: Token {token}" \
  -F "file=@test_mapping.csv" \
  -F "data_table={table_id}" \
  -F 'column_mapping={"Date":"date","Dist":"distance","Fuel":"fuel_type"}' \
  -F "mode=create"
```

**Expected Response:**
```json
{
  "created": 2,
  "failed": 0,
  "errors": []
}
```

---

## Step 9: Manual Test - Validation Error (Missing Required Field)

**Create CSV missing required 'date' field:**
```bash
cat > test_error.csv << 'EOF'
distance,fuel_type
100,diesel
150,gasoline
EOF
```

**Upload:**
```bash
curl -X POST http://localhost:8009/carbon-api/datarows/bulk-import/ \
  -H "Authorization: Token {token}" \
  -F "file=@test_error.csv" \
  -F "data_table={table_id}" \
  -F "mode=create"
```

**Expected Response:**
```json
{
  "created": 0,
  "failed": 2,
  "errors": [
    {
      "row": 2,
      "data": {"distance": 100, "fuel_type": "diesel"},
      "error": "... required ..."
    },
    {
      "row": 3,
      "data": {"distance": 150, "fuel_type": "gasoline"},
      "error": "... required ..."
    }
  ]
}
```

---

## Step 10: Manual Test - Invalid File Type

**Create invalid file:**
```bash
echo "not a csv" > test.txt
```

**Upload:**
```bash
curl -X POST http://localhost:8009/carbon-api/datarows/bulk-import/ \
  -H "Authorization: Token {token}" \
  -F "file=@test.txt" \
  -F "data_table={table_id}" \
  -F "mode=create"
```

**Expected Response:**
```json
{
  "error": "File must be CSV (.csv) or Excel (.xlsx, .xls)"
}
```

**Status Code:** 400

---

## Step 11: Verify Database Rows Created

**Django Shell:**
```bash
cd backend && python manage.py shell
```

**Python Commands:**
```python
from dataschema.models import DataRow
table_id = YOUR_TABLE_ID  # Replace with actual ID
rows = DataRow.objects.filter(data_table_id=table_id, is_archived=False)
print(f"Total rows: {rows.count()}")
for row in rows[:5]:
    print(f"Row ID: {row.id}, Values: {row.values}")
```

**Expected:**
- Rows from Step 7 and Step 8 should be present (5 total)
- Each row should have `values` dict with date, distance, fuel_type

---

## Step 12: Check Django Logs for Errors

**Review server logs:**
- Look for any ERROR or WARNING messages
- Verify no exceptions during file upload/parsing
- Confirm successful row creation logs

**Expected:**
- No errors related to bulk_import or download_template
- HTTP 200 responses for successful imports
- HTTP 400 for validation errors (expected behavior)

---

## Acceptance Criteria Checklist

Before marking Phase 1 complete, verify ALL criteria:

- [ ] `bulk_import()` action added to DataRowViewSet ✅ (already done)
- [ ] `download_template()` action added to DataRowViewSet ✅ (already done)
- [ ] CSV parsing works (pandas) - verify in Step 7
- [ ] Excel parsing works (.xlsx, .xls) - verify by creating .xlsx test file
- [ ] Column mapping applies correctly - verify in Step 8
- [ ] Row validation uses DataRowSerializer - verify in Step 9
- [ ] Bulk row creation works - verify in Step 7
- [ ] Created rows have `created_by` set to request user - verify in Step 11
- [ ] Detailed error reporting (row number, data, error message) - verify in Step 9
- [ ] Template generation returns CSV with field names - verify in Step 5
- [ ] Template includes example row when `include_example=true` - verify in Step 6
- [ ] Backend tests pass (9 tests) - verify in Step 2
- [ ] Manual cURL tests successful - verify in Steps 5-10

**Total: 13 Acceptance Criteria**

---

## Troubleshooting Guide

### Issue: Tests fail with "Module not found: pandas"
**Solution:**
```bash
cd backend && pip install pandas==2.3.0
```

### Issue: Tests fail with "DataTable matching query does not exist"
**Solution:**
- Fixtures in test file create test data (User, Organization, Module, DataTable)
- Ensure `setup_data` fixture runs before each test
- Check if pytest-django is installed: `pip install pytest-django`

### Issue: 403 Forbidden on API requests
**Solution:**
- Verify authentication token is valid
- Check RBAC permissions in [`backend/dataschema/views.py`](backend/dataschema/views.py:104)
- DataRowViewSet requires role: admin, admins_group, auditors_group, or dataowners_group
- Create test user with appropriate role

### Issue: 404 Not Found on /carbon-api/datarows/bulk-import/
**Solution:**
- Verify router registration in [`backend/dataschema/urls.py`](backend/dataschema/urls.py:1)
- Custom actions auto-register via DRF DefaultRouter
- Check if `@action` decorator is correct in views.py

### Issue: CSV parsing fails with encoding error
**Solution:**
- Ensure CSV is UTF-8 encoded
- Test with simple ASCII characters first
- pandas read_csv handles most encoding issues automatically

### Issue: Validation errors for valid data
**Solution:**
- Check DataRowSerializer logic in [`backend/dataschema/serializers.py`](backend/dataschema/serializers.py:58-105)
- Verify field types match (string, number, date, boolean, select)
- Check required field constraints in DataField model

---

## Deliverables

Once all steps complete successfully, create:

### 1. Test Results Report

Create file: `PHASE1_A9_TEST_RESULTS.md`

```markdown
# PHASE 1 - Backend Bulk Import API Test Results

## Backend Tests (9/9 PASS)
- ✅ test_bulk_import_csv_success
- ✅ test_bulk_import_with_column_mapping
- ✅ test_bulk_import_validation_errors
- ✅ test_bulk_import_invalid_file_type
- ✅ test_download_template
- ✅ test_download_template_with_example
- ✅ test_bulk_import_missing_file
- ✅ test_bulk_import_missing_table_id

## Manual cURL Tests (6/6 PASS)
- ✅ Download template (without example)
- ✅ Download template (with example)
- ✅ Bulk import CSV (success case)
- ✅ Bulk import with column mapping
- ✅ Validation error (missing required field)
- ✅ Invalid file type error

## Acceptance Criteria (13/13 ✅)
[List all 13 criteria with checkmarks]

## Files Modified
- backend/dataschema/views.py (added 2 custom actions)
- backend/dataschema/tests/test_bulk_import.py (created, 9 tests)

## Known Issues
[List any issues encountered and how they were resolved]

## Next Steps
- Proceed to Phase 2: Frontend Import Wizard Component
```

### 2. Git Commit

```bash
git add backend/dataschema/views.py
git add backend/dataschema/tests/test_bulk_import.py
git commit -m "feat(A9-P1): Backend bulk import API

- Add bulk_import() custom action to DataRowViewSet
  - CSV/Excel parsing with pandas
  - Column mapping support
  - Row validation via DataRowSerializer
  - Bulk row creation with error reporting
- Add download_template() custom action
  - CSV template generation with field headers
  - Optional example row
- Add 9 backend tests (all passing)
  - Test CSV import success
  - Test column mapping
  - Test validation errors
  - Test template generation

Phase 1/5 complete. Next: Frontend wizard component.

Relates-to: RUN-A9"
```

---

## Success Criteria

Phase 1 is complete when:

1. ✅ All backend code added (views.py, tests/test_bulk_import.py)
2. ⏳ All 9 backend tests PASS
3. ⏳ All 6 manual cURL tests successful
4. ⏳ All 13 acceptance criteria met
5. ⏳ Test results report created (PHASE1_A9_TEST_RESULTS.md)
6. ⏳ Git commit completed
7. ⏳ No errors in Django logs

**You are now ready to proceed to Phase 2: Frontend Import Wizard Component.**

---

## Notes for Raptor

- Follow each step sequentially - don't skip verification steps
- If any test fails, investigate and fix before proceeding
- Document all issues and resolutions in test results report
- Use actual table_id from your database (not placeholder)
- Keep Django server running during manual tests
- Clean up test CSV files after completion
- Verify created rows in database match imported CSV data

**Good luck with Phase 1 execution! 🚀**
