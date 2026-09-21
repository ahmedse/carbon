/**
 * Date utility functions — locale-aware (ADR-0018 / i18n audit Week 1).
 */
import i18n from '../i18n';

function resolveLocale(lang) {
  const l = lang || i18n.language || 'en';
  return String(l).toLowerCase().startsWith('ar') ? 'ar' : 'en';
}

/**
 * Format a date as relative time in the active (or provided) language.
 * @param {Date|string|number} date
 * @param {string} [lang]
 */
export const formatDistanceToNow = (date, lang) => {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const locale = resolveLocale(lang);
  const now = new Date();
  const diff = now - d;
  const seconds = Math.floor(diff / 1000);
  const minutes = Math.floor(seconds / 60);
  const hours = Math.floor(minutes / 60);
  const days = Math.floor(hours / 24);

  const t = (key, opts) => {
    try {
      return i18n.t(key, { ns: 'ai', lng: locale, ...opts });
    } catch {
      return null;
    }
  };

  if (seconds < 60) return t('justNow') || (locale === 'ar' ? 'الآن' : 'just now');
  if (minutes < 60) {
    return t('minutesAgo', { n: minutes }) || (locale === 'ar' ? `منذ ${minutes} د` : `${minutes}m ago`);
  }
  if (hours < 24) {
    return t('hoursAgo', { n: hours }) || (locale === 'ar' ? `منذ ${hours} س` : `${hours}h ago`);
  }
  if (days < 7) {
    return t('daysAgo', { n: days }) || (locale === 'ar' ? `منذ ${days} ي` : `${days}d ago`);
  }
  return d.toLocaleDateString(locale === 'ar' ? 'ar' : 'en');
};

/**
 * Format date as ISO string
 */
export const formatISODate = (date) => {
  return date.toISOString();
};

/**
 * Format date for display
 * @param {Date|string|number} date
 * @param {object} [options] — Intl options; may include `lang`
 */
export const formatDisplayDate = (date, options = {}) => {
  const { lang, ...intlOpts } = options;
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const locale = resolveLocale(lang);
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    ...intlOpts,
  }).format(d);
};

/**
 * Format datetime for display
 * @param {Date|string|number} date
 * @param {string} [lang]
 */
export const formatDisplayDateTime = (date, lang) => {
  const d = date instanceof Date ? date : new Date(date);
  if (Number.isNaN(d.getTime())) return '';
  const locale = resolveLocale(lang);
  return new Intl.DateTimeFormat(locale === 'ar' ? 'ar' : 'en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  }).format(d);
};
