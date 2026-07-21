# Quick Error Log Reference — How to Access Logs When Things Go Wrong

## 🎯 When Row Save Fails (400, 401, 5xx Error)

### Step 1: Frontend Console (Immediate)
```bash
F12 → Console tab → Look for "🔴 API ERROR" messages
```

**You'll see:**
```
🔴 API ERROR - PATCH http://localhost:8009/carbon-api/dataschema/rows/36/?data_table=8

Status: 400
Detail: {"field1": ["Must be a number."]}
Request: {method: "PATCH", endpoint: "...", body: {...}}
Response: {field1: ["Must be a number."]}
```

### Step 2: Error History (Without Page Reload)
```javascript
// Copy-paste in console:
JSON.parse(sessionStorage.getItem('api_errors')||'[]').map(e => ({
  time: e.timestamp,
  status: e.status,
  endpoint: e.endpoint,
  error: e.detail
}))
```

### Step 3: Full Error Object (For Detailed Analysis)
```javascript
// Copy-paste in console:
const allErrors = JSON.parse(sessionStorage.getItem('api_errors')||'[]');
const lastError = allErrors[allErrors.length - 1];
console.table(lastError);  // Shows: timestamp, status, endpoint, request, response
```

---

## 🖥️ When Backend Fails (Django Terminal)

### Look for These Patterns in Terminal

**PATCH Request Started:**
```
╔════════════════════════════════════════════════════════════════════════╗
║ 🟡 PATCH REQUEST → partial_update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: 36
║ USER: admin (ID: 1)
║ QUERY PARAMS: {'data_table': '8'}
║ REQUEST DATA: {'data_table': 8, 'values': {...}}
║ CONTENT-TYPE: application/json
╚════════════════════════════════════════════════════════════════════════╝
```

**Success:**
```
✅ PATCH SUCCESS - Row 36
```

**Error:**
```
╔════════════════════════════════════════════════════════════════════════╗
║ ❌ PATCH FAILED - Row 36
╠════════════════════════════════════════════════════════════════════════╣
║ ERROR: {"field1": ["Must be a number."]}
║ TYPE: ValidationError
╚════════════════════════════════════════════════════════════════════════╝
```

---

## 🔍 Debugging Workflow

### For "400 Bad Request" Errors

**Step 1:** What did frontend send?
```javascript
const err = JSON.parse(sessionStorage.getItem('api_errors')||'[]').pop();
console.log('Payload sent:', err.requestBody);
```

**Step 2:** What did backend complain about?
```javascript
console.log('Backend error:', err.responseData);
```

**Step 3:** Check backend logs for validation details
```
Terminal: Look for "ValidationError" or "Must be a number"
```

**Step 4:** Fix the field value and retry

---

### For "401 Unauthorized" Errors

**Step 1:** Token expired?
```javascript
const err = JSON.parse(sessionStorage.getItem('api_errors')||'[]').find(e => e.status === 401);
if (err) console.log('Token expired at:', err.timestamp);
```

**Step 2:** Check backend logs
```
Terminal: Look for "AnonymousUser" or "Permission denied"
```

**Step 3:** apiFetch should auto-refresh, if still failing:
- Clear localStorage token: `localStorage.removeItem('access_token')`
- Reload page and login again

---

### For Silent Errors (No Console Popup)

**Step 1:** Check error history exists
```javascript
const history = sessionStorage.getItem('api_errors');
console.log('Has errors?', history ? JSON.parse(history).length : 'No');
```

**Step 2:** If empty, error bypassed logging (check network tab)
```
DevTools → Network tab → Look for failed requests
```

**Step 3:** Check backend logs for unhandled exceptions
```
Terminal: Search for "Traceback" or "Exception"
```

---

## 📋 Common Error Patterns & Solutions

| Error | Where to Check | Solution |
|-------|---|---|
| 400 Bad Request | Frontend console + Backend logs | Check payload format, field types |
| 401 Unauthorized | Frontend console (status code) | Token expired, clear localStorage |
| 500 Server Error | Backend logs (Traceback) | Backend bug, check exception |
| Validation error | Backend logs (field name) | Required field missing, invalid value |
| Silent failure | sessionStorage history | Check if error was caught |

