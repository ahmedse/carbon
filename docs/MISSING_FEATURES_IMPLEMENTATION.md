# Missing Features - Implementation Guide

This document provides **code-ready specifications** for implementing the missing critical features identified in the technical review.

---

## 1. CYCLES/PERIODS MODEL (🔴 Critical - 2-4 hours)

### Problem
The design doc specifies a "Cycle" model for time-windowed carbon reporting (quarterly/yearly periods), but it's not implemented.

### Solution Specification

#### Backend Implementation

**File:** `backend/core/models.py`

```python
from django.db import models
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _

class Cycle(models.Model):
    """
    Represents a reporting period (e.g., Q1 2024, FY 2024).
    Each project can have multiple cycles for different reporting periods.
    """
    
    CYCLE_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('yearly', 'Yearly'),
        ('custom', 'Custom Period'),
    ]
    
    project = models.ForeignKey(
        'Project',
        on_delete=models.CASCADE,
        related_name='cycles',
        help_text="The project this cycle belongs to"
    )
    name = models.CharField(
        max_length=100,
        help_text="E.g., 'Q1 2024', 'FY 2024', 'Jan 2024'"
    )
    cycle_type = models.CharField(
        max_length=20,
        choices=CYCLE_TYPE_CHOICES,
        default='quarterly'
    )
    start_date = models.DateField()
    end_date = models.DateField()
    
    is_active = models.BooleanField(
        default=True,
        help_text="Whether data entry is allowed for this cycle"
    )
    is_archived = models.BooleanField(
        default=False,
        help_text="Archived cycles are read-only"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_cycles'
    )
    
    class Meta:
        ordering = ['-start_date']
        unique_together = [['project', 'name']]
        indexes = [
            models.Index(fields=['project', 'start_date', 'end_date']),
            models.Index(fields=['project', 'is_active']),
        ]
    
    def clean(self):
        """Validate that end_date is after start_date and no overlaps exist."""
        if self.end_date <= self.start_date:
            raise ValidationError({
                'end_date': _('End date must be after start date.')
            })
        
        # Check for overlapping cycles in the same project
        overlapping = Cycle.objects.filter(
            project=self.project,
            start_date__lt=self.end_date,
            end_date__gt=self.start_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError({
                'start_date': _('This cycle overlaps with an existing cycle.')
            })
    
    def save(self, *args, **kwargs):
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.project.name} - {self.name}"
    
    @property
    def duration_days(self):
        """Return the number of days in this cycle."""
        return (self.end_date - self.start_date).days
```

**Migration:**
```bash
cd backend
python manage.py makemigrations core --name add_cycle_model
python manage.py migrate core
```

**Serializer:** `backend/core/serializers.py`

```python
class CycleSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source='created_by.email', read_only=True)
    duration_days = serializers.IntegerField(read_only=True)
    project_name = serializers.CharField(source='project.name', read_only=True)
    
    class Meta:
        model = Cycle
        fields = [
            'id', 'project', 'project_name', 'name', 'cycle_type',
            'start_date', 'end_date', 'is_active', 'is_archived',
            'duration_days', 'created_at', 'created_by', 'created_by_email'
        ]
        read_only_fields = ['created_at', 'created_by', 'duration_days']
    
    def validate(self, data):
        """Ensure dates are valid and don't overlap."""
        if data['end_date'] <= data['start_date']:
            raise serializers.ValidationError({
                'end_date': 'End date must be after start date.'
            })
        return data
```

**ViewSet:** `backend/core/views.py`

```python
class CycleViewSet(viewsets.ModelViewSet):
    """
    API endpoint for managing reporting cycles/periods.
    
    list: Return cycles for projects the user has access to.
    create: Create a new cycle (admin/dataowner).
    retrieve: Get cycle details.
    update: Update cycle (admin only).
    destroy: Archive cycle (admin only, soft delete).
    """
    
    queryset = Cycle.objects.select_related('project', 'created_by')
    serializer_class = CycleSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasScopedRole(required_roles=['admin', 'admins_group', 'dataowners_group'])
    ]
    filterset_fields = ['project', 'cycle_type', 'is_active', 'is_archived']
    
    def get_queryset(self):
        """Filter cycles by projects the user has access to."""
        user = self.request.user
        if user.is_superuser:
            return self.queryset.all()
        
        allowed_project_ids = get_allowed_project_ids(user)
        return self.queryset.filter(project_id__in=allowed_project_ids)
    
    def perform_create(self, serializer):
        """Set created_by to current user."""
        serializer.save(created_by=self.request.user)
    
    def perform_destroy(self, instance):
        """Soft delete: archive instead of hard delete."""
        instance.is_archived = True
        instance.is_active = False
        instance.save()
```

