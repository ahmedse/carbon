// src/pages/catalog/tabs/DataProductEditTab.jsx
// Data Product Edit Tab: admin-gated metadata editing using the shared ProductForm
// plus destructive delete with table-count warning (ConfirmDialog — no window.confirm).
import React, { useState } from 'react';
import { useTranslation } from 'react-i18next';
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
  const { t } = useTranslation('catalog');
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
    org_unit: entityData?.org_unit ?? '',
    is_locked: Boolean(entityData?.is_locked),
  }));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [deleteOpen, setDeleteOpen] = useState(false);

  if (!entityData) {
    return (
      <DetailTabContent>
        <Typography variant="body2" color="text.secondary">{t('noDataAvailable')}</Typography>
      </DetailTabContent>
    );
  }

  const handleSave = async () => {
    if (!form.name.trim()) { setError(t('nameRequiredShort')); return; }
    setSaving(true);
    setError(null);
    try {
      await updateModule(token, entityData.id, {
        name: form.name.trim(),
        description: form.description.trim(),
        org_unit: form.org_unit === '' ? null : Number(form.org_unit),
        is_locked: form.is_locked,
      });
      notify({ message: `${DATA_PRODUCT} ${t('updated')}`, type: 'success' });
      if (onDataChanged) await onDataChanged();
    } catch (err) {
      setError(err.message || t('saveFailed'));
      notify({ message: err.message || t('saveFailed'), type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    try {
      await deleteModule(token, entityData.id);
      notify({ message: `${DATA_PRODUCT} ${t('deleted')}`, type: 'success' });
      navigate('/catalog/products');
    } catch (err) {
      notifyFromError(err, t('delete'));
      setDeleteOpen(false);
    }
  };

  const tableCount = entityData.table_count ?? 0;
  const deleteMessage = tableCount > 0
    ? t('deleteWarningTables', { name: entityData.name, count: tableCount })
    : t('deleteWarningSimple', { type: DATA_PRODUCT, name: entityData.name });

  return (
    <DetailTabContent>
      <Box sx={{ maxWidth: 800 }}>
        {!isAdmin && (
          <Alert severity="warning" sx={{ mb: 2 }}>
            {t('permissionDeniedEdit')} {DATA_PRODUCT.toLowerCase()}.
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
            {saving ? t('saving') : t('saveChanges')}
          </Button>
          {isAdmin && (
            <Button
              variant="outlined"
              color="error"
              size="small"
              startIcon={<DeleteIcon />}
              onClick={() => setDeleteOpen(true)}
            >
              {t('delete')} {DATA_PRODUCT}
            </Button>
          )}
        </Stack>

        <ConfirmDialog
          open={deleteOpen}
          title={t('deleteConfirmation', { type: DATA_PRODUCT })}
          message={deleteMessage}
          confirmLabel={t('delete')}
          destructive
          onConfirm={handleDelete}
          onCancel={() => setDeleteOpen(false)}
        />
      </Box>
    </DetailTabContent>
  );
}
