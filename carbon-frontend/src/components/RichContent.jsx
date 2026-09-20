// src/components/RichContent.jsx
// Platform rich-text surface — ONE formatter for Chat, Agent (Plan/Run/Canvas/
// Output), and domain apps. Wraps MarkdownMessage (GFM tables, code, mermaid,
// math, figures). Prefer this import outside the shell so apps do not reach
// into shell/ for presentation.
import React from 'react';
import PropTypes from 'prop-types';
import { Box } from '@mui/material';
import MarkdownMessage from '../shell/MarkdownMessage';

/**
 * @param {object} props
 * @param {string} props.content — markdown source
 * @param {string} [props.testId]
 * @param {'plain'|'message'} [props.variant='plain']
 *   message = Chat assistant bubble chrome (same content engine as Chat)
 * @param {object} [props.sx] — Box sx
 */
export default function RichContent({ content, testId = 'rich-content', variant = 'plain', sx }) {
  if (content == null || content === '') return null;
  const messageSx = variant === 'message'
    ? {
      alignSelf: 'flex-start',
      width: '100%',
      minWidth: 0,
      px: 0.25,
      py: 0.25,
      '& .MuiTypography-root': { fontSize: '0.8125rem' },
    }
    : {};
  return (
    <Box data-testid={testId} sx={{ minWidth: 0, ...messageSx, ...sx }}>
      <MarkdownMessage content={String(content)} />
    </Box>
  );
}

RichContent.propTypes = {
  content: PropTypes.string,
  testId: PropTypes.string,
  variant: PropTypes.oneOf(['plain', 'message']),
  sx: PropTypes.object,
};
