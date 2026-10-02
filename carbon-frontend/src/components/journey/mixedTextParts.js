// Pure helpers for MixedText. Kept out of the component file so fast refresh
// sees a components-only module.

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

/**
 * Split a sentence into plain and glossary-term parts. Terms come from the
 * pack's allowlist and are matched longest-first so "data quality tier" wins
 * over "tier". Case-insensitive; the original span text is preserved.
 */
export function splitMixed(text, glossary) {
  const source = String(text ?? '');
  const terms = (Array.isArray(glossary) ? glossary : [])
    .map((term) => String(term || '').trim())
    .filter(Boolean)
    .sort((a, b) => b.length - a.length);
  if (!source || terms.length === 0) return [{ text: source, term: false }];

  const pattern = new RegExp(`(${terms.map(escapeRegExp).join('|')})`, 'gi');
  return source.split(pattern).filter((part) => part !== '').map((part) => ({
    text: part,
    term: terms.some((term) => term.toLowerCase() === part.toLowerCase()),
  }));
}
