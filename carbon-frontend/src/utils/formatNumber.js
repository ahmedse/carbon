/**
 * Numeric display formatting — locale-aware (ADR-0018 §6).
 *
 * Numbers are formatted with the platform `Intl` locale, never with `t()` and
 * never by concatenating a raw API value into a label. The API returns strings
 * like `"80.0000"` / `"500000.0000"`; rendering those verbatim is what produced
 * `80.0000%` and `500000.0000 kgCO2e` in the coverage UI. Every number shown to
 * a person goes through this single source of truth so precision, grouping and
 * the locale stay consistent across pages.
 *
 * Arabic keeps Latin digits (`ar-EG-u-nu-latn`) — the agreed enterprise-data
 * convention (ADR-0018): `80` not `٨٠`.
 */
import i18n from '../i18n';

function resolveLocale(lang) {
  const l = String(lang || i18n?.language || 'en').toLowerCase();
  return l.startsWith('ar') ? 'ar-EG-u-nu-latn' : 'en-US';
}

function toNumber(value) {
  if (value === null || value === undefined || value === '') return null;
  const n = typeof value === 'number' ? value : Number(value);
  return Number.isFinite(n) ? n : null;
}

/**
 * Format a number for display. Trailing zeros are trimmed (`80.0000` → `80`,
 * `44.4400` → `44.44`) and thousands are grouped (`500000` → `500,000`).
 *
 * @param {number|string} value
 * @param {{ lang?: string, maximumFractionDigits?: number, minimumFractionDigits?: number, fallback?: string }} [options]
 */
export function formatNumber(value, options = {}) {
  const {
    lang,
    maximumFractionDigits = 2,
    minimumFractionDigits = 0,
    fallback = '—',
  } = options;
  const n = toNumber(value);
  if (n === null) return fallback;
  return new Intl.NumberFormat(resolveLocale(lang), {
    maximumFractionDigits,
    minimumFractionDigits,
  }).format(n);
}

/**
 * Format a percentage value that is already expressed in percent units
 * (`44.44` → `44.44%`, `80.0000` → `80%`, `0` → `0%`). This is NOT
 * `style: 'percent'` — the API supplies percent units, not a 0–1 fraction.
 */
export function formatPercent(value, options = {}) {
  const { fallback = '—', ...rest } = options;
  const formatted = formatNumber(value, { ...rest, fallback });
  return formatted === fallback ? fallback : `${formatted}%`;
}
