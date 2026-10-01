function norm(value) {
  return String(value || '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '');
}

/**
 * Suggest CSV header → declared field map.
 * `aliases` is { fieldName: string[] } supplied by the door (People / Catalog).
 */
export function suggestColumnMap(headers = [], fields = [], aliases = {}) {
  const unused = new Set(fields.map((f) => f.name));
  const columns = {};
  headers.forEach((header) => {
    const key = norm(header);
    let hit = fields.find((f) => unused.has(f.name) && (norm(f.name) === key || norm(f.label) === key));
    if (!hit) {
      hit = fields.find((f) => {
        if (!unused.has(f.name)) return false;
        return (aliases[f.name] || []).some((alias) => norm(alias) === key);
      });
    }
    if (hit) {
      columns[header] = hit.name;
      unused.delete(hit.name);
    } else {
      columns[header] = '';
    }
  });
  return columns;
}

export function unmappedRequired(columns, fields = []) {
  const mapped = new Set(Object.values(columns || {}).filter(Boolean));
  return fields.filter((f) => f.required && !mapped.has(f.name)).map((f) => f.name);
}

/**
 * True when every declared field name appears as a CSV header (identity layout).
 * Extra headers are allowed; alias-only layouts return false.
 */
export function headersMatchIdentity(headers = [], fields = []) {
  if (!fields.length) return false;
  const headerSet = new Set(headers.map((h) => String(h)));
  return fields.every((f) => headerSet.has(f.name));
}

/**
 * True when mapping.columns is a full identity map for declared fields.
 */
export function isIdentityMapping(columns = {}, fields = []) {
  if (!fields.length) return false;
  return fields.every((f) => columns[f.name] === f.name);
}

/**
 * Pick the official identity InboundTemplate for this target (People · *).
 * Prefers an exact identity column map; falls back to the People · name for the key.
 */
export function pickOfficialIdentityTemplate(templates = [], fields = [], targetKey = '') {
  const list = Array.isArray(templates) ? templates : [];
  const forKey = targetKey
    ? list.filter((t) => t && t.target_key === targetKey)
    : list;
  const identityHit = forKey.find((t) => isIdentityMapping(t?.mapping?.columns || {}, fields));
  if (identityHit) return identityHit;
  return forKey.find((t) => String(t?.name || '').startsWith('People · ')) || null;
}
