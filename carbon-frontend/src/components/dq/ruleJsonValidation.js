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
 * Format server-side rule_schema errors (DRF returns {definition: [errors]}).
 */
export function normalizeServerErrors(payload) {
  const list = [];
  const raw = payload?.definition;
  if (Array.isArray(raw)) {
    raw.forEach((e) => {
      if (typeof e === 'string') list.push({ field: 'definition', code: 'server', message: e });
      else if (e && typeof e === 'object') list.push({ field: e.field || 'definition', code: e.code || 'server', message: e.message || JSON.stringify(e) });
    });
  } else if (typeof raw === 'string') {
    list.push({ field: 'definition', code: 'server', message: raw });
  } else if (typeof payload?.error === 'string') {
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
