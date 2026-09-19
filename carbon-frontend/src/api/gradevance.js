// src/api/gradevance.js — GradeVance REST client (professor + student + HITL).

import { apiFetch, authFetch } from './api';

const ROOT = 'gradevance/';

const qs = (params = {}) => {
  const q = new URLSearchParams(
    Object.fromEntries(
      Object.entries(params).filter(([, v]) => v != null && v !== ''),
    ),
  ).toString();
  return q ? `?${q}` : '';
};

export const fetchGradeVanceSummary = (token) =>
  apiFetch(`${ROOT}summary/`, { token });

export const fetchProfiles = (token) =>
  apiFetch(`${ROOT}profiles/`, { token });

export const fetchProfileDetail = (token, packId, version = 1) =>
  apiFetch(
    `${ROOT}profiles/${encodeURIComponent(packId)}/${qs({ profile_version: version })}`,
    { token },
  );

export const fetchKnowledgeBases = (token) =>
  apiFetch(`${ROOT}knowledge-bases/`, { token });

export const fetchDemoExamples = (token) =>
  apiFetch(`${ROOT}examples/`, { token });

export const fetchCourses = (token) =>
  apiFetch(`${ROOT}courses/`, { token });

export const createCourse = (token, body) =>
  apiFetch(`${ROOT}courses/`, { method: 'POST', body, token });

export const fetchCourse = (token, courseId) =>
  apiFetch(`${ROOT}courses/${encodeURIComponent(courseId)}/`, { token });

export const patchCourse = (token, courseId, body) =>
  apiFetch(`${ROOT}courses/${encodeURIComponent(courseId)}/`, {
    method: 'PATCH',
    body,
    token,
  });

export const fetchCourseEnrollments = (token, courseId) =>
  apiFetch(`${ROOT}courses/${encodeURIComponent(courseId)}/enrollments/`, { token });

export const createCourseEnrollment = (token, courseId, body) =>
  apiFetch(`${ROOT}courses/${encodeURIComponent(courseId)}/enrollments/`, {
    method: 'POST',
    body,
    token,
  });

export const fetchAssignments = (token, params = {}) =>
  apiFetch(`${ROOT}assignments/${qs(params)}`, { token });

export const createAssignment = (token, body) =>
  apiFetch(`${ROOT}assignments/`, { method: 'POST', body, token });

export const fetchAssignment = (token, assignmentId) =>
  apiFetch(`${ROOT}assignments/${encodeURIComponent(assignmentId)}/`, { token });

export const patchAssignment = (token, assignmentId, body) =>
  apiFetch(`${ROOT}assignments/${encodeURIComponent(assignmentId)}/`, {
    method: 'PATCH',
    body,
    token,
  });

export const fetchSubmissions = (token, params = {}) =>
  apiFetch(`${ROOT}submissions/${qs(params)}`, { token });

export const submitAndAnalyze = (token, body) =>
  apiFetch(`${ROOT}submissions/`, {
    method: 'POST',
    body: { ...body, analyze: true },
    token,
  });

export const createSubmission = (token, body) =>
  apiFetch(`${ROOT}submissions/`, { method: 'POST', body, token });

export const analyzeSubmission = (token, submissionId) =>
  apiFetch(`${ROOT}submissions/${encodeURIComponent(submissionId)}/analyze/`, {
    method: 'POST',
    body: {},
    token,
  });

export const uploadSubmissionFile = async (token, { assignment, file, analyze = true }) => {
  const form = new FormData();
  form.append('assignment', assignment);
  form.append('file', file);
  if (analyze) form.append('analyze', 'true');
  const res = await authFetch(`${ROOT}submissions/upload/`, {
    method: 'POST',
    body: form,
    token,
    timeoutMs: 60000,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || err.message || `Upload failed (${res.status})`);
  }
  return res.json();
};

export const batchAnalyzeAssignment = (token, assignmentId, body = {}) =>
  apiFetch(`${ROOT}assignments/${encodeURIComponent(assignmentId)}/batch-analyze/`, {
    method: 'POST',
    body,
    token,
  });

export const fetchRuns = (token, params = {}) =>
  apiFetch(`${ROOT}runs/${qs(params)}`, { token });

export const fetchRun = (token, runId) =>
  apiFetch(`${ROOT}runs/${encodeURIComponent(runId)}/`, { token });

export const fetchReviewQueue = (token) =>
  apiFetch(`${ROOT}review-queue/`, { token });

export const postExpertEdit = (token, runId, body) =>
  apiFetch(`${ROOT}runs/${encodeURIComponent(runId)}/edits/`, {
    method: 'POST',
    body,
    token,
  });

export const releaseRun = (token, runId) =>
  apiFetch(`${ROOT}runs/${encodeURIComponent(runId)}/release/`, {
    method: 'POST',
    body: {},
    token,
  });

export const fetchCalibration = (token, params = {}) =>
  apiFetch(`${ROOT}calibration/${qs(params)}`, { token });

export const proposeCalibrationSegmentation = (token, body) =>
  apiFetch(`${ROOT}calibration/segmentation-propose/`, {
    method: 'POST',
    body,
    token,
  });

