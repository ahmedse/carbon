mg # RBAC Hardening Plan — Post-MVP Priority Fix

**Date:** 2026-07-24  
**Priority:** P0 (Production Blocker)  
**Status:** Planning

---

## Problem Statement

Currently all Carbon navigation items are set to `role: '*'` (public access), defeating the manifest role system.

**Current State (lines 52-72 in manifest.js):**
```javascript
items: [
  { label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
  { label: 'My Portal',          path: '/carbon/owner/portal',       role: '*' },
  // ... all items with role: '*'
  { label: 'Emission Factors',   path: '/carbon/admin/factors',      role: '*' },
]
```

**Root Cause:** Role filtering logic in ShellSidebar.jsx (lines 156-173) was broken—it tried to convert manifest role format (`carbon:data_owner`) to user perspective format (`data-owner`), but Ahmed's availablePerspectives array was empty or had different values.

**Temporary Fix Applied:** Set all items to `role: '*'` for development convenience.

**Why It's a Problem:**
- Security risk: non-admins see admin pages (Emission Factors, Reporting Periods)
- Users see navigation items they cannot use
- Violates platform app model principle (manifest roles should control access)

---

## Current Architecture

### Frontend: AuthContext → availablePerspectives

**File:** `carbon-frontend/src/auth/AuthContext.jsx` (lines 47, 78)

