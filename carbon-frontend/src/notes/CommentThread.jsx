// src/notes/CommentThread.jsx
// Flat 1-level thread for a note: composer on top, chronological comments below.
// Uses the per-note cache from NotesContext (fetched lazily on expand).

import React from 'react';
import { Box, Typography, Avatar, IconButton, Tooltip } from '@mui/material';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTranslation } from 'react-i18next';
import { ReactionBar } from './ReactionBar';
import { NoteComposer } from './NoteComposer';
import { authorInitials, authorDisplayName, formatNoteTime, formatNoteTimeIso } from './notesUtils';

export function CommentThread({
  comments,
  onAddComment,
  onToggleReaction,
  onRemoveComment,
}) {
  const { t } = useTranslation('notes');

  const visible = (comments || []).filter((c) => !c.is_removed);
  const removed = (comments || []).filter((c) => c.is_removed);

  return (
    <Box>
      {/* Composer on top — newest input, chronological thread below */}
      <NoteComposer
        placeholder={t('comments.addPlaceholder')}
        submitLabel={t('comments.add')}
        onSubmit={async (body) => {
          await onAddComment?.(body);
          return true;
        }}
      />

      {visible.length === 0 && removed.length === 0 && (
        <Typography variant="caption" sx={{ display: 'block', color: 'text.secondary', my: 0.25 }}>
          {t('comments.empty')}
        </Typography>
      )}

      {visible.map((comment) => (
        <Box
          key={comment.id}
          sx={{
            display: 'flex',
            gap: 0.5,
            py: 0.5,
            borderTop: '1px solid',
            borderColor: 'divider',
          }}
        >
          <Avatar sx={{ width: 14, height: 14, fontSize: '0.42rem', bgcolor: 'secondary.main' }}>
            {authorInitials(comment.author)}
          </Avatar>
          <Box sx={{ flex: 1, minWidth: 0 }}>
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.3 }}>
              <Typography variant="caption" sx={{ fontWeight: 600, fontSize: '0.58rem' }}>
                {authorDisplayName(comment.author)}
              </Typography>
              <Typography
                variant="caption"
                sx={{ color: 'text.disabled', fontSize: '0.5rem' }}
                title={formatNoteTimeIso(comment.created_at)}
              >
                {formatNoteTime(comment.created_at)}
              </Typography>
              <Box sx={{ flex: 1 }} />
              {comment.can_edit && (
                <Tooltip title={t('comments.delete')}>
                  <IconButton
                    size="small"
                    onClick={async () => {
                      if (window.confirm(t('comments.deleteConfirm'))) await onRemoveComment?.(comment.id);
                    }}
                    sx={{ p: 0.02 }}
                  >
                    <DeleteOutlineIcon sx={{ fontSize: 10 }} />
                  </IconButton>
                </Tooltip>
              )}
            </Box>
            <Typography variant="body2" sx={{ fontSize: '0.62rem', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>
              {comment.body}
            </Typography>
            <Box sx={{ mt: 0.1 }}>
              <ReactionBar
                reaction_counts={comment.reaction_counts}
                my_reaction={comment.my_reaction}
                onToggle={(r) => onToggleReaction?.(comment.id, r)}
              />
            </Box>
          </Box>
        </Box>
      ))}

      {removed.length > 0 && (
        <Typography variant="caption" sx={{ display: 'block', color: 'text.disabled', py: 0.25, fontStyle: 'italic' }}>
          {removed.length} {t('comments.removed')}
        </Typography>
      )}
    </Box>
  );
}
