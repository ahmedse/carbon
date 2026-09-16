// src/components/Form/SearchSelect.jsx
// Layer-2 primitive: the ONE searchable dropdown for the platform.
//
// WHY THIS EXISTS (design-system RULE 13):
//   Enterprise pickers MUST be searchable autocompletes — not raw <Select> with
//   a wall of <MenuItem>s. A governed enum or entity list can be dozens–hundreds
//   of entries; a non-searchable dropdown is unusable at that scale and gives
//   no loading/error/empty signal (the exact bug that left the Payroll Run
//   "Org Unit" dropdown empty).
//
// ENTERPRISE CONTRACT (always provided, zero setup):
//   - type-to-filter search (MUI Autocomplete, case-insensitive, partial)
//   - 4 data states: loading (spinner) / error (+ Retry) / empty (guidance) /
//     loaded (RULE 4) — never a blank listbox
//   - clearable, keyboard-navigable, auto-highlight
//   - groupBy, multiple, label/helper/required passthrough, i18n-ready
//
// USAGE:
//   // sync (already-fetched) options:
//   <SearchSelect options={orgUnits} valueKey="id" labelKey="name"
//                 value={form.org_unit} onChange={(v) => setForm(f => ({...f, org_unit: v?.id ?? ''}))} />
//   // async options via useReferenceOptions / any fetch:
//   <SearchSelect options={nationality.options} loading={nationality.loading}
//                 error={nationality.error} onRetry={nationality.refetch}
//                 value={form.nationality} onChange={...} />
//
// Options may be objects ({value,label} or {id,name}) or primitives. The raw
// option object (not just its key) is emitted from onChange — callers keep the
// full object for display, or read the key they care about.

import React, { useMemo } from 'react';
import PropTypes from 'prop-types';
import { Autocomplete, Box, Button, TextField, Typography } from '@mui/material';

function toOptionObject(opt, valueKey, labelKey) {
  if (opt === null || opt === undefined) return null;
  if (typeof opt !== 'object') return { [valueKey]: opt, [labelKey]: String(opt) };
  return opt;
}

/**
 * SearchSelect — searchable, state-aware dropdown (single or multiple).
 */
function SearchSelect({
  options = [],
  value,
  onChange,
  valueKey = 'value',
  labelKey = 'label',
  getOptionLabel,
  isOptionEqualToValue,
  groupBy,
  multiple = false,
  label,
  placeholder,
  helperText,
  error,
  onRetry,
  loading = false,
  required = false,
  disabled = false,
  size = 'small',
  fullWidth = true,
  clearable = true,
  limitTags,
  renderOption,
  noOptionsText,
  loadingText,
  autoHighlight = true,
  ...rest
}) {
  const normalized = useMemo(
    () => (options || []).map((o) => toOptionObject(o, valueKey, labelKey)),
    [options, valueKey, labelKey],
  );

  const optionValue = (o) => (o && o[valueKey] !== undefined ? o[valueKey] : o);
  const defaultLabel = (o) => (o && o[labelKey] !== undefined ? o[labelKey] : String(o));

  const resolveValue = useMemo(() => {
    if (multiple) {
      if (!Array.isArray(value) || value.length === 0) return [];
      return value
        .map((v) => normalized.find((o) => optionValue(o) === v) || null)
        .filter(Boolean);
    }
    if (value === null || value === undefined || value === '') return null;
    return normalized.find((o) => optionValue(o) === value) || null;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value, multiple, normalized]);

  const emptySlot = useMemo(() => {
    if (loading) {
      return loadingText || null;
    }
    if (error) {
      return (
        <Box sx={{ p: 1.5, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1 }}>
          <Typography variant="body2" color="error.main">
            {typeof error === 'string' ? error : 'Failed to load options'}
          </Typography>
          {onRetry && (
            <Button size="small" variant="outlined" onClick={onRetry}>
              Retry
            </Button>
          )}
        </Box>
      );
    }
    return noOptionsText || null;
  }, [loading, error, onRetry, noOptionsText, loadingText]);

  return (
    <Autocomplete
      multiple={multiple}
      options={normalized}
      value={resolveValue}
      onChange={(e, v) => onChange(v)}
      getOptionLabel={getOptionLabel || defaultLabel}
      isOptionEqualToValue={
        isOptionEqualToValue || ((a, b) => optionValue(a) === optionValue(b))
      }
      groupBy={groupBy}
      loading={loading}
      disabled={disabled}
      disableClearable={!clearable}
      autoHighlight={autoHighlight}
      size={size}
      fullWidth={fullWidth}
      limitTags={limitTags}
      filterSelectedOptions={multiple}
      renderOption={renderOption}
      noOptionsText={emptySlot}
      renderInput={(params) => (
        <TextField
          {...params}
          label={label}
          placeholder={placeholder}
          helperText={helperText}
          error={Boolean(error)}
          required={required}
        />
      )}
      {...rest}
    />
  );
}

SearchSelect.propTypes = {
  options: PropTypes.array,
  value: PropTypes.any,
  onChange: PropTypes.func.isRequired,
  valueKey: PropTypes.string,
  labelKey: PropTypes.string,
  getOptionLabel: PropTypes.func,
  isOptionEqualToValue: PropTypes.func,
  groupBy: PropTypes.func,
  multiple: PropTypes.bool,
  label: PropTypes.string,
  placeholder: PropTypes.string,
  helperText: PropTypes.string,
  error: PropTypes.oneOfType([PropTypes.string, PropTypes.bool]),
  onRetry: PropTypes.func,
  loading: PropTypes.bool,
  required: PropTypes.bool,
  disabled: PropTypes.bool,
  size: PropTypes.oneOf(['small', 'medium']),
  fullWidth: PropTypes.bool,
  clearable: PropTypes.bool,
  limitTags: PropTypes.number,
  renderOption: PropTypes.func,
  noOptionsText: PropTypes.node,
  loadingText: PropTypes.node,
  autoHighlight: PropTypes.bool,
};

export default React.memo(SearchSelect);
