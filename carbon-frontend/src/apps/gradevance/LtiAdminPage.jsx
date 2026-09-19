// LTI admin — read-only status + config cards (Phase D). No secrets displayed.

import React, { useCallback, useEffect, useState } from 'react';
import {
  Alert, Box, Button, Chip, Paper, Stack, Typography,
} from '@mui/material';
import LinkIcon from '@mui/icons-material/Link';
import ContentCopyIcon from '@mui/icons-material/ContentCopy';
import PageContainer from '../../components/layout/PageContainer';
import PageHeader from '../../components/Page/PageHeader';
import LoadingSkeleton from '../../components/Page/LoadingSkeleton';
import ErrorAlert from '../../components/Page/ErrorAlert';
import EmptyState from '../../components/Page/EmptyState';
import useDocumentTitle from '../../hooks/useDocumentTitle';
import { useAuth } from '../../auth/AuthContext';
import { fetchLtiConfig, fetchLtiStatus } from '../../api/gradevance';
import SkipToMain from './SkipToMain';

const API_PREFIX = '/api/v1/gradevance';

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return true;
  }
  return false;
}

export default function LtiAdminPage() {
  useDocumentTitle('GradeVance · LTI');
  const { token } = useAuth();
  const [status, setStatus] = useState(null);
  const [config, setConfig] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [copied, setCopied] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    setError(null);
    Promise.all([
      fetchLtiStatus(token),
      fetchLtiConfig(token).catch(() => null),
    ])
      .then(([st, cfg]) => {
        setStatus(st);
        setConfig(cfg);
      })
      .catch((err) => setError(err?.message || 'Failed to load LTI admin'))
      .finally(() => setLoading(false));
  }, [token]);

  useEffect(() => {
    load();
  }, [load]);

  const onCopy = async (label, url) => {
    const ok = await copyText(url);
    setCopied(ok ? label : null);
    if (!ok) setError('Clipboard unavailable — copy the URL manually');
  };

  if (loading) {
    return (
      <PageContainer>
        <PageHeader icon={LinkIcon} title="LTI" subtitle="1.3 tool registration (read-only)" />
        <LoadingSkeleton variant="console" />
      </PageContainer>
    );
  }

  if (error && !status) {
    return (
      <PageContainer>
        <PageHeader icon={LinkIcon} title="LTI" />
        <ErrorAlert message={error} onRetry={load} />
      </PageContainer>
    );
  }

  if (!status && !config) {
    return (
      <PageContainer>
        <PageHeader icon={LinkIcon} title="LTI" />
        <EmptyState
          icon={<LinkIcon />}
          title="LTI not configured"
          description="Enable GradeVance LTI settings on the platform to see status and tool URLs."
        />
      </PageContainer>
    );
  }

  const jwksUrl = `${window.location.origin}${API_PREFIX}/lti/jwks/`;
  const toolConfigUrl = `${window.location.origin}${API_PREFIX}/lti/tool-config/`;
  const loginUrl = status?.endpoints?.login
    ? `${window.location.origin}${status.endpoints.login.startsWith('/') ? '' : '/'}${status.endpoints.login}`
    : `${window.location.origin}${API_PREFIX}/lti/oidc/login/`;

  return (
    <PageContainer>
      <SkipToMain targetId="gv-lti-admin" />
      <Box component="main" id="gv-lti-admin" tabIndex={-1} aria-label="LTI administration">
        <PageHeader
          icon={LinkIcon}
          title="LTI"
          subtitle="1.3 OIDC + AGS — read-only registration URLs. Secrets are never shown."
        />

        {error && <ErrorAlert message={error} onRetry={load} />}
        {copied && (
          <Alert severity="success" sx={{ mb: 1.5 }} role="status" onClose={() => setCopied(null)}>
            Copied {copied}
          </Alert>
        )}

        <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="lti-status-h">
          <Stack direction="row" spacing={1} alignItems="center" sx={{ mb: 1 }} flexWrap="wrap" useFlexGap>
            <Typography id="lti-status-h" variant="subtitle1">Status</Typography>
            <Chip
              size="small"
              color={status?.ready ? 'success' : 'default'}
              label={status?.ready ? 'ready' : (status?.status || 'scaffold')}
            />
            {status?.ags?.dry_run != null && (
              <Chip size="small" label={status.ags.dry_run ? 'AGS dry-run' : 'AGS live'} />
            )}
            {config?.enabled != null && (
              <Chip size="small" label={config.enabled ? 'enabled' : 'disabled'} />
            )}
          </Stack>
          <Typography variant="body2" color="text.secondary">
            {status?.note || status?.reason || config?.reason || 'Configure LTI issuer and client on the platform.'}
          </Typography>
        </Paper>

        <Paper variant="outlined" sx={{ p: 1.5, mb: 2 }} component="section" aria-labelledby="lti-flags-h">
          <Typography id="lti-flags-h" variant="subtitle2" sx={{ mb: 1 }}>Config flags (no secrets)</Typography>
          {config ? (
            <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap>
              {[
                ['issuer', config.issuer_set],
                ['client_id', config.client_id_set],
                ['auth_login_url', config.auth_login_url_set],
                ['jwks_url', config.jwks_url_set],
                ['redirect_uri', config.redirect_uri_set],
              ].map(([label, set]) => (
                <Chip
                  key={label}
                  size="small"
                  color={set ? 'success' : 'default'}
                  label={`${label}: ${set ? 'set' : 'missing'}`}
                />
              ))}
              {config.deployment_ids_count != null && (
                <Chip size="small" label={`deployments: ${config.deployment_ids_count}`} />
              )}
            </Stack>
          ) : (
            <Typography variant="body2" color="text.secondary">Config endpoint unavailable.</Typography>
          )}
        </Paper>

        <Paper variant="outlined" sx={{ p: 1.5 }} component="section" aria-labelledby="lti-urls-h">
          <Typography id="lti-urls-h" variant="subtitle2" sx={{ mb: 1 }}>Registration URLs</Typography>
          <Stack spacing={1.25}>
            {[
              { label: 'JWKS', url: jwksUrl },
              { label: 'Tool config', url: toolConfigUrl },
              { label: 'OIDC login', url: loginUrl },
            ].map((row) => (
              <Stack
                key={row.label}
                direction={{ xs: 'column', sm: 'row' }}
                spacing={1}
                alignItems={{ xs: 'stretch', sm: 'center' }}
              >
                <Typography variant="body2" sx={{ minWidth: 100 }}>{row.label}</Typography>
                <Typography variant="caption" color="text.secondary" sx={{ flex: 1, wordBreak: 'break-all' }}>
                  {row.url}
                </Typography>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<ContentCopyIcon />}
                  onClick={() => onCopy(row.label, row.url)}
                  aria-label={`Copy ${row.label} URL`}
                >
                  Copy
                </Button>
              </Stack>
            ))}
          </Stack>
        </Paper>
      </Box>
    </PageContainer>
  );
}
