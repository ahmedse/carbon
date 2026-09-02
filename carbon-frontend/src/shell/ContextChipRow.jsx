// src/shell/ContextChipRow.jsx
// Persistent "Context" chips row (F2-F): renders the resolved mention objects
// pinned on the composer as chips (`#kind name`), each with a remove-✕, plus a
// "Clear" button to drop them all. Session-scoped — the mentions themselves
// live in AIInputBar state and ride as workspace_context.mentions on send.
import PropTypes from 'prop-types';
import { Box, Button, Chip, Typography } from '@mui/material';

function ContextChipRow({ mentions, onRemove, onClear }) {
  if (!mentions || mentions.length === 0) return null;

  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        gap: 0.5,
        flexWrap: 'wrap',
        px: 1.5,
        pt: 0.75,
      }}
    >
      <Typography variant="caption" color="text.secondary" sx={{ fontSize: '0.625rem' }}>
        Context
      </Typography>
      {mentions.map((m) => (
        <Chip
          key={`${m.kind}-${m.id}`}
          size="small"
          variant="outlined"
          label={`#${m.kind} ${m.name}`}
          onDelete={() => onRemove(m.kind, m.id)}
          aria-label={`Remove context ${m.kind} ${m.name}`}
        />
      ))}
      <Button
        size="small"
        onClick={onClear}
        aria-label="Clear all context"
        sx={{ fontSize: '0.625rem', minHeight: 20, p: 0.5 }}
      >
        Clear
      </Button>
    </Box>
  );
}

ContextChipRow.propTypes = {
  mentions: PropTypes.arrayOf(
    PropTypes.shape({
      kind: PropTypes.string.isRequired,
      id: PropTypes.string.isRequired,
      name: PropTypes.string.isRequired,
    }),
  ).isRequired,
  onRemove: PropTypes.func.isRequired,
  onClear: PropTypes.func.isRequired,
};

export default ContextChipRow;
