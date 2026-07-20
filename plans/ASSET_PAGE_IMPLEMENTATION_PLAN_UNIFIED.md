# Asset Page Implementation Plan - Unified Architecture

**Date:** July 20, 2026  
**Approach:** Reuse existing grid and detail page patterns  
**Status:** Ready for implementation

---

## OVERVIEW

Implement Asset Page using proven platform patterns:
- **List View:** Extend [`DataTableGrid.jsx`](carbon-frontend/src/components/DataTableGrid.jsx) with filtering, searching, ordering, and pagination
- **Detail View:** Extend [`BaseDetailPage.jsx`](carbon-frontend/src/components/detail/BaseDetailPage.jsx) with tabbed interface (like [`DomainDetailPage.jsx`](carbon-frontend/src/pages/catalog/DomainDetailPage.jsx))
- **Styling:** Use system theme (carbon theme) and existing Material-UI components
- **No custom components:** Leverage what already works

---

## ARCHITECTURE PATTERN REFERENCE

### Existing Pattern 1: List with Grid
**Used by:** Data Entry (rows), Schema Manager (tables)  
**Component:** [`DataTableGrid.jsx`](carbon-frontend/src/components/DataTableGrid.jsx) (522 lines)
- Built-in pagination
- Sortable columns
- Filterable columns
- Inline actions (edit, delete, view)
- File uploads
- Reference field dropdowns

**Advantage:** Already handles complex data, RBAC, file uploads, validation

---

### Existing Pattern 2: Detail Page with Tabs
**Used by:** [`DomainDetailPage.jsx`](carbon-frontend/src/pages/catalog/DomainDetailPage.jsx), [`RowDetailPage.jsx`](carbon-frontend/src/pages/dataschema/RowDetailPage.jsx), [`SchemaDetailPage.jsx`](carbon-frontend/src/pages/catalog/SchemaDetailPage.jsx)

**Structure:**
```jsx
<BaseDetailPage
  headerComponent={<DetailHeader title={...} icon={...} />}
  mainTabs={[
    { label: 'Overview', component: OverviewTab },
    { label: 'Edit', component: EditTab },
  ]}
  metricsTabs={[
    { label: 'Audit', component: AuditTab },
  ]}
  loading={loading}
  error={error}
  storageKey="carbonAssetDetail"
  entityData={asset}
/>
```

**Features:**
- Three-column layout: header + main + metrics panel
- Resizable divider between panels
- Tab persistence in localStorage
- Built-in loading/error states
- Theme-aware responsive design

---

## IMPLEMENTATION PLAN

### Phase 1: List Page (Assets Grid View)