```javascript
const [availablePerspectives, setAvailablePerspectives] = useState([]);

// Fetched from backend endpoint: /accounts/me/context/
const fetchPerspectiveContext = async (token) => {
  const res = await fetch(`${baseUrl}/accounts/me/context/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  const data = await res.json();
  setAvailablePerspectives(data.perspectives || []);  // ← What are the values?
  return data;
};
```

**Key Question:** What values does backend return in `perspectives` array?
- Option A: `['data-owner', 'admin']` (short format)?
- Option B: `['carbon:data_owner', 'carbon:admin']` (manifest format)?
- Option C: Empty array (current bug)?

### Frontend: ShellSidebar Role Filter Logic

**File:** `carbon-frontend/src/shell/ShellSidebar.jsx` (lines 156-173)

```javascript
if (activeStudio === 'carbon') {
  const userRoles = availablePerspectives || [];
  items = items.filter(item => {
    // Always show items without role restriction
    if (!item.role || item.role === '*') return true;
    // Show dividers and groups always
    if (item.type === 'divider' || item.type === 'group') return true;
    // For regular items with role: check if user has that role
    // Match both full role format (carbon:data_owner) and short format (data-owner)
    if (item.role.includes(':')) {
      // Extract the role suffix after ':' and convert underscore to hyphen
      const roleSuffix = item.role.split(':')[1].replace(/_/g, '-');
      return userRoles.includes(roleSuffix) || userRoles.includes('admin');
    }
    return userRoles.includes(item.role);
  });
}
```

**Current Status:** Logic exists but `availablePerspectives` is likely not populated correctly from backend.

### Backend: What Should Provide Perspectives?

**Suspected Location:** `backend/accounts/views.py` or similar

Need to find endpoint `/accounts/me/context/` and verify it returns user roles.

---

## Implementation Plan

### Phase 1: Verify Backend Role Provision (Discovery)

**Goal:** Understand what backend currently returns for user roles

**Tasks:**

1. **G1.1 — Find backend endpoint that provides perspectives/roles**
   - Search for `/accounts/me/context/` endpoint implementation
   - Check `backend/accounts/views.py`, `urls.py`
   - Verify it returns roles in correct format

2. **G1.2 — Validate role data structure**
   - Does it return `perspectives: ['data-owner']` or `perspectives: ['carbon:data_owner']`?
   - Is Ahmed user actually getting roles assigned?
   - Check `ScopedRole` or role assignment model

3. **G1.3 — Test endpoint with Ahmed user**
   - Manually call endpoint: `GET /accounts/me/context/` with Ahmed's token
   - Verify response includes perspectives array with values

**Expected Output:**
```json
{
  "perspectives": ["data-owner", "admin"],  // or ["carbon:data_owner", "carbon:admin"]
  "org_units": [...],
  ...
}
```

---

### Phase 2: Fix Role Mapping (Frontend)

**Goal:** Make role filter logic work with whatever backend provides

**Tasks:**

1. **G2.1 — Update availablePerspectives population**
   
   **File:** `carbon-frontend/src/auth/AuthContext.jsx` (line 78)
   
   ```javascript
   // Add fallback for missing perspectives
   setAvailablePerspectives(data.perspectives || ['dashboards']);
   ```
   
   **Why:** If backend doesn't return perspectives, default to `['dashboards']` (read-only user)

2. **G2.2 — Normalize role format in ShellSidebar**
   
   **File:** `carbon-frontend/src/shell/ShellSidebar.jsx` (lines 158-172)
   
   ```javascript
   const userRoles = availablePerspectives || [];
   
   // Normalize user roles to short format (data-owner, analyst, admin)
   const normalizedUserRoles = userRoles.map(role => {
     if (role.includes(':')) {
       return role.split(':')[1].replace(/_/g, '-');
     }
     return role;
   });
   
   items = items.filter(item => {
     if (!item.role || item.role === '*') return true;
     if (item.type === 'divider' || item.type === 'group') return true;
     
     // Normalize item role
     const normalizedItemRole = item.role.includes(':')
       ? item.role.split(':')[1].replace(/_/g, '-')
       : item.role;
     
     // Check match
     return normalizedUserRoles.includes(normalizedItemRole);
   });
   ```

3. **G2.3 — Add console logging for debugging**
   
   ```javascript
   if (process.env.NODE_ENV === 'development') {
     console.log('[RBAC] User roles:', normalizedUserRoles);
     console.log('[RBAC] Filtered items:', items.map(i => i.label));
   }
   ```

---

### Phase 3: Fix Manifest Roles (Frontend)

**Goal:** Restore proper role declarations in manifest

**Tasks:**

1. **G3.1 — Update Carbon manifest navigation**
   
   **File:** `carbon-frontend/src/apps/carbon/manifest.js` (lines 52-72)
   
   **Before:**
   ```javascript
   items: [
     { label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
     { label: 'My Portal',          path: '/carbon/owner/portal',       role: '*' },
     { label: 'Emission Factors',   path: '/carbon/admin/factors',      role: '*' },
   ]
   ```
   
   **After:**
   ```javascript
   items: [
     { label: 'Dashboard',          path: '/carbon/dashboard',          role: '*' },
     { type: 'divider' },
     { type: 'group', label: 'Data Owner' },
     { label: 'My Portal',          path: '/carbon/owner/portal',       role: 'carbon:data_owner' },
     { label: 'My Dashboard',       path: '/carbon/owner/dashboard',    role: 'carbon:data_owner' },
     { label: 'My Assets',          path: '/carbon/owner/assets',       role: 'carbon:data_owner' },
     { type: 'divider' },
     { type: 'group', label: 'Data Entry' },
     { label: 'Data Entry Hub',     path: '/carbon/data-entry',         role: 'carbon:data_owner' },
     { type: 'divider' },
     { type: 'group', label: 'Reporting' },
     { label: 'Generate Report',    path: '/carbon/reporting/generate', role: 'carbon:analyst' },
     { label: 'Saved Reports',      path: '/carbon/reporting/saved',    role: 'carbon:analyst' },
     { label: 'Analytics',          path: '/carbon/analytics',          role: 'carbon:analyst' },
     { type: 'divider' },
     { type: 'group', label: 'Administration' },
     { label: 'Emission Factors',   path: '/carbon/admin/factors',      role: 'carbon:admin' },
     { label: 'Reporting Periods',  path: '/carbon/reporting/periods',  role: 'carbon:admin' },
   ]
   ```

---

### Phase 4: Backend Role Assignment (Optional — if needed)

**Goal:** Ensure Ahmed user has proper roles assigned

**Tasks:**

1. **G4.1 — Check if Ahmed has ScopedRole assignments**
   
   **File:** `backend/accounts/models.py` or similar
   
   Query:
   ```python
   user = User.objects.get(username='ahmed')
   roles = ScopedRole.objects.filter(user=user, is_active=True)
   # Should show assignments like (user=ahmed, group='admin', org_unit=...)
   ```

2. **G4.2 — Verify role returns in `/accounts/me/context/` endpoint**
   
   If endpoint doesn't include roles, update it:
   
   ```python
   @api_view(['GET'])
   def user_context(request):
       user = request.user
       roles = ScopedRole.objects.filter(user=user, is_active=True).values_list('group__name', flat=True)
       perspectives = []
       if 'admin_group' in roles:
           perspectives.append('admin')
       if 'data_owners_group' in roles:
           perspectives.append('data-owner')
       if 'analysts_group' in roles:
           perspectives.append('analyst')
       
       return Response({
           'perspectives': perspectives,
           'org_units': [...],
       })
   ```

---

## Testing Checklist

### Unit Tests (Frontend)

- [ ] Test role normalization: `carbon:data_owner` → `data-owner`
- [ ] Test filter with single role: user has `data-owner`, should see Data Owner items only
- [ ] Test filter with multi role: user has `data-owner` AND `analyst`, should see both groups
- [ ] Test filter with admin: user has `admin`, should see all items
- [ ] Test filter with no roles: user has empty perspectives, should see Dashboard only

### Integration Tests (Frontend + Backend)

- [ ] Ahmed logs in → gets admin perspectives → sees all items
- [ ] Data Owner logs in → gets `data-owner` perspective → sees Data Owner + Dashboard only
- [ ] Analyst logs in → gets `analyst` perspective → sees Reporting items only
- [ ] Dashboard always visible to everyone

### Manual Testing

- [ ] Log in as Ahmed → verify all 11 items visible in Carbon sidebar
- [ ] Log in as test-data-owner → verify only Data Owner group items visible
- [ ] Check browser console for role mapping debug logs
- [ ] Verify `/accounts/me/context/` returns perspectives for each user

---

## Files to Modify

**Frontend (Required):**
1. `carbon-frontend/src/auth/AuthContext.jsx` — Add fallback for empty perspectives
2. `carbon-frontend/src/shell/ShellSidebar.jsx` — Fix role normalization logic
3. `carbon-frontend/src/apps/carbon/manifest.js` — Restore role assignments

**Backend (Optional — if /accounts/me/context/ is broken):**
1. `backend/accounts/views.py` — Verify endpoint returns user roles
2. Add tests to verify role provisioning

---

## Success Criteria

✅ All 11 Carbon navigation items have proper `role` assignments (not `role: '*'`)  
✅ ShellSidebar correctly filters items based on user's `availablePerspectives`  
✅ Ahmed (admin) sees all 11 items  
✅ Data Owner user sees only Data Owner + Dashboard items  
✅ Analyst user sees only Reporting + Dashboard items  
✅ Browser console shows role mapping debug output (in dev mode)  
✅ Frontend build succeeds  
✅ No regressions in existing tests

---

## Implementation Worker Assignment

**Worker 1 (Backend — If needed):**
- Verify `/accounts/me/context/` endpoint returns user roles
- Add/fix role provisioning if missing

**Worker 2 (Frontend — Required):**
- Fix role normalization in ShellSidebar
- Update manifest with proper role assignments
- Add dev mode logging for debugging

**Phase 1 (Discovery) should be completed first** before implementing Phase 2-4.

---

## Reference Documents

- Audit findings: [`plans/CARBON_APP_CRITICAL_AUDIT.md:80-132`](plans/CARBON_APP_CRITICAL_AUDIT.md:80)
- Current manifest: [`carbon-frontend/src/apps/carbon/manifest.js:40-72`](carbon-frontend/src/apps/carbon/manifest.js:40)
- Current filter logic: [`carbon-frontend/src/shell/ShellSidebar.jsx:156-173`](carbon-frontend/src/shell/ShellSidebar.jsx:156)
- AuthContext: [`carbon-frontend/src/auth/AuthContext.jsx:47-90`](carbon-frontend/src/auth/AuthContext.jsx:47)
