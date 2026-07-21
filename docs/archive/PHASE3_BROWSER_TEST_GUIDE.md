# RUN A9 - PHASE 3: Browser Testing Guide

## Test Environment Setup

1. **Start Backend Server**
   ```bash
   ./manage.sh runserver
   ```

2. **Start Frontend Dev Server**
   ```bash
   cd carbon-frontend && npm run dev
   ```

3. **Login Credentials**
   - Data Owner: `dataowner / Aa123456`
   - Navigate to: Data Hub Studio → Select Module → Select Table

---

## Test Scenario 1: Bulk Import Button Visibility

**Objective**: Verify Import and Template buttons appear on TableDataPage

**Steps**:
1. Navigate to Data Hub Studio
2. Select any module (e.g., "Transportation")
3. Select any table (e.g., "Bus Routes")
4. Look for button toolbar above data grid

**Expected Result**:
- ✅ "Bulk Import" button with Upload icon (contained, primary)
- ✅ "Download Template" button with Download icon (outlined)
- ✅ "Evidence" button with AttachFile icon (outlined, disabled if no row selected)
- ✅ All buttons properly aligned in horizontal Box with gap

**Pass/Fail**: ___________

---

## Test Scenario 2: Download Template (No Example)

**Objective**: Download CSV template without example row

**Steps**:
1. Click "Download Template" button
2. In browser alert, click "Cancel" (no example)
3. Check Downloads folder

**Expected Result**:
- ✅ CSV file downloaded: `{table_name}_template.csv`
- ✅ File contains header row with field names
- ✅ No data rows (just headers)
- ✅ Success notification: "Template downloaded successfully."

**Pass/Fail**: ___________

---

## Test Scenario 3: Download Template (With Example)

**Objective**: Download CSV template with example row

**Steps**:
1. Click "Download Template" button
2. In browser alert, click "OK" (include example)
3. Check Downloads folder

**Expected Result**:
- ✅ CSV file downloaded: `{table_name}_template.csv`
- ✅ File contains header row with field names
- ✅ File contains example row with type-appropriate values
- ✅ Success notification: "Template downloaded successfully."

**Pass/Fail**: ___________

---

## Test Scenario 4: Open Bulk Import Wizard

**Objective**: Open BulkImportWizard modal

**Steps**:
1. Click "Bulk Import" button
2. Observe modal dialog

**Expected Result**:
- ✅ Modal opens with title "Bulk Import Data"
- ✅ Stepper shows 3 steps: "Upload File", "Map Columns", "Validation Preview"
- ✅ Step 1 is active (highlighted)
- ✅ Dropzone visible with instructions
- ✅ "Next" button disabled (no file uploaded)
- ✅ "Cancel" button enabled

**Pass/Fail**: ___________

---

## Test Scenario 5: Upload CSV File

**Objective**: Upload valid CSV file and parse headers

**Steps**:
1. Open Bulk Import Wizard
2. Drag & drop or click to select downloaded template CSV
3. Add 2-3 data rows to CSV before uploading
4. Upload file

**Expected Result**:
- ✅ File name displayed in wizard
- ✅ Success message: "File uploaded: {filename}"
- ✅ Parsed row count shown: "X rows parsed"
- ✅ "Next" button enabled
- ✅ No error messages

**Pass/Fail**: ___________

---

## Test Scenario 6: Column Mapping (Auto-Map)

**Objective**: Verify automatic column mapping

**Steps**:
1. Complete file upload (Scenario 5)
2. Click "Next" to proceed to Map Columns step
3. Observe column mapping dropdowns

**Expected Result**:
- ✅ Stepper shows Step 2 active
- ✅ CSV header columns listed on left
- ✅ Each CSV column has dropdown showing mapped field
- ✅ Auto-mapping successful for exact matches (green chip)
- ✅ Unmapped columns show "-- Not Mapped --" (orange chip)
- ✅ "Next" button enabled
- ✅ "Back" button enabled

**Pass/Fail**: ___________

---

## Test Scenario 7: Manual Column Mapping

**Objective**: Manually remap unmapped columns

**Steps**:
1. Complete auto-mapping (Scenario 6)
2. Select unmapped column dropdown
3. Choose target field from list
4. Verify mapping updated

**Expected Result**:
- ✅ Dropdown shows all table fields
- ✅ Already mapped fields marked "(already mapped)"
- ✅ Selected field updates in UI
- ✅ Chip color changes to green (mapped)
- ✅ Changes persist when navigating steps

