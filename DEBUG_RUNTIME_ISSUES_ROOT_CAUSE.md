# Debug Report: Runtime Issues Analysis

## Executive Summary

Three runtime issues persist despite successful builds:
1. **Evidence Tab 401 Unauthorized** - Despite API path fix
2. **Edit Tab VALUES field showing [object Object]** - Despite extractEditableFields() function
3. **Unsaved Changes Warning** - Form state management issue

All three are due to logic errors, not syntax errors.

---

## Issue #1: Evidence Tab 401 Unauthorized

### Root Cause: Wrapped in Try-Catch Without Proper Status Checking

**File**: `carbon-frontend/src/components/evidence/EvidenceViewer.jsx:27-48`

```javascript
const fetchEvidence = async () => {
  if (!dataRowId) return;
  setLoading(true);
  setError(null);

  try {
    const response = await fetch(`${API_BASE_URL}evidence/?data_row=${dataRowId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    if (response.ok) {
      const data = await response.json();
      setEvidence(data.results || data);
    } else {
      setError('Failed to load evidence');  // ❌ GENERIC ERROR - hides 401
    }
  } catch (err) {
    setError(`Error: ${err.message}`);
  } finally {
    setLoading(false);
  }
};
```

**Problem**: 
- When `response.status === 401`, the code sets generic error "Failed to load evidence"
- Does not check if token is valid or expired
- Does not pass error details to console for debugging
- Does not attempt token recovery

**Impact**: User sees vague error, developer sees nothing in console

### Fix
Add detailed error logging and token validation:

```javascript
const fetchEvidence = async () => {
  if (!dataRowId) return;
  setLoading(true);
  setError(null);

  try {
    const response = await fetch(`${API_BASE_URL}evidence/?data_row=${dataRowId}`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });

    console.log('🟦 EvidenceViewer: Fetch response', {
      status: response.status,
      ok: response.ok,
      dataRowId,
      hasToken: !!token,
    });

    if (response.status === 401) {
      console.error('🔴 EvidenceViewer: 401 Unauthorized - token may be invalid or expired');
      setError('Authentication failed. Please refresh the page or log in again.');
    } else if (response.ok) {
      const data = await response.json();
      setEvidence(data.results || data);
      console.log('🟩 EvidenceViewer: Evidence loaded', { count: (data.results || data).length });
    } else {
      console.error('🔴 EvidenceViewer: HTTP error', { status: response.status, statusText: response.statusText });
      setError(`Failed to load evidence (${response.status})`);
    }
  } catch (err) {
    console.error('🔴 EvidenceViewer: Fetch error', err);
    setError(`Error: ${err.message}`);
  } finally {
    setLoading(false);
  }
};
```

---

## Issue #2: Edit Tab VALUES field showing [object Object]

### Root Cause: Initial Form State NOT Using extractEditableFields()

**File**: `carbon-frontend/src/pages/dataschema/tabs/RowEditTab.jsx:60`

```javascript
// Line 36-58: extractEditableFields() function defined
const extractEditableFields = (data) => {
  const metadataFields = ['created_at', 'updated_at', 'created_by', 'updated_by'];
  const nonDataFields = ['id', 'data_table', 'is_archived', 'version', 'values', ...metadataFields];
  const fieldData = {};

  // Primary: extract from nested 'values' object
  if (data.values && typeof data.values === 'object') {
    Object.entries(data.values).forEach(([key, value]) => {
      fieldData[key] = value;
    });
  }

  // Fallback: extract from data directly if values is empty
  if (Object.keys(fieldData).length === 0) {
    Object.entries(data).forEach(([key, value]) => {
      if (!nonDataFields.includes(key)) {
        fieldData[key] = value;
      }
    });
  }

  return fieldData;
};

