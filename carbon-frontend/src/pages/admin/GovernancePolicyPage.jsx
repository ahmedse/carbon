// src/pages/admin/GovernancePolicyPage.jsx
// Admin page: manage configurable governance policies (delete/update rules).
// Role-gated by AdminRoute in App.jsx.

import React, { useEffect, useState, useCallback } from "react";
import {
  Box, Typography, Button, Paper, Table, TableHead, TableRow, TableCell, TableBody,
  IconButton, Dialog, DialogTitle, DialogContent, DialogActions, TextField,
  MenuItem, Chip, CircularProgress, Alert, Switch, FormControlLabel, Tooltip,
  Divider, Stack,
} from "@mui/material";
import PageHeader from "../../components/Page/PageHeader";
import PageContainer from "../../components/layout/PageContainer";
import useDocumentTitle from '../../hooks/useDocumentTitle';

import AddIcon from "@mui/icons-material/Add";
import EditIcon from "@mui/icons-material/Edit";
import DeleteIcon from "@mui/icons-material/Delete";
import PolicyIcon from "@mui/icons-material/Policy";
import { useAuth } from "../../auth/AuthContext";
import { useNotification } from "../../components/NotificationProvider";
import {
  fetchGovernancePolicies, createGovernancePolicy,
  updateGovernancePolicy, deleteGovernancePolicy, fetchDataDomains,
} from "../../api/catalog";
import { fetchOrgUnits } from "../../api/orgUnits";

const POLICY_TYPES = [
  { value: "module_delete", label: "Data Product — Delete" },
  { value: "table_delete", label: "Table — Delete" },
  { value: "module_update", label: "Data Product — Update" },
  { value: "table_update", label: "Table — Update" },
];

const SCOPE_TYPES = [
  { value: "global", label: "Global (all)" },
  { value: "scope", label: "Emission Scope" },
  { value: "org_unit", label: "Organization Unit" },
  { value: "domain", label: "Data Domain" },
];

const EMISSION_SCOPES = [
  { value: 1, label: "Scope 1" },
  { value: 2, label: "Scope 2" },
  { value: 3, label: "Scope 3" },
];

const EMPTY_FORM = {
  policy_type: "table_delete",
  name: "",
  description: "",
  enabled: true,
  scope_type: "global",
  emission_scope: "",
  org_unit: "",
  domain: "",
  config: "{\n  \"block_with_dependencies\": true\n}",
  error_message: "This action is blocked by governance policy.",
  remediation_steps: "Remove dependencies first\nThen retry the action",
};