**Pass/Fail**: ___________

---

## Test Scenario 8: Validation Preview (All Valid)

**Objective**: Preview validation results for valid data

**Steps**:
1. Complete column mapping (Scenario 6 or 7)
2. Click "Next" to proceed to Validation Preview
3. Observe validation results

**Expected Result**:
- ✅ Stepper shows Step 3 active
- ✅ Info alert: "X valid rows, 0 invalid rows"
- ✅ Preview table shows first 10 rows
- ✅ All rows have green "Valid" chip
- ✅ No error column visible
- ✅ Checkbox: "Import only valid rows" checked by default
- ✅ "Import" button enabled
- ✅ "Back" button enabled

**Pass/Fail**: ___________

---

## Test Scenario 9: Validation Preview (Mixed Valid/Invalid)

**Objective**: Preview validation with errors

**Steps**:
1. Edit CSV file to include invalid data:
   - Missing required field
   - Wrong data type (text in number field)
   - Invalid select option
2. Upload edited CSV
3. Complete mapping
4. Proceed to Validation Preview

**Expected Result**:
- ✅ Warning alert: "X valid rows, Y invalid rows"
- ✅ Preview table shows valid and invalid rows
- ✅ Invalid rows have red "Invalid" chip
- ✅ Error column shows validation error messages
- ✅ Checkbox: "Import only valid rows" checked by default
- ✅ "Import" button enabled
- ✅ Error details shown in table

**Pass/Fail**: ___________

---

## Test Scenario 10: Import Valid Rows Only

**Objective**: Import only valid rows, skip invalid

**Steps**:
1. Complete validation (Scenario 9 - mixed results)
2. Ensure "Import only valid rows" is checked
3. Click "Import" button
4. Wait for import to complete

**Expected Result**:
- ✅ Loading spinner shown during import
- ✅ Buttons disabled during import
- ✅ Import completes successfully
- ✅ Warning notification: "Imported X rows with Y errors. Check console for details."
- ✅ Modal closes automatically
- ✅ Data grid refreshes
- ✅ New rows visible in grid
- ✅ Invalid rows NOT imported

**Pass/Fail**: ___________

---

## Test Scenario 11: Import All Rows (Force)

**Objective**: Attempt to import all rows including invalid

**Steps**:
1. Complete validation (Scenario 9 - mixed results)
2. Uncheck "Import only valid rows"
3. Click "Import" button
4. Observe result

**Expected Result**:
- ✅ Loading spinner shown
- ✅ Backend returns errors for invalid rows
- ✅ Error notification: "Import failed. Y rows had errors."
- ✅ Console shows error details
- ✅ Modal remains open (to allow fixing data)
- ✅ Valid rows may or may not be imported (depends on backend transaction)

**Pass/Fail**: ___________

---

## Test Scenario 12: Import Success (All Valid)

**Objective**: Complete successful import with no errors

**Steps**:
1. Use template CSV with all valid data
2. Complete upload → mapping → validation
3. Click "Import" button
4. Wait for completion

**Expected Result**:
- ✅ Loading spinner shown
- ✅ Import completes successfully
- ✅ Success notification: "Successfully imported X rows."
- ✅ Modal closes automatically
- ✅ Data grid refreshes
- ✅ All new rows visible in grid
- ✅ Row count updated

**Pass/Fail**: ___________

---

## Test Scenario 13: Cancel Import Wizard

**Objective**: Cancel wizard at various steps

**Steps**:
1. Open wizard and upload file → Click "Cancel"
2. Open wizard, upload file, proceed to mapping → Click "Cancel"
3. Open wizard, complete mapping, view validation → Click "Cancel"

**Expected Result (all steps)**:
- ✅ Modal closes immediately
- ✅ No data imported
- ✅ No error notifications
- ✅ Grid unchanged
- ✅ Wizard state resets (reopen shows step 1 fresh)

**Pass/Fail**: ___________

---

## Test Scenario 14: Navigate Back in Wizard

**Objective**: Use "Back" button to navigate steps

**Steps**:
1. Complete upload → mapping → validation
2. From validation step, click "Back"
3. From mapping step, click "Back"

**Expected Result**:
- ✅ Step 3 → Step 2: Mapping preserved
- ✅ Step 2 → Step 1: File still loaded
- ✅ Stepper updates correctly
- ✅ "Next" button works to advance again
- ✅ No data loss when navigating

**Pass/Fail**: ___________

---

## Test Scenario 15: Invalid File Type

