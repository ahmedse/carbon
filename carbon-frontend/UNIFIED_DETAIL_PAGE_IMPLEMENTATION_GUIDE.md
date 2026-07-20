// UNIFIED_DETAIL_PAGE_IMPLEMENTATION_GUIDE.md
# Unified Detail Page Implementation Guide

## Overview

This guide demonstrates how to convert all entity detail pages across the Carbon platform to use a unified three-column layout pattern, ensuring predictable and maintainable UI/UX.

## Architecture Components (Already Created)

### 1. Core Components in `/src/components/detail/`

- **BaseDetailPage.jsx** - Universal container for all detail pages
  - Handles three-column layout, tab state, panel resizing
  - Manages collapsible metrics panel
  - Provides loading/error states
  - Persistence via localStorage

- **DetailHeader.jsx** - Reusable breadcrumb header
  - Dynamic breadcrumb navigation
  - Title, description, icon display
  - Close button with callback

- **DetailMainPanel.jsx** - Tab content wrapper
  - Provides consistent styling
  - `DetailTabContent` component for padding/spacing
  - `DetailMetadataGrid` for metadata display

- **DetailMetricsPanel.jsx** - Metrics sidebar components
  - `MetricCard` - Individual metric display
  - `MetricsGrid` - Grid layout for cards
  - `MetricsSection` - Titled section with dividers
  - `MetricsChip` - Tags and status indicators

### 2. Pattern Documentation

- **DETAIL_PAGE_PATTERN.md** - Complete pattern specification
  - Component API documentation
  - Implementation step-by-step guide
  - Tab component examples
  - Storage key conventions

## Already Implemented Examples

### 1. RowDetailPage (Original - dataschema/)
**Status**: ✅ COMPLETE
**Features**: Shows row details with Overview/Edit/Evidence tabs + metrics panel

### 2. SchemaDetailPage (catalog/)
**Status**: ✅ CONVERTED
**Route**: `/catalog/schemas/:tableId`
**Features**: Overview + Edit tabs with metrics

### 3. DomainDetailPage (catalog/)
**Status**: ✅ NEW
**Route**: `/catalog/domains/:domainId`
**Features**: Overview + Edit tabs with metrics

### 4. TagDetailPage (catalog/)
**Status**: ✅ NEW
**Route**: `/catalog/tags/:tagId`
**Features**: Overview + Edit tabs with metrics

### 5. AssetDetailPage (catalog/)
**Status**: ✅ NEW
**Route**: `/catalog/assets/:assetId`
**Features**: Overview + Edit tabs + quality metrics

### 6. OrgUnitDetailPage (admin/)
**Status**: ✅ NEW
**Route**: `/admin/org-units/:orgUnitId`
**Features**: Overview + Edit tabs with hierarchy metrics

## Pages Still Needing Conversion

### Catalog Pages
1. **ImportDetailPage** - Individual import project/job details
2. **ExportDetailPage** - Individual export project/job details
3. **DataSourceDetailPage** - Individual data source/connection details
4. **GlossaryTermDetailPage** - Individual glossary term details
5. **ConnectionDetailPage** - Individual connection details

### Admin Pages
1. **UserDetailPage** - Individual user details and permissions
2. **GroupDetailPage** - Individual role/group details and members

## Quick Conversion Template

### Step 1: Create Detail Page File

