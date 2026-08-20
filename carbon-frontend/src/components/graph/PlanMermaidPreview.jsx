// src/components/graph/PlanMermaidPreview.jsx
// W3-F — static Mermaid `graph` preview of a plan DAG for the review card.
// Reuses the lazy-mermaid pattern from MarkdownMessage (mermaid is already a
// dependency; the heavy lib stays out of the main bundle). Theme tokens only
// (RULE_8); outcome labels only (RULE_23).
import React, { useEffect, useMemo, useRef, useState } from 'react';
import PropTypes from 'prop-types';
import { Box, Chip, Typography } from '@mui/material';
import { planDagMermaid } from '../../utils/planGraph';

const idRef = { current: 0 };

/**
 * Static Mermaid diagram preview of a plan DAG.
 * @param {object} props
 * @param {object} props.plan - plan payload
 * @param {number} [props.maxHeight] - scrollable content height
 * @param {string} [props.testId] - data-testid
 */
export default function PlanMermaidPreview({ plan, maxHeight = 340, testId = 'plan-mermaid-preview' }) {
  const [svg, setSvg] = useState('');
  const [error, setError] = useState('');
  const code = useMemo(() => planDagMermaid(plan), [plan]);

  useEffect(() => {
    let cancelled = false;
    setSvg('');
    setError('');
    (async () => {
      try {
        const mermaid = (await import('mermaid')).default;
        mermaid.initialize({
          startOnLoad: false,
          securityLevel: 'loose',
          theme: 'default',
          fontFamily: 'inherit',
        });
        idRef.current += 1;
        const id = `plan-mmd-${idRef.current}-${Date.now()}`;
        const { svg: rendered } = await mermaid.render(id, code);
        if (!cancelled) setSvg(rendered);
      } catch (err) {
        if (!cancelled) {
          setError(err?.message ? String(err.message) : 'Diagram render failed');
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <Box sx={{ borderRadius: 1, border: 1, borderColor: 'warning.main', overflow: 'hidden' }}>
        <Chip
          size="small"
          color="warning"
          variant="outlined"
          label="Diagram could not be rendered"
          sx={{ m: 0.75 }}
        />
      </Box>
    );
  }

  if (!svg) {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block', py: 1, fontSize: '0.6875rem' }}>
        Rendering diagram…
      </Typography>
    );
  }

  return (
    <Box
      data-testid={testId}
      sx={{
        overflowX: 'auto',
        overflowY: 'auto',
        bgcolor: 'background.paper',
        borderRadius: 1,
        border: 1,
        borderColor: 'divider',
        p: 1.5,
        maxHeight,
        '& svg': { maxWidth: '100%', height: 'auto' },
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

PlanMermaidPreview.propTypes = {
  plan: PropTypes.object,
  maxHeight: PropTypes.number,
  testId: PropTypes.string,
};
