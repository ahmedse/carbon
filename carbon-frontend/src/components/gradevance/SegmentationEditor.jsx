// Visual HITL resegment — continuous essay painter (colored spans).
// Click a word → select segment. Click the ▸ after a word → split there.
// Merge / retag stages in the toolbar. Emits word-span ExpertEdit payloads.

import React, { useMemo, useState } from 'react';
import {
  Alert, Box, Button, Chip, FormControl, InputLabel, MenuItem,
  Select, Stack, TextField, Tooltip, Typography,
} from '@mui/material';

const STAGES = ['what', 'so_what', 'now_what'];

const SPAN_BG = {
  what: 'rgba(100, 116, 139, 0.18)',
  so_what: 'rgba(14, 165, 233, 0.22)',
  now_what: 'rgba(16, 185, 129, 0.22)',
};
const SPAN_BG_SEL = {
  what: 'rgba(100, 116, 139, 0.38)',
  so_what: 'rgba(14, 165, 233, 0.42)',
  now_what: 'rgba(16, 185, 129, 0.42)',
};

function tokenize(text) {
  return (text || '').match(/\S+/g) || [];
}

function wordsToText(words, start, end) {
  return words.slice(start, end).join(' ');
}

export function buildSegDraft(segments = [], fullText = '') {
  const sorted = [...segments].sort(
    (a, b) => (a.start_word ?? a.ordinal ?? 0) - (b.start_word ?? b.ordinal ?? 0),
  );
  let words = tokenize(fullText);
  if (!words.length && sorted.length) {
    const parts = [];
    for (const s of sorted) parts.push(...tokenize(s.text || ''));
    words = parts;
  }
  // If no segments yet but we have text, one covering segment
  if (!sorted.length && words.length) {
    return {
      words,
      draft: [{
        key: 'draft-0',
        ordinal: 0,
        start_word: 0,
        end_word: words.length,
        stage_guess: 'what',
        text: wordsToText(words, 0, words.length),
      }],
    };
  }
  const draft = sorted.map((s, i) => {
    let start = Number.isFinite(s.start_word) ? s.start_word : null;
    let end = Number.isFinite(s.end_word) ? s.end_word : null;
    if (start == null || end == null || end <= start) {
      const prior = sorted.slice(0, i).reduce((n, x) => n + tokenize(x.text || '').length, 0);
      const len = tokenize(s.text || '').length || 1;
      start = prior;
      end = prior + len;
    }
    start = Math.max(0, Math.min(start, words.length));
    end = Math.max(start + 1, Math.min(end, words.length));
    return {
      key: s.id || `draft-${i}`,
      ordinal: i,
      start_word: start,
      end_word: end,
      stage_guess: s.stage_guess || 'what',
      text: wordsToText(words, start, end) || (s.text || ''),
    };
  });
  return { words, draft };
}

function emitPayload(draft, words) {
  return draft.map(({ ordinal, start_word, end_word, stage_guess }, i) => ({
    ordinal: i,
    start_word,
    end_word,
    stage_guess,
    text: wordsToText(words, start_word, end_word),
  }));
}

/** Heuristic split suggestions for Pulse / assist (read-only). */
export function suggestSplitPoints(words, draft, max = 5) {
  const markers = ['however', 'therefore', 'later', 'thus', 'so', 'because', 'for', 'example', 'next', 'now'];
  const suggestions = [];
  for (const seg of draft) {
    for (let wi = seg.start_word + 1; wi < seg.end_word; wi++) {
      const w = (words[wi] || '').toLowerCase().replace(/[^\w]/g, '');
      const prev = (words[wi - 1] || '').toLowerCase();
      if (markers.includes(w) || markers.includes(prev) || /[.!?]$/.test(words[wi - 1] || '')) {
        suggestions.push({
          after_word: wi,
          segment_ordinal: seg.ordinal,
          cue: words[wi - 1],
          preview: words.slice(Math.max(seg.start_word, wi - 3), Math.min(seg.end_word, wi + 3)).join(' '),
        });
        if (suggestions.length >= max) return suggestions;
      }
    }
  }
  return suggestions;
}

