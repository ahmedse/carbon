// src/components/inbound/InboundExampleTemplates.jsx
// Button + dialog that lists the shipped docs/migration/examples/*.template.csv
// files and downloads one. Real files only; downloads never write a template.

import React, { useCallback, useState } from 'react';
import { Box, Button, CircularProgress, Stack, Typography } from '@mui/material';
import DownloadIcon from '@mui/icons-material/Download';
import DescriptionOutlinedIcon from '@mui/icons-material/DescriptionOutlined';
import { useTranslation } from 'react-i18next';
import SystemDialog from '../SystemDialog';
import { useNotification } from '../NotificationProvider';
import { downloadInboundTemplateExample, fetchInboundTemplateExamples } from '../../api/inbound';

export default function InboundExampleTemplates({
  token,
  ns = 'people',
  size = 'small',
  variant = 'outlined',
}) {
  const { t } = useTranslation(ns);
  const { t: tCommon } = useTranslation('common');
  const { notifyFromError } = useNotification();

  const [open, setOpen] = useState(false);
  const [examples, setExamples] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [busySlug, setBusySlug] = useState(null);

  const load = useCallback(async () => {
    if (!token) return;
    setLoading(true);
    setError(null);
    try {
      const data = await fetchInboundTemplateExamples(token);
      setExamples(Array.isArray(data) ? data : data?.results || []);
    } catch (err) {
      setError(err?.message || t('importExamplesFailed'));
    } finally {
      setLoading(false);
    }
  }, [token, t]);

  const onOpen = () => {
    setOpen(true);
    load();
  };

  const onDownload = async (example) => {
    setBusySlug(example.slug);
    try {
      const blob = await downloadInboundTemplateExample(token, example.slug);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = example.filename;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      notifyFromError(err, t('importExamplesFailed'));
    } finally {
      setBusySlug(null);
    }
  };

  return (
    <>
      <Button size={size} variant={variant} startIcon={<DescriptionOutlinedIcon />} onClick={onOpen}>
        {t('importExamples')}
      </Button>
      <SystemDialog
        open={open}
        title={t('importExamplesTitle')}
        onClose={() => setOpen(false)}
        onCancel={() => setOpen(false)}
        cancelLabel={tCommon('close', { defaultValue: 'Close' })}
      >
        <Stack spacing={1.5}>
          <Typography variant="body2" color="text.secondary">{t('importExamplesHint')}</Typography>
          {loading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 3 }}>
              <CircularProgress size={22} />
            </Box>
          ) : error ? (
            <Stack spacing={1}>
              <Typography variant="body2" color="error">{error}</Typography>
              <Box>
                <Button size="small" onClick={load}>{tCommon('retry', { defaultValue: 'Retry' })}</Button>
              </Box>
            </Stack>
          ) : examples.length === 0 ? (
            <Typography variant="body2" color="text.secondary">{t('importExamplesEmpty')}</Typography>
          ) : (
            examples.map((example) => (
              <Stack
                key={example.slug}
                direction="row"
                spacing={1}
                alignItems="center"
                justifyContent="space-between"
              >
                <Box sx={{ minWidth: 0 }}>
                  <Typography variant="body2">{example.name}</Typography>
                  <Typography variant="caption" color="text.secondary" noWrap>
                    {example.filename} · {t('importExamplesColumns', { count: example.columns.length })}
                  </Typography>
                </Box>
                <Button
                  size="small"
                  variant="outlined"
                  startIcon={<DownloadIcon />}
                  disabled={busySlug === example.slug}
                  onClick={() => onDownload(example)}
                >
                  {t('importDownloadExample')}
                </Button>
              </Stack>
            ))
          )}
        </Stack>
      </SystemDialog>
    </>
  );
}
