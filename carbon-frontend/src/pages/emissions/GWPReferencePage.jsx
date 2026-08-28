// src/pages/emissions/GWPReferencePage.jsx
// GWP Reference Values admin — CRUD for IPCC Global Warming Potential values
// AI-toolkit compliant: FilteredDataGrid shell, SystemDialog forms, ConfirmDialog,
// can() admin gate (CB-13), useNotification, 4 data states, CB-09 defensive arrays.

import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Box, Button, Stack, IconButton, TextField } from '@mui/material';
import { useTranslation } from 'react-i18next';
import AddIcon from '@mui/icons-material/Add';
import EditIcon from '@mui/icons-material/Edit';
import DeleteIcon from '@mui/icons-material/Delete';

import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { can } from '../../authz';
import { useNotification } from '../../components/NotificationProvider';
import FilteredDataGrid from '../../components/FilteredDataGrid';
import ConfirmDialog from '../../components/ConfirmDialog';
import SystemDialog from '../../components/SystemDialog';
import {
  fetchGWPValues,
  createGWPValue,
  updateGWPValue,
  deleteGWPValue,
} from '../../api/emissions-extended';

// Numeric display — GWP model is decimal_places=2; strip trailing zeros (CB-16 display pattern)
function fmtNum(v) {
  if (v == null || v === '') return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return v;
  return n.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

// ── GwpDialog ──────────────────────────────────────────────────────────

function GwpDialog({ open, gwpValue, onSave, onClose }) {
  const { t } = useTranslation('emissions');
  const [form, setForm] = useState({
    gas_name: '',
    gas_formula: '',
    gwp_ar5_100yr: '',
    gwp_ar6_100yr: '',
    gwp_ar5_20yr: '',
    gwp_ar6_20yr: '',
    cas_number: '',
    notes: '',
  });

  useEffect(() => {
    if (gwpValue) {
      setForm({
        gas_name: gwpValue.gas_name || '',
        gas_formula: gwpValue.gas_formula || '',
        gwp_ar5_100yr: gwpValue.gwp_ar5_100yr ?? '',
        gwp_ar6_100yr: gwpValue.gwp_ar6_100yr ?? '',
        gwp_ar5_20yr: gwpValue.gwp_ar5_20yr ?? '',
        gwp_ar6_20yr: gwpValue.gwp_ar6_20yr ?? '',
        cas_number: gwpValue.cas_number || '',
        notes: gwpValue.notes || '',
      });
    } else {
      setForm({
        gas_name: '',
        gas_formula: '',
        gwp_ar5_100yr: '',
        gwp_ar6_100yr: '',
        gwp_ar5_20yr: '',
        gwp_ar6_20yr: '',
        cas_number: '',
        notes: '',
      });
    }
  }, [gwpValue, open]);

  const handleChange = (e) => {
    const { name, value } = e.target;
    setForm((prev) => ({ ...prev, [name]: value }));
  };

  const handleSubmit = () => {
    onSave(form);
  };

  return (
    <SystemDialog
      open={open}
      title={gwpValue ? t('editGwpTitle') : t('createGwpTitle')}
      onClose={onClose}
      onCancel={onClose}
      cancelLabel={t('cancel')}
      actions={
        <Button variant="contained" size="small" onClick={handleSubmit}>
          {gwpValue ? t('update') : t('create')}
        </Button>
      }
      width={520}
      height={600}
      minWidth={420}
      minHeight={460}
      maxWidth="calc(100vw - 32px)"
      maxHeight="calc(100vh - 32px)"
    >
      <Box px={2} py={1}>
        <Stack spacing={2}>
          <TextField
            label={t('gasName')}
            name="gas_name"
            value={form.gas_name}
            onChange={handleChange}
            fullWidth
            required
            size="small"
          />
          <TextField
            label={t('gasFormula')}
            name="gas_formula"
            value={form.gas_formula}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder={t('gasFormulaPlaceholder')}
          />
          <Stack direction="row" spacing={2}>
            <TextField
              label={t('ar5_100')}
              name="gwp_ar5_100yr"
              type="number"
              value={form.gwp_ar5_100yr}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ step: 0.1 }}
            />
            <TextField
              label={t('ar6_100')}
              name="gwp_ar6_100yr"
              type="number"
              value={form.gwp_ar6_100yr}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ step: 0.1 }}
            />
          </Stack>
          <Stack direction="row" spacing={2}>
            <TextField
              label={t('ar5_20')}
              name="gwp_ar5_20yr"
              type="number"
              value={form.gwp_ar5_20yr}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ step: 0.1 }}
            />
            <TextField
              label={t('ar6_20')}
              name="gwp_ar6_20yr"
              type="number"
              value={form.gwp_ar6_20yr}
              onChange={handleChange}
              fullWidth
              size="small"
              inputProps={{ step: 0.1 }}
            />
          </Stack>
          <TextField
            label={t('casNumber')}
            name="cas_number"
            value={form.cas_number}
            onChange={handleChange}
            fullWidth
            size="small"
            placeholder={t('casPlaceholder')}
          />
          <TextField
            label={t('notes')}
            name="notes"
            value={form.notes}
            onChange={handleChange}
            fullWidth
            multiline
            rows={2}
            size="small"
          />
        </Stack>
      </Box>
    </SystemDialog>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export default function GWPReferencePage() {
  const { t } = useTranslation('emissions');
  useDocumentTitle(t('gwpTitle'));
  const { user, token, availablePerspectives, isGlobalAdminFlag, userCapabilities, context } = useAuth();
  const { notify, notifyFromError } = useNotification();

  const [gwpValues, setGwpValues] = useState([]);
  const [loading, setLoading] = useState(true);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [currentGwp, setCurrentGwp] = useState(null);
  const [searchText, setSearchText] = useState('');

  // Same gate as AdminRoute for this route (CB-13 — never user?.is_superuser/groups)
  const isAdmin = can(user, 'manage', 'carbon', {
    perspectives: availablePerspectives,
    isGlobalAdminFlag,
    capabilities: userCapabilities,
    modules: context?.modules || [],
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const data = await fetchGWPValues(token);
      // Defensive: always ensure arrays (CB-09)
      setGwpValues(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      notifyFromError(err, t('failedToLoadGwp'));
      setGwpValues([]);
    } finally {
      setLoading(false);
    }
  }, [token, notifyFromError, t]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = () => {
    setCurrentGwp(null);
    setDialogOpen(true);
  };

  const handleEdit = (gwp) => {
    setCurrentGwp(gwp);
    setDialogOpen(true);
  };

  const handleSave = async (formData) => {
    // Convert numeric fields — null when blank
    const payload = {
      ...formData,
      gwp_ar5_100yr: formData.gwp_ar5_100yr !== '' && formData.gwp_ar5_100yr != null ? Number(formData.gwp_ar5_100yr) : null,
      gwp_ar6_100yr: formData.gwp_ar6_100yr !== '' && formData.gwp_ar6_100yr != null ? Number(formData.gwp_ar6_100yr) : null,
      gwp_ar5_20yr: formData.gwp_ar5_20yr !== '' && formData.gwp_ar5_20yr != null ? Number(formData.gwp_ar5_20yr) : null,
      gwp_ar6_20yr: formData.gwp_ar6_20yr !== '' && formData.gwp_ar6_20yr != null ? Number(formData.gwp_ar6_20yr) : null,
    };
    try {
      if (currentGwp) {
        await updateGWPValue(currentGwp.id, payload, token);
        notify({ message: t('gwpUpdated'), type: 'success' });
      } else {
        await createGWPValue(payload, token);
        notify({ message: t('gwpCreated'), type: 'success' });
      }
      setDialogOpen(false);
      setCurrentGwp(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, t('failedToSaveGwp'));
    }
  };

  const handleDelete = async (gwpId) => {
    try {
      await deleteGWPValue(gwpId, token);
      notify({ message: t('gwpDeleted'), type: 'success' });
      setDeleteConfirm(null);
      await loadData();
    } catch (err) {
      notifyFromError(err, t('failedToDeleteGwp'));
    }
  };

  const filteredGwp = useMemo(() => {
    let filtered = gwpValues;

    if (searchText.trim()) {
      const query = searchText.toLowerCase();
      filtered = filtered.filter(
        (g) =>
          (g.gas_name && g.gas_name.toLowerCase().includes(query)) ||
          (g.gas_formula && g.gas_formula.toLowerCase().includes(query)) ||
          (g.cas_number && g.cas_number.toLowerCase().includes(query))
      );
    }

    return filtered;
  }, [gwpValues, searchText]);

  const handleClearFilters = () => {
    setSearchText('');
  };

  const columns = [
    { field: 'gas_name', headerName: t('gasName'), flex: 1, minWidth: 170 },
    { field: 'gas_formula', headerName: t('gasFormula'), width: 110 },
    {
      field: 'gwp_ar5_100yr',
      headerName: t('ar5_100'),
      width: 105,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => fmtNum(value),
    },
    {
      field: 'gwp_ar6_100yr',
      headerName: t('ar6_100'),
      width: 105,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => fmtNum(value),
    },
    {
      field: 'gwp_ar5_20yr',
      headerName: t('ar5_20'),
      width: 105,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => fmtNum(value),
    },
    {
      field: 'gwp_ar6_20yr',
      headerName: t('ar6_20'),
      width: 105,
      align: 'right',
      headerAlign: 'right',
      valueFormatter: (value) => fmtNum(value),
    },
    { field: 'cas_number', headerName: t('casNumber'), width: 130 },
    { field: 'notes', headerName: t('notes'), width: 220 },
    ...(isAdmin
      ? [
          {
            field: 'actions',
            headerName: t('actions'),
            width: 100,
            sortable: false,
            renderCell: (params) => (
              <Box sx={{ display: 'flex', gap: 0.5 }}>
                <IconButton size="small" onClick={() => handleEdit(params.row)}>
                  <EditIcon fontSize="small" />
                </IconButton>
                <IconButton
                  size="small"
                  onClick={() => setDeleteConfirm(params.row.id)}
                  sx={{ color: 'error.main' }}
                >
                  <DeleteIcon fontSize="small" />
                </IconButton>
              </Box>
            ),
          },
        ]
      : []),
  ];

  return (
    <Box sx={{ flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
      <FilteredDataGrid
        title={t('gwpTitle')}
        subtitle={t('gwpSubtitle', { count: filteredGwp.length, total: gwpValues.length })}
        description={t('gwpDescription')}
        actions={
          isAdmin ? (
            <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={handleCreate}>
              {t('newGwp')}
            </Button>
          ) : null
        }
        rows={filteredGwp}
        loading={loading}
        columns={columns}
        countLabel={t('gwpSubtitle', { count: filteredGwp.length, total: gwpValues.length })}
        searchValue={searchText}
        onSearchChange={setSearchText}
        filterDefs={[]}
        onClearFilters={handleClearFilters}
        emptyMessage={t('noGwpFound')}
        emptySubtext={t('tryAdjustingSearch')}
      />

      {/* Create/Edit Dialog (modal — design system primitive) */}
      <GwpDialog
        open={dialogOpen}
        gwpValue={currentGwp}
        onSave={handleSave}
        onClose={() => setDialogOpen(false)}
      />

      {/* Delete Confirmation Dialog */}
      <ConfirmDialog
        open={!!deleteConfirm}
        title={t('deleteGwpTitle')}
        message={t('deleteGwpMessage')}
        confirmLabel={t('delete')}
        destructive
        onConfirm={() => handleDelete(deleteConfirm)}
        onCancel={() => setDeleteConfirm(null)}
      />
    </Box>
  );
}