**Objective**: Upload unsupported file type

**Steps**:
1. Open wizard
2. Try to upload .txt, .pdf, or .docx file

**Expected Result**:
- ✅ Error alert: "Unsupported file type. Please upload CSV or Excel files."
- ✅ File not processed
- ✅ "Next" button remains disabled
- ✅ No console errors

**Pass/Fail**: ___________

---

## Test Scenario 16: Excel File Support

**Objective**: Upload .xlsx file

**Steps**:
1. Convert template CSV to Excel (.xlsx)
2. Add test data rows
3. Upload Excel file to wizard
4. Complete import

**Expected Result**:
- ✅ Excel file accepted
- ✅ First sheet parsed correctly
- ✅ Headers extracted
- ✅ Data rows visible in preview
- ✅ Mapping and validation work same as CSV
- ✅ Import succeeds

**Pass/Fail**: ___________

---

## Test Scenario 17: Large File Performance

**Objective**: Test with 100+ rows

**Steps**:
1. Create CSV with 100-200 rows
2. Upload to wizard
3. Complete mapping and validation
4. Import

**Expected Result**:
- ✅ File uploads without errors
- ✅ Validation preview shows first 10 rows (not all)
- ✅ Progress indication during processing
- ✅ Import completes within reasonable time (<30s)
- ✅ Success notification with correct row count
- ✅ Grid refreshes with new data

**Pass/Fail**: ___________

---

## Test Scenario 18: Grid Refresh After Import

**Objective**: Verify grid updates after import

**Steps**:
1. Note current row count in grid
2. Complete successful import of 5 new rows
3. Observe grid after modal closes

**Expected Result**:
- ✅ Grid automatically refreshes (no manual refresh needed)
- ✅ Row count increases by 5
- ✅ New rows visible in grid
- ✅ New rows have correct data in columns
- ✅ No duplicate rows
- ✅ Existing rows unchanged

**Pass/Fail**: ___________

---

## Integration Tests

### Test I1: Import → View Evidence
1. Import row with specific ID
2. Select imported row
3. Click "Evidence" button
4. Upload evidence attachment

**Expected**: Evidence modal works for imported rows

**Pass/Fail**: ___________

---

### Test I2: Import → Export → Reimport
1. Import 5 rows
2. Export to CSV (select all rows)
3. Modify exported CSV
4. Reimport modified CSV

**Expected**: Modified values update correctly (or duplicate rows created, depending on backend logic)

**Pass/Fail**: ___________

---

### Test I3: Import → Filter → View
1. Import rows with various field values
2. Apply filters in grid
3. Verify imported rows appear/hide based on filters

**Expected**: Filtering works on imported data

**Pass/Fail**: ___________

---

### Test I4: Import → Edit → View
1. Import row
2. Edit imported row using grid drawer
3. Save changes

**Expected**: Edits save successfully, grid refreshes

**Pass/Fail**: ___________

---

### Test I5: Import → Delete
1. Import 3 rows
2. Select imported rows
3. Bulk delete

**Expected**: Imported rows delete successfully

**Pass/Fail**: ___________

---

## Error Handling Tests

### Test E1: Network Error During Import
1. Start import
2. Disconnect network / kill backend
3. Observe error handling

**Expected**: Error notification, modal stays open, no crash

**Pass/Fail**: ___________

---

### Test E2: Template Download Failure
1. Kill backend
2. Click "Download Template"

**Expected**: Error notification: "Failed to download template"

**Pass/Fail**: ___________

---

### Test E3: Malformed CSV
1. Create CSV with inconsistent column counts
2. Upload to wizard

**Expected**: Parsing error caught gracefully with user-friendly message

**Pass/Fail**: ___________

---

## Accessibility Tests

### Test A1: Keyboard Navigation
1. Use Tab to navigate wizard
2. Use Enter/Space to activate buttons

**Expected**: All interactive elements keyboard accessible

**Pass/Fail**: ___________

---

### Test A2: Screen Reader Labels
1. Inspect button aria-labels
2. Check form labels

**Expected**: All buttons and inputs have proper labels

**Pass/Fail**: ___________

---

## Test Summary

**Total Tests**: 18 scenarios + 5 integration + 3 error + 2 accessibility = **28 tests**

**Passed**: ___________
**Failed**: ___________
**Skipped**: ___________

**Build Status**: ✅ SUCCESS (11.57s, 0 errors)

**Critical Issues Found**: ___________

**Notes**:
