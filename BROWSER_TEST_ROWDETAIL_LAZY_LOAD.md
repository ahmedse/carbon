# Browser Test Guide: RowDetailPage Lazy Loading Verification

## Objective
Verify that the RowDetailPage loads immediately with row data, and metrics tabs only fetch when clicked (lazy loading).

## Prerequisites
- Backend running: `cd backend && python manage.py runserver 8009`
- Frontend dev server running: `cd carbon-frontend && npm run dev`
- Access to browser DevTools (F12)
- Test credentials ready (username/password)

---

## Test Scenario 1: Page Load Performance (No Metrics Fetch)

### Steps
1. **Open DevTools** → Network tab
2. **Clear network log** (Ctrl+Shift+Delete)
3. **Navigate to row detail page** via grid:
   - Go to Data Hub → Select a module → Open a data table
   - Click View icon on any row to open `/dataschema/row/{tableId}/{rowId}`
4. **Observe network requests** in Network tab

### Expected Results
✓ Page loads quickly (< 2 seconds)
✓ Row data fetched: `GET /carbon-api/dataschema/rows/{rowId}/?data_table={tableId}` → HTTP 200
✓ NO request to `/carbon-api/dq/metrics/table/` initially
✓ Overview tab shows row data immediately
✓ NO spinner in metrics panel during page load

### Actual Result
[User to report]

---

## Test Scenario 2: Tab Navigation - Lazy Load Triggers Fetch

### Steps
1. **Keep DevTools open** → Network tab
2. **Clear network log**
3. **Click on "DQ Metrics" tab** in the metrics panel (right side)
4. **Observe network requests**

### Expected Results
✓ Spinner appears briefly in DQ Metrics tab
✓ Network request appears: `GET /carbon-api/dq/metrics/table/{tableId}/?row_id={rowId}` → (200 or 404)
✓ Fetch happens ONLY when tab clicked (not before)
✓ Other tabs (Lineage, Related) don't fetch anything
✓ If fetch fails (404), error message shows in DQ tab only

### Actual Result
[User to report]

---

## Test Scenario 3: Tab Switching - No Duplicate Fetches

### Steps
1. **Keep Network tab open**
2. **Already in DQ Metrics tab** from previous test
3. **Click "Lineage" tab**
4. **Click "DQ Metrics" tab again**
5. **Observe network requests**

### Expected Results
✓ First click on DQ Metrics → 1 network request
✓ Switch to Lineage tab → NO new network requests
✓ Switch back to DQ Metrics tab → NO duplicate request (uses cached data)
✓ Metrics still display (or show error if initial fetch failed)

### Actual Result
[User to report]

---

## Test Scenario 4: Edit and Overview Tabs Work Independently

### Steps
1. **In Overview tab:**
   - Verify row data displays (all fields visible)
   - Check values match database
2. **Click "Edit" tab:**
   - Verify form loads with current values
   - Try editing a field (text, date, number)
   - Click "Save" button
   - Verify success notification
3. **Click back to "Overview":**
   - Verify updated value shows
4. **Check Network tab:**
   - Row detail fetch: 1 request (on page load)
   - Edit submit: 1 PATCH request
   - NO metrics requests during these operations

### Expected Results
✓ Overview shows row data instantly
✓ Edit tab loads form instantly
✓ Save sends PATCH request to `/carbon-api/dataschema/rows/{rowId}/`
✓ Success message appears
✓ Updated value reflects after save
✓ NO metrics fetch happens during these operations

### Actual Result
[User to report]

---

## Test Scenario 5: Evidence Tab (Future Use)

### Steps
1. **Click "Evidence" tab**
2. **Observe UI**

### Expected Results
✓ Evidence tab loads without triggering metrics fetch
✓ Evidence uploader/viewer available if component loaded
✓ NO spinner or error about missing data

### Actual Result
[User to report]

---

## Test Scenario 6: Page Responsiveness During Metrics Fetch

### Steps
1. **Click "DQ Metrics" tab** to start fetch
2. **Immediately click "Edit" tab** while spinner is showing
3. **Try editing a field** while metrics are loading

### Expected Results
✓ Edit tab responds immediately
✓ Form is interactive even while metrics load in background
✓ Can type/edit values in form
✓ Metrics loading spinner doesn't block other operations

