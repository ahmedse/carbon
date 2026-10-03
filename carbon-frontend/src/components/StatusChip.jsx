// src/components/StatusChip.jsx
// Layer-2 primitive: the ONE generic enum -> status chip (design-system RULE 2/5).
//
// Domain-neutral by design: the component carries NO domain words. The caller
// passes the value -> { label, color, variant } map, and the labels are already
// translated (or a <bdi> node) at the call site. Semantic colors come from the
// theme chip overrides, so the same status looks identical everywhere.
//
// This exists because seven near-copy chips (Scope/Tier/Status/Exclusion/
// Completeness/ActionType/Active) and three more in coverageTargetsShared all
// re-implemented the same `map[value] || { label: value }` -> <Chip> shape.
import React from 'react';
import PropTypes from 'prop-types';
import { Chip } from '@mui/material';

function StatusChip({
  value,
  map,
  label,
  color,
  fallbackLabel,
  size = 'small',
  variant = 'filled',
}) {
  const meta = (map && map[value]) || {};
  const resolvedColor = [color, meta.color].find((c) => c && c !== 'default');
  const resolvedLabel = label ?? meta.label ?? (
    fallbackLabel !== undefined ? fallbackLabel : (value ?? '—')
  );
  return (
    <Chip
      size={size}
      label={resolvedLabel}
      color={resolvedColor}
      variant={meta.variant ?? variant}
    />
  );
}

StatusChip.propTypes = {
  /** The raw enum value from the API. */
  value: PropTypes.oneOfType([PropTypes.string, PropTypes.number]),
  /** value -> { label, color, variant }. Labels must already be i18n-resolved. */
  map: PropTypes.objectOf(PropTypes.shape({
    label: PropTypes.node,
    color: PropTypes.string,
    variant: PropTypes.oneOf(['filled', 'outlined']),
  })),
  /** Explicit label override (wins over map[value].label). */
  label: PropTypes.node,
  /** Explicit theme chip color override (wins over map[value].color). */
  color: PropTypes.string,
  /** Shown when the value has no map entry. Defaults to the raw value. */
  fallbackLabel: PropTypes.node,
  size: PropTypes.oneOf(['small', 'medium']),
  variant: PropTypes.oneOf(['filled', 'outlined']),
};

StatusChip.defaultProps = {
  value: null,
  map: null,
  label: undefined,
  color: undefined,
  fallbackLabel: undefined,
  size: 'small',
  variant: 'filled',
};

export default React.memo(StatusChip);
