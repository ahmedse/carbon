/** Operator-facing step failure copy (RULE_23) — hide raw tracebacks by default. */
export function humanizeStepError(raw) {
  if (!raw || typeof raw !== 'string') {
    return { summary: 'This step failed.', detail: '' };
  }
  const text = raw.trim();
  if (!text) return { summary: 'This step failed.', detail: '' };

  if (/file write blocked in sandbox/i.test(text)) {
    return {
      summary: 'Chart code tried to save a file to disk. Charts stay in memory — use Rerun.',
      detail: text,
    };
  }
  if (/network access blocked in sandbox/i.test(text)) {
    return {
      summary: 'This step tried to reach the network, which the sandbox blocks.',
      detail: text,
    };
  }

  const lines = text.split('\n').map((l) => l.trim()).filter(Boolean);
  const last = lines[lines.length - 1] || text;
  const looksTrace = /traceback \(most recent call last\)/i.test(text) || lines.length > 4;
  if (looksTrace) {
    const short = last.replace(/^[A-Za-z_.]*Error:\s*/, '').trim() || last;
    return { summary: short.length > 220 ? `${short.slice(0, 200)}…` : short, detail: text };
  }
  if (text.length > 280) {
    return { summary: `${text.slice(0, 240)}…`, detail: text };
  }
  return { summary: text, detail: '' };
}
