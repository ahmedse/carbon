// Student-facing copy helpers for Learn (persona wall — no engine jargon by default).

import { LEARN_ACCESS, TEACH_ACCESS, hasCap, expandCapabilities } from '../../capabilities';

/** Known criterion ids → student labels (pack keys stay behind disclosure). */
const CRITERION_LABELS = Object.freeze({
  task_achievement: 'Task achievement',
  coherence_cohesion: 'Coherence & cohesion',
  lexical_resource: 'Lexical resource',
  grammatical_range: 'Grammatical range',
  grammatical_range_accuracy: 'Grammatical range & accuracy',
  content: 'Content',
  reflection: 'Reflection',
  criticality: 'Criticality',
  organisation: 'Organisation',
  organization: 'Organization',
  language: 'Language',
});

const STAGE_LABELS = Object.freeze({
  what: 'What',
  so_what: 'So what',
  now_what: 'Now what',
  WHAT: 'What',
  SO_WHAT: 'So what',
  NOW_WHAT: 'Now what',
});

/** Canonical student status thesaurus (list ↔ desk ↔ progress). */
const STATUS_LABELS = Object.freeze({
  open: 'Open',
  published: 'Open',
  draft: 'Drafted',
  drafted: 'Drafted',
  submitted: 'Submitted',
  released: 'Released',
  unreleased: 'Unreleased',
  complete: 'Complete',
  needs_review: 'Needs review',
  done: 'Done',
  unsaved: 'Unsaved',
});

function titleCaseWords(raw) {
  return String(raw)
    .replace(/[_-]+/g, ' ')
    .trim()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/** Human criterion label — never show raw snake_case as the primary label. */
export function criterionLabel(key) {
  if (key == null || key === '') return '';
  const k = String(key);
  if (CRITERION_LABELS[k]) return CRITERION_LABELS[k];
  if (!/[_-]/.test(k) && k === k.toLowerCase() && k.length < 3) return k;
  if (CRITERION_LABELS[k.toLowerCase()]) return CRITERION_LABELS[k.toLowerCase()];
  return titleCaseWords(k);
}

export function stageLabel(stage) {
  if (stage == null || stage === '') return '—';
  const s = String(stage);
  if (STAGE_LABELS[s]) return STAGE_LABELS[s];
  const lower = s.toLowerCase();
  if (STAGE_LABELS[lower]) return STAGE_LABELS[lower];
  return titleCaseWords(s);
}

/** Student-facing status chip text. */
export function statusLabel(status) {
  if (status == null || status === '') return 'Open';
  const key = String(status).toLowerCase();
  return STATUS_LABELS[key] || titleCaseWords(status);
}

export function statusChipColor(status) {
  switch ((status || '').toLowerCase()) {
    case 'released':
      return 'success';
    case 'submitted':
    case 'complete':
    case 'done':
      return 'info';
    case 'drafted':
    case 'draft':
      return 'default';
    case 'open':
    case 'published':
      return 'primary';
    case 'needs_review':
      return 'warning';
    case 'unsaved':
      return 'warning';
    default:
      return 'default';
  }
}

function capKeys(rawCapabilities) {
  if (!rawCapabilities) return [];
  const list = Array.isArray(rawCapabilities) ? rawCapabilities : [...rawCapabilities];
  return list.map((c) => (typeof c === 'string' ? c : c?.key || c?.capability)).filter(Boolean);
}

/**
 * Role-aware default home when landing would be empty Platform Home.
 * Preserve remembered non-home paths and admin / multi-app homes.
 *
 * @param {string} path — candidate landing (often '/' or remembered route)
 * @param {{ capabilities?: unknown, isAdmin?: boolean, isGlobalAdmin?: boolean }} opts
 * @returns {string}
 */
export function resolveRoleAwareHome(path, opts = {}) {
  const candidate = path || '/';
  const isHome = candidate === '/' || candidate === '/dashboard';
  if (!isHome) return candidate;

  if (opts.isAdmin || opts.isGlobalAdmin) return candidate;

  const expanded = expandCapabilities(capKeys(opts.capabilities));
  if (expanded.has('*')) return candidate;

  const learn = hasCap(expanded, LEARN_ACCESS);
  const teach = hasCap(expanded, TEACH_ACCESS);

  if (learn && !teach) return '/learn';
  if (teach && !learn) return '/teach';
  return candidate;
}

/** Prefer strengths; then most recent formative coaching run. */
export function pickLatestCoaching(submissions = []) {
  const rows = submissions
    .map((s) => {
      const latest = s.latest_run && typeof s.latest_run === 'object' ? s.latest_run : null;
      const coaching = latest?.coaching || s.coaching || s.run?.coaching || null;
      if (!coaching) return null;
      const hasStrengths = Array.isArray(coaching.strengths) && coaching.strengths.length > 0;
      const hasDiag = Array.isArray(coaching.diagnosis_actions) && coaching.diagnosis_actions.length > 0;
      if (!hasStrengths && !hasDiag) return null;
      const created =
        latest?.created_at
        || s.updated_at
        || s.created_at
        || '';
      return {
        submission: s,
        coaching,
        assignmentId: s.assignment || s.assignment_id,
        title: s.assignment_title || s.title,
        created,
        hasStrengths,
      };
    })
    .filter(Boolean);

  rows.sort((a, b) => {
    if (a.hasStrengths !== b.hasStrengths) return a.hasStrengths ? -1 : 1;
    return String(b.created).localeCompare(String(a.created));
  });
  return rows[0] || null;
}

/** Resolve run id from submission list payload (latest_run object preferred). */
export function resolveSubmissionRunId(submission) {
  if (!submission) return null;
  const latest = submission.latest_run;
  if (latest && typeof latest === 'object' && latest.id) return latest.id;
  if (typeof latest === 'string' && latest) return latest;
  if (submission.latest_run_id) return submission.latest_run_id;
  const run = submission.run;
  if (run && typeof run === 'object' && run.id) return run.id;
  if (typeof run === 'string' && run) return run;
  return null;
}
