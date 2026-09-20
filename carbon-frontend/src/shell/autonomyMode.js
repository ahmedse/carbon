/** Operator autonomy preference (Track D — UX-R3).
 *
 * localStorage key `carbon-ai-autonomy`. Does **not** bypass RULE_21 write
 * consent — only changes how aggressively the Run/consent UI surfaces detail.
 *
 * - careful: step list open by default; contract emphasizes approvals
 * - balanced: product default
 * - fast: collapse settled lists; still pause on writes
 */
export const AUTONOMY_KEY = 'carbon-ai-autonomy';
export const AUTONOMY_MODES = ['careful', 'balanced', 'fast'];

export function readAutonomyMode() {
  try {
    const v = localStorage.getItem(AUTONOMY_KEY);
    if (AUTONOMY_MODES.includes(v)) return v;
  } catch { /* ignore */ }
  return 'balanced';
}

export function writeAutonomyMode(mode) {
  const next = AUTONOMY_MODES.includes(mode) ? mode : 'balanced';
  try {
    localStorage.setItem(AUTONOMY_KEY, next);
  } catch { /* ignore */ }
  return next;
}

/** Whether the Run step list should open by default for this phase. */
export function autonomyDefaultListOpen(mode, { paused = false, awaiting = false, finished = false } = {}) {
  // Consent hero + timeline own the grant moment — do not open the Analyst
  // step wall underneath (Operator calm / Track E).
  if (awaiting) return false;
  if (mode === 'careful') return true;
  if (mode === 'fast') return false;
  if (paused) return mode === 'careful';
  // balanced: open while live-ish, closed when settled
  return !finished;
}