---

## 🛠️ Quick Commands

### Browser Console (Copy-Paste Ready)

**Show all errors:**
```javascript
JSON.parse(sessionStorage.getItem('api_errors')||'[]')
```

**Show last error:**
```javascript
JSON.parse(sessionStorage.getItem('api_errors')||'[]').pop()
```

**Show only 400 errors:**
```javascript
JSON.parse(sessionStorage.getItem('api_errors')||'[]').filter(e => e.status === 400)
```

**Show only PATCH errors:**
```javascript
JSON.parse(sessionStorage.getItem('api_errors')||'[]').filter(e => e.method === 'PATCH')
```

**Export all errors as JSON:**
```javascript
copy(JSON.stringify(JSON.parse(sessionStorage.getItem('api_errors')||'[]'), null, 2))
```
*(Then paste in a file)*

**Clear error history:**
```javascript
sessionStorage.removeItem('api_errors')
```

---

## 📱 For Mobile/Responsive Testing

Use **React DevTools** (extension):
1. Right-click → Inspect
2. DevTools → Console tab
3. Same commands as above

---

## 🚀 Production Troubleshooting

### If you can't see browser console:

**1. Check backend logs:**
```bash
# Docker
docker logs <container_name> -f | grep "API ERROR\|PATCH\|FAILED"

# Direct
tail -f /var/log/carbon/dataschema.log | grep "PATCH\|ERROR"
```

**2. Enable backend file logging:**
```python
# settings.py
LOGGING['loggers']['dataschema.views']['handlers'].append('file')
```

**3. Check web server logs:**
```bash
# Nginx
tail -f /var/log/nginx/error.log | grep carbon

# Apache
tail -f /var/log/apache2/error.log | grep carbon
```

---

## 🎓 Understanding Log Format

### Frontend Log Example
```
🔴 API ERROR - PATCH /dataschema/rows/36/?data_table=8
├─ Status: 400
├─ Detail: {"field1": ["Must be a number."]}
├─ Request: {method: "PATCH", body: {"data_table": 8, "values": {"field1": "abc"}}}
├─ Response: {field1: ["Must be a number."]}
└─ Timestamp: 2026-07-19T15:44:00.000Z
```

**Reading this:**
- User tried to PATCH row 36 in table 8
- Backend rejected with 400
- Reason: field1 received "abc" but expected a number
- Request was correct format, just wrong value

### Backend Log Example
```
╔════════════════════════════════════════════════════════════════════════╗
║ 🟡 PATCH REQUEST → partial_update()
╠════════════════════════════════════════════════════════════════════════╣
║ ROW ID: 36
║ USER: admin (ID: 1)
║ QUERY PARAMS: {'data_table': '8'}
║ REQUEST DATA: {'data_table': 8, 'values': {'field1': 'abc'}}
║ CONTENT-TYPE: application/json
╚════════════════════════════════════════════════════════════════════════╝

❌ PATCH FAILED - Row 36

ValidationError: {"field1": ["Must be a number."]}
```

**Reading this:**
- Admin user attempted partial_update
- Row 36 in table 8
- Payload had field1="abc"
- Failed at validation (serializer rejected it)

---

## ✅ Verification Checklist

- [ ] Builds without errors: `npm run build && python manage.py check`
- [ ] Frontend logging active: F12 Console visible during save
- [ ] Backend logging active: Terminal shows PATCH logs
- [ ] Error history enabled: `sessionStorage` contains error array
- [ ] Can inspect errors: Browser console commands work

---

## Next Steps

1. **Try it**: Edit a row, make it fail, check logs
2. **Understand the pattern**: Request → Response → Error
3. **Use for debugging**: When something breaks, logs show exactly why
4. **Share logs**: If reporting bugs, include console logs + backend logs

See [`DEBUG_ERROR_LOGGING_GUIDE.md`](DEBUG_ERROR_LOGGING_GUIDE.md) for full documentation.
