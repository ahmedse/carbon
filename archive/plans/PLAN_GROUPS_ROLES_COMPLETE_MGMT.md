# Complete Groups & Roles Management - Implementation Plan

**Date:** 2026-07-24  
**Context:** Current Groups & Roles page is too basic - needs comprehensive CRUD with detail pages, clear role type distinction, and member management  
**Status:** Planning

---

## Current State Analysis

### What Exists Now

**Frontend:**
- `GroupsPage.jsx` - Simple table with group name, users count, permissions count
- Basic create/edit dialog (only group name field)
- No detail page, no member management, no clear role types

**Backend:**
- `GroupViewSet` in `accounts/views.py` - Full CRUD API
- `GroupSerializer` - Returns id, name, permissions_count, users_count
- `ScopedRoleViewSet` - Manages role assignments
- Protected groups: `admin`, `carbon_data_owners_group`, `carbon_analysts_group`

### Problems

1. **No Detail View** - Can't drill into a group to see members and assignments
2. **No Member Management** - Can't see/manage users with this role
3. **No Scoped Assignments View** - Can't see org-unit scoped assignments for a role
4. **No Role Type Clarity** - Platform roles vs app-scoped roles not distinguished
5. **No Description Field** - Groups have no documentation

---

## Role Type Architecture (Crystal Clear)

### 1. Platform Global Roles (Django Groups)

**Purpose:** Platform administration and cross-cutting concerns  
**Naming:** No prefix (e.g., `admin`, `audit`, `steward`)  
**Scoping:** Always global OR can be org-scoped via ScopedRole  
**Examples:**

| Group Name | Label | Type | Description |
|------------|-------|------|-------------|
| `admin` | Platform Admin | Global | Full platform administration |
| `admins_group` | Platform Admin (legacy) | Global | Legacy admin group |
| `audit` | Audit Viewer | Global | View audit logs across platform |
| `steward` | Data Steward | Scoped | Manage master data in org unit |

### 2. App-Scoped Roles (Django Groups with App Prefix)

**Purpose:** App-specific permissions  
**Naming:** `{app_id}_{role_key}` (e.g., `carbon_data_owner`)  
**Scoping:** Defined in app manifest (`scoped: true/false`)  
**Manifest Mapping:** `carbon:data_owner` → Django Group `carbon_data_owner`

**Examples (Carbon App):**

| Manifest Role | Group Name | Label | Scoped | Description |
|---------------|------------|-------|--------|-------------|
| `carbon:data_owner` | `carbon_data_owner` | Carbon Data Owner | Yes | Manage emissions for assigned org units |
| `carbon:analyst` | `carbon_analyst` | Carbon Analyst | Yes | Run reports for assigned org units |
| `carbon:admin` | `carbon_admin` | Carbon Admin | No | Configure Carbon app settings (factors, periods) |

### 3. Assignment Types (ScopedRole Model)

| org_unit | module | Meaning | Example |
|----------|--------|---------|---------|
| NULL | NULL | **Global** - applies everywhere | Superuser admin role |
| SET | NULL | **Org-scoped** - applies to org unit and descendants | Ali → carbon_data_owner @ Transportation/Fleet |
| NULL | SET | **Module-scoped** - applies to specific module | (Future use) |
| SET | SET | **Module+Org-scoped** - module within org unit | (Future use) |

---

## Proposed Solution: Full Groups & Roles Management

### Architecture Pattern

Use the **OrgUnits pattern** as the gold standard:
- Grid/table list view (GroupsPage)
- Detail page with tabs (GroupDetailPage)
- BaseDetailPage component for layout
- Separate tab components for concerns

### Page Structure

```
Platform Admin > Groups & Roles
├── GroupsPage.jsx (Grid View)
│   ├── Enhanced table with role type, category, users, scoped assignments
│   ├── Click row → navigate to detail
│   └── Create/Edit/Delete actions
│
└── GroupDetailPage.jsx (Detail View with Tabs)
    ├── DetailHeader (group name, type badge, description)
    ├── Main Tabs:
    │   ├── Overview Tab (metadata, type, protected status, created date)
    │   ├── Members Tab (users with this role - global assignments)
    │   ├── Scoped Assignments Tab (user + org unit combinations)
    │   └── Edit Tab (rename, edit description, manage properties)
    └── Metrics Panel (optional):
        └── Summary (total users, total assignments, coverage stats)
```

