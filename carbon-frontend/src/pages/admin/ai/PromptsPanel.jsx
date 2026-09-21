// src/pages/admin/ai/PromptsPanel.jsx
// Assets → Prompts: PromptVersion activate / rollback (ADR-0036 Phase 7).
// PEC-7A: governs optimizer rows — live chat uses instance.yaml.
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Chip,
  CircularProgress,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Tooltip,
  Typography,
} from '@mui/material';
import RefreshIcon from '@mui/icons-material/Refresh';
import { useTranslation } from 'react-i18next';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { AI_MANAGE_CONSOLE, AI_PUBLISHER, hasAnyCap } from '../../../capabilities';
import {
  activatePromptVersion,
  listPromptVersions,
  rollbackPromptVersion,
} from '../../../api/aiPromptGovernance';

function capabilityKeys(caps) {
  if (!Array.isArray(caps)) return [];
  return caps
    .map((c) =>
      typeof c === 'string' ? c : c?.key || c?.capability || c?.code || '',
    )
    .filter(Boolean);
}

function GatedButton({ allowed, reason, children, ...props }) {
  const button = (
    <Button {...props} disabled={props.disabled || !allowed}>
      {children}
    </Button>
  );
  if (!allowed) {
    return (
      <Tooltip title={reason || ''}>
        <span>{button}</span>
      </Tooltip>
    );
  }
  return button;
}

export default function PromptsPanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.prompts.title'));
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const canGovern = useMemo(
    () => hasAnyCap(caps, [AI_PUBLISHER, AI_MANAGE_CONSOLE]),
    [caps],
  );

  const [rows, setRows] = useState([]);
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [acting, setActing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listPromptVersions(token);
      setRows(Array.isArray(data?.results) ? data.results : []);
      setNote(data?.note || '');
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onActivate = async (id) => {
    setActing(true);
    try {
      await activatePromptVersion(token, id);
      notify({ message: 'Prompt version activated.', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Activate failed');
    } finally {
      setActing(false);
    }
  };

  const onRollback = async (id) => {
    setActing(true);
    try {
      await rollbackPromptVersion(token, id);
      notify({ message: 'Rolled back to prior prompt version.', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Rollback failed');
    } finally {
      setActing(false);
    }
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h5" fontWeight={700}>
            {t('control.prompts.title')}
          </Typography>
          <Button size="small" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
            Refresh
          </Button>
        </Stack>
        <Alert severity="info">
          {note ||
            'Activate/rollback governs optimizer PromptVersion rows. Live chat uses instance.yaml (PEC-7A).'}
        </Alert>
        {loading ? (
          <CircularProgress size={24} />
        ) : rows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="body2" color="text.secondary">
              No PromptVersion rows for this instance yet.
            </Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('control.prompts.colRound')}</TableCell>
                  <TableCell>{t('control.prompts.colScore')}</TableCell>
                  <TableCell>{t('control.prompts.colActive')}</TableCell>
                  <TableCell>{t('control.prompts.colPreview')}</TableCell>
                  <TableCell>{t('control.prompts.colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.improvement_round ?? '—'}</TableCell>
                    <TableCell>
                      {row.score == null ? '—' : Number(row.score).toFixed(2)}
                    </TableCell>
                    <TableCell>
                      {row.is_active ? (
                        <Chip size="small" color="success" label={t('control.prompts.active')} />
                      ) : (
                        <Chip size="small" variant="outlined" label={t('control.prompts.inactive')} />
                      )}
                    </TableCell>
                    <TableCell sx={{ maxWidth: 320 }}>
                      <Typography
                        variant="body2"
                        sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      >
                        {row.prompt_preview || '—'}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <Stack direction="row" spacing={0.5}>
                        <GatedButton
                          allowed={canGovern}
                          reason="Requires ai:publisher or ai:manage_console"
                          size="small"
                          disabled={acting || row.is_active}
                          onClick={() => onActivate(row.id)}
                        >
                          Activate
                        </GatedButton>
                        <GatedButton
                          allowed={canGovern}
                          reason="Requires ai:publisher or ai:manage_console"
                          size="small"
                          disabled={acting}
                          onClick={() => onRollback(row.id)}
                        >
                          Rollback
                        </GatedButton>
                      </Stack>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Stack>
    </PageContainer>
  );
}
