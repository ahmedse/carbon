import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Chip, IconButton, TextField, Tooltip } from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import CategoryIcon from '@mui/icons-material/Category';
import VisibilityRounded from '@mui/icons-material/VisibilityRounded';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../components/layout/PageContainer';
import PageHeader from '../../../components/Page/PageHeader';
import LoadingSkeleton from '../../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../../components/Page/ErrorAlert';
import FilteredDataGrid from '../../../components/FilteredDataGrid';
import FormField from '../../../components/Form/FormField';
import { SearchSelect } from '../../../components/Form';
import SystemDialog from '../../../components/SystemDialog';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { createInboundCartridge, fetchInboundCartridges } from '../../../api/inbound';

const LIST = '/admin/migration/cartridges';

export default function CartridgeListPage() {
  const { t } = useTranslation('migration');
  const { t: tCommon } = useTranslation('common');
  useDocumentTitle(t('cartridgeTitle'));
  const navigate = useNavigate();
  const { token } = useAuth();
  const { notifyFromError } = useNotification();
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchValue, setSearchValue] = useState('');
  const [selectedId, setSelectedId] = useState(null);
  const [open, setOpen] = useState(false);
  const [creating, setCreating] = useState(false);
  const [key, setKey] = useState('');
  const [label, setLabel] = useState('');
  const [labelAr, setLabelAr] = useState('');
  const [fieldName, setFieldName] = useState('');
  const [fieldLabel, setFieldLabel] = useState('');
  const [required, setRequired] = useState('yes');

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInboundCartridges(token);
      setRows(Array.isArray(data) ? data : data.results || []);
    } catch (err) {
      setError(err?.status === 403 ? 'forbidden' : (err.message || t('cartridgeLoadFailed')));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => { load(); }, [load]);

  const filtered = useMemo(() => {
    const q = searchValue.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((row) => (
      row.key.toLowerCase().includes(q) || (row.label || '').toLowerCase().includes(q)
    ));
  }, [rows, searchValue]);

  const columns = useMemo(() => [
    { field: 'key', headerName: t('cartridgeColKey'), flex: 1, minWidth: 180 },
    { field: 'owner_app', headerName: t('cartridgeColOwner'), width: 120 },
    { field: 'label', headerName: t('cartridgeColLabel'), flex: 1, minWidth: 160 },
    {
      field: 'bound',
      headerName: t('cartridgeColBound'),
      width: 130,
      renderCell: (params) => (
        <Chip
          size="small"
          label={params.value ? t('cartridgeBound') : t('cartridgeUnbound')}
          color={params.value ? 'success' : 'warning'}
          variant="outlined"
        />
      ),
    },
    {
      field: 'enabled',
      headerName: t('cartridgeColEnabled'),
      width: 120,
      renderCell: (params) => (
        <Chip
          size="small"
          label={params.value ? t('cartridgeEnabled') : t('cartridgeDisabled')}
          variant="outlined"
        />
      ),
    },
    { field: 'batch_count', headerName: t('cartridgeColBatches'), width: 100 },
    {
      field: 'last_status',
      headerName: t('cartridgeColLast'),
      width: 120,
      valueGetter: (value) => value || '—',
    },
    {
      field: 'actions',
      headerName: t('cartridgeColActions'),
      width: 72,
      sortable: false,
      filterable: false,
      renderCell: (params) => {
        const openLabel = t('cartridgeOpen');
        return (
          <Tooltip title={openLabel}>
            <IconButton
              size="small"
              color="primary"
              aria-label={openLabel}
              onClick={(event) => {
                event.stopPropagation();
                navigate(`${LIST}/${params.row.id}`);
              }}
            >
              <VisibilityRounded fontSize="small" />
            </IconButton>
          </Tooltip>
        );
      },
    },
  ], [navigate, t]);

  const onCreate = async () => {
    setCreating(true);
    try {
      const created = await createInboundCartridge(token, {
        key: key.trim(),
        kind: 'typed_object',
        label: label.trim(),
        label_ar: labelAr.trim(),
        fields: [{
          name: fieldName.trim(),
          label: fieldLabel.trim(),
          required: required === 'yes',
        }],
      });
      setOpen(false);
      navigate(`${LIST}/${created.id}`);
    } catch (err) {
      notifyFromError(err, t('cartridgeCreateFailed'));
    } finally {
      setCreating(false);
    }
  };

  const canSubmit = key.trim() && label.trim() && fieldName.trim() && fieldLabel.trim();

  return (
    <PageContainer>
      <PageHeader
        icon={CategoryIcon}
        title={t('cartridgeTitle')}
        subtitle={t('cartridgeSubtitle')}
        actions={(
          <Button variant="contained" size="small" startIcon={<AddIcon />} onClick={() => setOpen(true)}>
            {t('cartridgeNew')}
          </Button>
        )}
      />
      {loading ? (
        <LoadingSkeleton variant="console" />
      ) : error === 'forbidden' ? (
        <ErrorAlert message={t('cartridgeForbidden')} />
      ) : error ? (
        <ErrorAlert message={error} onRetry={load} />
      ) : (
        <FilteredDataGrid
          embedded
          rows={filtered}
          columns={columns}
          getRowId={(row) => row.id}
          searchValue={searchValue}
          onSearchChange={setSearchValue}
          searchPlaceholder={t('cartridgeSearch')}
          emptyMessage={searchValue ? t('cartridgeNoResults') : t('cartridgeEmpty')}
          emptySubtext={searchValue ? t('cartridgeNoResultsDesc') : t('cartridgeEmptyDesc')}
          pageSize={25}
          height={560}
          onRowClick={(params) => {
            const id = params.row.id;
            setSelectedId((prev) => (prev === id ? null : id));
          }}
          highlightRow={(row) => row.id === selectedId}
        />
      )}
      <SystemDialog
        open={open}
        title={t('cartridgeNewTitle')}
        onClose={() => setOpen(false)}
        onCancel={() => setOpen(false)}
        cancelLabel={tCommon('cancel')}
        actions={(
          <Button variant="contained" disabled={!canSubmit || creating} onClick={onCreate}>
            {t('cartridgeCreate')}
          </Button>
        )}
      >
        <FormField label={t('cartridgeKey')} required helperText={t('cartridgeKeyHint')}>
          <TextField size="small" fullWidth value={key} onChange={(event) => setKey(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeLabel')} required>
          <TextField size="small" fullWidth value={label} onChange={(event) => setLabel(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeLabelAr')}>
          <TextField size="small" fullWidth value={labelAr} onChange={(event) => setLabelAr(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeFieldName')} required>
          <TextField size="small" fullWidth value={fieldName} onChange={(event) => setFieldName(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeFieldLabel')} required>
          <TextField size="small" fullWidth value={fieldLabel} onChange={(event) => setFieldLabel(event.target.value)} />
        </FormField>
        <FormField label={t('cartridgeRequired')} required>
          <SearchSelect
            label={t('cartridgeRequired')}
            value={required}
            onChange={(opt) => setRequired(opt?.value ?? 'yes')}
            options={[
              { value: 'yes', label: t('cartridgeYes') },
              { value: 'no', label: t('cartridgeNo') },
            ]}
          />
        </FormField>
      </SystemDialog>
    </PageContainer>
  );
}