---

## Implementation Plan

### Phase 1: Backend Enhancements

#### 1.1 Enhance Group Model
```python
# backend/accounts/models.py - Add to Group via proxy or extend

class GroupMetadata(models.Model):
    """Extended metadata for Django Groups"""
    group = models.OneToOneField(Group, on_delete=models.CASCADE, related_name='metadata')
    description = models.TextField(blank=True)
    category = models.CharField(max_length=20, choices=[
        ('platform', 'Platform Role'),
        ('app', 'App Role'),
    ], default='app')
    app_id = models.CharField(max_length=50, blank=True)  # e.g., 'carbon'
    manifest_key = models.CharField(max_length=100, blank=True)  # e.g., 'carbon:data_owner'
    is_scoped = models.BooleanField(default=False)  # From manifest
    is_protected = models.BooleanField(default=False)  # Can't be deleted
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"Metadata for {self.group.name}"
```

#### 1.2 Enhance GroupSerializer
```python
# backend/accounts/serializers.py

class GroupDetailSerializer(serializers.ModelSerializer):
    """Full group details with metadata and stats"""
    permissions_count = serializers.SerializerMethodField()
    users_count = serializers.SerializerMethodField()
    global_assignments_count = serializers.SerializerMethodField()
    scoped_assignments_count = serializers.SerializerMethodField()
    
    # Metadata fields
    description = serializers.CharField(source='metadata.description', allow_blank=True, required=False)
    category = serializers.CharField(source='metadata.category', read_only=True)
    app_id = serializers.CharField(source='metadata.app_id', read_only=True)
    manifest_key = serializers.CharField(source='metadata.manifest_key', read_only=True)
    is_scoped = serializers.BooleanField(source='metadata.is_scoped', read_only=True)
    is_protected = serializers.BooleanField(source='metadata.is_protected', read_only=True)
    created_at = serializers.DateTimeField(source='metadata.created_at', read_only=True)
    
    class Meta:
        model = Group
        fields = [
            'id', 'name', 'permissions_count', 'users_count',
            'global_assignments_count', 'scoped_assignments_count',
            'description', 'category', 'app_id', 'manifest_key',
            'is_scoped', 'is_protected', 'created_at',
        ]
    
    def get_global_assignments_count(self, obj):
        return ScopedRole.objects.filter(
            group=obj, 
            org_unit__isnull=True,
            module__isnull=True,
            is_active=True
        ).count()
    
    def get_scoped_assignments_count(self, obj):
        return ScopedRole.objects.filter(
            group=obj,
            is_active=True
        ).exclude(
            org_unit__isnull=True,
            module__isnull=True
        ).count()
```

#### 1.3 Add Group Detail Endpoints
```python
# backend/accounts/views.py

class GroupViewSet(viewsets.ModelViewSet):
    """Existing ViewSet - enhance with new actions"""
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return GroupDetailSerializer
        return GroupSerializer
    
    @action(detail=True, methods=['get'])
    def members(self, request, pk=None):
        """Get all users with global assignments to this group"""
        group = self.get_object()
        global_roles = ScopedRole.objects.filter(
            group=group,
            org_unit__isnull=True,
            module__isnull=True,
            is_active=True
        ).select_related('user')
        
        members = [{
            'id': role.user.id,
            'username': role.user.username,
            'email': getattr(role.user, 'email', ''),
            'assigned_at': role.created_at,
            'scoped_role_id': role.id,
        } for role in global_roles]
        
        return Response(members)
    
    @action(detail=True, methods=['get'])
    def scoped_assignments(self, request, pk=None):
        """Get all org-scoped assignments for this group"""
        group = self.get_object()
        scoped_roles = ScopedRole.objects.filter(
            group=group,
            is_active=True
        ).exclude(
            org_unit__isnull=True,
            module__isnull=True
        ).select_related('user', 'org_unit', 'module')
        
        serializer = ScopedRoleSerializer(scoped_roles, many=True)
        return Response(serializer.data)
```

