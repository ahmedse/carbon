# Comprehensive Error Logging & Monitoring Guide

## Overview
This document describes the error logging infrastructure added to both frontend and backend to track and debug issues silently occurring during API requests, particularly in form submissions like RowEditTab row editing.

## Problem Statement
Before this implementation, errors occurred silently:
- **Frontend**: API errors thrown in `apiFetch` were caught in try-catch blocks but not comprehensively logged
- **Backend**: ViewSet method overrides (update/partial_update) didn't log request details or error context
- **Result**: Difficult to diagnose issues like 400 Bad Request errors that didn't display obvious error messages

## Solution Architecture

### Frontend Error Logging (`carbon-frontend/src/api/api.js`)

#### 1. **Comprehensive Error Logging on Failed Responses**

When an API request fails (non-2xx status), the frontend now logs:

```javascript
console.group(`🔴 API ERROR - ${method} ${endpoint}`);
console.error('Status:', response.status);
console.error('Detail:', detail);
console.error('Request:', { method, endpoint, body });
console.error('Response:', responseData);
console.table(errorLog);
console.groupEnd();
```

**What gets logged:**
- HTTP status code (400, 401, 500, etc.)
- Error detail message from backend
- Full request (method, endpoint, request body)
- Full response data from backend
- Response headers
- Timestamp of the error

**How to view in browser:**
1. Open DevTools (F12)
2. Go to Console tab
3. Look for collapsed groups starting with `🔴 API ERROR`
4. Expand them to see detailed error information

#### 2. **Error History Storage in sessionStorage**

Errors are also stored in `sessionStorage` for inspection after the fact:

```javascript
sessionStorage.getItem('api_errors')  // Returns JSON array of last 50 errors
```

**Via Browser Console:**
```javascript
// View all captured errors
const errors = JSON.parse(sessionStorage.getItem('api_errors') || '[]');
errors.forEach((e, i) => console.log(`Error ${i}:`, e));

// View latest error only
const latest = JSON.parse(sessionStorage.getItem('api_errors') || '[]').pop();
console.table(latest);
```

#### 3. **Unexpected Error Logging**

Errors not related to HTTP responses are also logged:

```javascript
console.error('🔴 apiFetch Catch Block:', {
  endpoint,
  method,
  errorMessage: error.message,
  errorStack: error.stack,
  timestamp: new Date().toISOString(),
});
```

---

### Backend Error Logging (`backend/dataschema/views.py`)

#### 1. **DataRowViewSet Override Methods**

The `DataRowViewSet` now has overridden `update()` and `partial_update()` methods that log all PATCH/PUT requests:

```python
def update(self, request, *args, **kwargs):
    """Override to add comprehensive logging for PATCH/PUT operations"""
    import logging
    logger = logging.getLogger('dataschema.views')
    
    row_id = kwargs.get('pk')
    logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ 🔵 PATCH/PUT REQUEST → update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: {row_id}
║ USER: {request.user.username} (ID: {request.user.id})
║ QUERY PARAMS: {dict(request.query_params)}
║ REQUEST DATA: {dict(request.data)}
║ CONTENT-TYPE: {request.content_type}
╚════════════════════════════════════════════════════════════════════════╝
    """)
    
    try:
        result = super().update(request, *args, **kwargs)
        logger.error(f"✅ UPDATE SUCCESS - Row {row_id}")
        return result
    except Exception as e:
        logger.error(f"""
╔════════════════════════════════════════════════════════════════════════╗
║ ❌ UPDATE FAILED - Row {row_id}
╠════════════════════════════════════════════════════════════════════════╣
║ ERROR: {str(e)}
║ TYPE: {type(e).__name__}
╚════════════════════════════════════════════════════════════════════════╝
        """, exc_info=True)
        raise
```

**Similarly for `partial_update()` (PATCH requests)**

#### 2. **What Gets Logged on Backend**

**Request Details:**
- Row ID being updated
- Username and user ID making the request
- Query parameters (e.g., `?data_table=8`)
- Full request data (payload sent)
- Content-Type header

**Response/Error Details:**
- Success or failure status
- Full exception message
- Exception type
- Full traceback (via `exc_info=True`)

#### 3. **How to View Backend Logs**

**During development (Django runserver):**

```bash
cd backend
python manage.py runserver 0.0.0.0:8009
```

Look for log output in the terminal where Django is running. You'll see output like:

