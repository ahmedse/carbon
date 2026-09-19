/**
 * Split Agent final_response markdown into operator prose vs technical dumps.
 *
 * Synthesis often appends fenced JSON/Python (skill args, sort snippets).
 * Output Answer should lead with the human summary; dumps go behind a
 * collapsed "Technical details" section (Screen Spec / TASK-QA G5).
 */

const FENCE_RE = /```([^\n`]*)\r?\n([\s\S]*?)```/g;

const TECH_LANGS = new Set([
  '',
  'json',
  'javascript',
  'js',
  'typescript',
  'ts',
  'python',
  'py',
  'bash',
  'shell',
  'sh',
  'sql',
]);

const TOOLISH_RE = /("api_name"|"tool_name"|"tool_args"|sort_values|invoke_skill|call_host_api|analyze_employees)/i;

/**
 * @param {string|null|undefined} markdown
 * @returns {{ prose: string, appendix: string, hasAppendix: boolean }}
 */
export function splitAnswerAppendix(markdown) {
  if (!markdown || typeof markdown !== 'string') {
    return { prose: '', appendix: '', hasAppendix: false };
  }
  const appendixParts = [];
  const prose = markdown
    .replace(FENCE_RE, (full, lang, body) => {
      const l = String(lang || '').trim().toLowerCase();
      if (TECH_LANGS.has(l) || TOOLISH_RE.test(body)) {
        appendixParts.push(full.trim());
        return '\n';
      }
      return full;
    })
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim();

  if (!prose && appendixParts.length) {
    // Nothing but fences — show original so we never blank the Answer.
    return { prose: markdown.trim(), appendix: '', hasAppendix: false };
  }

  return {
    prose,
    appendix: appendixParts.join('\n\n'),
    hasAppendix: appendixParts.length > 0,
  };
}