**File:** [`carbon-frontend/src/pages/catalog/AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx)

**Approach:** DO NOT use custom table. Instead:
1. Fetch all assets from backend
2. Transform into grid-compatible rows
3. Define columns (name, type, domain, classification, quality, steward, tags, actions)
4. Use [`DataTableGrid.jsx`](carbon-frontend/src/components/DataTableGrid.jsx) OR create simple wrapper using MUI DataGrid with sorting/filtering/pagination

**Why not DataTableGrid directly?**
- [`DataTableGrid.jsx`](carbon-frontend/src/components/DataTableGrid.jsx) is designed for schema table data with file uploads and row editing
- Asset grid is simpler: read-only list with navigate-to-detail action

**Solution:** Create lightweight list using MUI DataGrid directly with:
- Sorting on: name, type, domain, classification, quality_status, steward
- Filtering on: domain, classification, quality_status, asset_type
- Searching on: name/description free text
- Pagination: 10, 25, 50 rows per page
- Quick actions: [View Details] [Edit] [Delete]

**Key Code Pattern:**
```jsx
import { DataGrid } from '@mui/x-data-grid';

const columns = [
  { field: 'title', headerName: 'Name', flex: 1, sortable: true },
  { field: 'asset_type', headerName: 'Type', width: 100, sortable: true },
  { field: 'domain_name', headerName: 'Domain', flex: 0.8, sortable: true },
  { field: 'classification', headerName: 'Classification', width: 120, sortable: true,
    renderCell: (params) => <ClassificationBadge value={params.value} /> 
  },
  { field: 'quality_status', headerName: 'Quality', width: 100, sortable: true,
    renderCell: (params) => <QualityStatusBadge value={params.value} />
  },
  { field: 'steward_name', headerName: 'Steward', flex: 0.8 },
  {
    field: 'actions',
    headerName: 'Actions',
    width: 120,
    sortable: false,
    renderCell: (params) => (
      <Box sx={{ display: 'flex', gap: 0.5 }}>
        <IconButton size="small" onClick={() => navigate(`/catalog/assets/${params.row.id}`)}>
          <VisibilityIcon fontSize="small" />
        </IconButton>
        <IconButton size="small" onClick={() => handleEdit(params.row)}>
          <EditIcon fontSize="small" />
        </IconButton>
        <IconButton size="small" onClick={() => handleDelete(params.row.id)}>
          <DeleteIcon fontSize="small" />
        </IconButton>
      </Box>
    ),
  },
];

const [paginationModel, setPaginationModel] = useState({ pageSize: 25, page: 0 });
const [filters, setFilters] = useState({});
const [searchText, setSearchText] = useState('');
const [sortModel, setSortModel] = useState([]);

<DataGrid
  rows={assets}
  columns={columns}
  paginationModel={paginationModel}
  onPaginationModelChange={setPaginationModel}
  pageSizeOptions={[10, 25, 50]}
  sortModel={sortModel}
  onSortModelChange={setSortModel}
  filterModel={filterModel}
  onFilterModelChange={setFilterModel}
/>
```

**Filter/Search Bar (above grid):**
```jsx
<Box sx={{ display: 'flex', gap: 2, mb: 2, p: 2, bgcolor: 'background.alt' }}>
  <TextField
    placeholder="Search by name or description..."
    value={searchText}
    onChange={(e) => setSearchText(e.target.value)}
    sx={{ flex: 1 }}
    InputProps={{ startAdornment: <SearchIcon sx={{ mr: 1 }} /> }}
  />
  <FormControl sx={{ minWidth: 150 }}>
    <InputLabel>Domain</InputLabel>
    <Select value={filters.domain} onChange={(e) => setFilters({...filters, domain: e.target.value})}>
      <MenuItem value="">All</MenuItem>
      {domains.map(d => <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>)}
    </Select>
  </FormControl>
  <FormControl sx={{ minWidth: 150 }}>
    <InputLabel>Classification</InputLabel>
    <Select value={filters.classification} onChange={(e) => setFilters({...filters, classification: e.target.value})}>
      <MenuItem value="">All</MenuItem>
      <MenuItem value="public">Public</MenuItem>
      <MenuItem value="internal">Internal</MenuItem>
      <MenuItem value="confidential">Confidential</MenuItem>
      <MenuItem value="pii">PII</MenuItem>
      <MenuItem value="sensitive">Sensitive</MenuItem>
    </Select>
  </FormControl>
  <FormControl sx={{ minWidth: 150 }}>
    <InputLabel>Quality</InputLabel>
    <Select value={filters.quality} onChange={(e) => setFilters({...filters, quality: e.target.value})}>
      <MenuItem value="">All</MenuItem>
      <MenuItem value="passing">Passing</MenuItem>
      <MenuItem value="warning">Warning</MenuItem>
      <MenuItem value="failing">Failing</MenuItem>
      <MenuItem value="unknown">Unknown</MenuItem>
    </Select>
  </FormControl>
  <Button onClick={() => setFilters({}) && setSearchText('')}>Clear</Button>
</Box>
```

**File Structure:**
```
carbon-frontend/src/pages/catalog/
├─ AssetsPage.jsx          (MODIFIED: replace with grid-based list)
├─ AssetDetailPage.jsx     (NEW: detail page with tabs)
└─ tabs/
   ├─ AssetOverviewTab.jsx (NEW: metadata display)
   ├─ AssetEditTab.jsx     (NEW: governance form)
   └─ AssetAuditTab.jsx    (NEW: audit history)
```

---

### Phase 2: Detail Page with Tabs

**File:** [`carbon-frontend/src/pages/catalog/AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx) (NEW)

**Approach:** Copy/adapt [`DomainDetailPage.jsx`](carbon-frontend/src/pages/catalog/DomainDetailPage.jsx) pattern