```jsx
// src/pages/{module}/{EntityName}DetailPage.jsx

import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import { useNotification } from '../../components/NotificationProvider';
import { Box } from '@mui/material';
import HomeIcon from '@mui/icons-material/Home';
import [EntityIcon] from '@mui/icons-material/[EntityIcon]';
import { API_BASE_URL, API_ROUTES } from '../../config';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import [EntityName]OverviewTab from './tabs/[EntityName]OverviewTab';
import [EntityName]EditTab from './tabs/[EntityName]EditTab';
import [EntityName]SummaryMetrics from './tabs/[EntityName]SummaryMetrics';

export default function [EntityName]DetailPage() {
  const { [entityId] } = useParams(); // e.g., { tagId }
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify } = useNotification();

  const [entity, setEntity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchEntity = async () => {
      if (![entityId] || !token) {
        setError('Missing required parameters');
        setLoading(false);
        return;
      }

      try {
        setLoading(true);
        const baseUrl = API_BASE_URL.replace(/\/$/, '');
        const url = `${baseUrl}${API_ROUTES.[apiRoute]}${[entityId]}/`;
        const response = await fetch(url, {
          headers: { Authorization: `Bearer ${token}` },
        });

        if (!response.ok) {
          throw new Error(`Failed to fetch: ${response.status}`);
        }

        const data = await response.json();
        setEntity(data);
      } catch (err) {
        const message = err.message || 'Failed to load entity';
        setError(message);
        notify({ message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchEntity();
  }, [[entityId], token]);

  const headerComponent = (
    <DetailHeader
      breadcrumbs={[
        { label: 'Home', icon: <HomeIcon />, path: '/' },
        { label: '[Category]', path: '/[category]' },
        { label: '[Entities]', path: '/[category]/[entities]' },
      ]}
      title={entity?.name || '[Entity]'}
      description={entity?.description}
      icon={[EntityIcon]}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: [EntityName]OverviewTab },
        { label: 'Edit', component: [EntityName]EditTab },
        { label: '[Optional Tab]', component: [EntityName][OptionalTab] }, // optional
      ]}
      metricsTabs={[
        { label: 'Summary', component: [EntityName]SummaryMetrics },
        { label: '[Optional Metrics]', component: [EntityName][OptionalMetrics] }, // optional
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbon[EntityName]Detail"
      entityData={entity}
    />
  );
}
```

### Step 2: Create Overview Tab

```jsx
// src/pages/{module}/tabs/[EntityName]OverviewTab.jsx

import React from 'react';
import { Box, Table, TableHead, TableRow, TableCell, TableBody, Typography } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';

export default function [EntityName]OverviewTab({ entityData }) {
  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography color="textSecondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  const attributes = [
    { label: 'ID', value: entityData.id },
    { label: 'Name', value: entityData.name },
    { label: 'Description', value: entityData.description || '—' },
    // Add more attributes as needed
  ];

  return (
    <DetailTabContent>
      <Box sx={{ overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell sx={{ fontWeight: 600 }}>Property</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {attributes.map((attr, idx) => (
              <TableRow key={idx} sx={{ '&:hover': { bgcolor: 'grey.50' } }}>
                <TableCell sx={{ fontWeight: 500, width: '30%' }}>{attr.label}</TableCell>
                <TableCell>{attr.value}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Box>
    </DetailTabContent>
  );
}
```

### Step 3: Create Edit Tab

```jsx
// src/pages/{module}/tabs/[EntityName]EditTab.jsx

import React, { useState } from 'react';
import { Box, TextField, Button, CircularProgress, Alert } from '@mui/material';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { API_BASE_URL, API_ROUTES } from '../../../config';

export default function [EntityName]EditTab({ entityData }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  const [formData, setFormData] = useState({
    name: entityData?.name || '',
    description: entityData?.description || '',
    // Add other fields as needed
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData(prev => ({ ...prev, [name]: value }));
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      setError('Name is required');
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const baseUrl = API_BASE_URL.replace(/\/$/, '');
      const url = `${baseUrl}${API_ROUTES.[apiRoute]}${entityData.id}/`;
      const response = await fetch(url, {
        method: 'PUT',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`Failed to save: ${response.status}`);
      }

      notify({ message: 'Entity updated successfully', type: 'success' });
    } catch (err) {
      const message = err.message || 'Failed to save entity';
      setError(message);
      notify({ message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: '600px' }}>
        {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

        <TextField
          fullWidth
          label="Name"
          name="name"
          value={formData.name}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
        />

        <TextField
          fullWidth
          label="Description"
          name="description"
          value={formData.description}
          onChange={handleChange}
          margin="normal"
          variant="outlined"
          multiline
          rows={4}
        />

        <Box sx={{ mt: 3, display: 'flex', gap: 1 }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? <CircularProgress size={24} /> : 'Save Changes'}
          </Button>
        </Box>
      </Box>
    </DetailTabContent>
  );
}
```

### Step 4: Create Metrics Tab

```jsx
// src/pages/{module}/tabs/[EntityName]SummaryMetrics.jsx

import React from 'react';
import {
  DetailMetricsPanel,
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import UpdateIcon from '@mui/icons-material/Update';

export default function [EntityName]SummaryMetrics({ entityData }) {
  if (!entityData) return null;

  const createdDate = entityData.created_at 
    ? new Date(entityData.created_at).toLocaleDateString()
    : '—';

  return (
    <DetailMetricsPanel>
      <MetricsSection title="[Entity] Information">
        <MetricsGrid>
          <MetricCard
            label="ID"
            value={entityData.id}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label="Created"
            value={createdDate}
            icon={<InfoIcon />}
            color="success"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
```