#### 1.4 Sync Groups from Manifests (Migration/Command)
```python
# backend/accounts/management/commands/sync_app_roles.py

from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group
from accounts.models import GroupMetadata
import json

class Command(BaseCommand):
    help = 'Sync app role definitions from manifests to Django Groups'
    
    def handle(self, *args, **options):
        # Load manifests from APP_REGISTRY
        manifests = self._load_manifests()
        
        for app_id, manifest in manifests.items():
            roles = manifest.get('roles', [])
            for role_def in roles:
                manifest_key = role_def['key']  # e.g., 'carbon:data_owner'
                group_name = manifest_key.replace(':', '_')  # 'carbon_data_owner'
                
                group, created = Group.objects.get_or_create(name=group_name)
                metadata, _ = GroupMetadata.objects.get_or_create(
                    group=group,
                    defaults={
                        'description': role_def.get('description', ''),
                        'category': 'app',
                        'app_id': app_id,
                        'manifest_key': manifest_key,
                        'is_scoped': role_def.get('scoped', False),
                        'is_protected': role_def.get('protected', False),
                    }
                )
                
                action = 'Created' if created else 'Updated'
                self.stdout.write(
                    self.style.SUCCESS(f'{action} {group_name} from {app_id} manifest')
                )
        
        # Mark platform roles
        platform_roles = ['admin', 'admins_group', 'audit', 'steward']
        for role_name in platform_roles:
            group, _ = Group.objects.get_or_create(name=role_name)
            GroupMetadata.objects.get_or_create(
                group=group,
                defaults={
                    'category': 'platform',
                    'is_protected': True,
                }
            )
```

### Phase 2: Frontend - Enhanced GroupsPage

#### 2.1 Update GroupsPage Grid
```javascript
// carbon-frontend/src/pages/admin/GroupsPage.jsx

import { useNavigate } from 'react-router-dom';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import SecurityIcon from '@mui/icons-material/Security';
import AppsIcon from '@mui/icons-material/Apps';

export default function GroupsPage() {
  const navigate = useNavigate();
  // ... existing state ...

  const getRoleTypeIcon = (group) => {
    return group.category === 'platform' 
      ? <SecurityIcon fontSize="small" color="primary" />
      : <AppsIcon fontSize="small" color="secondary" />;
  };

  const getRoleTypeBadge = (group) => {
    if (group.is_protected) {
      return <Chip size="small" label="Protected" color="error" />;
    }
    return group.category === 'platform'
      ? <Chip size="small" label="Platform" color="primary" />
      : <Chip size="small" label={group.app_id || 'App'} color="secondary" />;
  };

  return (
    <Box sx={{ p: 3 }}>
      {/* ... header ... */}
      
      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Type</TableCell>
            <TableCell>Group Name</TableCell>
            <TableCell>Category</TableCell>
            <TableCell>Scoped</TableCell>
            <TableCell>Global Members</TableCell>
            <TableCell>Scoped Assignments</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {groups.map((group) => (
            <TableRow key={group.id} hover sx={{ cursor: 'pointer' }}>
              <TableCell onClick={() => navigate(`/admin/groups/${group.id}`)}>
                {getRoleTypeIcon(group)}
              </TableCell>
              <TableCell onClick={() => navigate(`/admin/groups/${group.id}`)}>
                <Box>
                  <Typography variant="body2" fontWeight={600}>
                    {group.name}
                  </Typography>
                  {group.manifest_key && (
                    <Typography variant="caption" color="text.secondary">
                      {group.manifest_key}
                    </Typography>
                  )}
                </Box>
              </TableCell>
              <TableCell>{getRoleTypeBadge(group)}</TableCell>
              <TableCell>
                {group.is_scoped ? (
                  <Chip size="small" label="Org-Scoped" color="info" />
                ) : (
                  <Chip size="small" label="Global" />
                )}
              </TableCell>
              <TableCell>{group.global_assignments_count || 0}</TableCell>
              <TableCell>{group.scoped_assignments_count || 0}</TableCell>
              <TableCell align="right">
                <IconButton 
                  size="small" 
                  onClick={() => navigate(`/admin/groups/${group.id}`)}
                >
                  <VisibilityRounded fontSize="small" />
                </IconButton>
                <IconButton size="small" onClick={() => openEdit(group)}>
                  <EditRounded fontSize="small" />
                </IconButton>
                <IconButton 
                  size="small" 
                  color="error" 
                  onClick={() => handleDelete(group)}
                  disabled={group.is_protected}
                >
                  <DeleteRounded fontSize="small" />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
```