```
╔════════════════════════════════════════════════════════════════════════╗
║ 🟡 PATCH REQUEST → partial_update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: 36
║ USER: admin (ID: 1)
║ QUERY PARAMS: {'data_table': '8'}
║ REQUEST DATA: {'data_table': 8, 'values': {'field1': 'value1'}}
║ CONTENT-TYPE: application/json
╚════════════════════════════════════════════════════════════════════════╝
```

**For production/Docker:**

Check container logs:
```bash
docker logs <container_name> -f
```

**Configure Django logging in `settings.py`:**

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': '/var/log/carbon/dataschema.log',
        },
    },
    'loggers': {
        'dataschema.views': {
            'handlers': ['console', 'file'],
            'level': 'ERROR',  # Logs even in production
            'propagate': True,
        },
    },
}
```

---

## Real-World Debugging Scenarios

### Scenario 1: Row Save Returns 400 Bad Request

**Frontend (Browser Console):**

```javascript
// 1. Look at the API ERROR
// Console shows: "🔴 API ERROR - PATCH /dataschema/rows/36/?data_table=8"

// 2. Check stored errors
const errors = JSON.parse(sessionStorage.getItem('api_errors') || '[]');
const errorObj = errors.find(e => e.status === 400);

console.table({
  'Status': errorObj.status,
  'Request Payload': errorObj.requestBody,
  'Response': errorObj.responseData,
  'Endpoint': errorObj.endpoint
});

// Example output might show:
// Status: 400
// Request Payload: {data_table: 8, values: {name: "test"}}
// Response: {field1: ["Must be a number."]}
// Endpoint: dataschema/rows/36/?data_table=8
```

**Backend (Terminal/Logs):**

```
╔════════════════════════════════════════════════════════════════════════╗
║ 🟡 PATCH REQUEST → partial_update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: 36
║ USER: admin (ID: 1)
║ QUERY PARAMS: {'data_table': '8'}
║ REQUEST DATA: {'data_table': 8, 'values': {'name': 'test'}}
║ CONTENT-TYPE: application/json
╚════════════════════════════════════════════════════════════════════════╝

╔════════════════════════════════════════════════════════════════════════╗
║ ❌ PATCH FAILED - Row 36
╠════════════════════════════════════════════════════════════════════════╣
║ ERROR: {"field1": ["Must be a number."]}
║ TYPE: ValidationError
╚════════════════════════════════════════════════════════════════════════╝
Traceback (most recent call last):
  File "backend/dataschema/views.py", line 170, in partial_update
    result = super().partial_update(request, *args, **kwargs)
  File "rest_framework/viewsets.py", line 93, in partial_update
    return self.update(request, *args, partial=True, **kwargs)
  File "rest_framework/generics.py", line 98, in update
    serializer.save()
  File "backend/dataschema/serializers.py", line 64, in validate
    raise serializers.ValidationError(...)
```

**Analysis:**
- Frontend shows: Payload has `{data_table: 8, values: {name: "test"}}`
- Backend shows: Validation error on `field1` (not sent in payload)
- **Solution**: Field1 is required but wasn't included in the edit form

---

### Scenario 2: Silent 401 Unauthorized (Token Expired)

**Frontend (Browser Console):**

```javascript
const errors = JSON.parse(sessionStorage.getItem('api_errors') || '[]');
const authError = errors.find(e => e.status === 401);

if (authError) {
  console.log('Token expired at:', authError.timestamp);
  console.log('Attempted endpoint:', authError.endpoint);
  console.log('User should be redirected to login');
}
```

**Backend (Terminal/Logs):**

```
╔════════════════════════════════════════════════════════════════════════╗
║ 🟡 PATCH REQUEST → partial_update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: 36
║ USER: AnonymousUser (ID: None)
║ QUERY PARAMS: {'data_table': '8'}
║ REQUEST DATA: {'data_table': 8, 'values': {...}}
║ CONTENT-TYPE: application/json
╚════════════════════════════════════════════════════════════════════════╝

Permission denied: User is not authenticated
```

**Analysis:**
- Token was invalid/expired
- Backend rejected request before PATCH logic ran
- Frontend's `apiFetch` should have caught this and attempted refresh

---

## Integration with RowEditTab

### How RowEditTab Uses Logging

```javascript
// RowEditTab.jsx - lines 125-162

