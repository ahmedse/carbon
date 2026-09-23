// Assignments ledger (ADR-0048). One row = one user, one duty, one anchor org unit.
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
import { fetchOrgUnits } from "../../api/orgUnits";
import { fetchUsers, fetchScopedRoles, createScopedRole, deleteScopedRole } from "../../api/accessControl";
import { apiFetch } from "../../api/api";

const EMPTY_FORM = { user: "", duty: "", org_unit: "", valid_from: "", valid_to: "" };

function dateLabel(value) {
  return value || "Open";
}

export default function AccessControlPage() {
  useDocumentTitle("Assignments");
  const { user } = useAuth();
  const token = user?.token;

  const [assignments, setAssignments] = useState([]);
  const [users, setUsers] = useState([]);
  const [duties, setDuties] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [viewRow, setViewRow] = useState(null);
  const [deleteTarget, setDeleteTarget] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [searchValue, setSearchValue] = useState("");
  const [filters, setFilters] = useState({ duty: "", provenance: "", scope: "" });
  const [highlightRow, setHighlightRow] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchScopedRoles(token),
      fetchUsers(token),
      apiFetch("accounts/duties/", { token }),
      fetchOrgUnits(token),
    ])
      .then(([a, u, catalog, o]) => {
        setAssignments(a);
        setUsers(u);
        setDuties(Array.isArray(catalog?.duties) ? catalog.duties : []);
        setOrgUnits(o);
      })
      .catch((e) => setError(e.message || "Failed to load assignments"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const handleSave = async () => {
    if (!form.user || !form.duty) { setError("User and duty are required."); return; }
    setSaving(true);
    setError("");
    try {
      await createScopedRole(token, {
        user: form.user,
        duty: form.duty,
        org_unit: form.org_unit === "" ? null : form.org_unit,
        valid_from: form.valid_from || null,
        valid_to: form.valid_to || null,
        is_active: true,
      });
      setDialogOpen(false);
      load();
    } catch (e) {
      setError(e.message || "Failed to create assignment");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!deleteTarget) return;
    setError("");
    try {
      await deleteScopedRole(token, deleteTarget.id);
      setDeleteTarget(null);
      load();
    } catch (e) {
      setError(e.message || "Delete failed");
    }
  };

  const filterDefs = useMemo(() => [
    {
      key: "duty",
      label: "Duty",
      emptyLabel: "All duties",
      options: duties.map((d) => ({ value: d.duty, label: d.duty })),
    },
    {
      key: "provenance",
      label: "Provenance",
      emptyLabel: "All",
      options: [
        { value: "birthright", label: "Birthright" },
        { value: "exception", label: "Exception" },
      ],
    },
    {
      key: "scope",
      label: "Anchor",
      emptyLabel: "All anchors",
      options: [
        { value: "global", label: "Global" },
        { value: "org", label: "One org unit" },
      ],
    },
  ], [duties]);

  const filteredRows = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    return assignments.filter((a) => {
      if (filters.duty && (a.duty || a.group) !== filters.duty) return false;
      if (filters.provenance && a.provenance !== filters.provenance) return false;
      if (filters.scope === "global" && a.org_unit) return false;
      if (filters.scope === "org" && !a.org_unit) return false;
      if (!q) return true;
      return [a.employee_name, a.user, a.duty, a.group, a.org_unit].filter(Boolean).join(" ").toLowerCase().includes(q);
    });
  }, [assignments, searchValue, filters]);

  const columns = useMemo(() => [
    {
      field: "employee_name",
      headerName: "Employee",
      flex: 1.3,
      minWidth: 200,
      valueGetter: (value, row) => row.employee_name || row.user,
      renderCell: (p) => (
        <Box sx={{ lineHeight: 1.2 }}>
          <Typography variant="body2" sx={{ fontWeight: 600 }}>{p.row.employee_name || p.row.user}</Typography>
          {p.row.employee_name ? (
            <Typography variant="caption" color="text.secondary">{p.row.user}</Typography>
          ) : null}
        </Box>
      ),
    },
    {
      field: "duty",
      headerName: "Duty",
      flex: 1,
      minWidth: 160,
      valueGetter: (value, row) => row.duty || row.group,
      renderCell: (p) => <Typography variant="body2" sx={{ fontFamily: "monospace" }}>{p.value}</Typography>,
    },
    {
      field: "org_unit",
      headerName: "Anchor org unit",
      flex: 1.2,
      minWidth: 180,
      valueGetter: (value, row) => row.org_unit || "Global",
    },
    {
      field: "provenance",
      headerName: "Provenance",
      width: 120,
      valueGetter: (value, row) => (row.provenance === "birthright" ? "Birthright" : "Exception"),
    },
    { field: "valid_from", headerName: "From", width: 110, valueGetter: (value, row) => dateLabel(row.valid_from) },
    { field: "valid_to", headerName: "Until", width: 110, valueGetter: (value, row) => dateLabel(row.valid_to) },
    {
      field: "is_active",
      headerName: "Active",
      width: 90,
      valueGetter: (value, row) => (row.is_active ? "Yes" : "No"),
    },
    {
      field: "actions",
      headerName: "",
      width: 90,
      sortable: false,
      filterable: false,
      renderCell: (p) => (
        <Box>
          <Tooltip title="View assignment">
            <IconButton size="small" aria-label="View assignment" onClick={(e) => { e.stopPropagation(); setViewRow(p.row); }}>
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
          <Tooltip title={p.row.provenance === "birthright" ? "Birthright is changed from position, manager, or profile" : "Remove exception"}>
            <span>
              <IconButton
                size="small"
                aria-label="Remove exception"
                disabled={p.row.provenance === "birthright"}
                sx={{ color: "error.main" }}
                onClick={(e) => { e.stopPropagation(); setDeleteTarget(p.row); }}
              >
                <DeleteRounded fontSize="small" />
              </IconButton>
            </span>
          </Tooltip>
        </Box>
      ),
    },
  ], []);

  const orgOptions = orgUnits.map((o) => ({ id: o.id, name: o.full_path || o.name }));

  return (
    <>
      {error && <Alert severity="error" sx={{ mx: 1, mt: 1 }} onClose={() => setError("")}>{error}</Alert>}
      <FilteredDataGrid
        title="Assignments"
        description="One row is one user, one duty, and one anchor org unit. Global means no anchor. Child units are included when access is checked, not stored as more rows."
        actions={
          <Button variant="contained" size="small" startIcon={<AddRounded />} onClick={() => { setForm(EMPTY_FORM); setDialogOpen(true); }}>
            Grant exception
          </Button>
        }
        rows={filteredRows}
        columns={columns}
        loading={loading}
        countLabel={`${filteredRows.length} of ${assignments.length} assignments`}
        searchValue={searchValue}
        onSearchChange={setSearchValue}
        searchPlaceholder="Search user, duty, org unit…"
        filterDefs={filterDefs}
        filterValues={filters}
        onFilterChange={(key, value) => setFilters((prev) => ({ ...prev, [key]: value }))}
        onClearFilters={() => { setSearchValue(""); setFilters({ duty: "", provenance: "", scope: "" }); }}
        emptyMessage="No assignments match."
        highlightRow={(row) => row.id === highlightRow}
        onRowClick={(params) => setHighlightRow(params.row.id)}
      />

      <SystemDialog
        open={dialogOpen}
        title="Grant exception"
        onClose={() => setDialogOpen(false)}
        onCancel={() => setDialogOpen(false)}
        cancelLabel="Cancel"
        actions={
          <Button variant="contained" size="small" onClick={handleSave} disabled={saving}>
            {saving ? "Saving…" : "Grant"}
          </Button>
        }
        width={520}
        height={520}
        minWidth={420}
        minHeight={420}
      >
        <Box px={2} py={1} sx={{ display: "grid", gap: 2 }}>
          <SearchSelect
            label="User"
            required
            options={users}
            valueKey="id"
            labelKey="username"
            value={form.user}
            onChange={(v) => setForm({ ...form, user: v?.id ?? "" })}
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
            helperText="One duty on this row. The same person can have more rows on other anchors."
          />
          <SearchSelect
            label="Anchor org unit"
            options={orgOptions}
            valueKey="id"
            labelKey="name"
            value={form.org_unit}
            onChange={(v) => setForm({ ...form, org_unit: v?.id ?? "" })}
            helperText="One anchor, or empty for global. Descendants are included at read time."
          />
          <TextField
            label="Valid from" type="date" fullWidth size="small"
            value={form.valid_from} onChange={(e) => setForm({ ...form, valid_from: e.target.value })}
            InputLabelProps={{ shrink: true }}
          />
          <TextField
            label="Valid until" type="date" fullWidth size="small"
            value={form.valid_to} onChange={(e) => setForm({ ...form, valid_to: e.target.value })}
            InputLabelProps={{ shrink: true }}
            helperText="Empty means the exception does not expire."
          />
        </Box>
      </SystemDialog>

      <SystemDialog
        open={Boolean(viewRow)}
        title="Assignment"
        onClose={() => setViewRow(null)}
        onCancel={() => setViewRow(null)}
        cancelLabel="Close"
        showCancel={false}
        width={480}
        height={360}
        minWidth={400}
        minHeight={280}
      >
        {viewRow && (
          <Box px={2} py={1} sx={{ display: "grid", gap: 1 }}>
            <Typography variant="body2"><b>Employee.</b> {viewRow.employee_name || viewRow.user}</Typography>
            <Typography variant="body2"><b>User.</b> {viewRow.user}</Typography>
            <Typography variant="body2"><b>Duty.</b> {viewRow.duty || viewRow.group}</Typography>
            <Typography variant="body2"><b>Anchor org unit.</b> {viewRow.org_unit || "Global"}</Typography>
            <Typography variant="body2"><b>Provenance.</b> {viewRow.provenance === "birthright" ? "Birthright" : "Exception"}</Typography>
            <Typography variant="body2"><b>From.</b> {dateLabel(viewRow.valid_from)} <b>Until.</b> {dateLabel(viewRow.valid_to)}</Typography>
            <Typography variant="body2" color="text.secondary">
              This row is not a list of org units. Another anchor is another assignment.
            </Typography>
          </Box>
        )}
      </SystemDialog>

      <ConfirmDialog
        open={Boolean(deleteTarget)}
        title="Remove exception"
        message={deleteTarget ? `Remove ${deleteTarget.employee_name || deleteTarget.user}'s ${deleteTarget.duty || deleteTarget.group} on ${deleteTarget.org_unit || "global"}?` : ""}
        confirmLabel="Remove"
        destructive
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </>
  );
}
