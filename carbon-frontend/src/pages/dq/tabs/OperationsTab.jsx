// carbon-frontend/src/pages/dq/tabs/OperationsTab.jsx
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import {
  Alert,
  Box,
  Button,
  Chip,
  Paper,
  Stack,
  Typography,
} from '@mui/material';
import {
  Archive,
  ContentCopy,
  DeleteForever,
  PowerSettingsNew,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import ConfirmDialog from '../../../components/ConfirmDialog';
import { updateDQRule, deleteDQRule, createDQRule } from '../../../api/dq';

function OperationsTab({ rule, onChanged }) {
  const { token } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const navigate = useNavigate();
  const { t } = useTranslation('dq');
  const [busy, setBusy] = useState('');
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [confirmArchive, setConfirmArchive] = useState(false);

  const hasResults = Number(rule?.results_count) > 0;
  // In-scope copies for <Trans> children interpolation ({{name}}/{{count}}
  // shorthand compiles to object-literal references).
  const name = rule?.name;
  const count = rule?.results_count;

  const handleToggleActive = async () => {
    setBusy('toggle');
    try {
      await updateDQRule(token, rule.id, { is_active: !rule.is_active });
      notify({ message: rule.is_active ? t('operations.deactivated') : t('operations.activated'), type: 'success' });
      onChanged?.();
    } catch (err) {
      notifyFromError(err, t('operations.updateError'));
    } finally {
      setBusy('');
    }
  };

  const handleDuplicate = async () => {
    setBusy('duplicate');
    try {
      const newRule = await createDQRule(token, {
        definition: { ...(rule.definition || {}), name: `${rule.name} (copy)` },
        field_assignments_write: (rule.field_assignments || []).map((a) => ({
          data_table: a.data_table,
          data_field: a.data_field,
        })),
        tag_ids: (rule.tags || []).map((tag) => tag.id),
      });
      notify({ message: t('operations.duplicated', { name: newRule.name }), type: 'success' });
      navigate(`/dq/rules/${newRule.id}`, { replace: true });
      onChanged?.();
    } catch (err) {
      notifyFromError(err, t('operations.duplicateError'));
    } finally {
      setBusy('');
    }
  };

  const handleArchive = async () => {
    setBusy('archive');
    try {
      const result = await deleteDQRule(token, rule.id);
      if (result && result.archived) {
        notify({
          message: t('operations.archivedWithResults', {
            name: rule.name,
            count: result.results_count || 0,
          }),
          type: 'info',
        });
      } else {
        notify({ message: t('rules.deleted', { name: rule.name }), type: 'success' });
      }
      setConfirmArchive(false);
      navigate('/dq', { replace: true });
    } catch (err) {
      notifyFromError(err, t('operations.archiveError'));
    } finally {
      setBusy('');
    }
  };

  const handleDelete = async () => {
    setBusy('delete');
    try {
      const result = await deleteDQRule(token, rule.id);
      if (result && result.archived) {
        notify({
          message: t('operations.archivedWithResults', {
            name: rule.name,
            count: result.results_count || 0,
          }),
          type: 'info',
        });
      } else {
        notify({ message: t('rules.deleted', { name: rule.name }), type: 'success' });
      }
      setConfirmDelete(false);
      navigate('/dq', { replace: true });
    } catch (err) {
      notifyFromError(err, t('operations.deleteError'));
    } finally {
      setBusy('');
    }
  };

  return (
    <Box sx={{ p: 3 }}>
      {rule?.archived ? (
        <Alert severity="warning" sx={{ mb: 2 }}>
          {t('operations.archivedWarning')}
        </Alert>
      ) : null}

      <Stack spacing={1.5}>
        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('operations.state')}</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
            <Button
              variant="outlined"
              size="small"
              startIcon={<PowerSettingsNew />}
              disabled={busy === 'toggle' || rule?.archived}
              onClick={handleToggleActive}
            >
              {rule?.is_active ? t('operations.deactivate') : t('operations.activate')}
            </Button>
            <Chip
              size="small"
              color={rule?.is_active ? 'success' : 'default'}
              label={rule?.is_active ? t('status.active') : t('status.inactive')}
            />
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('operations.versioning')}</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap">
            <Button
              variant="outlined"
              size="small"
              startIcon={<ContentCopy />}
              disabled={busy === 'duplicate'}
              onClick={handleDuplicate}
            >
              {t('operations.duplicateRule')}
            </Button>
            <Typography sx={{ color: 'text.secondary', alignSelf: 'center' }}>
              {t('operations.currentVersion', { version: rule?.version ?? 1 })}
            </Typography>
          </Stack>
        </Paper>

        <Paper variant="outlined" sx={{ p: 2, borderRadius: 2 }}>
          <Typography sx={{ fontSize: '0.8125rem', fontWeight: 700, mb: 1 }}>{t('operations.delete')}</Typography>
          <Stack direction="row" spacing={1} flexWrap="wrap" alignItems="center">
            {hasResults ? (
              <>
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<Archive />}
                  disabled={busy === 'archive'}
                  onClick={() => setConfirmArchive(true)}
                >
                  {t('operations.archiveRule')}
                </Button>
                <Typography sx={{ color: 'text.secondary' }}>
                  {t('operations.resultsExist', { count: rule?.results_count })}
                </Typography>
              </>
            ) : (
              <>
                <Button
                  variant="outlined"
                  color="error"
                  size="small"
                  startIcon={<DeleteForever />}
                  disabled={busy === 'delete'}
                  onClick={() => setConfirmDelete(true)}
                >
                  {t('operations.deleteRule')}
                </Button>
                <Typography sx={{ color: 'text.secondary' }}>
                  {t('operations.noResultsExist')}
                </Typography>
              </>
            )}
          </Stack>
        </Paper>
      </Stack>

      <ConfirmDialog
        open={confirmDelete}
        title={t('operations.deleteTitle')}
        message={
          <Trans i18nKey="operations.deleteMessage" ns="dq" values={{ name }}>
            This permanently removes <strong>{{name}}</strong>. This cannot be undone.
          </Trans>
        }
        confirmLabel={t('operations.deletePermanently')}
        destructive
        onConfirm={handleDelete}
        onCancel={() => setConfirmDelete(false)}
      />

      <ConfirmDialog
        open={confirmArchive}
        title={t('operations.archiveTitle')}
        message={
          <Trans i18nKey="operations.archiveMessage" ns="dq" values={{ name, count }}>
            Archives <strong>{{name}}</strong> — it keeps its {{count}} result(s) but is deactivated
            and hidden from the active rules list. You can unarchive later.
          </Trans>
        }
        confirmLabel={t('operations.archiveConfirm')}
        destructive
        onConfirm={handleArchive}
        onCancel={() => setConfirmArchive(false)}
      />
    </Box>
  );
}

OperationsTab.propTypes = {
  rule: PropTypes.object,
  onChanged: PropTypes.func,
  onRun: PropTypes.func,
};

export default OperationsTab;