// ❌ LINE 60: INITIAL STATE PASSES RAW rowData, NOT EXTRACTED FIELDS
const [formData, setFormData] = useState(extractEditableFields(rowData));
```

**Wait - that LOOKS correct!** Let me check more carefully...

The issue is that `rowData` is passed as a prop, but if it initially contains the raw nested object structure (not yet processed), the form will render before `extractEditableFields()` can properly extract.

**The Real Problem**: Line 146 in RowEditTab shows:
```javascript
const handleReset = () => {
  setFormData(rowData);  // ❌ SETS TO RAW rowData, NOT EXTRACTED
  setHasChanges(false);
  setIsDirty(false);
};
```

And then line 179:
```javascript
value={value !== null && value !== undefined ? value : ''}
```

If `value` is an object (e.g., `{field1: 'x', field2: 'y'}`), it renders as `[object Object]`.

### Secondary Problem: Comparison Logic at Line 68

```javascript
useEffect(() => {
  // ❌ COMPARING formData (extracted) WITH rowData (nested)
  const changed = JSON.stringify(formData) !== JSON.stringify(rowData);
  setHasChanges(changed);
  if (changed) {
    setIsDirty(true);
  }
}, [formData, rowData]);
```

This compares extracted fields against the raw nested object, which will ALWAYS show as changed!

### Fix

**1. Fix handleReset to use extracted fields:**
```javascript
const handleReset = () => {
  const extracted = extractEditableFields(rowData);
  setFormData(extracted);
  setHasChanges(false);
  setIsDirty(false);
};
```

**2. Fix useEffect to compare correctly:**
```javascript
useEffect(() => {
  const originalExtracted = extractEditableFields(rowData);
  const changed = JSON.stringify(formData) !== JSON.stringify(originalExtracted);
  setHasChanges(changed);
  if (changed) {
    setIsDirty(true);
  }
}, [formData, rowData]);
```

**3. Add console logging to verify extraction:**
```javascript
useEffect(() => {
  const extracted = extractEditableFields(rowData);
  console.log('🟦 RowEditTab: Form data loaded', {
    fieldsCount: Object.keys(extracted).length,
    fieldNames: Object.keys(extracted),
    sampleValue: Object.values(extracted)[0],
  });
}, [rowData]);
```

---

## Issue #3: Unsaved Changes Warning

### Root Cause: isDirty Flag Never Resets Properly

**File**: `carbon-frontend/src/pages/dataschema/tabs/RowEditTab.jsx:134-149`

```javascript
const handleSave = async () => {
  // ... save logic ...
  const updated = await response.json();
  const editableFields = extractEditableFields(updated);
  setFormData(editableFields);
  setRowData(updated);
  setIsDirty(false);  // ✓ Sets to false
  // ...
};

const handleReset = () => {
  setFormData(rowData);  // ❌ Not extracted
  setHasChanges(false);
  setIsDirty(false);
};
```

**Problem**: After handleReset(), the comparison at line 68 might still show `changed = true` because:
1. `setFormData(rowData)` sets form to raw nested object
2. Comparison then sees `formData` (nested) vs `rowData` (nested) but with different object references
3. `isDirty` remains true despite the reset attempt

### Fix

Ensure both reset and save use properly extracted data:

```javascript
const handleSave = async () => {
  setSaving(true);
  setError(null);

  try {
    const excludeFields = ['id', 'created_at', 'updated_at', 'created_by', 'updated_by'];
    const updateData = Object.entries(formData)
      .filter(([key]) => !excludeFields.includes(key))
      .reduce((acc, [key, value]) => {
        acc[key] = value;
        return acc;
      }, {});

    const response = await fetch(
      `${API_BASE_URL}api/rows/${rowId}/?data_table=${tableId}`,
      {
        method: 'PATCH',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(updateData),
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `Save failed: ${response.status}`);
    }

    const updated = await response.json();
    const editableFields = extractEditableFields(updated);
    
    setFormData(editableFields);  // ✓ Set to extracted
    setRowData(updated);
    setIsDirty(false);  // ✓ Clear dirty flag
    setHasChanges(false);  // ✓ Clear changes flag too
    
    notify('Row saved successfully', 'success');
    console.log('✅ RowEditTab: Row saved successfully');
  } catch (err) {
    console.error('🔴 RowEditTab: Save error:', err);
    setError(err.message || 'Failed to save row');
    notify(`Error: ${err.message}`, 'error');
  } finally {
    setSaving(false);
  }
};

const handleReset = () => {
  const extracted = extractEditableFields(rowData);
  setFormData(extracted);  // ✓ Set to extracted
  setHasChanges(false);
  setIsDirty(false);
  console.log('✅ RowEditTab: Form reset to saved values');
};
```

---

## Summary of Fixes

| Issue | File | Lines | Fix |
|-------|------|-------|-----|
| Evidence 401 | EvidenceViewer.jsx | 27-48 | Add detailed error logging and 401 handling |
| VALUES field | RowEditTab.jsx | 60, 146, 68 | Use extractEditableFields() in initial state, reset, and comparison |
| Unsaved Warning | RowEditTab.jsx | 134-149 | Properly reset isDirty and hasChanges flags |

---

## Testing Checklist After Fixes

- [ ] Edit tab opens and shows field values (not [object Object])
- [ ] Changing a field value shows "unsaved changes" warning
- [ ] Clicking "Reset" clears the warning and restores original values
- [ ] Clicking "Save" saves the row and clears the warning
- [ ] Evidence tab loads without 401 error (or shows clear auth error message)
- [ ] Console shows detailed debug logs for all operations

