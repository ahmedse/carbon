# Token Recovery Debug Guide

## Problem Discovered

The RowDetailPage was stuck in infinite loading with console output:
```
"RowDetailPage: Missing required params { token: false, rowId: '37', tableId: '8' }"
```

**Root Cause:** The Auth context's `token` was `false` (falsy), meaning either:
1. The user wasn't authenticated when navigating to the page, OR
2. The token was lost during navigation (Auth context not initialized yet)

## Solution Implemented

Added **token recovery logic** to both `RowDetailPage.jsx` and `RowMetricsPanel.jsx`:

### RowDetailPage.jsx (Lines 61-95)

```javascript
let currentToken = token;

console.log('🟦 RowDetailPage: fetchRowData starting', {
  token: !!currentToken,
  rowId,
  tableId,
  API_BASE_URL,
  API_ROUTES_rows: API_ROUTES.rows,
});

// If no token, try to recover from localStorage
if (!currentToken) {
  console.log('🟨 RowDetailPage: No token from context, attempting recovery from localStorage');
  currentToken = localStorage.getItem('access');
  if (currentToken) {
    console.log('✅ RowDetailPage: Token recovered from localStorage');
  }
}

if (!currentToken || !rowId || !tableId) {
  console.log('🟨 RowDetailPage: Missing required params after recovery attempt', {
    token: !!currentToken,
    rowId,
    tableId,
  });
  setError('Authentication required. Please log in.');
  setLoading(false);
  return;
}
```

### RowMetricsPanel.jsx (Lines 30-55)

```javascript
let currentToken = token;

// If no token, try to recover from localStorage
if (!currentToken) {
  console.log('🟨 RowMetricsPanel: No token from context, attempting recovery');
  currentToken = localStorage.getItem('access');
  if (currentToken) {
    console.log('✅ RowMetricsPanel: Token recovered from localStorage');
  }
}
```

## Testing Steps

### Step 1: Login and Navigate to a Row
1. Open browser DevTools → Console tab
2. Log in to Carbon app
3. Navigate to Data Schema → Data Entry → Select a table
4. Click View icon on a row to open RowDetailPage

### Step 2: Check Console Output

**Expected sequence:**

```
🟦 RowDetailPage: fetchRowData starting {
  token: true,
  rowId: '37',
  tableId: '8',
  API_BASE_URL: 'http://localhost:8000',
  API_ROUTES_rows: 'dataschema/rows/'
}

🟦 RowDetailPage: Fetching from URL: http://localhost:8000/carbon-api/dataschema/rows/37/?data_table=8

🟦 RowDetailPage: Fetch response received {
  status: 200,
  ok: true,
  statusText: 'OK'
}

🟩 RowDetailPage: Row data received successfully {
  rowId: 37,
  fieldsCount: 12
}
```

### Step 3: If Token Recovery Trigger

If you navigate directly to the URL (e.g., `/dataschema/rows/detail/37/8`) without going through the normal flow, you might see:

```
🟦 RowDetailPage: fetchRowData starting { token: false, ... }
🟨 RowDetailPage: No token from context, attempting recovery from localStorage
✅ RowDetailPage: Token recovered from localStorage
🟦 RowDetailPage: Fetching from URL: ...
```

This shows the recovery mechanism working correctly.

### Step 4: Click DQ Metrics Tab

If row data loads successfully, click the **DQ Metrics** tab (second tab). You should see:

```
🟦 RowMetricsPanel: useEffect triggered {
  metricsTabIndex: 0,  // (0 = DQ Metrics tab is active)
  token: true,
  rowId: '37',
  tableId: '8',
  dqMetricsFetched: false,
  loading: false
}

🟦 RowMetricsPanel: fetchDQMetrics running {
  metricsTabIndex: 0,
  dqMetricsFetched: false,
  token: true
}

🟦 RowMetricsPanel: Starting fetch...
🟦 RowMetricsPanel: Trying primary URL: http://localhost:8000/carbon-api/dq/metrics/table/8/?row_id=37

🟦 RowMetricsPanel: Primary response received {
  status: 200,
  ok: true
}

🟩 RowMetricsPanel: Fallback fetch successful  // (or "Primary fetch successful" if 200)
```

