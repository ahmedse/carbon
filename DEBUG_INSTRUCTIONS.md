# Debug Instructions: RowDetailPage Loading Issue

## Quick Test Steps

1. **Open browser DevTools** (F12) → Console tab
2. **Navigate to row detail page:**
   - Go to Data Hub
   - Select a module
   - Open a data table
   - Click View icon on any row
   
3. **Watch the console** for these debug messages:
   ```
   🟦 RowDetailPage: fetchRowData starting
   🟦 RowDetailPage: Fetching from URL: ...
   🟦 RowDetailPage: Fetch response received
   🟩 RowDetailPage: Row data received successfully
   ```

4. **Report what you see:**
   - Do you see these messages?
   - What's the LAST message you see before page hangs?
   - Is there an error message?

---

## Expected Console Output (Page Loading Successfully)

```
🟦 RowDetailPage: fetchRowData starting {
  token: true,
  rowId: "36",
  tableId: "8",
  API_BASE_URL: "http://localhost:8000/api/v1/",
  API_ROUTES_rows: "dataschema/rows/"
}

🟦 RowDetailPage: Fetching from URL: http://localhost:8000/api/v1/dataschema/rows/36/?data_table=8

🟦 RowDetailPage: Fetch response received {
  status: 200,
  ok: true,
  statusText: "OK"
}

🟩 RowDetailPage: Row data received successfully {
  rowId: 36,
  fieldsCount: 4
}
```

---

## If Page Hangs - Check For These Issues

### Issue 1: Row Fetch Never Completes
**Sign:** See "Fetching from URL" but NO "Fetch response received"

**Cause:** Backend endpoint is hanging or not responding
**Fix:** Check backend logs, verify endpoint returns HTTP 200

### Issue 2: Row Fetch Returns Error
**Sign:** See "Failed to fetch row: 401" or "403" or "404"

**Cause:** Authentication, permissions, or endpoint not found
**Fix:** Check token expiration, RBAC permissions, URL routing

### Issue 3: Row Data Missing (metricsTabIndex stuck at -1)
**Sign:** See "Row data received successfully" but still loading spinner

**Cause:** metricsTabIndex not properly initialized in RowDetailPage
**Fix:** Check useState hook on line 37 of RowDetailPage

### Issue 4: Metrics Fetch Blocking Main Content
**Sign:** Row data loads, but page still shows spinner

**Cause:** RowMetricsPanel metrics fetch not actually lazy loading
**Fix:** Click "DQ Metrics" tab - if spinner disappears, then lazy loading is working

---

## Console Log Locations

- **RowDetailPage logs:** Lines 62-97 in RowDetailPage.jsx
- **RowMetricsPanel logs:** Lines 35-41 in RowMetricsPanel.jsx

---

## Copy/Paste This Command to Get Latest Version

```bash
cd carbon-frontend && npm run build && echo "✅ Build complete"
```

Then refresh browser (Ctrl+R or Cmd+R).
