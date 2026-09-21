// src/pages/admin/ai/KnowledgeBasePanel.jsx
// Assets → Knowledge: KnowledgeItem CRUD + revoke (ADR-0036 Phase 7).
import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Button,
  Chip,
  CircularProgress,
  Dialog,
  DialogActions,
  DialogContent,
  DialogTitle,
  FormControl,
  InputLabel,
  MenuItem,
  Paper,
  Select,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  TextField,
  Tooltip,
  Typography,
} from '@mui/material';
import AddIcon from '@mui/icons-material/Add';
import RefreshIcon from '@mui/icons-material/Refresh';
import useDocumentTitle from '../../../hooks/useDocumentTitle';
import { useTranslation } from 'react-i18next';
import PageContainer from '../../../components/layout/PageContainer';
import { useAuth } from '../../../auth/AuthContext';
import { useNotification } from '../../../components/NotificationProvider';
import { AI_MANAGE_CONSOLE, AI_PUBLISHER, hasAnyCap } from '../../../capabilities';
import {
  createKnowledgeItem,
  listKnowledgeItems,
  revokeKnowledgeItem,
} from '../../../api/aiKnowledge';

const CLASSES = [
  'policy',
  'process_definition',
  'business_fact',
  'procedural_heuristic',
  'episodic_observation',
  'user_preference',
];

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

export default function KnowledgeBasePanel() {
  const { t } = useTranslation('ai');
  useDocumentTitle(t('control.knowledgeBase.title'));
  const { token, userCapabilities } = useAuth();
  const { notify, notifyFromError } = useNotification();
  const caps = useMemo(() => capabilityKeys(userCapabilities), [userCapabilities]);
  const canWrite = useMemo(
    () => hasAnyCap(caps, [AI_PUBLISHER, AI_MANAGE_CONSOLE]),
    [caps],
  );

  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [form, setForm] = useState({
    knowledge_class: 'business_fact',
    content: '',
    source: 'steward',
  });

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listKnowledgeItems(token);
      setRows(Array.isArray(data?.results) ? data.results : []);
    } catch {
      setRows([]);
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onCreate = async () => {
    try {
      await createKnowledgeItem(token, form);
      notify({ message: 'Knowledge item created.', type: 'success' });
      setOpen(false);
      setForm({ knowledge_class: 'business_fact', content: '', source: 'steward' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Create failed');
    }
  };

  const onRevoke = async (id) => {
    try {
      await revokeKnowledgeItem(token, id, 'steward revoke from Assets');
      notify({ message: 'Knowledge item revoked.', type: 'success' });
      await load();
    } catch (err) {
      notifyFromError(err, 'Revoke failed');
    }
  };

  return (
    <PageContainer>
      <Stack spacing={2}>
        <Stack direction="row" justifyContent="space-between" alignItems="center">
          <Typography variant="h5" fontWeight={700}>
            {t('control.knowledgeBase.heading')}
          </Typography>
          <Stack direction="row" spacing={1}>
            <GatedButton
              allowed={canWrite}
              reason="Requires ai:publisher or ai:manage_console"
              size="small"
              variant="contained"
              startIcon={<AddIcon />}
              onClick={() => setOpen(true)}
            >
              New item
            </GatedButton>
            <Button size="small" startIcon={<RefreshIcon />} onClick={load} disabled={loading}>
              {t('control.knowledgeBase.refresh')}
            </Button>
          </Stack>
        </Stack>
        <Typography variant="body2" color="text.secondary">
          {t('control.knowledgeBase.subtitle')}
        </Typography>
        {loading ? (
          <CircularProgress size={24} />
        ) : rows.length === 0 ? (
          <Paper variant="outlined" sx={{ p: 3 }}>
            <Typography variant="body2" color="text.secondary">
              {t('control.knowledgeBase.empty')}
            </Typography>
          </Paper>
        ) : (
          <TableContainer component={Paper} variant="outlined">
            <Table size="small">
              <TableHead>
                <TableRow>
                  <TableCell>{t('control.knowledgeBase.colClass')}</TableCell>
                  <TableCell>{t('control.knowledgeBase.colStatus')}</TableCell>
                  <TableCell>{t('control.knowledgeBase.colSource')}</TableCell>
                  <TableCell>{t('control.knowledgeBase.colContent')}</TableCell>
                  <TableCell>{t('control.knowledgeBase.colActions')}</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {rows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>
                      <Chip size="small" label={row.knowledge_class} />
                    </TableCell>
                    <TableCell>{row.review_status}</TableCell>
                    <TableCell>{row.source}</TableCell>
                    <TableCell sx={{ maxWidth: 360 }}>
                      <Typography
                        variant="body2"
                        sx={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}
                      >
                        {row.content}
                      </Typography>
                    </TableCell>
                    <TableCell>
                      <GatedButton
                        allowed={canWrite}
                        reason="Requires ai:publisher or ai:manage_console"
                        size="small"
                        color="warning"
                        disabled={row.review_status === 'deprecated'}
                        onClick={() => onRevoke(row.id)}
                      >
                        {t('control.knowledgeBase.revoke')}
                      </GatedButton>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        )}
      </Stack>

      <Dialog open={open} onClose={() => setOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle>{t('control.knowledgeBase.newItem')}</DialogTitle>
        <DialogContent>
          <Stack spacing={2} sx={{ mt: 1 }}>
            <FormControl size="small" fullWidth>
              <InputLabel id="kclass">{t('control.knowledgeBase.class')}</InputLabel>
              <Select
                labelId="kclass"
                label={t('control.knowledgeBase.class')}
                value={form.knowledge_class}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, knowledge_class: e.target.value }))
                }
              >
                {CLASSES.map((c) => (
                  <MenuItem key={c} value={c}>
                    {c}
                  </MenuItem>
                ))}
              </Select>
            </FormControl>
            <TextField
              size="small"
              label={t('control.knowledgeBase.source')}
              value={form.source}
              onChange={(e) => setForm((prev) => ({ ...prev, source: e.target.value }))}
              fullWidth
            />
            <TextField
              label={t('control.knowledgeBase.content')}
              value={form.content}
              onChange={(e) => setForm((prev) => ({ ...prev, content: e.target.value }))}
              fullWidth
              multiline
              minRows={4}
            />
          </Stack>
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setOpen(false)}>{t('control.knowledgeBase.cancel')}</Button>
          <Button
            variant="contained"
            onClick={onCreate}
            disabled={!form.content.trim()}
          >
            {t('control.knowledgeBase.create')}
          </Button>
        </DialogActions>
      </Dialog>
    </PageContainer>
  );
}
