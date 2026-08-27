// src/notes/NoteComposer.jsx
// Small textarea + submit (and optional cancel) for notes/comments.
// Visibility is IMPLICIT (derived from the author's scope server-side) — no picker.

import React, { useState } from 'react';
import { Box, TextField, Button, CircularProgress } from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import { useTranslation } from 'react-i18next';

/**
 * @param {object} props
 * @param {string} [props.placeholder]
 * @param {string} [props.submitLabel]
 * @param {function(string): Promise<any>} props.onSubmit  (body)
 * @param {function(): void} [props.onCancel]
 * @param {string} [props.initial]
 */
export function NoteComposer({
  placeholder,
  submitLabel,
  onSubmit,
  onCancel,
  initial = '',
}) {
  const { t } = useTranslation('notes');
  const [body, setBody] = useState(initial);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const trimmed = body.trim();

  const handleSubmit = async () => {
    if (!trimmed || busy) return;
    setBusy(true);
    setError(null);
    try {
      await onSubmit?.(trimmed);
      setBody('');
    } catch (err) {
      setError(err?.message || t('composer.error'));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Box>
      <TextField
        multiline
        minRows={1}
        maxRows={4}
        fullWidth
        size="small"
        value={body}
        onChange={(e) => setBody(e.target.value)}
        placeholder={placeholder || t('composer.placeholder')}
        sx={{
          '& .MuiInputBase-root': { fontSize: '0.7rem' },
        }}
        onKeyDown={(e) => {
          if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            handleSubmit();
          }
        }}
      />
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}>
        <Box sx={{ flex: 1 }} />
        {onCancel && (
          <Button size="small" onClick={onCancel} sx={{ fontSize: '0.66rem' }}>
            {t('composer.cancel')}
          </Button>
        )}
        <Button
          size="small"
          variant="contained"
          disabled={!trimmed || busy}
          onClick={handleSubmit}
          startIcon={busy ? <CircularProgress size={11} /> : <SendIcon sx={{ fontSize: 13 }} />}
          sx={{ fontSize: '0.66rem', textTransform: 'none' }}
        >
          {submitLabel || t('composer.submit')}
        </Button>
      </Box>
      {error && (
        <Box component="div" sx={{ color: 'error.main', fontSize: '0.68rem', mt: 0.25 }}>
          {error}
        </Box>
      )}
    </Box>
  );
}
