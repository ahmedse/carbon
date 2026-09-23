// PV2-5C — pick the Chat/Agent continuity request from ConversationState.

const TERMINAL = new Set(['completed', 'completed_with_gaps', 'failed', 'cancelled']);

/**
 * First open (non-terminal) active plan, else the most recent snapshot.
 * @param {unknown} plans
 * @returns {{ plan_id?: string, title?: string, status?: string, slots?: object } | null}
 */
export function pickOpenActivePlan(plans) {
  const list = Array.isArray(plans)
    ? plans.filter((item) => item && typeof item === 'object')
    : [];
  if (!list.length) return null;
  return list.find((item) => !TERMINAL.has(String(item.status || ''))) || list[0];
}

/**
 * Outcome-facing inherited items for the Agent Run drawer (RULE_23).
 * @param {object|null} plan
 * @returns {{ key: string, value: string }[]}
 */
export function inheritedContextItems(plan) {
  const raw = plan?.inherited_context;
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((item) => item && typeof item === 'object' && item.key && item.value != null && item.value !== '')
    .map((item) => ({ key: String(item.key), value: String(item.value) }));
}