export default function GovernancePolicyPage() {
  useDocumentTitle("Governance Policies");
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [policies, setPolicies] = useState([]);
  const [domains, setDomains] = useState([]);
  const [orgUnits, setOrgUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [saving, setSaving] = useState(false);
  const [jsonError, setJsonError] = useState("");

  const load = useCallback(() => {
    setLoading(true);
    setError("");
    Promise.all([
      fetchGovernancePolicies(token),
      fetchDataDomains(token).catch(() => []),
      fetchOrgUnits(token).catch(() => []),
    ])
      .then(([pols, doms, orgs]) => {
        setPolicies(Array.isArray(pols) ? pols : pols?.results || []);
        setDomains(Array.isArray(doms) ? doms : doms?.results || []);
        setOrgUnits(Array.isArray(orgs) ? orgs : orgs?.results || []);
      })
      .catch((e) => setError(e.message || "Failed to load policies"))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => { load(); }, [load]);

  const openCreate = () => {
    setEditingId(null);
    setForm(EMPTY_FORM);
    setJsonError("");
    setDialogOpen(true);
  };

  const openEdit = (p) => {
    setEditingId(p.id);
    setForm({
      policy_type: p.policy_type,
      name: p.name || "",
      description: p.description || "",
      enabled: p.enabled,
      scope_type: p.scope_type || "global",
      emission_scope: p.emission_scope ?? "",
      org_unit: p.org_unit ?? "",
      domain: p.domain ?? "",
      config: JSON.stringify(p.config || {}, null, 2),
      error_message: p.error_message || "",
      remediation_steps: (p.remediation_steps || []).join("\n"),
    });
    setJsonError("");
    setDialogOpen(true);
  };

  const handleSave = async () => {
    if (!form.name.trim()) {
      notify({ message: "Name is required", type: "error" });
      return;
    }
    let parsedConfig;
    try {
      parsedConfig = form.config.trim() ? JSON.parse(form.config) : {};
      setJsonError("");
    } catch (e) {
      setJsonError("Invalid JSON: " + e.message);
      return;
    }

    const payload = {
      policy_type: form.policy_type,
      name: form.name.trim(),
      description: form.description,
      enabled: form.enabled,
      scope_type: form.scope_type,
      emission_scope: form.scope_type === "scope" && form.emission_scope !== "" ? Number(form.emission_scope) : null,
      org_unit: form.scope_type === "org_unit" && form.org_unit !== "" ? form.org_unit : null,
      domain: form.scope_type === "domain" && form.domain !== "" ? form.domain : null,
      config: parsedConfig,
      error_message: form.error_message,
      remediation_steps: form.remediation_steps
        .split("\n")
        .map((s) => s.trim())
        .filter(Boolean),
    };

    setSaving(true);
    try {
      if (editingId) {
        await updateGovernancePolicy(token, editingId, payload);
        notify({ message: "Policy updated", type: "success" });
      } else {
        await createGovernancePolicy(token, payload);
        notify({ message: "Policy created", type: "success" });
      }
      setDialogOpen(false);
      load();
    } catch (err) {
      notifyFromError(err, "Failed to save policy");
    } finally {
      setSaving(false);
    }
  };

  const handleToggle = async (p) => {
    try {
      await updateGovernancePolicy(token, p.id, { enabled: !p.enabled });
      load();
    } catch (err) {
      notifyFromError(err, "Failed to update policy");
    }
  };

  const handleDelete = async (p) => {
    if (!window.confirm(`Delete policy "${p.name}"?`)) return;
    try {
      await deleteGovernancePolicy(token, p.id);
      notify({ message: "Policy deleted", type: "success" });
      load();
    } catch (err) {
      notifyFromError(err, "Failed to delete policy");
    }
  };

  const scopeLabel = (p) => {
    if (p.scope_type === "global") return "Global";
    if (p.scope_type === "scope") return `Scope ${p.emission_scope ?? "?"}`;
    if (p.scope_type === "org_unit") {
      return orgUnits.find((o) => o.id === p.org_unit)?.name || "Org Unit";
    }
    if (p.scope_type === "domain") {
      return domains.find((d) => d.id === p.domain)?.name || "Domain";
    }
    return p.scope_type;
  };

  const policyTypeLabel = (t) =>
    POLICY_TYPES.find((pt) => pt.value === t)?.label || t;

  if (loading) {
    return (
      <PageContainer sx={{ alignItems: "center", justifyContent: "center" }}>
        <CircularProgress />
      </PageContainer>
    );
  }

  return (
    <PageContainer>
      <Box sx={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", mb: 3, flexWrap: "wrap", gap: 2 }}>
        <PageHeader
          icon={PolicyIcon}
          title="Governance Policies"
          subtitle="Configure the rules that guard delete and update actions across the platform"
          description="Define data governance guardrails: deletion protection, update constraints, retention policies, and compliance rules scoped to org units or domains."
        />
        <Button variant="contained" startIcon={<AddIcon />} onClick={openCreate}>
          New Policy
        </Button>
      </Box>

      {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

      <Paper variant="outlined">
        <Table>
          <TableHead>
            <TableRow sx={{ bgcolor: "action.hover" }}>
              <TableCell sx={{ fontWeight: 600 }}>Name</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Applies to</TableCell>
              <TableCell sx={{ fontWeight: 600 }}>Scope</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="center">Enforced</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="center">Active</TableCell>
              <TableCell sx={{ fontWeight: 600 }} align="right">Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {policies.length === 0 ? (
              <TableRow>
                <TableCell colSpan={6} align="center">
                  <Typography color="text.secondary" sx={{ py: 3 }}>
                    No policies defined yet. Create one to start enforcing governance rules.
                  </Typography>
                </TableCell>
              </TableRow>
            ) : (
              policies.map((p) => (
                <TableRow key={p.id} hover>
                  <TableCell>
                    <Typography fontWeight={600}>{p.name}</Typography>
                    {p.description && (
                      <Typography variant="caption" color="text.secondary">{p.description}</Typography>
                    )}
                  </TableCell>
                  <TableCell>{policyTypeLabel(p.policy_type)}</TableCell>
                  <TableCell><Chip size="small" label={scopeLabel(p)} variant="outlined" /></TableCell>
                  <TableCell align="center">
                    <Chip
                      size="small"
                      label={`${p.usage_count || 0}×`}
                      color={p.usage_count > 0 ? "primary" : "default"}
                    />
                  </TableCell>
                  <TableCell align="center">
                    <Switch checked={p.enabled} onChange={() => handleToggle(p)} size="small" />
                  </TableCell>
                  <TableCell align="right">
                    <Tooltip title="Edit">
                      <IconButton size="small" onClick={() => openEdit(p)}>
                        <EditIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                    <Tooltip title="Delete">
                      <IconButton size="small" color="error" onClick={() => handleDelete(p)}>
                        <DeleteIcon fontSize="small" />
                      </IconButton>
                    </Tooltip>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </Paper>

      {/* Create/Edit dialog */}
      <Dialog open={dialogOpen} onClose={() => setDialogOpen(false)} maxWidth="md" fullWidth>
        <DialogTitle>{editingId ? "Edit Policy" : "New Policy"}</DialogTitle>
        <DialogContent dividers>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <TextField
              label="Name" value={form.name} required fullWidth
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
            <TextField
              label="Description" value={form.description} fullWidth multiline rows={2}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
            <TextField
              select label="Applies to" value={form.policy_type} fullWidth
              onChange={(e) => setForm({ ...form, policy_type: e.target.value })}
            >
              {POLICY_TYPES.map((t) => (
                <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>
              ))}
            </TextField>

            <Divider textAlign="left">
              <Typography variant="caption" color="text.secondary">SCOPE</Typography>
            </Divider>

            <TextField
              select label="Scope type" value={form.scope_type} fullWidth
              onChange={(e) => setForm({ ...form, scope_type: e.target.value })}
            >
              {SCOPE_TYPES.map((t) => (
                <MenuItem key={t.value} value={t.value}>{t.label}</MenuItem>
              ))}
            </TextField>

            {form.scope_type === "scope" && (
              <TextField
                select label="Emission scope" value={form.emission_scope} fullWidth
                onChange={(e) => setForm({ ...form, emission_scope: e.target.value })}
              >
                {EMISSION_SCOPES.map((s) => (
                  <MenuItem key={s.value} value={s.value}>{s.label}</MenuItem>
                ))}
              </TextField>
            )}
            {form.scope_type === "org_unit" && (
              <TextField
                select label="Organization unit" value={form.org_unit} fullWidth
                onChange={(e) => setForm({ ...form, org_unit: e.target.value })}
              >
                {orgUnits.map((o) => (
                  <MenuItem key={o.id} value={o.id}>{o.name}</MenuItem>
                ))}
              </TextField>
            )}
            {form.scope_type === "domain" && (
              <TextField
                select label="Data domain" value={form.domain} fullWidth
                onChange={(e) => setForm({ ...form, domain: e.target.value })}
              >
                {domains.map((d) => (
                  <MenuItem key={d.id} value={d.id}>{d.name}</MenuItem>
                ))}
              </TextField>
            )}

            <Divider textAlign="left">
              <Typography variant="caption" color="text.secondary">RULES & USER FEEDBACK</Typography>
            </Divider>

            <TextField
              label="Rules (JSON)" value={form.config} fullWidth multiline rows={5}
              error={!!jsonError} helperText={jsonError || "Machine-readable rule configuration"}
              onChange={(e) => setForm({ ...form, config: e.target.value })}
              sx={{ "& textarea": { fontFamily: "monospace", fontSize: "0.8rem" } }}
            />
            <TextField
              label="Message shown when blocked" value={form.error_message} fullWidth multiline rows={2}
              onChange={(e) => setForm({ ...form, error_message: e.target.value })}
            />
            <TextField
              label="Remediation steps (one per line)" value={form.remediation_steps} fullWidth multiline rows={3}
              helperText="Tells the user what to do to resolve the block"
              onChange={(e) => setForm({ ...form, remediation_steps: e.target.value })}
            />

            <FormControlLabel
              control={<Switch checked={form.enabled} onChange={(e) => setForm({ ...form, enabled: e.target.checked })} />}
              label="Policy active"
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setDialogOpen(false)}>Cancel</Button>
          <Button variant="contained" onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
