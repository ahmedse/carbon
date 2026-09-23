// Shared graph copy helpers. Geometry stays in SVG user space (always LTR).
// Words are HTML, with each script run isolated so an Arabic page cannot
// reorder a date or clip the start of a Latin word.

const ARABIC = /[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]/;

/** 'rtl' when the string contains Arabic script, otherwise 'ltr'. */
export function dominantDir(text) {
  return ARABIC.test(String(text || '')) ? 'rtl' : 'ltr';
}

/**
 * Split text into script runs. Latin, digits, and dates stay one LTR island
 * inside an Arabic sentence.
 * @returns {Array<{ text: string, dir: 'rtl'|'ltr' }>}
 */
export function scriptRuns(text) {
  const s = String(text || '');
  if (!s) return [];
  const re = /([\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)|([^\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+)/g;
  const runs = [];
  let match = re.exec(s);
  while (match) {
    runs.push({ text: match[0], dir: match[1] ? 'rtl' : 'ltr' });
    match = re.exec(s);
  }
  return runs;
}

/**
 * Pointer delta → graph coordinate. A zero or non-finite zoom must not
 * produce NaN (that collapses the node and trips the error screen).
 */
export function dragPoint(origin, delta, zoom) {
  const base = Number.isFinite(origin) ? origin : 0;
  const z = Number.isFinite(zoom) && zoom > 0 ? zoom : 1;
  if (!Number.isFinite(delta)) return base;
  const next = base + delta / z;
  return Number.isFinite(next) ? next : base;
}

/** Drop a geometry override that would paint translate(NaN). */
export function finiteGeometry(node, override) {
  if (!override) return node;
  const merged = { ...node, ...override };
  const nums = [merged.x, merged.y, merged.w, merged.h];
  if (nums.some((v) => !Number.isFinite(v))) return node;
  return merged;
}