**Structure:**
```jsx
import BaseDetailPage from '../../components/detail/BaseDetailPage';
import DetailHeader from '../../components/detail/DetailHeader';
import AssetOverviewTab from './tabs/AssetOverviewTab';
import AssetEditTab from './tabs/AssetEditTab';
import AssetAuditTab from './tabs/AssetAuditTab';

export default function AssetDetailPage() {
  const { assetId } = useParams();
  const { token } = useAuth();
  const navigate = useNavigate();
  const { notify } = useNotification();

  const [asset, setAsset] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchAsset = async () => {
      try {
        setLoading(true);
        const data = await fetchAssetProfile(token, assetId);
        setAsset(data);
      } catch (err) {
        setError(err.message);
        notify({ message: err.message, type: 'error' });
      } finally {
        setLoading(false);
      }
    };
    fetchAsset();
  }, [assetId, token]);

  const headerComponent = (
    <DetailHeader
      title={asset?.title || 'Asset'}
      description={asset?.description}
      icon={asset?.asset_type === 'table' ? StorageIcon : ViewWeekIcon}
      onClose={() => navigate(-1)}
    />
  );

  return (
    <BaseDetailPage
      headerComponent={headerComponent}
      mainTabs={[
        { label: 'Overview', component: AssetOverviewTab },
        { label: 'Edit', component: AssetEditTab },
      ]}
      metricsTabs={[
        { label: 'Audit', component: AssetAuditTab },
      ]}
      loading={loading}
      error={error}
      onClose={() => navigate(-1)}
      storageKey="carbonAssetDetail"
      entityData={asset}
    />
  );
}
```

**Route Addition:**
```jsx
// In CatalogRoutes.jsx
<Route path="/assets/:assetId" element={<AssetDetailPage />} />
```

---

### Phase 2a: Tab Components

#### **AssetOverviewTab** - Read-only metadata display
```jsx
// File: carbon-frontend/src/pages/catalog/tabs/AssetOverviewTab.jsx

export default function AssetOverviewTab({ entityData: asset }) {
  if (!asset) return <CircularProgress />;

  return (
    <Box sx={{ p: 3 }}>
      <Stack spacing={2}>
        
        {/* Asset Identification */}
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Asset</Typography>
          <Stack spacing={1}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Type:</Typography>
              <Chip label={asset.asset_type === 'table' ? '🏠 Table' : '📄 Field'} size="small" />
            </Box>
            {asset.asset_type === 'table' ? (
              <>
                <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary">Table:</Typography>
                  <Typography>{asset.title}</Typography>
                </Box>
                <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary">ID:</Typography>
                  <Typography variant="body2" sx={{ fontFamily: 'monospace' }}>{asset.data_table}</Typography>
                </Box>
              </>
            ) : (
              <>
                <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
                  <Typography variant="subtitle2" color="text.secondary">Field:</Typography>
                  <Typography>{asset.title}</Typography>
                </Box>
              </>
            )}
          </Stack>
        </Paper>

        {/* Governance Metadata */}
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Governance</Typography>
          <Stack spacing={2}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Classification:</Typography>
              <Chip 
                label={asset.classification} 
                icon={<LockIcon />}
                variant="outlined"
                color={
                  asset.classification === 'pii' ? 'error' :
                  asset.classification === 'confidential' ? 'warning' :
                  'default'
                }
              />
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Domain:</Typography>
              <Typography>{asset.domain_name || '—'}</Typography>
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Owner:</Typography>
              <Typography>{asset.owner_name || '—'}</Typography>
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Steward:</Typography>
              <Typography>{asset.steward_name || '—'}</Typography>
            </Box>
          </Stack>
        </Paper>

        {/* Business Context */}
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Business Context</Typography>
          <Stack spacing={1}>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">Description:</Typography>
              <Typography>{asset.description || '—'}</Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">Semantic Type:</Typography>
              <Typography>{asset.semantic_type || '—'}</Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">Glossary Term:</Typography>
              <Typography>{asset.glossary_term_name || '—'}</Typography>
            </Box>
            <Box>
              <Typography variant="subtitle2" color="text.secondary">Tags:</Typography>
              <Box sx={{ display: 'flex', gap: 1, flexWrap: 'wrap', mt: 1 }}>
                {asset.tags && asset.tags.length > 0 ? (
                  asset.tags.map(tag => (
                    <Chip key={tag} label={tag} size="small" variant="outlined" />
                  ))
                ) : (
                  <Typography variant="body2" color="text.secondary">No tags</Typography>
                )}
              </Box>
            </Box>
          </Stack>
        </Paper>

        {/* Data Quality */}
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Data Quality</Typography>
          <Stack spacing={1}>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Status:</Typography>
              <QualityStatusBadge value={asset.quality_status} score={asset.quality_score} />
            </Box>
            <Box sx={{ display: 'grid', gridTemplateColumns: '150px 1fr', gap: 1 }}>
              <Typography variant="subtitle2" color="text.secondary">Score:</Typography>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                <LinearProgress variant="determinate" value={asset.quality_score || 0} sx={{ flex: 1 }} />
                <Typography variant="body2">{asset.quality_score || 0}%</Typography>
              </Box>
            </Box>
          </Stack>
        </Paper>

        {/* Audit Info */}
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Last Modified</Typography>
          <Stack spacing={1}>
            <Typography variant="body2">
              {new Date(asset.updated_at).toLocaleString()} by {asset.updated_by_name || 'System'}
            </Typography>
          </Stack>
        </Paper>

      </Stack>
    </Box>
  );
}
```