export default function SegmentationEditor({
  segments = [],
  fullText = '',
  rationale,
  onRationaleChange,
  onChange,
  suggestedSplits = null,
  onRequestSuggestions = null,
}) {
  const initial = useMemo(() => buildSegDraft(segments, fullText), [segments, fullText]);
  const [words] = useState(initial.words);
  const [draft, setDraft] = useState(initial.draft);
  const [selected, setSelected] = useState(0);

  const wordOwner = useMemo(() => {
    const map = new Array(words.length).fill(-1);
    draft.forEach((s, i) => {
      for (let w = s.start_word; w < s.end_word; w++) map[w] = i;
    });
    return map;
  }, [draft, words.length]);

  const commit = (next, selectIdx = selected) => {
    const normalized = next.map((s, i) => ({
      ...s,
      ordinal: i,
      key: s.key || `draft-${i}`,
      text: wordsToText(words, s.start_word, s.end_word),
    }));
    setDraft(normalized);
    setSelected(Math.max(0, Math.min(selectIdx, normalized.length - 1)));
    onChange?.(emitPayload(normalized, words));
  };

  const sel = draft[selected] || null;

  const setStage = (stage) => {
    if (!sel) return;
    commit(draft.map((s, i) => (i === selected ? { ...s, stage_guess: stage } : s)));
  };

  const mergeWithNext = () => {
    if (selected >= draft.length - 1) return;
    const a = draft[selected];
    const b = draft[selected + 1];
    const merged = { ...a, end_word: b.end_word, stage_guess: a.stage_guess };
    commit([...draft.slice(0, selected), merged, ...draft.slice(selected + 2)], selected);
  };

  const mergeWithPrev = () => {
    if (selected <= 0) return;
    const a = draft[selected - 1];
    const b = draft[selected];
    const merged = { ...a, end_word: b.end_word, stage_guess: a.stage_guess };
    commit([...draft.slice(0, selected - 1), merged, ...draft.slice(selected + 1)], selected - 1);
  };

  const splitAfterGlobalWord = (afterWord) => {
    // afterWord = global index of first word of the RIGHT piece
    const owner = wordOwner[afterWord - 1];
    if (owner < 0 || afterWord <= 0 || afterWord >= words.length) return;
    const seg = draft[owner];
    if (!seg || afterWord <= seg.start_word || afterWord >= seg.end_word) return;
    const left = { ...seg, key: `${seg.key}-a`, end_word: afterWord };
    const right = {
      ...seg,
      key: `${seg.key}-b`,
      start_word: afterWord,
      end_word: seg.end_word,
      stage_guess: seg.stage_guess,
    };
    commit([...draft.slice(0, owner), left, right, ...draft.slice(owner + 1)], owner);
  };

  const applySuggestion = (afterWord) => {
    splitAfterGlobalWord(afterWord);
  };

  if (!words.length) {
    return <Alert severity="warning">No essay text — cannot paint segments.</Alert>;
  }

  return (
    <Stack spacing={1.5} data-testid="segmentation-editor">
      <Alert severity="info" sx={{ py: 0.5 }}>
        Continuous essay: colored spans = segments. Click a word to select.
        Click the ▸ after a word to split there. Merge / retag in the toolbar.
      </Alert>

      <Stack direction="row" spacing={0.75} flexWrap="wrap" useFlexGap aria-label="Segment chips">
        {draft.map((s, i) => (
          <Chip
            key={s.key}
            size="small"
            color={i === selected ? 'primary' : 'default'}
            variant={i === selected ? 'filled' : 'outlined'}
            label={`#${i} ${s.stage_guess} · w${s.start_word}–${s.end_word}`}
            onClick={() => setSelected(i)}
            data-testid={`seg-chip-${i}`}
          />
        ))}
      </Stack>

      {/* Continuous painter */}
      <Box
        component="article"
        aria-label="Essay segmentation painter"
        data-testid="essay-painter"
        sx={{
          p: 1.5,
          border: 1,
          borderColor: 'divider',
          borderRadius: 1,
          lineHeight: 1.85,
          fontSize: '0.9rem',
          maxHeight: 280,
          overflow: 'auto',
          bgcolor: 'background.paper',
        }}
      >
        {words.map((w, wi) => {
          const oi = wordOwner[wi];
          const seg = oi >= 0 ? draft[oi] : null;
          const stage = seg?.stage_guess || 'what';
          const isSel = oi === selected;
          const isBoundaryEnd = seg && wi === seg.end_word - 1 && oi < draft.length;
          return (
            <Box component="span" key={`w-${wi}`} sx={{ display: 'inline' }}>
              <Box
                component="span"
                role="button"
                tabIndex={0}
                data-testid={`painter-word-${wi}`}
                data-seg={oi}
                onClick={() => oi >= 0 && setSelected(oi)}
                onKeyDown={(e) => {
                  if ((e.key === 'Enter' || e.key === ' ') && oi >= 0) {
                    e.preventDefault();
                    setSelected(oi);
                  }
                }}
                title={seg ? `Segment #${oi} · ${stage} · word ${wi}` : `word ${wi}`}
                sx={{
                  display: 'inline',
                  px: 0.2,
                  py: 0.15,
                  borderRadius: 0.5,
                  cursor: 'pointer',
                  bgcolor: isSel ? SPAN_BG_SEL[stage] : SPAN_BG[stage],
                  outline: isSel && wi === seg.start_word ? '1px solid' : 'none',
                  outlineColor: 'primary.main',
                  '&:hover': { filter: 'brightness(0.95)' },
                }}
              >
                {w}
              </Box>
              {' '}
              {/* Split handle after this word (except last word of essay) */}
              {wi < words.length - 1 && (
                <Tooltip title="Split after this word" enterDelay={400}>
                  <Box
                    component="button"
                    type="button"
                    data-testid={`split-after-${wi}`}
                    aria-label={`Split after word ${wi}`}
                    onClick={(e) => {
                      e.stopPropagation();
                      splitAfterGlobalWord(wi + 1);
                    }}
                    sx={{
                      display: 'inline',
                      border: 'none',
                      background: 'transparent',
                      color: 'text.disabled',
                      cursor: 'pointer',
                      px: 0.1,
                      fontSize: '0.7rem',
                      lineHeight: 1,
                      verticalAlign: 'middle',
                      opacity: isBoundaryEnd ? 0.35 : 0.55,
                      '&:hover': { color: 'primary.main', opacity: 1 },
                    }}
                  >
                    ▸
                  </Box>
                </Tooltip>
              )}
            </Box>
          );
        })}
      </Box>

      {sel && (
        <Stack direction={{ xs: 'column', sm: 'row' }} spacing={1} alignItems="center" flexWrap="wrap" useFlexGap>
          <FormControl size="small" sx={{ minWidth: 140 }}>
            <InputLabel id="seg-stage-label">Stage</InputLabel>
            <Select
              labelId="seg-stage-label"
              label="Stage"
              value={sel.stage_guess}
              onChange={(e) => setStage(e.target.value)}
              data-testid="seg-stage-select"
            >
              {STAGES.map((st) => (
                <MenuItem key={st} value={st}>{st}</MenuItem>
              ))}
            </Select>
          </FormControl>
          <Button size="small" variant="outlined" onClick={mergeWithPrev} disabled={selected <= 0} data-testid="merge-prev">
            Merge ← prev
          </Button>
          <Button size="small" variant="outlined" onClick={mergeWithNext} disabled={selected >= draft.length - 1} data-testid="merge-next">
            Merge next →
          </Button>
          {onRequestSuggestions && (
            <Button size="small" variant="text" onClick={onRequestSuggestions} data-testid="suggest-splits">
              Suggest splits (Pulse)
            </Button>
          )}
        </Stack>
      )}

      {Array.isArray(suggestedSplits) && suggestedSplits.length > 0 && (
        <Stack spacing={0.5} data-testid="suggested-splits">
          <Typography variant="caption" color="text.secondary">Pulse suggestions (draft only — click Apply)</Typography>
          {suggestedSplits.map((s) => (
            <Stack key={`sug-${s.after_word}`} direction="row" spacing={1} alignItems="center">
              <Typography variant="caption" sx={{ flex: 1 }}>
                After w{s.after_word - 1}: …{s.preview}…
              </Typography>
              <Button size="small" onClick={() => applySuggestion(s.after_word)}>Apply</Button>
            </Stack>
          ))}
        </Stack>
      )}

      <TextField
        size="small"
        label="Rationale"
        value={rationale}
        onChange={(e) => onRationaleChange?.(e.target.value)}
        multiline
        minRows={2}
        fullWidth
        required
        inputProps={{ 'data-testid': 'seg-rationale' }}
        helperText="Required — why these boundaries / stages are correct (append-only ExpertEdit)"
      />
    </Stack>
  );
}
