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
  nl_check: 'Pulse NL Check',
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
  nl_check: 'Pulse NL Check',
  suggest: 'Pulse Suggestion',
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
