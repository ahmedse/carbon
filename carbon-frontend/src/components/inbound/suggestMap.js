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
