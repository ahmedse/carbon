import { apiFetch, authFetch } from './api';

const ROOT = 'inbound/';

export function fetchInboundCartridges(token) {
  return apiFetch(`${ROOT}cartridges/`, { token });
}

export function fetchInboundCartridge(token, id) {
  return apiFetch(`${ROOT}cartridges/${id}/`, { token });
}

export function createInboundCartridge(token, body) {
  return apiFetch(`${ROOT}cartridges/`, { method: 'POST', token, body });
}

export function updateInboundCartridge(token, id, body) {
  return apiFetch(`${ROOT}cartridges/${id}/`, { method: 'PATCH', token, body });
}

export function deleteInboundCartridge(token, id) {
  return apiFetch(`${ROOT}cartridges/${id}/`, { method: 'DELETE', token });
}

export function fetchInboundTargets(token, kind = 'typed_object') {
  const qs = kind ? `?kind=${encodeURIComponent(kind)}` : '';
  return apiFetch(`${ROOT}batches/targets/${qs}`, { token });
}

export function fetchInboundBatches(token, kind = 'typed_object') {
  const qs = kind ? `?kind=${encodeURIComponent(kind)}` : '';
  return apiFetch(`${ROOT}batches/${qs}`, { token });
}

export function fetchInboundBatch(token, id) {
  return apiFetch(`${ROOT}batches/${id}/`, { token });
}

export function createInboundBatch(token, { kind, target_key }) {
  return apiFetch(`${ROOT}batches/`, {
    method: 'POST',
    token,
    body: { kind, target_key },
  });
}

export async function uploadInboundFile(token, id, file, encoding) {
  const form = new FormData();
  form.append('file', file);
  if (encoding) form.append('encoding', encoding);
  const res = await authFetch(`${ROOT}batches/${id}/file/`, {
    method: 'POST',
    token,
    body: form,
    timeoutMs: 60000,
  });
  const data = await res.json();
  if (!res.ok) {
    const err = new Error(data.detail || `Upload failed (${res.status})`);
    err.status = res.status;
    throw err;
  }
  return data;
}

export function saveInboundMapping(token, id, mapping) {
  return apiFetch(`${ROOT}batches/${id}/mapping/`, {
    method: 'PUT',
    token,
    body: mapping,
  });
}

export function smokeInboundBatch(token, id) {
  return apiFetch(`${ROOT}batches/${id}/smoke/`, {
    method: 'POST',
    token,
    body: {},
    timeoutMs: 60000,
  });
}

export function commitInboundBatch(token, id, allow_partial = false) {
  return apiFetch(`${ROOT}batches/${id}/commit/`, {
    method: 'POST',
    token,
    body: { allow_partial },
    timeoutMs: 60000,
  });
}

export async function downloadInboundRejects(token, id) {
  const res = await authFetch(`${ROOT}batches/${id}/rejects/`, { token, timeoutMs: 60000 });
  if (!res.ok) throw new Error(`Rejects download failed (${res.status})`);
  return res.blob();
}

export function fetchInboundTemplates(token, { kind, target_key } = {}) {
  const params = new URLSearchParams();
  if (kind) params.set('kind', kind);
  if (target_key) params.set('target_key', target_key);
  const qs = params.toString();
  return apiFetch(`${ROOT}templates/${qs ? `?${qs}` : ''}`, { token });
}

export function saveInboundTemplate(token, { name, kind, target_key, mapping }) {
  return apiFetch(`${ROOT}templates/`, {
    method: 'POST',
    token,
    body: { name, kind, target_key, mapping },
  });
}