### Step 5: Verify Lazy Loading

- Click back to **Overview** tab (first tab) - metrics should NOT be fetched
- Click to **Edit** tab (third tab) - metrics should NOT be fetched
- Click back to **DQ Metrics** tab - metrics should NOT be fetched again (already have `dqMetricsFetched: true`)

In console, after first DQ metrics fetch, you should see:

```
🟦 RowMetricsPanel: useEffect triggered { ..., dqMetricsFetched: true, ... }
🟨 RowMetricsPanel: Guard 1 returned - missing params or already fetched {
  token: true,
  rowId: '37',
  tableId: '8',
  dqMetricsFetched: true  // <-- Already fetched
}
```

This confirms metrics are only fetched **once** and **only when the tab is clicked**.

## Troubleshooting

### Issue: "Missing required params" - token still false after recovery

**Check 1: localStorage**
```javascript
// In browser console:
localStorage.getItem('access')
// If null or empty string → User not logged in
// If valid JWT → Token exists but auth context not initialized
```

**Check 2: AuthContext Initialization**
- Refresh the page and watch console
- The AuthContext should run its initial sync on mount (lines 91-100)
- Check if localStorage tokens are being loaded correctly

**Fix:** Log in again. The issue is likely a session expiration or login that didn't complete.

### Issue: 401 Unauthorized error after token recovery

**Cause:** The recovered token from localStorage is expired.

**Fix:** The App.jsx should have a 401 handler that redirects to login. If not:
1. Log out: `localStorage.removeItem('access'); localStorage.removeItem('refresh');`
2. Log in again
3. The backend will provide fresh tokens

### Issue: Row data loads but metrics stay "loading"

**Check:** Metrics tab DQ metrics fetch is blocked by a guard condition

```javascript
// In RowMetricsPanel, these guards prevent fetches:
1. !currentToken || !rowId || !tableId || dqMetricsFetched
2. metricsTabIndex !== 0  (must be on DQ Metrics tab, index 0)
```

**Verify:** Check console has both "fetchDQMetrics running" AND "Starting fetch..." messages. If only the first appears, a guard condition is blocking.

## Key Files Modified

1. **`carbon-frontend/src/pages/dataschema/RowDetailPage.jsx`** (Lines 61-95)
   - Added token recovery from localStorage
   - Sets error message if still no token after recovery
   - Uses `currentToken` variable throughout fetch

2. **`carbon-frontend/src/pages/dataschema/RowMetricsPanel.jsx`** (Lines 30-106)
   - Added token recovery from localStorage
   - Uses `currentToken` variable throughout both primary and fallback fetches
   - Maintains lazy loading behavior (only fetch when tab clicked)

## Expected Behavior After Fix

✅ **Page Load with Token from Context:**
- RowDetailPage fetches row data immediately (no loading state)
- Metrics panel is empty (not fetching until tab clicked)
- No "Missing required params" error

✅ **Direct URL Navigation:**
- Token recovered from localStorage
- Page loads normally
- Same behavior as above

✅ **DQ Metrics Tab Activation:**
- Metrics fetch only when tab clicked
- Fetch runs only once (dqMetricsFetched guard prevents re-fetch)
- Other tabs do NOT trigger metrics fetch (lazy loading works)

✅ **Session Expiration:**
- Backend 401 response triggers login redirect (existing auth flow)
- No infinite loading, user sees error or redirect

## Next Steps if Issue Persists

1. **Verify Backend Endpoint Working:**
   ```bash
   curl -H "Authorization: Bearer $(cat token.txt)" \
     "http://localhost:8000/carbon-api/dataschema/rows/37/?data_table=8"
   ```

2. **Enable Debug Logging in AuthContext:**
   Uncomment line 66 in `AuthContext.jsx`:
   ```javascript
   const debug = (...args) => { if (import.meta.env.DEV) console.log("[Auth]", ...args); };
   ```

3. **Check CORS Issues:**
   Look for CORS errors in browser console (different from auth errors)
   - If present, verify backend CORS config includes frontend URL

4. **Verify Backend Authentication:**
   - Ensure user is actually authenticated
   - Check that JWT token is valid (not expired, not tampered with)
   - Verify RBAC permissions for the table/row being viewed
