/**
 * Host write → Output actions (same contract as Chat message actions).
 * Prefer plan.output_actions from the API; fall back to scanning step tool_output.
 */
import { isSafeInternalRoute } from '../utils/navigation';

function layersFromToolOutput(toolOutput) {
  if (!toolOutput || typeof toolOutput !== 'object') return [];
  const layers = [toolOutput];
  if (toolOutput.data && typeof toolOutput.data === 'object') layers.push(toolOutput.data);
  let nested = toolOutput.result;
  if (typeof nested === 'string') {
    try {
      nested = JSON.parse(nested);
    } catch {
      nested = null;
    }
  }
  if (nested && typeof nested === 'object') {
    layers.push(nested);
    if (nested.data && typeof nested.data === 'object') layers.push(nested.data);
  }
  return layers;
}

export function collectNavigateActionsFromSteps(steps = []) {
  const actions = [];
  const seen = new Set();
  (Array.isArray(steps) ? steps : []).forEach((step) => {
    if (!step || step.status === 'failed') return;
    layersFromToolOutput(step.tool_output).forEach((layer) => {
      if (layer.action !== 'navigate') return;
      const route = String(layer.route || '').trim();
      if (!isSafeInternalRoute(route) || seen.has(route)) return;
      seen.add(route);
      actions.push({
        type: 'navigate',
        route,
        label: String(layer.label || 'Open').trim() || 'Open',
        summary: String(layer.summary || '').trim(),
      });
    });
  });
  return actions;
}

/**
 * @param {object|null} plan
 * @param {Array} [runSteps]
 * @returns {Array<{type:string,route:string,label:string,summary:string}>}
 */
export function resolveOutputActions(plan, runSteps = []) {
  const fromApi = Array.isArray(plan?.output_actions) ? plan.output_actions : [];
  const normalized = fromApi
    .filter((a) => a && a.type === 'navigate' && isSafeInternalRoute(a.route))
    .map((a) => ({
      type: 'navigate',
      route: a.route,
      label: String(a.label || 'Open').trim() || 'Open',
      summary: String(a.summary || '').trim(),
    }));
  if (normalized.length) return normalized;
  const steps = (Array.isArray(runSteps) && runSteps.length)
    ? runSteps
    : (Array.isArray(plan?.steps) ? plan.steps : []);
  return collectNavigateActionsFromSteps(steps);
}
