// File: src/components/detail/DETAIL_PAGE_PATTERN.md
# Unified Detail Page Pattern

This document describes the standardized component architecture for all entity detail pages in the Carbon platform.

## Architecture

All detail pages follow a three-column layout pattern:
```
┌─────────────────────────────────────────────────────────┐
│ DetailHeader (breadcrumbs + title + close)              │
├──────────────────────────────────────┬──────────────────┤
│                                      │   Metrics Panel  │
│ Main Panel                           │ (resizable,      │
│ (tabs + scrollable content)          │  collapsible)    │
│                                      │                  │
└──────────────────────────────────────┴──────────────────┘
```

## Components

### 1. BaseDetailPage (container)
**File**: `src/components/detail/BaseDetailPage.jsx`

Unified template that handles:
- Layout structure (flex, resizable divider)
- Tab state management with localStorage persistence
- Panel width/visibility state with localStorage persistence
- Loading/error states
- Collapsible metrics panel with toggle button

**Props**:
```jsx
<BaseDetailPage
  headerComponent={<DetailHeader {...} />}           // Required: header with breadcrumbs
  mainTabs={[                                         // Required: tab definitions
    { label: 'Overview', component: OverviewTab },
    { label: 'Edit', component: EditTab },
    { label: 'Audit', component: AuditTab },
  ]}
  metricsTabs={[                                      // Optional: metrics panel tabs
    { label: 'Summary', component: SummaryTab },
    { label: 'Relations', component: RelationsTab },
  ]}
  metricsPanel={MetricsPanelComponent}               // Optional: custom metrics component
  loading={loading}
  error={error}
  onClose={handleClose}
  storageKey="carbonEntityDetail"                    // For localStorage persistence
  entityData={entity}                                 // Data passed to tab components
/>
```

### 2. DetailHeader (breadcrumbs + title)
**File**: `src/components/detail/DetailHeader.jsx`

Standard header with:
- Breadcrumb navigation (dynamic path building)
- Icon + Title + Description
- Close button

**Props**:
```jsx
<DetailHeader
  breadcrumbs={[
    { label: 'Home', icon: <HomeIcon />, path: '/' },
    { label: 'Catalog', path: '/catalog' },
    { label: 'Assets', path: '/catalog/assets' },
  ]}
  title="Asset Name"
  description="Asset Description"
  icon={StorageIcon}
  onClose={() => navigate(-1)}
/>
```

### 3. DetailMainPanel (tab content wrapper)
**File**: `src/components/detail/DetailMainPanel.jsx`

Provides consistent styling and state handling for:
- Loading spinner
- Error alerts
- Content area

**Usage**:
```jsx
import { DetailTabContent } from '../../components/detail/DetailMainPanel';

function OverviewTab({ entityData }) {
  return (
    <DetailTabContent>
      {/* Tab content */}
    </DetailTabContent>
  );
}
```

### 4. DetailMetricsPanel (sidebar metrics)
**File**: `src/components/detail/DetailMetricsPanel.jsx`

Provides reusable components for metrics display:
- `MetricCard` - individual metric with icon and value
- `MetricsGrid` - grid layout for cards
- `MetricsSection` - section with header
- `MetricsChip` - tags/statuses

**Usage**:
```jsx
import {
  DetailMetricsPanel,
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../components/detail/DetailMetricsPanel';

function MetricsSummaryTab({ entityData }) {
  return (
    <DetailMetricsPanel loading={false} error={null}>
      <MetricsSection title="Overview">
        <MetricsGrid>
          <MetricCard
            label="Created"
            value={entityData.created_at}
            icon={<DateIcon />}
            color="primary"
          />
          <MetricCard
            label="Updated"
            value={entityData.updated_at}
            icon={<UpdateIcon />}
            color="info"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
```

## Implementation Pattern

### Step 1: Create Detail Page Component
```jsx
// src/pages/catalog/AssetDetailPage.jsx

import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../../auth/AuthContext';
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import { useNotification } from '../../components/NotificationProvider';
import HomeIcon from '@mui/icons-material/Home';
import StorageIcon from '@mui/icons-material/Storage';

// Import tab components
import AssetOverviewTab from './tabs/AssetOverviewTab';
import AssetEditTab from './tabs/AssetEditTab';
import AssetSummaryMetrics from './tabs/AssetSummaryMetrics';
import AssetRelationsMetrics from './tabs/AssetRelationsMetrics';

export default function AssetDetailPage() {
  const { assetId } = useParams();
  const navigate = useNavigate();
  const { user, token } = useAuth();
  const { notify } = useNotification();

  const [entity, setEntity] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchEntity = async () => {
      try {
        setLoading(true);
        // Fetch entity from API
        const response = await fetch(
          `${API_BASE_URL}/catalog/assets/${assetId}/`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!response.ok) throw new Error(`Failed to fetch: ${response.status}`);
        setEntity(await response.json());
      } catch (err) {
        setError(err.message);
        notify({ message: err.message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };

    fetchEntity();
  }, [assetId, token]);

  const headerComponent = (
    <DetailHeader
      breadcrumbs={[
        { label: 'Home', icon: <HomeIcon />, path: '/' },
        { label: 'Catalog', path: '/catalog' },
        { label: 'Assets', path: '/catalog/assets' },
      ]}
      title={entity?.name || 'Asset'}
      description={entity?.description}
      icon={StorageIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: AssetOverviewTab },
        { label: 'Edit', component: AssetEditTab },
        { label: 'Audit', component: AssetSummaryMetrics }, // Can use metrics as tab
      ]}
      metricsTabs={[
        { label: 'Summary', component: AssetSummaryMetrics },
        { label: 'Relations', component: AssetRelationsMetrics },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonAssetDetail"
      entityData={entity}
    />
  );
}
```

