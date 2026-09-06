// src/apps/team/TeamInbox.jsx
// Team (manager approvals inbox) — Approvals Inbox page (route /team).
// Lists actionable correspondence (items awaiting the current approver) in a
// compact table. Rows navigate to /team/:id. The backend now emits human-readable
// `requester_name` / `corr_type_code` / `corr_type_label` alongside the raw PKs;
// the local helpers below stay as defensive fallbacks only.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Box,
  Card,
  CardContent,
  Chip,
  CircularProgress,
  Skeleton,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography,
} from '@mui/material';
import InboxIcon from '@mui/icons-material/Inbox';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchInbox } from '../../api/team';
import { SectionTitle, InlineError } from '../my/components/myRequestsCommon';
import {
  STATUS_COLOR,
  STATUS_SUFFIX,
  codeLabel,
  formatDateTime,
} from '../my/components/myRequestsLabels';
import { FONT } from '../../theme/themeTokens';

// Governed correspondence codes (mirrors backend/seed_correspondence.py).
const CORR_TYPE_SUFFIX = {
  leave_request: 'leaveRequest',
  loan_request: 'loanRequest',
  profile_change: 'profileChange',
  internal_memo: 'internalMemo',
  circular: 'circular',
  decision: 'decision',
};

/** corr_type may be a serialized object ({id, code, label}) or a plain PK. */
function corrTypeLabel(t, corrType) {
  if (corrType == null) return '—';
  if (typeof corrType === 'object') {
    const code = corrType.code || corrType.name || corrType.label;
    return code ? codeLabel(t, 'corrType', CORR_TYPE_SUFFIX, code) : String(corrType.id ?? '');
  }
  return codeLabel(t, 'corrType', CORR_TYPE_SUFFIX, corrType);
}

/** requester may be a serialized object ({id, name/username}) or a plain PK. */
function requesterLabel(requester) {
  if (requester == null) return '—';
  if (typeof requester === 'object') {
    return (
      requester.name ||
      requester.full_name ||
      requester.username ||
      requester.label ||
      String(requester.id ?? '')
    );
  }
  return String(requester);
}

export default function TeamInbox() {
  const { t, i18n } = useTranslation('team');
  const { token } = useAuth();
  const navigate = useNavigate();
  useDocumentTitle(t('inboxTitle'));

  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchInbox(token);
      setItems(Array.isArray(result?.items) ? result.items : []);
    } catch (err) {
      setError(err?.message || t('error'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  useEffect(() => {
    load();
  }, [load]);

  const handleOpen = useCallback((id) => navigate(`/team/${id}`), [navigate]);

  const handleKeyDown = (event, id) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleOpen(id);
    }
  };

  const showInitialSkeleton = loading && items.length === 0;

  return (
    <Box
      component="main"
      sx={{ width: '100%', flex: 1, minHeight: 0, display: 'flex', flexDirection: 'column' }}
    >
      <PageContainer>
        <PageHeader icon={InboxIcon} title={t('inboxTitle')} subtitle={t('inboxSubtitle')} />
        <Card variant="outlined">
          <CardContent sx={{ p: 1.5, '&:last-child': { pb: 1.5 } }}>
            <Stack direction="row" alignItems="center" spacing={1} sx={{ mb: 1 }}>
              <SectionTitle icon={InboxIcon} title={t('inboxTitle')} />
              {loading && <CircularProgress size={12} aria-label={t('loading')} />}
            </Stack>
            {showInitialSkeleton ? (
              <Stack spacing={0.5} aria-label={t('loading')}>
                <Skeleton />
                <Skeleton width="70%" />
                <Skeleton width="85%" />
              </Stack>
            ) : error ? (
              <InlineError message={error} onRetry={load} />
            ) : items.length === 0 ? (
              <Typography sx={{ ...FONT.body2, color: 'text.secondary' }}>
                {t('inboxEmpty')}
              </Typography>
            ) : (
              <TableContainer>
                <Table size="small" aria-busy={loading}>
                  <TableHead>
                    <TableRow>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableReferenceNo')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableTitle')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableRequester')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableType')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableStatus')}
                      </TableCell>
                      <TableCell sx={{ ...FONT.body, fontWeight: 600 }}>
                        {t('tableDate')}
                      </TableCell>
                    </TableRow>
                  </TableHead>
                  <TableBody>
                    {items.map((row) => (
                      <TableRow
                        key={row.id}
                        hover
                        onClick={() => handleOpen(row.id)}
                        onKeyDown={(event) => handleKeyDown(event, row.id)}
                        role="button"
                        tabIndex={0}
                        aria-label={t('openItem', { ref: row.reference_no || row.id })}
                        sx={{ cursor: 'pointer', opacity: loading ? 0.6 : 1 }}
                      >
                        <TableCell sx={{ ...FONT.body2 }}>
                          {row.reference_no || '—'}
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>{row.title || '—'}</TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {row.requester_name || requesterLabel(row.requester)}
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {row.corr_type_label || row.corr_type_code || corrTypeLabel(t, row.corr_type)}
                        </TableCell>
                        <TableCell>
                          <Chip
                            size="small"
                            variant="outlined"
                            color={STATUS_COLOR[row.status] || 'default'}
                            label={codeLabel(t, 'status', STATUS_SUFFIX, row.status)}
                          />
                        </TableCell>
                        <TableCell sx={{ ...FONT.body2 }}>
                          {formatDateTime(row.created_at, i18n.language)}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </TableContainer>
            )}
          </CardContent>
        </Card>
      </PageContainer>
    </Box>
  );
}
