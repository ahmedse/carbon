# TASK A8: Evidence & Attachments Implementation

**RUN:** A8  
**Priority:** ⭐⭐⭐ CRITICAL  
**Status:** Ready for Execution  
**Executor:** Raptor (Code Mode)  
**Validator:** Architect Mode  
**Date:** 2026-07-18

---

## 1. OBJECTIVE

Implement a complete evidence file attachment system that enables users to upload, view, download, and delete supporting documents (invoices, receipts, photos, PDFs) for data rows in the Carbon Data Trust Platform.

**Business Impact:**
- **Critical:** Required for audited emissions reporting compliance
- **User Pain:** Currently users must organize evidence files manually outside the system
- **Audit Readiness:** Auditors need verifiable evidence trail attached to each data entry

**Success Definition:** Users can attach evidence files to any data row, view the list of attachments, download files for verification, and delete files as needed. Modal interface prevents accidental closure and provides clear context.

---

## 2. SCOPE — IN

### Backend (Django)
- ✅ Create `evidence` Django app
- ✅ Evidence model with FileField, metadata, soft delete
- ✅ EvidenceSerializer with file metadata helpers
- ✅ EvidenceViewSet with CRUD + download + bulk-upload actions
- ✅ EvidencePermission class for RBAC enforcement
- ✅ URL routing configuration
- ✅ Django admin interface
- ✅ Database migrations
- ✅ Media storage configuration (MEDIA_ROOT, MEDIA_URL)

### Frontend (React)
- ✅ EvidenceUploader component (drag-and-drop file upload)
- ✅ EvidenceViewer component (list, download, delete evidence)
- ✅ Modal dialog integration in TableDataPage
- ✅ Non-dismissible modal (backdrop click disabled)
- ✅ Resizable modal dialog
- ✅ Row context indicator (Row ID in header)
- ✅ Evidence button in data entry toolbar
- ✅ Upload progress indicator
- ✅ Error handling and user feedback