export const suggestSegmentationSplits = (token, body) =>
  apiFetch(`${ROOT}calibration/suggest-splits/`, {
    method: 'POST',
    body,
    token,
  });

export const fetchLtiStatus = (token) =>
  apiFetch(`${ROOT}lti/status/`, { token });

export const fetchAgsPreview = (token, runId, params = {}) =>
  apiFetch(
    `${ROOT}runs/${encodeURIComponent(runId)}/ags-preview/${qs(params)}`,
    { token },
  );

export const postAgsPassback = (token, runId, body) =>
  apiFetch(`${ROOT}runs/${encodeURIComponent(runId)}/ags-passback/`, {
    method: 'POST',
    body,
    token,
  });

export const previewDeepLink = (token, body) =>
  apiFetch(`${ROOT}lti/deep-link/preview/`, { method: 'POST', body, token });

export const fetchAccessibility = (token) =>
  apiFetch(`${ROOT}accessibility/`, { token });

export const fetchQaSummary = (token, params = {}) =>
  apiFetch(`${ROOT}qa/summary/${qs(params)}`, { token });

export const fetchLtiConfig = (token) =>
  apiFetch(`${ROOT}lti/config/`, { token });

export const fetchAuditExport = (token, runId, params = {}) =>
  apiFetch(
    `${ROOT}runs/${encodeURIComponent(runId)}/audit-export/${qs(params)}`,
    { token },
  );

export const fetchAppeals = (token, params = {}) =>
  apiFetch(`${ROOT}appeals/${qs(params)}`, { token });

export const resolveAppeal = (token, appealId, body) =>
  apiFetch(`${ROOT}appeals/${encodeURIComponent(appealId)}/resolve/`, {
    method: 'POST',
    body,
    token,
  });

export const fetchPublishGate = (token, packId, version = 1, params = {}) =>
  apiFetch(
    `${ROOT}publish-gate/${qs({
      profile_pack_id: packId,
      profile_version: version,
      ...params,
    })}`,
    { token },
  );

export const publishAssignment = (token, assignmentId, body = {}) =>
  apiFetch(`${ROOT}assignments/${encodeURIComponent(assignmentId)}/publish/`, {
    method: 'POST',
    body,
    token,
  });

export const fetchProposals = (token) =>
  apiFetch(`${ROOT}proposals/`, { token });

export const decideProposal = (token, id, decision) =>
  apiFetch(`${ROOT}proposals/${encodeURIComponent(id)}/decide/`, {
    method: 'POST',
    body: { decision },
    token,
  });

export const bumpProposal = (token, id, body = { require_canary: false }) =>
  apiFetch(`${ROOT}proposals/${encodeURIComponent(id)}/bump/`, {
    method: 'POST',
    body,
    token,
  });

export const repinProposal = (token, id, body) =>
  apiFetch(`${ROOT}proposals/${encodeURIComponent(id)}/repin/`, {
    method: 'POST',
    body,
    token,
  });

// ── Student self-service (gradevance/me/*) — Learn app ─────────────
const ME = `${ROOT}me/`;

export const fetchMyCourses = (token) =>
  apiFetch(`${ME}courses/`, { token });

export const joinCourseByCode = (token, entry_code) =>
  apiFetch(`${ME}join/`, {
    method: 'POST',
    body: { entry_code },
    token,
  });

export const fetchMyAssignments = (token, params = {}) =>
  apiFetch(`${ME}assignments/${qs(params)}`, { token });

export const fetchMyAssignment = (token, assignmentId) =>
  apiFetch(`${ME}assignments/${encodeURIComponent(assignmentId)}/`, { token });

export const fetchMySubmissions = (token, params = {}) =>
  apiFetch(`${ME}submissions/${qs(params)}`, { token });

/** POST draft/submit; pass analyze: true for formative coaching run. */
export const createMySubmission = (token, body) =>
  apiFetch(`${ME}submissions/`, {
    method: 'POST',
    body,
    token,
  });

export const patchMySubmission = (token, submissionId, body) =>
  apiFetch(`${ME}submissions/${encodeURIComponent(submissionId)}/`, {
    method: 'PATCH',
    body,
    token,
  });

export const fetchMyRun = (token, runId) =>
  apiFetch(`${ME}runs/${encodeURIComponent(runId)}/`, { token });

export const fetchMyProgress = (token, params = {}) =>
  apiFetch(`${ME}progress/${qs(params)}`, { token });

export const fetchMyAppeals = (token, params = {}) =>
  apiFetch(`${ME}appeals/${qs(params)}`, { token });

export const createMyAppeal = (token, body) =>
  apiFetch(`${ME}appeals/`, {
    method: 'POST',
    body,
    token,
  });

export const withdrawMyAppeal = (token, appealId) =>
  apiFetch(`${ME}appeals/${encodeURIComponent(appealId)}/withdraw/`, {
    method: 'POST',
    body: {},
    token,
  });

export const patchEnrollment = (token, courseId, enrollmentId, body) =>
  apiFetch(
    `${ROOT}courses/${encodeURIComponent(courseId)}/enrollments/${encodeURIComponent(enrollmentId)}/`,
    {
      method: 'PATCH',
      body,
      token,
    },
  );