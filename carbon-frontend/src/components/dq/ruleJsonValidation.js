export const RULE_TYPES = [
  'not_null', 'unique', 'allowed_values', 'range', 'regex',
  'reference_integrity', 'threshold', 'nl_check', 'anomaly_detect',
];

export const RULE_LEVELS = ['field', 'business'];

export const DIMENSION_CODES = [
  'completeness', 'validity', 'accuracy', 'consistency', 'timeliness',
  'uniqueness', 'integrity', 'reasonability',
];

export const SEVERITY_VALUES = ['info', 'warn', 'error'];

/**
 * Client-side structural validation mirroring backend rule_schema.validate_definition.
 * Returns [{field, code, message}] - empty array = looks valid.
 */
export function validateDefinitionClient(d) {
  const errors = [];
  if (!d || typeof d !== 'object' || Array.isArray(d)) {
    return [{ field: '_root', code: 'invalid_type', message: 'definition must be a JSON object' }];
  }
  if (d.schema_version !== 1) {
    errors.push({ field: 'schema_version', code: 'invalid_value', message: 'schema_version must be 1' });
  }
  if (!d.name || typeof d.name !== 'string' || !d.name.trim()) {
    errors.push({ field: 'name', code: 'required', message: 'name is required and must be a non-empty string' });
  }
  if (!RULE_LEVELS.includes(d.level)) {
    errors.push({ field: 'level', code: 'invalid_value', message: `level must be one of ${RULE_LEVELS.join(', ')}` });
  }
  if (!DIMENSION_CODES.includes(d.dimension)) {
    errors.push({ field: 'dimension', code: 'invalid_value', message: `dimension must be one of ${DIMENSION_CODES.join(', ')}` });
  }
  if (!RULE_TYPES.includes(d.type)) {
    errors.push({ field: 'type', code: 'invalid_value', message: `type must be one of ${RULE_TYPES.join(', ')}` });
  }
  if (!SEVERITY_VALUES.includes(d.severity)) {
    errors.push({ field: 'severity', code: 'invalid_value', message: `severity must be one of ${SEVERITY_VALUES.join(', ')}` });
  }
  if (typeof d.active !== 'boolean') {
    errors.push({ field: 'active', code: 'invalid_type', message: 'active must be a boolean' });
  }
  // ADR-0006: bindings are optional - rules are standalone; bindings applied at data product level
  const bindings = d.bindings;
  if (bindings != null) {
    if (!Array.isArray(bindings)) {
      errors.push({ field: 'bindings', code: 'invalid_type', message: 'bindings must be a list of {table, field} objects' });
    } else {
      bindings.forEach((b, i) => {
        if (!b || typeof b !== 'object' || !b.table || typeof b.table !== 'string') {
          errors.push({ field: `bindings[${i}].table`, code: 'required', message: 'binding table is required and must be a string' });
        }
      });
    }
  }
  if (d.params !== undefined && (typeof d.params !== 'object' || d.params === null || Array.isArray(d.params))) {
    errors.push({ field: 'params', code: 'invalid_type', message: 'params must be a JSON object' });
  }
  if (d.enforcement && d.enforcement.on_write === true && (d.type === 'nl_check' || d.type === 'anomaly_detect')) {
    errors.push({ field: 'enforcement.on_write', code: 'invalid_value', message: `enforcement.on_write cannot be true for ${d.type} rules` });
  }
  return errors;
}

/**
 * Normalize server-side error envelopes into [{field, code, message}] rows.
 *
 * Handles three shapes:
 *   1. DRF envelope (catalog.exceptions.data_trust_exception_handler):
 *      { error, message, timestamp, path, details?, suggested_action? }
 *      where `details` = exc.detail (a dict) — so field-level errors live under
 *      `payload.details` (details.definition, details.field_assignments_write, …),
 *      NOT `payload.definition`.
 *   2. AppFeedback envelope (core.feedback.AppFeedback):
 *      { code, severity, title, detail, reasons[], remediation[], context }
 *   3. Legacy direct fields: payload.definition / payload.error.
 */
export function normalizeServerErrors(payload) {
  const list = [];

  // Coerce a single server error value (string | array | nested object) into rows.
  const pushValue = (value, defaultField) => {
    if (Array.isArray(value)) {
      value.forEach((e) => {
        if (typeof e === 'string') {
          list.push({ field: defaultField, code: 'server', message: e });
        } else if (e && typeof e === 'object') {
          list.push({
            field: e.field || defaultField,
            code: e.code || 'server',
            message: e.message || JSON.stringify(e),
          });
        }
      });
    } else if (typeof value === 'string' && value.trim()) {
      list.push({ field: defaultField, code: 'server', message: value });
    } else if (value && typeof value === 'object') {
      // DRF nested: { field: [errors] } or { field: "error" }.
      Object.entries(value).forEach(([k, v]) => pushValue(v, k));
    }
  };

  // 1. DRF envelope — field errors live under payload.details (NOT payload.definition).
  const details = payload?.details;
  if (Array.isArray(details)) {
    pushValue(details, '_root');
  } else if (details && typeof details === 'object') {
    pushValue(details.definition, 'definition');
    // Drift guard / silent binding-drop rejection → actionable row.
    pushValue(details.field_assignments_write, 'field_assignments_write');
    Object.entries(details).forEach(([k, v]) => {
      if (k === 'definition' || k === 'field_assignments_write') return;
      pushValue(v, k);
    });
  } else {
    // 2. Legacy direct definition field (no details envelope).
    pushValue(payload?.definition, 'definition');
  }

  // 3. AppFeedback shape: { code, severity, title, detail, reasons[], ... }.
  if (typeof payload?.detail === 'string' || Array.isArray(payload?.reasons)) {
    if (typeof payload?.detail === 'string' && payload.detail.trim()) {
      list.push({ field: '_root', code: payload.code || 'server', message: payload.detail });
    }
    if (Array.isArray(payload?.reasons)) {
      payload.reasons.forEach((r) => {
        if (typeof r === 'string') {
          list.push({ field: '_root', code: payload.code || 'server', message: r });
        } else if (r && typeof r === 'object') {
          list.push({
            field: r.field || '_root',
            code: r.code || payload.code || 'server',
            message: r.message || r.detail || JSON.stringify(r),
          });
        }
      });
    }
    if (list.length === 0) {
      const fallback = payload?.title || payload?.message || payload?.detail;
      if (fallback) list.push({ field: '_root', code: payload.code || 'server', message: fallback });
    }
  }

  // 4. Final catch-all: legacy payload.error string.
  if (list.length === 0 && typeof payload?.error === 'string') {
    list.push({ field: '_root', code: 'server', message: payload.error });
  }

  return list;
}

export const EMPTY_DEFINITION_TEMPLATE = `{
  "schema_version": 1,
  "name": "",
  "level": "field",
  "dimension": "validity",
  "type": "not_null",
  "severity": "warn",
  "active": true,
  "bindings": [],
  "params": {},
  "enforcement": { "on_write": true },
  "description": ""
}`;