#### **AssetEditTab** - Governance form (editable fields)
```jsx
// File: carbon-frontend/src/pages/catalog/tabs/AssetEditTab.jsx

export default function AssetEditTab({ entityData: asset }) {
  const { token } = useAuth();
  const { notify } = useNotification();
  
  const [formData, setFormData] = useState(asset || {});
  const [saving, setSaving] = useState(false);
  const [domains, setDomains] = useState([]);
  const [users, setUsers] = useState([]);
  const [glossaryTerms, setGlossaryTerms] = useState([]);
  const [tags, setTags] = useState([]);

  useEffect(() => {
    fetchSelectOptions();
  }, [token]);

  const fetchSelectOptions = async () => {
    try {
      const [d, u, g, t] = await Promise.all([
        fetchDataDomains(token),
        fetchUsers(token),
        fetchGlossaryTerms(token),
        fetchTags(token),
      ]);
      setDomains(d || []);
      setUsers(u || []);
      setGlossaryTerms(g || []);
      setTags(t || []);
    } catch (err) {
      notify({ message: 'Failed to load options', type: 'error' });
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      await patchAssetProfile(token, asset.id, formData);
      notify({ message: 'Asset updated', type: 'success' });
    } catch (err) {
      notify({ message: err.message, type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      <Stack spacing={2}>
        
        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Classification</Typography>
          <Stack spacing={2}>
            <FormControl fullWidth>
              <InputLabel>Classification</InputLabel>
              <Select
                value={formData.classification}
                label="Classification"
                onChange={(e) => setFormData({...formData, classification: e.target.value})}
              >
                <MenuItem value="public">Public</MenuItem>
                <MenuItem value="internal">Internal</MenuItem>
                <MenuItem value="confidential">Confidential</MenuItem>
                <MenuItem value="pii">PII</MenuItem>
                <MenuItem value="sensitive">Sensitive</MenuItem>
              </Select>
            </FormControl>
            
            <FormControl fullWidth>
              <InputLabel>Domain</InputLabel>
              <Select
                value={formData.domain || ''}
                label="Domain"
                onChange={(e) => setFormData({...formData, domain: e.target.value})}
              >
                <MenuItem value="">None</MenuItem>
                {domains.map(d => (
                  <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </Paper>

        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Responsibility</Typography>
          <Stack spacing={2}>
            <FormControl fullWidth>
              <InputLabel>Owner</InputLabel>
              <Select
                value={formData.owner || ''}
                label="Owner"
                onChange={(e) => setFormData({...formData, owner: e.target.value})}
              >
                <MenuItem value="">None</MenuItem>
                {users.map(u => (
                  <MenuItem key={u.id} value={u.id}>{u.full_name || u.username}</MenuItem>
                ))}
              </Select>
            </FormControl>
            
            <FormControl fullWidth>
              <InputLabel>Steward</InputLabel>
              <Select
                value={formData.steward || ''}
                label="Steward"
                onChange={(e) => setFormData({...formData, steward: e.target.value})}
              >
                <MenuItem value="">None</MenuItem>
                {users.map(u => (
                  <MenuItem key={u.id} value={u.id}>{u.full_name || u.username}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </Paper>

        <Paper sx={{ p: 2 }}>
          <Typography variant="h6" gutterBottom>Business Context</Typography>
          <Stack spacing={2}>
            <TextField
              fullWidth
              multiline
              rows={3}
              label="Description"
              value={formData.description || ''}
              onChange={(e) => setFormData({...formData, description: e.target.value})}
            />
            
            <FormControl fullWidth>
              <InputLabel>Semantic Type</InputLabel>
              <Select
                value={formData.semantic_type || ''}
                label="Semantic Type"
                onChange={(e) => setFormData({...formData, semantic_type: e.target.value})}
              >
                <MenuItem value="">None</MenuItem>
                <MenuItem value="measure">Measure</MenuItem>
                <MenuItem value="dimension">Dimension</MenuItem>
                <MenuItem value="identifier">Identifier</MenuItem>
                <MenuItem value="metadata">Metadata</MenuItem>
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>Glossary Term</InputLabel>
              <Select
                value={formData.glossary_term || ''}
                label="Glossary Term"
                onChange={(e) => setFormData({...formData, glossary_term: e.target.value})}
              >
                <MenuItem value="">None</MenuItem>
                {glossaryTerms.map(g => (
                  <MenuItem key={g.id} value={g.id}>{g.term}</MenuItem>
                ))}
              </Select>
            </FormControl>

            <FormControl fullWidth>
              <InputLabel>Tags</InputLabel>
              <Select
                multiple
                value={formData.tags || []}
                label="Tags"
                onChange={(e) => setFormData({...formData, tags: e.target.value})}
              >
                {tags.map(t => (
                  <MenuItem key={t.id} value={t.id}>{t.name}</MenuItem>
                ))}
              </Select>
            </FormControl>
          </Stack>
        </Paper>

        <Box sx={{ display: 'flex', gap: 2, pt: 2 }}>
          <Button
            variant="contained"
            onClick={handleSave}
            disabled={saving}
          >
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
        </Box>

      </Stack>
    </Box>
  );
}
```