const handleSave = async () => {
  console.log('🟦 RowEditTab: Saving with apiFetch', {
    rowId,
    tableId,
    payloadKeys: Object.keys(updatePayload),
    valuesKeys: Object.keys(fieldData),
    fieldDataSample: fieldData,
    updatePayload,
  });
  
  try {
    const updated = await apiFetch(...);
    console.log('✅ RowEditTab: Response received', { 
      updatedKeys: Object.keys(updated),
      updated 
    });
    // ... update state
  } catch (err) {
    console.error('🔴 RowEditTab: Save error - full details:', {
      errorMessage: err.message,
      errorResponse: err.response,
      errorData: err.data,
      formDataSent: formData,
      error: err,
    });
    // ... show error
  }
};
```

**When debugging RowEditTab:**
1. Look for `🟦 RowEditTab: Saving` - shows what payload was sent
2. If error, look for `🔴 RowEditTab: Save error` - shows what went wrong
3. Check `🔴 API ERROR` logs for backend details
4. Check backend logs for validation errors

---

## Checking Error History

### Browser DevTools Console Commands

```javascript
// View all errors
const errors = JSON.parse(sessionStorage.getItem('api_errors') || '[]');
console.table(errors);

// View errors by status code
const status400 = errors.filter(e => e.status === 400);
console.log('400 Errors:', status400);

// View latest error with full detail
const latest = errors[errors.length - 1];
console.log('Latest Error:', latest);
console.table(latest);

// Export errors as JSON for analysis
copy(JSON.stringify(errors, null, 2));
// Then paste in a file

// Clear error history
sessionStorage.removeItem('api_errors');
```

---

## Best Practices

### For Frontend Developers

1. **Always check the API ERROR logs first** when something fails
2. **Use sessionStorage query** to get full error context without refreshing
3. **Look at request payload** - is it what you expected?
4. **Look at response data** - what did the backend actually say?

### For Backend Developers

1. **Errors are logged to Django logger** - check terminal during dev
2. **Each PATCH/PUT logs request details** - easy to reproduce issues
3. **Full tracebacks are included** - use `exc_info=True`
4. **Exceptions are re-raised** - API response includes error message

### For DevOps/Production

1. **Configure file logging** in Django settings
2. **Send logs to ELK/Splunk** for centralized monitoring
3. **Alert on patterns** like "400 Bad Request" spike
4. **Archive logs** for audit trail

---

## Testing Error Logging

### Manual Test: Trigger 400 Error

1. Open Row Edit form
2. Leave required field empty
3. Click Save
4. **Expected**: Browser console shows full error details with request/response

### Manual Test: Trigger 401 Error

1. Let token expire (wait or manually manipulate localStorage)
2. Try to save row
3. **Expected**: Browser logs show 401 initially, then retry after refresh

### Manual Test: Check Backend Logs

```bash
# Terminal 1: Run Django with logging visible
cd backend && python manage.py runserver 0.0.0.0:8009

# Terminal 2: Make a PATCH request
curl -X PATCH http://localhost:8009/carbon-api/dataschema/rows/36/?data_table=8 \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"data_table": 8, "values": {"field1": "value"}}'

# Terminal 1: Should show detailed PATCH logs
```

---

## Troubleshooting Guide

| Issue | Frontend Check | Backend Check |
|-------|---|---|
| Save appears to hang | Check network tab (DevTools) | Check backend logs for timeout |
| 400 Bad Request (silent) | Check `sessionStorage` errors | Check `partial_update()` logs |
| 401 Unauthorized | Check `apiFetch` logs | Check Django auth logs |
| Row not saved | Check ✅/❌ in console | Check validation logs |
| Error "not visible" to user | Check notification system | Check error response format |

---

## Configuration

### Enable Logging in Different Environments

**Development:**
```python
# settings.py
LOGGING['loggers']['dataschema.views']['level'] = 'ERROR'  # or 'DEBUG'
```

**Production:**
```python
# settings.py
LOGGING['loggers']['dataschema.views'] = {
    'handlers': ['file', 'console'],
    'level': 'ERROR',  # Only errors in prod
    'propagate': False,
}
```

---

## Related Files Modified

- [`carbon-frontend/src/api/api.js`](carbon-frontend/src/api/api.js:177-230) - Frontend error logging
- [`carbon-frontend/src/pages/dataschema/tabs/RowEditTab.jsx`](carbon-frontend/src/pages/dataschema/tabs/RowEditTab.jsx:106-153) - Component-level logging
- [`backend/dataschema/views.py`](backend/dataschema/views.py:119-225) - Backend request/error logging

---

## Summary

The comprehensive error logging infrastructure ensures that:
1. **Frontend errors are captured** with full request/response context
2. **Backend errors are logged** with user, request data, and exception details
3. **Errors are stored** in sessionStorage for inspection without page reload
4. **Debugging is traceable** across frontend→network→backend
5. **Silent failures are eliminated** - everything is logged and visible

Use this guide to diagnose any silent errors occurring in the application.
