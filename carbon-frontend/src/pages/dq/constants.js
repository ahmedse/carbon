// carbon-frontend/src/pages/dq/constants.js
// Shared display maps for the DQ Workspace + Rule Detail pages.
// Mirrors backend enums (backend/dq/models.py, rule_schema.py) — keep in sync.

export const RULE_TYPE_LABELS = {
  not_null: 'Not Null',
  unique: 'Unique',
  allowed_values: 'Allowed Values',
  range: 'Range',
  regex: 'Regex',
  reference_integrity: 'Reference Integrity',
  threshold: 'Threshold',
  nl_check: 'AI NL Check',
  anomaly_detect: 'Anomaly Detection',
};

export const RULE_LEVEL_LABELS = {
  field_validation: 'Field Validation',
  business_rule: 'Business Rule',
};

export const DIMENSION_LABELS = {
  completeness: 'Completeness',
  validity: 'Validity',
  accuracy: 'Accuracy',
  consistency: 'Consistency',
  timeliness: 'Timeliness',
  uniqueness: 'Uniqueness',
  integrity: 'Integrity',
  reasonability: 'Reasonability',
};

export const SEVERITY_LABELS = {
  info: 'Info',
  warn: 'Warning',
  error: 'Error',
};

export const JOB_TYPE_LABELS = {
  rule_run: 'Rule Run',
  profile: 'Profiling',
  freshness: 'Freshness',
  schema: 'Schema Snapshot',
  nl_check: 'AI NL Check',
  suggest: 'AI Suggestion',
  anomaly: 'Anomaly Scan',
};

export const JOB_STATUS_LABELS = {
  queued: 'Queued',
  running: 'Running',
  done: 'Done',
  failed: 'Failed',
  canceled: 'Canceled',
};

// MUI theme-chip color tokens (no raw hex).
export const SEVERITY_COLORS = {
  info: 'info',
  warn: 'warning',
  error: 'error',
};

export const JOB_STATUS_COLORS = {
  queued: 'default',
  running: 'primary',
  done: 'success',
  failed: 'error',
  canceled: 'default',
};

export const RESULT_STATUS_COLORS = {
  passed: 'success',
  failed: 'error',
  skipped_unavailable: 'warning',
};

export const SCHEMA_CHANGE_COLORS = {
  added: 'success',
  removed: 'error',
  modified: 'warning',
};

// ── Field type ↔ rule type applicability ─────────────────────────────────────
// Mirrors backend/dq/rule_schema.py RULE_FIELD_TYPE_COMPAT and
// backend/dataschema/models.py DataField.FIELD_TYPES — keep in sync.
export const FIELD_TYPE_LABELS = {
  string: 'String',
  text: 'Text',
  number: 'Number',
  date: 'Date',
  boolean: 'Boolean',
  select: 'Select',
  multiselect: 'Multi Select',
  file: 'File',
  reference: 'Reference',
};

// rule_type → array of compatible field types. null/undefined = any type.
export const RULE_FIELD_TYPE_COMPAT = {
  not_null: null,
  unique: null,
  allowed_values: ['string', 'text', 'select', 'number', 'date', 'boolean'],
  range: ['number'],
  regex: ['string', 'text'],
  reference_integrity: ['reference', 'select'],
  threshold: ['number'],
  nl_check: null,
  anomaly_detect: null,
};

export function isRuleCompatibleWithField(ruleType, fieldType) {
  const allowed = RULE_FIELD_TYPE_COMPAT[ruleType];
  if (!allowed) return true;
  return allowed.includes(fieldType);
}