**URL Routing:** `backend/core/urls.py`

```python
router.register(r'cycles', CycleViewSet, basename='cycle')
```

#### Frontend Implementation

**API Service:** `carbon-frontend/src/api/cyclesApi.js`

```javascript
import api from './api';

export const cyclesApi = {
  list: (params) => api.get('/core/cycles/', { params }),
  
  get: (id) => api.get(`/core/cycles/${id}/`),
  
  create: (data) => api.post('/core/cycles/', data),
  
  update: (id, data) => api.put(`/core/cycles/${id}/`, data),
  
  archive: (id) => api.delete(`/core/cycles/${id}/`),
  
  listByProject: (projectId) => 
    api.get('/core/cycles/', { params: { project: projectId, is_archived: false } }),
};
```

**Component:** `carbon-frontend/src/pages/CycleManagerPage.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import {
  Box, Button, Card, CardContent, Typography, Grid,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, MenuItem, Chip, Alert
} from '@mui/material';
import { Add as AddIcon, Archive as ArchiveIcon } from '@mui/icons-material';
import { cyclesApi } from '../api/cyclesApi';
import { useAuth } from '../auth/AuthContext';

export default function CycleManagerPage() {
  const { context } = useAuth();
  const [cycles, setCycles] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const [formData, setFormData] = useState({
    name: '',
    cycle_type: 'quarterly',
    start_date: '',
    end_date: '',
    project: context?.project_id || ''
  });
  
  useEffect(() => {
    loadCycles();
  }, [context?.project_id]);
  
  const loadCycles = async () => {
    if (!context?.project_id) return;
    
    setLoading(true);
    setError(null);
    try {
      const response = await cyclesApi.listByProject(context.project_id);
      setCycles(response.data);
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to load cycles');
    } finally {
      setLoading(false);
    }
  };
  
  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    try {
      await cyclesApi.create(formData);
      setOpenDialog(false);
      setFormData({
        name: '',
        cycle_type: 'quarterly',
        start_date: '',
        end_date: '',
        project: context.project_id
      });
      loadCycles();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to create cycle');
    } finally {
      setLoading(false);
    }
  };
  
  const handleArchive = async (id) => {
    if (!window.confirm('Archive this cycle? It will become read-only.')) return;
    
    try {
      await cyclesApi.archive(id);
      loadCycles();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to archive cycle');
    }
  };
  
  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Reporting Cycles</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          Add Cycle
        </Button>
      </Box>
      
      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}
      
      <Grid container spacing={2}>
        {cycles.map((cycle) => (
          <Grid item xs={12} sm={6} md={4} key={cycle.id}>
            <Card>
              <CardContent>
                <Typography variant="h6">{cycle.name}</Typography>
                <Typography color="text.secondary" gutterBottom>
                  {cycle.project_name}
                </Typography>
                <Typography variant="body2">
                  {cycle.start_date} to {cycle.end_date}
                </Typography>
                <Typography variant="caption" color="text.secondary">
                  {cycle.duration_days} days
                </Typography>
                <Box sx={{ mt: 2, display: 'flex', gap: 1 }}>
                  {cycle.is_active && <Chip label="Active" color="success" size="small" />}
                  {cycle.is_archived && <Chip label="Archived" size="small" />}
                </Box>
                <Button
                  size="small"
                  startIcon={<ArchiveIcon />}
                  onClick={() => handleArchive(cycle.id)}
                  sx={{ mt: 2 }}
                  disabled={cycle.is_archived}
                >
                  Archive
                </Button>
              </CardContent>
            </Card>
          </Grid>
        ))}
      </Grid>
      
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Create Reporting Cycle</DialogTitle>
        <DialogContent>
          <TextField
            label="Cycle Name"
            fullWidth
            margin="normal"
            value={formData.name}
            onChange={(e) => setFormData({ ...formData, name: e.target.value })}
            placeholder="e.g., Q1 2024, FY 2024"
          />
          <TextField
            select
            label="Cycle Type"
            fullWidth
            margin="normal"
            value={formData.cycle_type}
            onChange={(e) => setFormData({ ...formData, cycle_type: e.target.value })}
          >
            <MenuItem value="monthly">Monthly</MenuItem>
            <MenuItem value="quarterly">Quarterly</MenuItem>
            <MenuItem value="yearly">Yearly</MenuItem>
            <MenuItem value="custom">Custom</MenuItem>
          </TextField>
          <TextField
            label="Start Date"
            type="date"
            fullWidth
            margin="normal"
            value={formData.start_date}
            onChange={(e) => setFormData({ ...formData, start_date: e.target.value })}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="End Date"
            type="date"
            fullWidth
            margin="normal"
            value={formData.end_date}
            onChange={(e) => setFormData({ ...formData, end_date: e.target.value })}
            InputLabelProps={{ shrink: true }}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={loading}>
            Create
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

**Add Route:** `carbon-frontend/src/App.jsx`

```jsx
import CycleManagerPage from './pages/CycleManagerPage';

