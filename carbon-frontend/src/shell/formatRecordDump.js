/**
 * Turn a catalog field dump into a markdown table.
 * "Runs (2): id=56, status=committed; id=57, ..." is not an answer.
 */

function presentCell(value) {
  const raw = String(value || '').replace(/\|/g, ' ').replace(/\s+/g, ' ').trim();
  if (raw.length >= 11 && raw[4] === '-' && raw[7] === '-' && raw[10] === 'T') {
    return raw.slice(0, 10);
  }
  return raw;
}

function presentHeader(field) {
  const parts = String(field || '').split('_').filter(Boolean);
  if (!parts.length) return field;
  return parts.map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(' ');
}

function parseRecord(chunk) {
  const record = {};
  const bits = chunk.split(/,\s+/);
  for (const bit of bits) {
    const eq = bit.indexOf('=');
    if (eq < 1) return null;
    const key = bit.slice(0, eq).trim();
    if (!/^[a-z][a-z0-9_]*$/i.test(key)) return null;
    record[key] = bit.slice(eq + 1).trim();
  }
  return Object.keys(record).length ? record : null;
}

/**
 * @param {string} block one paragraph
 * @returns {string|null} markdown table, or null when this is prose
 */
export function dumpBlockToTable(block) {
  const flat = String(block || '').replace(/\s+/g, ' ').trim();
  const match = flat.match(/^(.{1,80}?)\s+\((\d+)\):\s+(.+?)\.?$/);
  if (!match || !match[3].includes('=')) return null;
  const rows = match[3].split(/;\s+/).map(parseRecord);
  if (!rows.length || rows.some((row) => !row)) return null;
  const fields = Object.keys(rows[0]);
  if (fields.length < 2) return null;
  if (!rows.every((row) => fields.every((field) => field in row))) return null;
  const headers = fields.map(presentHeader);
  const lines = [
    `${match[1]} (${rows.length} of ${match[2]})`,
    '',
    `| ${headers.join(' | ')} |`,
    `| ${headers.map(() => '---').join(' | ')} |`,
    ...rows.map((row) => `| ${fields.map((field) => presentCell(row[field])).join(' | ')} |`),
  ];
  return lines.join('\n');
}

/**
 * @param {string} markdown
 * @returns {string}
 */
export function presentRecordDump(markdown) {
  if (!markdown || typeof markdown !== 'string' || !markdown.includes('=')) return markdown || '';
  return markdown
    .split(/\n{2,}/)
    .map((block) => dumpBlockToTable(block) || block)
    .join('\n\n');
}
