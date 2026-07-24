# TASK: Platform RBAC + Admin Architecture Implementation

**Status:** Ready for Implementation  
**Priority:** P0 (Post-MVP Critical)  
**Context:** Based on holistic rethink in [`plans/PLATFORM_RBAC_ADMIN_ARCHITECTURE.md`](plans/PLATFORM_RBAC_ADMIN_ARCHITECTURE.md)

---

## Objective

Implement a comprehensive two-tier admin model:
1. **Platform Admin (Layer 2)** — System-wide RBAC control plane for ALL apps (users, groups, roles, org units)
2. **App Admin (Layer 3)** — Domain-specific configuration per app (Carbon: factors/periods/rules; Catalog: policies/domains)

Fix role provisioning backend + frontend filtering to make RBAC work correctly across all apps.

---

## Core Architecture Decisions

### Two-Tier Admin Model

**Platform Admin Studio** (`/admin/*` in activity bar)
- **Purpose:** Manage platform RBAC system (users, groups, org units, role assignments)
- **Scope:** Cross-app, system-wide
- **Who uses it:** Platform administrators, IT staff, superusers
- **Pages:** Users, Groups & Roles, Org Units, Access Control, Audit Log, Role Registry, Registered Apps

**App Admin Section** (within each app's sidebar)
- **Purpose:** Manage app-specific configuration and reference data
- **Scope:** Single app domain (Carbon, Catalog, etc.)
- **Who uses it:** App-specific admins (Carbon admin, Catalog steward)
- **Carbon Example:** Emission Factors, Reporting Periods, Calculation Rules
- **Catalog Example:** Governance Policies, Data Domains, DQ Rule Templates

### Critical Separation

| Feature | Platform Admin | App Admin |
|---------|----------------|-----------|
| Create user accounts | ✅ | ❌ |
| Assign roles to users | ✅ | ❌ |
| Manage org unit hierarchy | ✅ | ❌ |
| Configure emission factors | ❌ | ✅ (Carbon) |
| Configure reporting periods | ❌ | ✅ (Carbon) |
| Manage governance policies | ❌ | ✅ (Catalog) |
| View role audit log | ✅ | ❌ |

**Key Insight:** `carbon:admin` means "can configure Carbon settings" NOT "can assign users to Carbon roles"

---

## RBAC Flow

1. **Platform Admin creates user** → User exists but has no roles
2. **Platform Admin assigns role** → Creates `ScopedRole(user, group='carbon_data_owners_group', org_unit='Engineering')`
3. **Backend resolves perspective** → `/accounts/me/context/` returns `{perspectives: ['data-owner']}`
4. **Frontend filters navigation** → ShellSidebar shows Data Owner items, hides Admin items
5. **App admin configures domain** → Carbon admin manages factors/periods (cannot assign roles)

---

## Worker Split

- **Worker 1 (Backend):** Fix role provisioning endpoint, create Groups management API
- **Worker 2 (Frontend):** Rename Admin studio, create new admin pages, fix role filtering

---

# WORKER 1: Backend — Role Provisioning + Groups Management

## Context

**Current Problem:**
- `/accounts/me/context/` endpoint exists but may not return `perspectives` array correctly
- No API for managing Django Groups (roles) from frontend
- Group-to-perspective mapping is unclear

**Goal:**
- Fix `/accounts/me/context/` to return user roles correctly
- Create Groups API for Platform Admin to manage role definitions
- Ensure proper ScopedRole → perspective mapping

---

## G1: Fix `/accounts/me/context/` Endpoint

**File:** `backend/accounts/views.py`

### G1.1 — Update Perspective Mapping Logic

Locate the `me_context` view (around line 68):

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_context(request):
    """
    GET /api/v1/accounts/me/context/
    
    Returns user's available perspectives (roles) and visible org units.
    Used by frontend AuthContext to populate availablePerspectives state.
    
    Response:
    {
        "perspectives": ["admin", "data-owner"],
        "org_units": [3, 5, 7],
        "scoped_roles": [
            {"role": "admin", "org_unit": "Global", "is_active": true},
            {"role": "carbon_data_owners_group", "org_unit": "Engineering", "is_active": true}
        ]
    }
    """
    user = request.user
    from .rbac_utils import (
        get_visible_org_units,
        is_superuser,
        is_org_admin
    )
    from accounts.models import ScopedRole
    
    # Get all active scoped roles for this user
    scoped_roles = ScopedRole.objects.filter(
        user=user,
        is_active=True
    ).select_related('group', 'org_unit', 'module')
    
    # Map Django group names to frontend perspectives
    perspectives = set()
    scoped_roles_data = []
    
    for role in scoped_roles:
        group_name = role.group.name.lower()
        
        # Map to perspectives (normalize group names to perspective format)
        if 'admin' in group_name and 'carbon' not in group_name and 'catalog' not in group_name:
            # Platform admin (global)
            perspectives.add('admin')
        
        if 'data_owner' in group_name or 'dataowner' in group_name:
            perspectives.add('data-owner')
        
        if 'analyst' in group_name:
            perspectives.add('analyst')
        
        if 'steward' in group_name:
            perspectives.add('steward')
        
        if 'carbon' in group_name and 'admin' in group_name:
            perspectives.add('carbon-admin')
        
        if 'catalog' in group_name and 'admin' in group_name:
            perspectives.add('catalog-admin')
        
        # Build scoped roles response
        scoped_roles_data.append({
            'role': role.group.name,
            'org_unit': role.org_unit.name if role.org_unit else 'Global',
            'module': role.module.name if role.module else None,
            'is_active': role.is_active
        })
    
    # Get visible org units
    org_units = get_visible_org_units(user)
    
    return Response({
        'perspectives': list(perspectives),
        'org_units': [u.id for u in org_units],
        'scoped_roles': scoped_roles_data
    })
```

**Testing:**
```bash
# Test as ahmed (should have admin + data-owner perspectives)
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/accounts/me/context/
```

Expected response:
```json
{
  "perspectives": ["admin", "data-owner"],
  "org_units": [1, 2, 3],
  "scoped_roles": [
    {"role": "admin", "org_unit": "Global", "module": null, "is_active": true},
    {"role": "carbon_data_owners_group", "org_unit": "Engineering", "module": null, "is_active": true}
  ]
}
```

---

## G2: Create Groups Management API

**File:** `backend/accounts/views.py`

### G2.1 — Update GroupViewSet to Support CRUD

Currently `GroupViewSet` is read-only (line 142-149). Make it fully editable:

```python
class GroupViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing Django Groups (roles).
    
    Platform admins can:
    - List all groups (GET /api/v1/accounts/groups/)
    - Create new group (POST /api/v1/accounts/groups/)
    - Update group (PUT/PATCH /api/v1/accounts/groups/{id}/)
    - Delete group (DELETE /api/v1/accounts/groups/{id}/)
    
    Used by Platform Admin Studio → Groups & Roles page.
    """
    queryset = Group.objects.all().order_by('name')
    serializer_class = GroupSerializer
    permission_classes = [HasScopedRole]
    required_role = "admin"
    
    def destroy(self, request, *args, **kwargs):
        """
        Prevent deletion of system-critical groups.
        """
        group = self.get_object()
        protected_groups = ['admin', 'carbon_data_owners_group', 'carbon_analysts_group']
        
        if group.name in protected_groups:
            return Response(
                {'error': f'Cannot delete protected group: {group.name}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return super().destroy(request, *args, **kwargs)
```

**Serializer Update (if needed):**

Check `backend/accounts/serializers.py` for `GroupSerializer`:

```python
class GroupSerializer(serializers.ModelSerializer):
    """Serializer for Django Group model."""
    permissions_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Group
        fields = ['id', 'name', 'permissions', 'permissions_count', 'users_count']
        read_only_fields = ['id', 'permissions_count', 'users_count']
    
    def get_permissions_count(self, obj):
        return obj.permissions.count()
    
    def get_users_count(self, obj):
        from accounts.models import ScopedRole
        return ScopedRole.objects.filter(group=obj, is_active=True).values('user').distinct().count()
```

---

## G3: Create Role Registry Endpoint

**File:** `backend/accounts/views.py`

### G3.1 — Add `role_registry` View

Create new API view that reads all app manifests and returns role matrix:

```python
@api_view(['GET'])
@permission_classes([IsAuthenticated, HasScopedRole])
def role_registry(request):
    """
    GET /api/v1/accounts/role-registry/
    
    Returns all roles declared in app manifests across the platform.
    Used by Platform Admin Studio → Role Registry page.
    
    Response:
    {
        "apps": [
            {
                "id": "carbon",
                "name": "Carbon Footprint",
                "version": "1.0.0",
                "roles": [
                    {
                        "key": "carbon:data_owner",
                        "label": "Data Owner",
                        "scoped": true,
                        "description": "CRUD on assigned org-unit data"
                    }
                ]
            }
        ]
    }
    """
    from django.conf import settings
    from importlib import import_module
    
    role_data = []
    
    # Read APP_REGISTRY from settings (populated by shell startup)
    app_registry = getattr(settings, 'APP_REGISTRY', [])
    
    for app in app_registry:
        app_id = app.get('id')
        
        # Import app manifest
        try:
            manifest_module = import_module(f'{app_id}.manifest')
            manifest = getattr(manifest_module, 'default', None) or manifest_module.manifest
            
            roles = manifest.get('roles', [])
            
            role_data.append({
                'id': app_id,
                'name': manifest.get('name', app_id),
                'version': manifest.get('version', '1.0.0'),
                'roles': roles
            })
        except (ImportError, AttributeError):
            # App has no manifest or no roles
            continue
    
    return Response({'apps': role_data})
```

### G3.2 — Register URL

In `backend/accounts/urls.py`:

```python
from .views import role_registry

urlpatterns = [
    # ... existing routes
    path('role-registry/', role_registry, name='role-registry'),
]
```

**Testing:**
```bash
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/accounts/role-registry/
```

---

## G4: Testing Checklist

### Backend Tests

**File:** `backend/accounts/tests/test_rbac.py` (create if doesn't exist)

```python
from django.test import TestCase
from django.contrib.auth.models import User, Group
from accounts.models import ScopedRole
from mdm.models import OrgUnit
from rest_framework.test import APIClient

class RBACProvisioningTest(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(username='testuser', password='testpass')
        
        # Create groups
        self.admin_group = Group.objects.create(name='admin')
        self.data_owner_group = Group.objects.create(name='carbon_data_owners_group')
        
        # Create org unit
        self.org_unit = OrgUnit.objects.create(name='Engineering', code='ENG')
        
        # Create scoped roles
        ScopedRole.objects.create(user=self.user, group=self.admin_group, is_active=True)
        ScopedRole.objects.create(user=self.user, group=self.data_owner_group, org_unit=self.org_unit, is_active=True)
        
        self.client = APIClient()
        self.client.force_authenticate(user=self.user)
    
    def test_me_context_returns_perspectives(self):
        """Test /accounts/me/context/ returns correct perspectives array."""
        response = self.client.get('/api/v1/accounts/me/context/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('perspectives', data)
        self.assertIn('admin', data['perspectives'])
        self.assertIn('data-owner', data['perspectives'])
    
    def test_role_registry_returns_app_roles(self):
        """Test /accounts/role-registry/ returns Carbon roles."""
        response = self.client.get('/api/v1/accounts/role-registry/')
        self.assertEqual(response.status_code, 200)
        
        data = response.json()
        self.assertIn('apps', data)
        
        # Find Carbon app
        carbon_app = next((a for a in data['apps'] if a['id'] == 'carbon'), None)
        self.assertIsNotNone(carbon_app)
        self.assertIn('roles', carbon_app)
        self.assertGreater(len(carbon_app['roles']), 0)
```

Run tests:
```bash
python manage.py test accounts.tests.test_rbac
```

---

## Definition of Done (Worker 1)

- [ ] `/accounts/me/context/` returns correct `perspectives` array based on ScopedRole mappings
- [ ] GroupViewSet supports full CRUD operations
- [ ] Protected groups cannot be deleted (admin, carbon_data_owners_group, etc.)
- [ ] `/accounts/role-registry/` endpoint returns all app roles from manifests
- [ ] All endpoints have proper permission checks
- [ ] Backend tests pass (test_me_context, test_role_registry)
- [ ] Swagger docs updated

---

# WORKER 2: Frontend — Platform Admin Enhancement + Role Filtering

## Context

**Current State:**
- Admin studio exists but label is ambiguous ("Administration")
- No Groups management page
- No Role Registry page to see all app roles
- Role filtering logic exists in ShellSidebar but all items have `role: '*'`

**Goal:**
- Rename Admin studio to "Platform Admin"
- Create new admin pages (Groups, Role Registry, Registered Apps)
- Restore proper role assignments in Carbon manifest
- Fix role filtering in ShellSidebar

---

## G1: Rename Admin Studio to "Platform Admin"

**File:** `carbon-frontend/src/shell/useShellState.js`

### G1.1 — Update PLATFORM_STUDIOS Array

Locate the studios array (around line 18-25) and update label:

```javascript
const PLATFORM_STUDIOS = [
  { id: 'home',     label: 'Dashboard',      icon: DashboardIcon, path: '/dashboard' },
  { id: 'catalog',  label: 'Catalog',        icon: LayersIcon,    path: '/catalog' },
  { id: 'admin',    label: 'Platform Admin', icon: SecurityIcon,  path: '/admin' },  // ← Changed from "Administration"
  { id: 'settings', label: 'Settings',       icon: SettingsIcon,  path: '/settings' },
  { id: 'help',     label: 'Help',           icon: HelpIcon,      path: '/help' },
];
```

---

## G2: Create Platform Admin Sidebar Navigation

**File:** `carbon-frontend/src/shell/ShellSidebar.jsx`

### G2.1 — Add Admin Sidebar Items

Update `getSidebarItems` function to add admin navigation (around line 97-101):

```javascript
case 'admin':
  return [
    { label: 'Users',          path: '/admin/users',        icon: PeopleIcon,      role: 'admin' },
    { label: 'Groups & Roles', path: '/admin/groups',       icon: GroupIcon,       role: 'admin' },
    { label: 'Org Units',      path: '/admin/org-units',    icon: AccountTreeIcon, role: 'admin' },
    { label: 'Access Control', path: '/admin/access',       icon: SecurityIcon,    role: 'admin' },
    { label: 'Audit Log',      path: '/admin/audit',        icon: HistoryIcon,     role: 'admin' },
    { type: 'divider' },
    { type: 'group', label: 'App Management' },
    { label: 'Registered Apps', path: '/admin/apps',        icon: AppsIcon,        role: 'admin' },
    { label: 'Role Registry',   path: '/admin/role-matrix', icon: GridViewIcon,    role: 'admin' },
  ];
```

### G2.2 — Import New Icons

At top of file:

```javascript
import {
  // ... existing imports
  PeopleIcon,
  GroupIcon,
  SecurityIcon,
  HistoryIcon,
  AppsIcon,
  GridViewIcon,
} from '@mui/icons-material';
```

Map to actual MUI icons:
```javascript
import PeopleIcon from '@mui/icons-material/People';
import GroupIcon from '@mui/icons-material/Group';
import SecurityIcon from '@mui/icons-material/Security';
import HistoryIcon from '@mui/icons-material/History';
import AppsIcon from '@mui/icons-material/Apps';
import GridViewIcon from '@mui/icons-material/GridView';
import AccountTreeIcon from '@mui/icons-material/AccountTree';
```

---

## G3: Create Groups & Roles Page

**File:** `carbon-frontend/src/pages/admin/GroupsPage.jsx` (NEW)

```javascript
import React, { useState, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Button, Dialog, DialogTitle,
  DialogContent, DialogActions, TextField, IconButton, Chip, Alert
} from '@mui/material';
import { Add as AddIcon, Edit as EditIcon, Delete as DeleteIcon } from '@mui/icons-material';
import { useAuth } from '../../auth/AuthContext';

export default function GroupsPage() {
  const { token } = useAuth();
  const [groups, setGroups] = useState([]);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingGroup, setEditingGroup] = useState(null);
  const [formData, setFormData] = useState({ name: '' });
  const [error, setError] = useState('');

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/accounts/groups/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setGroups(data);
    } catch (err) {
      console.error('Failed to load groups:', err);
    }
  };

  const handleOpenDialog = (group = null) => {
    setEditingGroup(group);
    setFormData({ name: group ? group.name : '' });
    setDialogOpen(true);
    setError('');
  };

  const handleCloseDialog = () => {
    setDialogOpen(false);
    setEditingGroup(null);
    setFormData({ name: '' });
    setError('');
  };

  const handleSave = async () => {
    try {
      const url = editingGroup
        ? `http://localhost:8000/api/v1/accounts/groups/${editingGroup.id}/`
        : 'http://localhost:8000/api/v1/accounts/groups/';
      
      const method = editingGroup ? 'PUT' : 'POST';
      
      const res = await fetch(url, {
        method,
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(formData),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || 'Failed to save group');
      }

      await loadGroups();
      handleCloseDialog();
    } catch (err) {
      setError(err.message);
    }
  };

  const handleDelete = async (group) => {
    if (!confirm(`Delete group "${group.name}"? This cannot be undone.`)) return;

    try {
      const res = await fetch(`http://localhost:8000/api/v1/accounts/groups/${group.id}/`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` },
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.error || 'Failed to delete group');
      }

      await loadGroups();
    } catch (err) {
      alert(err.message);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 3 }}>
        <Typography variant="h4">Groups & Roles</Typography>
        <Button variant="contained" startIcon={<AddIcon />} onClick={() => handleOpenDialog()}>
          Create Group
        </Button>
      </Box>

      <Alert severity="info" sx={{ mb: 3 }}>
        Groups define roles that can be assigned to users. Groups map to app-specific roles declared in manifests (e.g., carbon:data_owner → carbon_data_owners_group).
      </Alert>

      <Card>
        <CardContent>
          <TableContainer>
            <Table>
              <TableHead>
                <TableRow>
                  <TableCell>Group Name</TableCell>
                  <TableCell align="center">Users</TableCell>
                  <TableCell align="center">Permissions</TableCell>
                  <TableCell align="right">Actions</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {groups.map((group) => (
                  <TableRow key={group.id}>
                    <TableCell>
                      <Typography variant="body1" fontWeight="medium">
                        {group.name}
                      </Typography>
                    </TableCell>
                    <TableCell align="center">
                      <Chip label={group.users_count || 0} size="small" />
                    </TableCell>
                    <TableCell align="center">
                      <Chip label={group.permissions_count || 0} size="small" color="primary" />
                    </TableCell>
                    <TableCell align="right">
                      <IconButton size="small" onClick={() => handleOpenDialog(group)}>
                        <EditIcon />
                      </IconButton>
                      <IconButton size="small" color="error" onClick={() => handleDelete(group)}>
                        <DeleteIcon />
                      </IconButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </CardContent>
      </Card>

      <Dialog open={dialogOpen} onClose={handleCloseDialog} maxWidth="sm" fullWidth>
        <DialogTitle>{editingGroup ? 'Edit Group' : 'Create Group'}</DialogTitle>
        <DialogContent>
          {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
          <TextField
            label="Group Name"
            fullWidth
            margin="normal"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., carbon_analysts_group"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={handleCloseDialog}>Cancel</Button>
          <Button variant="contained" onClick={handleSave}>
            {editingGroup ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

---

## G4: Create Role Registry Page

**File:** `carbon-frontend/src/pages/admin/RoleRegistryPage.jsx` (NEW)

```javascript
import React, { useState, useEffect } from 'react';
import {
  Box, Card, CardContent, Typography, Table, TableBody, TableCell,
  TableContainer, TableHead, TableRow, Chip, Alert, Accordion,
  AccordionSummary, AccordionDetails
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import CheckCircleIcon from '@mui/icons-material/CheckCircle';
import CancelIcon from '@mui/icons-material/Cancel';
import { useAuth } from '../../auth/AuthContext';

export default function RoleRegistryPage() {
  const { token } = useAuth();
  const [roleData, setRoleData] = useState([]);

  useEffect(() => {
    loadRoleRegistry();
  }, []);

  const loadRoleRegistry = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/v1/accounts/role-registry/', {
        headers: { Authorization: `Bearer ${token}` },
      });
      const data = await res.json();
      setRoleData(data.apps || []);
    } catch (err) {
      console.error('Failed to load role registry:', err);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Role Registry</Typography>
      
      <Alert severity="info" sx={{ mb: 3 }}>
        This page shows all roles declared by apps in their manifests. Platform admins can assign these roles to users via Access Control.
      </Alert>

      {roleData.map((app) => (
        <Accordion key={app.id} defaultExpanded={app.id === 'carbon'}>
          <AccordionSummary expandIcon={<ExpandMoreIcon />}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, width: '100%' }}>
              <Typography variant="h6">{app.name}</Typography>
              <Chip label={`${app.roles.length} roles`} size="small" color="primary" />
              <Typography variant="caption" color="text.secondary" sx={{ ml: 'auto' }}>
                v{app.version}
              </Typography>
            </Box>
          </AccordionSummary>
          <AccordionDetails>
            <TableContainer>
              <Table size="small">
                <TableHead>
                  <TableRow>
                    <TableCell>Role Key</TableCell>
                    <TableCell>Label</TableCell>
                    <TableCell align="center">Scoped</TableCell>
                    <TableCell>Description</TableCell>
                  </TableRow>
                </TableHead>
                <TableBody>
                  {app.roles.map((role) => (
                    <TableRow key={role.key}>
                      <TableCell>
                        <Typography variant="body2" fontFamily="monospace">
                          {role.key}
                        </Typography>
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" fontWeight="medium">
                          {role.label}
                        </Typography>
                      </TableCell>
                      <TableCell align="center">
                        {role.scoped ? (
                          <CheckCircleIcon color="success" fontSize="small" />
                        ) : (
                          <CancelIcon color="disabled" fontSize="small" />
                        )}
                      </TableCell>
                      <TableCell>
                        <Typography variant="body2" color="text.secondary">
                          {role.description}
                        </Typography>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            </TableContainer>
          </AccordionDetails>
        </Accordion>
      ))}

      {roleData.length === 0 && (
        <Alert severity="warning">No apps with roles found.</Alert>
      )}
    </Box>
  );
}
```

---

## G5: Create Registered Apps Page

**File:** `carbon-frontend/src/pages/admin/RegisteredAppsPage.jsx` (NEW)

```javascript
import React from 'react';
import {
  Box, Card, CardContent, Typography, Grid, Chip, Alert
} from '@mui/material';
import { APP_REGISTRY } from '../../apps/registry';

export default function RegisteredAppsPage() {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h4" gutterBottom>Registered Apps</Typography>
      
      <Alert severity="info" sx={{ mb: 3 }}>
        These are all apps registered in the platform APP_REGISTRY. Each app declares its own manifest with roles, navigation, and ontology.
      </Alert>

      <Grid container spacing={3}>
        {APP_REGISTRY.map((app) => (
          <Grid item xs={12} md={6} lg={4} key={app.id}>
            <Card>
              <CardContent>
                <Typography variant="h6" gutterBottom>{app.name}</Typography>
                <Typography variant="body2" color="text.secondary" paragraph>
                  {app.description}
                </Typography>
                <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mb: 2 }}>
                  <Chip label={`v${app.version}`} size="small" />
                  <Chip label={app.id} size="small" variant="outlined" />
                </Box>
                <Typography variant="caption" color="text.secondary">
                  Base Path: <code>{app.basePath}</code>
                </Typography>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
    </Box>
  );
}
```

---

## G6: Add Routes for New Pages

**File:** `carbon-frontend/src/App.jsx`

Add imports:
```javascript
import GroupsPage from './pages/admin/GroupsPage';
import RoleRegistryPage from './pages/admin/RoleRegistryPage';
import RegisteredAppsPage from './pages/admin/RegisteredAppsPage';
```

Add routes in admin section:
```javascript
{/* Platform Admin Routes */}
<Route path="/admin/users" element={<AdminRoute><UsersPage /></AdminRoute>} />
<Route path="/admin/groups" element={<AdminRoute><GroupsPage /></AdminRoute>} />
<Route path="/admin/org-units" element={<AdminRoute><OrgUnitsPage /></AdminRoute>} />
<Route path="/admin/org-units/:orgUnitId" element={<AdminRoute><OrgUnitDetailPage /></AdminRoute>} />
<Route path="/admin/access" element={<AdminRoute><AccessControlPage /></AdminRoute>} />
<Route path="/admin/audit" element={<AdminRoute><RoleAssignmentAuditPage /></AdminRoute>} />
<Route path="/admin/role-matrix" element={<AdminRoute><RoleRegistryPage /></AdminRoute>} />
<Route path="/admin/apps" element={<AdminRoute><RegisteredAppsPage /></AdminRoute>} />
```

---

## G7: Restore Proper Roles in Carbon Manifest

**File:** `carbon-frontend/src/apps/carbon/manifest.js`

### G7.1 — Update Navigation Items with Correct Roles

Locate navigation items (around line 52-73) and restore role assignments:

```javascript
navigation: {
  label: 'Carbon Footprint',
  items: [
    { label: 'Dashboard',          path: '/carbon/dashboard',          icon: 'DashboardIcon',     role: '*' },
    { type: 'divider' },
    { type: 'group', label: 'Data Owner' },
    { label: 'My Portal',          path: '/carbon/owner/portal',       icon: 'BusinessIcon',      role: 'carbon:data_owner' },
    { label: 'My Dashboard',       path: '/carbon/owner/dashboard',    icon: 'BarChartIcon',      role: 'carbon:data_owner' },
    { label: 'My Assets',          path: '/carbon/owner/assets',       icon: 'FactoryIcon',       role: 'carbon:data_owner' },
    { type: 'divider' },
    { type: 'group', label: 'Data Entry' },
    { label: 'Data Entry Hub',     path: '/carbon/data-entry',         icon: 'EditNoteIcon',      role: 'carbon:data_owner' },
    { type: 'divider' },
    { type: 'group', label: 'Reporting' },
    { label: 'Generate Report',    path: '/carbon/reports/generate',   icon: 'AssessmentIcon',    role: 'carbon:analyst' },
    { label: 'Saved Reports',      path: '/carbon/reports/saved',      icon: 'FolderIcon',        role: 'carbon:analyst' },
    { type: 'divider' },
    { type: 'group', label: 'Administration' },
    { label: 'Emission Factors',   path: '/carbon/admin/factors',      icon: 'ScienceIcon',       role: 'carbon:admin' },
    { label: 'Reporting Periods',  path: '/carbon/reporting/periods',  icon: 'CalendarMonthIcon', role: 'carbon:admin' },
  ],
},
```

**Key Changes:**
- Data Owner items: `role: 'carbon:data_owner'`
- Reporting items: `role: 'carbon:analyst'`
- Administration items: `role: 'carbon:admin'`
- Dashboard remains: `role: '*'` (public to all authenticated users)

---

## G8: Fix Role Filtering in ShellSidebar

**File:** `carbon-frontend/src/shell/ShellSidebar.jsx`

### G8.1 — Update Role Filtering Logic

The logic already exists (lines 156-173) but needs verification. Ensure proper normalization:

```javascript
// Filter items by user role (around line 156)
if (activeStudio === 'carbon') {
  const userRoles = availablePerspectives || [];
  
  items = items.filter(item => {
    // Always show dividers, groups, and items with no role restriction
    if (!item.role || item.role === '*') return true;
    if (item.type === 'divider' || item.type === 'group') return true;
    
    // Normalize manifest role format to perspective format
    if (item.role.includes(':')) {
      // carbon:data_owner → data-owner
      const roleSuffix = item.role.split(':')[1].replace(/_/g, '-');
      return userRoles.includes(roleSuffix) || userRoles.includes('admin');
    }
    
    // Direct match (for platform roles)
    return userRoles.includes(item.role) || userRoles.includes('admin');
  });
}
```

**Testing:**
1. Login as user with only `carbon:data_owner` role
2. Should see: Dashboard, Data Owner group, Data Entry Hub
3. Should NOT see: Generate Report, Emission Factors, Reporting Periods

---

## G9: Create Documentation

**File:** `docs/RBAC_APP_ADMIN_GUIDELINES.md` (NEW)

```markdown
# RBAC + App Admin Guidelines

**Last Updated:** 2026-07-24

---

## Core Principle: Two-Tier Admin Model

### Platform Admin (Layer 2 — System-Wide)
**Location:** `/admin/*` studio in activity bar  
**Purpose:** Manage platform RBAC system (users, groups, org units, role assignments)  
**Who:** Platform administrators, IT staff, superusers  

**Responsibilities:**
- Create/delete user accounts
- Define Django Groups (roles)
- Manage organizational hierarchy
- Assign users to roles + org units
- View audit logs of role changes

**Pages:**
- Users — CRUD user accounts
- Groups & Roles — Manage Django Groups
- Org Units — Manage organizational hierarchy
- Access Control — Assign ScopedRoles
- Audit Log — View role assignment history
- Role Registry — See all app-declared roles
- Registered Apps — View APP_REGISTRY

---

### App Admin (Layer 3 — Domain-Specific)
**Location:** Within each app's sidebar (e.g., Carbon → Administration group)  
**Purpose:** Manage app-specific configuration and reference data  
**Who:** App-specific admins (Carbon admin, Catalog steward)  

**Carbon Example Responsibilities:**
- Manage emission factors (reference data)
- Configure reporting periods (workflow config)
- Define calculation rules (business logic)

**Catalog Example Responsibilities:**
- Manage governance policies
- Configure data domains
- Define DQ rule templates

**DOES NOT:**
- Create/delete users
- Assign roles to users
- Manage org unit hierarchy

---

## Decision Matrix

| Feature | Platform Admin | App Admin |
|---------|----------------|-----------|
| Create user accounts | ✅ | ❌ |
| Assign roles to users | ✅ | ❌ |
| Manage org unit hierarchy | ✅ | ❌ |
| Configure emission factors | ❌ | ✅ (Carbon) |
| Configure reporting periods | ❌ | ✅ (Carbon) |
| Manage governance policies | ❌ | ✅ (Catalog) |
| Manage data domains | ❌ | ✅ (Catalog) |
| View role audit log | ✅ | ❌ |

---

## RBAC Flow

1. **Platform Admin creates user** → User exists but has no roles
2. **Platform Admin assigns role** → Creates `ScopedRole(user, group='carbon_data_owners_group', org_unit='Engineering')`
3. **Backend resolves perspective** → `/accounts/me/context/` returns `{perspectives: ['data-owner']}`
4. **Frontend filters navigation** → Shows Data Owner items, hides Admin items
5. **App admin configures domain** → Carbon admin manages factors/periods (cannot assign roles)

---

## For App Developers

When creating a new app:

1. **Declare roles in manifest:**
   ```javascript
   roles: [
     { key: 'myapp:editor', label: 'Editor', scoped: true, description: 'Can edit data' },
     { key: 'myapp:admin', label: 'App Admin', scoped: false, description: 'Can configure app settings' },
   ]
   ```

2. **Create Django Groups in backend:**
   ```python
   Group.objects.get_or_create(name='myapp_editors_group')
   Group.objects.get_or_create(name='myapp_admins_group')
   ```

3. **Add app-specific admin pages to app sidebar:**
   ```javascript
   { type: 'group', label: 'Administration' },
   { label: 'App Settings', path: '/myapp/admin/settings', role: 'myapp:admin' },
   ```

4. **Do NOT add user management pages** — that's platform-level

---

## Key Insight

**`carbon:admin` means "can configure Carbon settings" NOT "can assign users to Carbon roles"**

Platform admin assigns roles. App admin configures domain.
```

---

## Definition of Done (Worker 2)

- [ ] Admin studio renamed to "Platform Admin"
- [ ] Platform Admin sidebar shows: Users, Groups & Roles, Org Units, Access Control, Audit Log, Role Registry, Registered Apps
- [ ] GroupsPage.jsx created and functional (CRUD groups)
- [ ] RoleRegistryPage.jsx created (shows all app roles from manifests)
- [ ] RegisteredAppsPage.jsx created (shows APP_REGISTRY)
- [ ] All routes added to App.jsx with AdminRoute protection
- [ ] Carbon manifest roles restored (data_owner, analyst, admin)
- [ ] ShellSidebar role filtering works correctly
- [ ] `docs/RBAC_APP_ADMIN_GUIDELINES.md` created
- [ ] Build succeeds with no errors

---

## Testing Checklist

### Frontend Integration Tests

1. **Platform Admin Studio:**
   - [ ] Activity bar shows "Platform Admin" label
   - [ ] Click Platform Admin → sidebar shows 7 items (Users, Groups, Org Units, Access Control, Audit Log, Role Registry, Registered Apps)
   - [ ] All pages load without errors

2. **Groups & Roles Page:**
   - [ ] Lists all Django Groups
   - [ ] Can create new group
   - [ ] Can edit group name
   - [ ] Cannot delete protected groups (admin, carbon_data_owners_group)
   - [ ] Shows user count per group

3. **Role Registry Page:**
   - [ ] Shows Carbon app with 3 roles (data_owner, analyst, admin)
   - [ ] Shows Catalog app with roles (if exists)
   - [ ] Displays role key, label, scoped status, description

4. **Carbon Role Filtering:**
   - [ ] Login as `carbon:data_owner` user → sees Data Owner group items only
   - [ ] Login as `carbon:analyst` user → sees Reporting group items only
   - [ ] Login as `carbon:admin` user → sees Administration group items only
   - [ ] Login as platform `admin` → sees all items

5. **Backend Integration:**
   - [ ] `/accounts/me/context/` returns correct perspectives array
   - [ ] `/accounts/role-registry/` returns Carbon roles

---

## Files to Create/Modify

### Backend (Worker 1)
- **Modify:** `backend/accounts/views.py` — Fix `me_context`, update `GroupViewSet`, add `role_registry` view
- **Modify:** `backend/accounts/serializers.py` — Update `GroupSerializer` with counts
- **Modify:** `backend/accounts/urls.py` — Register `role-registry` endpoint
- **Create:** `backend/accounts/tests/test_rbac.py` — Backend tests

### Frontend (Worker 2)
- **Modify:** `carbon-frontend/src/shell/useShellState.js` — Rename Admin studio label
- **Modify:** `carbon-frontend/src/shell/ShellSidebar.jsx` — Add admin sidebar items
- **Modify:** `carbon-frontend/src/apps/carbon/manifest.js` — Restore role assignments
- **Modify:** `carbon-frontend/src/App.jsx` — Add routes for new pages
- **Create:** `carbon-frontend/src/pages/admin/GroupsPage.jsx`
- **Create:** `carbon-frontend/src/pages/admin/RoleRegistryPage.jsx`
- **Create:** `carbon-frontend/src/pages/admin/RegisteredAppsPage.jsx`
- **Create:** `docs/RBAC_APP_ADMIN_GUIDELINES.md`

---

## References

- Architecture: [`plans/PLATFORM_RBAC_ADMIN_ARCHITECTURE.md`](plans/PLATFORM_RBAC_ADMIN_ARCHITECTURE.md)
- Role Filtering: [`plans/RBAC-HARDENING-PLAN.md`](plans/RBAC-HARDENING-PLAN.md)
- Platform Model: [`docs/PLATFORM_APP_MODEL.md`](docs/PLATFORM_APP_MODEL.md)
- Existing Task: [`TASK-CARBON-ARCHITECTURE-FIXES.md`](TASK-CARBON-ARCHITECTURE-FIXES.md)

---

## Success Criteria

✅ Platform Admin studio clearly separated from app-specific admin  
✅ Role provisioning works: users with `carbon:data_owner` see correct navigation  
✅ Platform admins can manage groups, view role registry, see registered apps  
✅ Carbon manifest roles restored (no more `role: '*'` bypass)  
✅ Documentation exists for future app developers  
✅ All tests pass (backend + frontend integration)  
✅ Build succeeds with no errors
