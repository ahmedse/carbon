# ============================================================================
# CONFIGURATION SYSTEM - UNIFIED SOURCE OF TRUTH
# ============================================================================
# This document defines the configuration architecture for the Carbon platform
# ============================================================================

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    CONFIGURATION FLOW                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Backend (.env)              Frontend (.env)                │
│  ──────────────              ────────────────               │
│  DJANGO_API_PREFIX           VITE_API_BASE_URL              │
│  = /api/v1/                  = http://localhost:8000/api/v1/│
│                                                              │
│         │                            │                       │
│         ▼                            ▼                       │
│                                                              │
│  Backend (urls.py)           Frontend (config.js)           │
│  ──────────────              ────────────────               │
│  path('api/v1/', ...)        export const API_BASE_URL      │
│                              export const API_ROUTES         │
│                                                              │
│         │                            │                       │
│         └────────────┬───────────────┘                       │
│                      ▼                                       │
│                                                              │
│              HTTP Requests                                   │
│              http://localhost:8000/api/v1/...                │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## File Structure

### Backend Configuration

```
backend/
├── .env                          # MAIN CONFIG - Single source of truth
├── .env.example                  # Template for team
├── config/
│   ├── settings.py              # Reads from .env
│   └── urls.py                  # URL routing (uses settings)
```

### Frontend Configuration

```
carbon-frontend/
├── .env                          # MAIN CONFIG - Single source of truth
├── .env.example                  # Template for team
└── src/
    ├── config.js                # Central config (reads .env)
    └── api/
        ├── api.js               # Uses config.js
        └── aiCopilot.js         # Uses config.js
```

## Configuration Files

### 1. Backend .env (MUST MATCH!)

```bash
# API Configuration
DJANGO_API_PREFIX=/api/v1/

# Server
# Backend runs on port 8000 by default
# URL: http://localhost:8000/api/v1/

# CORS - Allow frontend origins
CORS_ALLOWED_ORIGINS=http://localhost:5173,http://localhost:3000
CSRF_TRUSTED_ORIGINS=http://localhost:5173,http://localhost:3000
```

### 2. Frontend .env (MUST MATCH!)

```bash
# MUST match backend: http://localhost:8000 + DJANGO_API_PREFIX
VITE_API_BASE_URL=http://localhost:8000/api/v1/
```

### 3. Frontend config.js (Reads .env)

```javascript
// NEVER hardcode URLs - ALWAYS use import.meta.env
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;

// All API routes relative to API_BASE_URL
export const API_ROUTES = {
  // Auth
  token: "token/",
  tokenRefresh: "token/refresh/",
  
  // Core
  projects: "core/projects/",
  
  // AI Copilot
  aiChat: "ai/chat/send_message/",
  aiInsights: "ai/insights/",
  // ...
};
```

### 4. Backend urls.py (Reads settings)

```python
from django.urls import path, include

urlpatterns = [
    # API v1 routes
    path('api/v1/token/', ...),
    path('api/v1/core/', include('core.urls')),
    path('api/v1/ai/', include('ai_copilot.urls')),
    # ...
]
```

## URL Resolution Examples

### Example 1: AI Chat Endpoint

**Backend .env:**
```
DJANGO_API_PREFIX=/api/v1/
```

**Backend urls.py:**
```python
path('api/v1/ai/', include('ai_copilot.urls'))
# ai_copilot/urls.py has: path('chat/send_message/', ...)
```

**Result:** `http://localhost:8000/api/v1/ai/chat/send_message/`

**Frontend .env:**
```
VITE_API_BASE_URL=http://localhost:8000/api/v1/
```

**Frontend config.js:**
```javascript
API_ROUTES.aiChat = "ai/chat/send_message/"
```

**Frontend usage:**
```javascript
apiFetch(API_ROUTES.aiChat)
// Resolves to: http://localhost:8000/api/v1/ai/chat/send_message/
```

### Example 2: Projects Endpoint

**Full URL:** `http://localhost:8000/api/v1/core/projects/`

**Breakdown:**
- Host: `http://localhost:8000`
- API Prefix: `/api/v1/` (from backend .env)
- App route: `core/` (from urls.py)
- Endpoint: `projects/` (from core/urls.py)

## Validation Rules

### ✅ CORRECT Configuration