### Actual Result
[User to report]

---

## Test Scenario 7: Error Handling - Metrics Endpoint 404

### Steps
1. **Open browser Console** (F12 → Console)
2. **Click "DQ Metrics" tab**
3. **Observe console and UI**

### Expected Results
✓ Spinner shows briefly
✓ After ~2 seconds: warning alert appears with "Failed to fetch DQ metrics" message
✓ Console shows: `DQ Metrics fetch error: Failed to fetch DQ metrics`
✓ Other tabs (Lineage, Related) remain functional
✓ No red error banner at top of page

### Actual Result
[User to report]

---

## Test Scenario 8: Browser Back Button & Navigation

### Steps
1. **In row detail page**
2. **Click browser back button**
3. **Should return to grid view**
4. **Click View on same row again**

### Expected Results
✓ Back button works correctly
✓ Returns to grid with table data
✓ Clicking View again reloads row detail page fresh
✓ Row data loads again (no cache persistence issues)
✓ Metrics panel resets (lazy loading triggered again on tab click)

### Actual Result
[User to report]

---

## Performance Checklist

| Metric | Expected | Actual |
|--------|----------|--------|
| Initial page load time | < 2 sec | |
| Row data display | Instant | |
| Metrics fetch (on tab click) | < 3 sec | |
| Tab switches | < 100ms | |
| Edit form response | < 100ms | |
| Save button | < 1 sec | |

---

## Browser DevTools Verification

### Network Tab Analysis

**Expected Request Timeline:**
```
t=0ms:   GET /carbon-api/dataschema/rows/{rowId}/?data_table={tableId}
t=200ms: Response received (HTTP 200)
         Page renders with row data ✓

t=1500ms: User clicks "DQ Metrics" tab
t=1510ms: GET /carbon-api/dq/metrics/table/{tableId}/?row_id={rowId}
t=1800ms: Response received (HTTP 200 or 404)
         Metrics tab renders or shows error ✓
```

**After fix verification:**
- ✓ NO metrics request at page load (t=0)
- ✓ Metrics request ONLY after user action (t=1500ms+)
- ✓ Single request per fetch (no duplicates on tab switches)

---

## Console Output

### Expected Logs
```javascript
// On page load:
✓ (No metrics-related logs)

// When clicking DQ Metrics tab:
DQ Metrics fetch started
DQ Metrics fetch error: (if 404) Failed to fetch DQ metrics
// OR
DQ Metrics fetch successful (if 200)
```

### Unexpected Logs (Report if seen)
- ❌ "Uncaught TypeError" errors
- ❌ "CORS error" in metrics request
- ❌ "Undefined is not a function"

---

## Sign-Off Checklist

- [ ] Page loads within 2 seconds
- [ ] Row data displays immediately
- [ ] NO metrics request on initial load
- [ ] Metrics request triggered only on tab click
- [ ] No duplicate fetch on tab re-visits
- [ ] Edit/Overview/Evidence tabs work without metrics
- [ ] Error handling works (404 shows alert, not page error)
- [ ] Other users' interactions don't affect this user's metrics
- [ ] Browser back button works
- [ ] Mobile view (if applicable) works as expected

---

## Notes

1. **What to watch for:** The key indicator that lazy loading works is that the metrics endpoint request does NOT appear in DevTools Network tab until you click the "DQ Metrics" tab.

2. **If metrics still load on page open:** Check [`RowMetricsPanel.jsx`](carbon-frontend/src/pages/dataschema/RowMetricsPanel.jsx:37) line 37 to verify `if (metricsTabIndex !== 0) return;` is present.

3. **If page is still slow:** Check if row data fetch is completing (HTTP 200). If it returns error or times out, that's the blocker.

4. **Cache behavior:** Each new row detail page should have its own metrics fetch. Switching rows should trigger new fetches (not reuse cached data from previous row).

---

## Rollback Plan (If Issues Found)

If lazy loading causes problems:
1. Revert to eager loading: Set `loading: true` initially in RowMetricsPanel
2. Remove `metricsTabIndex` check from useEffect dependency
3. Rebuild: `cd carbon-frontend && npm run build`
