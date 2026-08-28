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

// ── i18n label helpers (I18N-3) ──────────────────────────────────────────────
// The `*_LABELS` maps above stay as ENGLISH strings: they are also consumed by
// out-of-scope pages that do not use `t()` yet (inspector/tabs/ruleTabs.jsx,
// pages/catalog/tabs/DQRulesTab.jsx). Migrated pages resolve display labels
// through these key maps + helpers instead, so every rendered label goes
// through `t()`. Keys are prefix-free and live in the `dq` namespace.
export const RULE_TYPE_LABEL_KEYS = {
  not_null: 'ruleType.notNull',
  unique: 'ruleType.unique',
  allowed_values: 'ruleType.allowedValues',
  range: 'ruleType.range',
  regex: 'ruleType.regex',
  reference_integrity: 'ruleType.referenceIntegrity',
  threshold: 'ruleType.threshold',
  nl_check: 'ruleType.nlCheck',
  anomaly_detect: 'ruleType.anomalyDetect',
};

export const RULE_LEVEL_LABEL_KEYS = {
  field_validation: 'ruleLevel.fieldValidation',
  business_rule: 'ruleLevel.businessRule',
};

export const DIMENSION_LABEL_KEYS = {
  completeness: 'dimension.completeness',
  validity: 'dimension.validity',
  accuracy: 'dimension.accuracy',
  consistency: 'dimension.consistency',
  timeliness: 'dimension.timeliness',
  uniqueness: 'dimension.uniqueness',
  integrity: 'dimension.integrity',
  reasonability: 'dimension.reasonability',
};

export const SEVERITY_LABEL_KEYS = {
  info: 'severity.info',
  warn: 'severity.warning',
  error: 'severity.error',
};

export const JOB_TYPE_LABEL_KEYS = {
  rule_run: 'jobType.ruleRun',
  profile: 'jobType.profile',
  freshness: 'jobType.freshness',
  schema: 'jobType.schemaSnapshot',
  nl_check: 'jobType.nlCheck',
  suggest: 'jobType.suggestion',
  anomaly: 'jobType.anomalyScan',
};

export const JOB_STATUS_LABEL_KEYS = {
  queued: 'jobStatus.queued',
  running: 'jobStatus.running',
  done: 'jobStatus.done',
  failed: 'jobStatus.failed',
  canceled: 'jobStatus.canceled',
};

export const FIELD_TYPE_LABEL_KEYS = {
  string: 'fieldType.string',
  text: 'fieldType.text',
  number: 'fieldType.number',
  date: 'fieldType.date',
  boolean: 'fieldType.boolean',
  select: 'fieldType.select',
  multiselect: 'fieldType.multiselect',
  file: 'fieldType.file',
  reference: 'fieldType.reference',
};

export const ruleTypeLabel = (t, key) => t(RULE_TYPE_LABEL_KEYS[key] || key);
export const ruleLevelLabel = (t, key) => t(RULE_LEVEL_LABEL_KEYS[key] || key);
export const dimensionLabel = (t, key) => t(DIMENSION_LABEL_KEYS[key] || key);
export const severityLabel = (t, key) => t(SEVERITY_LABEL_KEYS[key] || key);
export const jobTypeLabel = (t, key) => t(JOB_TYPE_LABEL_KEYS[key] || key);
export const jobStatusLabel = (t, key) => t(JOB_STATUS_LABEL_KEYS[key] || key);
export const fieldTypeLabel = (t, key) => t(FIELD_TYPE_LABEL_KEYS[key] || key);

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
