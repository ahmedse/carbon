// src/apps/healthy/utils.js
// Pure, framework-free helpers for the Healthy Foods Factory screens.
// Kept separate from component files so components export only their component
// (react-refresh/only-export-components) and tests can unit-test these helpers
// without rendering.

/** Churn risk bucket for a rep's churn_probability (0..1). */
export function churnRiskLevel(probability) {
  if (probability == null || Number.isNaN(Number(probability))) {
    return { label: 'No data', color: 'default' };
  }
  if (probability < 0.3) return { label: 'Low risk', color: 'success' };
  if (probability < 0.6) return { label: 'At risk', color: 'warning' };
  return { label: 'High risk', color: 'error' };
}

/** AR collection priority bucket for a risk_score (0..1). */
export function arRiskLevel(score) {
  if (score == null || Number.isNaN(Number(score))) {
    return { label: 'Unknown', color: 'default' };
  }
  if (score < 0.4) return { label: 'Low', color: 'success' };
  if (score < 0.7) return { label: 'Medium', color: 'warning' };
  return { label: 'High', color: 'error' };
}

/** Slow-mover severity for a 4-week demand forecast. */
export function slowMoverSeverity(forecast) {
  if (forecast == null || Number.isNaN(Number(forecast))) return 'unknown';
  if (forecast <= 0) return 'dead';
  if (forecast < 10) return 'slow';
  return 'moving';
}

/** Format a currency amount (whole amounts shown without decimals). */
export function formatCurrency(amount) {
  if (amount == null || Number.isNaN(Number(amount))) return '—';
  const value = Number(amount);
  return value.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    maximumFractionDigits: value % 1 === 0 ? 0 : 2,
  });
}

/** Format a 0..1 probability as a whole percentage. */
export function formatPercent(probability) {
  if (probability == null || Number.isNaN(Number(probability))) return '—';
  return `${Math.round(Number(probability) * 100)}%`;
}

/**
 * Build a CSV payload from loadout sheets (rep + line items).
 * @param {Array} sheets - array of {week_start, rep_code, rep_name, line_items: []}
 * @returns {string} CSV text
 */
export function buildLoadoutCsv(sheets) {
  const header = [
    'week_start',
    'rep_code',
    'rep_name',
    'item_code',
    'item_name',
    'qty_forecast',
    'qty_actual',
    'return_rate_forecast',
  ];
  const rows = [];
  for (const sheet of sheets || []) {
    const items = Array.isArray(sheet.line_items) ? sheet.line_items : [];
    if (items.length === 0) {
      rows.push([sheet.week_start, sheet.rep_code, sheet.rep_name, '', '', '', '', '']);
      continue;
    }
    for (const item of items) {
      rows.push([
        sheet.week_start,
        sheet.rep_code,
        sheet.rep_name,
        item.item_code ?? '',
        item.item_name ?? '',
        item.qty_forecast ?? '',
        item.qty_actual ?? '',
        item.return_rate_forecast ?? '',
      ]);
    }
  }
  const escape = (value) => {
    const s = String(value ?? '');
    if (/[",\n]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };
  return [header, ...rows].map((row) => row.map(escape).join(',')).join('\n');
}
