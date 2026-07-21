# TASK A8 - PHASE 4: Testing & Validation

**Phase:** 4 of 5  
**Objective:** Test all evidence functionality  
**Estimated Time:** 20 minutes

---

## Test Checklist

### Pre-Test Setup

1. Ensure backend is running: `cd backend && python manage.py runserver`
2. Ensure frontend is running: `cd carbon-frontend && npm run dev`
3. Login to the platform
4. Navigate to data entry page (any module)
5. Have test files ready: test.pdf (small), test.jpg, test.xlsx

---

## Test Suite

### Test 1: Upload Single File ✓

**Steps:**
1. Select a single row (click checkbox)
2. Click "Evidence" button
3. Modal opens
4. Drag-and-drop test.pdf into upload area
5. Wait for upload to complete

**Expected:**
- ✅ Upload progress shown
- ✅ Success message displayed
- ✅ File appears in evidence list below
- ✅ Shows filename, size, date, uploader name

**Status:** [ ] PASS [ ] FAIL

---

### Test 2: Upload Multiple Files ✓

**Steps:**
1. In same modal, click "browse" (or drag multiple files)
2. Select test.jpg and test.xlsx together
3. Upload both files

**Expected:**
- ✅ Both files upload
- ✅ Both appear in evidence list
- ✅ Each shows correct metadata

**Status:** [ ] PASS [ ] FAIL

---

### Test 3: Download Evidence ✓

**Steps:**
1. Click download icon next to test.pdf
2. Check browser's download folder

**Expected:**
- ✅ File downloads
- ✅ Filename is correct (test.pdf)
- ✅ File opens correctly

**Status:** [ ] PASS [ ] FAIL

---

### Test 4: Delete Evidence ✓

**Steps:**
1. Click delete icon next to test.jpg
2. Confirm deletion in dialog
3. Evidence list refreshes

**Expected:**
- ✅ File removed from list
- ✅ Other files still visible
- ✅ No errors

**Status:** [ ] PASS [ ] FAIL

---

### Test 5: Modal Backdrop Click ✓

**Steps:**
1. With modal open, click outside modal (on dark backdrop)
2. Try pressing ESC key

**Expected:**
- ✅ Modal stays open (does NOT close)
- ✅ ESC key does nothing

**Status:** [ ] PASS [ ] FAIL

---

### Test 6: Modal Close Button ✓

**Steps:**
1. Click "Close" button at bottom of modal

**Expected:**
- ✅ Modal closes
- ✅ Returns to data grid

**Status:** [ ] PASS [ ] FAIL

---

### Test 7: File Type Validation ✓

**Steps:**
1. Try to upload an unsupported file type (.exe, .sh, .html)

**Expected:**
- ✅ File rejected
- ✅ Error message shown
- ✅ Upload does not proceed

**Status:** [ ] PASS [ ] FAIL

---

### Test 8: File Size Validation ✓

**Steps:**
1. Try to upload a file larger than 50MB

**Expected:**
- ✅ File rejected
- ✅ Error message: "File too large" or similar
- ✅ Upload does not proceed

**Status:** [ ] PASS [ ] FAIL

---

### Test 9: Row Selection ✓

**Steps:**
1. Deselect all rows
2. Click "Evidence" button
3. Select 2 rows at once
4. Click "Evidence" button
5. Select exactly 1 row
6. Click "Evidence" button

**Expected:**
- ✅ Button disabled when no rows selected (step 2)
- ✅ Button disabled when multiple rows selected (step 4)
- ✅ Button enabled when 1 row selected (step 6)
- ✅ Modal opens showing correct Row ID (step 6)

**Status:** [ ] PASS [ ] FAIL

---

### Test 10: Empty Evidence List ✓

**Steps:**
1. Select a row that has never had evidence uploaded
2. Open evidence modal

**Expected:**
- ✅ Modal shows "No evidence yet" message
- ✅ Upload area still works
- ✅ No errors

**Status:** [ ] PASS [ ] FAIL

---

## Quick Backend API Tests

If you have curl installed:

```bash
# Get JWT token first (from browser console: localStorage.getItem('token'))
TOKEN="<your-token-here>"

# Test 1: List evidence
curl -X GET "http://localhost:8000/carbon-api/evidence/" \
  -H "Authorization: Bearer $TOKEN"

# Test 2: List evidence for specific row
curl -X GET "http://localhost:8000/carbon-api/evidence/?data_row=1" \
  -H "Authorization: Bearer $TOKEN"

# Test 3: Upload evidence
curl -X POST "http://localhost:8000/carbon-api/evidence/bulk-upload/" \
  -H "Authorization: Bearer $TOKEN" \
  -F "data_row=1" \
  -F "files=@test.pdf"

# Test 4: Download evidence (replace 1 with actual ID)
curl -X GET "http://localhost:8000/carbon-api/evidence/1/download/" \
  -H "Authorization: Bearer $TOKEN" \
  -o downloaded.pdf
```

---

## Console Error Check

Open browser console (F12) and check for:
- [ ] No red errors during modal open
- [ ] No red errors during upload
- [ ] No red errors during download/delete
- [ ] Only warnings (yellow) are acceptable

---

## Build Check

```bash
cd carbon-frontend
npm run build
```

**Expected:**
- [ ] Build completes successfully
- [ ] No TypeScript errors
- [ ] No critical warnings

---

## Test Results Summary

Fill this out after testing:

| Test | Status |
|------|--------|
| 1. Upload single file | [ ] PASS [ ] FAIL |
| 2. Upload multiple files | [ ] PASS [ ] FAIL |
| 3. Download evidence | [ ] PASS [ ] FAIL |
| 4. Delete evidence | [ ] PASS [ ] FAIL |
| 5. Modal backdrop click | [ ] PASS [ ] FAIL |
| 6. Modal close button | [ ] PASS [ ] FAIL |
| 7. File type validation | [ ] PASS [ ] FAIL |
| 8. File size validation | [ ] PASS [ ] FAIL |
| 9. Row selection | [ ] PASS [ ] FAIL |
| 10. Empty evidence list | [ ] PASS [ ] FAIL |

**Total:** __ / 10 PASS

---

## If Tests Fail

Common issues and fixes:

**Issue:** Modal doesn't open
- Check console for import errors
- Verify state variables added correctly
- Check button onClick handler

**Issue:** Upload fails
- Check backend is running
- Check token is valid
- Check API_BASE_URL in config
- Check CORS settings

**Issue:** File doesn't download
- Check file exists in backend media folder
- Check download endpoint works (test with curl)

**Issue:** Modal closes on backdrop click
- Check onClose handler has backdropClick check
- Verify code matches Phase 3 instructions

---

## Next Step

When all tests pass (or issues documented), report back: "Phase 4 complete. Ready for Phase 5."

Include test results summary in your report.