**Backend .env:**
```bash
DJANGO_API_PREFIX=/api/v1/
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

**Frontend .env:**
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1/
```

**Frontend config.js:**
```javascript
export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL;
export const API_ROUTES = {
  aiChat: "ai/chat/send_message/",
};
```

**Frontend usage:**
```javascript
import { API_ROUTES } from '../config';
apiFetch(API_ROUTES.aiChat);
```

### ❌ WRONG Configuration

**Hardcoded URLs:**
```javascript
const url = "http://localhost:8000/api/v1/ai/chat/"; // WRONG!
```

**Mismatched prefixes:**
```bash
# Backend
DJANGO_API_PREFIX=/carbon-api/

# Frontend
VITE_API_BASE_URL=http://localhost:8000/api/v1/  # WRONG - doesn't match!
```

**Multiple sources:**
```javascript
// file1.js
const API_URL = "/api/v1/";

// file2.js
const API_URL = "/carbon-api/";  // WRONG - inconsistent!
```

## Validation Checklist

Before starting the application:

- [ ] Backend .env has `DJANGO_API_PREFIX=/api/v1/`
- [ ] Frontend .env has `VITE_API_BASE_URL=http://localhost:8000/api/v1/`
- [ ] Both .env files match (host + port + prefix)
- [ ] CORS origins include frontend URL (http://localhost:5173)
- [ ] No hardcoded URLs in any code files
- [ ] All API calls use API_ROUTES from config.js

## Troubleshooting

### Error: 404 Not Found

**Check:**
1. Backend .env: `DJANGO_API_PREFIX` value
2. Frontend .env: `VITE_API_BASE_URL` value
3. Do they match?
4. Did you restart both servers after changing?

### Error: CORS Error

**Check:**
1. Backend .env: `CORS_ALLOWED_ORIGINS` includes frontend URL
2. Frontend runs on http://localhost:5173 (default Vite port)
3. Backend .env includes: `http://localhost:5173`

### Error: Connection Refused

**Check:**
1. Backend server running? `python manage.py runserver`
2. Running on correct port? Default is 8000
3. Frontend .env uses correct port?

## Environment-Specific Configs

### Development

**Backend .env:**
```bash
DJANGO_ENV=development
DEBUG=True
DJANGO_API_PREFIX=/api/v1/
CORS_ALLOWED_ORIGINS=http://localhost:5173
```

**Frontend .env:**
```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1/
```

### Staging

**Backend .env.staging:**
```bash
DJANGO_ENV=staging
DEBUG=False
DJANGO_API_PREFIX=/api/v1/
CORS_ALLOWED_ORIGINS=https://staging.example.com
```

**Frontend .env.staging:**
```bash
VITE_API_BASE_URL=https://api-staging.example.com/api/v1/
```

### Production

**Backend .env.production:**
```bash
DJANGO_ENV=production
DEBUG=False
DJANGO_API_PREFIX=/api/v1/
CORS_ALLOWED_ORIGINS=https://app.example.com
DJANGO_SECURE_SSL_REDIRECT=True
```

**Frontend .env.production:**
```bash
VITE_API_BASE_URL=https://api.example.com/api/v1/
```

## Quick Reference

### Full URL Structure

```
http://localhost:8000/api/v1/ai/chat/send_message/
│      │          │    │   │  │   └─ Endpoint
│      │          │    │   │  └───── View path
│      │          │    │   └──────── App path
│      │          │    └──────────── API prefix (from .env)
│      │          └───────────────── Port
│      └──────────────────────────── Host
└─────────────────────────────────── Protocol
```

### Configuration Flow

1. Edit `backend/.env` → Set `DJANGO_API_PREFIX`
2. Edit `frontend/.env` → Set `VITE_API_BASE_URL` to match
3. Restart backend: `python manage.py runserver`
4. Restart frontend: `npm run dev`
5. Check console for "✅ API reachable" message

## GOLDEN RULES

1. **ONE SOURCE PER ENVIRONMENT**: Never hardcode, always use .env
2. **MUST MATCH**: Backend prefix + Frontend base URL must align
3. **USE CONFIG**: Always import from config.js, never hardcode
4. **RESTART REQUIRED**: .env changes need server restart
5. **DOCUMENT CHANGES**: Update .env.example when adding variables

---

**Last Updated:** January 13, 2026
**Status:** Unified configuration system implemented
