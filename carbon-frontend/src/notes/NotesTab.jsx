// src/notes/NotesTab.jsx
// The fixed first tab: entity context header + composer + note list
// (newest first, page 1) + "Show N older" accordion.

import React, { useState } from 'react';
import {
  Box, Typography, Chip, Accordion, AccordionSummary, AccordionDetails,
  CircularProgress, Button, Skeleton,
} from '@mui/material';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';
import { useTranslation } from 'react-i18next';
import { useNotes } from './NotesContext';
import { NoteComposer } from './NoteComposer';
import { NoteCard } from './NoteCard';
import { notesListKey } from './notesUtils';

const EXPANDED_CAP = 5; // first N notes shown expanded; the rest in the accordion

export function NotesTab() {
  const { t } = useTranslation('notes');
  const {
    contexts,
    lists,
    comments,
    fetchComments,
    loadMore,
    addNote,
    addComment,
    toggleReaction,
    toggleCommentReaction,
    removeNote,
    removeComment,
    editNote,
  } = useNotes();

  const key = notesListKey(contexts);
  const list = lists[key] || { notes: [], loading: true, error: null, page: 0, hasMore: false };
  const { notes, loading, error, hasMore } = list;

  const expanded = notes.slice(0, EXPANDED_CAP);
  const older = notes.slice(EXPANDED_CAP);
  const [accordionOpen, setAccordionOpen] = useState(false);
  const anchors = contexts.length
    ? contexts
    : [{ entityType: null, entityId: null }]; // global placeholder

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      {/* Context header — one chip per anchor (domain app, reporting year, …) */}
      <Box sx={{ px: 0.75, pt: 0.25, pb: 0.25 }}>
        <Typography variant="caption" sx={{ color: 'text.secondary', fontSize: '0.56rem', textTransform: 'uppercase', letterSpacing: '0.04em' }}>
          {t('tab.contextLabel')}
        </Typography>
        <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 0.25, mt: 0.15 }}>
          {anchors.map((c) => (
            <Chip
              key={`${c.entityType ?? 'global'}:${c.entityId ?? 0}`}
              size="small"
              label={c.entityType ? c.label || `${c.entityType} #${c.entityId}` : t('tab.global')}
              color={c.entityType ? 'primary' : 'default'}
              variant={c.entityType ? 'filled' : 'outlined'}
              sx={{ fontSize: '0.58rem', height: 18, maxWidth: '100%' }}
            />
          ))}
        </Box>
      </Box>

      {/* Composer — only when an entity context is active (notes are entity-anchored).
          On the global "All notes" view there is nothing to attach to, so we disable
          the composer with a hint instead of letting the user hit a server/context error. */}
      <Box sx={{ px: 0.75, pb: 0.4, borderBottom: '1px solid', borderColor: 'divider' }}>
        {contexts.length ? (
          <NoteComposer
            onSubmit={async (body) => {
              await addNote({ body });
              return true;
            }}
          />
        ) : (
          <Typography
            variant="caption"
            sx={{
              display: 'flex',
              alignItems: 'center',
              gap: 0.5,
              color: 'text.disabled',
              fontSize: '0.62rem',
              py: 0.4,
            }}
          >
            {t('tab.noContext')}
          </Typography>
        )}
      </Box>

      {/* List */}
      <Box sx={{ flex: 1, overflowY: 'auto', px: 0.75, py: 0.25 }} role="list">
        {loading && notes.length === 0 ? (
          <Box sx={{ display: 'flex', flexDirection: 'column', gap: 0.4 }}>
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} variant="rounded" height={48} />
            ))}
          </Box>
        ) : error && notes.length === 0 ? (
          <Typography variant="caption" sx={{ color: 'error.main', display: 'block', p: 0.75 }}>
            {error}
          </Typography>
        ) : notes.length === 0 ? (
          <Typography variant="caption" sx={{ color: 'text.secondary', display: 'block', p: 0.75 }}>
            {t('tab.empty')}
          </Typography>
        ) : (
          <>
            {expanded.map((note) => (
              <Box key={note.id} sx={{ mb: 0.4 }} role="listitem">
                <NoteCard
                  note={note}
                  comments={comments[note.id]?.comments}
                  commentsLoading={comments[note.id]?.loading}
                  commentsError={comments[note.id]?.error}
                  onToggleComments={fetchComments}
                  onToggleReaction={toggleReaction}
                  onAddComment={addComment}
                  onToggleCommentReaction={toggleCommentReaction}
                  onRemoveComment={removeComment}
                  onEditNote={editNote}
                  onRemoveNote={removeNote}
                />
              </Box>
            ))}

            {/* Older notes accordion */}
            {older.length > 0 && (
              <Accordion
                expanded={accordionOpen}
                onChange={() => setAccordionOpen((v) => !v)}
                sx={{
                  border: '1px solid',
                  borderColor: 'divider',
                  borderRadius: 1,
                  '&::before': { display: 'none' },
                  boxShadow: 'none',
                  bgcolor: 'transparent',
                }}
              >
                <AccordionSummary expandIcon={<ExpandMoreIcon sx={{ fontSize: 14 }} />} sx={{ minHeight: 24, '& .MuiAccordionSummary-content': { my: 0.2 } }}>
                  <Typography variant="caption" sx={{ fontSize: '0.62rem', color: 'text.secondary' }}>
                    {t('tab.older', { count: older.length })}
                  </Typography>
                </AccordionSummary>
                <AccordionDetails sx={{ p: 0 }}>
                  {older.map((note) => (
                    <Box key={note.id} sx={{ mb: 0.4 }} role="listitem">
                      <NoteCard
                        note={note}
                        comments={comments[note.id]?.comments}
                        commentsLoading={comments[note.id]?.loading}
                        commentsError={comments[note.id]?.error}
                        onToggleComments={fetchComments}
                        onToggleReaction={toggleReaction}
                        onAddComment={addComment}
                        onToggleCommentReaction={toggleCommentReaction}
                        onRemoveComment={removeComment}
                        onEditNote={editNote}
                        onRemoveNote={removeNote}
                      />
                    </Box>
                  ))}
                </AccordionDetails>
              </Accordion>
            )}

            {/* Load more */}
            {hasMore && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.35 }}>
                <Button size="small" onClick={loadMore} sx={{ fontSize: '0.6rem', textTransform: 'none' }}>
                  {t('tab.loadMore')}
                </Button>
              </Box>
            )}
            {list.loading && notes.length > 0 && (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 0.5 }}>
                <CircularProgress size={14} />
              </Box>
            )}
          </>
        )}
      </Box>
    </Box>
  );
}