### Phase 3: Frontend - GroupDetailPage

#### 3.1 Create GroupDetailPage
```javascript
// carbon-frontend/src/pages/admin/GroupDetailPage.jsx

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { Box } from '@mui/material';
import GroupIcon from '@mui/icons-material/Group';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import GroupOverviewTab from './tabs/GroupOverviewTab';
import GroupMembersTab from './tabs/GroupMembersTab';
import GroupScopedAssignmentsTab from './tabs/GroupScopedAssignmentsTab';
import GroupEditTab from './tabs/GroupEditTab';

export default function GroupDetailPage() {
  const { groupId } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  const [group, setGroup] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        setLoading(true);
        const res = await fetch(
          `${API_BASE_URL}accounts/groups/${groupId}/`,
          { headers: { Authorization: `Bearer ${user?.token}` } }
        );
        if (!res.ok) throw new Error('Failed to load group');
        const data = await res.json();
        setGroup(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [groupId, user?.token]);

  const headerComponent = (
    <DetailHeader
      title={group?.name || 'Group'}
      description={group?.description}
      icon={GroupIcon}
      onClose={() => navigate('/admin/groups')}
      badges={[
        group?.is_protected && { label: 'Protected', color: 'error' },
        group?.category === 'platform' 
          ? { label: 'Platform Role', color: 'primary' }
          : { label: group?.app_id || 'App Role', color: 'secondary' },
        group?.is_scoped && { label: 'Org-Scoped', color: 'info' },
      ].filter(Boolean)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: GroupOverviewTab },
        { label: 'Global Members', component: GroupMembersTab },
        { label: 'Scoped Assignments', component: GroupScopedAssignmentsTab },
        { label: 'Edit', component: GroupEditTab },
      ]}
      loading={loading}
      error={error}
      entityData={group}
      storageKey="groupDetail"
      onClose={() => navigate('/admin/groups')}
    />
  );
}
```

#### 3.2 Create Tab Components

**GroupOverviewTab.jsx:**
```javascript
// carbon-frontend/src/pages/admin/tabs/GroupOverviewTab.jsx

export default function GroupOverviewTab({ entityData: group }) {
  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="h6" gutterBottom>Role Information</Typography>
      
      <Grid container spacing={2}>
        <Grid item xs={12} md={6}>
          <InfoRow label="Group Name" value={group.name} />
          <InfoRow label="Category" value={group.category} />
          <InfoRow label="App ID" value={group.app_id || '—'} />
          <InfoRow label="Manifest Key" value={group.manifest_key || '—'} />
        </Grid>
        <Grid item xs={12} md={6}>
          <InfoRow label="Scoped" value={group.is_scoped ? 'Yes' : 'No'} />
          <InfoRow label="Protected" value={group.is_protected ? 'Yes' : 'No'} />
          <InfoRow label="Created" value={formatDate(group.created_at)} />
        </Grid>
      </Grid>

      {group.description && (
        <Box sx={{ mt: 3 }}>
          <Typography variant="subtitle2" gutterBottom>Description</Typography>
          <Typography variant="body2" color="text.secondary">
            {group.description}
          </Typography>
        </Box>
      )}

      <Box sx={{ mt: 4 }}>
        <Typography variant="h6" gutterBottom>Assignment Statistics</Typography>
        <Grid container spacing={2}>
          <StatCard 
            label="Global Members" 
            value={group.global_assignments_count} 
            icon={<PeopleIcon />}
          />
          <StatCard 
            label="Scoped Assignments" 
            value={group.scoped_assignments_count}
            icon={<AccountTreeIcon />}
          />
          <StatCard 
            label="Total Users" 
            value={group.users_count}
            icon={<PersonIcon />}
          />
        </Grid>
      </Box>
    </Box>
  );
}
```

