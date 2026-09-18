// src/api/aiControlPlane.js
// Pulse Control Plane APIs (ADR-0036) — command, evidence, containment, candidates, PDP, budget.
import { apiFetch } from './api';

const BASE = 'ai/pulse/control/';

export function getCommandCenter(token) {
  return apiFetch(`${BASE}command/`, { token });
}

export function getEvidence(token, { runId, conversationId } = {}) {
  const params = new URLSearchParams();
  if (runId) params.set('run_id', runId);
  if (conversationId) params.set('conversation_id', conversationId);
  const qs = params.toString();
  return apiFetch(qs ? `${BASE}evidence/?${qs}` : `${BASE}evidence/`, { token });
}

export function getContainment(token) {
  return apiFetch(`${BASE}containment/`, { token });
}

export function setContainment(token, { level, autonomyCeiling, reason }) {
  return apiFetch(`${BASE}containment/`, {
    token,
    method: 'POST',
    body: {
      level,
      autonomy_ceiling: autonomyCeiling,
      reason,
    },
  });
}

export function getLearningCandidates(token, { limit } = {}) {
  const params = new URLSearchParams();
  if (limit) params.set('limit', String(limit));
  const qs = params.toString();
  return apiFetch(qs ? `${BASE}candidates/?${qs}` : `${BASE}candidates/`, { token });
}

export function pdpDryRun(token, { action, autonomy, objects, processState }) {
  return apiFetch(`${BASE}pdp/dry-run/`, {
    token,
    method: 'POST',
    body: {
      action,
      autonomy,
      objects,
      process_state: processState,
    },
  });
}

export function getBudgetControl(token) {
  return apiFetch(`${BASE}budget/`, { token });
}

export function patchBudgetControl(token, dailyBudgetUsd) {
  return apiFetch(`${BASE}budget/`, {
    token,
    method: 'PATCH',
    body: { daily_budget_usd: dailyBudgetUsd },
  });
}