### Step 5: Add Route to App.jsx

```jsx
// In App.jsx, add new route:
import [EntityName]DetailPage from './pages/{module}/[EntityName]DetailPage';

// In routes array:
<Route path="/[path]/:[ entityId]" element={<[EntityName]DetailPage />} />
```

### Step 6: Update List Page Navigation

Make rows clickable in list pages:

```jsx
// In list page TableRow:
<TableRow
  onClick={() => navigate(`/[path]/${row.id}`)}
  sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
>
  {/* cells */}
</TableRow>
```

## Recommended Conversion Order

### Phase 1 (Immediate - Catalog Pages)
1. ImportDetailPage - For viewing specific import jobs
2. ExportDetailPage - For viewing specific export jobs
3. DataSourceDetailPage - For viewing specific data sources

### Phase 2 (Admin Pages)
1. UserDetailPage - For user management details
2. GroupDetailPage - For role/group details

### Phase 3 (Additional Catalog)
1. GlossaryTermDetailPage - For glossary term details
2. ConnectionDetailPage - For connection details

## Benefits of This Pattern

✅ **Unified UX** - All detail pages look and behave identically
✅ **Fast Implementation** - New detail pages created in minutes
✅ **Easy Maintenance** - Update BaseDetailPage once, benefit everywhere
✅ **Consistent Navigation** - Breadcrumbs and back navigation work the same way
✅ **Tab Persistence** - User preferences saved across sessions
✅ **Responsive Design** - Mobile-friendly with collapsible panels
✅ **Predictable Component Structure** - Developers know what to expect

## Common Patterns

### Adding Tabs
```jsx
mainTabs={[
  { label: 'Overview', component: OverviewTab },
  { label: 'Edit', component: EditTab },
  { label: 'History', component: HistoryTab },
  { label: 'Audit', component: AuditTab },
]}
```

### Adding Metrics Panels
```jsx
metricsTabs={[
  { label: 'Summary', component: SummaryMetrics },
  { label: 'Relations', component: RelationsMetrics },
  { label: 'Quality', component: QualityMetrics },
]}
```

### Conditional Tabs
```jsx
const mainTabs = [
  { label: 'Overview', component: OverviewTab },
  { label: 'Edit', component: EditTab },
  ...(entity?.hasAudit ? [{ label: 'Audit', component: AuditTab }] : []),
];
```

## Testing Checklist

For each new detail page:

- [ ] Route works: navigate to `/path/:id`
- [ ] Data loads: API call successful
- [ ] Tabs switch: main tabs work correctly
- [ ] Metrics panel toggles: toggle button works
- [ ] Panel resizes: drag divider to resize
- [ ] Persistence: reload page, same tab/width selected
- [ ] Breadcrumbs work: click breadcrumb navigates
- [ ] Close button works: returns to previous page
- [ ] Edit saves: PUT request succeeds
- [ ] Error handling: shows error if API fails
- [ ] Mobile responsive: panel collapses on small screens

## Files Created/Modified

### New Files
- `/src/components/detail/BaseDetailPage.jsx`
- `/src/components/detail/DetailHeader.jsx`
- `/src/components/detail/DetailMainPanel.jsx`
- `/src/components/detail/DetailMetricsPanel.jsx`
- `/src/components/detail/DETAIL_PAGE_PATTERN.md`
- `/src/pages/catalog/DomainDetailPage.jsx`
- `/src/pages/catalog/TagDetailPage.jsx`
- `/src/pages/catalog/AssetDetailPage.jsx`
- `/src/pages/admin/OrgUnitDetailPage.jsx`
- Tab components in `/tabs/` directories

### Modified Files
- `App.jsx` - Add new routes (6 new routes needed for existing examples)
- Config files may need updates for API route definitions

## Next Steps for User

1. Review existing implementations (Domain, Tag, Asset, OrgUnit detail pages)
2. Follow the template for any remaining detail pages
3. Add routes to App.jsx
4. Update list pages to include navigation links
5. Test all pages across desktop and mobile
6. Verify error handling and edge cases