#### **AssetAuditTab** - Governance events
```jsx
// File: carbon-frontend/src/pages/catalog/tabs/AssetAuditTab.jsx

export default function AssetAuditTab({ entityData: asset }) {
  const { token } = useAuth();
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchEvents = async () => {
      try {
        setLoading(true);
        const data = await fetchGovernanceEvents(token, { asset_id: asset.id });
        setEvents(data || []);
      } finally {
        setLoading(false);
      }
    };
    if (asset?.id) fetchEvents();
  }, [asset?.id, token]);

  if (loading) return <CircularProgress />;

  return (
    <Box sx={{ p: 3 }}>
      {events.length === 0 ? (
        <Typography color="text.secondary">No audit events</Typography>
      ) : (
        <Timeline>
          {events.map(event => (
            <TimelineItem key={event.id}>
              <TimelineOppositeContent color="text.secondary">
                {new Date(event.timestamp).toLocaleString()}
              </TimelineOppositeContent>
              <TimelineSeparator>
                <TimelineDot color={event.action === 'create' ? 'success' : 'primary'} />
                <TimelineConnector />
              </TimelineSeparator>
              <TimelineContent>
                <Paper sx={{ p: 1.5 }}>
                  <Typography variant="subtitle2">
                    {event.user?.username || 'System'} {event.action}d this asset
                  </Typography>
                  {event.before && event.after && (
                    <Typography variant="caption" color="text.secondary">
                      Changed: {JSON.stringify(event.after)}
                    </Typography>
                  )}
                </Paper>
              </TimelineContent>
            </TimelineItem>
          ))}
        </Timeline>
      )}
    </Box>
  );
}
```

---

## HELPER COMPONENTS (REUSED, NOT CUSTOM)

Use these existing/simple components:

### QualityStatusBadge
```jsx
// Reuse or create minimal version
function QualityStatusBadge({ value, score }) {
  const colorMap = {
    passing: 'success',
    warning: 'warning',
    failing: 'error',
    unknown: 'default',
  };
  
  const iconMap = {
    passing: '✓',
    warning: '!',
    failing: '✕',
    unknown: '?',
  };

  return (
    <Chip
      label={`${value || 'unknown'} ${score ? `(${score}%)` : ''}`}
      color={colorMap[value] || 'default'}
      variant="filled"
      size="small"
      icon={<Box>{iconMap[value]}</Box>}
    />
  );
}
```

### ClassificationBadge
```jsx
function ClassificationBadge({ value }) {
  const labelMap = {
    public: '🟢 Public',
    internal: '🟡 Internal',
    confidential: '🔶 Confidential',
    pii: '🔴 PII',
    sensitive: '🔴 Sensitive',
  };

  return <Chip label={labelMap[value] || value} size="small" />;
}
```

---

## FILE STRUCTURE & CHANGES