// Add to routes:
<Route path="/cycles" element={<CycleManagerPage />} />
```

---

## 2. USER MANAGEMENT UI (🔴 Critical - 1 week)

### Problem
Admins cannot create, edit, or manage users through the UI. Must use Django admin or shell.

### Solution Specification

#### Backend (Already Exists - Verify Endpoints)

**Endpoints:**
- `GET /carbon-api/accounts/users/` - List users
- `POST /carbon-api/accounts/users/` - Create user
- `GET /carbon-api/accounts/users/{id}/` - Get user
- `PUT /carbon-api/accounts/users/{id}/` - Update user
- `DELETE /carbon-api/accounts/users/{id}/` - Deactivate user

**Ensure ViewSet Allows Creation:**

```python
# backend/accounts/views.py

class UserViewSet(viewsets.ModelViewSet):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        HasScopedRole(required_roles=['admin', 'admins_group'])
    ]
    
    def get_queryset(self):
        """Superusers see all, others see only their tenant."""
        user = self.request.user
        if user.is_superuser:
            return self.queryset.all()
        return self.queryset.filter(tenant=user.tenant)
    
    def perform_create(self, serializer):
        """Set tenant to creator's tenant."""
        serializer.save(tenant=self.request.user.tenant)
```

**Serializer:**

```python
class UserSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = [
            'id', 'email', 'first_name', 'last_name', 'password',
            'is_active', 'is_staff', 'tenant', 'created_at'
        ]
        read_only_fields = ['created_at', 'tenant']
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User(**validated_data)
        user.set_password(password)
        user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        if password:
            instance.set_password(password)
        instance.save()
        return instance
```

#### Frontend Implementation

**API Service:** `carbon-frontend/src/api/usersApi.js`

```javascript
import api from './api';

export const usersApi = {
  list: (params) => api.get('/accounts/users/', { params }),
  
  get: (id) => api.get(`/accounts/users/${id}/`),
  
  create: (data) => api.post('/accounts/users/', data),
  
  update: (id, data) => api.put(`/accounts/users/${id}/`, data),
  
  deactivate: (id) => api.patch(`/accounts/users/${id}/`, { is_active: false }),
  
  activate: (id) => api.patch(`/accounts/users/${id}/`, { is_active: true }),
};
```

**Component:** `carbon-frontend/src/pages/UserManagementPage.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import {
  Box, Button, Paper, Typography, IconButton,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, Switch, FormControlLabel, Alert,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Chip
} from '@mui/material';
import {
  Add as AddIcon,
  Edit as EditIcon,
  Delete as DeleteIcon,
  CheckCircle as ActiveIcon
} from '@mui/icons-material';
import { usersApi } from '../api/usersApi';