**GroupMembersTab.jsx:**
```javascript
// carbon-frontend/src/pages/admin/tabs/GroupMembersTab.jsx

export default function GroupMembersTab({ entityData: group }) {
  const { user } = useAuth();
  const [members, setMembers] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchMembers = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}accounts/groups/${group.id}/members/`,
          { headers: { Authorization: `Bearer ${user?.token}` } }
        );
        const data = await res.json();
        setMembers(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchMembers();
  }, [group.id, user?.token]);

  const handleRemove = async (member) => {
    if (!window.confirm(`Remove ${member.username} from ${group.name}?`)) return;
    try {
      await fetch(
        `${API_BASE_URL}accounts/scoped-roles/${member.scoped_role_id}/`,
        { 
          method: 'DELETE',
          headers: { Authorization: `Bearer ${user?.token}` } 
        }
      );
      setMembers(members.filter(m => m.id !== member.id));
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        Users with global (non-scoped) assignments to this role
      </Typography>

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>Username</TableCell>
            <TableCell>Email</TableCell>
            <TableCell>Assigned At</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {members.map(member => (
            <TableRow key={member.id}>
              <TableCell>{member.username}</TableCell>
              <TableCell>{member.email}</TableCell>
              <TableCell>{formatDate(member.assigned_at)}</TableCell>
              <TableCell align="right">
                <IconButton 
                  size="small" 
                  color="error" 
                  onClick={() => handleRemove(member)}
                >
                  <DeleteRounded />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
```

**GroupScopedAssignmentsTab.jsx:**
```javascript
// carbon-frontend/src/pages/admin/tabs/GroupScopedAssignmentsTab.jsx

export default function GroupScopedAssignmentsTab({ entityData: group }) {
  const { user } = useAuth();
  const [assignments, setAssignments] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAssignments = async () => {
      try {
        const res = await fetch(
          `${API_BASE_URL}accounts/groups/${group.id}/scoped_assignments/`,
          { headers: { Authorization: `Bearer ${user?.token}` } }
        );
        const data = await res.json();
        setAssignments(data);
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    fetchAssignments();
  }, [group.id, user?.token]);

  return (
    <Box sx={{ p: 3 }}>
      <Typography variant="subtitle2" color="text.secondary" gutterBottom>
        Users with this role scoped to specific org units
      </Typography>

      <Table>
        <TableHead>
          <TableRow>
            <TableCell>User</TableCell>
            <TableCell>Org Unit</TableCell>
            <TableCell>Module</TableCell>
            <TableCell>Status</TableCell>
            <TableCell>Assigned At</TableCell>
            <TableCell align="right">Actions</TableCell>
          </TableRow>
        </TableHead>
        <TableBody>
          {assignments.map(assignment => (
            <TableRow key={assignment.id}>
              <TableCell>{assignment.user}</TableCell>
              <TableCell>{assignment.org_unit || '—'}</TableCell>
              <TableCell>{assignment.module || '—'}</TableCell>
              <TableCell>
                <Chip 
                  size="small" 
                  label={assignment.is_active ? 'Active' : 'Inactive'}
                  color={assignment.is_active ? 'success' : 'default'}
                />
              </TableCell>
              <TableCell>{formatDate(assignment.created_at)}</TableCell>
              <TableCell align="right">
                <IconButton size="small">
                  <VisibilityRounded />
                </IconButton>
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </Box>
  );
}
```

### Phase 4: API Client Updates

```javascript
// carbon-frontend/src/api/groups.js (NEW FILE)

import { apiFetch } from './api';
import { API_BASE_URL } from '../config';

export async function fetchGroups(token) {
  const res = await fetch(`${API_BASE_URL}accounts/groups/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch groups');
  const data = await res.json();
  return Array.isArray(data) ? data : data.results || [];
}

export async function fetchGroupDetail(token, groupId) {
  const res = await fetch(`${API_BASE_URL}accounts/groups/${groupId}/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch group');
  return res.json();
}

export async function fetchGroupMembers(token, groupId) {
  const res = await fetch(`${API_BASE_URL}accounts/groups/${groupId}/members/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch group members');
  return res.json();
}

export async function fetchGroupScopedAssignments(token, groupId) {
  const res = await fetch(`${API_BASE_URL}accounts/groups/${groupId}/scoped_assignments/`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error('Failed to fetch scoped assignments');
  return res.json();
}

export async function createGroup(token, data) {
  return apiFetch(`accounts/groups/`, {
    method: 'POST',
    token,
    body: data,
  });
}

export async function updateGroup(token, groupId, data) {
  return apiFetch(`accounts/groups/${groupId}/`, {
    method: 'PATCH',
    token,
    body: data,
  });
}

export async function deleteGroup(token, groupId) {
  return apiFetch(`accounts/groups/${groupId}/`, {
    method: 'DELETE',
    token,
  });
}
```

---

## Summary: Crystal Clear Role Types

### Role Type Matrix

| Type | Prefix | Examples | Scoped? | Purpose | Managed By |
|------|--------|----------|---------|---------|------------|
| **Platform Global** | None | `admin`, `audit` | Optional | Platform admin | Platform |
| **Platform Scoped** | None | `steward` | Yes | Org-level data governance | Platform |
| **App Global** | `{app}_` | `carbon_admin` | No | App configuration | App manifest |
| **App Scoped** | `{app}_` | `carbon_data_owner` | Yes | App data access | App manifest |

### Assignment Matrix

| Scenario | Group | org_unit | Meaning |
|----------|-------|----------|---------|
| **Superuser** | `admin` | NULL | Global platform admin |
| **Org Admin** | `admin` | Engineering College | Admin for Engineering and sub-units |
| **Global App Admin** | `carbon_admin` | NULL | Configure Carbon everywhere |
| **Scoped Data Owner** | `carbon_data_owner` | Transportation Dept | Manage Transportation emissions |

---

## Implementation Checklist

### Backend
- [ ] Create `GroupMetadata` model (description, category, app_id, manifest_key, is_scoped, is_protected)
- [ ] Migration to add metadata table
- [ ] Create `GroupDetailSerializer` with all stats
- [ ] Add `members()` action to `GroupViewSet`
- [ ] Add `scoped_assignments()` action to `GroupViewSet`
- [ ] Create `sync_app_roles` management command
- [ ] Update `PROTECTED_GROUPS` check to use `is_protected` field
- [ ] Write tests for new endpoints

### Frontend
- [ ] Update `GroupsPage.jsx` with enhanced table (type icon, badges, stats)
- [ ] Create `GroupDetailPage.jsx` with BaseDetailPage pattern
- [ ] Create `tabs/GroupOverviewTab.jsx` (metadata + stats)
- [ ] Create `tabs/GroupMembersTab.jsx` (global assignments)
- [ ] Create `tabs/GroupScopedAssignmentsTab.jsx` (org-scoped assignments)
- [ ] Create `tabs/GroupEditTab.jsx` (edit name, description)
- [ ] Create `api/groups.js` with all API calls
- [ ] Add route `/admin/groups/:groupId` in `App.jsx`
- [ ] Update `ShellSidebar.jsx` to highlight "Groups & Roles" correctly

### Data Migration
- [ ] Run `python manage.py sync_app_roles` to populate metadata
- [ ] Mark existing groups as protected where appropriate
- [ ] Link groups to manifests via manifest_key

### Documentation
- [ ] Update `RBAC_APP_ADMIN_GUIDELINES.md` with role type matrix
- [ ] Add "How to Assign Roles" guide with screenshots
- [ ] Document global vs scoped assignment patterns

---

## Benefits of This Approach

1. **Crystal Clear Role Types** - Visual distinction between platform and app roles
2. **Complete CRUD** - Full lifecycle management of groups and assignments
3. **Audit Trail** - See all members and assignments in one place
4. **Reuses Patterns** - Same BaseDetailPage pattern as OrgUnits
5. **Manifest-Driven** - App roles automatically synced from manifests
6. **Protected Groups** - System roles can't be accidentally deleted
7. **Scoped Visibility** - Clearly shows which assignments are global vs org-scoped

This gives Platform Admins complete control over the RBAC system with professional UX.
