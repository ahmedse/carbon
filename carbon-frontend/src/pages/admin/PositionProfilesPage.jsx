// Position code → one duty and a scope kind. The concrete org is chosen when the engine runs.
import React, { useCallback, useEffect, useMemo, useState } from "react";
import { Alert, Box, Button, IconButton, TextField, Tooltip, Typography } from "@mui/material";
import AddRounded from "@mui/icons-material/AddRounded";
import DeleteRounded from "@mui/icons-material/DeleteRounded";
import VisibilityRounded from "@mui/icons-material/VisibilityRounded";
import useDocumentTitle from "../../hooks/useDocumentTitle";
import FilteredDataGrid from "../../components/FilteredDataGrid";
import SystemDialog from "../../components/SystemDialog";
import ConfirmDialog from "../../components/ConfirmDialog";
import { SearchSelect } from "../../components/Form";
import { useAuth } from "../../auth/AuthContext";
import { apiFetch } from "../../api/api";

const EMPTY = { position_code: "", duty: "", scope: "home_org" };
const SCOPES = [
  { value: "home_org", label: "Home org unit" },
  { value: "managed_org", label: "Each org unit this person runs" },
  { value: "global", label: "Global" },
];

function unwrap(data) {
  if (Array.isArray(data)) return data;
  if (data && Array.isArray(data.results)) return data.results;
  return [];
}

export default function PositionProfilesPage() {
  useDocumentTitle("Position profiles");
  const { user } = useAuth();
  const token = user?.token;
  const [rows, setRows] = useState([]);
  const [duties, setDuties] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [viewRow, setViewRow] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(EMPTY);
  const [saving, setSaving] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [filters, setFilters] = useState({ duty: "", scope: "" });
  const [highlightRow, setHighlightRow] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [profiles, catalog] = await Promise.all([
        apiFetch("accounts/duty-profiles/", { token }),
        apiFetch("accounts/duties/", { token }),
      ]);
      setRows(unwrap(profiles));
      setDuties(Array.isArray(catalog?.duties) ? catalog.duties : []);
    } catch (e) {
      setError(e.message || "Failed to load position profiles");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!form.position_code.trim() || !form.duty) {
      setError("Position code and duty are required.");
      return;
    }
    setSaving(true);
    setError("");
    try {
      await apiFetch("accounts/duty-profiles/", {
        method: "POST",
        token,
        body: { position_code: form.position_code.trim(), duty: form.duty, scope: form.scope },
      });
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || "Save failed");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setError("");
    try {
      await apiFetch(`accounts/duty-profiles/${deleteTarget.id}/`, { method: "DELETE", token });
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  };

  const scopeLabel = (value) => SCOPES.find((s) => s.value === value)?.label || value;

  const filterDefs = useMemo(() => [
    {
      key: "duty",
      label: "Duty",
      emptyLabel: "All duties",
      options: duties.map((d) => ({ value: d.duty, label: d.duty })),
    },
    {
      key: "scope",
      label: "Scope",
      emptyLabel: "All scopes",
      options: SCOPES,
    },
  ], [duties]);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return rows.filter((row) => {
      if (filters.duty && row.duty !== filters.duty) return false;
      if (filters.scope && row.scope !== filters.scope) return false;
      if (!q) return true;
      return [row.position_code, row.duty, scopeLabel(row.scope)].join(" ").toLowerCase().includes(q);
    });
  }, [rows, searchValue, filters]);

  const columns = useMemo(() => [
    { field: "position_code", headerName: "Position code", flex: 1, minWidth: 140, renderCell: (p) => <Typography sx={{ fontWeight: 600 }}>{p.value}</Typography> },
    { field: "duty", headerName: "Duty", flex: 1, minWidth: 160, renderCell: (p) => <Typography variant="body2" sx={{ fontFamily: "monospace" }}>{p.value}</Typography> },
    { field: "scope", headerName: "Scope", flex: 1.2, minWidth: 200, valueGetter: (value, row) => scopeLabel(row.scope) },
    {
      field: "actions",
      headerName: "",
      width: 90,
      sortable: false,
      filterable: false,
      renderCell: (p) => (
        <Box>
          <Tooltip title="View profile">
            <IconButton size="small" aria-label="View profile" onClick={(e) => { e.stopPropagation(); setViewRow(p.row); }}>
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title="Remove profile">
            <IconButton size="small" aria-label="Remove profile" sx={{ color: "error.main" }} onClick={(e) => { e.stopPropagation(); setDeleteTarget(p.row); }}>
              <DeleteRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        </Box>
      ),
    },
  ], []);

  return (
    <>
      {error && <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError("")}>{error}</Alert>}
      <FilteredDataGrid
        title="Position profiles"
        description="A position code grants one duty. Scope says which org the engine uses: the person's home unit, each unit they run, or global. The profile does not store a list of org units."
        actions={
          <Button variant="contained" size="small" startIcon={<AddRounded />} onClick={() => { setForm(EMPTY); setDialogOpen(true); }}>
            Add profile
          </Button>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={`${filteredRows.length} of ${rows.length} profiles`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search position code or duty…"
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => { setSearchValue(""); setFilters({ duty: "", scope: "" }); }}
        emptyMessage="No position profiles yet."
        emptySubtext="Add a profile to grant a duty from a position code."
        highlightRow={(row) => row.id === highlightRow}
        onRowClick={(params) => setHighlightRow(params.row.id)}
      />

      <SystemDialog
        open={dialogOpen}
        title="Add position profile"
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel="Cancel"
        actions={
          <Button variant="contained" size="small" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Save"}
          </Button>
        }
        width={480}
        height={420}
        minWidth={400}
        minHeight={360}
      >
        <Box px={2} py={1} sx={{ display: "grid", gap: 2 }}>
          <TextField
            label="Position code"
            fullWidth
            required
            size="small"
            value={form.position_code}
            onChange={(e) => setForm({ ...form, position_code: e.target.value })}
            helperText="Matches Position.code, for example HR-DIR. The title is not used."
          />
          <SearchSelect
            label="Duty"
            required
            options={duties}
            valueKey="duty"
            labelKey="duty"
            groupBy={(o) => o.domain}
            value={form.duty}
            onChange={(v) => setForm({ ...form, duty: v?.duty ?? "" })}
          />
          <SearchSelect
            label="Scope"
            required
            clearable={false}
            options={SCOPES}
            valueKey="value"
            labelKey="label"
            value={form.scope}
            onChange={(v) => setForm({ ...form, scope: v?.value ?? "home_org" })}
          />
        </Box>
      </SystemDialog>

      <SystemDialog
        open={Boolean(viewRow)}
        title="Position profile"
        onClose={() => setViewRow(null)}
        onCancel={() => setViewRow(null)}
        cancelLabel="Close"
        width={440}
        height={280}
        minWidth={380}
        minHeight={220}
      >
        {viewRow && (
          <Box px={2} py={1} sx={{ display: "grid", gap: 1 }}>
            <Typography variant="body2"><b>Position code.</b> {viewRow.position_code}</Typography>
            <Typography variant="body2"><b>Duty.</b> {viewRow.duty}</Typography>
            <Typography variant="body2"><b>Scope.</b> {scopeLabel(viewRow.scope)}</Typography>
            <Typography variant="body2" color="text.secondary">
              Saving recalculates everyone who holds this code. The org unit is resolved then, one anchor per assignment.
            </Typography>
          </Box>
        )}
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Remove profile"
        message={deleteTarget ? `Remove ${deleteTarget.position_code} → ${deleteTarget.duty}? Incumbents lose this birthright.` : ""}
        confirmLabel="Remove"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
