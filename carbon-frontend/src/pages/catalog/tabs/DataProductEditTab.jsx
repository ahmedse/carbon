// src/pages/catalog/tabs/DataProductEditTab.jsx
// Data Product Edit Tab: admin-gated metadata editing using the shared ProductForm
// plus destructive delete with table-count warning (ConfirmDialog — no window.confirm).
import React, { useState } from 'react';
import { Box, Button, Alert, Typography, Stack } from '@mui/material';
import SaveIcon from '@mui/icons-material/Save';
import DeleteIcon from '@mui/icons-material/Delete';
import { useNavigate } from 'react-router-dom';
import { DetailTabContent } from '../../../components/detail/DetailMainPanel';
import { useNotification } from '../../../components/NotificationProvider';
import { useAuth } from '../../../auth/AuthContext';
import ProductForm from '../../../components/dataproducts/ProductForm';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { updateModule, deleteModule } from '../../../api/modules';
import { DATA_PRODUCT } from '../../../constants/terminology';

export default function DataProductEditTab({ entityData, additionalProps = {} }) {
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const {
    orgUnits = [],
    isAdmin = false,
    onDataChanged = null,
  } = additionalProps;

  const [form, setForm] = useState(() => ({
    name: entityData?.name || '',
    description: entityData?.description || '',
    scope: entityData?.scope || 1,
    org_unit: entityData?.org_unit ?? '',
    is_locked: Boolean(entityData?.is_locked),
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">No data available</Typography>
      </DetailTabContent>
    );
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setError('Name is required'); return; }
    setSaving(true);
    setError(null);
    try {
      await updateModule(token, entityData.id, {
        name: form.name.trim(),
        description: form.description.trim(),
        scope: Number(form.scope),
        org_unit: form.org_unit === '' ? null : Number(form.org_unit),
        is_locked: form.is_locked,
      });
      notify({ message: `${DATA_PRODUCT} updated`, type: 'success' });
      if (onDataChanged) await onDataChanged();
    } catch (err) {
      setError(err.message || 'Save failed');
      notify({ message: err.message || 'Save failed', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteModule(token, entityData.id);
      notify({ message: `${DATA_PRODUCT} deleted`, type: 'success' });
      navigate('/catalog/products');
    } catch (err) {
      notifyFromError(err, 'Delete failed');
      setDeleteOpen(false);
    }
  };

  const tableCount = entityData.table_count ?? 0;
  const deleteMessage = tableCount > 0
    ? `"${entityData.name}" has ${tableCount} table${tableCount !== 1 ? 's' : ''}. Deleting it may remove associated data. This action cannot be undone.`
    : `Delete ${DATA_PRODUCT} "${entityData.name}"? This action cannot be undone.`;

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: 800 }}>
        {!isAdmin && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            You don't have permission to edit this {DATA_PRODUCT.toLowerCase()}.
          </Alert>
        )}

        <ProductForm
          form={form}
          onChange={setForm}
          orgUnits={orgUnits}
          error={error}
          readOnly={!isAdmin}
          showLock
        />

        <Stack direction="row" spacing={1} sx={{ mt: 3 }}>
          <Button
            variant="contained"
            size="small"
            startIcon={<SaveIcon />}
            onClick={handleSave}
            disabled={saving || !isAdmin}
          >
            {saving ? 'Saving…' : 'Save Changes'}
          </Button>
          {isAdmin && (
            <Button
              variant="outlined"
              color="error"
              size="small"
              startIcon={<DeleteIcon />}
              onClick={() => setDeleteOpen(true)}
            >
              Delete {DATA_PRODUCT}
            </Button>
          )}
        </Stack>

        <ConfirmDialog
          open={deleteOpen}
          title={`Delete ${DATA_PRODUCT}?`}
          message={deleteMessage}
          confirmLabel="Delete"
          destructive
          onConfirm={handleDelete}
          onCancel={() => setDeleteOpen(false)}
        />
      </Box>
    </DetailTabContent>
  );
}