### Step 2: Create Tab Components
```jsx
// src/pages/catalog/tabs/AssetOverviewTab.jsx

import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { Box, Table, TableHead, TableRow, TableCell, TableBody } from '@mui/material';

export default function AssetOverviewTab({ entityData }) {
  if (!entityData) return null;

  return (
    <DetailTabContent>
      <Box sx={{ overflowX: 'auto' }}>
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: 'grey.100' }}>
              <TableCell>Property</TableCell>
              <TableCell>Value</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            <TableRow>
              <TableCell sx={{ fontWeight: 500 }}>ID</TableCell>
              <TableCell>{entityData.id}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: 500 }}>Name</TableCell>
              <TableCell>{entityData.name}</TableCell>
            </TableRow>
            <TableRow>
              <TableCell sx={{ fontWeight: 500 }}>Status</TableCell>
              <TableCell>{entityData.status}</TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </Box>
    </DetailTabContent>
  );
}
```

### Step 3: Create Metrics Tab Components
```jsx
// src/pages/catalog/tabs/AssetSummaryMetrics.jsx

import {
  DetailMetricsPanel,
  MetricCard,
  MetricsGrid,
  MetricsSection,
} from '../../../components/detail/DetailMetricsPanel';
import InfoIcon from '@mui/icons-material/Info';
import UpdateIcon from '@mui/icons-material/Update';

export default function AssetSummaryMetrics({ entityData }) {
  if (!entityData) return null;

  return (
    <DetailMetricsPanel>
      <MetricsSection title="Asset Info">
        <MetricsGrid>
          <MetricCard
            label="Status"
            value={entityData.status}
            icon={<InfoIcon />}
            color="primary"
          />
          <MetricCard
            label="Last Modified"
            value={entityData.updated_at}
            icon={<UpdateIcon />}
            color="info"
          />
        </MetricsGrid>
      </MetricsSection>
    </DetailMetricsPanel>
  );
}
```

### Step 4: Update Routing
Add route to App.jsx:
```jsx
import AssetDetailPage from './pages/catalog/AssetDetailPage';

// In routes array:
<Route path="/catalog/assets/:assetId" element={<AssetDetailPage />} />
```

### Step 5: Update List Page Navigation
In the list page, make rows clickable:
```jsx
<TableRow
  onClick={() => navigate(`/catalog/assets/${row.id}`)}
  sx={{ cursor: 'pointer', '&:hover': { bgcolor: 'action.hover' } }}
>
  {/* cells */}
</TableRow>
```

## Storage Keys Convention

Each detail page uses a unique storage key for localStorage persistence:

| Entity Type | Storage Key | Tab State |
|------------|-------------|----------|
| Row | `carbonRowDetail:mainTab` | Main tab index |
| Schema | `carbonSchemaDetail:mainTab` | Main tab index |
| Asset | `carbonAssetDetail:mainTab` | Main tab index |
| Domain | `carbonDomainDetail:mainTab` | Main tab index |
| Tag | `carbonTagDetail:mainTab` | Main tab index |
| OrgUnit | `carbonOrgUnitDetail:mainTab` | Main tab index |

Format: `{entityKey}Detail:{property}` (mainTab, metricsTab, panelWidth, metricsPanelOpen)

## Key Features

✓ **Unified Layout** - All detail pages use same three-column structure
✓ **Collapsible Metrics** - Persistent panel with resizable divider
✓ **Breadcrumb Navigation** - Dynamic breadcrumb trails
✓ **Tab Persistence** - Tab selection saved to localStorage
✓ **Responsive Design** - Adapts to mobile (collapses metrics panel)
✓ **Consistent Styling** - Material UI components with standard patterns
✓ **Error Handling** - Unified error states and notifications
✓ **Loading States** - Consistent spinners and placeholders

## Benefits

1. **Predictable UX** - Users know what to expect across all pages
2. **Maintainable Code** - Changes to BaseDetailPage update all pages
3. **Reusable Components** - DetailHeader, DetailMainPanel, DetailMetricsPanel used everywhere
4. **Consistent Styling** - Same Material UI patterns throughout
5. **Developer Velocity** - New detail pages created in minutes from template
6. **Mobile Friendly** - Responsive design handles all screen sizes
