# Configuration Best Practices - Avoiding API URL Errors

## 🎯 The Problem

API endpoint mismatches happen because:
1. URLs hardcoded in multiple places
2. No single source of truth
3. Dev/staging/prod environments differ
4. No validation on startup
5. Easy to forget to update all locations

## ✅ The Solution

### 1. Single Source of Truth

**Frontend:** All URLs in `src/config.js`
```javascript
export const API_ROUTES = {
  aiChat: "ai/chat/send_message/",
  aiInsights: "ai/insights/",
  // ... etc
};
```

**Backend:** All URLs in `config/urls.py`
```python
urlpatterns = [
    path('api/v1/ai/', include('ai_copilot.urls')),
]
```

### 2. Environment Variables (.env files)

**Frontend `.env`:**
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1/
```

**Backend `.env`:**
```bash
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1
```

### 3. Never Hardcode URLs in Components

❌ **WRONG:**
```javascript
const response = await fetch('http://localhost:8000/api/v1/ai/chat/');
```

✅ **CORRECT:**
```javascript
import { API_ROUTES } from '../config';
const response = await apiFetch(API_ROUTES.aiChat);
```

### 4. Validation on Startup

**config.js** now includes health check:
```javascript
const validateApiConfig = async () => {
  try {
    await fetch(API_BASE_URL);
    console.log("✅ API reachable");
  } catch {
    console.error("❌ API NOT reachable - check VITE_API_BASE_URL");
  }
};
```

### 5. Environment-Specific Configs

```
carbon-frontend/
├── .env                    # Development (gitignored)
├── .env.example           # Template (committed to git)
├── .env.production        # Production overrides
└── .env.staging           # Staging overrides
```

## 🔧 Implementation Checklist

### For Every New API Endpoint:

- [ ] Add route to backend `urls.py`
- [ ] Add route name to frontend `config.js` → `API_ROUTES`
- [ ] Use `API_ROUTES.routeName` in API service file
- [ ] Never hardcode the URL directly
- [ ] Test with dev server running

### For New Features:

- [ ] Check `config.js` for existing route definitions
- [ ] Reuse existing patterns (don't create new URL patterns)
- [ ] Update `.env.example` if adding new env variables
- [ ] Document any new configuration requirements

## 📋 Quick Reference

### Frontend API Call Pattern

```javascript
// 1. Import from config
import { API_ROUTES } from '../config';
import { apiFetch } from './api';

// 2. Use route name, not hardcoded URL
export const myFunction = async () => {
  const token = localStorage.getItem('access');
  return await apiFetch(API_ROUTES.myEndpoint, { 
    method: 'POST',
    token,
    body: { data }
  });
};
```

### Adding New Endpoint

1. **Backend** (`backend/myapp/urls.py`):
```python
urlpatterns = [
    path('my-endpoint/', MyView.as_view(), name='my-endpoint'),
]
```

2. **Frontend** (`src/config.js`):
```javascript
export const API_ROUTES = {
  // ... existing routes
  myEndpoint: "myapp/my-endpoint/",
};
```

3. **API Service** (`src/api/myService.js`):
```javascript
import { API_ROUTES } from '../config';
import { apiFetch } from './api';

export const callMyEndpoint = () => {
  return apiFetch(API_ROUTES.myEndpoint);
};
```

## 🚨 Common Mistakes to Avoid

### ❌ Mistake 1: Hardcoding URLs
```javascript
const response = await fetch('http://localhost:8000/api/ai/chat/');
```

### ❌ Mistake 2: Different URLs in Different Files
```javascript
// file1.js
const URL = '/api/v1/ai/';

// file2.js  
const URL = '/carbon-api/ai/';  // Different!
```

### ❌ Mistake 3: Not Using Environment Variables
```javascript
const API_BASE = "http://localhost:8000";  // Hardcoded!
```

### ❌ Mistake 4: Forgetting to Update .env.example
```bash
# Only you have the .env, teammates don't know what variables to set
```

## ✅ Correct Patterns

### ✅ Pattern 1: Use Config Routes
```javascript
import { API_ROUTES } from '../config';
const url = API_ROUTES.aiChat;
```

### ✅ Pattern 2: Use Environment Variables
```javascript
const baseUrl = import.meta.env.VITE_API_BASE_URL;
```

### ✅ Pattern 3: Centralize in One File
```javascript
// config.js - Single source of truth
export const API_ROUTES = { /* all routes */ };
```

### ✅ Pattern 4: Document Requirements
```bash
# .env.example - Committed to git
VITE_API_BASE_URL=http://localhost:8000/api/v1/
```

## 🔄 Workflow for Environment Changes

### Development → Staging
```bash
cp .env.example .env.staging
# Edit .env.staging with staging values
VITE_API_BASE_URL=https://staging.example.com/api/v1/
```

### Development → Production
```bash
cp .env.example .env.production
# Edit .env.production with production values
VITE_API_BASE_URL=https://api.example.com/api/v1/
```

### Build for Specific Environment
```bash
# Development
npm run dev

# Production
npm run build  # Uses .env.production
```

## 📊 Configuration Validation Script

Run this before committing:

```bash
#!/bin/bash
# validate-config.sh

echo "Validating configuration..."

# Check .env.example exists
if [ ! -f ".env.example" ]; then
  echo "❌ Missing .env.example"
  exit 1
fi

# Check config.js has API_ROUTES
if ! grep -q "API_ROUTES" src/config.js; then
  echo "❌ API_ROUTES not found in config.js"
  exit 1
fi

# Check no hardcoded localhost in components
if grep -r "localhost:800" src/components/; then
  echo "⚠️  Found hardcoded localhost URLs in components"
fi

echo "✅ Configuration validation passed"
```

## 🎯 Summary

**Golden Rules:**
1. **One source of truth** - `config.js` for all routes
2. **Environment variables** - Never hardcode URLs
3. **Validate on startup** - Catch errors early
4. **Document everything** - `.env.example` for teammates
5. **Use patterns consistently** - Import from config, use API_ROUTES

**When adding new features:**
- Think: "Does this need a new API endpoint?"
- If yes: Add to backend URLs → Add to config.js → Use in component
- Never skip the config.js step!

---

**Result:** Zero URL mismatch errors, easy environment switching, happy developers! 🎉