```
carbon-frontend/src/
├─ pages/catalog/
│  ├─ AssetsPage.jsx                (MODIFIED: grid + filter + search)
│  ├─ AssetDetailPage.jsx           (NEW)
│  └─ tabs/
│     ├─ AssetOverviewTab.jsx       (NEW)
│     ├─ AssetEditTab.jsx           (NEW)
│     └─ AssetAuditTab.jsx          (NEW)
└─ CatalogRoutes.jsx                (MODIFIED: add route)
```

---

## API ENDPOINTS REQUIRED

**Existing (already used):**
- `GET /catalog/assets/` — list with optional filters
- `GET /catalog/assets/{id}/` — detail
- `PATCH /catalog/assets/{id}/` — partial update
- `DELETE /catalog/assets/{id}/` — delete
- `GET /catalog/governance-events/` — audit history

**Need to add select options (if missing):**
- `GET /catalog/domains/` — for domain select
- `GET /accounts/users/` — for owner/steward select
- `GET /catalog/glossary/` — for glossary term select
- `GET /catalog/tags/` — for tags select

---

## IMPLEMENTATION CHECKLIST

### Phase 1: List Page
- [ ] Modify [`AssetsPage.jsx`](carbon-frontend/src/pages/catalog/AssetsPage.jsx) to use MUI DataGrid
- [ ] Add columns: title, asset_type, domain_name, classification, quality_status, steward_name, actions
- [ ] Add sorting capability
- [ ] Add filter bar (domain, classification, quality_status)
- [ ] Add search bar
- [ ] Add pagination (10, 25, 50)
- [ ] Add action buttons: [View] [Edit] [Delete]
- [ ] Test with test data (call ensure_asset_profiles() if needed)

### Phase 2: Detail Page
- [ ] Create [`AssetDetailPage.jsx`](carbon-frontend/src/pages/catalog/AssetDetailPage.jsx) using BaseDetailPage pattern
- [ ] Create [`AssetOverviewTab.jsx`](carbon-frontend/src/pages/catalog/tabs/AssetOverviewTab.jsx)
- [ ] Create [`AssetEditTab.jsx`](carbon-frontend/src/pages/catalog/tabs/AssetEditTab.jsx)
- [ ] Create [`AssetAuditTab.jsx`](carbon-frontend/src/pages/catalog/tabs/AssetAuditTab.jsx)
- [ ] Add route in CatalogRoutes
- [ ] Test navigation from list → detail
- [ ] Test tab persistence in localStorage

### Phase 3: Polish
- [ ] Add NotificationProvider feedback (toast on save/delete)
- [ ] Apply theme colors to badges
- [ ] Add loading states
- [ ] Add error boundaries
- [ ] Test RBAC (admin only for edit/delete)
- [ ] Test responsive design (mobile)
- [ ] Test with 100+ assets (performance)

---

## STYLING & THEMING

**Use existing theme:**
```jsx
import { useTheme } from '@mui/material/styles';
const theme = useTheme();

// Colors
sx={{ bgcolor: theme.palette.background.alt }} // for filter bar
sx={{ color: theme.palette.primary.main }} // for emphasis
```

**Spacing (Material-UI standard):**
```jsx
sx={{ p: 2, m: 1, gap: 1, mb: 2 }} // padding, margin, gap, margin-bottom
```

**Typography (system-wide):**
```jsx
<Typography variant="h5"> // titles
<Typography variant="subtitle2"> // labels
<Typography variant="body2" color="text.secondary"> // secondary text
```

---

## PERFORMANCE CONSIDERATIONS

1. **Pagination:** Load 25 items per page (not all assets)
2. **Filtering:** Backend filter via query params (not frontend filter)
3. **Sorting:** Use DataGrid's built-in sorting
4. **Search:** Debounce search input (300ms) before API call
5. **Caching:** Store domain/user/glossary selects in React state (fetched once per page)

---

## TESTING STRATEGY

1. **Unit tests:** Tab components (mock asset data)
2. **Integration tests:** List → Detail navigation
3. **E2E tests:** Full workflow (list, filter, sort, detail, edit, save)
4. **Visual tests:** Responsive design on mobile/tablet/desktop

---

## NEXT STEPS

1. Review this plan with product/UX
2. Confirm backend APIs are available (or create if missing)
3. Start Phase 1 (list page with grid)
4. Once list works, start Phase 2 (detail page with tabs)
5. Polish and test in browser

---

**END OF IMPLEMENTATION PLAN**
