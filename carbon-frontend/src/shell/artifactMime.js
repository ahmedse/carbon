/** Artifact preview mime allowlist — Office Open XML must NOT be text-previewable. */
export const PREVIEWABLE_MIME_ALLOWLIST = new Set([
  'text/plain',
  'text/csv',
  'text/markdown',
  'text/x-markdown',
  'application/json',
  'application/yaml',
  'application/x-yaml',
  'text/yaml',
  'text/x-yaml',
  'text/xml',
  'application/xml',
]);

/** True only for explicit text-like mimes (never substring-match openxmlformats). */
export function isPreviewableMime(mime) {
  const m = (mime || '').toLowerCase().split(';')[0].trim();
  if (!m) return false;
  if (PREVIEWABLE_MIME_ALLOWLIST.has(m)) return true;
  if (m.startsWith('text/') && !m.includes('html')) return true;
  return false;
}

export function isImageMime(mime) {
  const m = (mime || '').toLowerCase();
  return /image\/|png|jpeg|jpg|gif|webp/.test(m);
}
