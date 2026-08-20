// src/shell/LongContent.jsx
// ────────────────────────────────────────────────────────────────────────────
// LONG-CONTENT WRAPPER for assistant replies (Phase 4C, U6).
//
// Long replies collapse by default with an inner vertical scrollbar and a
// "Show more" toggle that expands them fully (browser scroll takes over — no
// nested scrollbars). "Show less" re-collapses. Horizontal scrolling for wide
// tables/code/mermaid blocks is handled per-block inside MarkdownMessage.
//
// Collapse is PURELY VISUAL (max-height/overflow) — the DOM stays intact, so
// rich copy / Ctrl+C selection / export serialize the FULL content regardless
// of collapse state. Nothing here needs special-casing in the serializer.
// ────────────────────────────────────────────────────────────────────────────
import React, { useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Button } from '@mui/material';
import ExpandLessIcon from '@mui/icons-material/ExpandLess';
import ExpandMoreIcon from '@mui/icons-material/ExpandMore';

// Deterministic heuristics — long = likely to blow up the conversation view.
export const LONG_CONTENT_THRESHOLD = 1600;
export const COLLAPSE_MAX_HEIGHT = 320;

export default function LongContent({ content, threshold = LONG_CONTENT_THRESHOLD, children }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = typeof content === 'string' && content.length > threshold;

  if (!isLong) {
    return <>{children}</>;
  }

  return (
    <Box sx={{ position: 'relative' }}>
      <Box
        sx={{
          maxHeight: expanded ? 'none' : COLLAPSE_MAX_HEIGHT,
          overflowY: expanded ? 'visible' : 'auto',
          // W2-B — wide JSON/terminal/table content scrolls horizontally inside
          // its own card (design §2.4) and never widens the viewport.
          overflowX: 'auto',
        }}
      >
        {children}
      </Box>
      <Box sx={{ display: 'flex', justifyContent: 'center', mt: 0.5 }}>
        <Button
          size="small"
          endIcon={expanded ? <ExpandLessIcon sx={{ fontSize: 16 }} /> : <ExpandMoreIcon sx={{ fontSize: 16 }} />}
          onClick={() => setExpanded((value) => !value)}
          sx={{ textTransform: 'none', fontSize: '0.75rem' }}
        >
          {expanded ? 'Show less' : 'Show more'}
        </Button>
      </Box>
    </Box>
  );
}

LongContent.propTypes = {
  content: PropTypes.string,
  threshold: PropTypes.number,
  children: PropTypes.node,
};
