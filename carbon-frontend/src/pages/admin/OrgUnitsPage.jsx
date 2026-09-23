// src/pages/admin/OrgUnitsPage.jsx
// Admin page: view + manage the OrgUnit tree. Role-gated by AdminRoute in App.jsx.
// List chrome is FilteredDataGrid (design-system RULE 14): search, type, parent.
import React, { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import {
  Button, IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  Chip, Alert, Tooltip,
} from "@mui/material";
import { useTranslation } from "react-i18next";
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { ORG_TYPE_KEYS as ORG_TYPES, orgTypeLabelKey } from '../../constants/orgTypes';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import { SearchSelect } from '../../components/Form';

import AddRounded from "@mui/icons-material/AddRounded";
import EditRounded from "@mui/icons-material/EditRounded";
import DeleteRounded from "@mui/icons-material/DeleteRounded";
import VisibilityRounded from "@mui/icons-material/VisibilityRounded";
import { useAuth } from "../../auth/AuthContext";
import {
  fetchOrgUnits, createOrgUnit, updateOrgUnit, deleteOrgUnit,
} from "../../api/orgUnits";

const ROOT_PARENT = '__root__';

const EMPTY_FORM = { name: "", org_type: "department", parent: "", code: "", description: "" };

export default function OrgUnitsPage() {
  useDocumentTitle("Org Units");
  const navigate = useNavigate();
  const { t } = useTranslation('catalog');
  const { user } = useAuth();
  const token = user?.token;

  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [searchValue, setSearchValue] = useState('');
  const [gridFilters, setGridFilters] = useState({ org_type: '', parent: '' });
  const [highlightId, setHighlightId] = useState(null);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    fetchOrgUnits(token)
      .then((data) => setUnits(data))
      .catch((e) => setError(e.message || "Failed to load org units"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setDialogOpen(true);
  };

  const openEdit = useCallback((u) => {
    setEditingId(u.id);
    setForm({
      name: u.name || "",
      org_type: u.org_type || "department",
      parent: u.parent || "",
      code: u.code || "",
      description: u.description || "",
    });
    setDialogOpen(true);
  }, []);

  const handleSave = async () => {
    if (!form.name.trim()) { setError("Name is required."); return; }
    setSaving(true);
    setError("");
    const payload = {
      name: form.name.trim(),
      org_type: form.org_type,
      parent: form.parent === "" ? null : form.parent,
      code: form.code.trim(),
      description: form.description.trim(),
    };
    try {
      if (editingId) await updateOrgUnit(token, editingId, payload);
      else await createOrgUnit(token, payload);
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = useCallback(async (u) => {
    if (!window.confirm(`Delete org unit "${u.name}"? This cannot be undone.`)) return;
    setError("");
    try {
      await deleteOrgUnit(token, u.id);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  }, [token, load]);

  const nameById = useMemo(
    () => Object.fromEntries(units.map((u) => [u.id, u.name])),
    [units],
  );
  const typeLabel = useCallback(
    (key) => t(orgTypeLabelKey(key), { defaultValue: key || '—' }),
    [t],
  );

  const filteredUnits = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return units.filter((u) => {
      if (gridFilters.org_type && u.org_type !== gridFilters.org_type) return false;
      if (gridFilters.parent === ROOT_PARENT) {
        if (u.parent) return false;
      } else if (gridFilters.parent && String(u.parent) !== String(gridFilters.parent)) {
        return false;
      }
      if (!q) return true;
      const hay = [
        u.name,
        u.code,
        u.full_path,
        u.parent ? nameById[u.parent] : '',
        typeLabel(u.org_type),
      ].filter(Boolean).join(' ').toLowerCase();
      return hay.includes(q);
    });
  }, [units, searchValue, gridFilters, nameById, typeLabel]);

  const filterDefs = useMemo(() => [
    {
      key: 'org_type',
      label: 'Type',
      emptyLabel: 'All types',
      options: ORG_TYPES.map((value) => ({ value, label: typeLabel(value) })),
    },
    {
      key: 'parent',
      label: 'Parent',
      emptyLabel: 'All parents',
      options: [
        { value: ROOT_PARENT, label: 'Top level' },
        ...units.map((u) => ({
          value: String(u.id),
          label: u.full_path || u.name,
        })),
      ],
    },
  ], [units, typeLabel]);

  const columns = useMemo(() => [
    { field: 'name', headerName: 'Name', flex: 1, minWidth: 180 },
    {
      field: 'org_type',
      headerName: 'Type',
      width: 140,
      valueGetter: (value) => typeLabel(value),
      renderCell: (params) => (
        <Chip size="small" variant="outlined" label={params.value} />
      ),
    },
    {
      field: 'parent',
      headerName: 'Parent',
      flex: 1,
      minWidth: 180,
      valueGetter: (value) => (value ? (nameById[value] || value) : '—'),
    },
    {
      field: 'code',
      headerName: 'Code',
      width: 180,
      valueGetter: (value) => value || '—',
    },
    {
      field: 'full_path',
      headerName: 'Path',
      flex: 1.4,
      minWidth: 220,
      valueGetter: (value, row) => value || row.name || '—',
    },
    {
      field: 'actions',
      headerName: 'Actions',
      width: 130,
      sortable: false,
      filterable: false,
      align: 'right',
      headerAlign: 'right',
      renderCell: (params) => (
        <>
          <Tooltip title="Open">
            <IconButton
              size="small"
              color="primary"
              aria-label={`Open ${params.row.name}`}
              onClick={() => navigate(`/admin/org-units/${params.row.id}`)}
            >
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Edit">
            <IconButton size="small" aria-label={`Edit ${params.row.name}`} onClick={() => openEdit(params.row)}>
              <EditRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Delete">
            <IconButton
              size="small"
              color="error"
              aria-label={`Delete ${params.row.name}`}
              onClick={() => handleDelete(params.row)}
            >
              <DeleteRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        </>
      ),
    },
  ], [nameById, typeLabel, navigate, openEdit, handleDelete]);

  return (
    <PageContainer>
      <PageHeader
        title="Organisation Units"
        description="Manage the org structure (campuses, colleges, departments). Data ownership and access are scoped to these units."
        actions={(
          <Button variant="contained" size="small" startIcon={<AddRounded />} onClick={openCreate}>
            New Org Unit
          </Button>
        )}
      />

      {error && <Alert severity="error" sx={{ mb: 2 }} onClose={() => setError("")}>{error}</Alert>}

      <FilteredDataGrid
        embedded
        rows={filteredUnits}
        columns={columns}
        loading={loading}
        getRowId={(row) => row.id}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search by name, code, or path…"
        filterDefs={filterDefs}
        filterValues={gridFilters}
        onFilterChange={(key, value) => setGridFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => {
          setSearchValue('');
          setGridFilters({ org_type: '', parent: '' });
        }}
        emptyMessage="No org units found."
        countLabel={loading ? '' : `${filteredUnits.length} of ${units.length}`}
        pageSize={25}
        height={560}
        initialState={{ sorting: { sortModel: [{ field: 'name', sort: 'asc' }] } }}
        highlightRow={(row) => row.id === highlightId}
        onRowClick={(params) => setHighlightId(params.row.id)}
      />

      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} fullWidth maxWidth="sm">
        <DialogTitle>{editingId ? "Edit Org Unit" : "New Org Unit"}</DialogTitle>
        <DialogContent>
          <TextField
            label="Name" fullWidth required margin="normal"
            value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })}
          />
          <SearchSelect
            label="Type"
            options={ORG_TYPES.map((value) => ({ value, label: typeLabel(value) }))}
            value={form.org_type}
            onChange={(v) => setForm({ ...form, org_type: v?.value ?? 'department' })}
            clearable={false}
            required
          />
          <SearchSelect
            label="Parent"
            options={[
              { value: '', label: '— None (top level) —' },
              ...units.filter((u) => u.id !== editingId).map((u) => ({
                value: u.id,
                label: u.full_path || u.name,
              })),
            ]}
            value={form.parent}
            onChange={(v) => setForm({ ...form, parent: v?.value ?? '' })}
            clearable={false}
          />
          <TextField
            label="Code" fullWidth margin="normal"
            value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })}
          />
          <TextField
            label="Description" fullWidth multiline minRows={2} margin="normal"
            value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
