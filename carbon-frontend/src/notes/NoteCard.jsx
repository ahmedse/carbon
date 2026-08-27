// src/notes/NoteCard.jsx
// A single note: author avatar + name + time, body, reaction bar,
// comment toggle (lazy thread), edit/delete for author or admins.

import React, { useState } from 'react';
import {
  Box, Typography, Avatar, IconButton, Tooltip, Collapse,
  CircularProgress, Menu, MenuItem, ListItemIcon,
} from '@mui/material';
import ChatBubbleOutlineIcon from '@mui/icons-material/ChatBubbleOutline';
import MoreVertIcon from '@mui/icons-material/MoreVert';
import EditOutlinedIcon from '@mui/icons-material/EditOutlined';
import DeleteOutlineIcon from '@mui/icons-material/DeleteOutline';
import { useTranslation } from 'react-i18next';
import { ReactionBar } from './ReactionBar';
import { CommentThread } from './CommentThread';
import { NoteComposer } from './NoteComposer';
import { authorInitials, authorDisplayName, formatNoteTime, formatNoteTimeIso } from './notesUtils';

export function NoteCard({
  note,
  comments,
  commentsLoading,
  commentsError,
  onToggleComments,
  onToggleReaction,
  onAddComment,
  onToggleCommentReaction,
  onRemoveComment,
  onEditNote,
  onRemoveNote,
}) {
  const { t } = useTranslation('notes');
  const [commentsOpen, setCommentsOpen] = useState(false);
  const [menuAnchor, setMenuAnchor] = useState(null);
  const [editing, setEditing] = useState(false);

  const canEdit = note.can_edit === true;

  const handleCommentsToggle = () => {
    const next = !commentsOpen;
    setCommentsOpen(next);
    if (next) onToggleComments?.(note.id);
  };

  return (
    <Box
      sx={{
        border: '1px solid',
        borderColor: 'divider',
        borderRadius: 1,
        bgcolor: 'background.paper',
        p: 0.5,
        '&:hover': { borderColor: 'action.active' },
      }}
    >
      {/* Header: avatar + author + time + menu */}
      <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.35 }}>
        <Avatar
          sx={{ width: 16, height: 16, fontSize: '0.48rem', bgcolor: 'primary.main' }}
        >
          {authorInitials(note.author)}
        </Avatar>
        <Box sx={{ flex: 1, minWidth: 0 }}>
          <Typography variant="caption" sx={{ fontWeight: 600, color: 'text.primary', display: 'block', lineHeight: 1.2, fontSize: '0.62rem' }}>
            {authorDisplayName(note.author)}
          </Typography>
          <Typography
            variant="caption"
            sx={{ color: 'text.secondary', fontSize: '0.52rem', lineHeight: 1.2 }}
            title={formatNoteTimeIso(note.created_at)}
          >
            {formatNoteTime(note.created_at)}
            {note.visibility === 'internal' ? ` · ${t('card.internal')}` : ''}
          </Typography>
        </Box>
        {canEdit && (
          <>
            <Tooltip title={t('card.actions')}>
              <IconButton size="small" onClick={(e) => setMenuAnchor(e.currentTarget)} sx={{ p: 0.1 }}>
                <MoreVertIcon sx={{ fontSize: 12 }} />
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={menuAnchor}
              open={Boolean(menuAnchor)}
              onClose={() => setMenuAnchor(null)}
            >
              <MenuItem
                onClick={() => { setMenuAnchor(null); setEditing(true); }}
              >
                <ListItemIcon><EditOutlinedIcon sx={{ fontSize: 16 }} /></ListItemIcon>
                {t('card.edit')}
              </MenuItem>
              <MenuItem
                onClick={async () => {
                  setMenuAnchor(null);
                  if (window.confirm(t('card.deleteConfirm'))) await onRemoveNote?.(note.id);
                }}
              >
                <ListItemIcon><DeleteOutlineIcon sx={{ fontSize: 16 }} /></ListItemIcon>
                {t('card.delete')}
              </MenuItem>
            </Menu>
          </>
        )}
      </Box>

      {/* Body or editor */}
      {editing ? (
        <Box sx={{ mt: 1 }}>
          <NoteComposer
            initial={note.body}
            submitLabel={t('composer.save')}
            onCancel={() => setEditing(false)}
            onSubmit={async (body) => {
              await onEditNote?.(note.id, body);
              setEditing(false);
            }}
          />
        </Box>
      ) : (
        <Typography
          variant="body2"
          sx={{
            mt: 0.35,
            whiteSpace: 'pre-wrap',
            wordBreak: 'break-word',
            color: 'text.primary',
            fontSize: '0.68rem',
          }}
        >
          {note.body}
        </Typography>
      )}

      {/* Footer: reactions + comments toggle */}
      <Box
        sx={{
          mt: 0.35,
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: 0.35,
        }}
      >
        <ReactionBar
          reaction_counts={note.reaction_counts}
          my_reaction={note.my_reaction}
          onToggle={(r) => onToggleReaction?.(note.id, r)}
        />
        <Tooltip title={t('card.comments')}>
          <Box
            component="button"
            type="button"
            onClick={handleCommentsToggle}
            aria-expanded={commentsOpen}
            aria-label={t('card.comments')}
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 0.4,
              border: 'none',
              bgcolor: 'transparent',
              cursor: 'pointer',
              color: commentsOpen ? 'primary.main' : 'text.secondary',
              fontSize: '0.66rem',
              '&:hover': { color: 'primary.main' },
              '&:focus-visible': { outline: '2px solid', outlineColor: 'primary.main' },
              p: 0.25,
              borderRadius: 1,
            }}
          >
            <ChatBubbleOutlineIcon sx={{ fontSize: 11 }} />
            <span>{note.comments_count ?? 0}</span>
          </Box>
        </Tooltip>
      </Box>

      {/* Lazy comment thread */}
      <Collapse in={commentsOpen} timeout="auto" unmountOnExit>
        <Box sx={{ mt: 0.75, pt: 0.75, borderTop: '1px dashed', borderColor: 'divider' }}>
          {commentsLoading ? (
            <Box sx={{ display: 'flex', justifyContent: 'center', py: 1 }}>
              <CircularProgress size={16} />
            </Box>
          ) : commentsError ? (
            <Typography variant="caption" sx={{ color: 'error.main' }}>
              {commentsError}
            </Typography>
          ) : (
            <CommentThread
              comments={comments || []}
              onAddComment={(body) => onAddComment?.(note.id, body)}
              onToggleReaction={(commentId, r) => onToggleCommentReaction?.(note.id, commentId, r)}
              onRemoveComment={(commentId) => onRemoveComment?.(note.id, commentId)}
            />
          )}
        </Box>
      </Collapse>
    </Box>
  );
}
