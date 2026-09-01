// src/shell/SuggestionDiff.jsx
// Wave D3 — AI output transparency: a legible "will be created" consent summary
// for a DQ rule suggestion (RULE_21 — consent is legible). Renders the
// structured definition fields the user is consenting to, not just the
// rationale. Reuses the shared DQ label maps (no new hardcoded label tables),
// theme tokens only (RULE_8), and a text label always accompanies the severity
// chip (status never color-only).
import PropTypes from 'prop-types';
import { Box, Chip, Stack, Typography } from '@mui/material';
import {
  RULE_TYPE_LABELS,
  RULE_LEVEL_LABELS,
  SEVERITY_LABELS,
  SEVERITY_COLORS,
  DIMENSION_LABELS,
} from '../pages/dq/constants';

function labelOrRaw(map, key) {
  if (key == null || key === '') return null;
  return map[key] || key;
}

// A binding may carry table/data_table and field/data_field (legacy aliases).
function formatBinding(binding) {
  if (!binding || typeof binding !== 'object') return null;
  const table = binding.table || binding.data_table;
  const field = binding.field || binding.data_field;
  if (table && field) return `${table}.${field}`;
  return table || field || null;
}

function Row({ label, children }) {
  return (
    <Box sx={{ display: 'flex', gap: 1, alignItems: 'baseline' }}>
      <Typography
        variant="caption"
        sx={{ flexShrink: 0, minWidth: 64, fontWeight: 600, color: 'text.secondary' }}
      >
        {label}
      </Typography>
      <Box sx={{ minWidth: 0 }}>{children}</Box>
    </Box>
  );
}

Row.propTypes = {
  label: PropTypes.string.isRequired,
  children: PropTypes.node,
};

function SuggestionDiff({ suggestion }) {
  const definition = suggestion?.definition;

  // Defensive: no structured definition → render the rationale only.
  if (!definition || typeof definition !== 'object') {
    return (
      <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
        {suggestion?.rationale || 'AI-generated suggestion'}
      </Typography>
    );
  }

  const name = definition.name || suggestion?.name;
  const typeLabel = labelOrRaw(RULE_TYPE_LABELS, definition.type);
  const levelLabel = labelOrRaw(RULE_LEVEL_LABELS, definition.level);
  const severityLabel = labelOrRaw(SEVERITY_LABELS, suggestion?.severity);
  const dimensionLabel = labelOrRaw(DIMENSION_LABELS, suggestion?.dimension);

  const bindings = Array.isArray(definition.bindings) ? definition.bindings : [];
  const bindingLabels = bindings.map(formatBinding).filter(Boolean);

  const params =
    definition.params && typeof definition.params === 'object'
      ? Object.entries(definition.params)
      : [];

  return (
    <Stack spacing={0.5} sx={{ mt: 0.5 }}>
      {name != null && name !== '' && (
        <Row label="Name">
          <Typography variant="body2">{name}</Typography>
        </Row>
      )}
      {typeLabel && (
        <Row label="Type">
          <Typography variant="caption">{typeLabel}</Typography>
        </Row>
      )}
      {levelLabel && (
        <Row label="Level">
          <Typography variant="caption">{levelLabel}</Typography>
        </Row>
      )}
      {severityLabel && (
        <Row label="Severity">
          <Chip
            size="small"
            variant="outlined"
            color={SEVERITY_COLORS[suggestion?.severity] || 'default'}
            label={severityLabel}
          />
        </Row>
      )}
      {dimensionLabel && (
        <Row label="Dimension">
          <Typography variant="caption">{dimensionLabel}</Typography>
        </Row>
      )}
      <Row label="Fields">
        <Typography variant="caption">{bindingLabels.length ? bindingLabels.join(', ') : '—'}</Typography>
      </Row>
      {params.length > 0 && (
        <Row label="Params">
          <Stack spacing={0.25}>
            {params.map(([key, value]) => (
              <Typography key={key} variant="caption" sx={{ display: 'block' }}>
                {key}: {String(value)}
              </Typography>
            ))}
          </Stack>
        </Row>
      )}
      {suggestion?.rationale && (
        <Typography variant="caption" color="text.secondary" sx={{ display: 'block' }}>
          {suggestion.rationale}
        </Typography>
      )}
    </Stack>
  );
}

SuggestionDiff.propTypes = {
  suggestion: PropTypes.shape({
    definition: PropTypes.object,
    rationale: PropTypes.string,
    severity: PropTypes.string,
    confidence: PropTypes.number,
    dimension: PropTypes.string,
  }),
};

export default SuggestionDiff;
