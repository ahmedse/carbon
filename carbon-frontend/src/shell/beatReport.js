/** Operator facts for one execution beat: heal, failure, tool. */

export function readHealNote(step) {
  const direct = String(step?.heal_note || '').trim();
  if (direct) return direct;
  const nested = step?.tool_output?.self_heal;
  if (nested && typeof nested === 'object') return String(nested.note || '').trim();
  return '';
}

/**
 * @param {object|null|undefined} step
 * @returns {{ failed: boolean, healed: boolean, writeStopped: boolean, retries: number, heal: string, error: string }}
 */
export function beatSituation(step) {
  const retries = Number(step?.retry_count) || 0;
  const heal = readHealNote(step);
  const mutation = Boolean(step?.is_mutation);
  const failed = step?.status === 'failed';
  const healed = !failed && !mutation && (retries > 0 || Boolean(heal));
  const writeStopped = !failed && mutation && retries > 0;
  return {
    failed,
    healed,
    writeStopped,
    retries,
    heal,
    error: String(step?.error || step?.error_message || '').trim(),
  };
}