export default function UserManagementPage() {
  const [users, setUsers] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [editMode, setEditMode] = useState(false);
  const [currentUser, setCurrentUser] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  const [formData, setFormData] = useState({
    email: '',
    first_name: '',
    last_name: '',
    password: '',
    is_active: true,
    is_staff: false
  });
  
  useEffect(() => {
    loadUsers();
  }, []);
  
  const loadUsers = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await usersApi.list();
      setUsers(response.data);
    } catch (err) {
      setError('Failed to load users');
    } finally {
      setLoading(false);
    }
  };
  
  const handleOpenCreate = () => {
    setFormData({
      email: '',
      first_name: '',
      last_name: '',
      password: '',
      is_active: true,
      is_staff: false
    });
    setEditMode(false);
    setCurrentUser(null);
    setOpenDialog(true);
  };
  
  const handleOpenEdit = (user) => {
    setFormData({
      email: user.email,
      first_name: user.first_name,
      last_name: user.last_name,
      password: '', // Don't show existing password
      is_active: user.is_active,
      is_staff: user.is_staff
    });
    setEditMode(true);
    setCurrentUser(user);
    setOpenDialog(true);
  };
  
  const handleSubmit = async () => {
    setLoading(true);
    setError(null);
    setSuccess(null);
    
    try {
      if (editMode) {
        const updateData = { ...formData };
        if (!updateData.password) {
          delete updateData.password; // Don't send empty password
        }
        await usersApi.update(currentUser.id, updateData);
        setSuccess('User updated successfully');
      } else {
        await usersApi.create(formData);
        setSuccess('User created successfully');
      }
      setOpenDialog(false);
      loadUsers();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to save user');
    } finally {
      setLoading(false);
    }
  };
  
  const handleToggleActive = async (user) => {
    try {
      if (user.is_active) {
        await usersApi.deactivate(user.id);
        setSuccess('User deactivated');
      } else {
        await usersApi.activate(user.id);
        setSuccess('User activated');
      }
      loadUsers();
    } catch (err) {
      setError('Failed to update user status');
    }
  };
  
  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">User Management</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={handleOpenCreate}
        >
          Add User
        </Button>
      </Box>
      
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}
      
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>Email</TableCell>
              <TableCell>Name</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Staff</TableCell>
              <TableCell>Created</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {users.map((user) => (
              <TableRow key={user.id}>
                <TableCell>{user.email}</TableCell>
                <TableCell>{user.first_name} {user.last_name}</TableCell>
                <TableCell>
                  {user.is_active ? (
                    <Chip label="Active" color="success" size="small" />
                  ) : (
                    <Chip label="Inactive" size="small" />
                  )}
                </TableCell>
                <TableCell>
                  {user.is_staff ? <Chip label="Staff" size="small" /> : '-'}
                </TableCell>
                <TableCell>{new Date(user.created_at).toLocaleDateString()}</TableCell>
                <TableCell align="right">
                  <IconButton onClick={() => handleOpenEdit(user)} size="small">
                    <EditIcon />
                  </IconButton>
                  <IconButton onClick={() => handleToggleActive(user)} size="small">
                    <ActiveIcon color={user.is_active ? 'success' : 'disabled'} />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{editMode ? 'Edit User' : 'Create User'}</DialogTitle>
        <DialogContent>
          <TextField
            label="Email"
            type="email"
            fullWidth
            margin="normal"
            value={formData.email}
            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
            required
          />
          <TextField
            label="First Name"
            fullWidth
            margin="normal"
            value={formData.first_name}
            onChange={(e) => setFormData({ ...formData, first_name: e.target.value })}
          />
          <TextField
            label="Last Name"
            fullWidth
            margin="normal"
            value={formData.last_name}
            onChange={(e) => setFormData({ ...formData, last_name: e.target.value })}
          />
          <TextField
            label="Password"
            type="password"
            fullWidth
            margin="normal"
            value={formData.password}
            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
            helperText={editMode ? 'Leave blank to keep existing password' : 'Required'}
            required={!editMode}
          />
          <FormControlLabel
            control={
              <Switch
                checked={formData.is_active}
                onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
              />
            }
            label="Active"
          />
          <FormControlLabel
            control={
              <Switch
                checked={formData.is_staff}
                onChange={(e) => setFormData({ ...formData, is_staff: e.target.checked })}
              />
            }
            label="Staff User"
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained" disabled={loading}>
            {editMode ? 'Update' : 'Create'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

**Add Route:** `carbon-frontend/src/App.jsx`

```jsx
import UserManagementPage from './pages/UserManagementPage';

// Add to routes (admin only):
<Route path="/users" element={<UserManagementPage />} />
```

---

## 3. ROLE ASSIGNMENT UI (🔴 Critical - 1 week)

### Problem
No UI to assign scoped roles to users. Must use Django admin.

### Solution Specification

#### Frontend Component

**File:** `carbon-frontend/src/pages/RoleAssignmentPage.jsx`

```jsx
import React, { useState, useEffect } from 'react';
import {
  Box, Button, Paper, Typography, Select, MenuItem,
  FormControl, InputLabel, Alert, Chip,
  Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
  Dialog, DialogTitle, DialogContent, DialogActions, IconButton
} from '@mui/material';
import { Add as AddIcon, Delete as DeleteIcon } from '@mui/icons-material';
import api from '../api/api';

export default function RoleAssignmentPage() {
  const [users, setUsers] = useState([]);
  const [projects, setProjects] = useState([]);
  const [modules, setModules] = useState([]);
  const [groups, setGroups] = useState([]);
  const [scopedRoles, setScopedRoles] = useState([]);
  const [openDialog, setOpenDialog] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);
  
  const [formData, setFormData] = useState({
    user: '',
    group: '',
    project: '',
    module: '',
    context: 'project' // 'tenant', 'project', or 'module'
  });
  
  useEffect(() => {
    loadData();
  }, []);
  
  const loadData = async () => {
    try {
      const [usersRes, projectsRes, groupsRes, rolesRes] = await Promise.all([
        api.get('/accounts/users/'),
        api.get('/core/projects/'),
        api.get('/accounts/roles/'),
        api.get('/accounts/scoped-roles/')
      ]);
      
      setUsers(usersRes.data);
      setProjects(projectsRes.data);
      setGroups(groupsRes.data);
      setScopedRoles(rolesRes.data);
    } catch (err) {
      setError('Failed to load data');
    }
  };
  
  const loadModules = async (projectId) => {
    if (!projectId) return;
    try {
      const response = await api.get('/core/modules/', { params: { project_id: projectId } });
      setModules(response.data);
    } catch (err) {
      setError('Failed to load modules');
    }
  };
  
  const handleProjectChange = (projectId) => {
    setFormData({ ...formData, project: projectId, module: '' });
    loadModules(projectId);
  };
  
  const handleSubmit = async () => {
    setError(null);
    setSuccess(null);
    
    const payload = {
      user: formData.user || null,
      group: formData.group || null,
      project: formData.context !== 'tenant' ? formData.project : null,
      module: formData.context === 'module' ? formData.module : null
    };
    
    try {
      await api.post('/accounts/scoped-roles/', payload);
      setSuccess('Role assigned successfully');
      setOpenDialog(false);
      loadData();
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to assign role');
    }
  };
  
  const handleDelete = async (roleId) => {
    if (!window.confirm('Remove this role assignment?')) return;
    
    try {
      await api.delete(`/accounts/scoped-roles/${roleId}/`);
      setSuccess('Role removed');
      loadData();
    } catch (err) {
      setError('Failed to remove role');
    }
  };
  
  return (
    <Box sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', justifyContent: 'space-between', mb: 3 }}>
        <Typography variant="h4">Role Assignments</Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => setOpenDialog(true)}
        >
          Assign Role
        </Button>
      </Box>
      
      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError(null)}>{error}</Alert>}
      {success && <Alert severity="success" sx={{ mb: 2 }} onClose={() => setSuccess(null)}>{success}</Alert>}
      
      <TableContainer component={Paper}>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell>User</TableCell>
              <TableCell>Group</TableCell>
              <TableCell>Project</TableCell>
              <TableCell>Module</TableCell>
              <TableCell>Context</TableCell>
              <TableCell align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {scopedRoles.map((role) => (
              <TableRow key={role.id}>
                <TableCell>{role.user_email || '-'}</TableCell>
                <TableCell>{role.group_name || '-'}</TableCell>
                <TableCell>{role.project_name || '-'}</TableCell>
                <TableCell>{role.module_name || '-'}</TableCell>
                <TableCell>
                  {role.module ? (
                    <Chip label="Module" size="small" color="primary" />
                  ) : role.project ? (
                    <Chip label="Project" size="small" color="secondary" />
                  ) : (
                    <Chip label="Tenant" size="small" />
                  )}
                </TableCell>
                <TableCell align="right">
                  <IconButton onClick={() => handleDelete(role.id)} size="small">
                    <DeleteIcon />
                  </IconButton>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </TableContainer>
      
      <Dialog open={openDialog} onClose={() => setOpenDialog(false)} maxWidth="sm" fullWidth>
        <DialogTitle>Assign Role</DialogTitle>
        <DialogContent>
          <FormControl fullWidth margin="normal">
            <InputLabel>User</InputLabel>
            <Select
              value={formData.user}
              onChange={(e) => setFormData({ ...formData, user: e.target.value })}
            >
              {users.map((user) => (
                <MenuItem key={user.id} value={user.id}>
                  {user.email}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <FormControl fullWidth margin="normal">
            <InputLabel>Group/Role</InputLabel>
            <Select
              value={formData.group}
              onChange={(e) => setFormData({ ...formData, group: e.target.value })}
            >
              {groups.map((group) => (
                <MenuItem key={group.id} value={group.id}>
                  {group.name}
                </MenuItem>
              ))}
            </Select>
          </FormControl>
          
          <FormControl fullWidth margin="normal">
            <InputLabel>Context Level</InputLabel>
            <Select
              value={formData.context}
              onChange={(e) => setFormData({ ...formData, context: e.target.value })}
            >
              <MenuItem value="tenant">Tenant-Wide</MenuItem>
              <MenuItem value="project">Project-Specific</MenuItem>
              <MenuItem value="module">Module-Specific</MenuItem>
            </Select>
          </FormControl>
          
          {formData.context !== 'tenant' && (
            <FormControl fullWidth margin="normal">
              <InputLabel>Project</InputLabel>
              <Select
                value={formData.project}
                onChange={(e) => handleProjectChange(e.target.value)}
              >
                {projects.map((project) => (
                  <MenuItem key={project.id} value={project.id}>
                    {project.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
          
          {formData.context === 'module' && (
            <FormControl fullWidth margin="normal">
              <InputLabel>Module</InputLabel>
              <Select
                value={formData.module}
                onChange={(e) => setFormData({ ...formData, module: e.target.value })}
              >
                {modules.map((module) => (
                  <MenuItem key={module.id} value={module.id}>
                    {module.name}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpenDialog(false)}>Cancel</Button>
          <Button onClick={handleSubmit} variant="contained">
            Assign
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
```

**Add Route:**

```jsx
import RoleAssignmentPage from './pages/RoleAssignmentPage';

// In App.jsx:
<Route path="/roles" element={<RoleAssignmentPage />} />
```

---

## 4. API RATE LIMITING (🔴 Critical - 1-2 days)

### Problem
No protection against brute-force attacks, API abuse, or DoS attempts.

### Solution

**Install Package:**

```bash
cd backend
pip install djangorestframework-simplejwt[crypto]
pip install django-ratelimit
pip freeze > requirements.txt
```

**Configure:** `backend/config/settings.py`

```python
# Rate limiting
REST_FRAMEWORK = {
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',      # Anonymous users: 100 requests/hour
        'user': '1000/hour',     # Authenticated: 1000 requests/hour
        'login': '5/minute',     # Login endpoint: 5 attempts/minute
    }
}
```

**Apply to Login Endpoint:** `backend/accounts/views.py`

```python
from rest_framework.throttling import AnonRateThrottle

class LoginRateThrottle(AnonRateThrottle):
    rate = '5/minute'

# In token view configuration:
from rest_framework_simplejwt.views import TokenObtainPairView

class CustomTokenObtainPairView(TokenObtainPairView):
    throttle_classes = [LoginRateThrottle]
```

**Update URLs:** `backend/config/urls.py`

```python
from accounts.views import CustomTokenObtainPairView

urlpatterns = [
    path(f'{api_prefix}token/', CustomTokenObtainPairView.as_view(), name='token_obtain'),
    # ... rest
]
```

---

## 5. COMPREHENSIVE TESTING (🔴 Critical - 3-5 days)

### Backend Testing Setup

**Install Test Packages:**

```bash
cd backend
pip install pytest-django pytest-cov factory-boy freezegun
pip freeze > requirements.txt
```

**Configure:** `backend/pytest.ini`

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
addopts = 
    --cov=.
    --cov-report=html
    --cov-report=term-missing
    --cov-branch
    --verbose
```

**Example Test:** `backend/accounts/tests/test_rbac.py`

```python
import pytest
from accounts.models import User, ScopedRole, Tenant
from core.models import Project
from django.contrib.auth.models import Group

@pytest.mark.django_db
class TestRBACPermissions:
    """Test role-based access control."""
    
    def test_admin_can_access_all_projects(self, admin_user, projects):
        """Admin should see all projects in their tenant."""
        allowed_ids = get_allowed_project_ids(admin_user)
        assert set(allowed_ids) == {p.id for p in projects}
    
    def test_dataowner_sees_only_assigned_projects(self, dataowner_user, project):
        """Dataowner should only see projects they're assigned to."""
        # Assign to project
        group = Group.objects.get(name='dataowners_group')
        ScopedRole.objects.create(
            user=dataowner_user,
            group=group,
            project=project
        )
        
        allowed_ids = get_allowed_project_ids(dataowner_user)
        assert project.id in allowed_ids
    
    def test_tenant_isolation(self, user_tenant_a, user_tenant_b, project_tenant_a):
        """Users from different tenants should not see each other's data."""
        allowed_ids = get_allowed_project_ids(user_tenant_b)
        assert project_tenant_a.id not in allowed_ids
```

**Factory:** `backend/conftest.py`

```python
import pytest
from accounts.models import User, Tenant
from core.models import Project

@pytest.fixture
def tenant():
    return Tenant.objects.create(name="Test Tenant", slug="test-tenant")

@pytest.fixture
def admin_user(tenant):
    user = User.objects.create_user(
        email="admin@test.com",
        password="testpass123",
        tenant=tenant,
        is_staff=True
    )
    # Assign admin role
    admin_group = Group.objects.get(name='admins_group')
    ScopedRole.objects.create(user=user, group=admin_group, tenant=tenant)
    return user

@pytest.fixture
def project(tenant, admin_user):
    return Project.objects.create(
        name="Test Project",
        tenant=tenant,
        created_by=admin_user
    )
```

**Run Tests:**

```bash
cd backend
pytest
pytest --cov-report=html  # Generate HTML coverage report
```

---

## 6. CSV IMPORT (🟡 High Priority - 1 week)

### Solution Specification

#### Backend

**Parser:** `backend/dataschema/parsers.py`

```python
import csv
from io import StringIO
from rest_framework.parsers import BaseParser

class CSVParser(BaseParser):
    """Parse CSV files for data import."""
    
    media_type = 'text/csv'
    
    def parse(self, stream, media_type=None, parser_context=None):
        """
        Parse CSV file and return list of dictionaries.
        """
        data = stream.read().decode('utf-8')
        csv_data = csv.DictReader(StringIO(data))
        return list(csv_data)
```

**Viewset Action:** `backend/dataschema/views.py`

```python
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from .parsers import CSVParser

class DataRowViewSet(viewsets.ModelViewSet):
    # ... existing code ...
    
    @action(detail=False, methods=['post'], parser_classes=[CSVParser])
    def import_csv(self, request):
        """
        Import multiple rows from CSV file.
        
        Expected format:
        field_name_1, field_name_2, ...
        value1, value2, ...
        """
        table_id = request.query_params.get('table_id')
        if not table_id:
            return Response(
                {'error': 'table_id query parameter required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            table = DataTable.objects.get(id=table_id)
        except DataTable.DoesNotExist:
            return Response(
                {'error': 'Table not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get field mapping
        fields = {f.name: f for f in table.fields.all()}
        
        # Parse CSV data
        csv_rows = request.data
        created_rows = []
        errors = []
        
        for idx, csv_row in enumerate(csv_rows, start=2):  # Start at 2 (header is row 1)
            try:
                # Map CSV columns to field values
                values = {}
                for field_name, field in fields.items():
                    csv_value = csv_row.get(field_name, '')
                    # Type conversion and validation
                    validated_value = self._convert_value(csv_value, field)
                    values[field_name] = validated_value
                
                # Create DataRow
                row = DataRow.objects.create(
                    table=table,
                    values=values,
                    created_by=request.user
                )
                created_rows.append(row.id)
                
            except Exception as e:
                errors.append({
                    'row': idx,
                    'error': str(e)
                })
        
        return Response({
            'created': len(created_rows),
            'errors': errors,
            'row_ids': created_rows
        }, status=status.HTTP_201_CREATED if created_rows else status.HTTP_400_BAD_REQUEST)
    
    def _convert_value(self, value, field):
        """Convert CSV string to appropriate field type."""
        if field.field_type == 'number':
            return float(value) if value else None
        elif field.field_type == 'boolean':
            return value.lower() in ['true', '1', 'yes']
        elif field.field_type == 'date':
            from datetime import datetime
            return datetime.strptime(value, '%Y-%m-%d').date() if value else None
        else:
            return value
```

#### Frontend

**Component:** `carbon-frontend/src/components/CSVUploader.jsx`

```jsx
import React, { useState } from 'react';
import { Box, Button, Alert, LinearProgress, Typography } from '@mui/material';
import { Upload as UploadIcon } from '@mui/icons-material';
import api from '../api/api';

export default function CSVUploader({ tableId, onSuccess }) {
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  
  const handleFileSelect = async (event) => {
    const file = event.target.files[0];
    if (!file) return;
    
    if (!file.name.endsWith('.csv')) {
      setError('Please select a CSV file');
      return;
    }
    
    setUploading(true);
    setError(null);
    setResult(null);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const response = await api.post(
        `/dataschema/rows/import_csv/?table_id=${tableId}`,
        file,
        {
          headers: { 'Content-Type': 'text/csv' }
        }
      );
      
      setResult(response.data);
      if (response.data.created > 0) {
        onSuccess?.();
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Upload failed');
    } finally {
      setUploading(false);
    }
  };
  
  return (
    <Box>
      <input
        accept=".csv"
        style={{ display: 'none' }}
        id="csv-upload"
        type="file"
        onChange={handleFileSelect}
      />
      <label htmlFor="csv-upload">
        <Button
          component="span"
          variant="outlined"
          startIcon={<UploadIcon />}
          disabled={uploading}
        >
          Import CSV
        </Button>
      </label>
      
      {uploading && <LinearProgress sx={{ mt: 2 }} />}
      
      {error && <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>}
      
      {result && (
        <Alert severity={result.errors.length > 0 ? 'warning' : 'success'} sx={{ mt: 2 }}>
          <Typography variant="body2">
            Created {result.created} rows
            {result.errors.length > 0 && `, ${result.errors.length} errors`}
          </Typography>
          {result.errors.length > 0 && (
            <Box sx={{ mt: 1 }}>
              {result.errors.slice(0, 5).map((err, idx) => (
                <Typography key={idx} variant="caption" display="block">
                  Row {err.row}: {err.error}
                </Typography>
              ))}
            </Box>
          )}
        </Alert>
      )}
    </Box>
  );
}
```

**Usage in DataEntryPage:**

```jsx
import CSVUploader from '../components/CSVUploader';

// In DataEntryPage.jsx:
<CSVUploader tableId={tableId} onSuccess={loadRows} />
```

---

## IMPLEMENTATION PRIORITY

**Week 1 (Critical Blockers):**
1. Cycles Model + Migrations (4 hours)
2. API Rate Limiting (4 hours)
3. Backend Tests Setup (8 hours)

**Week 2-3 (Core Features):**
4. User Management UI (40 hours)
5. Role Assignment UI (40 hours)

**Week 4-5 (Data Management):**
6. CSV Import (40 hours)
7. Pagination + Filtering (16 hours)

**Week 6+ (Advanced):**
8. Calculation Engine (80-120 hours)
9. Report Generation (40 hours)
10. Notifications (40 hours)

---

**Total Estimated Effort:** 12-16 weeks (2 full-time developers)

**Next Step:** Begin with Cycles model implementation (quickest win, unblocks Phase 2).