### Features
- ✅ Drag-and-drop file upload
- ✅ Browse file selection
- ✅ Multiple file upload (bulk)
- ✅ File type validation (PDF, JPG, PNG, Excel, CSV, Word, ZIP)
- ✅ File size limit (50MB max per file)
- ✅ Download evidence files
- ✅ Soft delete evidence (preserves audit trail)
- ✅ RBAC permissions (users access only their modules' evidence)
- ✅ Audit metadata (uploader, timestamp)

---

## 3. SCOPE — OUT (DO NOT TOUCH)

- ❌ Inline preview (PDF/image viewer in browser) - Future enhancement
- ❌ Version control for evidence files - Future enhancement
- ❌ Batch download as ZIP - Future enhancement
- ❌ OCR/AI data extraction from evidence - Future enhancement
- ❌ Evidence templates/requirements per table - Future enhancement
- ❌ Evidence approval workflow - Future enhancement
- ❌ External storage (S3/Azure Blob) - Use local filesystem for now
- ❌ Virus scanning - Future enhancement
- ❌ Evidence count badge in data grid - Future enhancement
- ❌ Other pages/components not explicitly mentioned

---

## 4. CONSTRAINTS

### Technical Constraints
- **Backend:** Django 4.x, Python 3.10+, PostgreSQL
- **Frontend:** React 18, Material-UI v5, Vite
- **File Storage:** Local filesystem (media/evidence/ directory)
- **Max File Size:** 50MB per file
- **File Types:** PDF, JPG, JPEG, PNG, XLSX, CSV, DOCX, TXT, ZIP only
- **Browser Support:** Modern browsers (Chrome, Firefox, Edge, Safari)

### UX Constraints (User Requirements)
- **MUST use Modal** (not drawer) for evidence UI
- **MUST NOT close on backdrop click** (prevents accidental loss)
- **MUST have explicit Close button**
- **MUST be resizable** (CSS resize property)
- **MUST show Row ID** in modal header for context

### Business Constraints
- Users can only access evidence for data rows in their assigned modules (RBAC)
- Admins can access all evidence
- Soft delete only (maintain audit trail)
- Evidence files stored per row (one-to-many relationship)

---

## 5. DELIVERABLES

### Code Deliverables

#### Backend Files (NEW)
1. `backend/evidence/__init__.py`
2. `backend/evidence/apps.py`
3. `backend/evidence/models.py` - Evidence model
4. `backend/evidence/serializers.py` - EvidenceSerializer, EvidenceUploadSerializer
5. `backend/evidence/views.py` - EvidenceViewSet
6. `backend/evidence/permissions.py` - EvidencePermission
7. `backend/evidence/urls.py` - URL routing
8. `backend/evidence/admin.py` - Django admin interface
9. `backend/evidence/migrations/0001_initial.py` - Auto-generated migration

#### Backend Files (MODIFIED)
1. `backend/config/settings.py` - Add evidence to INSTALLED_APPS, configure MEDIA_ROOT/MEDIA_URL
2. `backend/config/urls.py` - Include evidence URLs

#### Frontend Files (NEW)
1. `carbon-frontend/src/components/evidence/EvidenceUploader.jsx` - Drag-and-drop upload component
2. `carbon-frontend/src/components/evidence/EvidenceViewer.jsx` - Evidence list/download/delete component

#### Frontend Files (MODIFIED)
1. `carbon-frontend/src/components/TableDataPage.jsx` - Add modal integration

#### Dependencies
1. `carbon-frontend/package.json` - Add react-dropzone

### Documentation Deliverables
1. `docs/RUN_LOG.md` - Add A8 entry
2. `TASK-RESULT-A8.md` - Detailed completion report with test results

---

## 6. IMPLEMENTATION PLAN

### Phase 1: Backend Setup

**Tasks:**
1. Create `backend/evidence/` directory and Python files
2. Implement Evidence model with FileField and metadata
3. Implement serializers (EvidenceSerializer, EvidenceUploadSerializer)
4. Implement EvidenceViewSet with download and bulk-upload actions
5. Implement EvidencePermission class
6. Configure URL routing
7. Create Django admin interface
8. Update settings.py (INSTALLED_APPS, MEDIA_ROOT, FILE_UPLOAD_MAX_MEMORY_SIZE)
9. Update urls.py (include evidence.urls)
10. Run migrations: `python manage.py makemigrations evidence`
11. Run migrations: `python manage.py migrate evidence`
12. Verify migrations applied successfully

**Acceptance:**
- Evidence table created in database
- API endpoint `/carbon-api/evidence/` responds (empty list or 403 if not authenticated)
- Migration file created in `backend/evidence/migrations/0001_initial.py`

---

### Phase 2: Frontend Components

**Tasks:**
1. Create `carbon-frontend/src/components/evidence/` directory
2. Install react-dropzone: `npm install react-dropzone`
3. Implement EvidenceUploader.jsx (drag-and-drop, upload progress, error handling)
4. Implement EvidenceViewer.jsx (list, download, delete)
5. Test components render without errors

**Acceptance:**
- react-dropzone installed in package.json
- EvidenceUploader component compiles without errors
- EvidenceViewer component compiles without errors
- Components use Material-UI styling consistent with rest of app

---

### Phase 3: Integration with TableDataPage

**Tasks:**
1. Import evidence components and Material-UI Dialog in TableDataPage.jsx
2. Add state variables: selectedRowId, showEvidenceModal, evidenceRefreshKey
3. Add handleRowSelection handler
4. Add "Evidence" button to toolbar
5. Add Modal (Dialog) component with non-dismissible backdrop
6. Wire up modal open/close logic
7. Connect EvidenceUploader and EvidenceViewer to modal
8. Ensure row selection updates selectedRowId
9. Test modal opens when Evidence button clicked

**Acceptance:**
- Evidence button appears in TableDataPage toolbar
- Button disabled when no row or multiple rows selected
- Button enabled when exactly one row selected
- Modal opens on button click
- Modal does NOT close when clicking backdrop
- Modal closes when Close button clicked
- Modal displays Row ID in header

---

### Phase 4: Testing & Validation

**Manual Test Cases:**

#### Test 1: Upload Single File
1. Navigate to data entry page
2. Select a single row (checkbox)
3. Click "Evidence" button
4. Modal opens
5. Drag-and-drop a PDF file into upload area
6. Upload succeeds
7. File appears in evidence list with filename, size, date, uploader

**Expected:** ✅ File uploaded, appears in list

#### Test 2: Upload Multiple Files (Bulk)
1. Open evidence modal for a row
2. Select 3 files (PDF, JPG, Excel) via browse button
3. Upload all at once
4. All 3 files appear in evidence list

**Expected:** ✅ All files uploaded successfully

#### Test 3: Download Evidence
1. Open evidence modal for a row with evidence
2. Click download icon for a file
3. File downloads to browser's download folder

**Expected:** ✅ File downloads correctly

#### Test 4: Delete Evidence
1. Open evidence modal for a row with evidence
2. Click delete icon for a file
3. Confirm deletion
4. File removed from list

**Expected:** ✅ File soft-deleted (is_deleted=True in DB)

#### Test 5: Modal Backdrop Click (User Requirement)
1. Open evidence modal
2. Click outside modal (on backdrop)
3. Modal remains open (does NOT close)

**Expected:** ✅ Modal stays open

#### Test 6: File Type Validation
1. Try to upload .exe or .sh file
2. Upload rejected with error message

**Expected:** ✅ Only allowed file types accepted

#### Test 7: File Size Validation
1. Try to upload 60MB file
2. Upload rejected with error message

**Expected:** ✅ Files >50MB rejected

#### Test 8: RBAC Permissions
1. Login as data-owner with access to Module A only
2. Open evidence for a row in Module A
3. Can upload/view/delete evidence
4. Try to access evidence API for Module B row (via curl)
5. API returns 403 Forbidden

**Expected:** ✅ Users can only access evidence from their modules

#### Test 9: Build Success
1. Run `cd carbon-frontend && npm run build`
2. Build completes without errors

**Expected:** ✅ No build errors

---

### Phase 5: Documentation

**Tasks:**
1. Update `docs/RUN_LOG.md` - Add A8 entry after A7
2. Create `TASK-RESULT-A8.md` with:
   - Summary of changes
   - Files created/modified
   - Test results for all 9 test cases
   - Screenshots (optional but recommended)
   - Known issues/limitations
   - Next steps (RUN A9)

**Acceptance:**
- RUN_LOG.md has A8 entry
- TASK-RESULT-A8.md exists with complete test results
- All test cases documented as PASS/FAIL

---

## 7. ACCEPTANCE CRITERIA

### Backend Acceptance Criteria
- [x] Evidence model exists with fields: data_row, file, original_filename, file_size, mime_type, uploaded_by, uploaded_at, is_deleted
- [x] POST /carbon-api/evidence/bulk-upload/ accepts multipart/form-data
- [x] GET /carbon-api/evidence/?data_row={id} returns list of evidence for row
- [x] GET /carbon-api/evidence/{id}/download/ returns file with correct content-type
- [x] DELETE /carbon-api/evidence/{id}/ soft-deletes (sets is_deleted=True)
- [x] Files stored in media/evidence/YYYY/MM/DD/ directory
- [x] RBAC enforced: users can only access evidence from their modules
- [x] Admins can access all evidence
- [x] File type validation rejects non-allowed extensions
- [x] File size validation rejects files >50MB

### Frontend Acceptance Criteria
- [x] EvidenceUploader component renders upload area
- [x] Drag-and-drop works for file upload
- [x] Browse button works for file selection
- [x] Upload progress indicator shows during upload
- [x] Success/error messages displayed after upload
- [x] EvidenceViewer displays list of evidence files
- [x] Each evidence item shows: filename, size, date, uploader name
- [x] Download button downloads file correctly
- [x] Delete button removes evidence (with confirmation dialog)
- [x] Evidence button in TableDataPage toolbar
- [x] Button disabled when no row selected or multiple rows selected
- [x] Button enabled when exactly one row selected

### Modal UX Acceptance Criteria (User Requirements)
- [x] Modal (Dialog) used instead of Drawer
- [x] Modal does NOT close when clicking backdrop
- [x] Modal does NOT close when pressing ESC key
- [x] Modal has explicit "Close" button that works
- [x] Modal is resizable (CSS resize property)
- [x] Modal header shows Row ID for context
- [x] Modal has clear title "Evidence Attachments"

### Integration Acceptance Criteria
- [x] TableDataPage integrates evidence components
- [x] Row selection updates selectedRowId state
- [x] Modal opens/closes correctly
- [x] Evidence uploads refresh viewer automatically
- [x] Evidence deletes refresh viewer automatically
- [x] No console errors when opening/closing modal
- [x] No console errors during file upload/download/delete

### Build & Deployment Acceptance Criteria
- [x] Backend migrations applied successfully (no errors)
- [x] Frontend builds without errors (`npm run build`)
- [x] No TypeScript/linting errors
- [x] No runtime errors in browser console
- [x] Backend API accessible at /carbon-api/evidence/
- [x] Media files accessible at /media/evidence/ (if served locally)

---

## 8. TEST FRAMEWORK

### Backend API Tests (Manual via curl)

**Test 1: List Evidence (Empty)**
```bash
curl -X GET "http://localhost:8000/carbon-api/evidence/" \
  -H "Authorization: Bearer <token>"

Expected: {"count": 0, "results": []} or similar
```

**Test 2: Upload Evidence**
```bash
curl -X POST "http://localhost:8000/carbon-api/evidence/bulk-upload/" \
  -H "Authorization: Bearer <token>" \
  -F "data_row=1" \
  -F "files=@test-invoice.pdf"

Expected: {"results": [{"filename": "test-invoice.pdf", "status": "success", "id": 1}], "total": 1, "success": 1}
```

**Test 3: List Evidence (After Upload)**
```bash
curl -X GET "http://localhost:8000/carbon-api/evidence/?data_row=1" \
  -H "Authorization: Bearer <token>"

Expected: {"count": 1, "results": [{...}]}
```

**Test 4: Download Evidence**
```bash
curl -X GET "http://localhost:8000/carbon-api/evidence/1/download/" \
  -H "Authorization: Bearer <token>" \
  -o downloaded.pdf

Expected: File downloaded successfully
```

**Test 5: Delete Evidence**
```bash
curl -X DELETE "http://localhost:8000/carbon-api/evidence/1/" \
  -H "Authorization: Bearer <token>"

Expected: 204 No Content
```

**Test 6: Verify Soft Delete**
```bash
# Query database directly
psql -d carbon_dev -c "SELECT id, original_filename, is_deleted FROM evidence WHERE id=1;"

Expected: is_deleted = true
```

---

### Frontend UI Tests (Manual)

**Test Suite:** Evidence Upload Flow

| # | Test Case | Steps | Expected Result | Status |
|---|-----------|-------|-----------------|--------|
| 1 | Modal opens | Select row → Click Evidence button | Modal opens with Row ID in header | ⬜ |
| 2 | Upload single file | Drag PDF into upload area | File uploads, appears in list | ⬜ |
| 3 | Upload multiple files | Select 3 files via browse | All 3 upload, appear in list | ⬜ |
| 4 | Download file | Click download icon | File downloads to browser | ⬜ |
| 5 | Delete file | Click delete icon → Confirm | File removed from list | ⬜ |
| 6 | Backdrop click | Click outside modal | Modal stays open (no close) | ⬜ |
| 7 | ESC key | Press ESC while modal open | Modal stays open (no close) | ⬜ |
| 8 | Close button | Click Close button | Modal closes | ⬜ |
| 9 | File type validation | Try to upload .exe file | Error message shown | ⬜ |
| 10 | File size validation | Try to upload 60MB file | Error message shown | ⬜ |
| 11 | Progress indicator | Upload large file | Progress bar appears | ⬜ |
| 12 | Error handling | Upload with no internet | Clear error message shown | ⬜ |

**Pass Criteria:** All 12 tests must pass (✅)

---

### RBAC Permission Tests

**Test 1: Data Owner - Own Module**
1. Login as data-owner (Alice) with access to Module "Transportation"
2. Navigate to data entry for Transportation module
3. Select a row, click Evidence
4. Upload a file
5. File uploads successfully

**Expected:** ✅ Data owner can upload evidence to their module

**Test 2: Data Owner - Other Module**
1. Still logged in as Alice
2. Try to access API for evidence in Module "Energy" (not assigned to Alice)
```bash
curl -X GET "http://localhost:8000/carbon-api/evidence/?data_row=100" \
  -H "Authorization: Bearer <alice_token>"
```
**Expected:** ✅ Empty list or 403 Forbidden (depending on queryset filtering)

**Test 3: Admin - All Modules**
1. Login as admin
2. Navigate to any module's data entry
3. Select a row, click Evidence
4. Upload a file
5. File uploads successfully

**Expected:** ✅ Admin can upload evidence to any module

---

## 9. DEFINITION OF DONE

**Technical Completion:**
- [x] All backend files created and working
- [x] All frontend files created and working
- [x] Integration complete (modal in TableDataPage)
- [x] Migrations applied successfully
- [x] Dependencies installed (react-dropzone)
- [x] Build succeeds (no errors)

**Testing Completion:**
- [x] All 6 backend API tests pass
- [x] All 12 frontend UI tests pass
- [x] All 3 RBAC permission tests pass
- [x] No console errors
- [x] No build warnings (critical ones)

**Documentation Completion:**
- [x] RUN_LOG.md updated with A8 entry
- [x] TASK-RESULT-A8.md created with:
  - Summary of implementation
  - List of files created/modified
  - Test results (21 tests total)
  - Screenshots of UI (optional)
  - Known issues/limitations
  - Next steps

**User Acceptance:**
- [x] Modal approach implemented (not drawer)
- [x] Modal does NOT close on backdrop click
- [x] Modal is resizable
- [x] Row ID shown in modal header
- [x] Explicit Close button works

**Code Quality:**
- [x] Code follows existing project patterns
- [x] Error handling implemented
- [x] Loading states implemented
- [x] User feedback messages clear and helpful
- [x] No hardcoded values (use constants/config)
- [x] Comments added where logic is complex

---

## 10. VALIDATION PROCESS

After Raptor completes implementation and creates TASK-RESULT-A8.md:

### Architect Validation Checklist

**Code Review:**
- [ ] All backend files exist in correct locations
- [ ] Evidence model has all required fields
- [ ] Serializers handle file metadata correctly
- [ ] ViewSet implements download and bulk-upload actions
- [ ] Permissions enforce RBAC correctly
- [ ] Frontend components use Material-UI consistently
- [ ] Modal implementation matches user requirements
- [ ] No code smells or anti-patterns

**Testing Validation:**
- [ ] Review test results in TASK-RESULT-A8.md
- [ ] Verify all 21 tests passed
- [ ] Check for any skipped or failed tests
- [ ] Validate RBAC permissions tested thoroughly
- [ ] Confirm modal UX requirements met

**Documentation Validation:**
- [ ] RUN_LOG.md entry is clear and complete
- [ ] TASK-RESULT-A8.md follows standard format
- [ ] Test results documented with pass/fail status
- [ ] Screenshots provided (if applicable)
- [ ] Known issues listed (if any)
- [ ] Next steps outlined

**Integration Validation:**
- [ ] Evidence button appears in correct location
- [ ] Modal opens/closes as expected
- [ ] Upload/download/delete workflows function
- [ ] No breaking changes to existing features
- [ ] Build succeeds locally

**Sign-off Criteria:**
- All checkboxes above marked [x]
- No critical issues found
- User requirements met (modal, non-dismissible, resizable)
- Platform remains stable

---

## 11. KNOWN RISKS & MITIGATION

| Risk | Impact | Mitigation |
|------|--------|------------|
| File storage fills up quickly | High | Monitor storage usage, implement quotas in future |
| Malicious file uploads | High | Validate file types, consider virus scanning in future |
| Large files slow down UI | Medium | Show progress indicator, consider chunked upload in future |
| RBAC bypass | Critical | Thorough permission testing, code review |
| Modal UX confuses users | Low | Clear instructions in modal, Row ID context |
| Migration conflicts | Medium | Test migrations on fresh DB, backup before applying |
| CORS issues | Low | Verify django-cors-headers configured |

---

## 12. REFERENCE DOCUMENTATION

**Implementation Plan:** `plans/RUN_A8_EVIDENCE_ATTACHMENTS_v2.md` (complete code examples)

**Execution Prompt:** `plans/RAPTOR_PROMPT_A8.md` (step-by-step instructions)

**Platform Audit:** `plans/PLATFORM_COMPLETION_AUDIT.md` (context and next steps)

**Related Files:**
- `carbon-frontend/src/components/TableDataPage.jsx` (integration point)
- `backend/dataschema/models.py` (DataRow model - parent of Evidence)
- `backend/accounts/models.py` (User model - uploader reference)

**Django Docs:**
- FileField: https://docs.djangoproject.com/en/4.2/ref/models/fields/#filefield
- File uploads: https://docs.djangoproject.com/en/4.2/topics/http/file-uploads/

**React Docs:**
- react-dropzone: https://react-dropzone.js.org/
- Material-UI Dialog: https://mui.com/material-ui/react-dialog/

---

## 13. SUCCESS METRICS

**Quantitative:**
- ✅ 0 build errors
- ✅ 0 migration errors
- ✅ 21/21 tests pass (100%)
- ✅ 0 console errors
- ✅ 0 RBAC bypass vulnerabilities

**Qualitative:**
- ✅ Modal UX meets user requirements (non-dismissible, resizable, clear context)
- ✅ Upload flow is intuitive (drag-and-drop or browse)
- ✅ Error messages are helpful and actionable
- ✅ Evidence list displays all relevant metadata
- ✅ Code is clean, readable, maintainable

**Business:**
- ✅ Platform ready for audit readiness (evidence can be attached)
- ✅ Unblocks RUN A9 (bulk import can reuse upload patterns)
- ✅ Foundation for RUN A10 (lineage panel can use similar modal UX)

---

**EXECUTOR (Raptor): Follow Phase 1-5 sequentially. Report progress after each phase. Create TASK-RESULT-A8.md when complete.**

**VALIDATOR (Architect): Review TASK-RESULT-A8.md. Run validation checklist. Approve or request changes.**
